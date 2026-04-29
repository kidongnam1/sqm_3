"""
SQM v6.0.0 — Picking List 처리 엔진
======================================

Picking List PDF 파싱 결과를 받아
inventory_tonbag 상태를 RESERVED → PICKED 로 전환하고
picking_table에 이력을 기록한다.

비즈니스 규칙:
    - LOT 단위 처리 (Batch number = lot_no)
    - RESERVED 상태인 톤백만 PICKED 전환 대상
    - qty_kg 기준으로 필요한 개수만큼만 PICKED, 나머지는 RESERVED 유지
    - 샘플 톤백(is_sample=1) 별도 처리
    - All-or-Nothing 트랜잭션 (실패 시 전체 롤백)
"""

import logging
import os
from typing import Any
from engine_modules.constants import (
    STATUS_RESERVED, STATUS_PICKED  # v9.0: 하드코딩 → 상수 교체
)

logger = logging.getLogger(__name__)

from engine_modules.constants import DEFAULT_TONBAG_WEIGHT as TONBAG_WEIGHT_KG  # v8.6.1: 500 하드코딩 제거


class PickingEngine:
    """
    Picking List 파싱 결과 → DB 반영 엔진
    SQMDatabase 인스턴스를 주입받아 사용.
    """

    def __init__(self, db: Any) -> None:
        self.db = db

    def check_duplicate(self, picking_no: str) -> dict:
        """
        동일 picking_no가 이미 처리됐는지 확인
        Returns: {"exists": bool, "count": int, "first_date": str}
        """
        rows = self.db.fetchall(
            """
            SELECT COUNT(*) as cnt, MIN(picking_date) as first_date
            FROM picking_table
            WHERE picking_no = ?
            """,
            (picking_no,),
        )
        row = rows[0] if rows else {}
        cnt = row.get("cnt", 0) or 0
        return {
            "exists": cnt > 0,
            "count": cnt,
            "first_date": row.get("first_date"),
        }

    def process(self, parsed: dict, source_file: str = "") -> dict:
        """
        Picking List 파싱 결과 → picking_table INSERT + tonbag PICKED 전환

        Returns:
            success, picked, sample_picked, skipped_lots, partial_lots, warnings, picking_no
        """
        result = {
            "success": False,
            "picked": 0,
            "sample_picked": 0,
            "skipped_lots": [],
            "partial_lots": [],
            "warnings": list(parsed.get("warnings", [])),
            "picking_no": parsed.get("picking_no"),
        }

        if not parsed.get("parse_ok"):
            result["warnings"].append("❌ PDF 파싱 실패 — 처리 중단")
            return result

        items = parsed.get("items", [])
        picking_no = parsed.get("picking_no", "")
        sales_order_no = parsed.get("sales_order_no", "")
        outbound_id = parsed.get("outbound_id", "")
        customer = parsed.get("customer", "")
        plan_loading = parsed.get("plan_loading_date", "")
        creation_date = parsed.get("creation_date", "")
        # v8.6.1 [BAG-WEIGHT-PRIORITY]: PDF 감지 bag_weight_kg를 TONBAG_WEIGHT_KG fallback보다 우선
        # parsed["bag_weight_kg"] = 0이면 미감지 → 기존 TONBAG_WEIGHT_KG(500) 유지
        _doc_bag_weight = float(parsed.get("bag_weight_kg") or 0)
        _fallback_weight = _doc_bag_weight if _doc_bag_weight >= 100 else TONBAG_WEIGHT_KG

        try:
            for item in items:
                lot_no = item["lot_no"]
                qty_kg = item["qty_kg"]
                is_sample = item["is_sample"]

                if is_sample:
                    n = self._process_sample(
                        lot_no,
                        qty_kg,
                        picking_no,
                        sales_order_no,
                        outbound_id,
                        customer,
                        plan_loading,
                        creation_date,
                        source_file,
                    )
                    result["sample_picked"] += n
                else:
                    n, remaining_reserved, skipped = self._process_normal(
                        lot_no,
                        qty_kg,
                        picking_no,
                        sales_order_no,
                        outbound_id,
                        customer,
                        plan_loading,
                        creation_date,
                        source_file,
                    )
                    result["picked"] += n
                    if skipped:
                        result["skipped_lots"].append(lot_no)
                        result["warnings"].append(
                            f"⚠️ {lot_no}: RESERVED 톤백 없음 — 스킵"
                        )
                    elif remaining_reserved and remaining_reserved > 0:
                        result["partial_lots"].append(lot_no)
                        result["warnings"].append(
                            f"ℹ️ {lot_no}: {n}개 PICKED, "
                            f"잔여 {remaining_reserved}개 RESERVED 유지"
                        )

            self.db.commit()
            result["success"] = True
            logger.info(
                f"[PickingEngine] 완료 — PICKED:{result['picked']} "
                f"샘플:{result['sample_picked']} 스킵:{len(result['skipped_lots'])}개"
            )
        except Exception as e:
            self.db.rollback()
            result["success"] = False
            result["warnings"].append(f"❌ 처리 중 오류 발생 (롤백): {e}")
            logger.error(f"[PickingEngine] 오류 → 롤백: {e}")

        return result

    def _process_normal(
        self,
        lot_no: str,
        qty_kg: float,
        picking_no: str,
        sales_order_no: str,
        outbound_id: str,
        customer: str,
        plan_loading: str,
        creation_date: str,
        source_file: str,
    ) -> tuple:
        """
        RESERVED 톤백 중 qty_kg 만큼 PICKED 전환
        Returns: (picked_count, remaining_reserved, is_skipped)
        """
        tonbags = self.db.fetchall(
            """
            SELECT id, lot_no, sub_lt, weight, tonbag_uid
            FROM inventory_tonbag
            WHERE lot_no = ? AND status = 'RESERVED'  # noqa: STATUS_RESERVED
            ORDER BY sub_lt ASC
            """,
            (lot_no,),
        )

        if not tonbags:
            return 0, 0, True

        remaining_kg = qty_kg
        picked_count = 0

        for tb in tonbags:
            if remaining_kg <= 0:
                break
            tb_weight = tb.get("weight") or _fallback_weight  # v8.6.1: PDF 감지값 우선

            # [RUBI-PHASE2] 랜덤출고 정책: Picking List 단계에서는 TONBAG 상태를 변경하지 않습니다.
            # 기존 로직(RESERVED→PICKED)은 운영 혼선을 유발하므로 비활성화합니다.
            # TONBAG 확정은 출고 스캔(UID) 순간에만 발생합니다.
            # (picking_table에는 계획/이력만 기록)
            self.db.execute(
                """
                INSERT INTO picking_table (
                    lot_no, tonbag_id, sub_lt, tonbag_uid,
                    picking_no, sales_order_no, outbound_id,
                    customer, plan_loading, creation_date,
                    source_file, qty_mt, qty_kg, unit,
                    is_sample, storage_location,
                    status, picking_date
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', datetime('now')
                )
                """,
                (
                    lot_no,
                    tb["id"],
                    tb.get("sub_lt"),
                    tb.get("tonbag_uid"),
                    picking_no,
                    sales_order_no,
                    outbound_id,
                    customer,
                    plan_loading,
                    creation_date,
                    source_file,
                    round(tb_weight / 1000.0, 4),
                    tb_weight,
                    "MT",
                    0,
                    "1001 GY logistics",
                ),
            )

            remaining_kg -= tb_weight
            picked_count += 1

        remaining_reserved = len(tonbags) - picked_count
        return picked_count, remaining_reserved, False

    def _process_sample(
        self,
        lot_no: str,
        qty_kg: float,
        picking_no: str,
        sales_order_no: str,
        outbound_id: str,
        customer: str,
        plan_loading: str,
        creation_date: str,
        source_file: str,
    ) -> int:
        """샘플 톤백 RESERVED → PICKED 전환 (lot당 1개)."""
        tonbags = self.db.fetchall(
            """
            SELECT id, lot_no, sub_lt, weight, tonbag_uid
            FROM inventory_tonbag
            WHERE lot_no = ? AND status = 'RESERVED'  # noqa: STATUS_RESERVED
              AND (is_sample = 1 OR sub_lt = 0)
            LIMIT 1
            """,
            (lot_no,),
        )

        if not tonbags:
            logger.debug(f"[PickingEngine] 샘플 없음: {lot_no}")
            return 0

        tb = tonbags[0]
        # [RUBI-PHASE2] 샘플도 Picking 단계에서 TONBAG 상태를 변경하지 않습니다.
        # 샘플 확정 역시 스캔 순간에만 반영됩니다.
        self.db.execute(
            """
            INSERT INTO picking_table (
                lot_no, tonbag_id, sub_lt, tonbag_uid,
                picking_no, sales_order_no, outbound_id,
                customer, plan_loading, creation_date,
                source_file, qty_mt, qty_kg, unit,
                is_sample, storage_location,
                status, picking_date
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', datetime('now')
            )
            """,
            (
                lot_no,
                tb["id"],
                tb.get("sub_lt"),
                tb.get("tonbag_uid"),
                picking_no,
                sales_order_no,
                outbound_id,
                customer,
                plan_loading,
                creation_date,
                source_file,
                round(qty_kg / 1000.0, 6),
                qty_kg,
                "KG",
                1,
                "1001 GY logistics",
            ),
        )
        return 1


def apply_picking_list_to_db(engine: Any, doc: dict, pdf_path: str) -> dict:
    """
    앱 엔진 + 파싱 결과(doc) + PDF 경로로 DB 반영 (RESERVED → PICKED).

    Args:
        engine: .db 속성을 가진 엔진 (SQMDatabase)
        doc: PickingListParser.parse() 또는 parse_picking_list_pdf() 반환 dict
        pdf_path: 원본 PDF 경로 (파일명 기록용)

    Returns:
        PickingEngine.process() 결과 dict

    Raises:
        RuntimeError: 처리 실패 시 (롤백 후)
    """
    db = getattr(engine, "db", engine)
    source_file = os.path.basename(pdf_path) if pdf_path else ""
    pe = PickingEngine(db)
    result = pe.process(doc, source_file=source_file)
    if not result["success"]:
        msg = "; ".join(result["warnings"]) if result["warnings"] else "DB 반영 실패"
        raise RuntimeError(msg)
    return result
