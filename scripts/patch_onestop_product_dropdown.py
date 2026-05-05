#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5단계: 입고 미리보기 product 셀 더블클릭 시 product_master 드롭다운 연결
- window._pmCache[] 전역 캐시
- window.loadPmCache() — /api/product-master/list 호출 후 캐시
- onestopEditCell 수정: field === 'product' 이면 <select> 드롭다운 표시
"""
import sys

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-onestop-inbound.js'

with open(SRC, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"Size: {len(content):,}", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1: 상단에 _pmCache 캐시 변수 + loadPmCache 함수 추가
#   ONESTOP_MAX_HISTORY 선언 바로 뒤에 삽입
# ─────────────────────────────────────────────────────────────────────────────
OLD1 = "  var ONESTOP_MAX_HISTORY = 50;\n  /* [Sprint 1-2-C] 편집 가능 컬럼"
NEW1 = (
    "  var ONESTOP_MAX_HISTORY = 50;\n"
    "\n"
    "  /* ── 제품 마스터 캐시 (product 셀 드롭다운용) ── */\n"
    "  window._pmCache = [];\n"
    "  window.loadPmCache = function() {\n"
    "    return fetch(API + '/api/product-master/list')\n"
    "      .then(function(r){ return r.json(); })\n"
    "      .then(function(res){\n"
    "        var items = (res.data && res.data.items) || [];\n"
    "        window._pmCache = items.filter(function(i){ return i.is_active !== 0; });\n"
    "      })\n"
    "      .catch(function(e){ console.warn('PM cache load failed:', e); });\n"
    "  };\n"
    "  /* 최초 1회 로드 */\n"
    "  window.loadPmCache();\n"
    "\n"
    "  /* [Sprint 1-2-C] 편집 가능 컬럼"
)

if OLD1 in content:
    content = content.replace(OLD1, NEW1, 1)
    print("PATCH 1 OK: _pmCache + loadPmCache 추가", flush=True)
else:
    print("PATCH 1 FAIL", flush=True)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2: onestopEditCell 에서 product 필드 특수 처리
#   일반 <input> 생성 직전에 product 분기 삽입
# ─────────────────────────────────────────────────────────────────────────────
OLD2 = (
    "    var input = document.createElement('input');\n"
    "    input.type = 'text';\n"
    "    input.value = curVal;\n"
    "    input.className = 'onestop-edit-input';\n"
    "    input.style.cssText = 'width:100%;padding:2px 4px;background:var(--bg);color:var(--fg);border:1px solid var(--accent);border-radius:3px;font-size:11px;font-family:inherit';\n"
    "\n"
    "    td.innerHTML = '';\n"
    "    td.appendChild(input);\n"
    "    input.focus();\n"
    "    input.select();\n"
    "\n"
    "    function commit() {\n"
    "      var newVal = input.value;"
)

NEW2 = (
    "    /* ── product 필드: 제품 마스터 드롭다운 ── */\n"
    "    if (field === 'product') {\n"
    "      var pm = window._pmCache || [];\n"
    "      var sel = document.createElement('select');\n"
    "      sel.className = 'onestop-edit-input';\n"
    "      sel.style.cssText = 'width:100%;padding:2px 4px;background:var(--bg);color:var(--fg);border:1px solid var(--accent);border-radius:3px;font-size:11px;font-family:inherit';\n"
    "      /* 첫 옵션: 현재 값 또는 빈값 */\n"
    "      var opts = '<option value=\"\">(제품 선택)</option>';\n"
    "      pm.forEach(function(p) {\n"
    "        var code   = p.code || '';\n"
    "        var fn     = p.full_name || p.product_name || '';\n"
    "        var kr     = p.korean_name || '';\n"
    "        var label  = code ? (code + ' — ' + fn + (kr ? ' / ' + kr : '')) : fn;\n"
    "        var val    = code || fn;\n"
    "        var sel_   = (val === curVal || fn === curVal || p.product_name === curVal) ? ' selected' : '';\n"
    "        opts += '<option value=\"' + val.replace(/\"/g,'&quot;') + '\"' + sel_ + '>' + label + '</option>';\n"
    "      });\n"
    "      /* 직접 입력 옵션 */\n"
    "      opts += '<option value=\"__custom__\">✏️ 직접 입력...</option>';\n"
    "      sel.innerHTML = opts;\n"
    "      td.innerHTML = '';\n"
    "      td.appendChild(sel);\n"
    "      sel.focus();\n"
    "\n"
    "      function commitSel() {\n"
    "        var newVal = sel.value;\n"
    "        if (newVal === '__custom__') {\n"
    "          /* 직접 입력 모드로 전환 */\n"
    "          td.innerHTML = '';\n"
    "          var ci = document.createElement('input');\n"
    "          ci.type = 'text'; ci.value = curVal;\n"
    "          ci.className = 'onestop-edit-input';\n"
    "          ci.style.cssText = 'width:100%;padding:2px 4px;background:var(--bg);color:var(--fg);border:1px solid var(--accent);border-radius:3px;font-size:11px;font-family:inherit';\n"
    "          td.appendChild(ci); ci.focus(); ci.select();\n"
    "          ci.addEventListener('blur', function(){ applyCommit(ci.value); });\n"
    "          ci.addEventListener('keydown', function(e){\n"
    "            if (e.key==='Enter'){ e.preventDefault(); ci.blur(); }\n"
    "            else if (e.key==='Escape'){ e.preventDefault(); ci.removeEventListener('blur',function(){}); _onestopRenderPreview(_onestopState.previewRows); }\n"
    "          });\n"
    "          return;\n"
    "        }\n"
    "        applyCommit(newVal);\n"
    "      }\n"
    "      function applyCommit(newVal) {\n"
    "        if (String(newVal) === String(curVal) || !newVal) {\n"
    "          _onestopRenderPreview(_onestopState.previewRows); return;\n"
    "        }\n"
    "        _onestopState.history = _onestopState.history.slice(0, _onestopState.historyIdx + 1);\n"
    "        _onestopState.history.push({ rowIdx: rowIdx, field: field, oldVal: curVal, newVal: newVal });\n"
    "        if (_onestopState.history.length > ONESTOP_MAX_HISTORY) _onestopState.history.shift();\n"
    "        _onestopState.historyIdx = _onestopState.history.length - 1;\n"
    "        if (!_onestopState.previewRows[rowIdx]) _onestopState.previewRows[rowIdx] = {};\n"
    "        _onestopState.previewRows[rowIdx][field] = newVal;\n"
    "        var origVal = (_onestopState.originalRows[rowIdx] || {})[field];\n"
    "        var cellKey = rowIdx + '.' + field;\n"
    "        if (String(newVal) !== String(origVal == null ? '' : origVal)) { _onestopState.editedCells[cellKey] = true; }\n"
    "        else { delete _onestopState.editedCells[cellKey]; }\n"
    "        _onestopRenderPreview(_onestopState.previewRows);\n"
    "        _onestopUpdateHistoryButtons();\n"
    "      }\n"
    "      sel.addEventListener('change', commitSel);\n"
    "      sel.addEventListener('blur',   commitSel);\n"
    "      sel.addEventListener('keydown', function(e){\n"
    "        if (e.key === 'Enter')  { e.preventDefault(); commitSel(); }\n"
    "        else if (e.key === 'Escape') { e.preventDefault(); sel.removeEventListener('blur', commitSel); _onestopRenderPreview(_onestopState.previewRows); }\n"
    "      });\n"
    "      return;  /* product 처리 끝 — 아래 일반 input 로직 실행 안 함 */\n"
    "    }\n"
    "\n"
    "    var input = document.createElement('input');\n"
    "    input.type = 'text';\n"
    "    input.value = curVal;\n"
    "    input.className = 'onestop-edit-input';\n"
    "    input.style.cssText = 'width:100%;padding:2px 4px;background:var(--bg);color:var(--fg);border:1px solid var(--accent);border-radius:3px;font-size:11px;font-family:inherit';\n"
    "\n"
    "    td.innerHTML = '';\n"
    "    td.appendChild(input);\n"
    "    input.focus();\n"
    "    input.select();\n"
    "\n"
    "    function commit() {\n"
    "      var newVal = input.value;"
)

if OLD2 in content:
    content = content.replace(OLD2, NEW2, 1)
    print("PATCH 2 OK: product 드롭다운 분기 추가", flush=True)
else:
    print("PATCH 2 FAIL", flush=True)
    idx = content.find("var input = document.createElement('input')")
    print("  input 위치:", idx, flush=True)
    sys.exit(1)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print(f"Done. {len(content):,} bytes.", flush=True)
