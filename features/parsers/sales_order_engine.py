# ============================================================
# SQM Sales Order Engine 원칙 (v8.0.5 확정 — 2026-03-16)
# ------------------------------------------------------------
# Sales order flow must not mutate inventory summary directly;
# it must update item status first and finalize lot totals
# via central recalc.
#
# 핵심 inventory 상태 = OUTBOUND
# SOLD = sold_table 이력 전용 (inventory_tonbag write 금지)
#
# P2 경로:
#   _process_items_grouped → P2_SALES_ORDER_ENGINE
#   _process_item          → P2_SALES_ORDER_ITEM
#   retry_pending          → P2_SALES_ORDER_RETRY
# ============================================================

"""
SQM v6.0.0 — Sales Order Excel 처리 엔진 (4·5단계)
===================================================

Sales Order Excel 파일을 파싱하고
picking_table에서 매칭된 톤백을 SOLD 처리한다.

비즈니스 규칙:
    - 매칭 기준: LOT NO + Picking No (둘 다 일치)
    - 개수 기준: CT/PLT 우선, 없으면 NW ÷ 500 역산
    - BL NO → sold_table에만 저장 (inventory 덮어쓰기 금지)
    - 중복 Sales Order → 경고 후 사용자 선택
    - 미매칭 LOT → sold_table에 PENDING 상태로 보관
    - 잔여 PICKED 존재 시 → 경고 반환 (GUI에서 팝업 표시)
    - All-or-Nothing 트랜잭션
"""

import hashlib
import json
import logging
import math
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

from engine_modules.constants import DEFAULT_TONBAG_WEIGHT as TONBAG_WEIGHT_KG  # v8.6.1: 500 하드코딩 제거


def _round_half_up(x: float) -> int:
    """0.5는 항상 올림(은행가 반올림 회피)."""
    return int(math.floor((x or 0) + 0.5))

# Excel 헤더 별칭 (대소문자/공백 차이 허용)
_HEADER_ALIASES = {
    "LOT NO": ["LOT NO", "Lot No", "LOTNO", "lot no"],
    "Picking No": ["Picking No", "Picking no", "PICKING NO", "picking no"],
    "SAP NO": ["SAP NO", "Sap No", "sap no"],
    "BL NO": ["BL NO", "Bl No", "bl no"],
    "Destination": ["Destination", "destination"],
    "SKU": ["SKU", "Sku", "sku"],
    "Delivery Date": ["Delivery Date", "Delibery Date", "Deliver Date", "delivery date"],
    "NW": ["NW", "Nw", "nw"],
    "CT/PLT": ["CT/PLT", "CT/plt", "CT PLT", "ct/plt"],
}


def _normalize_header(h: str) -> str:
    return (h or "").strip()


# ─────────────────────────────────────────
# Sales Order Excel 파서
# ─────────────────────────────────────────

class SalesOrderParser:
    """
    Sales Order Excel 파일 파싱

    파일 구조:
        Row 0     : 빈 행
        Row 1     : "Sales order No : 3266"
        Row 2     : 날짜
        Row 3     : 합계 정보
        Row 4     : 컬럼 헤더
        Row 5~    : 데이터

    반환: sales_order_no, parse_ok, items[], warnings[]
    """

    def parse(self, file_path: str) -> dict:
        try:
            import pandas as pd
        except ImportError:
            return {
                "sales_order_no": None,
                "parse_ok": False,
                "items": [],
                "warnings": ["❌ pandas 필요: pip install pandas openpyxl"],
            }

        result = {
            "sales_order_no": None,
            "parse_ok": False,
            "items": [],
            "warnings": [],
        }
        try:
            df = pd.read_excel(file_path, header=None, dtype=str)

            so_no = self._extract_so_no(df)
            result["sales_order_no"] = so_no

            header_row = self._find_header_row(df)
            if header_row is None:
                result["warnings"].append("❌ 헤더 행을 찾을 수 없음")
                return result

            headers = [
                str(v).strip() if v and str(v) != "nan" else ""
                for v in df.iloc[header_row]
            ]
            col = self._map_columns(headers)
            if col.get("LOT NO") is None:
                result["warnings"].append("❌ 필수 컬럼(LOT NO) 없음")
                return result

            for idx in range(header_row + 1, len(df)):
                row = df.iloc[idx]
                lot_no = self._safe_str(row, col.get("LOT NO"))
                if not lot_no or not re.match(r"^\d{10,}$", lot_no):
                    continue

                picking_no = self._safe_str(row, col.get("Picking No"))
                sap_no = self._safe_str(row, col.get("SAP NO"))
                bl_no = self._safe_str(row, col.get("BL NO"))
                customer = self._safe_str(row, col.get("Destination"))
                sku = self._safe_str(row, col.get("SKU"))
                delivery_date = self._safe_date(
                    row,
                    col.get("Delivery Date"),
                )
                nw_kg = self._safe_float(row, col.get("NW"))
                ct_plt = self._safe_int(row, col.get("CT/PLT"))
                is_sample = "(SP)" in (sku or "")

                result["items"].append({
                    "lot_no": lot_no,
                    "picking_no": picking_no,
                    "sap_no": sap_no,
                    "bl_no": bl_no,
                    "customer": customer,
                    "sku": sku,
                    "delivery_date": delivery_date,
                    "nw_kg": nw_kg or 0.0,
                    "ct_plt": ct_plt or 0,
                    "is_sample": is_sample,
                })

            result["parse_ok"] = len(result["items"]) > 0
            logger.info(
                f"[SalesOrderParser] SO#{so_no} 파싱완료: {len(result['items'])}행"
            )
        except Exception as e:
            result["warnings"].append(f"❌ 파싱 오류: {e}")
            logger.error(f"[SalesOrderParser] 오류: {e}")

        return result

    def _extract_so_no(self, df: Any) -> Optional[str]:
        """Row 1에서 Sales Order No 추출"""
        try:
            cell = str(df.iloc[1, 0])
            m = re.search(r"(\d+)\s*$", cell)
            return m.group(1) if m else None
        except Exception:
            return None

    def _find_header_row(self, df: Any) -> Optional[int]:
        """LOT NO 컬럼이 있는 헤더 행 번호 반환"""
        for i in range(min(10, len(df))):
            row_vals = [str(v).strip() for v in df.iloc[i]]
            if "LOT NO" in row_vals or "Lot No" in row_vals:
                return i
        return None

    def _map_columns(self, headers: list) -> dict:
        """헤더 목록 → 표준 컬럼명:인덱스 매핑 (별칭·대소문자 무시)"""
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
        return mapping

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
            return float(v.replace(",", ""))
        except ValueError:
            return None

    def _safe_int(self, row: Any, col_idx: Optional[int]) -> Optional[int]:
        v = self._safe_float(row, col_idx)
        return int(v) if v is not None else None

    def _safe_date(self, row: Any, col_idx: Optional[int]) -> Optional[str]:
        v = self._safe_str(row, col_idx)
        if not v:
            return None
        return v[:10] if len(v) >= 10 else v


# ─────────────────────────────────────────
# Sales Order 처리 엔진 (4·5단계)
# ─────────────────────────────────────────

class SalesOrderEngine:
    """
    Sales Order Excel → picking_table 매칭 → SOLD/PENDING 처리

    Returns:
        success, sales_order_no, sold, pending,
        remaining_picked, skipped[], warnings[]
    """

    def __init__(self, db: Any) -> None:
        self.db = db

    def _compute_need_count(self, item: dict) -> int:
        """라인별 필요 톤백 수 계산(CT/PLT 우선, 없으면 NW 기반)."""
        ct_plt = item.get("ct_plt")
        nw_kg = item.get("nw_kg")
        is_sample = bool(item.get("is_sample"))
        try:
            if ct_plt and int(ct_plt) > 0:
                return int(ct_plt)
        except (ValueError, TypeError) as e:
            logger.debug(f"[SO파서] 톤백 수 파싱 실패: {e}")
        try:
            if nw_kg and float(nw_kg) > 0:
                unit_w = 1.0 if is_sample else TONBAG_WEIGHT_KG
                return max(1, _round_half_up((float(nw_kg) or 0.0) / unit_w))
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.debug(f"[SO파서] 중량→수량 변환 실패: {e}")
        return 1

    def _prefetch_picking_rows(self, lot_no: str, picking_no: str, is_sample_flag: int, limit: int) -> list:
        """(LOT, PickingNo, is_sample) 그룹 단위 ACTIVE 선조회."""
        if not lot_no or not picking_no or limit <= 0:
            return []
        try:
            return self.db.fetchall(
                """
                SELECT id, lot_no, tonbag_id, sub_lt, tonbag_uid, qty_kg, is_sample
                FROM picking_table
                WHERE lot_no = ? AND picking_no = ? AND status = 'ACTIVE'
                  AND COALESCE(is_sample, 0) = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (lot_no, picking_no, int(is_sample_flag or 0), int(limit)),
            )
        except Exception:
            # 구버전 DB(is_sample 컬럼 미존재) 폴백
            try:
                return self.db.fetchall(
                    """
                    SELECT id, lot_no, tonbag_id, sub_lt, tonbag_uid, qty_kg
                    FROM picking_table
                    WHERE lot_no = ? AND picking_no = ? AND status = 'ACTIVE'
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (lot_no, picking_no, int(limit)),
                )
            except Exception:
                return []

    def _process_items_grouped(self, items: list, so_no: str, so_file: str, result: dict) -> None:
        """
        v6.2.3: 그룹 선조회 + FIFO + 배치 반영.
        - (lot_no, picking_no, is_sample) 단위로 prefetch
        - 부분 SOLD 금지(부족 시 PENDING)
        """
        groups = {}
        ordered_keys = []
        for item in items:
            lot_no = item.get("lot_no") or ""
            picking_no = item.get("picking_no") or ""
            is_sample_flag = 1 if bool(item.get("is_sample")) else 0
            key = (lot_no, picking_no, is_sample_flag)
            if key not in groups:
                groups[key] = []
                ordered_keys.append(key)
            item["_need_count"] = self._compute_need_count(item)
            groups[key].append(item)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        picking_updates = []   # (so_no, id)
        tonbag_updates = []    # (so_no, tonbag_id)
        inventory_delta = {}   # lot_no -> kg sum
        sold_rows = []         # sold_table rows
        pending_rows = []      # sold_table PENDING rows
        movement_rows = []     # stock_movement rows

        for lot_no, picking_no, is_sample_flag in ordered_keys:
            group_items = groups[(lot_no, picking_no, is_sample_flag)]
            total_need = sum(int(it.get("_need_count") or 1) for it in group_items)
            pool = self._prefetch_picking_rows(lot_no, picking_no, is_sample_flag, total_need)
            ptr = 0

            for item in group_items:
                need_count = int(item.get("_need_count") or 1)

                # picking_no 누락 또는 수량 부족 시 부분처리 금지 → PENDING
                if not picking_no or ptr + need_count > len(pool):
                    found = 0 if not picking_no else max(0, len(pool) - ptr)
                    pending_rows.append((
                        item["lot_no"], so_no, so_file, item["picking_no"], item["sap_no"], item["bl_no"],
                        item["customer"], item["sku"], item["delivery_date"],
                        round((item["nw_kg"] or 0) / 1000.0, 4), item["nw_kg"] or 0, need_count,
                    ))
                    result["pending"] += 1
                    reason = "Picking No 없음 → PENDING 보관" if not picking_no else (
                        f"필요 {need_count}개 대비 ACTIVE {found}개 (부분처리 금지, PENDING)"
                    )
                    result["skipped"].append({"lot_no": lot_no, "picking_no": picking_no, "reason": reason})
                    result["warnings"].append(f"⚠️ {lot_no} (PK:{picking_no}): {reason}")
                    continue

                alloc_rows = pool[ptr: ptr + need_count]
                ptr += need_count
                lot_kg = 0.0

                for pk_row in alloc_rows:
                    pid = pk_row.get("id")
                    if pid is not None:
                        picking_updates.append((so_no, pid))
                    tonbag_id = pk_row.get("tonbag_id")
                    if tonbag_id:
                        tonbag_updates.append((so_no, tonbag_id))

                    qty_kg = pk_row.get("qty_kg")
                    if qty_kg is None or qty_kg == "":
                        qty_kg = 1.0 if bool(item.get("is_sample")) else TONBAG_WEIGHT_KG
                    try:
                        qty_kg = float(qty_kg)
                    except Exception:
                        qty_kg = 0.0

                    lot_kg += qty_kg
                    sold_rows.append((
                        item["lot_no"], tonbag_id, pk_row.get("sub_lt"), pk_row.get("tonbag_uid"), pid,
                        so_no, so_file, item["picking_no"], item["sap_no"], item["bl_no"], item["customer"],
                        item["sku"], item["delivery_date"], round(qty_kg / 1000.0, 4), qty_kg, item["ct_plt"] or 0,
                    ))

                if lot_kg > 0:
                    inventory_delta[lot_no] = float(inventory_delta.get(lot_no, 0.0)) + lot_kg
                    movement_rows.append((lot_no, lot_kg, f"SO#{so_no}"))
                result["sold"] += len(alloc_rows)

        if hasattr(self.db, "executemany"):
            if picking_updates:
                self.db.executemany(
                    """
                    UPDATE picking_table
                    SET status = 'OUTBOUND', sold_date = ?, sales_order_no = ?
                    WHERE id = ?
                    """,
                    [(now, so, pid) for so, pid in picking_updates],
                )
            if tonbag_updates:
                self.db.executemany(
                    """
                    UPDATE inventory_tonbag
                    SET status = 'OUTBOUND', outbound_date = ?, sale_ref = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    [(now, so, now, tid) for so, tid in tonbag_updates],
                )
            if inventory_delta:
                self.db.executemany(
                    """
                    UPDATE inventory
                    SET current_weight = MAX(0, current_weight - ?), updated_at = ?
                    WHERE lot_no = ?
                    """,
                    [(kg, now, lot) for lot, kg in inventory_delta.items()],
                )
                # v8.7.1 [RECALC-PARITY]: 배치 경로에도 중앙 재계산 추가.
                # 이전: 배치 경로(기본 경로)는 delta만 빼고 _recalc_current_weight 호출 안 함.
                # 샘플 1개만 판매 시 current_weight가 1kg 감소 (샘플은 current_weight 비포함인데).
                # → 누적 drift 발생. 비배치 경로(line 463-467)와 동일하게 recalc.
                engine = getattr(self, '_engine', None) or getattr(self, 'engine', None)
                if engine and hasattr(engine, '_recalc_current_weight'):
                    for lot in inventory_delta:
                        try:
                            engine._recalc_current_weight(lot, reason='P2_SALES_ORDER_ENGINE_BATCH')
                        except Exception as _re:
                            logger.warning("[P2_RECALC] %s 재계산 실패: %s", lot, _re)
            if sold_rows:
                self.db.executemany(
                    """
                    INSERT INTO sold_table (
                        lot_no, tonbag_id, sub_lt, tonbag_uid, picking_id,
                        sales_order_no, sales_order_file,
                        picking_no, sap_no, bl_no, customer, sku,
                        delivery_date, sold_qty_mt, sold_qty_kg, ct_plt,
                        status, sold_date, created_at, created_by
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'SOLD', ?, ?, 'system'
                    )
                    """,
                    [row + (now, now) for row in sold_rows],
                )
            if pending_rows:
                self.db.executemany(
                    """
                    INSERT INTO sold_table (
                        lot_no, sales_order_no, sales_order_file,
                        picking_no, sap_no, bl_no, customer, sku,
                        delivery_date, sold_qty_mt, sold_qty_kg, ct_plt,
                        status, created_at, created_by
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, 'system'
                    )
                    """,
                    [row + (now,) for row in pending_rows],
                )
            if movement_rows:
                self.db.executemany(
                    """
                    INSERT INTO stock_movement
                        (lot_no, movement_type, qty_kg, remarks, movement_date, created_at)
                    VALUES (?, 'SOLD', ?, ?, ?, ?)
                    """,
                    [(lot, qty, remarks, now, now) for lot, qty, remarks in movement_rows],
                )
        else:
            for so, pid in picking_updates:
                self.db.execute(
                    "UPDATE picking_table SET status='OUTBOUND', sold_date=?, sales_order_no=? WHERE id=?",
                    (now, so, pid),
                )
            for so, tid in tonbag_updates:
                self.db.execute(
                    "UPDATE inventory_tonbag SET status='OUTBOUND', outbound_date=?, sale_ref=?, updated_at=? WHERE id=?",
                    (now, so, now, tid),
                )
            for lot, kg in inventory_delta.items():
                self.db.execute(
                    "UPDATE inventory SET current_weight=MAX(0, current_weight-?), updated_at=? WHERE lot_no=?",
                    (kg, now, lot),
                )
            # v8.0.4 [P2]: 출고 후 current_weight 중앙 재계산
            engine = getattr(self, '_engine', None) or getattr(self, 'engine', None)
            if engine and hasattr(engine, '_recalc_current_weight'):
                for lot in inventory_delta:
                    engine._recalc_current_weight(lot, reason='P2_SALES_ORDER_ENGINE')
            for row in sold_rows:
                self.db.execute(
                    """
                    INSERT INTO sold_table (
                        lot_no, tonbag_id, sub_lt, tonbag_uid, picking_id,
                        sales_order_no, sales_order_file,
                        picking_no, sap_no, bl_no, customer, sku,
                        delivery_date, sold_qty_mt, sold_qty_kg, ct_plt,
                        status, sold_date, created_at, created_by
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'SOLD', ?, ?, 'system'
                    )
                    """,
                    row + (now, now),
                )
            for row in pending_rows:
                self.db.execute(
                    """
                    INSERT INTO sold_table (
                        lot_no, sales_order_no, sales_order_file,
                        picking_no, sap_no, bl_no, customer, sku,
                        delivery_date, sold_qty_mt, sold_qty_kg, ct_plt,
                        status, created_at, created_by
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, 'system'
                    )
                    """,
                    row + (now,),
                )
            for lot, qty, remarks in movement_rows:
                self.db.execute(
                    """
                    INSERT INTO stock_movement
                        (lot_no, movement_type, qty_kg, remarks, movement_date, created_at)
                    VALUES (?, 'SOLD', ?, ?, ?, ?)
                    """,
                    (lot, qty, remarks, now, now),
                )

    def check_duplicate(self, sales_order_no: str) -> dict:
        """
        동일 Sales Order No가 이미 처리됐는지 확인
        Returns: {"exists": bool, "sold_count": int, "first_date": str}
        """
        rows = self.db.fetchall(
            """
            SELECT COUNT(*) as cnt, MIN(created_at) as first_date
            FROM sold_table
            WHERE sales_order_no = ? AND status != 'PENDING'
            """,
            (sales_order_no,),
        )
        row = rows[0] if rows else {}
        cnt = row.get("cnt", 0) or 0
        return {
            "exists": cnt > 0,
            "sold_count": cnt,
            "first_date": row.get("first_date"),
        }

    def _pending_exists_for_item(self, sales_order_no: str, item: dict) -> bool:
        """해당 SO/LOT/PickingNo 기준 미해결 PENDING 존재 여부."""
        lot_no = item.get("lot_no") or ""
        picking_no = item.get("picking_no") or ""
        if not lot_no:
            return False
        try:
            rows = self.db.fetchall(
                """
                SELECT COUNT(*) AS cnt
                FROM sold_table
                WHERE sales_order_no = ?
                  AND status = 'PENDING'
                  AND lot_no = ?
                  AND COALESCE(picking_no, '') = ?
                """,
                (sales_order_no, lot_no, picking_no),
            )
            return int((rows[0] or {}).get("cnt", 0) or 0) > 0
        except Exception:
            return False

    def _resolve_pending_for_item(self, sales_order_no: str, item: dict) -> int:
        """retry_pending_only에서 기존 PENDING을 RESOLVED로 마감."""
        lot_no = item.get("lot_no") or ""
        picking_no = item.get("picking_no") or ""
        if not lot_no:
            return 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.db.execute(
            """
            UPDATE sold_table
            SET status = 'RESOLVED',
                remark = COALESCE(remark, '') || ?
            WHERE sales_order_no = ?
              AND status = 'PENDING'
              AND lot_no = ?
              AND COALESCE(picking_no, '') = ?
            """,
            (f" | resolved@{now}", sales_order_no, lot_no, picking_no),
        )
        try:
            return int(cur.rowcount or 0)
        except Exception:
            return 0

    def _insert_sales_order_import_log(
        self,
        import_run_id: str,
        so_no: str,
        so_file: str,
        file_hash: str,
        mode: str,
        sold_count: int,
        pending_count: int,
        warnings: list,
        elapsed_ms: int,
    ) -> Optional[int]:
        """Sales Order 업로드 실행 로그를 남긴다."""
        try:
            warnings_json = json.dumps(warnings or [], ensure_ascii=False)
            cur = self.db.execute(
                """
                INSERT INTO sales_order_import_log (
                    import_run_id, sales_order_no, file_name, file_hash,
                    mode, sold_count, pending_count, warnings_json, elapsed_ms,
                    created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_run_id,
                    so_no or "",
                    so_file or "",
                    file_hash or "",
                    mode or "normal",
                    int(sold_count or 0),
                    int(pending_count or 0),
                    warnings_json,
                    int(elapsed_ms or 0),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "system",
                ),
            )
            try:
                return int(cur.lastrowid)
            except Exception:
                return None
        except Exception as e:
            logger.debug(f"[SalesOrderEngine] import_log 기록 스킵: {e}")
            return None

    def process(
        self,
        file_path: str,
        sales_order_file: str = "",
        allow_duplicate: bool = False,
        mode: str = "normal",
        file_hash: str = "",
    ) -> dict:
        """
        Sales Order Excel 파일 → SOLD/PENDING 처리

        Args:
            file_path        : Excel 파일 경로
            sales_order_file : 원본 파일명 (표시용)
        """
        if not sales_order_file:
            sales_order_file = os.path.basename(file_path)

        result = {
            "success": False,
            "sales_order_no": None,
            "sold": 0,
            "pending": 0,
            "remaining_picked": 0,
            "skipped": [],
            "warnings": [],
            "duplicate": None,
            "mode": mode,
            "import_run_id": uuid.uuid4().hex,
            "resolved_pending": 0,
            "import_log_id": None,
            "elapsed_ms": 0,
        }

        parser = SalesOrderParser()
        parsed = parser.parse(file_path)

        if not parsed["parse_ok"]:
            result["warnings"].extend(parsed.get("warnings", []))
            result["warnings"].append("❌ Sales Order 파싱 실패")
            return result

        so_no = parsed["sales_order_no"]
        items = parsed["items"]
        result["sales_order_no"] = so_no
        result["warnings"].extend(parsed.get("warnings", []))
        result["file_hash"] = file_hash or ""

        dup = self.check_duplicate(so_no)
        result["duplicate"] = dup
        if dup.get("exists") and (not allow_duplicate) and (mode != "retry_pending_only"):
            result["warnings"].append(
                f"⚠️ 중복 Sales Order 감지: SO#{so_no} — 기존 SOLD {dup.get('sold_count', 0)}건"
            )
            result["warnings"].append("중복 방지 정책에 따라 기본 차단되었습니다.")
            return result

        started = time.perf_counter()
        try:
            if hasattr(self.db, "transaction"):
                with self.db.transaction("IMMEDIATE"):
                    if mode == "retry_pending_only":
                        retry_items = [it for it in items if self._pending_exists_for_item(so_no, it)]
                        skipped = len(items) - len(retry_items)
                        if skipped > 0:
                            result["warnings"].append(f"ℹ️ retry_pending_only: 기존 PENDING 없는 {skipped}행은 스킵")
                        self._process_items_grouped(retry_items, so_no, sales_order_file, result)
                        for it in retry_items:
                            result["resolved_pending"] += self._resolve_pending_for_item(so_no, it)
                    else:
                        self._process_items_grouped(items, so_no, sales_order_file, result)
            else:
                if mode == "retry_pending_only":
                    retry_items = [it for it in items if self._pending_exists_for_item(so_no, it)]
                    skipped = len(items) - len(retry_items)
                    if skipped > 0:
                        result["warnings"].append(f"ℹ️ retry_pending_only: 기존 PENDING 없는 {skipped}행은 스킵")
                    self._process_items_grouped(retry_items, so_no, sales_order_file, result)
                    for it in retry_items:
                        result["resolved_pending"] += self._resolve_pending_for_item(so_no, it)
                else:
                    self._process_items_grouped(items, so_no, sales_order_file, result)
                self.db.commit()
            result["success"] = True
            result["remaining_picked"] = self._count_remaining_picked()
            result["elapsed_ms"] = int((time.perf_counter() - started) * 1000)

            result["import_log_id"] = self._insert_sales_order_import_log(
                import_run_id=result["import_run_id"],
                so_no=so_no,
                so_file=sales_order_file,
                file_hash=file_hash,
                mode=mode,
                sold_count=result["sold"],
                pending_count=result["pending"],
                warnings=result["warnings"],
                elapsed_ms=result["elapsed_ms"],
            )

            logger.info(
                f"[SalesOrderEngine] SO#{so_no} 완료 — "
                f"SOLD:{result['sold']} PENDING:{result['pending']} "
                f"잔여PICKED:{result['remaining_picked']} "
                f"elapsed={result['elapsed_ms']}ms mode={mode}"
            )
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as e:
                logger.warning(f"[SO파서] 롤백 실패 (데이터 손실 위험): {e}")
            result["success"] = False
            result["warnings"].append(f"❌ 처리 오류 (롤백): {e}")
            logger.error(f"[SalesOrderEngine] 오류 → 롤백: {e}")

        return result

    def _process_item(
        self,
        item: dict,
        so_no: str,
        so_file: str,
        result: dict,
    ) -> None:
        """LOT 1개 처리: picking_table 매칭 → SOLD 또는 PENDING"""
        lot_no = item["lot_no"]
        picking_no = item["picking_no"] or ""
        ct_plt = item["ct_plt"]
        nw_kg = item["nw_kg"]
        is_sample = item["is_sample"]

        if ct_plt and ct_plt > 0:
            need_count = ct_plt
        elif nw_kg and nw_kg > 0:
            unit_w = 1.0 if is_sample else TONBAG_WEIGHT_KG
            need_count = max(1, round(nw_kg / unit_w))
        else:
            need_count = 1

        picking_rows = self.db.fetchall(
            """
            SELECT id, lot_no, tonbag_id, sub_lt, tonbag_uid, qty_kg, is_sample
            FROM picking_table
            WHERE lot_no = ? AND picking_no = ? AND status = 'ACTIVE'
            ORDER BY id ASC
            LIMIT ?
            """,
            (lot_no, picking_no, need_count),
        )

        if not picking_rows:
            self._insert_sold_pending(item, so_no, so_file, need_count)
            result["pending"] += 1
            result["skipped"].append({
                "lot_no": lot_no,
                "picking_no": picking_no,
                "reason": "picking_table 매칭 없음 (PENDING 보관)",
            })
            result["warnings"].append(
                f"⚠️ {lot_no} (PK:{picking_no}): PICKED 없음 → PENDING 보관"
            )
            return

        for pk_row in picking_rows:
            self.db.execute(
                """
                UPDATE picking_table
                SET status = 'OUTBOUND', sold_date = datetime('now')
                WHERE id = ?
                """,
                (pk_row["id"],),
            )

            if pk_row.get("tonbag_id"):
                self.db.execute(
                    """
                    UPDATE inventory_tonbag
                    SET status = 'OUTBOUND', outbound_date = datetime('now'),
                        sale_ref = ?, updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (so_no, pk_row["tonbag_id"]),
                )
                qty_kg = pk_row.get("qty_kg") or TONBAG_WEIGHT_KG
                self.db.execute(
                    """
                    UPDATE inventory
                    SET current_weight = MAX(0, current_weight - ?),
                        updated_at = datetime('now')
                    WHERE lot_no = ?
                    """,
                    (qty_kg, lot_no),
                )

            self._insert_sold_record(
                item,
                so_no,
                so_file,
                pk_row["id"],
                pk_row.get("tonbag_id"),
                pk_row.get("sub_lt"),
                pk_row.get("tonbag_uid"),
                status="SOLD",
            )
            self._insert_movement(lot_no, pk_row.get("qty_kg", 0), so_no)
            # v8.0.5 [P2]: _process_item 출고 후 재계산
            _eng = getattr(self, '_engine', None) or getattr(self, 'engine', None)
            if _eng and hasattr(_eng, '_recalc_current_weight'):
                _eng._recalc_current_weight(lot_no, reason='P2_SALES_ORDER_ITEM')
            result["sold"] += 1

    def _insert_sold_pending(
        self,
        item: dict,
        so_no: str,
        so_file: str,
        need_count: int,
    ) -> None:
        """PENDING 상태 sold_table 레코드 삽입"""
        self.db.execute(
            """
            INSERT INTO sold_table (
                lot_no, sales_order_no, sales_order_file,
                picking_no, sap_no, bl_no, customer, sku,
                delivery_date, sold_qty_mt, sold_qty_kg, ct_plt,
                status, created_at, created_by
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', datetime('now'), 'system'
            )
            """,
            (
                item["lot_no"],
                so_no,
                so_file,
                item["picking_no"],
                item["sap_no"],
                item["bl_no"],
                item["customer"],
                item["sku"],
                item["delivery_date"],
                round((item["nw_kg"] or 0) / 1000.0, 4),
                item["nw_kg"] or 0,
                need_count,
            ),
        )

    def _insert_sold_record(
        self,
        item: dict,
        so_no: str,
        so_file: str,
        picking_id: int,
        tonbag_id: Optional[int],
        sub_lt: Optional[int],
        tonbag_uid: Optional[str],
        status: str = "SOLD",
    ) -> None:
        """SOLD 상태 sold_table 레코드 삽입"""
        self.db.execute(
            """
            INSERT INTO sold_table (
                lot_no, tonbag_id, sub_lt, tonbag_uid, picking_id,
                sales_order_no, sales_order_file,
                picking_no, sap_no, bl_no, customer, sku,
                delivery_date, sold_qty_mt, sold_qty_kg, ct_plt,
                status, sold_date, created_at, created_by
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, datetime('now'), datetime('now'), 'system'
            )
            """,
            (
                item["lot_no"],
                tonbag_id,
                sub_lt,
                tonbag_uid,
                picking_id,
                so_no,
                so_file,
                item["picking_no"],
                item["sap_no"],
                item["bl_no"],
                item["customer"],
                item["sku"],
                item["delivery_date"],
                round((item["nw_kg"] or 0) / 1000.0, 4),
                item["nw_kg"] or 0,
                item["ct_plt"] or 0,
                status,
            ),
        )

    def _insert_movement(self, lot_no: str, qty_kg: float, so_no: str) -> None:
        """stock_movement 출고 이력 기록"""
        try:
            self.db.execute(
                """
                INSERT INTO stock_movement
                    (lot_no, movement_type, qty_kg, remarks, movement_date, created_at)
                VALUES (?, 'SOLD', ?, ?, datetime('now'), datetime('now'))
                """,
                (lot_no, qty_kg, f"SO#{so_no}"),
            )
        except Exception as e:
            logger.debug(f"[SalesOrderEngine] movement 기록 스킵: {e}")

    def _count_remaining_picked(self) -> int:
        """처리 후 잔여 PICKED 톤백 수 (5단계 경고용)"""
        try:
            rows = self.db.fetchall(
                "SELECT COUNT(*) as cnt FROM inventory_tonbag WHERE status = 'PICKED'"
            )
            return rows[0].get("cnt", 0) if rows else 0
        except Exception:
            return 0

    def retry_pending(self, sales_order_no: str) -> dict:
        """
        PENDING 상태 LOT를 다시 picking_table 매칭 시도
        Picking List가 뒤늦게 도착한 경우 사용.
        SOLD 전환 시 inventory current_weight 차감 및 stock_movement 기록 포함.
        """
        result = {
            "retried": 0,
            "newly_sold": 0,
            "still_pending": 0,
            "warnings": [],
        }
        try:
            pending_rows = self.db.fetchall(
                """
                SELECT id, lot_no, picking_no, sap_no, bl_no,
                       customer, sku, delivery_date,
                       sold_qty_kg, ct_plt,
                       sales_order_no, sales_order_file
                FROM sold_table
                WHERE sales_order_no = ? AND status = 'PENDING'
                """,
                (sales_order_no,),
            )

            for pr in pending_rows:
                result["retried"] += 1
                lot_no = pr["lot_no"]
                picking_no = pr["picking_no"] or ""
                need_count = pr["ct_plt"] or 1

                picking_rows = self.db.fetchall(
                    """
                    SELECT id, tonbag_id, sub_lt, tonbag_uid, qty_kg
                    FROM picking_table
                    WHERE lot_no = ? AND picking_no = ? AND status = 'ACTIVE'
                    ORDER BY id ASC LIMIT ?
                    """,
                    (lot_no, picking_no, need_count),
                )

                if picking_rows:
                    self.db.execute(
                        "UPDATE sold_table SET status='OUTBOUND', sold_date=datetime('now') WHERE id=?",
                        (pr["id"],),
                    )
                    for pk in picking_rows:
                        self.db.execute(
                            "UPDATE picking_table SET status='OUTBOUND', sold_date=datetime('now') WHERE id=?",
                            (pk["id"],),
                        )
                        if pk.get("tonbag_id"):
                            self.db.execute(
                                "UPDATE inventory_tonbag SET status='OUTBOUND', outbound_date=datetime('now') WHERE id=?",
                                (pk["tonbag_id"],),
                            )
                            qty_kg = pk.get("qty_kg") or TONBAG_WEIGHT_KG
                            self.db.execute(
                                """
                                UPDATE inventory
                                SET current_weight = MAX(0, current_weight - ?),
                                    updated_at = datetime('now')
                                WHERE lot_no = ?
                                """,
                                (qty_kg, lot_no),
                            )
                            self._insert_movement(lot_no, qty_kg, sales_order_no)
                            # v8.0.5 [P2]: retry_pending 출고 후 재계산
                            _eng = getattr(self, '_engine', None) or getattr(self, 'engine', None)
                            if _eng and hasattr(_eng, '_recalc_current_weight'):
                                _eng._recalc_current_weight(lot_no, reason='P2_SALES_ORDER_RETRY')
                    result["newly_sold"] += 1
                else:
                    result["still_pending"] += 1

            self.db.commit()
            logger.info(
                f"[SalesOrderEngine] retry_pending SO#{sales_order_no}: "
                f"신규SOLD={result['newly_sold']} 여전히PENDING={result['still_pending']}"
            )
        except Exception as e:
            self.db.rollback()
            result["warnings"].append(f"❌ 재처리 오류: {e}")
            logger.error(f"[SalesOrderEngine] retry_pending 오류: {e}")

        return result


def apply_sales_order_to_db(
    engine: Any,
    file_path: str,
    allow_duplicate: bool = False,
    mode: str = "normal",
) -> dict:
    """
    앱 엔진 + Sales Order Excel 경로로 DB 반영 (PICKED → SOLD/PENDING).

    Args:
        engine   : .db 속성을 가진 엔진 (SQMDatabase)
        file_path: Sales Order Excel 파일 경로

    Returns:
        SalesOrderEngine.process() 결과 dict

    Raises:
        RuntimeError: 처리 실패 시 (롤백 후)
    """
    db = getattr(engine, "db", engine)
    pe = SalesOrderEngine(db)
    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
    except Exception:
        file_hash = ""
    result = pe.process(
        file_path,
        sales_order_file=os.path.basename(file_path),
        allow_duplicate=allow_duplicate,
        mode=mode,
        file_hash=file_hash,
    )
    if not result["success"]:
        msg = "; ".join(result["warnings"]) if result["warnings"] else "Sales Order 처리 실패"
        raise RuntimeError(msg)
    return result
