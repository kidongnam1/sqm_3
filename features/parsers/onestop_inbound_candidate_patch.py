# -*- coding: utf-8 -*-
"""
onestop_inbound_candidate_patch.py — SQM v8.0.6 PATCH
======================================================
onestop_inbound.py 의 BL / DO 파싱 진입부에
candidate_engine(다중 템플릿 후보 엔진)을 연결하는 패치 모듈.

★ 이 파일은 onestop_inbound.py 를 직접 수정하지 않습니다.
  onestop_inbound.py 의 해당 elif 블록 안에서
  아래 함수 2개를 호출하는 방식으로 연결합니다.

연결 위치 (onestop_inbound.py):
  elif doc_type == 'BL':
      bl_result = _parse_bl_with_candidate(parser, file_path, _hint_bl, _bl_format, self._log_safe)
      ...
  elif doc_type == 'DO':
      do_result = _parse_do_with_candidate(parser, file_path, self._log_safe)
      ...

[수정이력]
  2026-03-17  Ruby  SQM v8.0.6 신규 생성
"""
from __future__ import annotations

import logging
import os
import json
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _dbg_log(tag: str = "", location: str = "", message: str = "", data=None) -> None:
    # v8.6.4: 프로덕션 debug 파일 쓰기 제거 → logger.debug
    # v8.7.0 [FIX]: 호출부가 (tag, location, message, data) 4-arg을 쓰고 있어 시그니처 정합
    logger.debug(f'[DBG:{tag}] {location} — {message} | {data}')


def _extract_first_page_text(pdf_path: str) -> str:
    """pdfplumber로 1페이지 텍스트 안전 추출"""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as p:
            if p.pages:
                return p.pages[0].extract_text() or ""
    except Exception as e:
        logger.debug("[CandidatePatch] 1페이지 텍스트 추출 실패(무시): %s", e)
    return ""


def parse_bl_with_candidate(
    parser: Any,
    file_path: str,
    hint_bl: str = "",
    bl_format: str = "",
    log_fn: Optional[Any] = None,
    use_multi: bool = True,
    db_carrier_id: str = "",   # v8.4.5: DB 템플릿 선사 ID (hint_bl 있을 때 우선 사용)
) -> Any:
    """
    BL 파싱 — 다중 템플릿 후보 엔진 적용 버전.

    1. pdfplumber로 1페이지 텍스트 추출
    2. multi_template_registry로 최적 gemini_hint 선택
    3. 기존 parser.parse_bl() 호출 (gemini_hint + bl_format 전달)
    4. 실패 시 기존 hint_bl 기반 fallback

    Parameters
    ----------
    parser       : GeminiDocumentParser 인스턴스
    file_path    : BL PDF 경로
    hint_bl      : 기존 템플릿 테이블 gemini_hint_bl (있으면 우선 사용)
    bl_format    : 기존 bl_format (그대로 전달)
    log_fn       : self._log_safe (onestop_inbound UI 로그 함수)
    use_multi    : True 이면 다중 템플릿 후보 엔진 사용 (PreParseSelectDialog 연동)
    db_carrier_id: DB 템플릿에 저장된 선사 ID — hint_bl 있을 때 multi_template 후보가
                   엉뚱한 선사를 carrier_id로 덮어쓰는 버그 방지 (v8.4.5)
    """
    def _log(msg: str) -> None:
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                logger.debug("[SUPPRESSED] exception in onestop_inbound_candidate_patch.py")  # noqa
        logger.info(msg)

    filename = os.path.basename(file_path)

    # ── Step 1. 1페이지 텍스트 추출 ──────────────────────────────
    first_page_text = _extract_first_page_text(file_path)

    # ── Step 2. 다중 템플릿 후보 gemini_hint 선택 ────────────────
    # use_multi=False 이면 후보 엔진 건너뜀 (단일 모드)
    if not use_multi:
        _log("  📌 [MultiTemplate] 단일 모드 — 기존 템플릿 힌트만 사용")
        try:
            # v8.4.5: 단일 모드에서도 db_carrier_id 전달 (carrier_id 미전달 버그 수정)
            return parser.parse_bl(file_path, gemini_hint=hint_bl,
                                   bl_format=bl_format, carrier_id=db_carrier_id)
        except TypeError:
            return parser.parse_bl(file_path, gemini_hint=hint_bl,
                                   carrier_id=db_carrier_id)

    candidate_hint = ""
    selected_template_id = ""
    selected_carrier_id = ""
    try:
        from features.ai.multi_template_registry import get_candidate_templates
        candidates = get_candidate_templates(
            first_page_text=first_page_text,
            filename=filename,
            doc_type="BL",
            max_candidates=3,
        )
        if candidates:
            best = candidates[0]
            candidate_hint = best["template_hint"].get("gemini_hint", "")
            selected_template_id = best["template_id"]
            carrier = best["carrier"]
            selected_carrier_id = str(carrier or "").upper()
            score = best["match_score"]
            _log(
                f"  🔍 [MultiTemplate] BL 후보: {selected_template_id} "
                f"(선사={carrier}, score={score})"
            )
            # 2위/3위 후보도 로그
            for rank, c in enumerate(candidates[1:], start=2):
                logger.info(
                    "[CandidatePatch] BL 후보%d: %s score=%s",
                    rank, c["template_id"], c["match_score"],
                )
    except Exception as e:
        logger.debug("[CandidatePatch] 후보 템플릿 선택 실패(무시): %s", e)

    # ── Step 3. 최종 gemini_hint 및 carrier_id 결정 ──────────────
    # 우선순위: ① 기존 템플릿 테이블 hint_bl (수동 지정 우선)
    #           ② 후보 엔진 선택 candidate_hint
    #           ③ 없으면 빈 문자열 (기존 동작 유지)
    final_hint = hint_bl or candidate_hint
    if selected_template_id and not hint_bl:
        _log(f"  📌 [MultiTemplate] 적용 템플릿: {selected_template_id}")
    elif hint_bl:
        _log("  📌 [MultiTemplate] 기존 템플릿 힌트 우선 적용")

    # v8.4.5: carrier_id 우선순위 결정
    # hint_bl(DB 템플릿) 있을 때 → db_carrier_id 우선 (MSC 선택 시 MAERSK로 오파싱 방지)
    # hint_bl 없을 때 → multi_template 후보 carrier_id 사용
    if db_carrier_id:
        final_carrier_id = db_carrier_id
        if hint_bl:
            _log(f"  📌 [CarrierID] DB 템플릿 선사 우선 적용: {final_carrier_id}")
    else:
        final_carrier_id = selected_carrier_id

    # ── Step 4. 기존 parse_bl 호출 ───────────────────────────────
    try:
        # region agent log
        _dbg_log(
            "H6",
            "onestop_inbound_candidate_patch.py:parse_bl_with_candidate:before_parse_bl",
            "calling parser.parse_bl from candidate patch",
            {
                "selected_template_id": selected_template_id,
                "selected_carrier_id": selected_carrier_id,
                "has_hint_bl": bool(hint_bl),
                "has_candidate_hint": bool(candidate_hint),
                "bl_format": bl_format,
            },
        )
        # endregion
        bl_result = parser.parse_bl(
            file_path,
            gemini_hint=final_hint,
            bl_format=bl_format,
            carrier_id=final_carrier_id,
        )
        return bl_result
    except TypeError:
        # region agent log
        _dbg_log(
            "H7",
            "onestop_inbound_candidate_patch.py:parse_bl_with_candidate:type_error_fallback",
            "parse_bl signature fallback without bl_format",
            {"final_carrier_id": final_carrier_id},
        )
        # endregion
        # bl_format 인자가 없는 구버전 호환
        try:
            bl_result = parser.parse_bl(file_path, gemini_hint=final_hint, carrier_id=final_carrier_id)
            return bl_result
        except Exception as e2:
            logger.error("[CandidatePatch] parse_bl 오류: %s", e2)
            raise
    except Exception as e:
        logger.error("[CandidatePatch] parse_bl 오류: %s", e)
        raise


def parse_do_with_candidate(
    parser: Any,
    file_path: str,
    log_fn: Optional[Any] = None,
) -> Any:
    """
    DO 파싱 — 다중 템플릿 후보 엔진 적용 버전.

    1. pdfplumber로 1페이지 텍스트 추출
    2. multi_template_registry로 최적 선사 감지 + 로그
    3. 기존 parser.parse_do() 호출 (DO는 gemini_hint 인자 없음 → 그대로)
    4. 실패 시 기존 fallback

    Parameters
    ----------
    parser    : GeminiDocumentParser 인스턴스
    file_path : DO PDF 경로
    log_fn    : self._log_safe (onestop_inbound UI 로그 함수)
    """
    # REMOVED: duplicate _log() definition (v8.6.4)

    filename = os.path.basename(file_path)

    # ── Step 1. 1페이지 텍스트 추출 ──────────────────────────────
    first_page_text = _extract_first_page_text(file_path)

    # ── Step 2. 후보 템플릿 감지 (로그/뱃지용) ───────────────────
    try:
        from features.ai.multi_template_registry import get_candidate_templates
        candidates = get_candidate_templates(
            first_page_text=first_page_text,
            filename=filename,
            doc_type="DO",
            max_candidates=3,
        )
        if candidates:
            best = candidates[0]
            selected_template_id = best["template_id"]
            carrier = best["carrier"]
            score = best["match_score"]
            _log(
                f"  🔍 [MultiTemplate] DO 후보: {selected_template_id} "
                f"(선사={carrier}, score={score})"
            )
            # MSC DO는 샘플 미확보 → 검수 권고
            if "MSC" in carrier and "DO" in selected_template_id:
                _log("  ⚠️ [MultiTemplate] MSC DO — 파싱 후 수동 검수를 권장합니다")
    except Exception as e:
        logger.debug("[CandidatePatch] DO 후보 감지 실패(무시): %s", e)

    # ── Step 3. 기존 parse_do 호출 (기존 시그니처 유지) ──────────
    try:
        do_result = parser.parse_do(file_path)
        return do_result
    except Exception as e:
        logger.error("[CandidatePatch] parse_do 오류: %s", e)
        raise
