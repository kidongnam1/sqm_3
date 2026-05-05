#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inventory 탭 필터 바를 4개 드롭다운으로 교체 + 상태 종속 로직 추가
- SAP / BL / LOT / 컨테이너 각각 독립 select 박스
- 상태 필터가 부모: 상태 변경 시 4개 드롭다운 재구성
"""
import sys, re

SRC  = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'
DEST = SRC

print("Reading file...", flush=True)
with open(SRC, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"File size: {len(content):,} bytes", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1: _invAllRows = rows; 를 loadInventoryPage 안에 삽입
# ─────────────────────────────────────────────────────────────────────────────
OLD1 = "      var rows = extractRows(res);\n      if (!rows.length) {\n        c.innerHTML = '<div class=\"empty\" style=\"padding:60px;text-align:center\">No inventory data</div>';"
NEW1 = "      var rows = extractRows(res);\n      _invAllRows = rows;\n      if (!rows.length) {\n        c.innerHTML = '<div class=\"empty\" style=\"padding:60px;text-align:center\">No inventory data</div>';"

if OLD1 in content:
    content = content.replace(OLD1, NEW1, 1)
    print("PATCH 1 applied: _invAllRows = rows", flush=True)
else:
    print("PATCH 1 SKIP (already applied or not found)", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2: 필터 바 HTML 교체 (텍스트 입력 → 4개 드롭다운)
# ─────────────────────────────────────────────────────────────────────────────
OLD2 = (
    "'<div id=\"inv-filter-bar\" style=\"display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px\">' +\n"
    "        '  <label style=\"font-size:12px;white-space:nowrap\">상태:</label>' +\n"
    "        '  <select id=\"inv-status-filter\" style=\"font-size:12px;padding:2px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)\" onchange=\"window.invApplyFilter()\">' +\n"
    "        '    <option value=\"\">전체</option>' +\n"
    "        '    <option value=\"AVAILABLE\">AVAILABLE</option>' +\n"
    "        '    <option value=\"RESERVED\">RESERVED</option>' +\n"
    "        '    <option value=\"PICKED\">PICKED</option>' +\n"
    "        '    <option value=\"RETURN\">RETURN</option>' +\n"
    "        '  </select>' +\n"
    "        '  <input id=\"inv-search-input\" type=\"text\" placeholder=\"LOT / SAP / BL / Product 검색...\" ' +\n"
    "        '    style=\"flex:1;min-width:180px;font-size:12px;padding:2px 8px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)\" ' +\n"
    "        '    oninput=\"window.invApplyFilter()\">' +\n"
    "        '  <button class=\"btn btn-ghost\" style=\"font-size:12px\" onclick=\"window.invClearFilter()\">✕ 초기화</button>' +\n"
    "        '</div>' +"
)

NEW2 = (
    "'<div id=\"inv-filter-bar\" style=\"display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:8px 10px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px\">' +\n"
    "        '<label style=\"font-size:12px;white-space:nowrap;font-weight:600;color:var(--text-muted)\">상태</label>' +\n"
    "        '<select id=\"inv-status-filter\" style=\"font-size:12px;padding:3px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)\" onchange=\"window.invOnStatusChange()\">' +\n"
    "        '<option value=\"\">전체</option>' +\n"
    "        '<option value=\"AVAILABLE\">AVAILABLE</option>' +\n"
    "        '<option value=\"RESERVED\">RESERVED</option>' +\n"
    "        '<option value=\"PICKED\">PICKED</option>' +\n"
    "        '<option value=\"RETURN\">RETURN</option>' +\n"
    "        '</select>' +\n"
    "        '<span style=\"width:1px;height:20px;background:var(--panel-border);margin:0 2px\"></span>' +\n"
    "        '<label style=\"font-size:12px;white-space:nowrap;font-weight:600;color:var(--text-muted)\">SAP</label>' +\n"
    "        '<select id=\"inv-sap-filter\" style=\"font-size:12px;padding:3px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg);min-width:110px\" onchange=\"window.invApplyFilter()\"><option value=\"\">전체</option></select>' +\n"
    "        '<label style=\"font-size:12px;white-space:nowrap;font-weight:600;color:var(--text-muted)\">BL</label>' +\n"
    "        '<select id=\"inv-bl-filter\" style=\"font-size:12px;padding:3px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg);min-width:110px\" onchange=\"window.invApplyFilter()\"><option value=\"\">전체</option></select>' +\n"
    "        '<label style=\"font-size:12px;white-space:nowrap;font-weight:600;color:var(--text-muted)\">LOT</label>' +\n"
    "        '<select id=\"inv-lot-filter\" style=\"font-size:12px;padding:3px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg);min-width:130px\" onchange=\"window.invApplyFilter()\"><option value=\"\">전체</option></select>' +\n"
    "        '<label style=\"font-size:12px;white-space:nowrap;font-weight:600;color:var(--text-muted)\">컨테이너</label>' +\n"
    "        '<select id=\"inv-cont-filter\" style=\"font-size:12px;padding:3px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg);min-width:130px\" onchange=\"window.invApplyFilter()\"><option value=\"\">전체</option></select>' +\n"
    "        '<button class=\"btn btn-ghost\" style=\"font-size:12px;margin-left:auto\" onclick=\"window.invClearFilter()\">✕ 초기화</button>' +\n"
    "        '</div>' +"
)

if OLD2 in content:
    content = content.replace(OLD2, NEW2, 1)
    print("PATCH 2 applied: filter bar → 4 dropdowns", flush=True)
else:
    print("PATCH 2 FAILED: old filter bar HTML not found", flush=True)
    # 디버깅: 첫 300자 비교
    idx = content.find("inv-filter-bar")
    if idx >= 0:
        print("  Found inv-filter-bar at:", idx, flush=True)
        print("  Context:", repr(content[idx:idx+200]), flush=True)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 3: invApplyFilter / invClearFilter 로직 교체 + invPopulateDropdowns / invOnStatusChange 추가
# ─────────────────────────────────────────────────────────────────────────────
OLD3 = (
    "  var _invAllRows = [];  // 전체 행 캐시 (필터용)\n"
    "\n"
    "  window.invApplyFilter = function() {\n"
    "    var statusEl = document.getElementById('inv-status-filter');\n"
    "    var searchEl = document.getElementById('inv-search-input');\n"
    "    var statusVal = statusEl ? statusEl.value : '';\n"
    "    var searchVal = searchEl ? searchEl.value.trim().toLowerCase() : '';\n"
    "    var tbody = document.querySelector('[data-page=\"inventory\"] tbody');\n"
    "    var tfoot = document.querySelector('[data-page=\"inventory\"] tfoot');\n"
    "    if (!tbody) return;\n"
    "\n"
    "    var rows = Array.from(tbody.querySelectorAll('tr'));\n"
    "    var visible = 0;\n"
    "    rows.forEach(function(tr) {\n"
    "      var cells = tr.querySelectorAll('td');\n"
    "      if (!cells.length) return;\n"
    "      var lot    = (cells[1] ? cells[1].textContent : '').toLowerCase();\n"
    "      var sap    = (cells[2] ? cells[2].textContent : '').toLowerCase();\n"
    "      var bl     = (cells[3] ? cells[3].textContent : '').toLowerCase();\n"
    "      var prod   = (cells[4] ? cells[4].textContent : '').toLowerCase();\n"
    "      var status = (cells[5] ? cells[5].textContent.trim() : '').toUpperCase();\n"
    "\n"
    "      var matchStatus = !statusVal || status === statusVal;\n"
    "      var matchSearch = !searchVal ||\n"
    "        lot.includes(searchVal) || sap.includes(searchVal) ||\n"
    "        bl.includes(searchVal)  || prod.includes(searchVal);\n"
    "\n"
    "      if (matchStatus && matchSearch) {\n"
    "        tr.style.display = '';\n"
    "        visible++;\n"
    "      } else {\n"
    "        tr.style.display = 'none';\n"
    "      }\n"
    "    });\n"
    "    var countEl = document.getElementById('inv-count-label');\n"
    "    if (countEl) countEl.textContent = visible + ' / ' + rows.length + ' LOTs';\n"
    "  };\n"
    "\n"
    "  window.invClearFilter = function() {\n"
    "    var statusEl = document.getElementById('inv-status-filter');\n"
    "    var searchEl = document.getElementById('inv-search-input');\n"
    "    if (statusEl) statusEl.value = '';\n"
    "    if (searchEl) searchEl.value = '';\n"
    "    window.invApplyFilter();\n"
    "  };"
)

NEW3 = (
    "  var _invAllRows = [];  // 전체 행 캐시 (필터용)\n"
    "\n"
    "  /* SAP/BL/LOT/컨테이너 드롭다운을 statusFilteredRows 기준으로 재구성 */\n"
    "  window.invPopulateDropdowns = function(filteredRows) {\n"
    "    var fields = [\n"
    "      { id: 'inv-sap-filter',  key: 'sap' },\n"
    "      { id: 'inv-bl-filter',   key: 'bl' },\n"
    "      { id: 'inv-lot-filter',  key: 'lot' },\n"
    "      { id: 'inv-cont-filter', key: 'container' }\n"
    "    ];\n"
    "    fields.forEach(function(f) {\n"
    "      var sel = document.getElementById(f.id);\n"
    "      if (!sel) return;\n"
    "      var prevVal = sel.value;\n"
    "      var vals = [];\n"
    "      filteredRows.forEach(function(r) {\n"
    "        var v = (r[f.key] || '').trim();\n"
    "        if (v && vals.indexOf(v) === -1) vals.push(v);\n"
    "      });\n"
    "      vals.sort();\n"
    "      sel.innerHTML = '<option value=\"\">전체 (' + vals.length + ')</option>' +\n"
    "        vals.map(function(v) {\n"
    "          return '<option value=\"' + escapeHtml(v) + '\"' + (v === prevVal ? ' selected' : '') + '>' + escapeHtml(v) + '</option>';\n"
    "        }).join('');\n"
    "    });\n"
    "  };\n"
    "\n"
    "  /* 상태 변경 시: 드롭다운 재구성 후 필터 적용 */\n"
    "  window.invOnStatusChange = function() {\n"
    "    var statusVal = ((document.getElementById('inv-status-filter') || {}).value || '').toUpperCase();\n"
    "    var statusFiltered = _invAllRows.filter(function(r) {\n"
    "      return !statusVal || (r.status || '').toUpperCase() === statusVal;\n"
    "    });\n"
    "    window.invPopulateDropdowns(statusFiltered);\n"
    "    window.invApplyFilter();\n"
    "  };\n"
    "\n"
    "  /* 4개 드롭다운 + 상태 필터 조합 적용 */\n"
    "  window.invApplyFilter = function() {\n"
    "    var statusVal = ((document.getElementById('inv-status-filter') || {}).value || '').toUpperCase();\n"
    "    var sapVal    = (document.getElementById('inv-sap-filter')    || {}).value || '';\n"
    "    var blVal     = (document.getElementById('inv-bl-filter')     || {}).value || '';\n"
    "    var lotVal    = (document.getElementById('inv-lot-filter')    || {}).value || '';\n"
    "    var contVal   = (document.getElementById('inv-cont-filter')   || {}).value || '';\n"
    "    var tbody = document.querySelector('[data-page=\"inventory\"] tbody');\n"
    "    if (!tbody) return;\n"
    "    var rows = Array.from(tbody.querySelectorAll('tr'));\n"
    "    var visible = 0;\n"
    "    rows.forEach(function(tr) {\n"
    "      var cells = tr.querySelectorAll('td');\n"
    "      if (!cells.length) return;\n"
    "      var lot    = (cells[1] ? cells[1].textContent.trim() : '');\n"
    "      var sap    = (cells[2] ? cells[2].textContent.trim() : '');\n"
    "      var bl     = (cells[3] ? cells[3].textContent.trim() : '');\n"
    "      var status = (cells[5] ? cells[5].textContent.trim() : '').toUpperCase();\n"
    "      var cont   = (cells[8] ? cells[8].textContent.trim() : '');\n"
    "      var ok = (!statusVal || status === statusVal) &&\n"
    "               (!sapVal    || sap    === sapVal)    &&\n"
    "               (!blVal     || bl     === blVal)     &&\n"
    "               (!lotVal    || lot    === lotVal)    &&\n"
    "               (!contVal   || cont   === contVal);\n"
    "      tr.style.display = ok ? '' : 'none';\n"
    "      if (ok) visible++;\n"
    "    });\n"
    "    var countEl = document.getElementById('inv-count-label');\n"
    "    if (countEl) countEl.textContent = visible + ' / ' + rows.length + ' LOTs';\n"
    "  };\n"
    "\n"
    "  window.invClearFilter = function() {\n"
    "    ['inv-status-filter','inv-sap-filter','inv-bl-filter','inv-lot-filter','inv-cont-filter'].forEach(function(id) {\n"
    "      var el = document.getElementById(id); if (el) el.value = '';\n"
    "    });\n"
    "    window.invPopulateDropdowns(_invAllRows);\n"
    "    window.invApplyFilter();\n"
    "  };"
)

if OLD3 in content:
    content = content.replace(OLD3, NEW3, 1)
    print("PATCH 3 applied: invApplyFilter + invClearFilter + new functions", flush=True)
else:
    print("PATCH 3 FAILED: old filter logic not found", flush=True)
    idx = content.find("window.invApplyFilter")
    if idx >= 0:
        print("  Found invApplyFilter at:", idx, flush=True)
        print("  Context:", repr(content[idx:idx+300]), flush=True)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 4: loadInventoryPage 마지막에 invPopulateDropdowns 호출 추가
# 테이블이 렌더된 후 c.innerHTML = html; 바로 다음에 호출
# ─────────────────────────────────────────────────────────────────────────────
OLD4 = (
    "      c.innerHTML = html;\n"
    "    }).catch(function(e){\n"
    "      if (_currentRoute !== route) return;\n"
    "      c.innerHTML = '<div class=\"empty\" style=\"padding:40px;text-align:center\">Load failed: '+escapeHtml(e.message||String(e))+'</div>';\n"
    "      showToast('error', 'Inventory load failed');"
)

NEW4 = (
    "      c.innerHTML = html;\n"
    "      // 드롭다운 초기 구성 (전체 행 기준)\n"
    "      if (window.invPopulateDropdowns) window.invPopulateDropdowns(_invAllRows);\n"
    "    }).catch(function(e){\n"
    "      if (_currentRoute !== route) return;\n"
    "      c.innerHTML = '<div class=\"empty\" style=\"padding:40px;text-align:center\">Load failed: '+escapeHtml(e.message||String(e))+'</div>';\n"
    "      showToast('error', 'Inventory load failed');"
)

if OLD4 in content:
    content = content.replace(OLD4, NEW4, 1)
    print("PATCH 4 applied: invPopulateDropdowns call after render", flush=True)
else:
    print("PATCH 4 SKIP/FAIL: c.innerHTML = html context not found", flush=True)
    idx = content.find("Inventory load failed")
    print("  Inventory load failed at:", idx, flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# Write
# ─────────────────────────────────────────────────────────────────────────────
print("Writing file...", flush=True)
with open(DEST, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print(f"Done. Written {len(content):,} bytes.", flush=True)
