/* SQM Inventory v8.6.6 — sqm-logistics.js (Logistics — 입고·출고·반품·이동·로그·스캔) */
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
  var dbgLog        = function() { return window.dbgLog.apply(window, arguments); };
  var extractRows               = function() { return window.extractRows.apply(window, arguments); };
  var fmtN                      = function() { return window.fmtN.apply(window, arguments); };
  /* ──────────────────────────────────────────────────────────────── */

  /* ─── Inbound 페이지 공유 상태 (sqm-logistics 전용) ─── */
  var _inboundAllRows = [];

  var STATUS_COLOR = {
    'INBOUND':'#1976d2','ALLOCATED':'#7b1fa2','PICKED':'#f57c00',
    'OUTBOUND':'#388e3c','RETURN':'#c62828','HOLD':'#616161'
  };

  function _renderInboundRows(rows) {
    var tbody = document.getElementById('inbound-tbody');
    var empty = document.getElementById('inbound-empty');
    var tbl   = document.getElementById('inbound-table');
    if (!tbody) return;
    if (!rows.length) {
      if (tbl)   tbl.style.display   = 'none';
      if (empty) { empty.textContent = '📭 해당 상태의 데이터 없음'; empty.style.display = 'block'; }
      return;
    }
    if (empty) empty.style.display = 'none';
    tbody.innerHTML = rows.map(function(r, i){
      var sc     = STATUS_COLOR[r.status] || '#888';
      var netMT  = r.net_weight     != null ? fmtN(r.net_weight     / 1000) : '-';
      var curMT  = r.current_weight != null ? fmtN(r.current_weight / 1000) : '-';
      return '<tr>' +
        '<td class="mono-cell" style="color:var(--text-muted)">'+(i+1)+'</td>' +
        '<td class="mono-cell" style="color:var(--accent);font-weight:600">'+escapeHtml(r.lot_no||'')+'</td>' +
        '<td class="mono-cell">'+escapeHtml(r.lot_sqm||'-')+'</td>' +
        '<td class="mono-cell">'+escapeHtml(r.sap_no||'-')+'</td>' +
        '<td class="mono-cell">'+escapeHtml(r.bl_no||'-')+'</td>' +
        '<td><span class="tag">'+escapeHtml(r.product||'-')+'</span></td>' +
        '<td class="mono-cell" style="text-align:right">'+netMT+'</td>' +
        '<td class="mono-cell" style="text-align:right">'+curMT+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+(r.tonbag_count||0)+'</td>' +
        '<td><span style="color:'+sc+';font-weight:600;font-size:11px">'+escapeHtml(r.status||'-')+'</span></td>' +
        '<td class="mono-cell">'+escapeHtml((r.inbound_date||'').slice(0,10)||'-')+'</td>' +
        '<td class="mono-cell">'+escapeHtml((r.arrival_date||'').slice(0,10)||'-')+'</td>' +
        '<td><span class="tag">'+escapeHtml(r.warehouse||'-')+'</span></td>' +
        '<td>'+escapeHtml(r.vessel||'-')+'</td>' +
        '</tr>';
    }).join('');
    if (tbl) tbl.style.display = '';
    dbgLog('📋','inbound-table shown', 'rows='+rows.length+' tbl='+(tbl?tbl.style.display:'?'), '#4caf50');
  }

  function _inboundFilter(status) {
    document.querySelectorAll('.inbound-filter-btn').forEach(function(b){
      b.style.fontWeight = (b.dataset.status === status) ? '700' : '400';
      b.style.opacity    = (b.dataset.status === status) ? '1'   : '0.55';
    });
    var filtered = status === 'ALL'
      ? _inboundAllRows
      : _inboundAllRows.filter(function(r){ return r.status === status; });
    var count = document.getElementById('inbound-count');
    if (count) count.textContent = filtered.length + ' / ' + _inboundAllRows.length + '건';
    _renderInboundRows(filtered);
  }
  window._inboundFilter = _inboundFilter;

  function loadInboundPage() {
    var route = window.getCurrentRoute();
    var c = document.getElementById('page-container');
    if (!c) return;
    _inboundAllRows = [];

    var FILTERS = ['ALL','INBOUND','ALLOCATED','PICKED','OUTBOUND','RETURN','HOLD'];
    var filterBtns = FILTERS.map(function(s){
      var col = STATUS_COLOR[s] || '#555';
      return '<button class="inbound-filter-btn" data-status="'+s+'" '+
        'onclick="_inboundFilter(\''+s+'\')" '+
        'style="border:1px solid '+col+';color:'+col+';background:transparent;'+
        'border-radius:4px;padding:3px 10px;cursor:pointer;font-size:12px;font-weight:400;opacity:0.55">'+s+'</button>';
    }).join('');

    c.innerHTML = [
      '<section class="page" data-page="inbound">',
      '<div style="display:flex;align-items:center;gap:12px;padding:8px 0 10px;flex-wrap:wrap">',
      '<h2 style="margin:0;white-space:nowrap">📥 입고 목록</h2>',
      '<div style="display:flex;gap:6px;flex-wrap:wrap">'+filterBtns+'</div>',
      '<span id="inbound-count" style="margin-left:auto;font-size:12px;color:var(--text-muted)">--</span>',
      '<button class="btn btn-secondary" onclick="renderPage(\'inbound\')" style="white-space:nowrap">🔁 새로고침</button>',
      '</div>',
      '<div id="inbound-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '<table class="data-table" id="inbound-table" style="display:none">',
      '<thead><tr>',
      '<th>#</th><th>LOT No</th><th>SQM LOT</th><th>SAP No</th><th>BL No</th>',
      '<th>제품</th><th>순중량(MT)</th><th>현재중량(MT)</th><th>톤백수</th>',
      '<th>상태</th><th>입고일자</th><th>도착일자</th><th>창고</th><th>선박</th>',
      '</tr></thead>',
      '<tbody id="inbound-tbody"></tbody>',
      '</table>',
      '</div>',
      '<div class="empty" id="inbound-empty" style="display:none;padding:60px;text-align:center;color:var(--text-muted)">📭 입고 데이터 없음</div>',
      '</section>'
    ].join('');

    apiGet('/api/q/inbound-status').then(function(res){
      if (window.getCurrentRoute() !== route) return;
      _inboundAllRows = (res.data && res.data.items) || [];
      var total = _inboundAllRows.length;
      document.getElementById('inbound-loading').style.display = 'none';
      if (!total) {
        document.getElementById('inbound-empty').style.display = 'block';
        return;
      }
      _inboundFilter('ALL');   /* ALL 버튼 active + 전체 렌더 */
      dbgLog('📥','inbound-page','total='+total,'#4caf50');
    }).catch(function(e){
      if (window.getCurrentRoute() !== route) return;
      document.getElementById('inbound-loading').style.display = 'none';
      var el = document.getElementById('inbound-empty');
      if (el) { el.textContent = '❌ 로드 실패: '+(e.message||String(e)); el.style.display = 'block'; }
      showToast('error', '입고 목록 로드 실패');
      dbgLog('❌','inbound-page',String(e),'#f44336');
    });
  }

  /* ===================================================
     7d. PAGE: Outbound (출고 현황 — F025/F037)
     /api/q/outbound-status → res.data.items
     columns: lot_no, movement_type, qty_kg, customer,
              from_location, to_location, movement_date,
              source_type, actor, remarks
     =================================================== */
  /* ===================================================
     7d. PAGE: Outbound/Sold — 2단 구조 (LOT 요약 + 톤백 상세)
     =================================================== */
  /* ═══════════════════════════════════════════════════════════════
     📋 Picking List PDF 업로드 모달
     POST /api/outbound/picking-list-pdf → 파싱+DB반영 원스텝
     ═══════════════════════════════════════════════════════════════ */
  window.showOutboundPickingModal = function() {
    var html = [
      '<div style="max-width:560px">',
      '<h2 style="margin:0 0 4px 0">📋 Picking List PDF 업로드</h2>',
      '<p style="color:var(--text-muted);font-size:.85rem;margin:0 0 16px 0">',
      '  PDF를 업로드하면 자동 파싱 후 <b>RESERVED → PICKED</b> 상태로 반영합니다.',
      '</p>',

      '<!-- 업로드 존 -->',
      '<div id="pkl-dropzone" style="border:2px dashed var(--panel-border);border-radius:10px;',
      '  padding:32px;text-align:center;cursor:pointer;transition:border-color .2s;margin-bottom:16px"',
      '  onclick="document.getElementById(\'pkl-file-input\').click()"',
      '  ondragover="event.preventDefault();this.style.borderColor=\'var(--accent)\'"',
      '  ondragleave="this.style.borderColor=\'var(--panel-border)\'"',
      '  ondrop="event.preventDefault();this.style.borderColor=\'var(--panel-border)\';window._pklHandleFile(event.dataTransfer.files[0])">',
      '  <div style="font-size:2rem;margin-bottom:8px">📄</div>',
      '  <div style="font-weight:600;margin-bottom:4px">클릭 또는 드래그 앤 드롭</div>',
      '  <div style="font-size:.8rem;color:var(--text-muted)">Picking List PDF 파일 (.pdf)</div>',
      '</div>',
      '<input type="file" id="pkl-file-input" accept=".pdf" style="display:none"',
      '  onchange="window._pklHandleFile(this.files[0])">',

      '<!-- 진행/결과 영역 -->',
      '<div id="pkl-status" style="display:none;padding:12px;border-radius:8px;',
      '  background:var(--panel);border:1px solid var(--panel-border);margin-bottom:12px;font-size:.9rem"></div>',

      '<!-- 버튼 -->',
      '<div style="display:flex;justify-content:flex-end;gap:8px">',
      '  <button class="btn btn-ghost" onclick="window._closeDataModal()">닫기</button>',
      '</div>',
      '</div>'
    ].join('');

    if (window.showDataModal) showDataModal('', html);
    else {
      var m = document.getElementById('sqm-modal');
      if (m) { m.querySelector('.modal-body, .modal-content, div').innerHTML = html; m.style.display='flex'; }
    }
  };

  /* 파일 선택/드롭 핸들러 */
  window._pklHandleFile = function(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showToast('error', 'PDF 파일만 업로드 가능합니다');
      return;
    }
    var status = document.getElementById('pkl-status');
    var dropzone = document.getElementById('pkl-dropzone');
    if (!status) return;

    // 로딩 표시
    status.style.display = 'block';
    status.style.borderLeft = '4px solid var(--accent)';
    status.innerHTML = '<div style="display:flex;align-items:center;gap:10px">'
      + '<span style="font-size:1.2rem">⏳</span>'
      + '<div><b>' + escapeHtml(file.name) + '</b><br>'
      + '<span style="color:var(--text-muted);font-size:.8rem">파싱 중... (텍스트 PDF: 빠름 / 스캔 PDF: Gemini OCR 사용)</span>'
      + '</div></div>';
    if (dropzone) dropzone.style.opacity = '0.5';

    var fd = new FormData();
    fd.append('file', file);

    fetch('/api/outbound/picking-list-pdf', { method: 'POST', body: fd })
      .then(function(r){ return r.json(); })
      .then(function(res) {
        if (dropzone) dropzone.style.opacity = '1';
        var d = res.data || {};
        var ok = res.ok === true;
        var color = ok ? '#22c55e' : '#ef4444';
        var icon  = ok ? '✅' : '❌';

        var warnHtml = '';
        if (d.warnings && d.warnings.length) {
          warnHtml = '<details style="margin-top:8px"><summary style="cursor:pointer;color:#f59e0b;font-size:.8rem">⚠️ 경고 '
            + d.warnings.length + '건 (클릭하여 펼치기)</summary>'
            + '<pre style="white-space:pre-wrap;font-size:.75rem;margin-top:6px;color:var(--text-muted)">'
            + escapeHtml((d.warnings||[]).join('\n')) + '</pre></details>';
        }

        var detailHtml = '';
        if (ok && d.details && d.details.length) {
          var rows = d.details.slice(0,20).map(function(dt){
            return '<tr><td class="mono-cell">' + escapeHtml(dt.lot_no||'') + '</td>'
              + '<td style="text-align:right">' + (dt.picked||0) + '</td>'
              + '<td style="color:#f59e0b">' + (dt.partial ? '부분' : '') + '</td></tr>';
          }).join('');
          detailHtml = '<details style="margin-top:8px"><summary style="cursor:pointer;font-size:.8rem">📦 LOT별 반영 결과</summary>'
            + '<table class="data-table" style="margin-top:6px;font-size:.8rem">'
            + '<thead><tr><th style="text-align:left">LOT No</th><th>PICKED</th><th>비고</th></tr></thead>'
            + '<tbody>' + rows + '</tbody></table></details>';
        }

        status.style.borderLeft = '4px solid ' + color;
        status.innerHTML = '<div style="display:flex;align-items:flex-start;gap:10px">'
          + '<span style="font-size:1.4rem">' + icon + '</span>'
          + '<div style="flex:1">'
          + '<div style="font-weight:700;margin-bottom:2px">' + escapeHtml(res.message || (ok ? '완료' : '실패')) + '</div>'
          + (ok ? '<div style="font-size:.85rem;color:var(--text-muted)">'
            + '파일: <b>' + escapeHtml(d.filename||file.name) + '</b>'
            + ' · LOT <b>' + (d.total_lots||0) + '개</b>'
            + ' · 일반 <b style="color:#22c55e">' + (d.total_normal_mt||0) + ' MT</b>'
            + ' · 샘플 <b style="color:#f59e0b">' + (d.total_sample_kg||0) + ' KG</b>'
            + ' · 반영 <b style="color:var(--accent)">' + (d.applied||0) + '건</b>'
            + '</div>' : '<div style="color:#ef4444;font-size:.85rem">' + escapeHtml(res.error||'오류') + '</div>')
          + warnHtml + detailHtml
          + '</div></div>';

        if (ok) {
          showToast('success', 'Picking List 반영 완료 — ' + (d.applied||0) + '건');
          // 현재 페이지 갱신
          setTimeout(function(){
            if (window.getCurrentRoute() === 'outbound') renderPage('outbound');
            if (typeof window.loadSidebarBadges === 'function') window.loadSidebarBadges();
          }, 600);
        } else {
          showToast('error', res.message || 'Picking List 반영 실패');
        }
      })
      .catch(function(e) {
        if (dropzone) dropzone.style.opacity = '1';
        status.style.borderLeft = '4px solid #ef4444';
        status.innerHTML = '<div style="color:#ef4444">❌ 네트워크 오류: ' + escapeHtml(e.message||String(e)) + '</div>';
        showToast('error', '업로드 실패: ' + (e.message||String(e)));
      });
  };

  /* 모달 닫기 헬퍼 */
  window._closeDataModal = function() {
    var m = document.getElementById('sqm-modal');
    if (m) m.style.display = 'none';
  };

  function loadOutboundPage() {
    var route = window.getCurrentRoute();
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="outbound">',
      '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:8px 0 12px">',
      '  <h2 style="margin:0">📤 출고 완료 (Sold / Outbound)</h2>',
      '  <div style="margin-left:auto;display:flex;gap:8px">',
      '    <button class="btn btn-primary" onclick="window.showOutboundPickingModal()" style="font-weight:600">📋 Picking List 업로드</button>',
      '    <button class="btn btn-secondary" onclick="renderPage(\'outbound\')">🔁 새로고침</button>',
      '  </div>',
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
      if (window.getCurrentRoute() !== route) return;
      var rows = extractRows(res);
      document.getElementById('outbound-loading').style.display = 'none';
      if (!rows.length) {
        document.getElementById('outbound-empty').style.display = 'block';
        return;
      }
      var tbody = document.getElementById('outbound-tbody');
      if (tbody) tbody.innerHTML = rows.map(function(r, i){
        var lot = escapeHtml(r.lot_no||'');
        return '<tr class="outbound-summary-row" data-lot="'+lot+'" style="cursor:pointer" onclick="window.toggleOutboundDetail(\''+lot+'\')">' +
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
      if (window.getCurrentRoute() !== route) return;
      document.getElementById('outbound-loading').style.display = 'none';
      var el = document.getElementById('outbound-empty');
      if (el) { el.textContent = '❌ 로드 실패: '+(e.message||String(e)); el.style.display = 'block'; }
      showToast('error', '출고 현황 로드 실패');
    });
  }

  var _outboundExpandedLot = null;
  window.toggleOutboundDetail = function(lotNo) {
    var panel = document.getElementById('outbound-detail-panel');
    var content = document.getElementById('outbound-detail-content');
    var title = document.getElementById('outbound-detail-title');

    if (_outboundExpandedLot === lotNo) {
      panel.style.display = 'none';
      _outboundExpandedLot = null;
      document.querySelectorAll('.outbound-summary-row').forEach(function(r){ r.style.background=''; });
      document.querySelectorAll('.outbound-expand-icon').forEach(function(i){ i.textContent='▶'; });
      return;
    }

    _outboundExpandedLot = lotNo;
    document.querySelectorAll('.outbound-summary-row').forEach(function(r){
      if (r.dataset.lot === lotNo) {
        r.style.background = 'var(--bg-active)';
        r.querySelector('.outbound-expand-icon').textContent = '▼';
      } else {
        r.style.background = '';
        r.querySelector('.outbound-expand-icon').textContent = '▶';
      }
    });

    panel.style.display = 'block';
    title.textContent = '📤 ' + lotNo + ' 톤백 상세';
    content.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">⏳ 로딩...</div>';

    apiGet('/api/tonbags?lot_no=' + encodeURIComponent(lotNo)).then(function(res){
      var rows = extractRows(res);
      if (!rows.length) { content.innerHTML = '<div class="empty">톤백 데이터 없음</div>'; return; }
      var tbl = '<table class="data-table"><thead><tr><th>#</th><th>톤백ID</th><th>중량(kg)</th><th>위치</th><th>상태</th><th>출고일</th></tr></thead><tbody>';
      tbl += rows.map(function(r, i){
        return '<tr><td>'+(i+1)+'</td><td class="mono-cell">'+escapeHtml(r.sub_lt||r.tonbag_id||'-')+'</td><td class="mono-cell" style="text-align:right">'+(r.weight!=null?Number(r.weight).toLocaleString():'-')+'</td><td>'+escapeHtml(r.location||'-')+'</td><td><span class="tag">'+escapeHtml(r.status||'-')+'</span></td><td>'+escapeHtml(r.sold_date||r.updated_at||'-')+'</td></tr>';
      }).join('');
      tbl += '</tbody></table>';
      content.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:8px">' + rows.length + '개 톤백</p>' + tbl;
    }).catch(function(e){
      content.innerHTML = '<div class="empty">톤백 로드 실패: '+escapeHtml(e.message||'')+'</div>';
    });
  };

  /* ===================================================
     7e. PAGE: Return
     =================================================== */
  function loadReturnPage() {
    var route = window.getCurrentRoute();
    var container = document.getElementById('page-container');
    if (!container) return;
    container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-muted)">⏳ Return 재고 로딩 중...</div>';
    apiGet('/api/inventory?status=RETURN').then(function(res){
      if (window.getCurrentRoute() !== route) return;
      var rows = extractRows(res);
      renderReturnRows(rows, container);
    }).catch(function(e){
      if (window.getCurrentRoute() !== route) return;
      container.innerHTML = '<div class="empty" style="padding:60px;text-align:center">Load failed: ' + escapeHtml(String(e)) + '</div>';
    });
  }

  function renderReturnRows(rows, container) {
    if (!rows.length) {
      container.innerHTML = '<div class="empty" style="padding:60px;text-align:center;color:var(--text-muted)">🔄 반품 재고 없음</div>';
      return;
    }
    var sumBal = 0;
    rows.forEach(function(r){ if (r.balance != null) sumBal += Number(r.balance); });
    var html = '<section style="padding:12px 16px">'
      + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;flex-wrap:wrap">'
      + '<h2 style="margin:0;font-size:16px;color:#a855f7">🔄 Return 재고 — 반품 입고 · 검사 대기</h2>'
      + '<span style="font-size:12px;color:var(--text-muted)">' + rows.length + ' LOT · ' + fmtN(sumBal) + ' MT</span>'
      + '<span style="font-size:11px;color:#f59e0b;background:rgba(245,158,11,0.12);padding:2px 8px;border-radius:4px">⚠ 검사완료 후 수동으로 AVAILABLE 전환</span>'
      + '<button class="btn btn-ghost" style="font-size:12px;margin-left:auto" onclick="window.loadReturnPage()">🔄 새로고침</button>'
      + '</div>'
      + '<div style="overflow-x:auto"><table class="data-table"><thead><tr>'
      + '<th>#</th><th style="text-align:center!important">LOT</th><th style="width:32px;text-align:center">+</th><th>SAP</th><th>BL</th><th>Product</th>'
      + '<th>Balance(MT)</th><th>NET(MT)</th><th>Container</th><th>Invoice</th>'
      + '<th>Ship</th><th>Arrival</th><th>WH</th><th>Inbound(MT)</th><th>Location</th><th>검사완료</th>'
      + '</tr></thead><tbody>';
    html += rows.map(function(r, i){
      var lotKey = escapeHtml(r.lot||'');
      var hasSample = (r.sample_bags > 0);
      var sampleRow = '';
      if (hasSample) {
        sampleRow =
          '<tr style="background:rgba(234,179,8,0.08);border-left:3px solid #eab308">' +
          '<td style="text-align:center">🔬</td>' +
          '<td class="mono-cell cell-left" style="color:#eab308;font-weight:700;padding:6px 10px">' + lotKey + '(SP)</td>' +
          '<td class="mono-cell" style="color:#94a3b8">' + escapeHtml(r.sap||'') + '</td>' +
          '<td class="mono-cell" style="color:#94a3b8">' + escapeHtml(r.bl||'') + '</td>' +
          '<td><span class="tag" style="background:rgba(234,179,8,0.2);color:#eab308">' + escapeHtml(r.product||'') + '</span></td>' +
          '<td class="mono-cell" style="text-align:right;color:#eab308">' + fmtN(r.sample_weight_mt||0) + '</td>' +
          '<td colspan="8" style="color:#555;text-align:center">—</td>' +
          '<td></td>' +
          '</tr>';
      }
      var mainRow =
        '<tr style="border-left:3px solid #a855f7">'
        + '<td class="mono-cell" style="color:var(--text-muted)">' + (i+1) + '</td>'
        + '<td class="mono-cell cell-left" style="color:#a855f7;font-weight:600;padding:6px 10px">' + lotKey + '</td>'
        + '<td style="text-align:center;padding:3px 4px;width:32px">'+'<button class="btn btn-ghost btn-xs" data-lot="'+lotKey+'" onclick="window.showReturnActionMenu(this)" style="font-size:15px;padding:0 4px;letter-spacing:1px" title="추가기능">⋯</button></td>'
        + '<td class="mono-cell">' + escapeHtml(r.sap||'') + '</td>'
        + '<td class="mono-cell">' + escapeHtml(r.bl||'') + '</td>'
        + '<td><span class="tag" style="background:rgba(168,85,247,0.12);color:#a855f7">' + escapeHtml(r.product||'') + '</span></td>'
        + '<td class="mono-cell" style="text-align:right">' + (r.balance!=null?fmtN(r.balance):'-') + '</td>'
        + '<td class="mono-cell" style="text-align:right">' + (r.net!=null?fmtN(r.net):'-') + '</td>'
        + '<td class="mono-cell">' + escapeHtml(r.container||'') + '</td>'
        + '<td class="mono-cell">' + escapeHtml(r.invoice_no||'') + '</td>'
        + '<td class="mono-cell">' + escapeHtml((r.ship_date||'').slice(0,10)) + '</td>'
        + '<td class="mono-cell">' + escapeHtml((r.arrival_date||'').slice(0,10)) + '</td>'
        + '<td class="mono-cell">' + escapeHtml(r.wh||'') + '</td>'
        + '<td class="mono-cell" style="text-align:right">' + (r.initial_weight!=null?fmtN(r.initial_weight):'-') + '</td>'
        + '<td><span class="tag">' + escapeHtml(r.location||'-') + '</span></td>'
        + '<td style="white-space:nowrap;padding:4px 8px">'
          + '<button class="btn btn-ghost btn-xs" style="color:#22c55e;font-size:11px" '
          + 'data-lot="' + lotKey + '" onclick="window.returnToAvailable(this.dataset.lot)" title="검사완료 → AVAILABLE 전환">✅ 검사완료</button>'
        + '</td>'
        + '</tr>';
      return mainRow + sampleRow;
    }).join('');
    html += '</tbody></table></div></section>';
    container.innerHTML = html;
  }

  /* 반품 검사완료 → AVAILABLE 전환 */
  window.showReturnActionMenu = function(btn) {
    var lot = btn.dataset.lot || '';
    window._openContextMenu(btn, [
      { icon:'📋', label:'LOT 상세 보기',     kbd:'Enter',  fn:function(){ if(window.showLotDetail) window.showLotDetail(lot); } },
      { icon:'📄', label:'LOT 번호 복사',     kbd:'Ctrl+C', fn:function(){ navigator.clipboard&&navigator.clipboard.writeText(lot); showToast('info','LOT 복사: '+lot); } },
      '-',
      { icon:'✅', label:'검사완료 → AVAILABLE', kbd:'A', color:'#22c55e', fn:function(){
          if(!confirm('['+lot+'] 검사 완료 — AVAILABLE로 전환하시겠습니까?')) return;
          window.returnToAvailable(lot, true);
        }
      },
    ]);
  };
  window.returnToAvailable = function(lotNo, skipConfirm) {
    if (!skipConfirm && !confirm('LOT ' + lotNo + ' 검사완료 처리합니다.\nAVAILABLE로 전환하시겠습니까?')) return;
    apiPost('/api/inventory/adjust', { lot_no: lotNo, action: 'return_to_available' })
      .then(function(){ showToast('success', lotNo + ' AVAILABLE 전환 완료'); window.loadReturnPage(); })
      .catch(function(e){ showToast('error', '전환 실패: ' + (e.message||String(e))); });
  };

  /* ===================================================
     7f. PAGE: Move
     =================================================== */
  function loadMovePage() {
    var route = window.getCurrentRoute();
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="move">',
      '<h2>Move - Inventory Relocation</h2>',
      '<div class="card" style="padding:20px;margin-bottom:16px">',
      '<h3 style="margin-bottom:12px">Execute Move</h3>',
      '<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">',
      '<input id="move-barcode" class="input" placeholder="Tonbag barcode" style="width:200px">',
      '<input id="move-dest" class="input" placeholder="Destination (e.g. A-3-2)" style="width:200px">',
      '<button class="btn btn-primary" onclick="window.executeMove()">Execute Move</button>',
      '</div></div>',
      '<div id="move-loading" style="padding:20px;text-align:center">Loading history...</div>',
      '<table class="data-table" id="move-table" style="display:none">',
      '<thead><tr><th>Date</th><th>LOT No</th><th>Type</th><th>Qty(MT)</th><th>From</th><th>To</th><th>By</th></tr></thead>',
      '<tbody id="move-tbody"></tbody></table>',
      '<div class="empty" id="move-empty" style="display:none">No movement history</div>',
      '</section>'
    ].join('');
    apiGet('/api/q/movement-history').then(function(res){
      if (window.getCurrentRoute() !== route) return;
      var rows = extractRows(res);
      document.getElementById('move-loading').style.display = 'none';
      if (!rows.length) { document.getElementById('move-empty').style.display='block'; return; }
      var tbody = document.getElementById('move-tbody');
      if (tbody) tbody.innerHTML = rows.map(function(r){
        var qtyMT = r.qty_mt != null ? fmtN(r.qty_mt) : (r.qty_kg != null ? fmtN(r.qty_kg/1000) : '-');
        return '<tr>' +
          '<td class="mono-cell">'+escapeHtml(r.movement_date||r.moved_at||r.date||'')+'</td>' +
          '<td class="mono-cell" style="color:var(--accent)">'+escapeHtml(r.lot_no||r.sub_lt||r.barcode||'')+'</td>' +
          '<td>'+escapeHtml(r.movement_type||'')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+qtyMT+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.from_location||'-')+'</td>' +
          '<td class="mono-cell" style="color:var(--accent)">'+escapeHtml(r.to_location||'-')+'</td>' +
          '<td>'+escapeHtml(r.actor||r.moved_by||'system')+'</td></tr>';
      }).join('');
      document.getElementById('move-table').style.display = '';
    }).catch(function(){
      if (window.getCurrentRoute() !== route) return;
      document.getElementById('move-loading').style.display = 'none';
      document.getElementById('move-empty').style.display = 'block';
    });
  }

  window.executeMove = function() {
    var barcode = (document.getElementById('move-barcode')||{}).value||'';
    var dest = (document.getElementById('move-dest')||{}).value||'';
    if (!barcode||!dest) { showToast('warning','Enter barcode and destination'); return; }
    apiPost('/api/action/inventory-move',{barcode:barcode,destination:dest})
      .then(function(){ showToast('success',barcode+' moved to '+dest); renderPage('move'); })
      .catch(function(e){
        if (e.status===501) showToast('info','Move (coming soon)');
        else showToast('error','Move failed: '+(e.message||String(e)));
      });
  };

  /* ===================================================
     7g. PAGE: Log
     =================================================== */
  function loadLogPage() {
    var route = window.getCurrentRoute();
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="log">',
      '<h2>Log - Activity Log</h2>',
      '<div class="toolbar-mini">',
      '<button class="btn btn-secondary" onclick="renderPage(\'log\')">Refresh</button>',
      '<select id="log-limit" class="select" style="margin-left:8px" onchange="renderPage(\'log\')">',
      '<option value="100">Last 100</option>',
      '<option value="500">Last 500</option>',
      '<option value="1000">Last 1000</option>',
      '</select></div>',
      '<div id="log-loading" style="padding:40px;text-align:center">Loading...</div>',
      '<table class="data-table" id="log-table" style="display:none;table-layout:fixed;width:100%">',
      '<colgroup>',
      '<col style="width:148px">',
      '<col style="width:170px">',
      '<col style="width:130px">',
      '<col>',
      '</colgroup>',
      '<thead><tr>',
      '<th style="text-align:left;padding:5px 8px;white-space:nowrap">Time</th>',
      '<th style="text-align:left;padding:5px 8px">Type</th>',
      '<th style="text-align:left;padding:5px 8px">LOT</th>',
      '<th style="text-align:left;padding:5px 8px">Detail</th>',
      '</tr></thead>',
      '<tbody id="log-tbody"></tbody></table>',
      '<div class="empty" id="log-empty" style="display:none">No logs</div>',
      '</section>'
    ].join('');
    var limit = 100;
    try { var el=document.getElementById('log-limit'); if(el) limit=parseInt(el.value)||100; } catch {}
    apiGet('/api/q/audit-log?limit='+limit).then(function(res){
      if (window.getCurrentRoute() !== route) return;
      var rows = extractRows(res);
      document.getElementById('log-loading').style.display = 'none';
      if (!rows.length) { document.getElementById('log-empty').style.display='block'; return; }
      var tbody = document.getElementById('log-tbody');
      if (tbody) tbody.innerHTML = rows.map(function(r){
        var rawDetail = r.event_data||r.user_note||r.note||r.memo||r.detail||'';
        var fmtDetail = rawDetail;
        if (rawDetail && rawDetail.trim().startsWith('{')) {
          try {
            var parsed = JSON.parse(rawDetail);
            var parts = [];
            Object.keys(parsed).forEach(function(k){
              var v = parsed[k];
              if (v === null || v === undefined || v === '') return;
              parts.push('<b>' + escapeHtml(String(k)) + '</b>:' + escapeHtml(String(v)));
            });
            fmtDetail = parts.join('  ');
          } catch(e) { fmtDetail = escapeHtml(rawDetail); }
        } else {
          fmtDetail = escapeHtml(rawDetail);
        }
        var evtType = r.event_type||r.type||r.action||'';
        var evtColor = evtType.indexOf('ALLOC')>=0 ? '#7b1fa2'
          : evtType.indexOf('OUTBOUND')>=0 ? '#388e3c'
          : evtType.indexOf('INBOUND')>=0 ? '#1976d2'
          : evtType.indexOf('RETURN')>=0 ? '#c62828'
          : evtType.indexOf('ADJUST')>=0 ? '#f57c00'
          : 'inherit';
        return '<tr style="font-size:12px">' +
          '<td class="mono-cell" style="padding:4px 8px;white-space:nowrap;text-align:left;font-size:11px;color:var(--text-muted)">'+escapeHtml(r.created_at||r.time||r.timestamp||'')+'</td>' +
          '<td style="padding:4px 8px;text-align:left;white-space:nowrap;font-weight:600;color:'+evtColor+'">'+escapeHtml(evtType)+'</td>' +
          '<td class="mono-cell" style="padding:4px 8px;text-align:left;font-size:11px;color:var(--accent)">'+escapeHtml(r.lot_no||r.lot||r.tonbag_id||'')+'</td>' +
          '<td style="padding:4px 8px;text-align:left;word-break:break-all;line-height:1.4;font-size:11px">'+fmtDetail+'</td></tr>';
      }).join('');
      document.getElementById('log-table').style.display = '';
    }).catch(function(e){
      if (window.getCurrentRoute() !== route) return;
      document.getElementById('log-loading').style.display = 'none';
      var el=document.getElementById('log-empty');
      if (el) { el.textContent='Load failed: '+(e.message||String(e)); el.style.display='block'; }
    });
  }

  /* ===================================================
     7h. PAGE: Scan + PDF Upload
     =================================================== */
  function loadScanPage() {
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="scan">',
      '<h2>Scan - Barcode / PDF Inbound</h2>',
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">',

      '<!-- Barcode Panel -->',
      '<div class="card" style="padding:20px">',
      '<h3 style="margin-bottom:12px">Barcode Scan</h3>',
      '<input id="scan-input" class="input" placeholder="Scan or type barcode + Enter" style="width:100%;margin-bottom:12px">',
      '<div style="display:flex;gap:8px;margin-bottom:16px">',
      '<button class="btn btn-primary btn-sm" onclick="window.ScanActions.quickAction(\'inbound\')">Inbound</button>',
      '<button class="btn btn-warning btn-sm" onclick="window.ScanActions.quickAction(\'outbound\')">Outbound</button>',
      '<button class="btn btn-secondary btn-sm" onclick="window.ScanActions.quickAction(\'move\')">Move</button>',
      '</div>',
      '<table class="data-table"><thead><tr><th>Time</th><th>Barcode</th><th>Action</th><th>Result</th></tr></thead>',
      '<tbody id="scan-history-tbody"><tr><td colspan="4" style="text-align:center;padding:20px;color:var(--text-muted)">No scan history</td></tr></tbody></table>',
      '</div>',

      '<!-- PDF Panel -->',
      '<div class="card" style="padding:20px">',
      '<h3 style="margin-bottom:12px">PDF Inbound</h3>',
      '<div id="pdf-drop-zone" style="border:2px dashed var(--border);border-radius:8px;padding:40px;text-align:center;cursor:pointer;color:var(--text-muted)" onclick="document.getElementById(\'pdf-file-input\').click()" ondragover="event.preventDefault();this.style.borderColor=\'var(--accent)\'" ondragleave="this.style.borderColor=\'var(--border)\'" ondrop="window.PdfInbound.handleDrop(event)">',
      '<div style="font-size:2rem">&#x1F4C4;</div>',
      '<div style="margin-top:8px">Drag PDF here or click to select</div>',
      '<div style="font-size:0.8rem;margin-top:4px;color:var(--text-muted)">Picking List / BL / Inbound PDF</div>',
      '</div>',
      '<input type="file" id="pdf-file-input" accept=".pdf" style="display:none" onchange="window.PdfInbound.handleFile(this.files[0])">',
      '<div id="pdf-status" style="margin-top:12px;color:var(--text-muted);font-size:0.9rem"></div>',
      '<button class="btn btn-primary" id="pdf-upload-btn" style="display:none;margin-top:8px" onclick="window.PdfInbound.upload()">Upload &amp; Process</button>',
      '</div>',

      '</div></section>'
    ].join('');

    var inp = document.getElementById('scan-input');
    if (inp) {
      inp.addEventListener('keydown', function(e){
        if (e.key==='Enter') {
          e.preventDefault();
          window.ScanActions.processBarcode(inp.value.trim());
          inp.value='';
        }
      });
      inp.focus();
    }
  }

  var _scanHistory = [];
  window.ScanActions = {
    _lastBarcode: '',
    processBarcode: function(barcode, action) {
      if (!barcode) return;
      window.ScanActions._lastBarcode = barcode;
      if (!action) { showToast('info','Scanned: '+barcode+' - select action button'); return; }
      apiPost('/api/scan/process',{barcode:barcode,action:action})
        .then(function(res){
          var ok = res.success !== false;
          showToast(ok?'success':'error', res.message||(ok?'Done':'Failed'));
          window.ScanActions._addHist(barcode, action, ok);
        })
        .catch(function(e){
          if (e.status===501) showToast('info','Scan (coming soon)');
          else showToast('error','Scan error: '+(e.message||String(e)));
          window.ScanActions._addHist(barcode, action, false);
        });
    },
    quickAction: function(action) {
      var inp = document.getElementById('scan-input');
      var bc = (inp?inp.value.trim():'')||window.ScanActions._lastBarcode;
      if (!bc) { showToast('warning','Scan barcode first'); return; }
      window.ScanActions.processBarcode(bc, action);
      if (inp) inp.value='';
    },
    _addHist: function(barcode, action, ok) {
      var now = new Date();
      var t = [now.getHours(),now.getMinutes(),now.getSeconds()].map(function(n){return String(n).padStart(2,'0');}).join(':');
      _scanHistory.unshift({time:t,barcode:barcode,action:action,ok:ok});
      if (_scanHistory.length>100) _scanHistory.pop();
      var tbody = document.getElementById('scan-history-tbody');
      if (tbody) tbody.innerHTML = _scanHistory.slice(0,20).map(function(h){
        return '<tr><td class="mono-cell">'+h.time+'</td><td class="mono-cell">'+escapeHtml(h.barcode)+'</td><td>'+escapeHtml(h.action)+'</td><td>'+(h.ok?'<span style="color:var(--status-available)">OK</span>':'<span style="color:var(--status-return)">FAIL</span>')+'</td></tr>';
      }).join('');
    }
  };

  var _pdfFile=null, _pdfB64=null;
  window.PdfInbound = {
    handleDrop: function(e) {
      e.preventDefault();
      var dz = document.getElementById('pdf-drop-zone');
      if (dz) dz.style.borderColor='var(--border)';
      var f = e.dataTransfer.files[0];
      if (f) window.PdfInbound.handleFile(f);
    },
    handleFile: function(f) {
      if (!f||!f.name.toLowerCase().endsWith('.pdf')) { showToast('error','PDF files only'); return; }
      _pdfFile = f;
      var status=document.getElementById('pdf-status');
      var btn=document.getElementById('pdf-upload-btn');
      if (status) status.textContent='Selected: '+f.name+' ('+(f.size/1024).toFixed(1)+' KB)';
      var reader=new FileReader();
      reader.onload=function(ev){ _pdfB64=ev.target.result.split(',')[1]; if(btn) btn.style.display=''; };
      reader.readAsDataURL(f);
    },
    upload: function() {
      if (!_pdfB64) { showToast('warning','Select a PDF first'); return; }
      var status=document.getElementById('pdf-status');
      var btn=document.getElementById('pdf-upload-btn');
      if (status) status.textContent='Uploading...';
      if (btn) btn.disabled=true;
      apiPost('/api/inbound/pdf',{pdf_base64:_pdfB64,filename:(_pdfFile?_pdfFile.name:'upload.pdf')})
        .then(function(res){
          showToast('success','PDF inbound done: '+(res.message||'OK'));
          if (status) status.textContent='Done: '+(res.message||'Success');
          if (btn) { btn.style.display='none'; btn.disabled=false; }
          _pdfB64=null; _pdfFile=null;
        })
        .catch(function(e){
          if (e.status===501) showToast('info','PDF inbound (coming soon)');
          else showToast('error','Upload failed: '+(e.message||String(e)));
          if (status) status.textContent='Failed: '+(e.message||String(e));
          if (btn) btn.disabled=false;
        });
    }
  };

  /* ===================================================
     7i. PAGE: Tonbag
     =================================================== */

  window.loadInboundPage   = loadInboundPage;
  window.loadOutboundPage  = loadOutboundPage;
  window.loadReturnPage    = loadReturnPage;
  window.loadMovePage      = loadMovePage;
  window.loadLogPage       = loadLogPage;
  window.loadScanPage      = loadScanPage;
})();
