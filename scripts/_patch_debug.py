# -*- coding: utf-8 -*-
"""debug_api_parsers.py + run_comparison_windows.py 패치:
1. .strip() 추가 (xAI 공백/개행 제거)
2. OpenRouter 모델명 교체 (free tier 유효한 것으로)
3. SyntaxWarning \d 수정
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 1. debug_api_parsers.py ──────────────────────────────────
src = os.path.join(ROOT, "scripts", "debug_api_parsers.py")
with open(src, "r", encoding="utf-8") as f:
    c = f.read()

# fix \d SyntaxWarning
c = c.replace(r'실행: python scripts\debug_api_[parsers.py](http://parsers.py)',
              r'실행: python scripts\\debug_api_parsers.py')

# add .strip() to all key reads
c = c.replace(
    'GROQ_KEY       = os.environ.get("GROQ_API_KEY","")       or _cfg.get("Groq",       "api_key", fallback="")',
    'GROQ_KEY       = (os.environ.get("GROQ_API_KEY","")       or _cfg.get("Groq",       "api_key", fallback="")).strip()'
)
c = c.replace(
    'XAI_KEY        = os.environ.get("XAI_API_KEY","")        or _cfg.get("xAI",        "api_key", fallback="")',
    'XAI_KEY        = (os.environ.get("XAI_API_KEY","")        or _cfg.get("xAI",        "api_key", fallback="")).strip()'
)
c = c.replace(
    'OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY","") or _cfg.get("OpenRouter", "api_key", fallback="")',
    'OPENROUTER_KEY = (os.environ.get("OPENROUTER_API_KEY","") or _cfg.get("OpenRouter", "api_key", fallback="")).strip()'
)
c = c.replace(
    'OPENAI_KEY     = os.environ.get("OPENAI_API_KEY","")     or _cfg.get("OpenAI",     "api_key", fallback="")',
    'OPENAI_KEY     = (os.environ.get("OPENAI_API_KEY","")     or _cfg.get("OpenAI",     "api_key", fallback="")).strip()'
)

# fix OpenRouter model: mistralai/mistral-7b-instruct:free → deepseek/deepseek-r1:free
c = c.replace(
    '"mistralai/mistral-7b-instruct:free"',
    '"deepseek/deepseek-r1:free"'
)

with open(src, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)
print("[debug_api_parsers.py] 패치 완료")

# ── 2. run_comparison_windows.py ────────────────────────────
src2 = os.path.join(ROOT, "scripts", "run_comparison_windows.py")
with open(src2, "r", encoding="utf-8") as f:
    c2 = f.read()

# add .strip() to all key reads
replacements = [
    ('or cfg.get("Gemini",    "api_key", fallback="")',
     'or cfg.get("Gemini",    "api_key", fallback="")).strip()'),
    ('or cfg.get("Groq",       "api_key", fallback="")',
     'or cfg.get("Groq",       "api_key", fallback="")).strip()'),
    ('or cfg.get("xAI",        "api_key", fallback="")',
     'or cfg.get("xAI",        "api_key", fallback="")).strip()'),
    ('or cfg.get("OpenRouter", "api_key", fallback="")',
     'or cfg.get("OpenRouter", "api_key", fallback="")).strip()'),
    ('or cfg.get("OpenAI",     "api_key", fallback="")',
     'or cfg.get("OpenAI",     "api_key", fallback="")).strip()'),
]
for old, new in replacements:
    if old in c2:
        # wrap the whole expression in parens for .strip()
        c2 = c2.replace(
            'os.environ.get("GEMINI_API_KEY","")     ' + old,
            '(os.environ.get("GEMINI_API_KEY","")     ' + new,
            1
        )
        c2 = c2.replace(
            'os.environ.get("GROQ_API_KEY","")       ' + old,
            '(os.environ.get("GROQ_API_KEY","")       ' + new,
            1
        )
        c2 = c2.replace(
            'os.environ.get("XAI_API_KEY","")        ' + old,
            '(os.environ.get("XAI_API_KEY","")        ' + new,
            1
        )
        c2 = c2.replace(
            'os.environ.get("OPENROUTER_API_KEY","") ' + old,
            '(os.environ.get("OPENROUTER_API_KEY","") ' + new,
            1
        )
        c2 = c2.replace(
            'os.environ.get("OPENAI_API_KEY","")     ' + old,
            '(os.environ.get("OPENAI_API_KEY","")     ' + new,
            1
        )

# fix OpenRouter model
c2 = c2.replace(
    '"mistralai/mistral-7b-instruct:free"',
    '"deepseek/deepseek-r1:free"'
)

with open(src2, "w", encoding="utf-8", newline="\n") as f:
    f.write(c2)
print("[run_comparison_windows.py] 패치 완료")
