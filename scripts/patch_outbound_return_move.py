#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Outbound / Return / Move 탭을 V864-2 수준으로 업그레이드
"""
import sys

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"Size: {len(content):,}", flush=True)

# ═══════════════════════════════════════════════════════════════════════════
# PATCH 1: Outbound 탭 전면 개편
# ═══════════════════════════════════════════════════════════════════════════
OLD_OB_HTML = """  function loadOutboundPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="outbound">',
      '<div style="display:flex;align-items:center;gap:12px;padding:8px 0 12px">',
      '  <h2 style="margin:0">📤 출고 완료 (Sold / Outbound)</h2>',
      '  <button class="btn btn-secondary" onclick="renderPage(\\'outbound\\')" style="margin-left:auto">🔁 새로고침</button>',
      '</div>',
      '<div id="outbound-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '  <table class="data-table" id="outbound-table" style="display:none">',
      '  <thead><tr><th></th><th>#</th><th>LOT No</th><th>판매주문No</th><th>고객사</th><th>톤백수</th><th>중량(kg)</th><th>출고일</th></tr></thead>',
      '  <tbody id="outbound-tbody"></tbody>',
      '  </table>',
      '</div>',
      '<div class="empty" id="outbound-empty" style="display:none;padding:60px;text-align:center;color:var(--text-muted)">📭 출고 데이터 없음</div>',
      '<div id="outbound-detail-panel" style="display:none;margin-top:16px;border-top:2px solid var(--border);padding-top:16px">',
      '  <h3 id="outbound-detail-title" style="margin:0 0 12px 0">톤백 상세</h3>',
      '  <div id="outbound-detail-content"></div>',
      '</div>',
      '</section>'
    ].join('');

    apiGet('/api/q/sold-list').then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      document.getElementById('outbound-loading').style.display = 'none';
      if (!rows.length) {
        document.getElementById('outbound-empty').style.display = 'block';
        return;
      }
      var tbody = document.getElementById('outbound-tbody');
      if (tbody) tbody.innerHTML = rows.map(function(r, i){
        var lot = escapeHtml(r.lot_no||'');
        return '<tr class="outbound-summary-row" data-lot="'+lot+'" style="cursor:pointer" onclick="window.toggleOutboundDetail(\\''+lot+'\\')">' +
          '<td style="width:24px;text-align:center"><span class="outbound-expand-icon">▶</span></td>' +
          '<td class="mono-cell" style="color:var(--text-muted)">'+(i+1)+'</td>' +
          '<td class="mono-cell" style="color:var(--accent);font-weight:600">'+lot+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.sales_order_no||'-')+'</td>' +
          '<td>'+escapeHtml(r.customer||'-')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.tonbag_count||0)+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.total_kg!=null?fmtN(r.total_kg):'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.sold_date||'-')+'</td>' +
          '</tr>';
      }).join('');
      document.getElementById('outbound-table').style.display = '';
      dbgLog('📤','outbound-page','rows='+rows.length,'#4caf50');
    }).catch(function(e){
      if (_currentRoute !== route) return;
      document.getElementById('outbound-loading').style.display = 'none';
      var el = document.getElementById('outbound-empty');
      if (el) { el.textContent = '❌ 로드 실패: '+(e.message||String(e)); el.style.display = 'block'; }
      showToast('error', '출고 현황 로드 실패');
    });
  }"""

NEW_OB_HTML = """  var _obAllRows = [];  // 출고 전체 데이터 캐시

  function loadOutboundPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="outbound">',
      /* ── 제목 + 카운트 ── */
      '<div style="display:flex;align-items:center;gap:8px;padding:6px 0 8px;border-bottom:1px solid var(--panel-border);margin-bottom:8px">',
      '<h2 style="margin:0;font-size:16px">📤 출고완료(OUTBOUND) LOT 리스트</h2>',
      '<span id="ob-count-label" style="font-size:12px;color:var(--text-muted);margin-left:8px">0 LOT / 0건</span>',
      '<div style="margin-left:auto;font-size:12px">',
      '<button class="btn btn-ghost btn-sm" onclick="window.obToggleAllSale()">📋 전체 판매 보기</button>',
      '</div></div>',
      /* ── 날짜 필터 바 ── */
      '<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px;font-size:12px">',
      '<label style="font-weight:600;color:var(--text-muted)">시작일</label>',
      '<input id="ob-date-from" type="date" style="font-size:12px;padding:2px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)">',
      '<span style="color:var(--text-muted)">~</span>',
      '<label style="font-weight:600;color:var(--text-muted)">종료일</label>',
      '<input id="ob-date-to" type="date" style="font-size:12px;padding:2px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)">',
      '<button class="btn btn-primary btn-sm" onclick="window.obApplyFilter()">🔍 조회</button>',
      '<button class="btn btn-ghost btn-sm" onclick="window.obClearFilter()">✕ 초기화</button>',
      '</div>',
      /* ── 액션 툴바 ── */
      '<div style="display:flex;gap:6px;align-items:center;padding:4px 0 8px;flex-wrap:wrap">',
      '<button class="btn btn-secondary btn-sm" onclick="renderPage(\\'outbound\\')">🔁 새로고침</button>',
      '<button class="btn btn-warning btn-sm" onclick="window.obCancelOutbound()" title="선택 LOT → PICKED (판매화물 결정 단계로)">↩ 출고 취소 (→ 판매화물 결정)</button>',
      '<button class="btn btn-ghost btn-sm" onclick="window.obReturnConfirm()" title="선택 LOT → AVAILABLE (반품 처리)">🔄 반품 확정 (→ AVAILABLE)</button>',
      /* ── 합계바 ── */
      '<div style="margin-left:auto;font-size:12px;color:var(--text-muted);padding:2px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:4px">',
      'Σ 건수: <b id="ob-sum-count">0</b> &nbsp;|&nbsp; 중량(kg): <b id="ob-sum-kg">0</b>',
      '</div></div>',
      '<div id="outbound-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '<table class="data-table" id="outbound-table" style="display:none">',
      '<thead><tr>',
      '<th style="width:32px;text-align:center"><input type="checkbox" id="ob-chk-all" onclick="window.obToggleAll(this.checked)"></th>',
      '<th style="text-align:center">No.</th>',
      '<th style="text-align:center">LOT NO</th>',
      '<th style="text-align:center">판매주문No</th>',
      '<th style="text-align:center">고객사</th>',
      '<th style="text-align:center">톤백수</th>',
      '<th style="text-align:center">중량(kg)</th>',
      '<th style="text-align:center">판매일</th>',
      '</tr></thead>',
      '<tbody id="outbound-tbody"></tbody>',
      '</table>',
      '</div>',
      '<div class="empty" id="outbound-empty" style="display:none;padding:60px;text-align:center;color:var(--text-muted)">📭 출고 데이터 없음</div>',
      '<div id="outbound-detail-panel" style="display:none;margin-top:16px;border-top:2px solid var(--border);padding-top:16px">',
      '<h3 id="outbound-detail-title" style="margin:0 0 12px 0">톤백 상세</h3>',
      '<div id="outbound-detail-content"></div>',
      '</div>',
      '</section>'
    ].join('');

    apiGet('/api/q/sold-list').then(function(res){
      if (_currentRoute !== route) return;
      _obAllRows = extractRows(res);
      document.getElementById('outbound-loading').style.display = 'none';
      window.obRenderRows(_obAllRows);
      dbgLog('📤','outbound-page','rows='+_obAllRows.length,'#4caf50');
    }).catch(function(e){
      if (_currentRoute !== route) return;
      document.getElementById('outbound-loading').style.display = 'none';
      var el = document.getElementById('outbound-empty');
      if (el) { el.textContent = '❌ 로드 실패: '+(e.message||String(e)); el.style.display = 'block'; }
      showToast('error', '출고 현황 로드 실패');
    });
  }

  window.obRenderRows = function(rows) {
    var totalCount = 0, totalKg = 0;
    var tbody = document.getElementById('outbound-tbody');
    var empty  = document.getElementById('outbound-empty');
    var table  = document.getElementById('outbound-table');
    if (!tbody) return;
    if (!rows.length) {
      table.style.display = 'none';
      empty.style.display = 'block';
      document.getElementById('ob-count-label').textContent = '0 LOT / 0건';
      document.getElementById('ob-sum-count').textContent = '0';
      document.getElementById('ob-sum-kg').textContent = '0';
      return;
    }
    empty.style.display = 'none';
    tbody.innerHTML = rows.map(function(r, i){
      var lot = escapeHtml(r.lot_no||'');
      totalCount += (r.tonbag_count||0);
      totalKg += (r.total_kg||0);
      return '<tr class="outbound-summary-row" data-lot="'+lot+'">' +
        '<td style="text-align:center;width:32px"><input type="checkbox" class="ob-row-chk" onclick="event.stopPropagation()" data-lot="'+lot+'"></td>' +
        '<td style="text-align:center;color:var(--text-muted);font-size:11px">'+(i+1)+'</td>' +
        '<td class="mono-cell" style="text-align:center;color:var(--accent);font-weight:600;cursor:pointer" onclick="window.toggleOutboundDetail(\\''+lot+'\\')">'+lot+' <span class="outbound-expand-icon" style="font-size:10px">▶</span></td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml(r.sales_order_no||'-')+'</td>' +
        '<td style="text-align:center">'+escapeHtml(r.customer||'-')+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+(r.tonbag_count||0)+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+(r.total_kg!=null?fmtN(r.total_kg):'-')+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml((r.sold_date||'-').slice(0,10))+'</td>' +
        '</tr>';
    }).join('');
    table.style.display = '';
    document.getElementById('ob-count-label').textContent = rows.length + ' LOT / ' + totalCount + '건';
    document.getElementById('ob-sum-count').textContent = totalCount;
    document.getElementById('ob-sum-kg').textContent = fmtN(totalKg);
  };

  window.obApplyFilter = function() {
    var from = (document.getElementById('ob-date-from')||{}).value || '';
    var to   = (document.getElementById('ob-date-to')  ||{}).value || '';
    var filtered = _obAllRows.filter(function(r) {
      var d = (r.sold_date||'').slice(0,10);
      if (from && d < from) return false;
      if (to   && d > to)   return false;
      return true;
    });
    window.obRenderRows(filtered);
  };

  window.obClearFilter = function() {
    var f = document.getElementById('ob-date-from'); if (f) f.value = '';
    var t = document.getElementById('ob-date-to');   if (t) t.value = '';
    window.obRenderRows(_obAllRows);
  };

  window.obToggleAll = function(checked) {
    document.querySelectorAll('.ob-row-chk').forEach(function(c){ c.checked = checked; });
  };

  window.obCancelOutbound = function() {
    var lots = Array.from(document.querySelectorAll('.ob-row-chk:checked')).map(function(c){ return c.dataset.lot; });
    if (!lots.length) { showToast('warning','취소할 LOT을 선택하세요'); return; }
    if (!confirm(lots.length + '개 LOT 출고 취소(→ PICKED)하겠습니까?')) return;
    apiPost('/api/allocation/revert-step', {step:'outbound_to_picked', lot_nos: lots})
      .then(function(r){ showToast('success',(r.reverted||lots.length)+' LOT 취소 완료'); renderPage('outbound'); })
      .catch(function(e){ showToast('error','실패: '+(e.message||String(e))); });
  };

  window.obReturnConfirm = function() {
    var lots = Array.from(document.querySelectorAll('.ob-row-chk:checked')).map(function(c){ return c.dataset.lot; });
    if (!lots.length) { showToast('warning','반품 처리할 LOT을 선택하세요'); return; }
    if (!confirm(lots.length + '개 LOT을 반품(→ AVAILABLE) 처리하겠습니까?')) return;
    apiPost('/api/allocation/revert-step', {step:'outbound_to_available', lot_nos: lots})
      .then(function(r){ showToast('success',(r.reverted||lots.length)+' LOT 반품 완료'); renderPage('outbound'); })
      .catch(function(e){ showToast('error','실패: '+(e.message||String(e))); });
  };

  window.obToggleAllSale = function() {
    var rows = document.querySelectorAll('.outbound-summary-row');
    rows.forEach(function(tr){ var lot = tr.dataset.lot; if (lot) window.toggleOutboundDetail(lot); });
  };"""

if OLD_OB_HTML in content:
    content = content.replace(OLD_OB_HTML, NEW_OB_HTML, 1)
    print("PATCH 1 OK: Outbound redesign", flush=True)
else:
    print("PATCH 1 FAIL: Outbound pattern not found", flush=True)
    idx = content.find("loadOutboundPage")
    print("  loadOutboundPage at:", idx, flush=True)
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════
# PATCH 2: Return 탭 전면 개편
# ═══════════════════════════════════════════════════════════════════════════
OLD_RET = """  function loadReturnPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="return">',
      '<h2>Return - Re-inbound</h2>',
      '<div class="toolbar-mini"><button class="btn btn-secondary" onclick="renderPage(\\'return\\')">Refresh</button></div>',
      '<div id="return-loading" style="padding:40px;text-align:center">Loading...</div>',
      '<table class="data-table" id="return-table" style="display:none">',
      '<thead><tr><th>LOT</th><th>Product</th><th>Qty</th><th>Date</th><th>Reason</th></tr></thead>',
      '<tbody id="return-tbody"></tbody></table>',
      '<div class="empty" id="return-empty" style="display:none">No return data</div>',
      '</section>'
    ].join('');
    /* return-stats는 통계 구조(by_reason/monthly_trend)라 items 없음 → inventory?status=RETURN 직접 조회 */
    apiGet('/api/inventory?status=RETURN').then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      renderReturnRows(rows, route);
    }).catch(function(){
      if (_currentRoute !== route) return;
      document.getElementById('return-loading').style.display = 'none';
      document.getElementById('return-empty').style.display = 'block';
    });
  }

  function renderReturnRows(rows, route) {
    if (_currentRoute !== route) return;
    document.getElementById('return-loading').style.display = 'none';
    if (!rows.length) { document.getElementById('return-empty').style.display='block'; return; }
    var tbody = document.getElementById('return-tbody');
    if (tbody) tbody.innerHTML = rows.map(function(r){
      return '<tr><td>'+escapeHtml(r.lot||'')+'</td><td>'+escapeHtml(r.product||'')+'</td><td>'+(r.bags||r.qty||'')+'</td><td>'+escapeHtml(r.date||'')+'</td><td>'+escapeHtml(r.reason||'')+'</td></tr>';
    }).join('');
    document.getElementById('return-table').style.display = '';
  }"""

NEW_RET = """  var _retActiveTab = 'reinbound';  // 현재 활성 Return 서브탭

  function loadReturnPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="return">',
      /* ── 제목 + 서브탭 ── */
      '<div style="display:flex;align-items:center;gap:0;padding:6px 0 0;border-bottom:2px solid var(--panel-border);margin-bottom:12px">',
      '<h2 style="margin:0 16px 0 0;font-size:16px">🔄 Return Management</h2>',
      '<button class="btn btn-ghost btn-sm" id="ret-tab-reinbound" onclick="window.retSwitchTab(\\'reinbound\\')" style="border-radius:4px 4px 0 0;border-bottom:2px solid var(--accent);color:var(--accent)">📥 Return Inbound (Excel)</button>',
      '<button class="btn btn-ghost btn-sm" id="ret-tab-list" onclick="window.retSwitchTab(\\'list\\')" style="border-radius:4px 4px 0 0">📋 Return (Re-inbound)</button>',
      '<button class="btn btn-ghost btn-sm" id="ret-tab-stats" onclick="window.retSwitchTab(\\'stats\\')" style="border-radius:4px 4px 0 0">📊 Return Statistics</button>',
      '<button class="btn btn-secondary btn-sm" onclick="renderPage(\\'return\\')" style="margin-left:auto">🔁 Refresh</button>',
      '</div>',
      /* ── 통계 카드 ── */
      '<div style="display:flex;gap:12px;margin-bottom:12px">',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Total Returns</div><div id="ret-stat-total" style="font-size:24px;font-weight:700;margin-top:4px">—</div></div>',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Pending Review</div><div id="ret-stat-pending" style="font-size:24px;font-weight:700;margin-top:4px">—</div></div>',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Completed</div><div id="ret-stat-complete" style="font-size:24px;font-weight:700;margin-top:4px">—</div></div>',
      '</div>',
      /* ── Return Inbound (Excel) 패널 ── */
      '<div id="ret-panel-reinbound">',
      '<div style="padding:16px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:12px">',
      '<p style="font-size:13px;color:var(--text-muted);margin:0 0 8px 0">반품 데이터를 Excel 파일로 업로드하거나 DB에서 반품 상태 항목을 조회합니다.</p>',
      '<div style="display:flex;gap:8px;flex-wrap:wrap">',
      '<button class="btn btn-primary btn-sm" onclick="window.retUploadExcel()">📂 Excel 업로드</button>',
      '<button class="btn btn-ghost btn-sm" onclick="window.retExportExcel()">📊 Excel 내보내기</button>',
      '</div></div>',
      '</div>',
      /* ── Re-inbound 목록 패널 ── */
      '<div id="ret-panel-list">',
      '<div id="return-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '<table class="data-table" id="return-table" style="display:none">',
      '<thead><tr>',
      '<th style="text-align:center">순번</th>',
      '<th style="text-align:center">LOT NO</th>',
      '<th style="text-align:center">Product</th>',
      '<th style="text-align:center">Return Date</th>',
      '<th style="text-align:center">Qty (kg)</th>',
      '<th style="text-align:center">Reason</th>',
      '<th style="text-align:center">Status</th>',
      '</tr></thead>',
      '<tbody id="return-tbody"></tbody>',
      '</table>',
      '</div>',
      '<div class="empty" id="return-empty" style="display:none;padding:60px;text-align:center">📭 반품 데이터 없음</div>',
      '</div>',
      /* ── Statistics 패널 ── */
      '<div id="ret-panel-stats" style="display:none">',
      '<div id="ret-stats-content" style="padding:20px;color:var(--text-muted)">통계 데이터 로딩 중...</div>',
      '</div>',
      '</section>'
    ].join('');

    _retActiveTab = 'reinbound';
    window.retSwitchTab('reinbound');

    apiGet('/api/inventory?status=RETURN').then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      renderReturnRows(rows, route);
      /* 통계 카드 업데이트 */
      document.getElementById('ret-stat-total').textContent   = rows.length;
      document.getElementById('ret-stat-pending').textContent = rows.filter(function(r){ return !r.return_reviewed; }).length;
      document.getElementById('ret-stat-complete').textContent= rows.filter(function(r){ return r.return_reviewed; }).length;
    }).catch(function(){
      if (_currentRoute !== route) return;
      document.getElementById('return-loading').style.display = 'none';
      document.getElementById('return-empty').style.display = 'block';
    });
  }

  window.retSwitchTab = function(tab) {
    _retActiveTab = tab;
    var panels = ['reinbound','list','stats'];
    panels.forEach(function(p) {
      var panel = document.getElementById('ret-panel-' + p);
      var btn   = document.getElementById('ret-tab-' + p);
      if (!panel || !btn) return;
      if (p === tab) {
        panel.style.display = '';
        btn.style.borderBottom = '2px solid var(--accent)';
        btn.style.color = 'var(--accent)';
      } else {
        panel.style.display = 'none';
        btn.style.borderBottom = '';
        btn.style.color = '';
      }
    });
  };

  window.retUploadExcel = function() {
    showToast('info', 'Excel 업로드 기능은 준비 중입니다');
  };
  window.retExportExcel = function() {
    var a = document.createElement('a');
    a.href = '/api/allocation/export-excel?status=RETURN';
    a.download = 'return_list.xlsx'; a.click();
  };

  function renderReturnRows(rows, route) {
    if (_currentRoute !== route) return;
    document.getElementById('return-loading').style.display = 'none';
    if (!rows.length) { document.getElementById('return-empty').style.display='block'; return; }
    var tbody = document.getElementById('return-tbody');
    if (tbody) tbody.innerHTML = rows.map(function(r, i){
      var statusColor = '#f59e0b';
      return '<tr>' +
        '<td style="text-align:center;color:var(--text-muted);font-size:11px">'+(i+1)+'</td>' +
        '<td class="mono-cell" style="text-align:center;color:var(--accent);font-weight:600">'+escapeHtml(r.lot||r.lot_no||'')+'</td>' +
        '<td style="text-align:center">'+escapeHtml(r.product||'-')+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml((r.return_date||r.updated_at||r.date||'').slice(0,10))+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+(r.balance!=null?fmtN(Number(r.balance)*1000):(r.qty||r.bags||'-'))+'</td>' +
        '<td style="text-align:center">'+escapeHtml(r.return_reason||r.reason||'-')+'</td>' +
        '<td style="text-align:center"><span class="tag" style="color:'+statusColor+'">'+escapeHtml(r.status||'RETURN')+'</span></td>' +
        '</tr>';
    }).join('');
    document.getElementById('return-table').style.display = '';
  }"""

if OLD_RET in content:
    content = content.replace(OLD_RET, NEW_RET, 1)
    print("PATCH 2 OK: Return redesign", flush=True)
else:
    print("PATCH 2 FAIL", flush=True)
    idx = content.find("loadReturnPage")
    print("  loadReturnPage at:", idx, flush=True)
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════
# PATCH 3: Move 탭 전면 개편
# ═══════════════════════════════════════════════════════════════════════════
# loadMovePage 함수의 c.innerHTML 블록을 교체
# 먼저 정확한 위치 찾기
move_start = content.find("  function loadMovePage() {")
if move_start < 0:
    print("PATCH 3: loadMovePage not found", flush=True)
    sys.exit(1)

# executeMove 함수 바로 전까지를 교체 범위로 잡기
move_end = content.find("  window.executeMove = function() {", move_start)
if move_end < 0:
    print("PATCH 3: executeMove anchor not found", flush=True)
    sys.exit(1)

OLD_MOVE_BLOCK = content[move_start:move_end]
print(f"PATCH 3: Move block found ({len(OLD_MOVE_BLOCK)} chars)", flush=True)
print("  first 100:", repr(OLD_MOVE_BLOCK[:100]), flush=True)

NEW_MOVE_BLOCK = """  function loadMovePage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="move">',
      /* ── 제목 ── */
      '<div style="display:flex;align-items:center;gap:8px;padding:6px 0 8px;border-bottom:1px solid var(--panel-border);margin-bottom:10px">',
      '<h2 style="margin:0;font-size:16px">🔀 Move Management</h2>',
      '<button class="btn btn-secondary btn-sm" onclick="renderPage(\\'move\\')" style="margin-left:auto">🔁 Refresh</button>',
      '</div>',
      /* ── Scan to Move ── */
      '<div class="card" style="padding:14px;margin-bottom:12px">',
      '<div style="font-weight:700;font-size:13px;margin-bottom:10px">⚡ Scan to Move</div>',
      '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:8px">',
      '<div style="display:flex;align-items:center;gap:6px">',
      '<label style="font-size:12px;white-space:nowrap;min-width:90px">Tonbag UID:</label>',
      '<input id="move-barcode" class="input" placeholder="바코드 스캔 또는 입력" style="width:200px;font-size:12px;padding:3px 8px">',
      '<button class="btn btn-ghost btn-sm" onclick="window.moveLookup()">🔍 Lookup</button>',
      '<span id="move-current-loc" style="font-size:11px;color:var(--text-muted)">Current: —</span>',
      '</div>',
      '</div>',
      '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:8px">',
      '<div style="display:flex;align-items:center;gap:6px">',
      '<label style="font-size:12px;white-space:nowrap;min-width:90px">To Location:</label>',
      '<input id="move-dest" class="input" placeholder="예: A-3-2" style="width:200px;font-size:12px;padding:3px 8px">',
      '</div>',
      '<button class="btn btn-primary btn-sm" onclick="window.executeMove()">✅ Move</button>',
      '<button class="btn btn-ghost btn-sm" onclick="window.moveClear()">🗑 Clear</button>',
      '<label style="font-size:12px;display:flex;align-items:center;gap:4px">',
      '<input type="checkbox" id="move-continuous"> 연속 스캔',
      '</label>',
      '</div>',
      '<div style="font-size:11px;color:var(--text-muted)">톤백 바코드를 스캔하거나 UID를 입력하세요.</div>',
      '</div>',
      /* ── 보조 툴바 ── */
      '<div style="display:flex;gap:6px;align-items:center;padding:4px 0 8px;flex-wrap:wrap">',
      '<button class="btn btn-ghost btn-sm" onclick="showToast(\\'info\\',\\'Excel 업로드 준비 중\\')">📂 Location Upload (Excel)</button>',
      '<button class="btn btn-ghost btn-sm" onclick="window.loadMoveApprovals()">✅ Move Approval</button>',
      '</div>',
      /* ── 통계 카드 ── */
      '<div style="display:flex;gap:12px;margin-bottom:12px">',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Pending</div><div id="move-stat-pending" style="font-size:22px;font-weight:700;margin-top:4px">—</div></div>',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Approved</div><div id="move-stat-approved" style="font-size:22px;font-weight:700;margin-top:4px">—</div></div>',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Completed</div><div id="move-stat-complete" style="font-size:22px;font-weight:700;margin-top:4px">—</div></div>',
      '</div>',
      /* ── 필터 ── */
      '<div style="display:flex;gap:8px;align-items:center;font-size:12px;margin-bottom:6px">',
      '<label>Status:</label>',
      '<select id="move-status-filter" style="font-size:12px;padding:2px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)" onchange="window.moveApplyFilter()">',
      '<option value="">ALL</option>',
      '<option value="MOVE">MOVE</option>',
      '<option value="APPROVED">APPROVED</option>',
      '<option value="COMPLETED">COMPLETED</option>',
      '</select>',
      '<label>LOT:</label>',
      '<input id="move-lot-filter" type="text" style="font-size:12px;padding:2px 8px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg);width:140px" oninput="window.moveApplyFilter()">',
      '<button class="btn btn-ghost btn-xs" onclick="window.moveFilterClear()">🔍</button>',
      '</div>',
      /* ── Move History 테이블 ── */
      '<div style="font-weight:700;font-size:13px;margin-bottom:6px">📋 Move History</div>',
      '<div id="move-loading" style="padding:20px;text-align:center;color:var(--text-muted)">⏳ 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '<table class="data-table" id="move-table" style="display:none">',
      '<thead><tr>',
      '<th style="text-align:center">순번</th>',
      '<th style="text-align:center">Time</th>',
      '<th style="text-align:center">LOT NO</th>',
      '<th style="text-align:center">Tonbag No</th>',
      '<th style="text-align:center">From</th>',
      '<th style="text-align:center">To</th>',
      '<th style="text-align:center">Status</th>',
      '<th style="text-align:center">Operator</th>',
      '</tr></thead>',
      '<tbody id="move-tbody"></tbody>',
      '</table>',
      '</div>',
      '<div class="empty" id="move-empty" style="display:none;padding:40px;text-align:center">📭 이동 이력 없음</div>',
      '</section>'
    ].join('');

    var _moveAllRows = [];

    apiGet('/api/q/movement-history').then(function(res){
      if (_currentRoute !== route) return;
      _moveAllRows = extractRows(res);
      document.getElementById('move-loading').style.display = 'none';
      /* 통계 카드 */
      var pending   = _moveAllRows.filter(function(r){ return (r.status||'').toUpperCase()==='MOVE'; }).length;
      var approved  = _moveAllRows.filter(function(r){ return (r.status||'').toUpperCase()==='APPROVED'; }).length;
      var completed = _moveAllRows.filter(function(r){ return (r.status||'').toUpperCase()==='COMPLETED'; }).length;
      document.getElementById('move-stat-pending').textContent  = pending;
      document.getElementById('move-stat-approved').textContent = approved;
      document.getElementById('move-stat-complete').textContent = completed;
      window._moveAllRows = _moveAllRows;
      window.moveRenderHistory(_moveAllRows);
    }).catch(function(){
      if (_currentRoute !== route) return;
      document.getElementById('move-loading').style.display = 'none';
      document.getElementById('move-empty').style.display = 'block';
    });
  }

  window.moveRenderHistory = function(rows) {
    var tbody = document.getElementById('move-tbody');
    var table = document.getElementById('move-table');
    var empty = document.getElementById('move-empty');
    if (!tbody) return;
    if (!rows.length) {
      if (table) table.style.display = 'none';
      if (empty) empty.style.display = 'block';
      return;
    }
    if (empty) empty.style.display = 'none';
    tbody.innerHTML = rows.map(function(r, i){
      var qtyMT = r.qty_mt != null ? fmtN(r.qty_mt) : (r.qty_kg != null ? fmtN(r.qty_kg/1000) : '-');
      return '<tr>' +
        '<td style="text-align:center;color:var(--text-muted);font-size:11px">'+(i+1)+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml(r.movement_date||r.moved_at||r.date||'')+'</td>' +
        '<td class="mono-cell" style="text-align:center;color:var(--accent)">'+escapeHtml(r.lot_no||r.sub_lt||r.barcode||'')+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml(r.tonbag_id||r.sub_lt||'-')+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml(r.from_location||'-')+'</td>' +
        '<td class="mono-cell" style="text-align:center;color:var(--accent)">'+escapeHtml(r.to_location||'-')+'</td>' +
        '<td style="text-align:center"><span class="tag">'+escapeHtml(r.status||r.movement_type||'-')+'</span></td>' +
        '<td style="text-align:center">'+escapeHtml(r.actor||r.moved_by||'system')+'</td></tr>';
    }).join('');
    if (table) table.style.display = '';
  };

  window.moveApplyFilter = function() {
    var statusVal = ((document.getElementById('move-status-filter')||{}).value||'').toUpperCase();
    var lotVal    = ((document.getElementById('move-lot-filter')||{}).value||'').toLowerCase();
    var rows = (window._moveAllRows||[]).filter(function(r){
      var status = (r.status||r.movement_type||'').toUpperCase();
      var lot    = (r.lot_no||r.sub_lt||'').toLowerCase();
      return (!statusVal || status === statusVal) && (!lotVal || lot.includes(lotVal));
    });
    window.moveRenderHistory(rows);
  };

  window.moveFilterClear = function() {
    var s = document.getElementById('move-status-filter'); if (s) s.value = '';
    var l = document.getElementById('move-lot-filter');    if (l) l.value = '';
    window.moveRenderHistory(window._moveAllRows||[]);
  };

  window.moveLookup = function() {
    var uid = ((document.getElementById('move-barcode')||{}).value||'').trim();
    if (!uid) { showToast('warning','UID를 입력하세요'); return; }
    apiGet('/api/tonbags?sub_lt='+encodeURIComponent(uid)).then(function(res){
      var rows = extractRows(res);
      if (!rows.length) { showToast('warning','해당 톤백을 찾을 수 없습니다'); return; }
      var loc = rows[0].location||'-';
      var el = document.getElementById('move-current-loc');
      if (el) el.textContent = 'Current: ' + loc;
      showToast('info', uid + ' → 현재위치: ' + loc);
    }).catch(function(e){ showToast('error','조회 실패: '+(e.message||'')); });
  };

  window.moveClear = function() {
    var b = document.getElementById('move-barcode'); if (b) b.value = '';
    var d = document.getElementById('move-dest');    if (d) d.value = '';
    var el = document.getElementById('move-current-loc'); if (el) el.textContent = 'Current: —';
  };

  window.loadMoveApprovals = function() {
    showToast('info', 'Move Approval 기능 준비 중');
  };

"""

content = content[:move_start] + NEW_MOVE_BLOCK + content[move_end:]
print("PATCH 3 OK: Move redesign", flush=True)

# ═══════════════════════════════════════════════════════════════════════════
# Write
# ═══════════════════════════════════════════════════════════════════════════
with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print(f"Done. {len(content):,} bytes.", flush=True)
