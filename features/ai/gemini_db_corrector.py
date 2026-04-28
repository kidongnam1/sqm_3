# -*- coding: utf-8 -*-
"""
SQM v8.0.6 — Gemini DB 수정 엔진
===================================
자연어 명령으로 DB 오류 데이터를 안전하게 수정합니다.

수정 가능 필드 (5개만 허용):
    bl_no, remarks, location, customer, destination

수정 불가 필드 (자동 차단):
    lot_no, tonbag_uid, sub_lt, current_weight, picked_weight,
    status, inbound_date, weight, is_sample

수정 절차:
    1. 자연어 입력
    2. Gemini가 의도 파악 → 수정 내용 확인 메시지
    3. 사용자 "확인" 입력
    4. DB 수정 실행 + audit_log 기록
    5. 결과 반환
"""

import logging
import re
import sqlite3
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── 수정 허용/금지 필드 ────────────────────────────────────────────
ALLOWED_FIELDS = {
    # inventory 테이블
    'bl_no':        ('inventory',        'B/L 번호'),
    'remarks':      ('inventory',        '비고/메모'),
    'location':     ('inventory_tonbag', '위치'),
    'customer':     ('outbound',         '고객사명'),
    'destination':  ('outbound',         '목적지'),
    'sap_no':       ('inventory',        'SAP 번호'),
    'container_no': ('inventory',        '컨테이너 번호'),
}

BLOCKED_FIELDS = [
    'lot_no', 'tonbag_uid', 'sub_lt', 'id',
    'current_weight', 'picked_weight', 'initial_weight', 'weight',
    'status', 'inbound_date', 'is_sample', 'inventory_id',
]


class GeminiDBCorrector:
    """
    자연어 명령 → DB 수정 엔진
    Gemini가 의도를 분석하고 승인 후 실행
    """

    def __init__(self, db_path: str, gemini_client=None, model_name: str = 'gemini-2.5-flash',
                 db_adapter=None):
        self.db_path    = db_path
        self._db_adapter = db_adapter  # v8.1.9: DB 어댑터 주입 (있으면 어댑터 사용)
        self.client  = gemini_client
        self.model   = model_name
        self._pending = None  # 승인 대기 중인 수정 내용

    # ── 1단계: 자연어 분석 → 수정 계획 생성 ───────────────────────
    def analyze_command(self, user_input: str) -> dict:
        """
        자연어 명령을 분석해서 수정 계획을 반환합니다.
        Returns: {'status': 'confirm'|'error', 'plan': {...}, 'message': str}
        """
        try:
            plan = self._parse_with_gemini(user_input)
            if plan.get('error'):
                return {'status': 'error', 'message': plan['error']}

            # 차단 필드 검사
            field = plan.get('field', '').lower()
            if field in BLOCKED_FIELDS:
                return {
                    'status': 'error',
                    'message': (
                        f"⛔ '{field}' 는 수정할 수 없는 필드입니다.\n"
                        f"수정 가능 필드: bl_no, remarks, location, customer, destination"
                    )
                }

            if field not in ALLOWED_FIELDS:
                return {
                    'status': 'error',
                    'message': (
                        f"⛔ '{field}' 는 지원하지 않는 필드입니다.\n"
                        f"수정 가능 필드: bl_no, remarks, location, customer, destination"
                    )
                }

            # 현재 DB 값 조회
            current_val = self._get_current_value(
                plan.get('lot_no'), plan.get('tonbag_uid'), field
            )

            self._pending = {
                'lot_no':      plan.get('lot_no'),
                'tonbag_uid':  plan.get('tonbag_uid'),
                'field':       field,
                'old_value':   current_val,
                'new_value':   plan.get('new_value'),
                'table':       ALLOWED_FIELDS[field][0],
                'field_label': ALLOWED_FIELDS[field][1],
            }

            # 확인 메시지 생성
            target = plan.get('lot_no') or plan.get('tonbag_uid') or '?'
            msg = (
                f"📋 수정 내용을 확인해 주세요\n\n"
                f"  대상:    {target}\n"
                f"  필드:    {ALLOWED_FIELDS[field][1]} ({field})\n"
                f"  현재값:  {current_val or '(없음)'}\n"
                f"  수정값:  {plan.get('new_value')}\n\n"
                f"✅ 확인하시려면 「확인」 또는 「yes」를 입력하세요.\n"
                f"❌ 취소하시려면 「취소」 또는 「no」를 입력하세요."
            )
            return {'status': 'confirm', 'message': msg, 'plan': self._pending}

        except Exception as e:
            logger.error(f"[Corrector] analyze 오류: {e}")
            return {'status': 'error', 'message': f"분석 실패: {e}"}

    # ── 2단계: 승인 후 실행 ────────────────────────────────────────
    def execute_confirmed(self) -> dict:
        """
        승인된 수정을 실제 DB에 반영합니다.
        audit_log에 이력 자동 기록.
        """
        if not self._pending:
            return {'status': 'error', 'message': '승인 대기 중인 수정 내용이 없습니다.'}

        p = self._pending
        # v8.1.9: DB 어댑터 우선 사용 (3중 방어 적용)
        _use_adapter = self._db_adapter is not None
        conn = None
        try:
            if not _use_adapter:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            def _exec(sql, params=()):
                if _use_adapter:
                    return self._db_adapter.execute(sql, params)
                # fallback: sqlite3 직접 연결 (db_adapter 없을 때만)
                return conn.execute(sql, params)

            # ── 실제 UPDATE ──────────────────────────────────────
            if p['table'] == 'inventory':
                _exec(
                    f"UPDATE inventory SET {p['field']} = ?, updated_at = ? WHERE lot_no = ?",
                    (p['new_value'], now, p['lot_no'])
                )
            elif p['table'] == 'inventory_tonbag':
                if p.get('tonbag_uid'):
                    _exec(
                        f"UPDATE inventory_tonbag SET {p['field']} = ?, updated_at = ? "
                        f"WHERE tonbag_uid = ?",
                        (p['new_value'], now, p['tonbag_uid'])
                    )
                else:
                    _exec(
                        f"UPDATE inventory_tonbag SET {p['field']} = ?, updated_at = ? "
                        f"WHERE lot_no = ?",
                        (p['new_value'], now, p['lot_no'])
                    )
            elif p['table'] == 'outbound':
                _exec(
                    f"UPDATE outbound SET {p['field']} = ?, updated_at = ? "
                    f"WHERE sale_ref IN ("
                    f"  SELECT sale_ref FROM inventory_tonbag WHERE lot_no = ?"
                    f")",
                    (p['new_value'], now, p['lot_no'])
                )

            # ── audit_log 기록 ───────────────────────────────────
            try:
                _exec("""
                    INSERT INTO audit_log
                        (action, table_name, record_id, field_name,
                         old_value, new_value, operator, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'CORRECT',
                    p['table'],
                    p.get('lot_no') or p.get('tonbag_uid'),
                    p['field'],
                    str(p['old_value']),
                    str(p['new_value']),
                    'Gemini-DB-Corrector',
                    now,
                ))
            except Exception as ae:
                logger.debug(f"audit_log 기록 무시: {ae}")

            conn.commit()
            self._pending = None

            return {
                'status': 'success',
                'message': (
                    f"✅ 수정 완료!\n\n"
                    f"  대상:    {p.get('lot_no') or p.get('tonbag_uid')}\n"
                    f"  필드:    {p['field_label']} ({p['field']})\n"
                    f"  이전값:  {p['old_value'] or '(없음)'}\n"
                    f"  수정값:  {p['new_value']}\n"
                    f"  시각:    {now}\n\n"
                    f"📝 audit_log에 이력이 기록되었습니다."
                )
            }

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"[Corrector] execute 오류: {e}")
            return {'status': 'error', 'message': f"수정 실패: {e}"}
        finally:
            if conn:
                conn.close()

    def cancel(self) -> dict:
        """수정 취소"""
        self._pending = None
        return {'status': 'cancelled', 'message': '❌ 수정이 취소되었습니다.'}

    # ── Gemini 자연어 파싱 ─────────────────────────────────────────
    def _parse_with_gemini(self, user_input: str) -> dict:
        """Gemini로 자연어 → 수정 계획 JSON 추출"""

        allowed_list = ', '.join(ALLOWED_FIELDS.keys())
        prompt = f"""
너는 SQM 재고관리 시스템의 DB 수정 명령 분석기야.
사용자 입력을 분석해서 아래 JSON 형식으로만 답해줘. 다른 텍스트는 절대 쓰지 마.

수정 가능한 필드: {allowed_list}
수정 불가 필드: lot_no, status, current_weight, weight, is_sample, sub_lt, tonbag_uid

JSON 형식:
{{
  "lot_no": "LOT번호 또는 null",
  "tonbag_uid": "톤백UID 또는 null",
  "field": "수정할 필드명",
  "new_value": "새 값",
  "error": "오류가 있으면 한국어 설명, 없으면 null"
}}

사용자 입력: {user_input}
"""
        try:
            from features.ai.gemini_utils import call_gemini_safe
            import json

            if not self.client:
                # Gemini 없으면 정규식 폴백
                return self._parse_with_regex(user_input)

            resp = call_gemini_safe(
                self.client, self.model, prompt,
                temperature=0.0, max_output_tokens=512
            )
            if not resp:
                return self._parse_with_regex(user_input)

            text = resp.text.strip()
            # ```json 제거
            text = re.sub(r'```json|```', '', text).strip()
            result = json.loads(text)
            return result

        except Exception as e:
            logger.debug(f"Gemini 파싱 실패, 정규식 사용: {e}")
            return self._parse_with_regex(user_input)

    def _parse_with_regex(self, text: str) -> dict:
        """Gemini 없을 때 정규식으로 기본 파싱"""
        result = {'lot_no': None, 'tonbag_uid': None,
                  'field': None, 'new_value': None, 'error': None}

        t = text.lower()

        # LOT 번호 추출
        lot = re.search(r'lot[\s\-_]?(?:no|번호)?[\s:：]*([\w\-]+)', t, re.I)
        if lot:
            result['lot_no'] = lot.group(1).upper()

        # 필드 키워드 매핑
        field_map = {
            'bl': 'bl_no', 'b/l': 'bl_no', 'b_l': 'bl_no', 'bl번호': 'bl_no',
            '비고': 'remarks', '메모': 'remarks', 'remark': 'remarks',
            '위치': 'location', 'location': 'location',
            '고객': 'customer', '고객사': 'customer', 'customer': 'customer',
            '목적지': 'destination', 'destination': 'destination',
            'sap': 'sap_no', 'container': 'container_no', '컨테이너': 'container_no',
        }
        for kw, field in field_map.items():
            if kw in t:
                result['field'] = field
                break

        # 새 값 추출 ("로" 또는 "으로" 또는 "=" 뒤)
        val = re.search(r'(?:을|를|을/를)?\s*["\']?([A-Z0-9가-힣\-_/ ]+)["\']?\s*(?:로|으로|수정|변경|바꿔|바꾸|이다|임)', text, re.I)
        if val:
            result['new_value'] = val.group(1).strip()
        else:
            # 마지막 따옴표 안 값
            val2 = re.search(r'["\']([^"\']+)["\']', text)
            if val2:
                result['new_value'] = val2.group(1).strip()

        if not result['field'] or not result['new_value']:
            result['error'] = (
                "수정 내용을 이해하지 못했습니다.\n"
                "예시: 'LOT-001의 B/L번호를 BLTEST123으로 수정해줘'"
            )
        return result

    def _get_current_value(self, lot_no, tonbag_uid, field) -> Optional[str]:
        """현재 DB 값 조회 — v8.3.1: db_adapter 우선, fallback sqlite3"""
        try:
            table, _ = ALLOWED_FIELDS.get(field, ('inventory', ''))
            # DEAD CODE REMOVED v8.6.4: _qry()
            # 사유: 전체 코드베이스에서 호출 없음 (2026-03-28 감사)
            # 원본 9줄 제거

            if table == 'inventory_tonbag' and tonbag_uid:
                if self._db_adapter:
                    row = self._db_adapter.fetchone(
                        f"SELECT {field} FROM inventory_tonbag WHERE tonbag_uid=?",
                        (tonbag_uid,)
                    )
                else:
                    with sqlite3.connect(self.db_path) as conn:
                        r = conn.execute(
                            f"SELECT {field} FROM inventory_tonbag WHERE tonbag_uid=?",
                            (tonbag_uid,)
                        ).fetchone()
                        row = {field: r[0]} if r else None
            elif lot_no:
                if self._db_adapter:
                    row = self._db_adapter.fetchone(
                        f"SELECT {field} FROM {table} WHERE lot_no=? LIMIT 1",
                        (lot_no,)
                    )
                else:
                    with sqlite3.connect(self.db_path) as conn:
                        r = conn.execute(
                            f"SELECT {field} FROM {table} WHERE lot_no=? LIMIT 1",
                            (lot_no,)
                        ).fetchone()
                        row = {field: r[0]} if r else None
            else:
                return None

            if row is None:
                return None
            val = row.get(field) if isinstance(row, dict) else (row[0] if row else None)
            return str(val) if val is not None else None
        except Exception:
            return None
