# -*- coding: utf-8 -*-
"""
Gemini API 전수 진단 스크립트
실행: python debug_gemini.py
"""
import os, sys
sys.path.insert(0, '.')

KEY = os.environ.get('GEMINI_API_KEY', '')
print(f"[1] API 키: {'있음 (길이 ' + str(len(KEY)) + ')' if KEY else '❌ 없음 — GEMINI_API_KEY 환경변수 확인'}")
if not KEY:
    sys.exit(1)

from google import genai

client = genai.Client(api_key=KEY)

# ── Step 2: 사용 가능한 모델 목록 ────────────────────────────────────────
print("\n[2] models.list() 조회...")
try:
    models = list(client.models.list())
    names = sorted([m.name.split('/')[-1] for m in models if 'gemini' in m.name.lower()])
    print(f"  사용 가능 모델 {len(names)}개:")
    for n in names:
        print(f"    {n}")
except Exception as e:
    print(f"  ❌ models.list() 오류: {e}")

# ── Step 3: 모델별 단순 Hello 호출 테스트 ────────────────────────────────
TEST_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]
print("\n[3] 모델별 단순 호출 테스트 ('Hello' 전송):")
for model in TEST_MODELS:
    try:
        r = client.models.generate_content(model=model, contents="Hello. Reply with OK only.")
        print(f"  ✅ {model}: {r.text[:50]!r}")
    except Exception as e:
        err = str(e)[:120]
        print(f"  ❌ {model}: {err}")

# ── Step 4: GeminiDocumentParser 초기화 및 모델 선택 확인 ─────────────────
print("\n[4] GeminiDocumentParser 초기화 (실제 코드 경로):")
try:
    import logging
    logging.basicConfig(level=logging.INFO, format='  %(message)s')
    from features.ai.gemini_parser import GeminiDocumentParser
    gp = GeminiDocumentParser(api_key=KEY)
    print(f"  선택된 모델: {gp.model}")
except Exception as e:
    print(f"  ❌ 초기화 오류: {e}")

print("\n[진단 완료]")
