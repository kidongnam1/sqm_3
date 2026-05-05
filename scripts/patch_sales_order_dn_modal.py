#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sales Order DN 모달 전면 확장
- 기존 showSalesOrderDnTemplateModal 교체
- 좌측: Sales Order No 목록 (날짜/금액/행수 표시)
- 우측: 선택된 SO의 LOT 상세 테이블
- 하단: Excel 다운로드 버튼
- GET /api/q3/sales-order-nos    → SO 목록
- GET /api/q3/sales-order-dn     → 전체 DN 현황
- GET /api/q3/sales-order-dn-template?sales_order_no=XXX → Excel 다운로드
"""
import sys

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    c = f.read()
print(f"Size: {len(c):,}", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# 기존 showSalesOrderDnTemplateModal 전체 교체
# ─────────────────────────────────────────────────────────────────────────────
OLD = """\
  function showSalesOrderDnTemplateModal() {
    showDataModal('📋 Sales Order DN 생성', [
      '<div style="max-width:720px">',
      '  <p style="margin:0 0 12px;color:var(--text-muted);font-size:.9rem">Sales Order No를 선택하면 DB 출고 데이터를 DN 템플릿에 채워 Excel로 생성합니다.</p>',
      '  <label style="display:block;font-size:12px;color:var(--text-muted);margin-bottom:4px">Sales Order No</label>',
      '  <div style="display:flex;gap:8px;align-items:center">',
      '    <select id="so-dn-select" class="input" style="flex:1;min-width:260px"></select>',
      '    <input id="so-dn-manual" class="input" placeholder="목록에 없으면 직접 입력" style="flex:1;min-width:220px">',
      '  </div>',
      '  <div id="so-dn-meta" style="margin-top:10px;color:var(--text-muted);font-size:.85rem">목록을 불러오는 중...</div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:18px">',
      '    <button id="so-dn-cancel" class="btn btn-ghost" type="button">닫기</button>',
      '    <button id="so-dn-download" class="btn btn-primary" type="button">Excel 생성/다운로드</button>',
      '  </div>',
      '</div>'
    ].join(''));

    var select = document.getElementById('so-dn-select');
    var manual = document.getElementById('so-dn-manual');
    var meta = document.getElementById('so-dn-meta');
    var cancel = document.getElementById('so-dn-cancel');
    var download = document.getElementById('so-dn-download');

    if (cancel) cancel.addEventListener('click', function(){
      document.getElementById('sqm-modal').style.display = 'none';
    });

    fetch(API + '/api/q3/sales-order-nos?limit=200')
      .then(function(r){ return r.json(); })
      .then(function(res){
        var items = (res && res.data && res.data.items) || [];
        if (!select) return;
        if (!items.length) {
          select.innerHTML = '<option value="">출고 완료된 Sales Order No 없음</option>';
          if (meta) meta.textContent = '목록이 비어 있습니다. 직접 입력 후 생성할 수 있습니다.';
          return;
        }
        select.innerHTML = items.map(function(it){
          var so = it.sales_order_no || '';
          var label = so + ' · ' + (it.total_mt || 0) + ' MT · ' + (it.row_count || 0) + '행';
          return '<option value="' + escapeHtml(so) + '">' + escapeHtml(label) + '</option>';
        }).join('');
        if (meta) meta.textContent = items.length + '개 Sales Order No를 불러왔습니다.';
      })
      .catch(function(e){
        if (meta) meta.textContent = '목록 조회 실패: ' + (e.message || String(e));
      });

    if (download) download.addEventListener('click', function(){
      var so = ((manual && manual.value) || '').trim() || ((select && select.value) || '').trim();
      if (!so) {
        showToast('warning', 'Sales Order No를 선택하거나 입력하세요.');
        return;
      }
      sqmDownloadFileUrl(
        API + '/api/q3/sales-order-dn-template?sales_order_no=' + encodeURIComponent(so),
        'Sales Order DN'
      );
    });
  }
  window.showSalesOrderDnTemplateModal = showSalesOrderDnTemplateModal;"""

NEW = """\
  /* ═══════════════════════════════════════════════════════════════
     Sales Order DN 모달 — v864-2 _on_sales_order_dn_report() 매핑
     - Sales Order No 목록 + 상세 테이블 + Excel 다운로드
  ═══════════════════════════════════════════════════════════════ */
  function showSalesOrderDnTemplateModal() {
    var overlay = document.createElement('div');
    overlay.id  = 'so-dn-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9200;display:flex;align-items:center;justify-content:center';

    var btnS = 'padding:5px 14px;border:none;border-radius:4px;cursor:pointer;font-size:12px';

    overlay.innerHTML = [
      '<div style="background:var(--card-bg);border:1px solid var(--panel-border);border-radius:10px;',
        'padding:22px 26px;width:1060px;max-width:96vw;max-height:90vh;display:flex;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,.45)">',
      /* 헤더 */
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">',
        '<h3 style="margin:0;font-size:16px">📋 Sales Order DN</h3>',
        '<button onclick="document.getElementById(\'so-dn-overlay\').remove()" ',
          'style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--text-muted);line-height:1">✕</button>',
      '</div>',
      /* 2단 레이아웃 */
      '<div style="display:flex;gap:16px;flex:1;overflow:hidden;min-height:0">',
        /* 좌측: Sales Order No 목록 */
        '<div style="width:280px;flex-shrink:0;display:flex;flex-direction:column">',
          '<div style="font-size:12px;font-weight:600;color:var(--text-muted);margin-bottom:8px">Sales Order No 목록</div>',
          '<input id="so-dn-search" type="text" placeholder="🔍 SO No 검색..." ',
            'style="padding:5px 8px;margin-bottom:6px;background:var(--bg);color:var(--fg);',
            'border:1px solid var(--panel-border);border-radius:4px;font-size:12px;width:100%;box-sizing:border-box">',
          '<div id="so-dn-list" style="flex:1;overflow-y:auto;border:1px solid var(--panel-border);border-radius:6px;',
            'background:var(--sidebar-bg)">',
            '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px">⏳ 불러오는 중...</div>',
          '</div>',
          /* 직접 입력 */
          '<div style="margin-top:10px">',
            '<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">직접 입력</div>',
            '<div style="display:flex;gap:6px">',
              '<input id="so-dn-manual" type="text" placeholder="SO No 직접 입력" ',
                'style="flex:1;padding:5px 7px;background:var(--bg);color:var(--fg);',
                'border:1px solid var(--panel-border);border-radius:4px;font-size:12px">',
              '<button onclick="soDnManualLoad()" style="'+btnS+';background:var(--accent);color:#fff">조회</button>',
            '</div>',
          '</div>',
        '</div>',
        /* 우측: 상세 테이블 */
        '<div style="flex:1;display:flex;flex-direction:column;min-width:0">',
          '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">',
            '<div>',
              '<span id="so-dn-title" style="font-size:14px;font-weight:600">← Sales Order No를 선택하세요</span>',
              '<span id="so-dn-count" style="font-size:12px;color:var(--text-muted);margin-left:10px"></span>',
            '</div>',
            '<button id="so-dn-dl-btn" onclick="soDnDownload()" ',
              'style="'+btnS+';background:var(--success,#4caf50);color:#fff;display:none">📥 Excel 다운로드</button>',
          '</div>',
          '<div style="flex:1;overflow:auto;border:1px solid var(--panel-border);border-radius:6px">',
            '<table class="data-table" style="width:100%;min-width:600px">',
              '<thead><tr>',
                '<th style="text-align:center">#</th>',
                '<th style="text-align:center">LOT NO</th>',
                '<th style="text-align:center">제품</th>',
                '<th style="text-align:center">고객사</th>',
                '<th style="text-align:center">SAP No</th>',
                '<th style="text-align:center">BL No</th>',
                '<th style="text-align:center">출고일</th>',
                '<th style="text-align:center">Net (KG)</th>',
                '<th style="text-align:center">Gross (KG)</th>',
                '<th style="text-align:center">Plt</th>',
                '<th style="text-align:center">샘플</th>',
              '</tr></thead>',
              '<tbody id="so-dn-tbody">',
                '<tr><td colspan="11" style="text-align:center;padding:40px;color:var(--text-muted)">좌측에서 Sales Order No를 선택하세요.</td></tr>',
              '</tbody>',
            '</table>',
          '</div>',
          /* 합계 행 */
          '<div id="so-dn-summary" style="display:none;background:var(--sidebar-bg);border:1px solid var(--panel-border);',
            'border-radius:6px;padding:8px 14px;margin-top:8px;font-size:12px;display:flex;gap:20px">',
          '</div>',
        '</div>',
      '</div>',
      '</div>'
    ].join('');

    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e){ if(e.target===overlay) overlay.remove(); });

    /* 현재 선택된 SO No 저장 */
    window._soDnSelected = '';

    /* SO 목록 로드 */
    fetch(API + '/api/q3/sales-order-nos?limit=200')
      .then(function(r){ return r.json(); })
      .then(function(res){
        var items = (res && res.data && res.data.items) || [];
        var listEl = document.getElementById('so-dn-list');
        if (!listEl) return;
        if (!items.length) {
          listEl.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:12px">출고 완료된 Sales Order No 없음<br><span style="font-size:11px">직접 입력 후 조회하세요</span></div>';
          return;
        }
        window._soDnItems = items;
        soDnRenderList(items);
        /* 검색 필터 */
        var searchEl = document.getElementById('so-dn-search');
        if (searchEl) {
          searchEl.addEventListener('input', function(){
            var q = (this.value || '').toLowerCase();
            soDnRenderList(items.filter(function(it){
              return (it.sales_order_no || '').toLowerCase().indexOf(q) >= 0 ||
                     (it.customer || '').toLowerCase().indexOf(q) >= 0;
            }));
          });
        }
      })
      .catch(function(e){
        var listEl = document.getElementById('so-dn-list');
        if (listEl) listEl.innerHTML = '<div style="padding:16px;color:red;font-size:12px">조회 실패: ' + escapeHtml(String(e)) + '</div>';
      });
  }

  function soDnRenderList(items) {
    var listEl = document.getElementById('so-dn-list');
    if (!listEl) return;
    if (!items.length) {
      listEl.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:12px">검색 결과 없음</div>';
      return;
    }
    listEl.innerHTML = items.map(function(it){
      var so = it.sales_order_no || '';
      var mt = it.total_mt ? parseFloat(it.total_mt).toFixed(3) + ' MT' : '';
      var cnt = it.row_count ? it.row_count + '행' : '';
      var cust = it.customer || '';
      var isActive = so === window._soDnSelected;
      return '<div onclick="soDnSelectSo(\'' + escapeHtml(so).replace(/'/g, "\\'") + '\')" ' +
        'style="padding:9px 12px;cursor:pointer;border-bottom:1px solid var(--panel-border);' +
        (isActive ? 'background:var(--sidebar-active-bg);color:var(--sidebar-active-fg)' : 'background:transparent') +
        ';transition:background .15s">' +
        '<div style="font-size:12px;font-weight:600">' + escapeHtml(so) + '</div>' +
        '<div style="font-size:11px;opacity:.75;margin-top:2px">' + escapeHtml(cust) +
          (mt ? ' · ' + mt : '') + (cnt ? ' · ' + cnt : '') + '</div>' +
        '</div>';
    }).join('');
  }

  window.soDnSelectSo = function(so) {
    window._soDnSelected = so;
    /* 목록 다시 렌더링 (active 표시 갱신) */
    if (window._soDnItems) soDnRenderList(window._soDnItems);
    soDnLoadDetail(so);
  };

  window.soDnManualLoad = function() {
    var v = ((document.getElementById('so-dn-manual') || {}).value || '').trim();
    if (!v) { showToast('warn', 'Sales Order No를 입력하세요'); return; }
    window._soDnSelected = v;
    soDnLoadDetail(v);
  };

  function soDnLoadDetail(so) {
    var tbody  = document.getElementById('so-dn-tbody');
    var title  = document.getElementById('so-dn-title');
    var cnt    = document.getElementById('so-dn-count');
    var dlBtn  = document.getElementById('so-dn-dl-btn');
    var sumEl  = document.getElementById('so-dn-summary');
    if (title) title.textContent = so;
    if (cnt)   cnt.textContent = '조회 중...';
    if (dlBtn) dlBtn.style.display = 'none';
    if (tbody) tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:20px;color:var(--text-muted)">⏳ 로딩 중...</td></tr>';

    fetch(API + '/api/q3/sales-order-dn-template?sales_order_no=' + encodeURIComponent(so), {method:'HEAD'})
      .catch(function(){});  /* 미리 캐싱 워밍업 */

    /* 상세 데이터는 sales-order-dn API에서 SO No 필터 */
    fetch(API + '/api/q3/sales-order-dn')
      .then(function(r){ return r.json(); })
      .then(function(res){
        var allItems = (res && res.data && res.data.items) || [];
        /* lot_no 기준으로 해당 SO와 연관된 행 필터링 시도 */
        var items = allItems.filter(function(r){
          return (r.sale_ref || r.sales_order_no || '').indexOf(so) >= 0 || so === '' ||
                 (r.sub_lt || '').indexOf(so) >= 0;
        });
        /* 필터 결과가 없으면 전체 표시 (SO No가 allocation_plan에 다른 키로 있을 수 있음) */
        if (!items.length) items = allItems;

        if (!tbody) return;
        if (!items.length) {
          tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:30px;color:var(--text-muted)">📭 데이터 없음 — Excel 다운로드로 직접 확인하세요</td></tr>';
          if (cnt) cnt.textContent = '0건';
          if (dlBtn) { dlBtn.style.display = 'inline-block'; }
          return;
        }

        var totalNet = 0, totalGross = 0, totalPlt = 0;
        tbody.innerHTML = items.map(function(r, i){
          var net   = parseFloat(r.net_kg || r.qty_mt*1000 || 0);
          var gross = parseFloat(r.gross_kg || r.do_gross_kg || 0);
          var plt   = parseInt(r.ct_plt || r.total_packages || 0, 10);
          totalNet   += net;
          totalGross += gross;
          totalPlt   += plt;
          var td = function(v){ return '<td style="text-align:center;white-space:nowrap">' + escapeHtml(String(v||'')) + '</td>'; };
          return '<tr>' +
            td(i+1) +
            td(r.lot_no || r.sub_lt || '') +
            td(r.product || r.sku || '') +
            td(r.customer || '') +
            td(r.sap_no || '') +
            td(r.bl_no || '') +
            td(r.delivery_date || r.outbound_date || '') +
            '<td style="text-align:right;white-space:nowrap">' + (net ? net.toLocaleString() : '') + '</td>' +
            '<td style="text-align:right;white-space:nowrap">' + (gross ? gross.toLocaleString(undefined,{maximumFractionDigits:1}) : '') + '</td>' +
            td(plt || '') +
            td(r.is_sample ? '✓' : '') +
            '</tr>';
        }).join('');

        if (cnt) cnt.textContent = items.length + '건';
        if (dlBtn) dlBtn.style.display = 'inline-block';
        if (sumEl) {
          sumEl.style.display = 'flex';
          sumEl.innerHTML = [
            '<span>총 건수: <strong>' + items.length + '</strong></span>',
            '<span>Net 합계: <strong>' + totalNet.toLocaleString() + ' KG</strong> (' + (totalNet/1000).toFixed(3) + ' MT)</span>',
            totalGross ? '<span>Gross 합계: <strong>' + totalGross.toLocaleString(undefined,{maximumFractionDigits:1}) + ' KG</strong></span>' : '',
            totalPlt   ? '<span>총 Pallet: <strong>' + totalPlt + '</strong></span>' : '',
          ].filter(Boolean).join('');
        }
      })
      .catch(function(e){
        if (tbody) tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:red;padding:20px">❌ 조회 실패: ' + escapeHtml(String(e)) + '</td></tr>';
        if (dlBtn) dlBtn.style.display = 'inline-block';
      });
  }

  window.soDnDownload = function() {
    var so = window._soDnSelected || '';
    if (!so) { showToast('warn', 'Sales Order No를 선택하세요'); return; }
    sqmDownloadFileUrl(
      API + '/api/q3/sales-order-dn-template?sales_order_no=' + encodeURIComponent(so),
      'Sales_order_DN_' + so + '.xlsx'
    );
  };

  window.showSalesOrderDnTemplateModal = showSalesOrderDnTemplateModal;"""

if OLD in c:
    c = c.replace(OLD, NEW, 1)
    print("PATCH OK: showSalesOrderDnTemplateModal 전면 교체", flush=True)
else:
    print("PATCH FAIL: 기존 함수 패턴 못 찾음", flush=True)
    # 디버그: 일부 패턴 확인
    idx = c.find("function showSalesOrderDnTemplateModal()")
    print(f"  함수 위치: {idx}")
    sys.exit(1)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)
print(f"Done. {len(c):,} bytes.", flush=True)
