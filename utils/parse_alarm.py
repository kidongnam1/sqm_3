# -*- coding: utf-8 -*-
"""
utils/parse_alarm.py
====================
SQM v865 — 입고 서류 파싱 알람 로직
v1.0.0 (2026-04-30) Ruby 작성

역할:
  - 파싱 결과의 필수 필드 누락/오류를 감지
  - 심각도(CRITICAL / WARNING / INFO) 분류
  - FastAPI 엔드포인트 / UI Toast 메시지에 바로 연결 가능

사용 예:
    from utils.parse_alarm import check_bl, check_do, check_packing, check_invoice
    alarms = check_do(do_result, carrier_id="ONE")
    if alarms.has_critical:
        raise HTTPException(422, alarms.summary())
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Any
import logging

logger = logging.getLogger(__name__)

# ── 심각도 상수 ────────────────────────────────────────────────
CRITICAL = "CRITICAL"   # 입고 등록 불가 — 즉시 중단
WARNING  = "WARNING"    # 등록은 가능하나 수동 보완 필요
INFO     = "INFO"       # 참고용 메시지


@dataclass
class ParseAlarm:
    level:   str          # CRITICAL / WARNING / INFO
    field:   str          # 문제 필드명
    message: str          # 사람이 읽는 설명
    doc_type: str = ""    # BL / DO / FA / PL
    carrier:  str = ""    # ONE / MAERSK / MSC / HAPAG


@dataclass
class AlarmReport:
    alarms: List[ParseAlarm] = field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(a.level == CRITICAL for a in self.alarms)

    @property
    def has_warning(self) -> bool:
        return any(a.level == WARNING for a in self.alarms)

    @property
    def criticals(self) -> List[ParseAlarm]:
        return [a for a in self.alarms if a.level == CRITICAL]

    @property
    def warnings(self) -> List[ParseAlarm]:
        return [a for a in self.alarms if a.level == WARNING]

    def summary(self) -> str:
        """Toast / 로그용 한 줄 요약"""
        parts = []
        if self.criticals:
            fields = ", ".join(a.field for a in self.criticals)
            parts.append(f"[CRITICAL] 필수 필드 누락: {fields}")
        if self.warnings:
            fields = ", ".join(a.field for a in self.warnings)
            parts.append(f"[WARNING] 보완 필요: {fields}")
        return " / ".join(parts) if parts else "OK"

    def to_dict(self) -> dict:
        return {
            "has_critical": self.has_critical,
            "has_warning":  self.has_warning,
            "summary":      self.summary(),
            "alarms": [
                {"level": a.level, "field": a.field,
                 "message": a.message, "doc_type": a.doc_type}
                for a in self.alarms
            ],
        }

    def log(self, doc_type: str = "", carrier: str = "") -> None:
        prefix = f"[ALARM][{doc_type}][{carrier}]"
        for a in self.alarms:
            if a.level == CRITICAL:
                logger.error(f"{prefix} {a.field}: {a.message}")
            elif a.level == WARNING:
                logger.warning(f"{prefix} {a.field}: {a.message}")
            else:
                logger.info(f"{prefix} {a.field}: {a.message}")


def _add(report: AlarmReport, level: str, field: str, msg: str,
         doc_type: str = "", carrier: str = "") -> None:
    report.alarms.append(ParseAlarm(level, field, msg, doc_type, carrier))


# ── BL 체크 ──────────────────────────────────────────────────
def check_bl(result: Any, carrier_id: str = "") -> AlarmReport:
    """
    BL 파싱 결과 알람 체크.
    result: BLData 또는 None
    """
    r = AlarmReport()
    dt, ca = "BL", carrier_id or ""

    if result is None:
        _add(r, CRITICAL, "bl_no", "BL 파싱 완전 실패 — None 반환", dt, ca)
        return r

    bl_no = str(getattr(result, "bl_no", "") or "").strip()
    if not bl_no:
        _add(r, CRITICAL, "bl_no", "BL 번호 추출 실패 — 입고 등록 불가", dt, ca)
    elif len(bl_no) < 8:
        _add(r, WARNING, "bl_no", f"BL 번호 너무 짧음: '{bl_no}' — 오추출 가능성", dt, ca)

    carrier = str(getattr(result, "carrier_id", "") or "").strip()
    if not carrier:
        _add(r, WARNING, "carrier_id", "선사 미감지 — 좌표 파싱 비활성화 상태", dt, ca)

    vessel = str(getattr(result, "vessel", "") or "").strip()
    if not vessel:
        _add(r, WARNING, "vessel", "선명 추출 실패", dt, ca)
    elif len(vessel) > 80 or vessel.upper() in ("VESSEL", "OCEAN VESSEL VOYAGE NO. FLAG"):
        _add(r, CRITICAL, "vessel", f"선명 오추출 (라벨 텍스트 의심): '{vessel[:40]}'", dt, ca)

    voyage = str(getattr(result, "voyage", "") or "").strip()
    if not voyage:
        _add(r, WARNING, "voyage", "항차 추출 실패", dt, ca)
    elif voyage.upper() in ("PORT OF LOADING", "VOYAGE", "VOYAGE NO"):
        _add(r, CRITICAL, "voyage", f"항차 오추출 (라벨 텍스트 의심): '{voyage}'", dt, ca)

    ship_date = getattr(result, "ship_date", None)
    if not ship_date:
        _add(r, WARNING, "ship_date", "선적일 추출 실패 — 재고 날짜 공란 처리됨", dt, ca)

    r.log(dt, ca)
    return r


# ── DO 체크 ──────────────────────────────────────────────────
def check_do(result: Any, carrier_id: str = "") -> AlarmReport:
    """
    D/O 파싱 결과 알람 체크.
    mrn·msn은 통관 필수 → CRITICAL 처리.
    result: DOData 또는 None
    """
    r = AlarmReport()
    dt, ca = "DO", carrier_id or ""

    if result is None:
        _add(r, WARNING, "DO", "D/O 파싱 결과 없음 — 나중에 수동 등록 필요", dt, ca)
        return r

    success = getattr(result, "success", False)
    if not success:
        _add(r, WARNING, "DO", "D/O 파싱 실패 플래그 — Gemini fallback 실패 포함", dt, ca)

    bl_no = str(getattr(result, "bl_no", "") or "").strip()
    if not bl_no:
        _add(r, CRITICAL, "bl_no", "D/O에서 BL 번호 추출 실패 — LOT 매핑 불가", dt, ca)

    arrival_date = getattr(result, "arrival_date", None)
    if not arrival_date:
        _add(r, CRITICAL, "arrival_date", "입항일 추출 실패 — Free Time 계산 불가", dt, ca)

    # ── mrn / msn: 통관 필수 필드 ──
    mrn = str(getattr(result, "mrn", "") or "").strip()
    msn = str(getattr(result, "msn", "") or "").strip()
    if not mrn:
        _add(r, CRITICAL, "mrn", "MRN(수입신고번호) 추출 실패 — 통관 처리 불가", dt, ca)
    elif " " not in mrn and len(mrn) < 8:
        _add(r, WARNING, "mrn", f"MRN 형식 이상 (짧음): '{mrn}'", dt, ca)
    if not msn:
        _add(r, CRITICAL, "msn", "MSN(적하목록번호) 추출 실패 — 통관 처리 불가", dt, ca)

    vessels = str(getattr(result, "vessel", "") or "").strip()
    if not vessels:
        _add(r, WARNING, "vessel", "D/O 선명 추출 실패", dt, ca)

    containers = getattr(result, "containers", []) or []
    if not containers:
        _add(r, CRITICAL, "containers", "컨테이너 목록 없음 — 톤백 생성 불가", dt, ca)
    else:
        # free_time_date 빠진 컨테이너 확인
        missing_ft = [
            c.container_no for c in containers
            if not getattr(c, "free_time_date", None)
        ]
        if missing_ft:
            _add(r, WARNING, "free_time_date",
                 f"Free Time 날짜 없는 컨테이너 {len(missing_ft)}개: {missing_ft[:3]}", dt, ca)

    r.log(dt, ca)
    return r


# ── Invoice(FA) 체크 ─────────────────────────────────────────
def check_invoice(result: Any, carrier_id: str = "") -> AlarmReport:
    r = AlarmReport()
    dt, ca = "FA", carrier_id or ""

    if result is None:
        _add(r, CRITICAL, "invoice", "Invoice 파싱 완전 실패", dt, ca)
        return r

    for fld, label in [("invoice_no", "인보이스 번호"), ("bl_no", "BL 번호"),
                        ("unit_price", "단가"), ("total_amount", "총금액")]:
        val = getattr(result, fld, None)
        if val is None or str(val).strip() in ("", "0", "0.0"):
            _add(r, WARNING, fld, f"{label} 추출 실패", dt, ca)

    lot_count = 0
    lots = getattr(result, "lot_numbers", None) or getattr(result, "lots", None) or []
    lot_count = len(lots) if lots else 0
    if lot_count == 0:
        _add(r, WARNING, "lot_count", "LOT 목록 추출 실패 — SAP 대조 불가", dt, ca)

    r.log(dt, ca)
    return r


# ── PL 체크 ──────────────────────────────────────────────────
def check_packing(result: Any, carrier_id: str = "") -> AlarmReport:
    r = AlarmReport()
    dt, ca = "PL", carrier_id or ""

    if result is None:
        _add(r, CRITICAL, "packing_list", "패킹리스트 파싱 완전 실패", dt, ca)
        return r

    lots = getattr(result, "packing_list_items", None) or getattr(result, "lots", None) or []
    if not lots:
        _add(r, CRITICAL, "lot_rows", "LOT 행 없음 — 재고 등록 불가", dt, ca)
        r.log(dt, ca)
        return r

    missing_mxbg = [
        getattr(lot, "lot_no", "?") for lot in lots
        if not getattr(lot, "mxbg_pallet", 0)
    ]
    if missing_mxbg:
        _add(r, CRITICAL, "mxbg_pallet",
             f"MXBG(톤백수) 없는 LOT {len(missing_mxbg)}개: {missing_mxbg[:3]} — 톤백 생성 불가", dt, ca)

    missing_net = [
        getattr(lot, "lot_no", "?") for lot in lots
        if not getattr(lot, "net_weight_kg", 0)
    ]
    if missing_net:
        _add(r, CRITICAL, "net_weight_kg",
             f"순중량 없는 LOT {len(missing_net)}개: {missing_net[:3]}", dt, ca)

    r.log(dt, ca)
    return r


# ── 통합 체크 (ShipmentDocuments 전체) ───────────────────────
def check_all(shipment: Any) -> dict:
    """
    ShipmentDocuments 전체를 한번에 체크.
    반환: {"BL": AlarmReport, "DO": AlarmReport, "FA": AlarmReport, "PL": AlarmReport}
    """
    carrier = str(getattr(shipment, "carrier_id", "") or "").strip()
    return {
        "BL": check_bl(getattr(shipment, "bl_data", None), carrier),
        "DO": check_do(getattr(shipment, "do_data", None), carrier),
        "FA": check_invoice(getattr(shipment, "invoice_data", None), carrier),
        "PL": check_packing(getattr(shipment, "packing_list_data", None), carrier),
    }
