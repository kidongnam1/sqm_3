#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Picked 탭 데이터 행 렌더링 교체 + 새 핸들러 추가
"""
import sys

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"Size: {len(content):,}", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 3: Picked 행 렌더링 교체
# ─────────────────────────────────────────────────────────────────────────────
# 정확한 old 문자열 (파일에서 복사)
OLD3 = """      if (tbody) tbody.innerHTML = rows.map(function(r){
        var lot = escapeHtml(r.lot_no||'');
        return '<tr class="picked-summary-row" data-lot="'+lot+'" style="cursor:pointer" onclick="window.togglePickedDetail(\\''+lot+'\\')">'+
          '<td style="width:24px;text-align:center"><span class="picked-expand-icon">▶</span></td>' +
          '<td class="mono-cell" style="color:var(--accent);font-weight:600">'+lot+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.picking_no||'')+'</td>' +
          '<td>'+escapeHtml(r.customer||r.picked_to||'')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.tonbag_count||0)+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.total_kg!=null?fmtN(r.total_kg):'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.picking_date||'')+'</td>' +
          '</tr>';
      }).join('');
      document.getElementById('picked-table').style.display = '';"""

NEW3 = """      var totalCount = 0, totalKg = 0;
      if (tbody) tbody.innerHTML = rows.map(function(r, idx){
        var lot = escapeHtml(r.lot_no||'');
        totalCount += (r.tonbag_count||0);
        totalKg += (r.total_kg||0);
        return '<tr class="picked-summary-row" data-lot="'+lot+'">' +
          '<td style="text-align:center;width:32px"><input type="checkbox" class="picked-row-chk" onclick="event.stopPropagation()" data-lot="'+lot+'"></td>' +
          '<td style="text-align:center;color:var(--text-muted);font-size:11px">'+(idx+1)+'</td>' +
          '<td class="mono-cell" style="text-align:center;color:var(--accent);font-weight:600;cursor:pointer" onclick="window.togglePickedDetail(\\''+lot+'\\')">'+lot+' <span class="picked-expand-icon" style="font-size:10px">▶</span></td>' +
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

if OLD3 in content:
    content = content.replace(OLD3, NEW3, 1)
    print("PATCH 3 OK: Picked rows", flush=True)
else:
    print("PATCH 3 FAIL - trying line-by-line search...", flush=True)
    # 디버깅
    search = "if (tbody) tbody.innerHTML = rows.map"
    idx = content.find(search)
    while idx >= 0:
        snippet = content[idx:idx+600]
        print(f"  Found at {idx}:", repr(snippet[:200]), flush=True)
        idx = content.find(search, idx+1)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 4: Picked 탭 새 핸들러 함수들 삽입
# ─────────────────────────────────────────────────────────────────────────────
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
    print("PATCH 4 OK: Picked new handlers", flush=True)
else:
    print("PATCH 4 FAIL: anchor not found", flush=True)
    sys.exit(1)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print(f"Done. {len(content):,} bytes written.", flush=True)
