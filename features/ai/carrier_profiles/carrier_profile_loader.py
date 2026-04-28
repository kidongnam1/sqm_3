# -*- coding: utf-8 -*-
"""
carrier_profile_loader.py — SQM v8.7.0 (Track B · Chunk B POC)
==============================================================
선사 프로파일 YAML 로더.

정책 (v8.7.0 Chunk A 반영):
  - 자동 선사 감지는 이미 제거되었음 (사용자 콤보박스 선택만 신뢰).
  - 따라서 이 YAML 플러그인은 "자동 매칭" 용도가 아니라,
    사용자가 선택한 선사의 파싱 힌트/정규식/컨테이너 prefix를
    외부 파일로 관리할 수 있게 해주는 **설정 저장소**이다.

설계 원칙:
  - pyyaml 옵셔널: import 실패 시 graceful no-op (빈 dict 반환).
  - 예외 raise 금지: 모든 오류는 logger.warning/debug 로 suppress.
  - 기존 CARRIER_TEMPLATES 내용은 건드리지 않는다 (YAML-only 키만 추가).
  - 병합 전략: "YAML이 지정한 키만 override, 나머지는 기존 유지" (dict.update).

공개 API:
    load_all_profiles() -> Dict[str, dict]
    get_profile(carrier_id: str) -> Optional[dict]
    merge_with_registry(registry_dict: dict) -> dict
"""
from __future__ import annotations

import glob
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

__version__ = "8.7.0"

_PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")

# 로드 1회 캐시
_CACHE: Optional[Dict[str, dict]] = None


# ─────────────────────────────────────────────────────────────────────
# 내부: YAML 로드 (pyyaml 옵셔널)
# ─────────────────────────────────────────────────────────────────────
def _import_yaml():
    """pyyaml 옵셔널 import. 실패 시 None 반환 (앱 중단 금지)."""
    try:
        import yaml  # type: ignore
        return yaml
    except ImportError:
        logger.debug(
            "[CarrierProfile] PyYAML 미설치 — YAML 프로파일 건너뜀 "
            "(pip install pyyaml 로 활성화 가능)"
        )
        return None


def _load_single_file(path: str, yaml_mod) -> Optional[dict]:
    """단일 YAML 파일 파싱. 실패 시 warning 후 None 반환."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml_mod.safe_load(f) or {}
        if not isinstance(data, dict):
            logger.warning(f"[CarrierProfile] 최상위가 dict가 아님 skip: {path}")
            return None
        cid = (data.get("id") or "").strip().upper()
        if not cid:
            logger.warning(f"[CarrierProfile] id 필드 없음 skip: {path}")
            return None
        data["id"] = cid  # 정규화
        return data
    except Exception as e:
        logger.warning(f"[CarrierProfile] 파싱 실패 {os.path.basename(path)}: {e}")
        return None


def _do_load(profile_dir: str = _PROFILE_DIR) -> Dict[str, dict]:
    """실제 디스크 스캔. 실패는 모두 suppress."""
    out: Dict[str, dict] = {}
    yaml_mod = _import_yaml()
    if yaml_mod is None:
        return out
    if not os.path.isdir(profile_dir):
        logger.debug(f"[CarrierProfile] 프로파일 디렉터리 없음: {profile_dir}")
        return out
    try:
        paths = sorted(glob.glob(os.path.join(profile_dir, "*.yml"))) + sorted(
            glob.glob(os.path.join(profile_dir, "*.yaml"))
        )
    except Exception as e:
        logger.warning(f"[CarrierProfile] 디렉터리 스캔 실패: {e}")
        return out

    for path in paths:
        prof = _load_single_file(path, yaml_mod)
        if not prof:
            continue
        cid = prof["id"]
        if cid in out:
            logger.warning(
                f"[CarrierProfile] 중복 id={cid} 발견 — 나중 파일이 우선: "
                f"{os.path.basename(path)}"
            )
        out[cid] = prof
        logger.info(
            f"[CarrierProfile] 로드: {cid} ({prof.get('name', cid)}) "
            f"← {os.path.basename(path)}"
        )
    return out


# ─────────────────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────────────────
def load_all_profiles(force_reload: bool = False) -> Dict[str, dict]:
    """
    모든 YAML 프로파일을 dict로 반환. 로드 실패 시 빈 dict.

    Returns:
        {carrier_id(대문자): profile_dict}
    """
    global _CACHE
    if _CACHE is not None and not force_reload:
        return dict(_CACHE)
    try:
        _CACHE = _do_load()
    except Exception as e:
        logger.warning(f"[CarrierProfile] load_all_profiles 실패(빈 dict 반환): {e}")
        _CACHE = {}
    return dict(_CACHE)


def get_profile(carrier_id: str) -> Optional[dict]:
    """단일 선사 프로파일 조회. 없으면 None."""
    if not carrier_id:
        return None
    profiles = load_all_profiles()
    return profiles.get(carrier_id.strip().upper())


def merge_with_registry(registry_dict: dict) -> dict:
    """
    기존 CARRIER_TEMPLATES 와 YAML 프로파일을 병합해 새 dict 반환.

    병합 규칙 (역호환 100%):
      1. 기존 registry의 모든 엔트리는 그대로 유지.
      2. YAML에만 있는 선사는 신규 CarrierTemplate 로 추가.
      3. 양쪽 모두에 있는 선사는 **기존 Python 엔트리 우선** —
         YAML이 지정한 필드 중 기존에 없던 필드만 보강 (object attr 방식).
         기존값을 덮어쓰지 않는다 (MSC/MAERSK 동작 100% 보존).

    Args:
        registry_dict: bl_carrier_registry.CARRIER_TEMPLATES

    Returns:
        병합된 dict (원본도 in-place 갱신되지만, 호출부에서 재대입 가능하도록 반환).
    """
    if not isinstance(registry_dict, dict):
        logger.warning("[CarrierProfile] registry_dict가 dict 아님 — 병합 skip")
        return registry_dict

    profiles = load_all_profiles()
    if not profiles:
        return registry_dict

    # CarrierTemplate dataclass lazy import (순환참조 회피)
    CarrierTemplate = None
    try:
        from features.ai.bl_carrier_registry import CarrierTemplate as _CT
        CarrierTemplate = _CT
    except Exception as e:
        logger.debug(f"[CarrierProfile] CarrierTemplate import 실패: {e}")

    added = 0
    enriched = 0
    for cid, prof in profiles.items():
        existing = registry_dict.get(cid)
        if existing is None:
            # 신규 선사 — CarrierTemplate 가 import 가능할 때만 추가
            if CarrierTemplate is None:
                logger.debug(
                    f"[CarrierProfile] CarrierTemplate 미가용 — {cid} 신규 추가 skip"
                )
                continue
            try:
                registry_dict[cid] = _build_template_from_profile(prof, CarrierTemplate)
                added += 1
                logger.info(f"[CarrierProfile] 신규 선사 추가: {cid}")
            except Exception as e:
                logger.warning(f"[CarrierProfile] {cid} 템플릿 생성 실패: {e}")
        else:
            # 기존 선사 — 기존값 우선, 빈 필드만 YAML로 보강
            try:
                if _enrich_existing_template(existing, prof):
                    enriched += 1
            except Exception as e:
                logger.debug(f"[CarrierProfile] {cid} 보강 skip: {e}")

    if added or enriched:
        logger.info(
            f"[CarrierProfile] 병합 완료: 신규 {added}개 / 보강 {enriched}개 "
            f"(registry 총 {len(registry_dict)}개)"
        )
    return registry_dict


# ─────────────────────────────────────────────────────────────────────
# 내부: 프로파일 dict → CarrierTemplate 변환
# ─────────────────────────────────────────────────────────────────────
def _build_template_from_profile(prof: dict, CarrierTemplate) -> Any:
    """YAML dict → CarrierTemplate. 누락 필드는 안전 기본값."""
    cid = prof["id"]
    detect = prof.get("detect") or {}
    bl = prof.get("bl") or {}
    hints = prof.get("hints") or {}

    keywords = detect.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = [str(keywords)]
    keywords = [str(k) for k in keywords if k]

    # detect_pattern 자동 생성: keywords 중 하나라도 매칭되는 정규식
    pattern = detect.get("pattern") or ""
    if not pattern and keywords:
        # 공백/특수문자 escape 후 OR
        import re as _re
        pattern = "|".join(_re.escape(k) for k in keywords[:5])

    return CarrierTemplate(
        carrier_id=cid,
        carrier_name=prof.get("name") or cid,
        detect_keywords=keywords,
        detect_pattern=pattern,
        bl_extract_pattern=bl.get("number_regex") or "",
        bl_page_scope=bl.get("page_scope") or "page0",
        bl_format_hint=bl.get("format_hint") or "",
        sap_page_hint=bl.get("sap_page_hint") or "all",
        bl_no_prompt_hint=hints.get("bl") or bl.get("gemini_hint") or "",
        bl_equals_booking_no=bool(bl.get("bl_equals_booking_no", False)),
    )


def _enrich_existing_template(existing, prof: dict) -> bool:
    """
    기존 CarrierTemplate에 YAML 값 "보강만" (override 금지).
    기존 필드가 빈 값(빈 문자열/빈 리스트)일 때만 YAML 값 주입.

    Returns:
        True if any field was enriched.
    """
    touched = False

    def _is_empty(v) -> bool:
        return v is None or v == "" or v == [] or v == {}

    bl = prof.get("bl") or {}
    hints = prof.get("hints") or {}
    detect = prof.get("detect") or {}

    pairs = [
        ("bl_extract_pattern", bl.get("number_regex")),
        ("bl_format_hint", bl.get("format_hint")),
        ("bl_no_prompt_hint", hints.get("bl") or bl.get("gemini_hint")),
    ]
    for attr, new_val in pairs:
        if not new_val:
            continue
        try:
            cur = getattr(existing, attr, None)
        except Exception:
            continue
        if _is_empty(cur):
            try:
                setattr(existing, attr, new_val)
                touched = True
            except Exception as _e:
                logger.debug("[carrier] setattr(%s) 실패: %s", attr, _e)

    # detect_keywords 는 append (기존 유지 + YAML 보강)
    try:
        cur_kw = list(getattr(existing, "detect_keywords", []) or [])
        new_kw = [k for k in (detect.get("keywords") or []) if k and k not in cur_kw]
        if new_kw:
            setattr(existing, "detect_keywords", cur_kw + new_kw)
            touched = True
    except Exception as _e:
        logger.debug("[carrier] profile merge 실패: %s", _e)

    return touched
