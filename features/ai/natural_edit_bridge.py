# -*- coding: utf-8 -*-
"""AI 자연어 수정 브리지
이 파일은 OpenAI/Gemini/Claude 어느 쪽이든 붙일 수 있도록
'프롬프트 입력'과 '기대 JSON 스키마'만 정의한다.
"""
from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """
너는 SQM 파싱 보정 보조기다.
역할은 '첫 번째 파싱 라인'의 수정 지시를 구조화하는 것이다.
문서 전체를 다시 파싱하지 말고, 전달된 fields만 기준으로 수정안을 JSON으로 반환하라.
반드시 아래 스키마를 지켜라.
{
  "field_updates": {"FIELD_KEY": "NEW_VALUE"},
  "field_type_updates": {"FIELD_KEY": "float"},
  "remap_hints": [{"from": "column_3", "to": "LOCATION"}],
  "notes": ["brief note"]
}
""".strip()


def build_user_prompt(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
