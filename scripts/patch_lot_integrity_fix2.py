#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JS 구문 오류 수정: showFixLotIntegrityModal 내부 onclick 단일인용부호 충돌 교정
"""
import sys

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    c = f.read()
print(f"Size: {len(c):,}", flush=True)

# 문제 있는 함수 전체를 교체
OLD = "  function showFixLotIntegrityModal() {\n"

# 안전하게 교체할 새 함수 (onclick에 named function 사용)
NEW_FUNC = """\
  function _fixLotIntegrityClose() {
    var ov = document.getElementById('fix-lot-integrity-overlay');
    if (ov) ov.remove();
    renderPage(_currentRoute || 'dashboard');
  }
  function showFixLotIntegrityModal() {
"""

# OLD가 정확히 한 번만 있는지 확인 후 치환
if c.count(OLD) == 1:
    c = c.replace(OLD, NEW_FUNC, 1)
    print("STEP 1: 함수 헤더 앞에 클로저 함수 삽입", flush=True)
else:
    print("STEP 1 FAIL: 패턴 ", c.count(OLD), "회 발견", flush=True)
    sys.exit(1)

# onclick 부분 교정
OLD_BTN = """          '<button onclick="this.closest(\\'[style*=fixed]\\').remove();renderPage(_currentRoute||'dashboard')" style="padding:6px 18px;background:var(--accent);color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:13px">확인 &amp; 새로고침</button>',"""

# 실제 파일 내 어떤 모양인지 확인
idx = c.find("this.closest")
if idx >= 0:
    print("closest 부분 발견:", repr(c[idx-20:idx+80]), flush=True)

# closest 부분 전체를 단순 버튼으로 교체
OLD_BTN2 = '<button onclick="this.closest('
# 정확히 찾기
start = c.find("'<button onclick=\"this.closest(")
if start < 0:
    # 다른 형태로 존재하는지 확인
    start = c.find("onclick=\"this.closest(")
    print("Alternative pattern idx:", start, flush=True)

# 패턴을 단순화해서 찾기
import re
pat = r"'<button onclick=\"this\.closest\([^)]+\)\.remove\(\);renderPage\([^)]+\)\"[^>]+>[^<]+</button>',"
m = re.search(pat, c)
if m:
    OLD_BTN_ACTUAL = m.group(0)
    NEW_BTN = "'<button onclick=\"_fixLotIntegrityClose()\" style=\"padding:6px 18px;background:var(--accent);color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:13px\">확인 &amp; 새로고침</button>',"
    c = c.replace(OLD_BTN_ACTUAL, NEW_BTN, 1)
    print("STEP 2 OK: onclick 교정 완료", flush=True)
else:
    # 수동 찾기
    idx2 = c.find("_fixLotIntegrityClose")
    if idx2 > 0:
        print("이미 교정된 상태 — 추가 수정 불필요", flush=True)
    else:
        print("STEP 2 FAIL: 버튼 패턴 못 찾음", flush=True)
        # 파일에서 closest 근방 출력
        idx3 = c.find("closest")
        print("closest context:", repr(c[max(0,idx3-30):idx3+120]))
        sys.exit(1)

# overlay id 추가 (식별자 추가)
OLD_OV = "    var overlay = document.createElement('div');\n    overlay.style.cssText = 'position:fixed;inset:0;"
NEW_OV = "    var overlay = document.createElement('div');\n    overlay.id = 'fix-lot-integrity-overlay';\n    overlay.style.cssText = 'position:fixed;inset:0;"

if OLD_OV in c:
    c = c.replace(OLD_OV, NEW_OV, 1)
    print("STEP 3 OK: overlay id 추가", flush=True)
else:
    print("STEP 3 SKIP (이미 id 있을 수 있음)", flush=True)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)
print(f"Done. {len(c):,} bytes.", flush=True)
