#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sales Order DN 모달 인용부호 충돌 수정
onclick에서 단일 인용부호 → named function으로 교체
"""
import sys, re

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    c = f.read()
print(f"Size: {len(c):,}", flush=True)

# ✕ 버튼 onclick 교정 (so-dn-overlay)
OLD1 = """        '<button onclick="document.getElementById(\\'so-dn-overlay\\').remove()" ',
          'style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--text-muted);line-height:1">✕</button>',"""

# 실제 내용 확인
idx = c.find("document.getElementById('so-dn-overlay')")
if idx < 0:
    idx = c.find('so-dn-overlay')
print(f"so-dn-overlay 위치: {idx}", flush=True)
if idx > 0:
    print("근방:", repr(c[max(0,idx-50):idx+120]), flush=True)

# regex로 패턴 찾아서 교체
pat1 = r"'<button onclick=\"document\.getElementById\('so-dn-overlay'\)\.remove\(\)\" ',"
m1 = re.search(pat1, c)
if m1:
    old_str = m1.group(0)
    new_str = "'<button onclick=\"_soDnClose()\" ',"
    c = c.replace(old_str, new_str, 1)
    print("PATCH 1 OK: ✕ 버튼 onclick 교정", flush=True)
else:
    # 다른 형태 시도
    pat1b = r"getElementById\(['\"]so-dn-overlay['\"]\)\.remove\(\)"
    m1b = re.search(pat1b, c)
    if m1b:
        print("패턴 1b 발견:", repr(c[m1b.start()-30:m1b.end()+30]), flush=True)
    print("PATCH 1 FAIL", flush=True)
    sys.exit(1)

# _soDnClose 함수 삽입 (showSalesOrderDnTemplateModal 앞에)
ANCHOR2 = "  function showSalesOrderDnTemplateModal()"
CLOSE_FN = """\
  function _soDnClose() {
    var ov = document.getElementById('so-dn-overlay');
    if (ov) ov.remove();
  }
"""
if ANCHOR2 in c:
    c = c.replace(ANCHOR2, CLOSE_FN + "  function showSalesOrderDnTemplateModal()", 1)
    print("PATCH 2 OK: _soDnClose 함수 삽입", flush=True)
else:
    print("PATCH 2 FAIL", flush=True); sys.exit(1)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)
print(f"Done. {len(c):,} bytes.", flush=True)
