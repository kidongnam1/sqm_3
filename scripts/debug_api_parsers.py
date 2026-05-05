# -*- coding: utf-8 -*-
"""
API 파서 디버그 스크립트
Gemini MAERSK_DO.pdf 하나로 테스트
전체 에러 메시지 출력 (80자 자르기 없음)

실행: python scripts/debug_api_parsers.py
"""
import os, sys, time, json, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PDF = os.path.join(ROOT, "tests", "fixtures", "MAERSK_DO.pdf")

import configparser as _cfg_mod
_cfg = _cfg_mod.ConfigParser()
_cfg.read(os.path.join(ROOT, "settings.ini"), encoding="utf-8")
GEMINI_KEY = (os.environ.get("GEMINI_API_KEY", "") or _cfg.get("Gemini", "api_key", fallback="")).strip()

print(f"PDF: {PDF}")
print(f"PDF exists: {os.path.exists(PDF)}")
print(f"Gemini key prefix: {GEMINI_KEY[:20]}..." if GEMINI_KEY else "Gemini KEY EMPTY")
print()

# --- Gemini ping test ---
def gemini_ping(key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": "Reply with JSON: {\"test\":\"ok\"}"}]}],
        "generationConfig": {"maxOutputTokens": 50, "temperature": 0}
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    print(f"\n{'='*60}")
    print(f"[Gemini] URL: {url[:80]}...")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = time.time() - t0
            print(f"[Gemini] HTTP 200  ({elapsed:.1f}s)")
            data = json.loads(raw)
            candidates = data.get("candidates") or []
            if candidates:
                content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                print(f"[Gemini] Response: {content[:200]}")
            else:
                print(f"[Gemini] Raw (no candidates): {raw[:300]}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"[Gemini] HTTP ERROR {e.code}: {detail[:500]}")
    except urllib.error.URLError as e:
        print(f"[Gemini] URL ERROR: {e}")
    except Exception as e:
        print(f"[Gemini] EXCEPTION: {e}")

if GEMINI_KEY:
    gemini_ping(GEMINI_KEY)
else:
    print("[Gemini] KEY없음 -- settings.ini [Gemini] api_key 설정 후 재실행")

print(f"\n{'='*60}")
print("--- 위 결과를 Ruby에게 붙여넣기 하세요 ---")
