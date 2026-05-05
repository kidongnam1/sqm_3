/* SQM Inventory — sqm-inventory.js (Inventory — 재고목록·톤백모달) */
(function () {
  'use strict';
  /* ─── sqm-core.js 공유 함수 로컬 앨리어스 ─────────────────────────
     sqm-core.js 가 먼저 로드된 뒤 window.* 에 할당된 함수들을
     this IIFE 내부 변수로 re-bind. 직접 호출 패턴 유지. */
  var showToast     = function() { return window.showToast.apply(window, arguments); };
  var apiCall       = function() { return window.apiCall.apply(window, arguments); };
  var apiGet        = function() { return window.apiGet.apply(window, arguments); };
  var apiPost       = function() { return window.apiPost.apply(window, arguments); };
  var renderPage    = function() { return window.renderPage.apply(window, arguments); };
  var closeAllMenus = function() { return window.closeAllMenus.apply(window, arguments); };
  var getStore      = function() { return window.getStore.apply(window, arguments); };
  var escapeHtml    = function() { return window.escapeHtml.apply(window, arguments); };
  var extractRows               = function() { return window.extractRows.apply(window, arguments); };
  var fmtN                      = function() { return window.fmtN.apply(window, arguments); };
  /* ──────────────────────────────────────────────────────────────── */

  function loadInventoryPage() {
    var route = window.getCurrentRoute();
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = '<div style="padding:40px;text-align:center">Loading inventory...</div>';
    apiGet('/api/inventory').then(function(res){
      if (window.getCurrentRoute() !== route) return;
      var rows = extractRows(res);
      if (!rows.length) {
        c.innerHTML = '<div class="empty" style="padding:60px;text-align:center">No inventory data</div>';
        return;
      }
      var sumBal = 0;
      var sumNet = 0;
      var sumIni = 0;
      var sumOb = 0;
      var sumUnsold = 0;
      var sumSold = 0;
      var sumAvailMt = 0;
      var sumRsvMt = 0;
      rows.forEach(function(r){
        if (r.balance != null && !isNaN(Number(r.balance))) {
          var bal = Number(r.balance);
          sumBal += bal;
          var st = String(r.status || '').toUpperCase();
          if (st === 'SOLD' || st === 'OUTBOUND' || st === 'SHIPPED' || st === 'CONFIRMED') sumSold += bal;
          else sumUnsold += bal;
        }
        if (r.net != null && !isNaN(Number(r.net))) sumNet += Number(r.net);
        if (r.initial_weight != null && !isNaN(Number(r.initial_weight))) sumIni += Number(r.initial_weight);
        if (r.outbound_weight != null && !isNaN(Number(r.outbound_weight))) sumOb += Number(r.outbound_weight);
        if (r.avail_mt != null && !isNaN(Number(r.avail_mt))) sumAvailMt += Number(r.avail_mt);
        if (r.reserved_mt != null && !isNaN(Number(r.reserved_mt))) sumRsvMt += Number(r.reserved_mt);
      });
      var html = '<section class="page" data-page="inventory">' +
        '<div style="display:flex;align-items:center;gap:12px;padding:4px 0 10px">' +
        '<h2 style="margin:0">📦 재고 목록 (Inventory)</h2>' +
        '<span style="font-size:12px;color:var(--text-muted)" id="inv-count-label">'+rows.length+' LOTs</span>' +
        '<button class="btn btn-secondary" onclick="renderPage(\'inventory\')" style="margin-left:auto">🔁 새로고침</button>' +
        '</div>' +
        /* ── 필터 / 검색 바 ── */
        '<div id="inv-filter-bar" style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px">' +
        '  <label style="font-size:12px;white-space:nowrap">상태:</label>' +
        '  <select id="inv-status-filter" style="font-size:12px;padding:2px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)" onchange="window.invApplyFilter()">' +
        '    <option value="">전체</option>' +
        '    <option value="AVAILABLE">AVAILABLE</option>' +
        '    <option value="RESERVED">RESERVED</option>' +
        '    <option value="PICKED">PICKED</option>' +
        '    <option value="RETURN">RETURN</option>' +
        '  </select>' +
        '  <input id="inv-search-input" type="text" placeholder="LOT / SAP / BL / Product 검색..." ' +
        '    style="flex:1;min-width:180px;font-size:12px;padding:2px 8px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)" ' +
        '    oninput="window.invApplyFilter()">' +
        '  <button class="btn btn-ghost" style="font-size:12px" onclick="window.invClearFilter()">✕ 초기화</button>' +
        '</div>' +
        '<p style="font-size:12px;color:var(--text-muted);margin:0 0 8px 0">' +
        '목록 합계 · NET(MT): <b style="color:var(--accent)">'+fmtN(sumNet)+'</b> · Balance(MT): <b>'+fmtN(sumBal)+'</b> · 미판매(MT): <b style="color:#22c55e">'+fmtN(sumUnsold)+'</b> · 판매완료(MT): <b style="color:#ef4444;font-weight:700">'+fmtN(sumSold)+'</b> · 차이(순−현, 샘플 등): <b style="color:#f59e0b">'+fmtN(sumNet - sumBal)+'</b>' +
        '</p>' +
        '<div style="overflow-x:auto"><table class="data-table"><thead><tr>' +
        '<th>#</th><th style="text-align:center !important">LOT</th><th style="width:32px;text-align:center">+</th><th>SAP</th><th>BL</th><th>Product</th>' +
        '<th>Status</th><th>Balance(MT)</th><th>Avail/Rsv(MT)</th><th>NET(MT)</th><th>Container</th>' +
        '<th>MXBG</th><th>Avail</th><th>Invoice</th>' +
        '<th>Ship</th><th>Arrival</th><th>Con Return</th><th>Free</th>' +
        '<th>WH</th><th>Customs</th><th>Inbound(MT)</th><th>Outbound(MT)</th><th>Location</th><th></th>' +
        '</tr></thead><tbody>';
      html += rows.map(function(r, i){
        var lotKey = escapeHtml(r.lot||'');
        var parentContainer = escapeHtml(r.parent_container || r.container || '-');
        var hasSample = (r.sample_bags > 0);
        var sampleRow = '';
        if (hasSample) {
          sampleRow =
            '<tr style="background:rgba(234,179,8,0.08);border-left:3px solid #eab308">' +
            '<td class="mono-cell" style="color:#eab308;font-size:15px;text-align:center;padding:6px 10px;line-height:1.2">🔬</td>' +
            '<td class="mono-cell" style="color:#eab308;font-size:15px;font-weight:700;text-align:left;padding:6px 10px;line-height:1.2">'+lotKey+'(SP)</td>' +
            '<td class="mono-cell" style="color:#94a3b8;font-size:15px;padding:6px 10px;line-height:1.2">'+escapeHtml(r.sap||'')+'</td>' +
            '<td class="mono-cell" style="color:#94a3b8;font-size:15px;padding:6px 10px;line-height:1.2">'+escapeHtml(r.bl||'')+'</td>' +
            '<td><span class="tag" style="background:rgba(234,179,8,0.2);color:#eab308">'+escapeHtml(r.product||'')+'</span></td>' +
            '<td style="font-size:15px;color:#eab308;font-weight:600;padding:6px 10px;line-height:1.2">SAMPLE</td>' +
            '<td class="mono-cell" style="text-align:right;color:#eab308;font-weight:600;padding:6px 10px;line-height:1.2">'+fmtN(r.sample_weight_mt||0)+'</td>' +
            '<td class="mono-cell" style="text-align:right;color:#eab308;padding:6px 10px;line-height:1.2">'+fmtN(r.sample_weight_mt||0)+'</td>' +
            '<td class="mono-cell" style="text-align:right;color:#eab308;padding:6px 10px;line-height:1.2">'+fmtN(r.sample_weight_mt||0)+'</td>' +
            '<td class="mono-cell" style="font-size:15px;color:#94a3b8;padding:6px 10px;line-height:1.2">'+parentContainer+'</td>' +
            '<td class="mono-cell" style="text-align:center;color:#eab308;font-weight:700;padding:6px 10px;line-height:1.2">'+r.sample_bags+'</td>' +
            '<td class="mono-cell" style="text-align:center;color:#eab308;font-weight:700;padding:6px 10px;line-height:1.2">'+r.sample_bags+'</td>' +
            '<td class="mono-cell" style="font-size:15px;color:#94a3b8;padding:6px 10px;line-height:1.2">'+escapeHtml(r.invoice_no||'')+'</td>' +
            '<td class="mono-cell" style="font-size:15px;color:#94a3b8;padding:6px 10px;line-height:1.2">'+escapeHtml((r.ship_date||'').slice(0,10))+'</td>' +
            '<td class="mono-cell" style="font-size:15px;color:#94a3b8;padding:6px 10px;line-height:1.2">'+escapeHtml((r.arrival_date||'').slice(0,10))+'</td>' +
            '<td class="mono-cell" style="color:#555">—</td>' +
            '<td class="mono-cell" style="color:#555">—</td>' +
            '<td class="mono-cell" style="font-size:15px;color:#94a3b8;padding:6px 10px;line-height:1.2">'+escapeHtml(r.wh||'')+'</td>' +
            '<td class="mono-cell" style="color:#555">—</td>' +
            '<td class="mono-cell" style="color:#555">—</td>' +
            '<td class="mono-cell" style="color:#555">—</td>' +
            '<td><span class="tag" style="background:rgba(234,179,8,0.1);color:#94a3b8">'+escapeHtml(r.location||'-')+'</span></td>' +
            '<td></td>' +
            '</tr>';
        }
        var rawStatus = String(r.status || '').toUpperCase();
        var statusLabel = rawStatus || '-';
        var statusBadgeBg = (rawStatus === 'AVAILABLE') ? 'rgba(34,197,94,0.18)'
          : (rawStatus === 'RESERVED') ? 'rgba(245,158,11,0.22)'
          : (rawStatus === 'PICKED') ? 'rgba(59,130,246,0.22)'
          : (rawStatus === 'SOLD' || rawStatus === 'OUTBOUND' || rawStatus === 'SHIPPED' || rawStatus === 'CONFIRMED') ? 'rgba(239,68,68,0.2)'
          : (rawStatus === 'RETURN' || rawStatus === 'RETURNED') ? 'rgba(168,85,247,0.2)'
          : 'rgba(148,163,184,0.2)';
        var statusBadgeColor = (rawStatus === 'AVAILABLE') ? '#22c55e'
          : (rawStatus === 'RESERVED') ? '#f59e0b'
          : (rawStatus === 'PICKED') ? '#3b82f6'
          : (rawStatus === 'SOLD' || rawStatus === 'OUTBOUND' || rawStatus === 'SHIPPED' || rawStatus === 'CONFIRMED') ? '#ef4444'
          : (rawStatus === 'RETURN' || rawStatus === 'RETURNED') ? '#a855f7'
          : '#94a3b8';

        var mainRow =
          '<tr style="'+(hasSample ? 'border-left:3px solid #3b82f6' : '')+'">' +
          '<td class="mono-cell" style="color:var(--text-muted)">'+(i+1)+'</td>' +
          '<td class="mono-cell cell-left" style="color:var(--accent);font-weight:600;padding:6px 10px;line-height:1.2">'+lotKey+'</td>' +
          '<td style="text-align:center;padding:3px 4px;width:32px">'+'<button class="btn btn-ghost btn-xs" data-lot="'+lotKey+'" onclick="window.showInvActionMenu(this)"'+'  style="font-size:15px;padding:0 4px;letter-spacing:1px;line-height:1.2" title="추가기능">⋯</button>'+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.sap||'')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.bl||'')+'</td>' +
          '<td><span class="tag">'+escapeHtml(r.product||'')+'</span></td>' +
          '<td><span class="tag" style="background:'+statusBadgeBg+';color:'+statusBadgeColor+';font-weight:700">'+escapeHtml(statusLabel)+'</span></td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.balance!=null?fmtN(r.balance):'-')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'
            + '<span style="color:#22c55e;font-weight:700">'+(r.avail_mt!=null?fmtN(r.avail_mt):'-')+'</span>'
            + '<span style="color:#94a3b8;font-size:11px"> / </span>'
            + '<span style="color:#3b82f6">'+(r.reserved_mt!=null&&r.reserved_mt>0?'▲'+fmtN(r.reserved_mt):'0')+'</span>'
          + '</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.net!=null?fmtN(r.net):'-')+'</td>' +
          '<td class="mono-cell">'+parentContainer+'</td>' +
          '<td class="mono-cell" style="text-align:center;padding:6px 10px;line-height:1.2">' +
          (r.mxbg_pallet > 0
            ? '<button class="btn btn-ghost btn-xs" style="font-weight:700;color:var(--accent);padding:0 4px;line-height:1.1;min-height:18px" '
            + 'onclick="window.showTonbagModal(\'' + lotKey + '\')" title="톤백 세부 보기">'
            + r.mxbg_pallet + '</button>'
            : '-') +
          '</td>' +
          '<td class="mono-cell" style="text-align:center">'+(r.avail_bags!=null?r.avail_bags:'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.invoice_no||'')+'</td>' +
          '<td class="mono-cell">'+escapeHtml((r.ship_date||'').slice(0,10))+'</td>' +
          '<td class="mono-cell">'+escapeHtml((r.arrival_date||'').slice(0,10))+'</td>' +
          '<td class="mono-cell">'+escapeHtml((r.con_return||'').slice(0,10))+'</td>' +
          '<td class="mono-cell" style="text-align:center">'+(r.free_time||'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.wh||'')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.customs||'')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.initial_weight!=null?fmtN(r.initial_weight):'-')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.outbound_weight!=null?fmtN(r.outbound_weight):'-')+'</td>' +
          '<td><span class="tag">'+escapeHtml(r.location||'-')+'</span></td>' +
'<td></td>' +
          '</tr>';
        return sampleRow + mainRow;
      }).join('');
      html += '</tbody><tfoot><tr style="background:var(--panel);font-weight:700">';
      html += '<td colspan="7" style="text-align:right;padding:8px 10px">합계 ('+rows.length+' LOT) · 미판매 '+fmtN(sumUnsold)+' / <span style="color:#ef4444;font-weight:700">판매완료 '+fmtN(sumSold)+'</span></td>';
      html += '<td class="mono-cell" style="text-align:right">'+fmtN(sumBal)+'</td>';
      html += '<td class="mono-cell" style="text-align:right">' + '<span style="color:#22c55e;font-weight:700">'+fmtN(sumAvailMt)+'</span>' + '<span style="color:#94a3b8;font-size:11px"> / </span>' + '<span style="color:#3b82f6">'+fmtN(sumRsvMt)+'</span>' + '</td>';
      html += '<td class="mono-cell" style="text-align:right">'+fmtN(sumNet)+'</td>';
      html += '<td colspan="10"></td>';
      html += '<td class="mono-cell" style="text-align:right">'+fmtN(sumIni)+'</td>';
      html += '<td class="mono-cell" style="text-align:right">'+fmtN(sumOb)+'</td>';
      html += '<td colspan="2"></td>';
      html += '</tr></tfoot></table></div></section>';
      c.innerHTML = html;
    }).catch(function(e){
      if (window.getCurrentRoute() !== route) return;
      c.innerHTML = '<div class="empty" style="padding:40px;text-align:center">Load failed: '+escapeHtml(e.message||String(e))+'</div>';
      showToast('error', 'Inventory load failed');
    });
  }

  /* ── Inventory 탭 필터/검색 핸들러 ─────────────────────────────── */
  var _invAllRows = [];  // 전체 행 캐시 (필터용)

  window.invApplyFilter = function() {
    var statusEl = document.getElementById('inv-status-filter');
    var searchEl = document.getElementById('inv-search-input');
    var statusVal = statusEl ? statusEl.value : '';
    var searchVal = searchEl ? searchEl.value.trim().toLowerCase() : '';
    var tbody = document.querySelector('[data-page="inventory"] tbody');
    var tfoot = document.querySelector('[data-page="inventory"] tfoot');
    if (!tbody) return;

    var rows = Array.from(tbody.querySelectorAll('tr'));
    var visible = 0;
    rows.forEach(function(tr) {
      var cells = tr.querySelectorAll('td');
      if (!cells.length) return;
      var lot    = (cells[1] ? cells[1].textContent : '').toLowerCase();
      var sap    = (cells[2] ? cells[2].textContent : '').toLowerCase();
      var bl     = (cells[3] ? cells[3].textContent : '').toLowerCase();
      var prod   = (cells[4] ? cells[4].textContent : '').toLowerCase();
      var status = (cells[5] ? cells[5].textContent.trim() : '').toUpperCase();

      var matchStatus = !statusVal || status === statusVal;
      var matchSearch = !searchVal ||
        lot.includes(searchVal) || sap.includes(searchVal) ||
        bl.includes(searchVal)  || prod.includes(searchVal);

      if (matchStatus && matchSearch) {
        tr.style.display = '';
        visible++;
      } else {
        tr.style.display = 'none';
      }
    });
    var countEl = document.getElementById('inv-count-label');
    if (countEl) countEl.textContent = visible + ' / ' + rows.length + ' LOTs';
  };

  window.invClearFilter = function() {
    var statusEl = document.getElementById('inv-status-filter');
    var searchEl = document.getElementById('inv-search-input');
    if (statusEl) statusEl.value = '';
    if (searchEl) searchEl.value = '';
    window.invApplyFilter();
  };

  /* ─── 추가기능 드롭다운 (공용 _openContextMenu 사용) ──────────────── */
  window.showInvActionMenu = function(btn) {
    var lot = btn.dataset.lot || '';
    window._openContextMenu(btn, [
      { icon:'📋', label:'LOT 상세 보기',  kbd:'Enter',   fn:function(){ window.showLotDetail(lot); } },
      { icon:'📄', label:'LOT 번호 복사',  kbd:'Ctrl+C',  fn:function(){ window.invCopyLot(lot); } },
      { icon:'📑', label:'행 전체 복사',   kbd:'Ctrl+Shift+C', fn:function(){ window.invCopyLot(lot); } },
      '-',
      { icon:'🚀', label:'즉시 출고 진입', kbd:'O',       color:'#42a5f5', fn:function(){ window.invQuickOutbound(lot); } },
      { icon:'🔄', label:'반품 진입',      kbd:'R',       color:'#ef5350', fn:function(){ window.invQuickReturn(lot); } },
      { icon:'📊', label:'LOT 이력 보기', kbd:'H',       color:'#66bb6a', fn:function(){ window.invShowLotHistory(lot); } },
    ]);
  };

  window.invCopyLot = function(lot) {
    if (!lot) return;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(lot).then(function(){
        showToast('success', '📋 LOT 번호 복사됨: ' + lot);
      }).catch(function(){ prompt('수동 복사:', lot); });
    } else {
      prompt('수동 복사:', lot);
    }
  };

  window.invCopyRow = function(btn) {
    var tr = btn ? btn.closest('tr') : null;
    if (!tr) return;
    var cells = Array.from(tr.querySelectorAll('td'));
    var text = cells.slice(0, cells.length - 1).map(function(td){ return td.textContent.trim(); }).join('\t');
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function(){
        showToast('success', '📑 행 복사됨');
      }).catch(function(){ prompt('수동 복사:', text); });
    } else {
      prompt('수동 복사:', text);
    }
  };

  window.invQuickOutbound = function(lot) {
    if (!lot) return;
    renderPage('outbound');
    showToast('info', '🚀 출고 탭으로 이동: ' + lot);
  };

  window.invQuickReturn = function(lot) {
    if (!lot) return;
    renderPage('return');
    showToast('info', '🔄 반품 탭으로 이동: ' + lot);
  };

  /* ── 톤백 세부 모달 ─────────────────────────────── */
  window.showTonbagModal = function(lotNo) {
    if (!lotNo) return;
    var modal = document.getElementById('tonbag-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'tonbag-modal';
      modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center';
      modal.innerHTML =
        '<div style="background:var(--card-bg,#1e293b);border:1px solid var(--border,#334155);border-radius:12px;'
        + 'width:min(900px,95vw);max-height:85vh;display:flex;flex-direction:column;padding:20px;gap:12px">'
        + '<div style="display:flex;align-items:center;justify-content:space-between">'
        + '<h3 id="tbm-title" style="margin:0;font-size:16px;font-weight:700">톤백 세부</h3>'
        + '<div style="display:flex;gap:8px;align-items:center">'
        + '<select id="tbm-filter" onchange="window._filterTonbagModal()" '
        + 'style="background:var(--input-bg,#0f172a);border:1px solid var(--border,#334155);border-radius:6px;padding:4px 8px;color:inherit;font-size:13px">'
        + '<option value="">전체 상태</option>'
        + '<option value="AVAILABLE">AVAILABLE</option>'
        + '<option value="RESERVED">RESERVED</option>'
        + '<option value="PICKED">PICKED</option>'
        + '<option value="RETURN">RETURN</option>'
        + '<option value="SOLD">SOLD</option>'
        + '</select>'
        + '<button onclick="document.getElementById(\'tonbag-modal\').remove()" '
        + 'style="background:none;border:none;color:var(--text-muted,#94a3b8);font-size:20px;cursor:pointer;line-height:1">✕</button>'
        + '</div></div>'
        + '<div style="overflow:auto;flex:1">'
        + '<table id="tbm-table" style="width:100%;border-collapse:collapse;font-size:13px">'
        + '<thead><tr style="background:var(--table-header,#0f172a);position:sticky;top:0">'
        + '<th style="padding:8px;text-align:right;white-space:nowrap">#</th>'
        + '<th style="padding:8px;text-align:left;white-space:nowrap">Sub-LT</th>'
        + '<th style="padding:8px;text-align:right;white-space:nowrap">무게(MT)</th>'
        + '<th style="padding:8px;text-align:center;white-space:nowrap">상태</th>'
        + '<th style="padding:8px;text-align:center;white-space:nowrap">구분</th>'
        + '<th style="padding:8px;text-align:left;white-space:nowrap">위치</th>'
        + '<th style="padding:8px;text-align:left;white-space:nowrap">컨테이너</th>'
        + '<th style="padding:8px;text-align:left;white-space:nowrap">입고일</th>'
        + '</tr></thead>'
        + '<tbody id="tbm-body"></tbody>'
        + '</table></div>'
        + '<div id="tbm-summary" style="font-size:12px;color:var(--text-muted,#94a3b8);text-align:right"></div>'
        + '</div>';
      document.body.appendChild(modal);
      modal.addEventListener('click', function(e){ if (e.target === modal) modal.remove(); });
    }
    document.getElementById('tbm-title').textContent = '톤백 세부 — LOT ' + lotNo;
    document.getElementById('tbm-filter').value = '';
    document.getElementById('tbm-body').innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:#94a3b8">로딩 중...</td></tr>';
    document.getElementById('tbm-summary').textContent = '';
    modal.style.display = 'flex';
    modal._allRows = [];
    apiGet('/api/tonbags?lot_no=' + encodeURIComponent(lotNo) + '&limit=500')
      .then(function(res){
        var rows = Array.isArray(res) ? res : (res.data || res.items || []);
        modal._allRows = rows;
        window._filterTonbagModal();
      })
      .catch(function(){ document.getElementById('tbm-body').innerHTML =
        '<tr><td colspan="8" style="text-align:center;padding:20px;color:#ef4444">로드 실패</td></tr>'; });
  };

  window._filterTonbagModal = function() {
    var modal = document.getElementById('tonbag-modal');
    if (!modal || !modal._allRows) return;
    var filter = document.getElementById('tbm-filter').value;
    var rows = filter ? modal._allRows.filter(function(r){ return r.status === filter; }) : modal._allRows;
    var STATUS_COLOR = {
      AVAILABLE:'#22c55e', RESERVED:'#f59e0b', PICKED:'#3b82f6',
      RETURN:'#a855f7', SOLD:'#ef4444'
    };
    var html = '';
    rows.forEach(function(r, i){
      var isSample = r.is_sample == 1 || r.is_sample === true;
      var rowBg = isSample ? 'background:rgba(234,179,8,0.10)' : '';
      var sc = STATUS_COLOR[r.status] || '#94a3b8';
      html += '<tr style="border-bottom:1px solid var(--border,#334155);' + rowBg + '">'
        + '<td style="padding:6px 8px;text-align:right;color:#94a3b8">' + (i+1) + '</td>'
        + '<td style="padding:6px 8px;font-family:monospace">' + escapeHtml(r.sub_lt || r.tonbag_no || '') + '</td>'
        + '<td style="padding:6px 8px;text-align:right">' + ((r.weight != null && r.weight !== '') ? Number(r.weight).toFixed(3) : '-') + '</td>'
        + '<td style="padding:6px 8px;text-align:center"><span style="color:' + sc + ';font-weight:700">' + escapeHtml(r.status||'') + '</span></td>'
        + '<td style="padding:6px 8px;text-align:center">' + (isSample ? '🔬 샘플' : '📦 일반') + '</td>'
        + '<td style="padding:6px 8px;text-align:center">' + escapeHtml(r.location || '-') + '</td>'
        + '<td style="padding:6px 8px;font-family:monospace">' + escapeHtml(r.container || '-') + '</td>'
        + '<td style="padding:6px 8px;text-align:center">' + escapeHtml((r.inbound_date || '').slice(0,10)) + '</td>'
        + '</tr>';
    });
    document.getElementById('tbm-body').innerHTML = html ||
      '<tr><td colspan="8" style="text-align:center;padding:20px;color:#94a3b8">데이터 없음</td></tr>';
    var totalMt = rows.reduce(function(s,r){ return s + (parseFloat(r.weight)||0); }, 0);
    var sampleCnt = rows.filter(function(r){ return r.is_sample==1||r.is_sample===true; }).length;
    document.getElementById('tbm-summary').textContent =
      '표시 ' + rows.length + '개 / 합계 ' + totalMt.toFixed(3) + ' MT'
      + (sampleCnt > 0 ? ' (🔬 샘플 ' + sampleCnt + '개 포함)' : '');
  };

  window.invShowLotHistory = function(lot) {
    if (!lot) return;
    apiGet('/api/action/lot-detail?lot_no=' + encodeURIComponent(lot)).then(function(res){
      var d = res && res.data ? res.data : res;
      var history = (d.history || d.audit_log || []);
      var lines = history.map(function(h){
        return '[' + (h.created_at||h.action_time||'').slice(0,16) + '] ' + (h.action||'') + ' — ' + (h.note||h.detail||'');
      });
      var msg = lines.length ? lines.join('\n') : '이력 없음';
      alert('📊 LOT 이력: ' + lot + '\n\n' + msg);
    }).catch(function(e){
      showToast('error', 'LOT 이력 조회 실패: ' + (e.message||e));
    });
  };


  /* ===================================================
     7a-2. PAGE: Available (AVAILABLE 톤백 필터 뷰) — v9.5
     =================================================== */
  function loadAvailablePage() {
    var route = 'available';
    if (window.getCurrentRoute() !== route) return;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = '<div class="loading-spinner" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ Available 재고 로딩 중...</div>';

    // /api/inventory?status=AVAILABLE 호출 — 기존 인벤토리 API 재활용
    apiGet('/api/inventory?status=AVAILABLE&limit=500').then(function(res) {
      if (window.getCurrentRoute() !== route) return;
      var rows = Array.isArray(res) ? res : (res.data || res.rows || res.items || []);
      if (!rows.length) {
        c.innerHTML = '<div class="empty" style="padding:60px;text-align:center;color:var(--text-muted,#888)">✅ Available 재고 없음 (전량 배분 또는 피킹 완료)</div>';
        return;
      }
      // 헤더 (색상 강조 — Available 전용)
      var sumBal = 0, sumNet = 0, sumIni = 0, sumOb = 0;
      rows.forEach(function(r) {
        if (r.balance != null && !isNaN(Number(r.balance))) sumBal += Number(r.balance);
        if (r.net     != null && !isNaN(Number(r.net)))     sumNet += Number(r.net);
        if (r.initial_weight != null) sumIni += Number(r.initial_weight);
        if (r.outbound_weight != null) sumOb  += Number(r.outbound_weight);
      });
      var html = '<section style="padding:12px 16px">'
        + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;flex-wrap:wrap">'
        + '<h2 style="margin:0;font-size:16px;color:#22c55e">✅ Available 재고 — 판매 가능 물량</h2>'
        + '<span style="font-size:12px;color:var(--text-muted)">' + rows.length + ' LOT · Balance ' + fmtN(sumBal) + ' MT</span>'
        + '<button class="btn btn-ghost" style="font-size:12px;margin-left:auto" onclick="window.loadAvailablePage()">🔄 새로고침</button>'
        + '</div>'
        + '<div style="overflow-x:auto"><table class="data-table"><thead><tr>'
        + '<th>#</th><th style="text-align:center">LOT</th><th style="width:32px;text-align:center">+</th><th>SAP</th><th>BL</th><th>Product</th>'
        + '<th>Status</th><th>Balance(MT)</th><th>Avail/Rsv(MT)</th><th>NET(MT)</th><th>Container</th>'
        + '<th>MXBG</th><th>Avail</th><th>Invoice</th>'
        + '<th>Ship</th><th>Arrival</th><th>WH</th><th>Customs</th>'
        + '<th>Inbound(MT)</th><th>Location</th><th></th>'
        + '</tr></thead><tbody>';
      html += rows.map(function(r, i) {
        var lotKey = escapeHtml(r.lot||'');
        var hasSample = (r.sample_bags > 0);
        var parentContainer = escapeHtml(r.container || '-');
        var sampleRow = '';
        if (hasSample) {
          sampleRow =
            '<tr style="background:rgba(234,179,8,0.08);border-left:3px solid #eab308">' +
            '<td class="mono-cell" style="color:#eab308;text-align:center;padding:6px 10px">🔬</td>' +
            '<td class="mono-cell cell-left" style="color:#eab308;font-weight:700;padding:6px 10px">' + lotKey + '(SP)</td>' +
            '<td class="mono-cell" style="color:#94a3b8">' + escapeHtml(r.sap||'') + '</td>' +
            '<td class="mono-cell" style="color:#94a3b8">' + escapeHtml(r.bl||'') + '</td>' +
            '<td><span class="tag" style="background:rgba(234,179,8,0.2);color:#eab308">' + escapeHtml(r.product||'') + '</span></td>' +
            '<td style="color:#eab308;font-weight:600">SAMPLE</td>' +
            '<td class="mono-cell" style="text-align:right;color:#eab308;font-weight:600">' + fmtN(r.sample_weight_mt||0) + '</td>' +
            '<td class="mono-cell" style="text-align:right;color:#eab308">' + fmtN(r.sample_weight_mt||0) + '</td>' +
            '<td class="mono-cell" style="text-align:right;color:#eab308">' + fmtN(r.sample_weight_mt||0) + '</td>' +
            '<td class="mono-cell" style="color:#94a3b8">' + parentContainer + '</td>' +
            '<td class="mono-cell" style="text-align:center;color:#eab308;font-weight:700">' + r.sample_bags + '</td>' +
            '<td class="mono-cell" style="text-align:center;color:#eab308;font-weight:700">' + r.sample_bags + '</td>' +
            '<td colspan="7" style="color:#555">—</td>' +
            '<td></td><td></td>' +
            '</tr>';
        }
        var mainRow =
          '<tr style="' + (hasSample ? 'border-left:3px solid #22c55e' : '') + '">'
          + '<td class="mono-cell" style="color:var(--text-muted)">' + (i+1) + '</td>'
          + '<td class="mono-cell cell-left" style="color:var(--accent);font-weight:600;padding:6px 10px">' + lotKey + '</td>'
          + '<td class="mono-cell">' + escapeHtml(r.sap||'') + '</td>'
          + '<td class="mono-cell">' + escapeHtml(r.bl||'') + '</td>'
          + '<td><span class="tag">' + escapeHtml(r.product||'') + '</span></td>'
          + '<td><span class="tag" style="background:rgba(34,197,94,0.15);color:#22c55e">✅ AVAILABLE</span></td>'
          + '<td class="mono-cell" style="text-align:right">' + (r.balance!=null?fmtN(r.balance):'-') + '</td>'
          + '<td class="mono-cell" style="text-align:right">'
            + '<span style="color:#22c55e;font-weight:700">' + (r.avail_mt!=null?fmtN(r.avail_mt):'-') + '</span>'
            + '<span style="color:#94a3b8;font-size:11px"> / </span>'
            + '<span style="color:#3b82f6">' + (r.reserved_mt!=null&&r.reserved_mt>0?'▲'+fmtN(r.reserved_mt):'0') + '</span>'
          + '</td>'
          + '<td class="mono-cell" style="text-align:right">' + (r.net!=null?fmtN(r.net):'-') + '</td>'
          + '<td class="mono-cell">' + escapeHtml(r.container||'') + '</td>'
          + '<td class="mono-cell" style="text-align:center">'
            + (r.mxbg_pallet > 0
              ? '<button class="btn btn-ghost btn-xs" style="font-weight:700;color:var(--accent)" '
                + 'data-lot="' + lotKey + '" onclick="window.showTonbagModal(this.dataset.lot)">' + r.mxbg_pallet + '</button>'
              : '-')
          + '</td>'
          + '<td class="mono-cell" style="text-align:center">' + (r.avail_bags!=null?r.avail_bags:'-') + '</td>'
          + '<td class="mono-cell">' + escapeHtml(r.invoice_no||'') + '</td>'
          + '<td class="mono-cell">' + escapeHtml((r.ship_date||'').slice(0,10)) + '</td>'
          + '<td class="mono-cell">' + escapeHtml((r.arrival_date||'').slice(0,10)) + '</td>'
          + '<td class="mono-cell">' + escapeHtml(r.wh||'') + '</td>'
          + '<td class="mono-cell">' + escapeHtml(r.customs||'') + '</td>'
          + '<td class="mono-cell" style="text-align:right">' + (r.initial_weight!=null?fmtN(r.initial_weight):'-') + '</td>'
          + '<td><span class="tag">' + escapeHtml(r.location||'-') + '</span></td>'
          + '<td></td>'
          + '</tr>';
        return mainRow + sampleRow;
      }).join('');
      html += '</tbody><tfoot><tr style="background:var(--panel);font-weight:700">';
      html += '<td colspan="6" style="text-align:right;padding:8px 10px">합계 (' + rows.length + ' LOT)</td>';
      html += '<td class="mono-cell" style="text-align:right">' + fmtN(sumBal) + '</td>';
      html += '<td></td>';
      html += '<td class="mono-cell" style="text-align:right">' + fmtN(sumNet) + '</td>';
      html += '<td colspan="8"></td>';
      html += '<td class="mono-cell" style="text-align:right">' + fmtN(sumIni) + '</td>';
      html += '<td colspan="2"></td>';
      html += '</tr></tfoot></table></div></section>';
      c.innerHTML = html;
    }).catch(function(e) {
      if (window.getCurrentRoute() !== route) return;
      c.innerHTML = '<div class="empty" style="padding:40px;text-align:center">Load failed: ' + escapeHtml(e.message||String(e)) + '</div>';
      showToast('error', 'Available 로드 실패');
    });
  }
  window.loadAvailablePage = loadAvailablePage;
  /* ===================================================
     7b. PAGE: Allocation
     =================================================== */
  /* ===================================================
     7b. PAGE: Allocation — 2단 구조 (LOT 요약 + Detail)
     상단: LOT 단위 집계 (클릭 시 하단 확장)
     하단: 해당 LOT의 톤백 상세 목록
     =================================================== */
  /* ===================================================================
     [Sprint 1-1] Allocation 탭 — v864-2 AllocationDialog (1616줄) 포팅
     ──────────────────────────────────────────────────────────────────
     v864-2 source: gui_app_modular/dialogs/allocation_dialog.py
     v864-3 target: 이 함수 (탭 페이지) + 3개 기존 모달 재활용

     이 Phase(1-B+1-C)에서 구현:
       ✅ 9열 테이블 (ALLOC_PREVIEW_COLUMNS 매칭)
       ✅ 상단 액션 툴바 (4개 작동 + 3개 placeholder)
       ✅ 상태 필터 (전체/RESERVED/PICKED/SOLD)
       ✅ 다중 선택 체크박스 + 일괄 취소
       ✅ 합계 푸터 (qty_mt, 4 decimals)
       ✅ LOT 확장/축소 (기존 패턴 유지)

     다음 Phase(1-1-D~E)에서 추가:
       🟡 인라인 편집 (PATCH API 필요)
       🟡 PICKED/SOLD 상태 전환 (백엔드 엔드포인트 필요)
       🟡 LOT 예약 초기화 (백엔드 엔드포인트 필요)
       🟡 우클릭 컨텍스트 메뉴 (행 삭제/복사)
     =================================================================== */
  var _allocState = { currentFilter: 'all', rows: [], selectedLots: new Set() };
  /* [Sprint 1-1-D] 편집 가능 필드 (백엔드 _ALLOC_EDITABLE_FIELDS 와 일치 필요) */
  var ALLOC_EDITABLE_FIELDS = new Set(['customer', 'sale_ref', 'qty_mt', 'outbound_date']);


  window.loadInventoryPage  = loadInventoryPage;
})();
