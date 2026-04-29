"""
SQM v6.0 — 반품 입고 Excel 파서
================================

반품 Excel 업로드용 파서.
- 필수: LOT NO, WEIGHT(MT), PICKING NO, REASON (하나라도 없으면 해당 행 에러 → 전체 스톱)
- 선택: SALES ORDER NO, BL NO, REMARK, RETURN DATE
- 1행 = 1 LOT. WEIGHT(MT) ÷ 0.5 = 톤백 개수 (정수). 샘플은 1개 고정.
"""

import logging
from engine_modules.constants import estimate_tonbag_count, DEFAULT_TONBAG_WEIGHT  # v8.6.1
from datetime import date
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# 헤더 별칭 (대소문자/공백 무시). 입고 형식(lot_no, net_weight, picking_no, return_reason) 포함
_HEADER_ALIASES = {
    "LOT NO": ["LOT NO", "Lot No", "LOTNO", "lot no", "lot_no"],
    "WEIGHT(MT)": ["WEIGHT(MT)", "WEIGHT (MT)", "Weight(MT)", "weight_mt", "WEIGHT MT"],
    "NET_WEIGHT_KG": ["NET(Kg)", "net_weight", "NET(Kg)", "Balance(Kg)"],
    "PICKING NO": ["PICKING NO", "Picking No", "Picking no", "picking no", "picking_no"],
    "REASON": ["REASON", "Reason", "reason", "사유", "return_reason", "반품사유"],
    "REMARK": ["REMARK", "Remark", "remark", "비고"],
    "RETURN DATE": ["RETURN DATE", "Return Date", "return date", "반품일"],
    "SALES ORDER NO": ["SALES ORDER NO", "Sales Order No", "sales order no"],
    "BL NO": ["BL NO", "Bl No", "bl no"],
}


def _normalize_header(h: str) -> str:
    return (h or "").strip()


def _map_columns(headers: List[str]) -> dict:
    """헤더 목록 → 표준 컬럼명:인덱스 매핑"""
    mapping = {}
    for i, h in enumerate(headers):
        h_n = _normalize_header(h).lower()
        for standard_name, aliases in _HEADER_ALIASES.items():
            if standard_name in mapping:
                continue
            for alias in aliases:
                if _normalize_header(alias).lower() == h_n:
                    mapping[standard_name] = i
                    break
            if standard_name in mapping:
                break
        if not mapping.get("LOT NO") and ("lot" in h_n and "no" in h_n):
            mapping["LOT NO"] = i
        if not mapping.get("LOT NO") and h_n == "lot_no":
            mapping["LOT NO"] = i
    return mapping


class ReturnInboundParser:
    """
    반품 입고 Excel 파싱
    - 필수 4개: LOT NO, WEIGHT(MT), PICKING NO, REASON
    - 1행 = 1 LOT. weight_mt / 0.5 = 톤백 개수 (정수). 샘플 행이면 1개.
    """

    def parse(self, file_path: str) -> dict:
        """
        Returns:
            parse_ok: bool
            items: [{ lot_no, weight_mt, tonbag_count, picking_no, reason, remark, return_date, ... }]
            errors: [str]  # 1건이라도 있으면 전체 스톱용
        """
        try:
            import pandas as pd
        except ImportError:
            return {
                "parse_ok": False,
                "items": [],
                "errors": ["❌ pandas 필요: pip install pandas openpyxl"],
            }

        result = {"parse_ok": False, "items": [], "errors": []}
        try:
            df = pd.read_excel(file_path, header=None, dtype=str)
            header_row = self._find_header_row(df)
            if header_row is None:
                result["errors"].append("❌ 헤더 행을 찾을 수 없음 (LOT NO 또는 WEIGHT(MT) 등)")
                return result

            headers = [
                str(v).strip() if v and str(v) != "nan" else ""
                for v in df.iloc[header_row]
            ]
            col = _map_columns(headers)

            has_lot = col.get("LOT NO") is not None
            has_weight_mt = col.get("WEIGHT(MT)") is not None
            has_net_kg = col.get("NET_WEIGHT_KG") is not None
            has_picking = col.get("PICKING NO") is not None
            has_reason = col.get("REASON") is not None
            if not has_lot:
                result["errors"].append("❌ 필수 컬럼 없음: LOT NO (또는 lot_no)")
                return result
            if not has_picking:
                result["errors"].append("❌ 필수 컬럼 없음: PICKING NO (또는 picking_no)")
                return result
            if not has_reason:
                result["errors"].append("❌ 필수 컬럼 없음: REASON (또는 return_reason/반품사유)")
                return result
            if not has_weight_mt and not has_net_kg:
                result["errors"].append("❌ 필수 컬럼 없음: WEIGHT(MT) 또는 NET(Kg)/net_weight")
                return result

            for idx in range(header_row + 1, len(df)):
                row = df.iloc[idx]
                lot_no = self._safe_str(row, col.get("LOT NO"))
                weight_mt = self._safe_float(row, col.get("WEIGHT(MT)"))
                weight_kg = self._safe_float(row, col.get("NET_WEIGHT_KG"))
                picking_no = self._safe_str(row, col.get("PICKING NO"))
                reason = self._safe_str(row, col.get("REASON"))

                if not lot_no or not str(lot_no).strip():
                    result["errors"].append(f"행 {idx + 1}: LOT NO 비어 있음")
                    return result
                if not picking_no or not str(picking_no).strip():
                    result["errors"].append(f"행 {idx + 1}: PICKING NO 비어 있음")
                    return result
                if not reason or not str(reason).strip():
                    result["errors"].append(f"행 {idx + 1}: REASON 비어 있음")
                    return result

                # 중량: NET(Kg) 우선, 없으면 WEIGHT(MT)
                if weight_kg is not None and weight_kg > 0:
                    weight_mt = round(weight_kg / 1000.0, 3)
                    tonbag_count = estimate_tonbag_count(weight_kg)  # v8.6.1: 500 하드코딩 제거
                elif weight_mt is not None and weight_mt > 0:
                    tonbag_count = max(1, int(weight_mt / 0.5))
                else:
                    result["errors"].append(f"행 {idx + 1}: WEIGHT(MT) 또는 NET(Kg) 없음/0 이하")
                    return result

                lot_no = str(lot_no).strip()
                picking_no = str(picking_no).strip()
                reason = str(reason).strip()

                is_sample = self._is_sample_row(row, col, reason)
                if is_sample:
                    tonbag_count = 1

                remark = self._safe_str(row, col.get("REMARK")) or ""
                return_date = self._safe_date(row, col.get("RETURN DATE"))
                if not return_date:
                    return_date = date.today().strftime("%Y-%m-%d")
                sales_order_no = self._safe_str(row, col.get("SALES ORDER NO")) or ""
                bl_no = self._safe_str(row, col.get("BL NO")) or ""

                result["items"].append({
                    "lot_no": lot_no,
                    "weight_mt": weight_mt,
                    "tonbag_count": tonbag_count,
                    "picking_no": picking_no,
                    "reason": reason,
                    "remark": remark,
                    "return_date": return_date,
                    "sales_order_no": sales_order_no,
                    "bl_no": bl_no,
                    "is_sample": is_sample,
                })

            result["parse_ok"] = len(result["items"]) > 0
            if result["parse_ok"]:
                logger.info(f"[ReturnInboundParser] 반품 {len(result['items'])}행 파싱 완료")
            else:
                result["errors"].append("❌ 유효한 데이터 행이 없음")
        except Exception as e:
            result["errors"].append(f"❌ 파싱 오류: {e}")
            logger.error(f"[ReturnInboundParser] 오류: {e}")

        return result

    def _find_header_row(self, df: Any) -> Optional[int]:
        for i in range(min(15, len(df))):
            row_vals = [str(v).strip() for v in df.iloc[i]]
            row_lower = [x.lower() for x in row_vals]
            if any("lot" in x and "no" in x for x in row_lower):
                return i
            if any(x in ("lot_no", "net_weight", "picking_no", "return_reason") for x in row_lower):
                return i
        return None

    def _safe_str(self, row: Any, col_idx: Optional[int]) -> Optional[str]:
        if col_idx is None:
            return None
        try:
            v = str(row.iloc[col_idx]).strip()
            return None if v in ("nan", "", "None") else v
        except Exception:
            return None

    def _safe_float(self, row: Any, col_idx: Optional[int]) -> Optional[float]:
        v = self._safe_str(row, col_idx)
        if v is None:
            return None
        try:
            return float(str(v).replace(",", ""))
        except ValueError:
            return None

    def _safe_date(self, row: Any, col_idx: Optional[int]) -> Optional[str]:
        v = self._safe_str(row, col_idx)
        if not v:
            return None
        if len(v) >= 10:
            return v[:10]
        return v

    def _is_sample_row(self, row: Any, col: dict, reason: str) -> bool:
        """샘플 반품 행 여부 (샘플이면 톤백 1개 고정)"""
        if reason and "샘플" in reason:
            return True
        if reason and "(SP)" in reason:
            return True
        return False


def parse_return_inbound_excel(file_path: str) -> dict:
    """진입점: Excel 경로 → 파싱 결과 dict."""
    return ReturnInboundParser().parse(file_path)


def parse_return_inbound_from_rows(rows: List[dict]) -> dict:
    """
    붙여넣기 데이터(입고 형식 컬럼) → 파싱 결과 dict.
    각 행은 lot_no, net_weight(Kg), picking_no, return_reason 필수.
    """
    result = {"parse_ok": False, "items": [], "errors": []}
    if not rows:
        result["errors"].append("❌ 입력된 데이터가 없습니다.")
        return result
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            result["errors"].append(f"행 {idx + 1}: dict가 아님")
            return result
        lot_no = _cell_str(row.get("lot_no"))
        net_kg = _cell_float(row.get("net_weight"))
        picking_no = _cell_str(row.get("picking_no"))
        reason = _cell_str(row.get("return_reason")) or _cell_str(row.get("reason"))
        if not lot_no:
            result["errors"].append(f"행 {idx + 1}: LOT NO 비어 있음")
            return result
        if not picking_no:
            result["errors"].append(f"행 {idx + 1}: PICKING NO 비어 있음")
            return result
        if not reason:
            result["errors"].append(f"행 {idx + 1}: 반품사유 비어 있음")
            return result
        if net_kg is None or net_kg <= 0:
            result["errors"].append(f"행 {idx + 1}: NET(Kg) 없음 또는 0 이하")
            return result
        weight_mt = round(net_kg / 1000.0, 3)
        tonbag_count = estimate_tonbag_count(net_kg)  # v8.6.1: 500 하드코딩 제거
        if reason and ("샘플" in reason or "(SP)" in reason):
            tonbag_count = 1
        remark = _cell_str(row.get("remark")) or ""
        result["items"].append({
            "lot_no": lot_no,
            "weight_mt": weight_mt,
            "tonbag_count": tonbag_count,
            "picking_no": picking_no,
            "reason": reason,
            "remark": remark,
            "return_date": date.today().strftime("%Y-%m-%d"),
            "sales_order_no": _cell_str(row.get("sales_order_no")) or "",
            "bl_no": _cell_str(row.get("bl_no")) or "",
            "is_sample": tonbag_count == 1 and ("샘플" in reason or "(SP)" in reason),
        })
    result["parse_ok"] = len(result["items"]) > 0
    if result["parse_ok"]:
        logger.info(f"[parse_return_inbound_from_rows] 반품 {len(result['items'])}행 파싱 완료")
    return result


def _cell_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s in ("nan", "", "None") else s


def _cell_float(v: Any) -> Optional[float]:
    s = _cell_str(v) if v is not None else ""
    if not s:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None
