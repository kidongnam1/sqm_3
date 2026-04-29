# -*- coding: utf-8 -*-
"""
engine_modules/audit_helper.py — SQM v8.3.0
=============================================
LOT 처리 이력 감사 로그 중앙 헬퍼

CATL·BYD·LG 고객사 감사 대응용.
모든 입고·출고·배정·반품을 audit_log에 단일 인터페이스로 기록.

이벤트 타입 상수:
  EVT_INBOUND            = 'INBOUND'
  EVT_LOT_UPDATE         = 'LOT_UPDATE'
  EVT_LOT_DELETE         = 'LOT_DELETE'
  EVT_RESERVED           = 'RESERVED'
  EVT_CANCEL_RESERVATION = 'CANCEL_RESERVATION'
  EVT_PICKED             = 'PICKED'
  EVT_OUTBOUND           = 'OUTBOUND'
  EVT_RETURN             = 'RETURN'
  EVT_INTEGRITY_FAIL     = 'INTEGRITY_FAIL'
  EVT_PARSING_RESULT     = 'PARSING_RESULT'
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# ── 이벤트 타입 상수 ──────────────────────────────────────────────
EVT_INBOUND            = 'INBOUND'
EVT_LOT_UPDATE         = 'LOT_UPDATE'
EVT_LOT_DELETE         = 'LOT_DELETE'
EVT_RESERVED           = 'RESERVED'
EVT_CANCEL_RESERVATION = 'CANCEL_RESERVATION'
EVT_PICKED             = 'PICKED'
EVT_OUTBOUND           = 'OUTBOUND'
EVT_RETURN             = 'RETURN'
EVT_INTEGRITY_FAIL     = 'INTEGRITY_FAIL'
EVT_PARSING_RESULT     = 'PARSING_RESULT'


def write_audit(
    db,
    event_type: str,
    lot_no: str = '',
    detail: Optional[Dict[str, Any]] = None,
    batch_id: str = '',
    tonbag_id: str = '',
    user_note: str = '',
    created_by: str = 'system',
) -> bool:
    """
    audit_log에 단건 기록.

    Args:
        db         : SQMDatabase 인스턴스
        event_type : EVT_* 상수
        lot_no     : 대상 LOT 번호
        detail     : 추가 정보 dict (JSON 직렬화)
        batch_id   : 배치 작업 ID
        tonbag_id  : 톤백 UID
        user_note  : 사용자 메모
        created_by : 작업자

    Returns:
        True  — 성공
        False — 실패 (예외 삼킴, 업무 흐름 차단 안 함)
    """
    try:
        data = {'lot_no': lot_no}
        if detail:
            data.update(detail)
        event_json = json.dumps(data, ensure_ascii=False, default=str)

        db.execute(
            """INSERT INTO audit_log
               (event_type, event_data, batch_id, tonbag_id,
                user_note, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event_type,
                event_json,
                batch_id or '',
                tonbag_id or '',
                user_note or '',
                created_by or 'system',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            )
        )
        logger.debug(f"[Audit] {event_type} | {lot_no}")
        return True
    except Exception as e:
        # audit 실패는 업무 흐름을 절대 차단하지 않음
        logger.debug(f"[Audit] 기록 스킵 ({event_type}): {e}")
        return False


def write_audit_bulk(db, events: List[dict]) -> int:
    """
    audit_log 다건 일괄 기록.

    Args:
        events : [{'event_type':..., 'lot_no':..., 'detail':...}, ...]

    Returns:
        기록 성공 건수
    """
    success = 0
    for ev in events:
        ok = write_audit(
            db,
            event_type = ev.get('event_type', 'UNKNOWN'),
            lot_no     = ev.get('lot_no', ''),
            detail     = ev.get('detail'),
            batch_id   = ev.get('batch_id', ''),
            tonbag_id  = ev.get('tonbag_id', ''),
            user_note  = ev.get('user_note', ''),
            created_by = ev.get('created_by', 'system'),
        )
        if ok:
            success += 1
    return success


def query_lot_history(db, lot_no: str) -> List[dict]:
    """
    특정 LOT의 전체 감사 이력 조회.

    Returns:
        [{'event_type', 'detail', 'created_at', ...}, ...]
    """
    try:
        rows = db.fetchall(
            """SELECT id, event_type, event_data, batch_id,
                      tonbag_id, user_note, created_by, created_at
               FROM audit_log
               WHERE event_data LIKE ?
               ORDER BY created_at ASC""",
            (f'%"lot_no": "{lot_no}"%',)
        )
        result = []
        for r in rows:
            row = dict(r) if isinstance(r, dict) else {
                'id': r[0], 'event_type': r[1], 'event_data': r[2],
                'batch_id': r[3], 'tonbag_id': r[4],
                'user_note': r[5], 'created_by': r[6], 'created_at': r[7],
            }
            try:
                row['detail'] = json.loads(row.get('event_data') or '{}')
            except (json.JSONDecodeError, TypeError):
                row['detail'] = {}
            result.append(row)
        return result
    except Exception as e:
        logger.warning(f"[Audit] LOT 이력 조회 실패: {e}")
        return []


def query_audit_summary(db, date_from: str = '', date_to: str = '') -> dict:
    """
    기간별 이벤트 요약 통계.

    Returns:
        {'INBOUND': 5, 'OUTBOUND': 12, ...}
    """
    try:
        where = ''
        params: list = []
        if date_from:
            where += ' AND created_at >= ?'
            params.append(date_from + ' 00:00:00')
        if date_to:
            where += ' AND created_at <= ?'
            params.append(date_to + ' 23:59:59')

        rows = db.fetchall(
            f"""SELECT event_type, COUNT(*) AS cnt
                FROM audit_log
                WHERE 1=1 {where}
                GROUP BY event_type
                ORDER BY cnt DESC""",
            tuple(params)
        )
        return {
            (r['event_type'] if isinstance(r, dict) else r[0]):
            (r['cnt']        if isinstance(r, dict) else r[1])
            for r in rows
        }
    except Exception as e:
        logger.warning(f"[Audit] 요약 통계 조회 실패: {e}")
        return {}
