# -*- coding: utf-8 -*-
"""
SQM 재고관리 시스템 - 데이터 정합성 검사 리포트 (v7.0.0)
=======================================================

DB 이관 전/운영 중 데이터 무결성을 자동 점검합니다.

검사 항목:
    1. 중복 LOT 번호
    2. 고아 TONBAG (LOT에 연결 안 됨)
    3. 날짜 포맷 불량 (ISO 8601 위반)
    4. 수량/중량 불일치 (음수, 비정상 0)
    5. FK 위반 (외래키 무결성)
    6. 상태 불일치 (AVAILABLE인데 중량 0 등)
    7. [Stage4] Rack 용량 검사 (rack당 20개 한계)
    8. [Stage4] 창고 용량 검사 (A/B 각 3500, 합계 7000)
    9. [Stage4] Location 코드 형식 검사 (A-03-05-02)

Author: Ruby
Version: v7.0.0 (v6.9.0 IntegrityChecker + Stage4 capacity 통합)
"""

from engine_modules.constants import STATUS_AVAILABLE, STATUS_DEPLETED, STATUS_PICKED, STATUS_RESERVED, STATUS_SOLD
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

# Stage4 capacity 검사 (engine_modules/inventory_validator.py)
from engine_modules.inventory_validator import (
    check_rack_capacity,
    check_warehouse_capacity,
    check_system_capacity,
    validate_location_code,
)

logger = logging.getLogger(__name__)

# ISO 8601 날짜 패턴 (YYYY-MM-DD)
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
DATETIME_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}')


@dataclass
class CheckResult:
    """개별 검사 결과"""
    check_name: str
    passed: bool
    issue_count: int = 0
    details: List[str] = field(default_factory=list)
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL


@dataclass
class IntegrityReport:
    """전체 정합성 리포트"""
    timestamp: str = ""
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    results: List[CheckResult] = field(default_factory=list)

    @property
    def score(self) -> int:
        """100점 기반 점수 (통과 비율)"""
        if self.total_checks == 0:
            return 100
        return int((self.passed / self.total_checks) * 100)


class IntegrityChecker:
    """재고 데이터 정합성 검사기 (v7.0.0 통합판)"""

    def __init__(self, db):
        self.db = db

    def run_all(self) -> IntegrityReport:
        """전체 정합성 검사 실행"""
        report = IntegrityReport(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        checks = [
            self._check_duplicate_lots,
            self._check_orphan_tonbags,
            self._check_date_formats,
            self._check_weight_integrity,
            self._check_status_consistency,
            self._check_fk_integrity,
            self._check_stage4_rack_capacity,
            self._check_stage4_warehouse_capacity,
            self._check_stage4_location_codes,
        ]

        for check_fn in checks:
            try:
                result = check_fn()
                report.results.append(result)
                report.total_checks += 1
                if result.passed:
                    report.passed += 1
                elif result.severity == "WARNING":
                    report.warnings += 1
                    report.failed += 1
                else:
                    report.failed += 1
            except Exception as e:
                logger.error(f"검사 실패 [{check_fn.__name__}]: {e}")
                report.results.append(CheckResult(
                    check_name=check_fn.__name__,
                    passed=False,
                    details=[f"검사 실행 오류: {e}"],
                    severity="ERROR"
                ))
                report.total_checks += 1
                report.failed += 1

        return report

    # =========================================================================
    # 1. 중복 LOT 번호
    # =========================================================================
    def _check_duplicate_lots(self) -> CheckResult:
        """중복 LOT 번호 검사"""
        try:
            rows = self.db.fetchall(
                "SELECT lot_no, COUNT(*) as cnt FROM inventory "
                "GROUP BY lot_no HAVING cnt > 1"
            )
            if not rows:
                return CheckResult("중복 LOT 번호", passed=True)
            details = [f"LOT {r['lot_no']}: {r['cnt']}건 중복" for r in rows]
            return CheckResult("중복 LOT 번호", passed=False,
                               issue_count=len(rows), details=details,
                               severity="CRITICAL")
        except Exception as e:
            return CheckResult("중복 LOT 번호", passed=False,
                               details=[str(e)], severity="ERROR")

    # =========================================================================
    # 2. 고아 TONBAG
    # =========================================================================
    def _check_orphan_tonbags(self) -> CheckResult:
        """LOT에 연결되지 않은 고아 톤백 검사"""
        try:
            rows = self.db.fetchall(
                "SELECT t.id, t.lot_no, t.tonbag_no "
                "FROM inventory_tonbag t "
                "LEFT JOIN inventory i ON t.lot_no = i.lot_no "
                "WHERE i.lot_no IS NULL"
            )
            if not rows:
                return CheckResult("고아 톤백", passed=True)
            details = [f"ID {r['id']}: {r['lot_no']}-{r.get('tonbag_no','?')}" for r in rows]
            return CheckResult("고아 톤백", passed=False,
                               issue_count=len(rows), details=details,
                               severity="ERROR")
        except Exception as e:
            return CheckResult("고아 톤백", passed=False,
                               details=[str(e)], severity="ERROR")

    # =========================================================================
    # 3. 날짜 포맷 불량
    # =========================================================================
    def _check_date_formats(self) -> CheckResult:
        """날짜 컬럼 ISO 8601 형식 검사"""
        issues = []
        date_columns = ['arrival_date', 'ship_date', 'stock_date']
        # v6.5.4: 화이트리스트 — 정해진 컬럼명만 SQL에 삽입
        _DATE_COL_WHITELIST = frozenset(date_columns)
        try:
            for col in date_columns:
                if col not in _DATE_COL_WHITELIST:
                    continue  # 화이트리스트 외 컬럼 차단
                try:
                    rows = self.db.fetchall(
                        f"SELECT lot_no, {col} FROM inventory "
                        f"WHERE {col} IS NOT NULL AND {col} != ''"
                    )
                    for r in (rows or []):
                        val = str(r.get(col, '') or '').strip()
                        if val and not DATE_PATTERN.match(val) and not DATETIME_PATTERN.match(val):
                            issues.append(f"{col}: {r['lot_no']} = '{val}'")
                except Exception:
                    logger.debug("[SUPPRESSED] exception in integrity_check.py")  # noqa
            if not issues:
                return CheckResult("날짜 형식", passed=True)
            return CheckResult("날짜 형식", passed=False,
                               issue_count=len(issues), details=issues[:20],
                               severity="WARNING")
        except Exception as e:
            return CheckResult("날짜 형식", passed=False,
                               details=[str(e)], severity="ERROR")

    # =========================================================================
    # 4. 중량 무결성
    # =========================================================================
    def _check_weight_integrity(self) -> CheckResult:
        """음수/비정상 0 중량 검사"""
        issues = []
        try:
            # 음수 중량
            rows = self.db.fetchall(
                "SELECT lot_no, current_weight FROM inventory "
                "WHERE current_weight < 0"
            )
            for r in (rows or []):
                issues.append(f"음수 중량: {r['lot_no']} = {r['current_weight']}kg")

            # AVAILABLE인데 중량 0 (sample 1kg 제외)
            rows2 = self.db.fetchall(
                "SELECT lot_no, current_weight, status FROM inventory "
                "WHERE status = 'AVAILABLE' AND current_weight <= 0"
            )
            for r in (rows2 or []):
                issues.append(f"AVAILABLE 중량 0: {r['lot_no']}")

            if not issues:
                return CheckResult("중량 무결성", passed=True)
            return CheckResult("중량 무결성", passed=False,
                               issue_count=len(issues), details=issues,
                               severity="ERROR")
        except Exception as e:
            return CheckResult("중량 무결성", passed=False,
                               details=[str(e)], severity="ERROR")

    # =========================================================================
    # 5. 상태 불일치
    # =========================================================================
    def _check_status_consistency(self) -> CheckResult:
        """재고 상태 불일치 검사"""
        issues = []
        valid_statuses = {STATUS_AVAILABLE, STATUS_RESERVED, STATUS_PICKED, STATUS_SOLD, STATUS_DEPLETED, 'RETURN'}
        try:
            rows = self.db.fetchall("SELECT lot_no, status FROM inventory")
            for r in (rows or []):
                status = str(r.get('status', '') or '').upper()
                if status not in valid_statuses:
                    issues.append(f"비정상 상태: {r['lot_no']} = '{r['status']}'")

            if not issues:
                return CheckResult("상태 일관성", passed=True)
            return CheckResult("상태 일관성", passed=False,
                               issue_count=len(issues), details=issues,
                               severity="ERROR")
        except Exception as e:
            return CheckResult("상태 일관성", passed=False,
                               details=[str(e)], severity="ERROR")

    # =========================================================================
    # 6. FK 무결성
    # =========================================================================
    def _check_fk_integrity(self) -> CheckResult:
        """외래키 무결성 검사"""
        issues = []
        try:
            # tonbag → inventory 참조
            rows = self.db.fetchall(
                "SELECT DISTINCT t.lot_no FROM inventory_tonbag t "
                "LEFT JOIN inventory i ON t.lot_no = i.lot_no "
                "WHERE i.lot_no IS NULL"
            )
            for r in (rows or []):
                issues.append(f"FK 위반(tonbag→inventory): {r['lot_no']}")

            if not issues:
                return CheckResult("외래키 무결성", passed=True)
            return CheckResult("외래키 무결성", passed=False,
                               issue_count=len(issues), details=issues,
                               severity="ERROR")
        except Exception as e:
            return CheckResult("외래키 무결성", passed=False,
                               details=[str(e)], severity="ERROR")

    # =========================================================================
    # 7. [Stage4] Rack 용량 검사
    # =========================================================================
    def _check_stage4_rack_capacity(self) -> CheckResult:
        """Stage4: Rack당 용량 20개 초과 검사"""
        issues = []
        try:
            rows = self.db.fetchall(
                "SELECT location, COUNT(*) as cnt "
                "FROM inventory_tonbag "
                "WHERE location IS NOT NULL AND location != '' "
                "  AND status NOT IN ('SOLD','DEPLETED') "
                "GROUP BY location HAVING cnt > 0"
            )
            for r in (rows or []):
                cnt = int(r.get('cnt', 0))
                result = check_rack_capacity(cnt)
                if not result.is_valid:
                    issues.append(f"Rack {r['location']}: {cnt}개 ({result.message})")

            if not issues:
                return CheckResult("[Stage4] Rack 용량", passed=True)
            return CheckResult("[Stage4] Rack 용량", passed=False,
                               issue_count=len(issues), details=issues,
                               severity="WARNING")
        except Exception as e:
            return CheckResult("[Stage4] Rack 용량", passed=False,
                               details=[str(e)], severity="ERROR")

    # =========================================================================
    # 8. [Stage4] 창고 용량 검사
    # =========================================================================
    def _check_stage4_warehouse_capacity(self) -> CheckResult:
        """Stage4: A/B 창고 용량 검사 (각 3500, 합계 7000)"""
        issues = []
        try:
            for wh in ['A', 'B']:
                rows = self.db.fetchall(
                    "SELECT COUNT(*) as cnt FROM inventory_tonbag "
                    "WHERE warehouse = ? AND status NOT IN ('SOLD','DEPLETED')",
                    (wh,)
                )
                cnt = int((rows[0].get('cnt', 0) if rows else 0))
                result = check_warehouse_capacity(wh, cnt)
                if not result.is_valid:
                    issues.append(f"창고 {wh}: {cnt}개 ({result.message})")

            # 전체 시스템 용량
            rows2 = self.db.fetchall(
                "SELECT COUNT(*) as cnt FROM inventory_tonbag "
                "WHERE status NOT IN ('SOLD','DEPLETED')"
            )
            total = int((rows2[0].get('cnt', 0) if rows2 else 0))
            sys_result = check_system_capacity(total)
            if not sys_result.is_valid:
                issues.append(f"시스템 전체: {total}개 ({sys_result.message})")

            if not issues:
                return CheckResult("[Stage4] 창고 용량", passed=True)
            return CheckResult("[Stage4] 창고 용량", passed=False,
                               issue_count=len(issues), details=issues,
                               severity="WARNING")
        except Exception as e:
            return CheckResult("[Stage4] 창고 용량", passed=False,
                               details=[str(e)], severity="ERROR")

    # =========================================================================
    # 9. [Stage4] Location 코드 형식 검사
    # =========================================================================
    def _check_stage4_location_codes(self) -> CheckResult:
        """Stage4: Location 코드 형식 검사 (A-03-05-02)"""
        issues = []
        try:
            rows = self.db.fetchall(
                "SELECT DISTINCT location FROM inventory_tonbag "
                "WHERE location IS NOT NULL AND location != '' "
                "  AND status NOT IN ('SOLD','DEPLETED')"
            )
            for r in (rows or []):
                loc = str(r.get('location', '') or '').strip()
                if loc:
                    result = validate_location_code(loc)
                    if not result.is_valid:
                        issues.append(f"위치코드 오류: '{loc}' ({result.message})")

            if not issues:
                return CheckResult("[Stage4] Location 코드", passed=True)
            return CheckResult("[Stage4] Location 코드", passed=False,
                               issue_count=len(issues), details=issues[:20],
                               severity="WARNING")
        except Exception as e:
            return CheckResult("[Stage4] Location 코드", passed=False,
                               details=[str(e)], severity="ERROR")

    # =========================================================================
    # 리포트 출력
    # =========================================================================
    def print_report(self, report: IntegrityReport) -> str:
        """콘솔 리포트 출력 및 문자열 반환"""
        lines = [
            f"{'='*60}",
            f"SQM 정합성 검사 리포트 — {report.timestamp}",
            f"{'='*60}",
            f"총 검사: {report.total_checks}  통과: {report.passed}  "
            f"실패: {report.failed}  점수: {report.score}점",
            f"{'-'*60}",
        ]
        for r in report.results:
            icon = "✅" if r.passed else ("⚠️" if r.severity == "WARNING" else "❌")
            lines.append(f"{icon} {r.check_name} — {'통과' if r.passed else f'{r.issue_count}건 이슈'}")
            for d in r.details[:5]:
                lines.append(f"     · {d}")
            if len(r.details) > 5:
                lines.append(f"     ... 외 {len(r.details)-5}건")
        lines.append(f"{'='*60}")
        output = "\n".join(lines)
        logger.info(output)
        return output

    def save_report(self, report: IntegrityReport, filepath: str = None) -> str:
        """리포트를 파일로 저장"""
        import os
        if not filepath:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            os.makedirs('data/reports', exist_ok=True)
            filepath = f'data/reports/integrity_{ts}.txt'
        text = self.print_report(report)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text)
            logger.info(f"리포트 저장: {filepath}")
        except Exception as e:
            logger.error(f"리포트 저장 실패: {e}")
        return filepath


def run_integrity_check(db) -> IntegrityReport:
    """편의 함수: 전체 검사 실행 후 리포트 반환"""
    checker = IntegrityChecker(db)
    report = checker.run_all()
    checker.print_report(report)
    return report


# Stage4 re-export (하위 호환)
__all__ = [
    'IntegrityChecker', 'IntegrityReport', 'CheckResult', 'run_integrity_check',
    'check_rack_capacity', 'check_warehouse_capacity',
    'check_system_capacity', 'validate_location_code',
]
