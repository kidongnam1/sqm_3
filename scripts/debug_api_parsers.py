# -*- coding: utf-8 -*-
"""
API 파서 디버그 스크립트
Groq / xAI / OpenRouter / OpenAI 각각 MAERSK_DO.pdf 하나로 테스트
전체 에러 메시지 출력 (80자 자르기 없음)

실행: python scripts\debug_api_parsers.py
"""
import os, sys, time, json, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PDF = os.path.join(ROOT, "tests", "fixtures", "MAERSK_DO.pdf")

import configparser as _cfg_mod
_cfg = _cfg_mod.ConfigParser()
_cfg.read(os.path.join(ROOT, "settings.ini"), encoding="utf-8")
GROQ_KEY       = os.environ.get("GROQ_API_KEY","")       or _cfg.get("Groq",       "api_key", fallback="")
XAI_KEY        = os.environ.get("XAI_API_KEY","")        or _cfg.get("xAI",        "api_key", fallback="")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY","") or _cfg.get("OpenRouter", "api_key", fallback="")
OPENAI_KEY     = os.environ.get("OPENAI_API_KEY","")     or _cfg.get("OpenAI",     "api_key", fallback="")

PROVIDERS = [
    ("Groq",        "https://api.groq.com/openai/v1",    "llama-3.3-70b-versatile",             GROQ_KEY),
    ("xAI",         "https://api.x.ai/v1",               "grok-beta",                            XAI_KEY),
    ("OpenRouter",  "https://openrouter.ai/api/v1",      "mistralai/mistral-7b-instruct:free",   OPENROUTER_KEY),
    ("OpenAI",      "https://api.openai.com/v1",         "gpt-4o-mini",                          OPENAI_KEY),
]

print(f"PDF: {PDF}")
print(f"PDF exists: {os.path.exists(PDF)}\n")

# --- raw HTTP ping test (직접 curl-like 요청) ---
def raw_ping(name, base_url, model, key):
    url = f"{base_url}/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with JSON: {\"test\":\"ok\"}"}],
        "max_tokens": 50,
        "temperature": 0
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}" if key else ""
    }
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    print(f"\n{'='*60}")
    print(f"[{name}] URL: {url}")
    print(f"[{name}] Model: {model}")
    print(f"[{name}] Key prefix: {key[:20]}..." if key else f"[{name}] KEY EMPTY")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = time.time() - t0
            print(f"[{name}] HTTP 200  ({elapsed:.1f}s)")
            data = json.loads(raw)
            if "choices" in data:
                content = data["choices"][0]["message"].get("content","")
                print(f"[{name}] Response: {content[:200]}")
            else:
                print(f"[{name}] Raw: {raw[:300]}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"[{name}] HTTP ERROR {e.code}: {detail[:500]}")
    except urllib.error.URLError as e:
        print(f"[{name}] URL ERROR: {e}")
    except Exception as e:
        print(f"[{name}] EXCEPTION: {e}")

for name, base_url, model, key in PROVIDERS:
    raw_ping(name, base_url, model, key)

print(f"\n{'='*60}")
print("--- 위 결과를 Ruby에게 붙여넣기 하세요 ---")
