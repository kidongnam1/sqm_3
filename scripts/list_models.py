# -*- coding: utf-8 -*-
"""
각 API의 실제 사용 가능한 모델 목록 조회
실행: python scripts/list_models.py
"""
import os, sys, json, urllib.request, urllib.error
import configparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = configparser.ConfigParser()
cfg.read(os.path.join(ROOT, "settings.ini"), encoding="utf-8")

XAI_KEY        = (os.environ.get("XAI_API_KEY","")        or cfg.get("xAI",        "api_key", fallback="")).strip()
OPENROUTER_KEY = (os.environ.get("OPENROUTER_API_KEY","") or cfg.get("OpenRouter", "api_key", fallback="")).strip()
GROQ_KEY       = (os.environ.get("GROQ_API_KEY","")       or cfg.get("Groq",       "api_key", fallback="")).strip()

def list_models(name, base_url, key, filter_free=False):
    url = f"{base_url}/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    print(f"\n{'='*60}")
    print(f"[{name}] 모델 목록 조회: {url}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            if filter_free:
                models = [m for m in models if ":free" in m.get("id","")]
            print(f"[{name}] 총 {len(models)}개")
            for m in models[:15]:
                mid = m.get("id","?")
                print(f"  - {mid}")
            if len(models) > 15:
                print(f"  ... 외 {len(models)-15}개")
    except urllib.error.HTTPError as e:
        print(f"[{name}] ERROR {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        print(f"[{name}] EXCEPTION: {e}")

list_models("xAI",        "https://api.x.ai/v1",           XAI_KEY)
list_models("OpenRouter", "https://openrouter.ai/api/v1",  OPENROUTER_KEY, filter_free=True)
list_models("Groq",       "https://api.groq.com/openai/v1",GROQ_KEY)

print(f"\n{'='*60}")
print("위 결과를 Ruby에게 붙여넣기 하세요")
