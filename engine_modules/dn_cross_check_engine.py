# -*- coding: utf-8 -*-
"""
SQM v8.6.4 — DN 교차검증 엔진 (dn_cross_check_engine.py)

Author: Ruby
Version: 1.0.0 (2026-03-29)

고객 Sales Order / DN 파일 vs SQM DB 비교 기능.

비교 항목:
  1. Sales Order No  — SO 번호 일치 여부
  2. LOT No          — 출고 LOT 목록 일치
  3. 수량 (MT)       — 출고 수량 오차 ±0.01MT 이하
  4. 고객명          — 고객사 일치
  5. 납기일          — Delivery Date 일치 여부

결과 코드:
  DN-OK-01: 완전 일치
  DN-WARN-01: 수량 오차 (±0.01MT 초과)
  DN-WARN-02: 납기일 불일치
  DN-ERR-01: LOT 불일치 (SQM에 없는 LOT)
  DN-ERR-02: Sales Order No 없음
  DN-ERR-03: 수량 초과 (고객 DN > SQM 출고)
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DNCheckItem:
    """DN 교차검증 개별 항목."""
    code: str
    level: str            # "OK" | "WARN" | "ERROR"
    field: str            # 비교 필드명
    dn_value: str         # 고객 DN 값
    sqm_value: str        # SQM DB 값
    message: str

    def __str__(self) -> str:
        icon = {"OK": "✅", "WARN": "⚠️", "ERROR": "❌"}.get(self.level, "❓")
        return f"{icon} [{self.code}] {self.message}"


@dataclass
class DNCheckResult:
    """DN 교차검증 전체 결과."""
    sales_order_no: str = ""
    items: List[DNCheckItem] = field(default_factory=list)
    is_clean: bool = False
    error_count: int = 0
    warn_count: int = 0

    @property
    def summary(self) -> str:
        if self.is_clean:
            return f"✅ DN 교차검증 통과 — {self.sales_order_no}"
        return (f"DN 교차검증: 오류 {self.error_count}건 / "
                f"경고 {self.warn_count}건 ({self.sales_order_no})")


def cross_check_dn(db_adapter, sales_order_no: str,
                   dn_data: dict) -> DNCheckResult:
    """SQM DB vs 고객 DN 데이터 교차검증.

    Args:
        db_adapter:      SQM DB 어댑터 (fetchall/fetchone 지원)
        sales_order_no:  고객 Sales Order No
        dn_data: {
            'sales_order_no': str,
            'lots': [{'lot_no': str, 'qty_mt': float}],
            'total_mt': float,
            'customer': str,
            'delivery_date': str (YYYY-MM-DD),
        }

    Returns:
        DNCheckResult
    """
    result = DNCheckResult(sales_order_no=sales_order_no)

    # ── DB에서 해당 SO 출고 내역 조회 ──────────────────────────────────
    try:
        sqm_rows = db_adapter.fetchall(
            """SELECT lot_no, sub_lt,
                      COALESCE(sold_qty_mt, sold_qty_kg/1000.0, 0) AS qty_mt,
                      customer, delivery_date, status
               FROM sold_table
               WHERE sales_order_no = ?
               ORDER BY lot_no, sub_lt""",
            (sales_order_no,)
        ) or []
    except Exception as e:
        logger.warning(f"[DN검증] DB 조회 실패: {e}")
        result.items.append(DNCheckItem(
            "DN-ERR-02", "ERROR", "sales_order_no",
            sales_order_no, "(조회실패)",
            f"SQM DB 조회 오류: {e}"
        ))
        result.error_count = 1
        return result

    # ── 1. Sales Order No 존재 확인 ──────────────────────────────────
    if not sqm_rows:
        result.items.append(DNCheckItem(
            "DN-ERR-02", "ERROR", "sales_order_no",
            sales_order_no, "(없음)",
            f"Sales Order '{sales_order_no}'가 SQM 출고 이력에 없습니다."
        ))
        result.error_count += 1
        _finalize(result)
        return result

    # ── 2. 고객명 비교 ───────────────────────────────────────────────
    dn_customer = str(dn_data.get("customer") or "").strip()
    sqm_customers = list({r["customer"] if isinstance(r, dict) else r[3]
                          for r in sqm_rows})
    sqm_customer  = sqm_customers[0] if sqm_customers else ""

    if dn_customer and sqm_customer and dn_customer != sqm_customer:
        result.items.append(DNCheckItem(
            "DN-WARN-01", "WARN", "customer",
            dn_customer, sqm_customer,
            f"고객명 불일치: DN='{dn_customer}' / SQM='{sqm_customer}'"
        ))
        result.warn_count += 1

    # ── 3. LOT 목록 비교 ─────────────────────────────────────────────
    dn_lots = {str(item["lot_no"]).strip()
               for item in dn_data.get("lots", [])
               if item.get("lot_no")}
    sqm_lots = {str(r["lot_no"] if isinstance(r, dict) else r[0]).strip()
                for r in sqm_rows}

    only_in_dn  = dn_lots - sqm_lots
    only_in_sqm = sqm_lots - dn_lots

    if only_in_dn:
        result.items.append(DNCheckItem(
            "DN-ERR-01", "ERROR", "lot_no",
            str(only_in_dn), str(sqm_lots),
            f"고객 DN에만 있는 LOT: {', '.join(sorted(only_in_dn))}"
        ))
        result.error_count += 1

    if only_in_sqm:
        result.items.append(DNCheckItem(
            "DN-WARN-02", "WARN", "lot_no",
            str(dn_lots), str(only_in_sqm),
            f"SQM에만 있는 LOT (DN 미포함): {', '.join(sorted(only_in_sqm))}"
        ))
        result.warn_count += 1

    # ── 4. 수량 비교 ─────────────────────────────────────────────────
    dn_total  = float(dn_data.get("total_mt") or 0)
    sqm_total = sum(
        float(r["qty_mt"] if isinstance(r, dict) else r[2]) for r in sqm_rows
    )
    diff = dn_total - sqm_total

    if abs(diff) > 0.01:
        level = "ERROR" if diff > 0 else "WARN"
        code  = "DN-ERR-03" if diff > 0 else "DN-WARN-01"
        result.items.append(DNCheckItem(
            code, level, "qty_mt",
            f"{dn_total:.3f} MT", f"{sqm_total:.3f} MT",
            f"수량 {'초과' if diff > 0 else '부족'}: DN={dn_total:.3f} / SQM={sqm_total:.3f} "
            f"(차이 {diff:+.3f} MT)"
        ))
        if level == "ERROR":
            result.error_count += 1
        else:
            result.warn_count += 1

    # ── 5. 납기일 비교 ───────────────────────────────────────────────
    dn_date = str(dn_data.get("delivery_date") or "").strip()
    sqm_dates = list({str(r["delivery_date"] if isinstance(r, dict) else r[4] or "")
                      for r in sqm_rows})
    sqm_date = sqm_dates[0] if sqm_dates else ""

    if dn_date and sqm_date and dn_date != sqm_date:
        result.items.append(DNCheckItem(
            "DN-WARN-02", "WARN", "delivery_date",
            dn_date, sqm_date,
            f"납기일 불일치: DN='{dn_date}' / SQM='{sqm_date}'"
        ))
        result.warn_count += 1

    # ── OK 항목 추가 (이상 없는 필드) ───────────────────────────────
    if not only_in_dn and not only_in_sqm and dn_lots:
        result.items.append(DNCheckItem(
            "DN-OK-01", "OK", "lot_no",
            str(dn_lots), str(sqm_lots),
            f"LOT 목록 일치 ({len(dn_lots)}개)"
        ))
    if abs(diff) <= 0.01 and dn_total > 0:
        result.items.append(DNCheckItem(
            "DN-OK-01", "OK", "qty_mt",
            f"{dn_total:.3f} MT", f"{sqm_total:.3f} MT",
            f"수량 일치 ({dn_total:.3f} MT)"
        ))

    _finalize(result)
    return result


def _finalize(result: DNCheckResult) -> None:
    result.is_clean = (result.error_count == 0 and result.warn_count == 0)


def parse_dn_excel(excel_path: str) -> dict:
    """고객 DN/Sales Order Excel 파일 파싱.

    지원 컬럼: Sales Order No, LOT No, QTY (MT), Customer, Delivery Date
    Returns dn_data dict
    """
    import openpyxl
    try:
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        ws = wb.active
    except Exception as e:
        logger.warning(f"[DN파싱] Excel 로드 실패: {e}")
        return {}

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {}

    # 헤더 행 탐색 (최대 5행)
    header_row = None
    col_map = {}
    ALIASES = {
        "sales_order_no": ["SALES ORDER", "SO NO", "ORDER NO", "SALES_ORDER",
                           "판매오더", "수주번호", "DN NO", "DN_NO"],
        "lot_no":         ["LOT NO", "LOT_NO", "LOT", "LOT NUMBER"],
        "qty_mt":         ["QTY", "QTY (MT)", "QUANTITY", "수량", "MT"],
        "customer":       ["CUSTOMER", "SOLD TO", "고객", "거래처"],
        "delivery_date":  ["DELIVERY DATE", "DELIVERY", "납기일", "출고일"],
    }

    for r_idx, row in enumerate(rows[:5]):
        cells = [str(v or "").strip().upper() for v in row]
        matched = 0
        tmp_map = {}
        for field, aliases in ALIASES.items():
            for c_idx, cell in enumerate(cells):
                if any(a in cell for a in aliases):
                    tmp_map[field] = c_idx
                    matched += 1
                    break
        if matched >= 2:
            header_row = r_idx
            col_map = tmp_map
            break

    if header_row is None:
        return {}

    # 데이터 파싱
    lots = []
    so_no = ""
    customer = ""
    delivery_date = ""
    total_mt = 0.0

    for row in rows[header_row + 1:]:
        if not any(row):
            continue
        def _get(field):
            idx = col_map.get(field)
            return str(row[idx] or "").strip() if idx is not None and idx < len(row) else ""

        lot = _get("lot_no")
        if not lot:
            continue

        qty_str = _get("qty_mt")
        try:
            qty = float(qty_str.replace(",", "")) if qty_str else 0.0
        except ValueError:
            qty = 0.0

        lots.append({"lot_no": lot, "qty_mt": qty})
        total_mt += qty

        if not so_no:      so_no = _get("sales_order_no")
        if not customer:   customer = _get("customer")
        if not delivery_date: delivery_date = _get("delivery_date")

    return {
        "sales_order_no": so_no,
        "lots":           lots,
        "total_mt":       total_mt,
        "customer":       customer,
        "delivery_date":  delivery_date,
    }
