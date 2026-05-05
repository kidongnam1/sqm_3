/* SQM Inventory v8.6.6 — sqm-allocation.js (Allocation — 배정관리) */
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
  /* ──────────────────────────────────────────────────────────────── */

  /* ─── 모듈 상태 (sqm-inline.js 분리 후 이쪽에서 선언) ─────────── */
  var _allocState = {
    currentFilter: 'all',
    rows: [],
    selectedLots: new Set()
  };

  function allocStatusPalette(status) {
    var st = String(status || '').toUpperCase();
    if (st === 'AVAILABLE') return { bg: 'rgba(34,197,94,0.18)', fg: '#22c55e' };
    if (st === 'RESERVED')  return { bg: 'rgba(245,158,11,0.22)', fg: '#f59e0b' };
    if (st === 'PICKED')    return { bg: 'rgba(59,130,246,0.22)', fg: '#3b82f6' };
    if (st === 'SOLD' || st === 'OUTBOUND' || st === 'SHIPPED' || st === 'CONFIRMED') return { bg: 'rgba(239,68,68,0.2)', fg: '#ef4444' };
    if (st === 'RETURN' || st === 'RETURNED') return { bg: 'rgba(168,85,247,0.2)', fg: '#a855f7' };
    return { bg: 'rgba(148,163,184,0.2)', fg: '#94a3b8' };
  }

  function loadAllocationPage() {
    var route = window.getCurrentRoute();
    var c = document.getElementById('page-container');
    if (!c) return;
    _allocState.selectedLots.clear();
    c.innerHTML = [
      '<section class="page" data-page="allocation">',
      /* ── 헤더 ── */
      '<div class="alloc-header" style="display:flex;align-items:center;gap:12px;padding:8px 0 8px">',
      '  <h2 style="margin:0">📋 판매 배정 (Allocation)</h2>',
      '  <span id="alloc-summary-label" style="color:var(--text-muted);font-size:.9rem"></span>',
      '  <button class="btn btn-secondary" onclick="renderPage(\'allocation\')" style="margin-left:auto">🔁 새로고침</button>',
      '</div>',
      /* ── 액션 툴바 (v864-2 AllocationDialog primary_buttons 매핑) ── */
      '<div class="alloc-toolbar" style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:8px 10px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px">',
      '  <button class="btn btn-primary" onclick="window.allocUploadExcel()">📂 Excel 업로드</button>',
      '  <button class="btn" onclick="window.allocApplyApproved()">📌 승인분 반영</button>',
      '  <button class="btn" onclick="window.allocShowApprovalQueue()">✅ 승인 대기</button>',
      '  <span style="width:1px;height:22px;background:var(--panel-border);margin:0 4px"></span>',
      '  <button class="btn btn-danger" onclick="window.allocCancelSelected()">❌ 선택 배정 취소</button>',
      '  <span style="width:1px;height:22px;background:var(--panel-border);margin:0 4px"></span>',
      /* 백엔드 엔드포인트 미구현 — Sprint 1-1-E에서 연결 */
      '  <button class="btn" onclick="window.allocPickSelected()" title="RESERVED → PICKED">📦 출고 실행 (PICKED)</button>',
      '  <button class="btn" onclick="window.allocConfirmSelected()" title="PICKED → SOLD">🔒 출고 확정 (SOLD)</button>',
      '  <button class="btn" onclick="window.allocResetSelected()" title="LOT 배정 완전 삭제">🧹 LOT 초기화</button>',
      '  <span style="width:1px;height:22px;background:var(--panel-border);margin:0 4px"></span>',
      '  <button class="btn btn-danger" onclick="window.allocResetAll()" title="모든 배정 취소 + AVAILABLE 원복">⚠️ 전체 초기화</button>',
      '  <button class="btn" onclick="window.allocCancelBySaleRef()" title="SALE REF 입력 후 해당 배정 전체 취소">🔖 SALE REF 취소</button>',
      '  <button class="btn" onclick="window.allocOpenLotOverview()" title="LOT별 배정 현황 팝업">📦 LOT 현황</button>',
      '  <button class="btn btn-secondary" onclick="window.allocExportExcel()" title="현재 배정 데이터 Excel 다운로드">📊 Excel 내보내기</button>',
      '</div>',
      /* ── 단계 되돌리기 버튼 행 ── */
      '<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px">',
      '  <span style="font-size:12px;font-weight:600;white-space:nowrap">&#x21A9; 단계 되돌리기:</span>',
      '  <button class="btn" onclick="window.allocRevertStep(\'RESERVED\')" style="font-size:12px">RESERVED &rarr; AVAILABLE</button>',
      '  <button class="btn" onclick="window.allocRevertStep(\'PICKED\')" style="font-size:12px">PICKED &rarr; RESERVED</button>',
      '  <button class="btn" onclick="window.allocRevertStep(\'OUTBOUND\')" style="font-size:12px">OUTBOUND &rarr; PICKED</button>',
      '</div>',
      /* ── 상태 필터 ── */
      '<div class="alloc-filter" style="display:flex;gap:4px;margin-bottom:8px">',
      '  <button class="alloc-filter-btn active" data-filter="all" onclick="window.allocFilterBy(\'all\')">전체</button>',
      '  <button class="alloc-filter-btn" data-filter="RESERVED" onclick="window.allocFilterBy(\'RESERVED\')">RESERVED</button>',
      '  <button class="alloc-filter-btn" data-filter="PICKED" onclick="window.allocFilterBy(\'PICKED\')">PICKED</button>',
      '  <button class="alloc-filter-btn" data-filter="SOLD" onclick="window.allocFilterBy(\'SOLD\')">SOLD</button>',
      '</div>',
      /* ── 로딩 / 빈 상태 ── */
      '<div id="alloc-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>',
      '<div class="empty" id="alloc-empty" style="display:none;padding:60px;text-align:center">📭 배정 데이터 없음</div>',
      /* ── 테이블 (v864-2 ALLOC_PREVIEW_COLUMNS: LOT/SAP/PRODUCT/QTY/CUSTOMER/SALE REF/OUTBOUND DATE/WH/STATUS) ── */
      '<div style="overflow-x:auto">',
      '  <table class="data-table" id="alloc-summary-table" style="display:none;width:100%">',
      '  <thead><tr>',
      '    <th style="width:32px"><input type="checkbox" id="alloc-select-all" onclick="window.allocToggleAll(this.checked)"></th>',
      '    <th style="width:40px">No.</th>',
      '    <th>LOT NO</th>',
      '    <th>SAP NO</th>',
      '    <th>PRODUCT</th>',
      '    <th style="text-align:right">QTY (MT)</th>',
      '    <th>CUSTOMER</th>',
      '    <th>SALE REF</th>',
      '    <th>OUTBOUND DATE</th>',
      '    <th>WH</th>',
      '    <th>STATUS</th>',
      '  </tr></thead>',
      '  <tbody id="alloc-summary-tbody"></tbody>',
      '  <tfoot id="alloc-summary-tfoot"></tfoot>',
      '  </table>',
      '</div>',
      /* ── 상세 패널 (기존 기능 유지) ── */
      '<div id="alloc-detail-panel" style="display:none;margin-top:16px;border-top:2px solid var(--panel-border);padding-top:16px">',
      '  <h3 id="alloc-detail-title" style="margin:0 0 12px 0">톤백 상세</h3>',
      '  <div id="alloc-detail-content"></div>',
      '</div>',
      '</section>'
    ].join('');

    apiGet('/api/q/allocation-summary').then(function(res){
      if (window.getCurrentRoute() !== route) return;
      _allocState.rows = extractRows(res);
      document.getElementById('alloc-loading').style.display = 'none';
      if (!_allocState.rows.length) {
        document.getElementById('alloc-empty').style.display = 'block';
        var lbl = document.getElementById('alloc-summary-label');
        if (lbl) lbl.textContent = '(0건)';
        return;
      }
      _renderAllocTable();
    }).catch(function(e){
      if (window.getCurrentRoute() !== route) return;
      document.getElementById('alloc-loading').style.display = 'none';
      document.getElementById('alloc-empty').textContent = 'Load failed: ' + (e.message||'');
      document.getElementById('alloc-empty').style.display = 'block';
    });
  }

  /* ── 테이블 렌더 (필터 적용) ────────────────────────────────────── */
  function _renderAllocTable() {
    var filter = _allocState.currentFilter;
    var rows = _allocState.rows.filter(function(r){
      if (filter === 'all') return true;
      return (r.status || 'RESERVED').toUpperCase() === filter;
    });
    var tbody = document.getElementById('alloc-summary-tbody');
    var tfoot = document.getElementById('alloc-summary-tfoot');
    var table = document.getElementById('alloc-summary-table');
    var empty = document.getElementById('alloc-empty');
    var lbl = document.getElementById('alloc-summary-label');

    if (!rows.length) {
      if (tbody) tbody.innerHTML = '';
      if (tfoot) tfoot.innerHTML = '';
      if (table) table.style.display = 'none';
      if (empty) { empty.textContent = '📭 (' + filter + ') 배정 데이터 없음'; empty.style.display = 'block'; }
      if (lbl) lbl.textContent = '(0/' + _allocState.rows.length + '건)';
      return;
    }
    if (empty) empty.style.display = 'none';
    if (table) table.style.display = '';
    if (lbl) lbl.textContent = '(' + rows.length + '/' + _allocState.rows.length + '건)';

    var totalMt = 0;
    /* [Sprint 1-1-D] 편집 가능 셀에 data-lot/data-field + ondblclick + oncontextmenu */
    tbody.innerHTML = rows.map(function(r, i){
      var lot = escapeHtml(r.lot_no || '');
      var qtyMt = (r.total_mt != null) ? Number(r.total_mt) : (r.qty_mt != null ? Number(r.qty_mt) : 0);
      if (!isNaN(qtyMt)) totalMt += qtyMt;
      var status = (r.status || 'RESERVED').toUpperCase();
      var pal = allocStatusPalette(status);
      var checked = _allocState.selectedLots.has(lot) ? 'checked' : '';

      /* 편집 가능 셀 attrs 헬퍼 */
      function editTd(field, display, extraClass, extraStyle) {
        var attrs = 'class="' + (extraClass || '') + ' alloc-editable" ' +
          'data-lot="' + lot + '" data-field="' + field + '"' +
          (extraStyle ? ' style="' + extraStyle + '"' : '') +
          ' ondblclick="window.allocEditCell(this)" title="더블클릭으로 편집";';
        return '<td ' + attrs + '>' + display + '</td>';
      }

      return '<tr class="alloc-summary-row" data-lot="' + lot + '" data-status="' + status + '" oncontextmenu="window.allocContextMenu(event, \'' + lot + '\'); return false;">' +
        '<td style="text-align:center"><input type="checkbox" ' + checked + ' onclick="event.stopPropagation();window.allocToggleRow(\'' + lot + '\',this.checked)"></td>' +
        '<td class="mono-cell" style="text-align:right">' + (i + 1) + '</td>' +
        '<td class="mono-cell cell-left" style="color:var(--accent);font-weight:600;cursor:pointer" onclick="window.toggleAllocDetail(\'' + lot + '\')">' +
          '<span class="alloc-expand-icon">▶</span> ' + lot + '</td>' +
        '<td class="mono-cell">' + escapeHtml(r.sap_no || '-') + '</td>' +
        '<td>' + escapeHtml(r.product || '-') + '</td>' +
        editTd('qty_mt', (qtyMt ? qtyMt.toFixed(4) : '-'), 'mono-cell', 'text-align:right') +
        editTd('customer', escapeHtml(r.customer || r.sold_to || '-'), '', '') +
        editTd('sale_ref', escapeHtml(r.sale_ref || '-'), 'mono-cell', '') +
        editTd('outbound_date', escapeHtml(r.outbound_date || r.ship_date || '-'), 'mono-cell', '') +
        '<td>' + escapeHtml(r.warehouse || r.wh || '-') + '</td>' +
        '<td><span class="tag" style="background:' + pal.bg + ';color:' + pal.fg + ';font-weight:700">' + status + '</span></td>' +
        '</tr>';
    }).join('');

    /* Footer 합계 (v864-2 TreeviewTotalFooter 매칭) */
    tfoot.innerHTML =
      '<tr style="background:var(--panel);font-weight:700">' +
      '<td colspan="6" style="text-align:right">합계:</td>' +
      '<td class="mono-cell" style="text-align:right">' + totalMt.toFixed(4) + ' MT</td>' +
      '<td colspan="5"></td>' +
      '</tr>';
  }

  /* ── 버튼 핸들러 ─────────────────────────────────────────────────── */
  window.showAllocActionMenu = function(btn) {
    var lot = btn.dataset.lot || '';
    window._openContextMenu(btn, [
      { icon:'📋', label:'LOT 상세 보기',  kbd:'Enter',  fn:function(){ if(window.showLotDetail) window.showLotDetail(lot); } },
      { icon:'📄', label:'LOT 번호 복사',  kbd:'Ctrl+C', fn:function(){ navigator.clipboard&&navigator.clipboard.writeText(lot); showToast('info','LOT 복사: '+lot); } },
      '-',
      { icon:'▶',  label:'배분 상세 열기', kbd:'Space',  color:'#3b82f6', fn:function(){ window.toggleAllocDetail(lot); } },
      { icon:'❌', label:'배분 취소',       kbd:'Del',    color:'#ef5350', fn:function(){
          if(!confirm(lot+' 배분을 취소하시겠습니까?')) return;
          window._allocState && window._allocState.selectedLots.add(lot);
          window.allocCancelSelected && window.allocCancelSelected();
        }
      },
    ]);
  };
  window.allocUploadExcel = function() {
    if (typeof showAllocationUploadModal === 'function') { showAllocationUploadModal(); }
    else { showToast('error', 'Upload modal 미초기화'); }
  };
  window.allocApplyApproved = function() {
    if (typeof showApplyApprovedAllocationModal === 'function') { showApplyApprovedAllocationModal(); }
    else { showToast('error', 'Apply modal 미초기화'); }
  };
  window.allocShowApprovalQueue = function() {
    if (typeof showApprovalQueueModal === 'function') { showApprovalQueueModal(); }
    else { showToast('error', 'Approval queue 미초기화'); }
  };
  window.allocWipToast = function(featureName) {
    showToast('info', featureName + ': 준비 중 (Sprint 1-1-E 예정 — 백엔드 엔드포인트 구현 후 연결)');
  };
  window.allocFilterBy = function(filter) {
    _allocState.currentFilter = filter;
    document.querySelectorAll('.alloc-filter-btn').forEach(function(b){
      b.classList.toggle('active', b.dataset.filter === filter);
    });
    _renderAllocTable();
  };
  window.allocToggleAll = function(checked) {
    var visibleFilter = _allocState.currentFilter;
    _allocState.rows.forEach(function(r){
      var status = (r.status || 'RESERVED').toUpperCase();
      if (visibleFilter !== 'all' && status !== visibleFilter) return;
      var lot = r.lot_no || '';
      if (checked) _allocState.selectedLots.add(lot);
      else _allocState.selectedLots.delete(lot);
    });
    _renderAllocTable();
  };
  window.allocToggleRow = function(lot, checked) {
    if (checked) _allocState.selectedLots.add(lot);
    else _allocState.selectedLots.delete(lot);
  };
  window.allocCancelSelected = function() {
    _allocBulkAction({
      url_suffix:   '/cancel',
      method:       'POST',
      label:        '배정 취소',
      icon:         '❌',
      confirmMsg:   '건 배정 취소?',
    });
  };

  /* ── [Sprint 1-1-E] 상태 전환 버튼 핸들러 ──────────────────────────── */
  window.allocPickSelected = function() {
    _allocBulkAction({
      url_suffix:   '/pick',
      method:       'POST',
      label:        '출고 실행 (PICKED)',
      icon:         '📦',
      confirmMsg:   '건을 PICKED 상태로 변경?\n(RESERVED → PICKED)',
    });
  };
  window.allocConfirmSelected = function() {
    _allocBulkAction({
      url_suffix:   '/confirm',
      method:       'POST',
      label:        '출고 확정 (SOLD)',
      icon:         '🔒',
      confirmMsg:   '건을 SOLD 상태로 확정?\n(PICKED → SOLD — 되돌릴 수 없음)',
    });
  };

  /* ── 전체 초기화 ── */
  window.allocResetAll = function() {
    if (!confirm('⚠️ 전체 초기화\n\n모든 RESERVED/PICKED/OUTBOUND 배정을 취소하고 AVAILABLE로 원복합니다.\n(SOLD는 보호됩니다)\n\n계속하시겠습니까?')) return;
    apiPost('/api/allocation/reset-all', {})
      .then(function(res){
        showToast('success', '⚠️ ' + (res.message || '전체 초기화 완료'));
        loadAllocationPage();
      })
      .catch(function(e){ showToast('error', '전체 초기화 실패: ' + (e.message||e)); });
  };

  /* ── SALE REF 일괄 취소 ── */
  window.allocCancelBySaleRef = function() {
    var saleRef = prompt('SALE REF 번호를 입력하세요 (예: SC-2026-001)');
    if (!saleRef || !saleRef.trim()) return;
    saleRef = saleRef.trim();
    if (!confirm('🔖 SALE REF 취소\n\n"' + saleRef + '" 에 해당하는 모든 배정을 취소하고 AVAILABLE로 원복합니다.\n계속하시겠습니까?')) return;
    apiPost('/api/allocation/cancel-by-sale-ref', { sale_ref: saleRef })
      .then(function(res){
        if (res.ok === false) { showToast('warn', res.message || '취소 대상 없음'); }
        else { showToast('success', '🔖 ' + (res.message || 'SALE REF 취소 완료')); loadAllocationPage(); }
      })
      .catch(function(e){ showToast('error', 'SALE REF 취소 실패: ' + (e.message||e)); });
  };

  /* ── LOT 현황 팝업 ── */
  window.allocOpenLotOverview = function() {
    showToast('info', '📦 LOT 현황 로딩...');
    apiGet('/api/allocation/lot-overview').then(function(res){
      var rows = (res.data || []);
      if (!rows.length) { showToast('warn', 'LOT 현황 데이터 없음'); return; }
      var lines = rows.map(function(r, i){
        return (i+1) + '. ' + r.lot_no +
          ' | 순중량: ' + (r.net_mt||0).toFixed(3) + 'MT' +
          ' | 현재: ' + (r.balance_mt||0).toFixed(3) + 'MT' +
          ' | 배정: ' + (r.alloc_mt||0).toFixed(3) + 'MT' +
          ' | 잔여: ' + (r.remain_mt||0).toFixed(3) + 'MT' +
          (r.sample_bags ? ' | 샘플:' + r.sample_bags + '개' : '');
      });
      alert('📦 LOT 배정 현황 (' + rows.length + '건)\n\n' + lines.join('\n'));
    }).catch(function(e){ showToast('error', 'LOT 현황 실패: ' + (e.message||e)); });
  };

  /* ── Excel 내보내기 ── */
  window.allocExportExcel = function() {
    var url = (typeof window.API !== 'undefined' ? window.API : 'http://localhost:8765') + '/api/allocation/export-excel';
    var a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast('success', '📊 Excel 다운로드 시작됨');
  };

  /* ── 단계 되돌리기 ── */
  window.allocRevertStep = function(fromStatus) {
    var labels = { RESERVED: 'RESERVED → AVAILABLE', PICKED: 'PICKED → RESERVED', OUTBOUND: 'OUTBOUND → PICKED' };
    var label = labels[fromStatus] || fromStatus;
    if (!confirm('↩️ 단계 되돌리기\n\n' + label + '\n\n' + fromStatus + ' 상태의 모든 배정을 한 단계 되돌립니다.\n계속하시겠습니까?')) return;
    apiPost('/api/allocation/revert-step', { from_status: fromStatus })
      .then(function(res){
        if (res.ok === false) { showToast('warn', res.message || '되돌릴 대상 없음'); }
        else { showToast('success', '↩️ ' + (res.message || label + ' 완료')); loadAllocationPage(); }
      })
      .catch(function(e){ showToast('error', '되돌리기 실패: ' + (e.message||e)); });
  };


  /* ── 전체 초기화 ── */
  window.allocResetAll = function() {
    if (!confirm('⚠️ 전체 초기화\n\n모든 RESERVED/PICKED/OUTBOUND 배정을 취소하고 AVAILABLE로 원복합니다.\n(SOLD는 보호됩니다)\n\n계속하시겠습니까?')) return;
    apiPost('/api/allocation/reset-all', {})
      .then(function(res){
        showToast('success', '⚠️ ' + (res.message || '전체 초기화 완료'));
        loadAllocationPage();
      })
      .catch(function(e){ showToast('error', '전체 초기화 실패: ' + (e.message||e)); });
  };

  /* ── SALE REF 일괄 취소 ── */
  window.allocCancelBySaleRef = function() {
    var saleRef = prompt('SALE REF 번호를 입력하세요 (예: SC-2026-001)');
    if (!saleRef || !saleRef.trim()) return;
    saleRef = saleRef.trim();
    if (!confirm('🔖 SALE REF 취소\n\n"' + saleRef + '" 에 해당하는 모든 배정을 취소하고 AVAILABLE로 원복합니다.\n계속하시겠습니까?')) return;
    apiPost('/api/allocation/cancel-by-sale-ref', { sale_ref: saleRef })
      .then(function(res){
        if (res.ok === false) { showToast('warn', res.message || '취소 대상 없음'); }
        else { showToast('success', '🔖 ' + (res.message || 'SALE REF 취소 완료')); loadAllocationPage(); }
      })
      .catch(function(e){ showToast('error', 'SALE REF 취소 실패: ' + (e.message||e)); });
  };

  /* ── LOT 현황 팝업 ── */
  window.allocOpenLotOverview = function() {
    showToast('info', '📦 LOT 현황 로딩...');
    apiGet('/api/allocation/lot-overview').then(function(res){
      var rows = (res.data || []);
      if (!rows.length) { showToast('warn', 'LOT 현황 데이터 없음'); return; }
      var lines = rows.map(function(r, i){
        return (i+1) + '. ' + r.lot_no +
          ' | 순중량: ' + (r.net_mt||0).toFixed(3) + 'MT' +
          ' | 현재: ' + (r.balance_mt||0).toFixed(3) + 'MT' +
          ' | 배정: ' + (r.alloc_mt||0).toFixed(3) + 'MT' +
          ' | 잔여: ' + (r.remain_mt||0).toFixed(3) + 'MT' +
          (r.sample_bags ? ' | 샘플:' + r.sample_bags + '개' : '');
      });
      alert('📦 LOT 배정 현황 (' + rows.length + '건)\n\n' + lines.join('\n'));
    }).catch(function(e){ showToast('error', 'LOT 현황 실패: ' + (e.message||e)); });
  };

  /* ── Excel 내보내기 ── */
  window.allocExportExcel = function() {
    var url = (typeof window.API !== 'undefined' ? window.API : 'http://localhost:8765') + '/api/allocation/export-excel';
    var a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast('success', '📊 Excel 다운로드 시작됨');
  };

  /* ── 단계 되돌리기 ── */
  window.allocRevertStep = function(fromStatus) {
    var labels = { RESERVED: 'RESERVED → AVAILABLE', PICKED: 'PICKED → RESERVED', OUTBOUND: 'OUTBOUND → PICKED' };
    var label = labels[fromStatus] || fromStatus;
    if (!confirm('↩️ 단계 되돌리기\n\n' + label + '\n\n' + fromStatus + ' 상태의 모든 배정을 한 단계 되돌립니다.\n계속하시겠습니까?')) return;
    apiPost('/api/allocation/revert-step', { from_status: fromStatus })
      .then(function(res){
        if (res.ok === false) { showToast('warn', res.message || '되돌릴 대상 없음'); }
        else { showToast('success', '↩️ ' + (res.message || label + ' 완료')); loadAllocationPage(); }
      })
      .catch(function(e){ showToast('error', '되돌리기 실패: ' + (e.message||e)); });
  };

  window.allocResetSelected = function() {
    _allocBulkAction({
      url_suffix:   '/reset',
      method:       'POST',
      label:        'LOT 배정 초기화',
      icon:         '🧹',
      confirmMsg:   '건 배정 완전 초기화?\nallocation_plan 에서 삭제 + inventory AVAILABLE 원복\n(SOLD 는 보호됨)',
    });
  };

  /* 공통 다중 선택 액션 헬퍼 */
  function _allocBulkAction(opts) {
    var selected = Array.from(_allocState.selectedLots);
    if (!selected.length) { showToast('warn', opts.label + ': 대상을 먼저 선택하세요'); return; }
    var preview = selected.slice(0, 5).join(', ') + (selected.length > 5 ? ' …외 ' + (selected.length - 5) + '건' : '');
    if (!confirm(opts.icon + ' ' + opts.label + '\n\n' + selected.length + opts.confirmMsg + '\n\n' + preview)) return;

    var okCount = 0, errors = [];
    var promises = selected.map(function(lot){
      return apiPost('/api/allocation/' + encodeURIComponent(lot) + opts.url_suffix, {})
        .then(function(){ okCount++; })
        .catch(function(e){ errors.push({ lot: lot, reason: (e && e.message) || String(e) }); });
    });
    Promise.all(promises).then(function(){
      var errCount = errors.length;
      if (errCount === 0) {
        showToast('success', opts.icon + ' ' + opts.label + ': ' + okCount + '건 성공');
      } else {
        var errSample = errors.slice(0, 3).map(function(e){ return e.lot + ' (' + e.reason + ')'; }).join(', ');
        showToast('warn', opts.label + ': 성공 ' + okCount + ' / 실패 ' + errCount + ' (' + errSample + ')');
      }
      _allocState.selectedLots.clear();
      loadAllocationPage();
    });
  }

  /* ── [Sprint 1-1-D] 인라인 편집 — 셀 더블클릭 → PATCH ─────────────── */
  window.allocEditCell = function(td) {
    if (!td || td.querySelector('input')) return;
    var lot = td.dataset.lot;
    var field = td.dataset.field;
    if (!lot || !field || !ALLOC_EDITABLE_FIELDS.has(field)) return;

    /* 현재 값 추출 (display 에서 HTML tag 제거) */
    var curDisplay = td.textContent.trim();
    var curVal = curDisplay === '-' ? '' : curDisplay;

    /* qty_mt 는 number input */
    var input = document.createElement('input');
    input.type = (field === 'qty_mt') ? 'number' : (field === 'outbound_date' ? 'date' : 'text');
    if (field === 'qty_mt') input.step = '0.0001';
    input.value = curVal;
    input.className = 'alloc-edit-input';
    input.style.cssText = 'width:100%;padding:2px 4px;background:var(--bg);color:var(--fg);border:1px solid var(--accent);border-radius:3px;font-size:11px;font-family:inherit';

    td.innerHTML = '';
    td.appendChild(input);
    input.focus();
    input.select && input.select();

    var committed = false;
    function cancel() {
      if (committed) return;
      committed = true;
      _renderAllocTable();  /* 원복 */
    }
    function commit() {
      if (committed) return;
      committed = true;
      var newVal = input.value;
      if (String(newVal).trim() === String(curVal).trim()) {
        _renderAllocTable();
        return;
      }
      /* PATCH /api/allocation/{lot} */
      td.innerHTML = '<span style="color:var(--text-muted);font-size:11px">⏳ 저장 중...</span>';
      var payload = {};
      payload[field] = newVal;
      fetch(window.API + '/api/allocation/' + encodeURIComponent(lot), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then(function(r){ return r.json().then(function(b){ return { ok: r.ok, body: b }; }); })
        .then(function(res){
          if (!res.ok || !res.body.success) {
            throw new Error((res.body && (res.body.detail || res.body.message)) || 'PATCH 실패');
          }
          /* 로컬 rows 업데이트 */
          var row = _allocState.rows.find(function(r){ return (r.lot_no || '') === lot; });
          if (row) {
            row[field] = (field === 'qty_mt') ? Number(newVal) : newVal;
            if (field === 'customer') row.sold_to = newVal;
          }
          showToast('success', '💾 ' + lot + '.' + field + ' 저장됨');
          _renderAllocTable();
        })
        .catch(function(e){
          showToast('error', '편집 실패: ' + (e.message || String(e)));
          _renderAllocTable();
        });
    }
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', function(e){
      if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
      else if (e.key === 'Escape') {
        e.preventDefault();
        input.removeEventListener('blur', commit);
        cancel();
      }
    });
  };

  /* ── [Sprint 1-1-D] 우클릭 컨텍스트 메뉴 — 행 삭제/복사 ─────────────── */
  window.allocContextMenu = function(e, lot) {
    e.preventDefault();
    /* 기존 컨텍스트 메뉴 제거 */
    var old = document.querySelector('.ctx-menu');
    if (old) old.remove();

    var row = _allocState.rows.find(function(r){ return (r.lot_no || '') === lot; });
    if (!row) return;

    var m = document.createElement('div');
    m.className = 'ctx-menu';
    m.style.cssText = 'position:fixed;z-index:9999;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;padding:4px 0;min-width:160px;box-shadow:0 4px 16px rgba(0,0,0,.4);font-size:13px;';
    m.style.left = e.clientX + 'px';
    m.style.top = e.clientY + 'px';

    function mi(label, onClick, danger) {
      var b = document.createElement('button');
      b.textContent = label;
      b.style.cssText = 'display:block;width:100%;text-align:left;padding:6px 14px;background:transparent;border:none;color:' + (danger ? 'var(--danger)' : 'var(--fg)') + ';cursor:pointer;font-size:13px';
      b.addEventListener('mouseover', function(){ b.style.background = 'var(--btn-hover)'; });
      b.addEventListener('mouseout', function(){ b.style.background = 'transparent'; });
      b.addEventListener('click', function(){ m.remove(); onClick(); });
      m.appendChild(b);
    }

    mi('📋 행 복사 (CSV)', function(){
      var cols = ['lot_no', 'sap_no', 'product', 'qty_mt', 'customer', 'sale_ref', 'outbound_date', 'warehouse', 'status'];
      var header = cols.join(',');
      var values = cols.map(function(c){ return String(row[c] != null ? row[c] : (c === 'customer' ? (row.sold_to || '') : '')); }).join(',');
      var text = header + '\n' + values;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function(){
          showToast('success', '📋 클립보드에 복사됨');
        }).catch(function(){
          prompt('수동 복사:', text);
        });
      } else {
        prompt('수동 복사:', text);
      }
    });

    mi('❌ 이 행 배정 취소', function(){
      if (!confirm('❌ ' + lot + '\n배정 취소하시겠습니까?')) return;
      apiPost('/api/allocation/' + encodeURIComponent(lot) + '/cancel', {})
        .then(function(){ showToast('success', lot + ' 취소됨'); loadAllocationPage(); })
        .catch(function(err){ showToast('error', '취소 실패: ' + (err.message || err)); });
    }, false);

    mi('🧹 이 행 초기화 (삭제)', function(){
      if (!confirm('🧹 ' + lot + '\nallocation 기록 삭제 + inventory AVAILABLE 원복\n(SOLD 는 보호됨)\n계속하시겠습니까?')) return;
      apiPost('/api/allocation/' + encodeURIComponent(lot) + '/reset', {})
        .then(function(res){ showToast('success', (res.data && res.data.message) || (lot + ' 초기화됨')); loadAllocationPage(); })
        .catch(function(err){ showToast('error', '초기화 실패: ' + (err.message || err)); });
    }, true);

    document.body.appendChild(m);
    /* 다음 클릭 또는 ESC 로 자동 닫기 */
    var closeHandler = function(ev){
      if (!m.contains(ev.target)) { m.remove(); document.removeEventListener('click', closeHandler); }
    };
    setTimeout(function(){ document.addEventListener('click', closeHandler); }, 10);
  };

  var _allocExpandedLot = null;
  window.toggleAllocDetail = function(lotNo) {
    var panel = document.getElementById('alloc-detail-panel');
    var content = document.getElementById('alloc-detail-content');
    var title = document.getElementById('alloc-detail-title');

    // 같은 LOT 클릭 시 닫기
    if (_allocExpandedLot === lotNo) {
      panel.style.display = 'none';
      _allocExpandedLot = null;
      document.querySelectorAll('.alloc-summary-row').forEach(function(r){ r.style.background=''; });
      document.querySelectorAll('.alloc-expand-icon').forEach(function(i){ i.textContent='▶'; });
      return;
    }

    _allocExpandedLot = lotNo;
    document.querySelectorAll('.alloc-summary-row').forEach(function(r){
      if (r.dataset.lot === lotNo) {
        r.style.background = 'var(--bg-active)';
        r.querySelector('.alloc-expand-icon').textContent = '▼';
      } else {
        r.style.background = '';
        r.querySelector('.alloc-expand-icon').textContent = '▶';
      }
    });

    panel.style.display = 'block';
    title.textContent = '📋 ' + lotNo + ' 톤백 상세';
    content.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">⏳ 로딩...</div>';

    apiGet('/api/q/allocation-detail/' + encodeURIComponent(lotNo)).then(function(res){
      var rows = extractRows(res);
      if (!rows.length) { content.innerHTML = '<div class="empty">상세 데이터 없음</div>'; return; }
      var tbl = '<table class="data-table"><thead><tr><th>#</th><th>톤백ID</th><th>중량(kg)</th><th>위치</th><th>상태</th><th>배정일</th></tr></thead><tbody>';
      tbl += rows.map(function(r, i){
        var p = allocStatusPalette(r.status);
        return '<tr><td>'+(i+1)+'</td><td class="mono-cell">'+escapeHtml(r.tonbag_id||r.sub_lt||'-')+'</td><td class="mono-cell" style="text-align:right">'+(r.weight!=null?Number(r.weight).toLocaleString():'-')+'</td><td>'+escapeHtml(r.location||'-')+'</td><td><span class="tag" style="background:'+p.bg+';color:'+p.fg+';font-weight:700">'+escapeHtml(r.status||'-')+'</span></td><td>'+escapeHtml(r.plan_date||r.allocated_date||'-')+'</td></tr>';
      }).join('');
      tbl += '</tbody></table>';
      content.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:8px">' + rows.length + '개 톤백</p>' + tbl;
    }).catch(function(e){
      content.innerHTML = '<div class="empty">상세 로드 실패: '+escapeHtml(e.message||'')+'</div>';
    });
  };

  window.cancelAllocation = function(lot) {
    if (!confirm(lot + ': cancel allocation?')) return;
    apiPost('/api/allocation/' + encodeURIComponent(lot) + '/cancel', {})
      .then(function(){ showToast('success', lot + ' allocation cancelled'); loadAllocationPage(); })
      .catch(function(e){ showToast('error', 'Cancel failed: ' + (e.message||String(e))); });
  };

  /* ===================================================
     7c. PAGE: Picked
     =================================================== */
  /* ===================================================
     7c. PAGE: Picked — 2단 구조 (LOT 요약 + 톤백 상세)
     =================================================== */


  /* ===================================================
     Allocation 양식 가져오기 모달 v2
     - 모달 열 때 기존 양식 목록 표시 + 삭제
     - 파일 분석(check) → 중복 여부에 따라 확인 UI
     - 비중복: "추가하시겠습니까?" / 중복: 3가지 선택
     =================================================== */
  function showImportAllocationTemplateModal() {
    var _pendingFile = null;   // 분석 완료된 파일 보관
    var _pendingFd   = null;   // 재사용할 FormData (label 포함)
    var _pendingRes  = null;   // check 결과 보관

    var html = [
      '<div style="max-width:560px">',
      '<h2 style="margin:0 0 14px 0">📥 Allocation 양식 관리</h2>',

      // ── 기존 양식 목록 ──────────────────────────────────
      '<div style="margin-bottom:16px">',
      '  <div style="font-size:.85rem;font-weight:600;color:var(--text-muted);margin-bottom:6px">📋 현재 등록된 양식</div>',
      '  <div id="atpl-list" style="background:var(--bg-hover);border:1px solid var(--border);border-radius:6px;min-height:40px;max-height:160px;overflow-y:auto;padding:4px 0">',
      '    <div style="padding:10px 12px;color:var(--text-muted);font-size:.85rem">⏳ 목록 불러오는 중...</div>',
      '  </div>',
      '</div>',

      '<hr style="border:none;border-top:1px solid var(--border);margin:0 0 14px 0">',

      // ── 새 양식 업로드 ──────────────────────────────────
      '<div style="margin-bottom:10px">',
      '  <label style="display:block;font-size:.85rem;color:var(--text-muted);margin-bottom:4px">양식 이름 (탭에 표시할 이름)</label>',
      '  <input type="text" id="atpl-label" placeholder="예: Song_LGES 11컬럼"',
      '    style="width:100%;box-sizing:border-box;padding:7px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text-primary);font-size:.9rem">',
      '</div>',
      '<div id="atpl-drop" style="border:2px dashed var(--border);border-radius:8px;padding:24px 16px;text-align:center;background:var(--bg-hover);cursor:pointer;margin-bottom:10px;transition:border-color .2s">',
      '  <div style="font-size:2rem;margin-bottom:4px">📁</div>',
      '  <div id="atpl-fname" style="color:var(--text-muted);font-size:.88rem">클릭 또는 파일을 여기에 드롭하세요 (.xlsx)</div>',
      '</div>',
      '<input type="file" id="atpl-input" accept=".xlsx,.xls" style="display:none">',

      // ── 분석 결과 / 확인 UI ──────────────────────────────
      '<div id="atpl-result" style="margin-bottom:12px;font-size:.88rem"></div>',

      // ── 하단 버튼 ────────────────────────────────────────
      '<div style="display:flex;gap:8px;justify-content:flex-end">',
      '  <button type="button" class="btn btn-primary" id="atpl-submit" disabled>🔍 분석</button>',
      '  <button type="button" class="btn btn-ghost" id="atpl-close">닫기</button>',
      '</div>',
      '</div>'
    ].join('');
    showDataModal('', html);

    var dropZone  = document.getElementById('atpl-drop');
    var fileInput = document.getElementById('atpl-input');
    var submitBtn = document.getElementById('atpl-submit');
    var resultDiv = document.getElementById('atpl-result');
    var listDiv   = document.getElementById('atpl-list');

    document.getElementById('atpl-close').onclick = function(){
      document.getElementById('sqm-modal').style.display = 'none';
    };

    // ── 기존 양식 목록 로드 ────────────────────────────────
    function loadList() {
      fetch(window.API + '/api/allocation/template-list')
        .then(function(r){ return r.json(); })
        .then(function(res){
          if (!res.ok || !res.templates || res.templates.length === 0) {
            listDiv.innerHTML = '<div style="padding:10px 12px;color:var(--text-muted);font-size:.85rem">등록된 양식이 없습니다.</div>';
            return;
          }
          var rows = res.templates.map(function(t){
            var cols = (t.columns || []).length;
            return '<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 12px;border-bottom:1px solid var(--border)">' +
              '<div style="font-size:.87rem">' +
                '<span style="font-weight:600">' + escapeHtml(t.tab_label) + '</span>' +
                '<span style="color:var(--text-muted);margin-left:8px;font-size:.8rem">[' + cols + '컬럼]</span>' +
              '</div>' +
              '<button type="button" onclick="window._atplDelete(\'' + t.id.replace(/\'/g, "\\\'" ) + '\')" ' +
                'style="background:none;border:1px solid var(--danger);color:var(--danger);border-radius:4px;padding:2px 8px;font-size:.78rem;cursor:pointer">🗑️ 삭제</button>' +
            '</div>';
          });
          listDiv.innerHTML = rows.join('');
        })
        .catch(function(){ listDiv.innerHTML = '<div style="padding:10px 12px;color:var(--danger);font-size:.85rem">목록 불러오기 실패</div>'; });
    }

    window._atplDelete = function(id) {
      if (!confirm('양식 [' + id + '] 을(를) 삭제하시겠습니까?')) return;
      fetch(window.API + '/api/allocation/template/' + encodeURIComponent(id), { method:'DELETE' })
        .then(function(r){ return r.json(); })
        .then(function(res){
          if (res.ok) { showToast('success', '삭제 완료: ' + id); loadList(); }
          else showToast('error', res.detail || '삭제 실패');
        })
        .catch(function(){ showToast('error', '통신 오류'); });
    };

    loadList();

    // ── 파일 선택 ──────────────────────────────────────────
    function setFile(f) {
      if (!f) return;
      if (!f.name.match(/\.xlsx?$/i)) {
        resultDiv.innerHTML = '<span style="color:var(--danger)">⚠️ xlsx 또는 xls 파일만 가능합니다.</span>';
        return;
      }
      _pendingFile = f;
      _pendingFd = null; _pendingRes = null;
      document.getElementById('atpl-fname').textContent = f.name + ' (' + (f.size/1024).toFixed(1) + ' KB)';
      dropZone.style.borderColor = 'var(--accent)';
      resultDiv.innerHTML = '<span style="color:var(--text-muted)">파일 선택됨. [분석] 버튼을 클릭하세요.</span>';
      submitBtn.disabled = false;
      submitBtn.textContent = '🔍 분석';
    }

    dropZone.addEventListener('click', function(){ fileInput.click(); });
    fileInput.addEventListener('change', function(){ if (fileInput.files[0]) setFile(fileInput.files[0]); });
    dropZone.addEventListener('dragover',  function(e){ e.preventDefault(); dropZone.style.borderColor='var(--accent)'; });
    dropZone.addEventListener('dragleave', function(){ dropZone.style.borderColor='var(--border)'; });
    dropZone.addEventListener('drop', function(e){
      e.preventDefault(); dropZone.style.borderColor='var(--border)';
      var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) setFile(f);
    });

    // ── 분석 버튼 클릭 → action=check ─────────────────────
    submitBtn.addEventListener('click', function(){
      if (!_pendingFile) return;
      var label = (document.getElementById('atpl-label').value || '').trim();
      submitBtn.disabled = true;
      submitBtn.textContent = '⏳ 분석 중...';
      resultDiv.innerHTML = '<span style="color:var(--text-muted)">헤더 분석 중...</span>';

      var fd = new FormData();
      fd.append('file', _pendingFile);
      if (label) fd.append('label', label);
      fd.append('action', 'check');
      _pendingFd = fd;

      fetch(window.API + '/api/allocation/template-upload', { method:'POST', body:fd })
        .then(function(r){ return r.json(); })
        .then(function(res){
          if (!res.ok) {
            resultDiv.innerHTML = '<span style="color:var(--danger)">❌ ' + escapeHtml(res.detail || '분석 실패') + '</span>';
            submitBtn.disabled = false; submitBtn.textContent = '🔍 분석';
            return;
          }
          _pendingRes = res;
          showAnalysisResult(res);
        })
        .catch(function(e){
          resultDiv.innerHTML = '<span style="color:var(--danger)">❌ 통신 오류: ' + escapeHtml(e.message||String(e)) + '</span>';
          submitBtn.disabled = false; submitBtn.textContent = '🔍 분석';
        });
    });

    // ── 필수 컬럼 검증 ────────────────────────────────────
    var _REQUIRED_PATTERNS = {
      'LOT NO':   /lot/i,
      'QTY(MT)':  /qty|quantity|balance|수량/i,
      'SOLD TO':  /sold|customer|고객/i
    };
    function _checkRequiredCols(columns) {
      var missing = [];
      Object.keys(_REQUIRED_PATTERNS).forEach(function(label) {
        var found = columns.some(function(c) { return _REQUIRED_PATTERNS[label].test(c); });
        if (!found) missing.push(label);
      });
      return missing;
    }

    // ── 분석 결과 표시 + 확인 UI ───────────────────────────
    function showAnalysisResult(res) {
      var cols = (res.columns || []).join(', ');
      var preview = '<div style="background:var(--bg-hover);border:1px solid var(--border);border-radius:6px;padding:10px 12px;margin-bottom:10px">' +
        '<div style="font-size:.83rem;color:var(--text-muted)">' +
        '<b>ID:</b> ' + escapeHtml(res.id) + ' &nbsp;|&nbsp; ' +
        '<b>시트:</b> ' + escapeHtml(res.sheet) + ' &nbsp;|&nbsp; ' +
        '<b>헤더행:</b> ' + res.header_row + '행<br>' +
        '<b>감지 컬럼 (' + (res.columns||[]).length + '개):</b> ' + escapeHtml(cols) +
        '</div></div>';

      // 필수 컬럼 누락 경고 배너
      var missingCols = _checkRequiredCols(res.columns || []);
      if (missingCols.length > 0) {
        preview += '<div style="background:rgba(255,193,7,.1);border:1px solid #ffc107;border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:.85rem">' +
          '<b style="color:#ffc107">⚠️ 필수 컬럼 누락 감지</b><br>' +
          '<span style="color:var(--text-muted)">아래 컬럼이 없으면 배분 실행 시 오류가 발생할 수 있습니다:</span><br>' +
          missingCols.map(function(m){ return '&nbsp;&nbsp;• <b>' + escapeHtml(m) + '</b>'; }).join('<br>') +
          '<br><span style="color:var(--text-muted);font-size:.8rem">계속 등록할 수 있지만, 실제 사용 전 Excel 양식에 해당 컬럼을 추가하세요.</span>' +
          '</div>';
      }

      if (!res.duplicate) {
        // 비중복 → 추가 확인
        resultDiv.innerHTML = preview +
          '<div style="background:rgba(var(--success-rgb,40,167,69),.08);border:1px solid var(--success);border-radius:6px;padding:10px 14px;display:flex;align-items:center;justify-content:space-between">' +
          '<span style="color:var(--success);font-weight:600">✅ 새 양식입니다. 목록에 추가하시겠습니까?</span>' +
          '<div style="display:flex;gap:6px">' +
          '<button type="button" class="btn btn-primary" onclick="window._atplDoSave(\'overwrite\')">➕ 추가</button>' +
          '<button type="button" class="btn btn-ghost" onclick="window._atplCancelSave()">취소</button>' +
          '</div></div>';
        submitBtn.style.display = 'none';
      } else {
        // 중복 → 3가지 선택
        resultDiv.innerHTML = preview +
          '<div style="background:rgba(255,193,7,.08);border:1px solid #ffc107;border-radius:6px;padding:10px 14px">' +
          '<div style="color:#ffc107;font-weight:600;margin-bottom:8px">⚠️ 이미 같은 이름의 양식이 존재합니다. 어떻게 할까요?</div>' +
          '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
          '<button type="button" class="btn btn-ghost" onclick="window._atplCancelSave()">🔒 기존 유지</button>' +
          '<button type="button" style="background:var(--danger);color:#fff;border:none;border-radius:6px;padding:6px 14px;cursor:pointer" onclick="window._atplDoSave(\'overwrite\')">🔄 대체</button>' +
          '<button type="button" style="background:var(--accent);color:#fff;border:none;border-radius:6px;padding:6px 14px;cursor:pointer" onclick="window._atplDoSave(\'keep_both\')">📋 둘 다 등록</button>' +
          '</div></div>';
        submitBtn.style.display = 'none';
      }
    }

    // ── 실제 저장 (action=overwrite|keep_both) ────────────
    window._atplDoSave = function(action) {
      if (!_pendingFile || !_pendingRes) return;
      var label = (document.getElementById('atpl-label').value || '').trim();
      var fd = new FormData();
      fd.append('file', _pendingFile);
      if (label) fd.append('label', label);
      fd.append('action', action);

      resultDiv.innerHTML = '<span style="color:var(--text-muted)">⏳ 저장 중...</span>';
      fetch(window.API + '/api/allocation/template-upload', { method:'POST', body:fd })
        .then(function(r){ return r.json(); })
        .then(function(res){
          if (res.ok) {
            resultDiv.innerHTML = '<div style="color:var(--success);font-weight:600;padding:8px 0">✅ ' + escapeHtml(res.message) + '</div>';
            showToast('success', (res.overwritten ? '덮어쓰기' : '신규 등록') + ': ' + escapeHtml(res.tab_label));
            submitBtn.style.display = '';
            submitBtn.disabled = true; submitBtn.textContent = '🔍 분석';
            _pendingFile = null; _pendingFd = null; _pendingRes = null;
            document.getElementById('atpl-fname').textContent = '클릭 또는 파일을 여기에 드롭하세요 (.xlsx)';
            dropZone.style.borderColor = 'var(--border)';
            loadList();
          } else {
            resultDiv.innerHTML = '<span style="color:var(--danger)">❌ ' + escapeHtml(res.detail || '저장 실패') + '</span>';
            submitBtn.style.display = '';
            submitBtn.disabled = false; submitBtn.textContent = '🔍 분석';
          }
        })
        .catch(function(e){
          resultDiv.innerHTML = '<span style="color:var(--danger)">❌ 통신 오류: ' + escapeHtml(e.message||String(e)) + '</span>';
          submitBtn.style.display = '';
          submitBtn.disabled = false; submitBtn.textContent = '🔍 분석';
        });
    };

    window._atplCancelSave = function() {
      resultDiv.innerHTML = '<span style="color:var(--text-muted)">취소됨. 다른 파일을 선택하거나 닫으세요.</span>';
      submitBtn.style.display = '';
      submitBtn.disabled = false; submitBtn.textContent = '🔍 분석';
    };
  }
  window.showImportAllocationTemplateModal = showImportAllocationTemplateModal;

  window.loadAllocationPage = loadAllocationPage;
})();
