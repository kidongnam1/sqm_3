#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Picked 탭 행 렌더링 교체 + 핸들러 추가
파일에서 직접 추출한 정확한 패턴 사용
"""
import sys, re

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"Size: {len(content):,}", flush=True)

# ─── PATCH 3: tbody.innerHTML 교체 (파일 내용 그대로 매칭) ───────────────────
# 파일에서 직접 읽어낸 패턴 (줄 1917~1929 그대로)
START_MARKER = "      if (tbody) tbody.innerHTML = rows.map(function(r){\n        var lot = escapeHtml(r.lot_no||'');\n        return '<tr class=\"picked-summary-row\""
END_MARKER   = "      document.getElementById('picked-table').style.display = '';\n    }).catch(function(e){\n      if (_currentRoute !== route) return;\n      document.getElementById('picked-loading').style.display = 'none';\n      var el = document.getElementById('picked-empty');"

start_idx = content.find(START_MARKER)
if start_idx < 0:
    print("START_MARKER not found", flush=True)
    sys.exit(1)

end_idx = content.find(END_MARKER, start_idx)
if end_idx < 0:
    print("END_MARKER not found", flush=True)
    sys.exit(1)

# end_idx 는 END_MARKER 시작점; 실제로는 "document.getElementById('picked-table').style.display = '';\n" 까지만 교체
END_OF_REPLACE = content.find("\n    }).catch(function(e){", start_idx)
OLD_BLOCK = content[start_idx:END_OF_REPLACE+1]
print("OLD_BLOCK found, length:", len(OLD_BLOCK), flush=True)
print("OLD_BLOCK first 100:", repr(OLD_BLOCK[:100]), flush=True)

NEW_BLOCK = """      var totalCount = 0, totalKg = 0;
      if (tbody) tbody.innerHTML = rows.map(function(r, idx){
        var lot = escapeHtml(r.lot_no||'');
        totalCount += (r.tonbag_count||0);
        totalKg += (r.total_kg||0);
        return '<tr class="picked-summary-row" data-lot="'+lot+'">' +
          '<td style="text-align:center;width:32px"><input type="checkbox" class="picked-row-chk" onclick="event.stopPropagation()" data-lot="'+lot+'"></td>' +
          '<td style="text-align:center;color:var(--text-muted);font-size:11px">'+(idx+1)+'</td>' +
          '<td class="mono-cell" style="text-align:center;color:var(--accent);font-weight:600;cursor:pointer" onclick="window.togglePickedDetail(\\''+lot+'\\')">' +
            lot+' <span class="picked-expand-icon" style="font-size:10px">▶</span></td>' +
          '<td class="mono-cell" style="text-align:center">'+escapeHtml(r.picking_no||'-')+'</td>' +
          '<td style="text-align:center">'+escapeHtml(r.customer||r.picked_to||'-')+'</td>' +
          '<td class="mono-cell" style="text-align:center">'+(r.tonbag_count||0)+'</td>' +
          '<td class="mono-cell" style="text-align:center">'+(r.total_kg!=null?fmtN(r.total_kg):'-')+'</td>' +
          '<td class="mono-cell" style="text-align:center">'+escapeHtml((r.picking_date||'').slice(0,10))+'</td>' +
          '</tr>';
      }).join('');
      var sumBar = document.getElementById('picked-summary-bar');
      if (sumBar) {
        document.getElementById('picked-sum-count').textContent = totalCount;
        document.getElementById('picked-sum-kg').textContent = fmtN(totalKg);
        sumBar.style.display = '';
      }
      document.getElementById('picked-table').style.display = '';"""

content = content[:start_idx] + NEW_BLOCK + content[END_OF_REPLACE+1:]
print("PATCH 3 OK", flush=True)

# ─── PATCH 4: 새 핸들러 삽입 ────────────────────────────────────────────────
OLD4 = "  var _pickedExpandedLot = null;\n  window.togglePickedDetail = function(lotNo) {"

NEW4 = """  /* ── Picked 탭 추가 핸들러 ── */
  window.pickedToggleAll = function(checked) {
    document.querySelectorAll('.picked-row-chk').forEach(function(c){ c.checked = checked; });
  };
  window.pickedSelectAll = function() {
    var allChk = document.getElementById('picked-chk-all');
    var newState = allChk ? !allChk.checked : true;
    if (allChk) allChk.checked = newState;
    window.pickedToggleAll(newState);
  };
  window.pickedCancelSale = function() {
    var lots = Array.from(document.querySelectorAll('.picked-row-chk:checked')).map(function(c){ return c.dataset.lot; });
    if (!lots.length) { showToast('warning','되돌릴 LOT을 선택하세요'); return; }
    if (!confirm(lots.length + '개 LOT을 PICKED → RESERVED (판매 배정)로 되돌리겠습니까?')) return;
    apiPost('/api/allocation/revert-step', {step:'picked_to_reserved', lot_nos: lots})
      .then(function(res){ showToast('success', (res.reverted||lots.length) + ' LOT 되돌리기 완료'); renderPage('picked'); })
      .catch(function(e){ showToast('error', '실패: '+(e.message||String(e))); });
  };
  window.pickedExportExcel = function() {
    var a = document.createElement('a');
    a.href = '/api/allocation/export-excel?status=PICKED';
    a.download = 'picked_list.xlsx'; a.click();
  };
  var _pickedShowAllDetail = false;
  window.pickedToggleAllDetail = function() {
    _pickedShowAllDetail = !_pickedShowAllDetail;
    if (!_pickedShowAllDetail) {
      var panel = document.getElementById('picked-detail-panel');
      if (panel) panel.style.display = 'none';
      _pickedExpandedLot = null;
      document.querySelectorAll('.picked-expand-icon').forEach(function(i){ i.textContent='▶'; });
    }
  };

  var _pickedExpandedLot = null;
  window.togglePickedDetail = function(lotNo) {"""

if OLD4 in content:
    content = content.replace(OLD4, NEW4, 1)
    print("PATCH 4 OK: new handlers", flush=True)
else:
    print("PATCH 4 FAIL", flush=True)
    sys.exit(1)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print(f"Done. {len(content):,} bytes.", flush=True)
