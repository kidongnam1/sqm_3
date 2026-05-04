# -*- coding: utf-8 -*-
"""
재고조정 자연어 입력 파서 (adjust_parser.py)

사용자가 한국어 혼합 자연어로 입력한 재고조정 요청을 파싱하여
AdjustParseResult 구조체로 반환합니다.

파싱 흐름:
  1. _reason_classify(): 사유 코드 자동 분류
  2. DB에서 컨테이너/BL 번호 → LOT 목록 조회 (필요 시)
  3. _build_gemini_prompt(): Gemini 프롬프트 생성
  4. Gemini API 호출 → JSON 파싱
  5. Gemini 실패 시 _regex_fallback_parse() 로 대체
  6. _validate_lots(): LOT 번호 DB 검증 + delta 계산

Author: Ruby (Senior Software Architect)
Version: 1.0.0
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Gemini 라이브러리 (선택적 임포트) ─────────────────────────────────────────
try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    logger.warning("[AdjustParser] google-genai 미설치 — Gemini 비활성화. pip install google-genai")

# ── 기본 Gemini 모델명 ────────────────────────────────────────────────────────
_DEFAULT_MODEL = "gemini-2.5-flash"

# ── 사유 코드 매핑 ────────────────────────────────────────────────────────────
REASON_CODES = ("DAMAGE", "LOSS", "RECOUNT", "TRANSFER", "OTHER")

# ── 사유 코드 키워드 매핑 (한/영 혼합) ────────────────────────────────────────
_REASON_KEYWORDS: Dict[str, List[str]] = {
    "DAMAGE":   ["파손", "손상", "찢", "터짐", "훼손", "damage", "torn", "broken"],
    "LOSS":     ["분실", "도난", "없어", "실종", "missing", "lost", "theft"],
    "RECOUNT":  ["실사", "재고조사", "재실사", "실물", "재확인", "count", "recount", "실물확인"],
    "TRANSFER": ["이동", "이송", "입고", "출고", "transfer", "move"],
}


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class AdjustItem:
    """재고조정 단일 항목."""
    lot_no: str = ""            # LOT 번호 (DB 확인 후 채움)
    new_count: int = 0          # 새 포대 수 (실물 기준, -1=미확정)
    delta: int = 0              # 변화량 (+/-). DB 조회 후 계산
    reason_code: str = "OTHER"  # DAMAGE / LOSS / RECOUNT / TRANSFER / OTHER
    reason_text: str = ""       # 자유 입력 사유
    confidence: float = 1.0     # AI 확신도 0.0~1.0
    raw_input: str = ""         # 원본 입력 텍스트


@dataclass
class AdjustParseResult:
    """재고조정 파싱 전체 결과."""
    items: List[AdjustItem] = field(default_factory=list)
    ambiguous: List[str] = field(default_factory=list)  # 확신도 0.7 미만 항목
    error: Optional[str] = None                         # 전체 파싱 실패 시


# =============================================================================
# 공개 API
# =============================================================================

def parse_adjust_request(text: str, db) -> AdjustParseResult:
    """
    자연어 재고조정 요청 → AdjustParseResult 변환.

    Args:
        text: 사용자 입력 (한국어 혼합 자연어)
        db:   SQMDatabase 인스턴스 (LOT 조회용)

    Returns:
        AdjustParseResult
    """
    if not text or not text.strip():
        return AdjustParseResult(error="입력값이 비어 있습니다.")

    raw = text.strip()

    # 1. DB context 수집 (컨테이너/BL 번호 → LOT 목록)
    db_context = _collect_db_context(raw, db)

    # 2. Gemini 시도
    result = _try_gemini_parse(raw, db_context)
    if result is not None:
        result = _validate_lots(result.items, db, raw)
        return result

    # 3. Gemini 실패 → regex fallback
    logger.info("[AdjustParser] Gemini 실패 → regex fallback 사용")
    result = _regex_fallback_parse(raw, db_context, db)
    return result


# =============================================================================
# Gemini 호출
# =============================================================================

def _try_gemini_parse(text: str, db_context: dict) -> Optional[AdjustParseResult]:
    """Gemini API로 파싱 시도. 실패 시 None 반환."""
    if not HAS_GEMINI:
        return None

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning("[AdjustParser] GEMINI_API_KEY 미설정 — regex fallback 사용")
        return None

    try:
        client = genai.Client(api_key=api_key)
        model = os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL)
        prompt = _build_gemini_prompt(text, db_context)

        config_kw: Dict[str, Any] = {
            "temperature": 0.1,
            "max_output_tokens": 8192,
        }
        # thinking_config 지원 여부 확인 (gemini-2.5 계열)
        thinking_cfg = getattr(genai_types, "ThinkingConfig", None)
        if thinking_cfg is not None:
            try:
                config_kw["thinking_config"] = thinking_cfg(thinkingBudget=512)
            except Exception as _e:
                logger.debug("[AdjustParser] ThinkingConfig 미적용: %s", _e)

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(**config_kw),
        )
        raw_text = _extract_response_text(response)
        if not raw_text:
            logger.warning("[AdjustParser] Gemini 빈 응답")
            return None

        parsed = _parse_gemini_json(raw_text, text)
        return parsed

    except Exception as exc:
        logger.warning("[AdjustParser] Gemini 호출 실패: %s", exc)
        return None


def _extract_response_text(response) -> str:
    """Gemini response 객체에서 텍스트 추출 (다중 경로)."""
    # 1차: .text 속성
    try:
        t = response.text
        if t and len(t) > 2:
            return t
    except Exception:
        pass
    # 2차: candidates → parts
    try:
        for cand in response.candidates or []:
            for part in (cand.content.parts or []):
                t = getattr(part, "text", None)
                if t and len(t) > 2:
                    return t
    except Exception:
        pass
    return ""


def _parse_gemini_json(raw_text: str, original_input: str) -> Optional[AdjustParseResult]:
    """Gemini 응답 텍스트에서 JSON 추출 → AdjustParseResult 변환."""
    # JSON 블록 추출 (```json ... ``` 또는 { ... })
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", raw_text)
    match = re.search(r"```json\s*([\s\S]+?)\s*```", text, re.IGNORECASE)
    if match:
        json_str = match.group(1)
    else:
        brace_match = re.search(r"(\{[\s\S]+\})", text)
        if brace_match:
            json_str = brace_match.group(1)
        else:
            logger.warning("[AdjustParser] Gemini 응답에서 JSON 블록 미발견")
            return None

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning("[AdjustParser] JSON 파싱 실패: %s", exc)
        return None

    items: List[AdjustItem] = []
    ambiguous: List[str] = []
    error_msg: Optional[str] = data.get("error")

    raw_items = data.get("items", [])
    if not isinstance(raw_items, list):
        raw_items = []

    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        lot_no = str(entry.get("lot_no", "")).strip()
        new_count = _safe_int(entry.get("new_count", -1))
        delta = _safe_int(entry.get("delta", 0))
        reason_code = str(entry.get("reason_code", "OTHER")).upper()
        if reason_code not in REASON_CODES:
            reason_code = "OTHER"
        reason_text = str(entry.get("reason_text", "")).strip()
        confidence = float(entry.get("confidence", 1.0))
        confidence = max(0.0, min(1.0, confidence))

        item = AdjustItem(
            lot_no=lot_no,
            new_count=new_count,
            delta=delta,
            reason_code=reason_code,
            reason_text=reason_text,
            confidence=confidence,
            raw_input=original_input,
        )
        items.append(item)
        if confidence < 0.7:
            ambiguous.append(f"{lot_no} (확신도 {confidence:.0%})")

    return AdjustParseResult(items=items, ambiguous=ambiguous, error=error_msg)


# =============================================================================
# 프롬프트 생성
# =============================================================================

def _build_gemini_prompt(text: str, db_context: dict) -> str:
    """
    Gemini 프롬프트 생성.

    Args:
        text:       사용자 원본 입력
        db_context: DB에서 조회한 LOT 컨텍스트

    Returns:
        완성된 프롬프트 문자열
    """
    lots_json = json.dumps(db_context.get("lots", []), ensure_ascii=False, indent=2)

    prompt = f"""당신은 GY Logis 물류창고 재고관리 시스템의 재고조정 파서입니다.
아래 사용자 입력을 분석하여 구조화된 JSON으로 변환하세요.

## 입력
{text}

## 현재 DB 재고 현황 (참고용)
{lots_json if lots_json != '[]' else '(DB 데이터 없음 — LOT 번호 직접 추출)'}

## 파싱 규칙

1. **LOT 번호 인식**: 10자리 숫자(예: 1126012309), 컨테이너 번호(TCLU..., MAEU...), BL 번호(MAEU..., MEDU..., ONEY...) 모두 인식
2. **포대 수 해석**:
   - "X포대밖에 없어" / "X포대야" / "X포대로 확인" → new_count=X (절대값), delta는 DB 조회 후 계산 (0으로 두기)
   - "X포대 줄었어" / "X포대 파손됐어" / "X포대 손상" → delta=-X (상대값), new_count는 -1로 두기
   - "X포대씩" → 모든 LOT에 동일 적용
3. **정상/이상없음 표현**: "정상", "이상없음", "문제없음" → delta=0, new_count는 DB 현재값 유지 (-1로 표시)
4. **다중 LOT**: "랑", "과", "와", "각각" 등으로 연결된 복수 LOT → items 배열로 분리
5. **컨테이너/BL 전체**: DB 현황에 해당 LOT들이 있으면 각각 항목으로 전개, 없으면 lot_no에 컨테이너/BL 번호 기재
6. **확신도(confidence)**:
   - LOT 번호가 명확하고 포대 수도 명확: 0.95
   - LOT 번호는 명확하나 포대 수가 모호: 0.75
   - LOT 번호가 불명확하거나 맥락 추론 필요: 0.55

## 사유 코드 분류
- DAMAGE: 파손, 손상, 찢김, 터짐, 훼손
- LOSS: 분실, 도난, 없어짐, 실종
- RECOUNT: 실사, 재고조사, 실물 확인, 재확인
- TRANSFER: 이동, 이송
- OTHER: 기타

## 출력 형식 (JSON만 반환, 코드블록 포함)
```json
{{
  "items": [
    {{
      "lot_no": "LOT 번호 또는 컨테이너/BL 번호",
      "new_count": 포대_수_또는_-1,
      "delta": 변화량_또는_0,
      "reason_code": "DAMAGE|LOSS|RECOUNT|TRANSFER|OTHER",
      "reason_text": "사유 원문 요약",
      "confidence": 0.0~1.0
    }}
  ],
  "error": null
}}
```

주의: JSON 외 다른 텍스트를 절대 포함하지 마세요."""

    # 제어문자 제거
    prompt = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", prompt)
    return prompt


# =============================================================================
# DB 컨텍스트 수집
# =============================================================================

def _collect_db_context(text: str, db) -> dict:
    """
    텍스트에서 컨테이너/BL 번호를 추출하여 DB LOT 목록 조회.

    Returns:
        {"lots": [{lot_no, tonbag_count, container_no, bl_no, status}, ...]}
    """
    context: Dict[str, Any] = {"lots": []}
    if db is None:
        return context

    # 컨테이너 번호 패턴 (4자리 알파벳 + 6~7자리 숫자, 예: TCLU6404353)
    container_pattern = r"\b([A-Z]{4}\d{6,7})\b"
    # BL 번호 패턴 (MAEU/MEDU/MSCU/HLCU/ONEY + 숫자, 예: MAEU265083673)
    bl_pattern = r"\b(MAEU\d{9}|MEDU\d{9}|MSCU\d{9}|HLCU\d{9}|ONEY\d{9,12})\b"

    containers = re.findall(container_pattern, text.upper())
    bls = re.findall(bl_pattern, text.upper())

    rows: List[Dict] = []
    try:
        for c_no in set(containers):
            found = db.fetchall(
                "SELECT lot_no, tonbag_count, container_no, bl_no, status "
                "FROM inventory WHERE container_no=?",
                (c_no,),
            )
            rows.extend(found or [])

        for bl_no in set(bls):
            found = db.fetchall(
                "SELECT lot_no, tonbag_count, container_no, bl_no, status "
                "FROM inventory WHERE bl_no=?",
                (bl_no,),
            )
            rows.extend(found or [])
    except Exception as exc:
        logger.warning("[AdjustParser] DB 컨텍스트 조회 실패: %s", exc)
        return context

    # 중복 제거 (lot_no 기준)
    seen = set()
    unique_rows: List[Dict] = []
    for r in rows:
        key = str(r.get("lot_no", ""))
        if key not in seen:
            seen.add(key)
            unique_rows.append(r)

    context["lots"] = unique_rows
    return context


# =============================================================================
# LOT 번호 DB 검증 + delta 계산
# =============================================================================

def _validate_lots(items: List[AdjustItem], db, raw_input: str) -> AdjustParseResult:
    """
    파싱된 AdjustItem 목록의 LOT 번호를 DB에서 검증하고
    new_count / delta 값을 보정합니다.

    Args:
        items:     Gemini 또는 fallback이 파싱한 AdjustItem 목록
        db:        SQMDatabase 인스턴스
        raw_input: 원본 입력 (ambiguous 메시지용)

    Returns:
        검증이 완료된 AdjustParseResult
    """
    validated: List[AdjustItem] = []
    ambiguous: List[str] = []

    for item in items:
        if not item.lot_no:
            ambiguous.append(f"LOT 번호 미확인 (입력: {raw_input[:30]}...)")
            item.confidence = min(item.confidence, 0.4)
            validated.append(item)
            continue

        if db is None:
            # DB 없으면 그대로 통과
            validated.append(item)
            if item.confidence < 0.7:
                ambiguous.append(f"{item.lot_no} (확신도 {item.confidence:.0%})")
            continue

        try:
            row = db.fetchone(
                "SELECT lot_no, tonbag_count FROM inventory WHERE lot_no=?",
                (item.lot_no,),
            )
        except Exception as exc:
            logger.warning("[AdjustParser] LOT 검증 DB 조회 실패 (%s): %s", item.lot_no, exc)
            row = None

        if row is None:
            # LOT 미존재 → 컨테이너/BL 번호일 가능성
            logger.debug("[AdjustParser] LOT 미발견: %s — 컨테이너/BL일 수 있음", item.lot_no)
            item.confidence = min(item.confidence, 0.5)
            ambiguous.append(f"{item.lot_no} (DB 미존재)")
            validated.append(item)
            continue

        db_count: int = int(row.get("tonbag_count") or 0)

        # new_count / delta 보정
        if item.new_count >= 0:
            # 절대값 입력 → delta 계산
            item.delta = item.new_count - db_count
        elif item.delta != 0:
            # 상대값 입력 → new_count 계산
            item.new_count = db_count + item.delta
        else:
            # delta=0, new_count=-1 → 정상(변경 없음)
            item.new_count = db_count
            item.delta = 0

        # lot_no 정규화 (DB 원본으로 덮어쓰기)
        item.lot_no = str(row.get("lot_no", item.lot_no))

        validated.append(item)
        if item.confidence < 0.7:
            ambiguous.append(f"{item.lot_no} (확신도 {item.confidence:.0%})")

    return AdjustParseResult(items=validated, ambiguous=ambiguous)


# =============================================================================
# 사유 코드 자동 분류
# =============================================================================

def _reason_classify(text: str) -> str:
    """
    입력 텍스트에서 사유 코드를 자동 분류.

    Returns:
        "DAMAGE" | "LOSS" | "RECOUNT" | "TRANSFER" | "OTHER"
    """
    lower = text.lower()
    for code, keywords in _REASON_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return code
    return "OTHER"


# =============================================================================
# Regex Fallback 파서
# =============================================================================

def _regex_fallback_parse(text: str, db_context: dict, db) -> AdjustParseResult:
    """
    Gemini 실패 시 정규식 기반 fallback 파서.

    처리 가능한 패턴:
      - "LOT번호 X포대 [사유]"          → new_count 또는 delta
      - "LOT번호 X포대밖에 없어"        → new_count=X
      - "LOT번호 X포대 파손됐어"        → delta=-X
      - "LOT번호랑 LOT번호 각각 X포대씩" → 다중 LOT
      - "컨테이너/BL 전체 LOT X포대씩"  → DB 컨텍스트 활용
    """
    items: List[AdjustItem] = []
    ambiguous: List[str] = []

    # 정상 표현 패턴 — 변경 없음 처리
    normal_pattern = re.compile(r"정상|이상\s*없|문제\s*없")

    # LOT 번호 패턴 (10자리 숫자)
    lot_pattern = re.compile(r"\b(\d{10})\b")
    # 포대 수 패턴
    count_pattern = re.compile(r"(\d+)\s*포대")
    # 감소 표현 패턴
    decrease_pattern = re.compile(
        r"(\d+)\s*포대\s*(줄|파손|손상|분실|없어|도난|훼손|찢|터)"
    )
    # 절대값 표현 패턴 ("X포대밖에", "X포대야", "X포대로 확인", "X포대씩")
    absolute_pattern = re.compile(
        r"(\d+)\s*포대\s*(밖에|야|이야|로\s*확인|로\s*확정|씩|뿐)"
    )

    reason_code = _reason_classify(text)
    reason_text = text[:80].strip()

    # 컨테이너/BL 전체 처리 (DB 컨텍스트 LOT 목록 사용)
    db_lots = db_context.get("lots", [])
    if db_lots:
        # 전체 포대 수 추출
        count_match = count_pattern.search(text)
        is_normal = bool(normal_pattern.search(text))

        for row in db_lots:
            lot_no = str(row.get("lot_no", ""))
            if not lot_no:
                continue
            db_count = int(row.get("tonbag_count") or 0)

            if is_normal or not count_match:
                new_count = db_count
                delta = 0
                confidence = 0.85 if is_normal else 0.55
            else:
                new_count = int(count_match.group(1))
                delta = new_count - db_count
                confidence = 0.88

            # 감소 표현이면 delta 적용
            dec_match = decrease_pattern.search(text)
            if dec_match:
                delta = -int(dec_match.group(1))
                new_count = db_count + delta
                confidence = 0.90

            item = AdjustItem(
                lot_no=lot_no,
                new_count=new_count,
                delta=delta,
                reason_code=reason_code,
                reason_text=reason_text,
                confidence=confidence,
                raw_input=text,
            )
            items.append(item)
            if confidence < 0.7:
                ambiguous.append(f"{lot_no} (확신도 {confidence:.0%})")

        if items:
            return AdjustParseResult(items=items, ambiguous=ambiguous)

    # LOT 번호 직접 추출
    lot_matches = lot_pattern.findall(text)
    if not lot_matches:
        return AdjustParseResult(
            error=f"LOT 번호를 찾을 수 없습니다. 입력: '{text[:60]}'"
        )

    # 포대 수 추출 (전체 텍스트에서 1개 또는 "각각 X포대씩")
    count_values = count_pattern.findall(text)
    is_normal = bool(normal_pattern.search(text))
    dec_match = decrease_pattern.search(text)
    abs_match = absolute_pattern.search(text)

    for i, lot_no in enumerate(lot_matches):
        # 포대 수 결정 (인덱스 범위 초과 시 마지막 값 재사용)
        if is_normal:
            new_count = -1
            delta = 0
            confidence = 0.85
        elif dec_match:
            # 감소 표현: delta=-X
            delta = -int(dec_match.group(1))
            new_count = -1  # DB 조회 후 채움
            confidence = 0.90
        elif count_values:
            idx = min(i, len(count_values) - 1)
            cnt = int(count_values[idx])
            if abs_match:
                new_count = cnt
                delta = 0  # DB 조회 후 계산
                confidence = 0.92
            else:
                new_count = cnt
                delta = 0
                confidence = 0.75
        else:
            new_count = -1
            delta = 0
            confidence = 0.50

        item = AdjustItem(
            lot_no=lot_no,
            new_count=new_count,
            delta=delta,
            reason_code=reason_code,
            reason_text=reason_text,
            confidence=confidence,
            raw_input=text,
        )
        items.append(item)
        if confidence < 0.7:
            ambiguous.append(f"{lot_no} (확신도 {confidence:.0%})")

    if not items:
        return AdjustParseResult(
            error=f"파싱 결과가 없습니다. 입력: '{text[:60]}'"
        )

    # DB 검증
    return _validate_lots(items, db, text)


# =============================================================================
# 내부 유틸
# =============================================================================

def _safe_int(v: Any, default: int = 0) -> int:
    """안전한 정수 변환."""
    if v is None or v == "":
        return default
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (ValueError, TypeError):
        return default
