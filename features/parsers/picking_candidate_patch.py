# -*- coding: utf-8 -*-
"""
picking_candidate_patch.py — SQM v8.0.6 PATCH
==============================================
outbound_handlers.py 의 Picking List 파싱 진입부에
첫 행 검수(firstrow_review) + 열 매핑 품질 점수 기능을 연결하는 패치 모듈.

★ 이 파일은 outbound_handlers.py 를 직접 수정하지 않습니다.
  outbound_handlers.py 의 parse_picking_list_pdf() 호출 이후
  아래 함수를 삽입하는 방식으로 연결합니다.

연결 위치 (outbound_handlers.py 약 1744행):
  doc = parse_picking_list_pdf(path)
  # ↓ 아래 한 줄 추가
  doc = enrich_picking_doc_with_review(doc, path, log_fn=self._append_log)

설계 원칙:
  - PickingListParser 자체는 수정하지 않음 (기존 pdfplumber→Gemini 흐름 유지)
  - 파싱 완료 후 결과를 검수하여 품질 점수 + 첫 행 검수 데이터를 doc에 추가
  - 열 매핑 이상 감지 시 log_fn으로 경고 출력
  - 화주별 피킹 템플릿(customer_templates) 확장 기반 마련

[수정이력]
  2026-03-17  Ruby  SQM v8.0.6 신규 생성
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# 피킹리스트 필드 검증 규칙
# ─────────────────────────────────────────────────────────────────
_REQUIRED_PICKING_FIELDS = [
    "outbound_id",
    "items",
]
_IMPORTANT_PICKING_FIELDS = [
    "sales_order_no",
    "picking_no",
    "customer",
    "plan_loading_date",
]

# 허용 UNIT
_VALID_UNITS = {"MT", "KG", "TON", "KGS"}

# LOT_NO 패턴 (숫자 10자리 또는 영숫자)
_LOT_NO_PATTERN = re.compile(r"^\d{7,15}$|^[A-Z0-9\-]{5,20}$")

# 허용 LOCATION 패턴 (예: A-01, ZONE1, GW01 등)
_LOCATION_PATTERN = re.compile(r"^[A-Za-z0-9\-_]{1,20}$")


# ─────────────────────────────────────────────────────────────────
# 첫 행 검수
# ─────────────────────────────────────────────────────────────────
def _validate_first_row(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """첫 번째 유효 행의 필드 검증 결과 반환"""
    if not items:
        return {"status": "empty", "warnings": ["items 리스트가 비어 있습니다"]}

    row = items[0]
    warnings: List[str] = []
    field_status: Dict[str, str] = {}

    # LOT_NO
    lot_no = str(row.get("lot_no", "") or "").strip()
    if not lot_no:
        field_status["lot_no"] = "empty"
        warnings.append("첫 행 lot_no 없음")
    elif not _LOT_NO_PATTERN.match(lot_no):
        field_status["lot_no"] = "invalid_format"
        warnings.append(f"첫 행 lot_no 형식 이상: {lot_no!r}")
    else:
        field_status["lot_no"] = "ok"

    # QTY (qty_mt 또는 qty_kg)
    qty = row.get("qty_mt") or row.get("qty_kg") or 0
    try:
        qty_f = float(str(qty).replace(",", ""))
        field_status["qty"] = "ok" if qty_f > 0 else "zero"
        if qty_f <= 0:
            warnings.append(f"첫 행 qty=0 또는 음수: {qty}")
    except (ValueError, TypeError):
        field_status["qty"] = "invalid_number"
        warnings.append(f"첫 행 qty 숫자 변환 불가: {qty!r}")

    # UNIT
    unit = str(row.get("unit", "") or "").strip().upper()
    if unit in _VALID_UNITS:
        field_status["unit"] = "ok"
    elif unit:
        field_status["unit"] = "invalid_unit"
        warnings.append(f"첫 행 unit 비정상: {unit!r} (허용: {_VALID_UNITS})")
    else:
        field_status["unit"] = "empty"
        warnings.append("첫 행 unit 없음")

    # LOCATION
    loc = str(row.get("storage_location", "") or "").strip()
    if not loc:
        field_status["storage_location"] = "empty"
        # location은 없어도 경고만 (필수 아님)
    elif _LOCATION_PATTERN.match(loc):
        field_status["storage_location"] = "ok"
    else:
        field_status["storage_location"] = "invalid_format"
        warnings.append(f"첫 행 storage_location 형식 이상: {loc!r}")

    # IS_SAMPLE
    field_status["is_sample"] = "ok"

    score = _calc_firstrow_score(field_status, warnings)

    return {
        "status": "ok" if score >= 50 else "warning",
        "score": score,
        "field_status": field_status,
        "first_row": {
            "lot_no": lot_no,
            "qty": qty,
            "unit": unit,
            "storage_location": loc,
            "is_sample": row.get("is_sample", False),
        },
        "warnings": warnings,
    }


def _calc_firstrow_score(
    field_status: Dict[str, str], warnings: List[str]
) -> int:
    score = 0
    for field, state in field_status.items():
        if state == "ok":
            score += 20 if field in {"lot_no", "qty"} else 10
        elif state == "empty":
            score -= 10 if field in {"lot_no", "qty"} else 2
        else:
            score -= 15
    score -= len(warnings) * 3
    return max(score, -100)


# ─────────────────────────────────────────────────────────────────
# 열 매핑 품질 감지
# ─────────────────────────────────────────────────────────────────
def _detect_column_mapping_issues(items: List[Dict[str, Any]]) -> List[str]:
    """전체 items에서 열 매핑 이상 징후 감지"""
    issues: List[str] = []
    if not items:
        return issues

    # lot_no 자리에 숫자만 있는 경우 → qty와 혼용 가능성
    lot_numeric_count = sum(
        1 for row in items
        if str(row.get("lot_no", "")).strip().replace(".", "").isdigit()
    )
    if lot_numeric_count > len(items) * 0.5:
        issues.append(
            f"lot_no 열에 순수 숫자가 {lot_numeric_count}/{len(items)}건 → "
            "qty 열과 혼용 가능성 확인 필요"
        )

    # qty가 0인 행이 과반이면 매핑 오류 의심
    zero_qty = sum(
        1 for row in items
        if (row.get("qty_mt") or row.get("qty_kg") or 0) == 0
    )
    if zero_qty > len(items) * 0.3:
        issues.append(
            f"qty=0 행이 {zero_qty}/{len(items)}건 → 열 매핑 오류 의심"
        )

    # unit이 빈 행이 과반
    no_unit = sum(1 for row in items if not row.get("unit"))
    if no_unit > len(items) * 0.5:
        issues.append(
            f"unit 없는 행이 {no_unit}/{len(items)}건 → unit 열 매핑 확인 필요"
        )

    return issues


# ─────────────────────────────────────────────────────────────────
# 피킹 문서 전체 품질 점수
# ─────────────────────────────────────────────────────────────────
def _score_picking_doc(doc: Dict[str, Any]) -> int:
    score = 0

    for field in _REQUIRED_PICKING_FIELDS:
        val = doc.get(field)
        if val and val != [] and val != "":
            score += 25
        else:
            score -= 20

    for field in _IMPORTANT_PICKING_FIELDS:
        val = doc.get(field)
        if val and val != "":
            score += 10
        else:
            score -= 5

    items = doc.get("items", []) or []
    total_lots = doc.get("total_lots", 0) or 0
    if total_lots > 0:
        score += 20
    elif items:
        score += 10

    if not doc.get("parse_ok", False):
        score -= 30

    warnings = doc.get("warnings", []) or []
    score -= len(warnings) * 3

    return score


# ─────────────────────────────────────────────────────────────────
# 공개 API — outbound_handlers.py 에서 호출
# ─────────────────────────────────────────────────────────────────
def enrich_picking_doc_with_review(
    doc: Dict[str, Any],
    pdf_path: str = "",
    log_fn: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    PickingListParser 결과 doc에 검수 정보를 추가하여 반환.

    추가 키:
      doc["_review"]["firstrow"]          : 첫 행 검수 결과
      doc["_review"]["column_issues"]     : 열 매핑 이상 감지 결과
      doc["_review"]["doc_quality_score"] : 전체 품질 점수
      doc["_review"]["has_issues"]        : 이슈 존재 여부

    Parameters
    ----------
    doc      : parse_picking_list_pdf() 반환값
    pdf_path : 원본 PDF 경로 (로그용)
    log_fn   : UI 로그 함수 (outbound_handlers의 self._append_log 등)
    """
    def _log(msg: str) -> None:
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                logger.debug("[SUPPRESSED] exception in picking_candidate_patch.py")  # noqa
        logger.info(msg)

    if not isinstance(doc, dict):
        logger.warning("[PickingReview] doc이 dict가 아님 — 검수 건너뜀")
        return doc

    items: List[Dict[str, Any]] = doc.get("items", []) or []

    # ── 첫 행 검수 ──────────────────────────────────────────────
    firstrow_result = _validate_first_row(items)

    # ── 열 매핑 이상 감지 ────────────────────────────────────────
    column_issues = _detect_column_mapping_issues(items)

    # ── 전체 품질 점수 ───────────────────────────────────────────
    doc_score = _score_picking_doc(doc)

    has_issues = (
        firstrow_result.get("status") != "ok"
        or bool(column_issues)
        or doc_score < 30
    )

    # ── doc에 검수 결과 주입 ──────────────────────────────────────
    doc["_review"] = {
        "firstrow": firstrow_result,
        "column_issues": column_issues,
        "doc_quality_score": doc_score,
        "has_issues": has_issues,
    }

    # ── 로그 출력 ────────────────────────────────────────────────
    score_label = "✅" if doc_score >= 50 else ("⚠️" if doc_score >= 0 else "❌")
    _log(
        f"  {score_label} [PickingReview] 품질점수={doc_score} "
        f"첫행상태={firstrow_result.get('status')} "
        f"LOT수={doc.get('total_lots', 0)}"
    )

    for issue in column_issues:
        _log(f"  ⚠️ [PickingReview] 열매핑 이상: {issue}")

    for warn in firstrow_result.get("warnings", []):
        _log(f"  ⚠️ [PickingReview] 첫행 검수: {warn}")

    if has_issues:
        _log("  💡 [PickingReview] PickingListPreviewDialog에서 값/열 매핑을 확인하세요")

    logger.info(
        "[PickingReview] 완료: score=%d firstrow=%s column_issues=%d",
        doc_score,
        firstrow_result.get("status"),
        len(column_issues),
    )

    return doc
