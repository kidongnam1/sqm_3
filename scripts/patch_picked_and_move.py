#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1. Move 탭 테이블 td 가운데 정렬 (text-align:center)
2. Picked 탭 V864-2 동일하게 서브메뉴 + No. + 체크박스 + 합계행 추가
"""
import sys

SRC  = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

print("Reading...", flush=True)
with open(SRC, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"Size: {len(content):,} bytes", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1: Move 탭 테이블 td 가운데 정렬
#   현재 text-align:right 셀만 있고 나머지는 지정 없음
#   → 명시적으로 text-align:center 추가
# ─────────────────────────────────────────────────────────────────────────────
OLD_MOVE_ROW = (
    "        return '<tr>' +\n"
    "          '<td class=\"mono-cell\">'+escapeHtml(r.movement_date||r.moved_at||r.date||'')+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"color:var(--accent)\">'+escapeHtml(r.lot_no||r.sub_lt||r.barcode||'')+'</td>' +\n"
    "          '<td>'+escapeHtml(r.movement_type||'')+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:right\">'+qtyMT+'</td>' +\n"
    "          '<td class=\"mono-cell\">'+escapeHtml(r.from_location||'-')+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"color:var(--accent)\">'+escapeHtml(r.to_location||'-')+'</td>' +\n"
    "          '<td>'+escapeHtml(r.actor||r.moved_by||'system')+'</td></tr>';"
)

NEW_MOVE_ROW = (
    "        return '<tr>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:center\">'+escapeHtml(r.movement_date||r.moved_at||r.date||'')+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:center;color:var(--accent)\">'+escapeHtml(r.lot_no||r.sub_lt||r.barcode||'')+'</td>' +\n"
    "          '<td style=\"text-align:center\">'+escapeHtml(r.movement_type||'')+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:center\">'+qtyMT+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:center\">'+escapeHtml(r.from_location||'-')+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:center;color:var(--accent)\">'+escapeHtml(r.to_location||'-')+'</td>' +\n"
    "          '<td style=\"text-align:center\">'+escapeHtml(r.actor||r.moved_by||'system')+'</td></tr>';"
)

if OLD_MOVE_ROW in content:
    content = content.replace(OLD_MOVE_ROW, NEW_MOVE_ROW, 1)
    print("PATCH 1 applied: Move table center align", flush=True)
else:
    print("PATCH 1 SKIP: Move row pattern not found", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2: Picked 탭 - V864-2 서브메뉴 + No. + 체크박스 + 합계행
# ─────────────────────────────────────────────────────────────────────────────

OLD_PICKED_HTML = (
    "    c.innerHTML = [\n"
    "      '<section class=\"page\" data-page=\"picked\">',\n"
    "      '<div style=\"display:flex;align-items:center;gap:12px;padding:8px 0 12px\">',\n"
    "      '  <h2 style=\"margin:0\">🚛 Picked - 피킹 완료 (화물 결정)</h2>',\n"
    "      '  <button class=\"btn btn-secondary\" onclick=\"renderPage(\\'picked\\')\" style=\"margin-left:auto\">🔁 새로고침</button>',\n"
    "      '</div>',\n"
    "      '<div id=\"picked-loading\" style=\"padding:40px;text-align:center;color:var(--text-muted)\">⏳ 데이터 로딩 중...</div>',\n"
    "      '<div style=\"overflow-x:auto\">',\n"
    "      '  <table class=\"data-table\" id=\"picked-table\" style=\"display:none\">',\n"
    "      '  <thead><tr><th></th><th>LOT No</th><th>피킹No</th><th>고객사</th><th>톤백수</th><th>중량(kg)</th><th>피킹일</th></tr></thead>',\n"
    "      '  <tbody id=\"picked-tbody\"></tbody>',\n"
    "      '  </table>',\n"
    "      '</div>',\n"
    "      '<div class=\"empty\" id=\"picked-empty\" style=\"display:none;padding:60px;text-align:center\">📭 피킹 데이터 없음</div>',\n"
    "      '<div id=\"picked-detail-panel\" style=\"display:none;margin-top:16px;border-top:2px solid var(--border);padding-top:16px\">',\n"
    "      '  <h3 id=\"picked-detail-title\" style=\"margin:0 0 12px 0\">톤백 상세</h3>',\n"
    "      '  <div id=\"picked-detail-content\"></div>',\n"
    "      '</div>',\n"
    "      '</section>'\n"
    "    ].join('');"
)

NEW_PICKED_HTML = (
    "    c.innerHTML = [\n"
    "      '<section class=\"page\" data-page=\"picked\">',\n"
    "      /* ── 헤더 + 툴바 ── */\n"
    "      '<div style=\"display:flex;align-items:center;gap:6px;padding:6px 0 10px;flex-wrap:wrap;border-bottom:1px solid var(--panel-border);margin-bottom:8px\">',\n"
    "      '<h2 style=\"margin:0;font-size:16px\">🚛 Picked - 피킹 완료 (화물 결정)</h2>',\n"
    "      '<div style=\"margin-left:auto;display:flex;gap:6px;align-items:center;flex-wrap:wrap\">',\n"
    "      '<button class=\"btn btn-secondary btn-sm\" onclick=\"renderPage(\\'picked\\')\">🔁 새로고침</button>',\n"
    "      '<button class=\"btn btn-warning btn-sm\" onclick=\"window.pickedCancelSale()\" title=\"선택된 LOT의 PICKED → RESERVED 되돌리기\">↩ 판매 결정 취소 (→ 판매 배정)</button>',\n"
    "      '<button class=\"btn btn-ghost btn-sm\" onclick=\"window.pickedSelectAll()\">☑ 전체 선택</button>',\n"
    "      '<span style=\"width:1px;height:20px;background:var(--panel-border)\"></span>',\n"
    "      '<button class=\"btn btn-secondary btn-sm\" onclick=\"window.pickedExportExcel()\">📊 Excel 내보내기</button>',\n"
    "      '<button class=\"btn btn-ghost btn-sm\" onclick=\"window.pickedToggleAllDetail()\">📋 전체 피킹 보기</button>',\n"
    "      '</div></div>',\n"
    "      /* ── 합계 표시줄 ── */\n"
    "      '<div id=\"picked-summary-bar\" style=\"display:none;padding:4px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:4px;font-size:12px;color:var(--text-muted);margin-bottom:8px\">',\n"
    "      'Σ 건수: <b id=\"picked-sum-count\">0</b> &nbsp;|&nbsp; 중량(kg): <b id=\"picked-sum-kg\">0</b>',\n"
    "      '</div>',\n"
    "      '<div id=\"picked-loading\" style=\"padding:40px;text-align:center;color:var(--text-muted)\">⏳ 데이터 로딩 중...</div>',\n"
    "      '<div style=\"overflow-x:auto\">',\n"
    "      '<table class=\"data-table\" id=\"picked-table\" style=\"display:none\">',\n"
    "      '<thead><tr>',\n"
    "      '<th style=\"width:32px;text-align:center\"><input type=\"checkbox\" id=\"picked-chk-all\" onclick=\"window.pickedToggleAll(this.checked)\"></th>',\n"
    "      '<th style=\"text-align:center\">No.</th>',\n"
    "      '<th style=\"text-align:center\">LOT NO</th>',\n"
    "      '<th style=\"text-align:center\">피킹No</th>',\n"
    "      '<th style=\"text-align:center\">고객사</th>',\n"
    "      '<th style=\"text-align:center\">톤백수</th>',\n"
    "      '<th style=\"text-align:center\">중량(kg)</th>',\n"
    "      '<th style=\"text-align:center\">피킹일</th>',\n"
    "      '</tr></thead>',\n"
    "      '<tbody id=\"picked-tbody\"></tbody>',\n"
    "      '</table>',\n"
    "      '</div>',\n"
    "      '<div class=\"empty\" id=\"picked-empty\" style=\"display:none;padding:60px;text-align:center\">📭 피킹 데이터 없음</div>',\n"
    "      '<div id=\"picked-detail-panel\" style=\"display:none;margin-top:16px;border-top:2px solid var(--border);padding-top:16px\">',\n"
    "      '<h3 id=\"picked-detail-title\" style=\"margin:0 0 12px 0\">톤백 상세</h3>',\n"
    "      '<div id=\"picked-detail-content\"></div>',\n"
    "      '</div>',\n"
    "      '</section>'\n"
    "    ].join('');"
)

if OLD_PICKED_HTML in content:
    content = content.replace(OLD_PICKED_HTML, NEW_PICKED_HTML, 1)
    print("PATCH 2 applied: Picked HTML with toolbar", flush=True)
else:
    print("PATCH 2 FAILED: Picked HTML pattern not found", flush=True)
    idx = content.find("loadPickedPage")
    if idx >= 0:
        print("  loadPickedPage at:", idx, flush=True)
        print("  Context:", repr(content[idx:idx+400]), flush=True)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 3: Picked 탭 - 데이터 행 렌더링 (No. + 체크박스 + center)
# ─────────────────────────────────────────────────────────────────────────────
OLD_PICKED_ROW = (
    "      if (tbody) tbody.innerHTML = rows.map(function(r){\n"
    "        var lot = escapeHtml(r.lot_no||'');\n"
    "        return '<tr class=\"picked-summary-row\" data-lot=\"'+lot+'\" style=\"cursor:pointer\" onclick=\"window.togglePickedDetail(\\''+lot+'\\')\">'+\n"
    "          '<td style=\"width:24px;text-align:center\"><span class=\"picked-expand-icon\">▶</span></td>' +\n"
    "          '<td class=\"mono-cell\" style=\"color:var(--accent);font-weight:600\">'+lot+'</td>' +\n"
    "          '<td class=\"mono-cell\">'+escapeHtml(r.picking_no||'')+'</td>' +\n"
    "          '<td>'+escapeHtml(r.customer||r.picked_to||'')+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:right\">'+(r.tonbag_count||0)+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:right\">'+(r.total_kg!=null?fmtN(r.total_kg):'-')+'</td>' +\n"
    "          '<td class=\"mono-cell\">'+escapeHtml(r.picking_date||'')+'</td>' +\n"
    "          '</tr>';\n"
    "      }).join('');\n"
    "      document.getElementById('picked-table').style.display = '';"
)

NEW_PICKED_ROW = (
    "      var totalCount = 0, totalKg = 0;\n"
    "      if (tbody) tbody.innerHTML = rows.map(function(r, idx){\n"
    "        var lot = escapeHtml(r.lot_no||'');\n"
    "        totalCount += (r.tonbag_count||0);\n"
    "        totalKg += (r.total_kg||0);\n"
    "        return '<tr class=\"picked-summary-row\" data-lot=\"'+lot+'\" data-idx=\"'+(idx+1)+'\">' +\n"
    "          '<td style=\"text-align:center;width:32px\"><input type=\"checkbox\" class=\"picked-row-chk\" onclick=\"event.stopPropagation()\" data-lot=\"'+lot+'\"></td>' +\n"
    "          '<td style=\"text-align:center;color:var(--text-muted);font-size:11px\">'+(idx+1)+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:center;color:var(--accent);font-weight:600;cursor:pointer\" onclick=\"window.togglePickedDetail(\\''+lot+'\\')\">' +\n"
    "            lot + ' <span class=\"picked-expand-icon\" style=\"font-size:10px\">▶</span></td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:center\">'+escapeHtml(r.picking_no||'-')+'</td>' +\n"
    "          '<td style=\"text-align:center\">'+escapeHtml(r.customer||r.picked_to||'-')+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:center\">'+(r.tonbag_count||0)+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:center\">'+(r.total_kg!=null?fmtN(r.total_kg):'-')+'</td>' +\n"
    "          '<td class=\"mono-cell\" style=\"text-align:center\">'+escapeHtml((r.picking_date||'').slice(0,10))+'</td>' +\n"
    "          '</tr>';\n"
    "      }).join('');\n"
    "      var sumBar = document.getElementById('picked-summary-bar');\n"
    "      if (sumBar) {\n"
    "        document.getElementById('picked-sum-count').textContent = totalCount;\n"
    "        document.getElementById('picked-sum-kg').textContent = fmtN(totalKg);\n"
    "        sumBar.style.display = '';\n"
    "      }\n"
    "      document.getElementById('picked-table').style.display = '';"
)

if OLD_PICKED_ROW in content:
    content = content.replace(OLD_PICKED_ROW, NEW_PICKED_ROW, 1)
    print("PATCH 3 applied: Picked rows with No. + checkbox + center", flush=True)
else:
    print("PATCH 3 FAILED: Picked row pattern not found", flush=True)
    idx = content.find("picked-summary-row")
    print("  picked-summary-row at:", idx, flush=True)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 4: Picked 탭 새 핸들러 함수 추가 (togglePickedDetail 바로 앞에 삽입)
# ─────────────────────────────────────────────────────────────────────────────
OLD_PICKED_HANDLERS_ANCHOR = "  var _pickedExpandedLot = null;\n  window.togglePickedDetail = function(lotNo) {"

NEW_PICKED_HANDLERS = (
    "  /* ── Picked 탭 추가 핸들러 ── */\n"
    "  window.pickedSelectAll = function() {\n"
    "    var allChk = document.getElementById('picked-chk-all');\n"
    "    var state = allChk ? !allChk.checked : true;\n"
    "    if (allChk) allChk.checked = state;\n"
    "    document.querySelectorAll('.picked-row-chk').forEach(function(c){ c.checked = state; });\n"
    "  };\n"
    "  window.pickedToggleAll = function(checked) {\n"
    "    document.querySelectorAll('.picked-row-chk').forEach(function(c){ c.checked = checked; });\n"
    "  };\n"
    "  window.pickedCancelSale = function() {\n"
    "    var lots = Array.from(document.querySelectorAll('.picked-row-chk:checked')).map(function(c){ return c.dataset.lot; });\n"
    "    if (!lots.length) { showToast('warning','되돌릴 LOT을 선택하세요'); return; }\n"
    "    if (!confirm(lots.length + '개 LOT을 PICKED → RESERVED (판매 배정)로 되돌리겠습니까?')) return;\n"
    "    apiPost('/api/allocation/revert-step', {step:'picked_to_reserved', lot_nos: lots})\n"
    "      .then(function(res){ showToast('success', (res.reverted||lots.length) + 'LOT 되돌리기 완료'); renderPage('picked'); })\n"
    "      .catch(function(e){ showToast('error', '실패: '+(e.message||String(e))); });\n"
    "  };\n"
    "  window.pickedExportExcel = function() {\n"
    "    var url = '/api/allocation/export-excel?status=PICKED';\n"
    "    var a = document.createElement('a'); a.href = url; a.download = 'picked_list.xlsx'; a.click();\n"
    "  };\n"
    "  var _pickedShowAllDetail = false;\n"
    "  window.pickedToggleAllDetail = function() {\n"
    "    _pickedShowAllDetail = !_pickedShowAllDetail;\n"
    "    var rows = document.querySelectorAll('.picked-summary-row');\n"
    "    if (_pickedShowAllDetail) {\n"
    "      rows.forEach(function(tr){ var lot = tr.dataset.lot; if (lot) window.togglePickedDetail(lot); });\n"
    "    } else {\n"
    "      var panel = document.getElementById('picked-detail-panel');\n"
    "      if (panel) panel.style.display = 'none';\n"
    "      _pickedExpandedLot = null;\n"
    "      document.querySelectorAll('.picked-expand-icon').forEach(function(i){ i.textContent='▶'; });\n"
    "    }\n"
    "  };\n"
    "\n"
    "  var _pickedExpandedLot = null;\n"
    "  window.togglePickedDetail = function(lotNo) {"
)

if OLD_PICKED_HANDLERS_ANCHOR in content:
    content = content.replace(OLD_PICKED_HANDLERS_ANCHOR, NEW_PICKED_HANDLERS, 1)
    print("PATCH 4 applied: Picked new handler functions", flush=True)
else:
    print("PATCH 4 FAILED: handler anchor not found", flush=True)
    idx = content.find("_pickedExpandedLot")
    print("  _pickedExpandedLot at:", idx, flush=True)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Write
# ─────────────────────────────────────────────────────────────────────────────
print("Writing...", flush=True)
with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print(f"Done. {len(content):,} bytes written.", flush=True)
