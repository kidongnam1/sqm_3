"""
SQM v6.0 — 반품 입고 엔진
==========================

반품 Excel 파싱 결과를 받아 한 트랜잭션으로:
- picking_table에서 LOT NO + PICKING NO 매칭 (ACTIVE/SOLD), sub_lt 순
- 톤백 개수만큼 확보 실패 시 전체 롤백
- return_history, stock_movement, inventory_tonbag → AVAILABLE, inventory 복구
- picking_table / sold_table → RETURNED
"""

import logging
import sqlite3
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


def process_return_inbound(engine: Any, parsed: dict, source_file: str = "") -> dict:
    """
    반품 Excel 파싱 결과 → DB 반영 (한 트랜잭션, 1건이라도 실패 시 전체 롤백).

    Args:
        engine: .db, ._recalc_lot_status 갖는 엔진 (ReturnMixin 포함)
        parsed: ReturnInboundParser.parse() 반환값
        source_file: 원본 파일명 (표시용)

    Returns:
        success, returned, errors, details
    """
    db = getattr(engine, "db", engine)
    result = {"success": False, "returned": 0, "errors": [], "details": []}

    if not parsed.get("parse_ok"):
        result["errors"] = list(parsed.get("errors", ["파싱 실패"]))
        return result

    items = parsed.get("items", [])
    if not items:
        result["errors"].append("처리할 반품 행이 없습니다.")
        return result

    # 1) 각 행별로 picking_table에서 (lot_no, sub_lt, tonbag_id, weight, ...) 목록 확보
    return_rows = []  # (lot_no, sub_lt, reason, remark, picking_id, tb_weight, tonbag_row)
    for row in items:
        lot_no = row["lot_no"]
        picking_no = row["picking_no"]
        tonbag_count = row["tonbag_count"]
        reason = row.get("reason", "")
        remark = row.get("remark", "")

        rows_pt = db.fetchall(
            """
            SELECT id, lot_no, tonbag_id, sub_lt
            FROM picking_table
            WHERE lot_no = ? AND picking_no = ? AND status IN ('ACTIVE', 'SOLD')
            ORDER BY sub_lt ASC
            LIMIT ?
            """,
            (lot_no, picking_no, tonbag_count),
        )

        if not rows_pt or len(rows_pt) < tonbag_count:
            need, got = tonbag_count, len(rows_pt) if rows_pt else 0
            result["errors"].append(
                f"LOT {lot_no} / PICKING NO {picking_no}: 필요 {need}개, 매칭 {got}개 — 전체 중단"
            )
            return result

        # v9.1: N+1 쿼리 → 일괄 조회로 개선
        # 기존: for r in rows_pt: fetchone(lot_no, sub_lt) → rows_pt 수만큼 쿼리
        # 수정: IN 절로 한 번에 조회 → 쿼리 1회
        if rows_pt:
            _sub_lts = [r["sub_lt"] for r in rows_pt]
            _placeholders = ",".join(["?"] * len(_sub_lts))
            _tonbag_rows = db.fetchall(
                f"SELECT sub_lt, weight, status, picked_to, sale_ref "
                f"FROM inventory_tonbag "
                f"WHERE lot_no = ? AND sub_lt IN ({_placeholders})",
                [lot_no] + _sub_lts,
            )
            _tonbag_map = {
                row["sub_lt"]: row for row in (_tonbag_rows or [])
            }
        else:
            _tonbag_map = {}

        for r in rows_pt:
            tonbag = _tonbag_map.get(r["sub_lt"])
            if not tonbag:
                result["errors"].append(f"톤백 없음: {r['lot_no']}-{r['sub_lt']}")
                return result
            if tonbag["status"] not in ("PICKED", "CONFIRMED", "SHIPPED", "SOLD", "RESERVED"):
                result["errors"].append(f"반품 불가 상태 {tonbag['status']}: {r['lot_no']}-{r['sub_lt']}")
                return result
            tb_weight = float(tonbag["weight"] or 0)
            return_rows.append({
                "lot_no": r["lot_no"],
                "sub_lt": r["sub_lt"],
                "reason": reason,
                "remark": remark,
                "picking_id": r["id"],
                "tb_weight": tb_weight,
                "tonbag": tonbag,
            })

    # 2) 한 트랜잭션으로 반품 + RETURNED 처리
    try:
        with db.transaction("IMMEDIATE"):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            today = date.today()

            for r in return_rows:
                lot_no = r["lot_no"]
                sub_lt = r["sub_lt"]
                reason = r["reason"]
                remark = r["remark"]
                picking_id = r["picking_id"]
                tb_weight = r["tb_weight"]
                tonbag = r["tonbag"]

                db.execute(
                    """
                    INSERT INTO return_history
                    (lot_no, sub_lt, return_date, original_customer, original_sale_ref, reason, remark, weight_kg)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (lot_no, sub_lt, today, tonbag.get("picked_to"), tonbag.get("sale_ref", ""), reason, remark, tb_weight),
                )
                db.execute(
                    """
                    INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, source_type, source_file, created_at)
                    VALUES (?, 'RETURN', ?, ?, ?, ?, ?)
                    """,
                    (lot_no, tb_weight, f"sub_lt={sub_lt}, reason={reason}", "RETURN_EXCEL", source_file or "", now),
                )
                db.execute(
                    """
                    UPDATE inventory_tonbag
                    SET status = 'AVAILABLE', outbound_date = NULL, picked_date = NULL,
                        picked_to = NULL, sale_ref = NULL, updated_at = ?
                    WHERE lot_no = ? AND sub_lt = ?
                    """,
                    (now, lot_no, sub_lt),
                )
                if tonbag["status"] == "RESERVED":
                    try:
                        db.execute(
                            "UPDATE allocation_plan SET status = 'CANCELLED', cancelled_at = ? WHERE lot_no = ? AND sub_lt = ? AND status = 'RESERVED'",
                            (now, lot_no, sub_lt),
                        )
                    except (sqlite3.OperationalError, ValueError, TypeError, KeyError, AttributeError) as _ae:
                        logger.debug(f"[v6.2.2] allocation_plan CANCELLED 스킵: {_ae}")
                else:
                    db.execute(
                        """
                        UPDATE inventory
                        SET current_weight = current_weight + ?, picked_weight = MAX(0, picked_weight - ?), updated_at = ?
                        WHERE lot_no = ?
                        """,
                        (tb_weight, tb_weight, now, lot_no),
                    )
                    # v8.0.4 [P2]: 반품 후 중앙 재계산
                    _eng = getattr(db, '_engine', None) or getattr(db, 'engine', None)
                    if _eng and hasattr(_eng, '_recalc_current_weight'):
                        _eng._recalc_current_weight(lot_no, reason='P2_RETURN_INBOUND_ENGINE')
                db.execute("UPDATE picking_table SET status = 'RETURNED' WHERE id = ?", (picking_id,))
                result["returned"] += 1
                result["details"].append({"lot_no": lot_no, "sub_lt": sub_lt, "weight": tb_weight})

            # sold_table RETURNED (lot_no + sub_lt 기반)
            for r in return_rows:
                try:
                    db.execute(
                        "UPDATE sold_table SET status = 'RETURNED' "
                        "WHERE lot_no = ? AND sub_lt = ? AND status IN ('SOLD','OUTBOUND')",
                        (r["lot_no"], r["sub_lt"]),
                    )
                except (sqlite3.OperationalError, ValueError, TypeError, KeyError, AttributeError) as _se:
                    logger.debug(f"[v6.2.2] sold_table RETURNED 스킵: {_se}")
                # 반품 후 문서 연계 점검용 감사 이력 (ReturnMixin 구현 재사용)
                if hasattr(engine, "_log_return_doc_review_audit"):
                    try:
                        engine._log_return_doc_review_audit(
                            lot_no=r["lot_no"],
                            sub_lt=r["sub_lt"],
                            reason=r.get("reason", ""),
                            source_type="RETURN_EXCEL",
                            source_file=source_file or "",
                        )
                    except (sqlite3.OperationalError, ValueError, TypeError, KeyError, AttributeError) as _ae:
                        logger.debug(f"[v6.2.2] return doc audit 스킵: {_ae}")

            returned_lots = set(r["lot_no"] for r in return_rows)
            for rlt in returned_lots:
                if hasattr(engine, "_recalc_lot_status"):
                    engine._recalc_lot_status(rlt)

            # return_mixin과 동일하게 트랜잭션 안에서 정합성 검증
            if hasattr(engine, "verify_lot_integrity") and returned_lots:
                for rlt in returned_lots:
                    integrity = engine.verify_lot_integrity(rlt)
                    if not integrity.get("valid", True):
                        raise ValueError(
                            f"반품 후 정합성 실패 ({rlt}): {integrity.get('errors', [])}"
                        )

        result["success"] = True
        logger.info(f"[ReturnInboundEngine] 반품 입고 완료: {result['returned']}건 (파일: {source_file})")
    except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        result["errors"].append(str(e))
        logger.exception("반품 입고 트랜잭션 실패")

    return result


def apply_return_inbound_to_db(engine: Any, parsed: dict, file_path: str = "") -> dict:
    """
    앱 엔진 + 파싱 결과 + 파일 경로로 반품 입고 처리.
    실패 시 RuntimeError.
    """
    import os
    source = os.path.basename(file_path) if file_path else ""
    r = process_return_inbound(engine, parsed, source_file=source)
    if not r["success"]:
        msg = "; ".join(r["errors"]) if r["errors"] else "반품 입고 처리 실패"
        raise RuntimeError(msg)
    return r
