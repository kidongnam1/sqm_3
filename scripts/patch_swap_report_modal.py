#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Swap 리포트 웹 모달 구현
1. ENDPOINTS: onSwapReport → JS 'swap-report-modal' 로 변경
2. dispatchAction: swap-report-modal 분기 추가
3. showSwapReportModal() 함수 삽입
   - 기간/고객사/LOT/작업자 필터
   - GET /api/action2/swap-report 조회
   - 결과 테이블 표시
   - Excel 내보내기 버튼 → GET /api/action2/swap-report/export
"""
import sys

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    c = f.read()
print(f"Size: {len(c):,}", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1: ENDPOINTS 테이블 — onSwapReport 수정
# ─────────────────────────────────────────────────────────────────────────────
OLD1 = "    'onSwapReport':        {m:'GET', u:'/api/action2/swap-report',                 lbl:'Swap 보고서'},"
NEW1 = "    'onSwapReport':        {m:'JS',  u:'swap-report-modal',                        lbl:'Swap 리포트'},"

if OLD1 in c:
    c = c.replace(OLD1, NEW1, 1)
    print("PATCH 1 OK: onSwapReport → JS 핸들러로 변경", flush=True)
else:
    print("PATCH 1 FAIL", flush=True); sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2: dispatchAction — swap-report-modal 분기 추가
#   fix-lot-integrity 분기 바로 뒤에 삽입
# ─────────────────────────────────────────────────────────────────────────────
OLD2 = (
    "      if (conf.u === 'fix-lot-integrity') {\n"
    "        showFixLotIntegrityModal();\n"
    "        return;\n"
    "      }"
)
NEW2 = (
    "      if (conf.u === 'fix-lot-integrity') {\n"
    "        showFixLotIntegrityModal();\n"
    "        return;\n"
    "      }\n"
    "      if (conf.u === 'swap-report-modal') {\n"
    "        showSwapReportModal();\n"
    "        return;\n"
    "      }"
)

if OLD2 in c:
    c = c.replace(OLD2, NEW2, 1)
    print("PATCH 2 OK: dispatchAction 분기 추가", flush=True)
else:
    print("PATCH 2 FAIL", flush=True); sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 3: showSwapReportModal 함수 삽입
#   showFixLotIntegrityModal 바로 앞에 삽입
# ─────────────────────────────────────────────────────────────────────────────
ANCHOR3 = "  function _fixLotIntegrityClose()"
SWAP_FUNC = r"""  /* ═══════════════════════════════════════════════════════════════
     Swap 리포트 모달 — v864-2 _show_swap_report_dialog() 매핑
     GET /api/action2/swap-report?start_date=&end_date=&customer=&lot_no=&operator=
     GET /api/action2/swap-report/export?fmt=xlsx
  ═══════════════════════════════════════════════════════════════ */
  function showSwapReportModal() {
    /* 오늘 날짜 기본값 */
    var today = new Date();
    function fmt(d) {
      return d.getFullYear() + '-' +
        String(d.getMonth()+1).padStart(2,'0') + '-' +
        String(d.getDate()).padStart(2,'0');
    }
    var d30 = new Date(today); d30.setDate(d30.getDate() - 30);
    var defStart = fmt(d30);
    var defEnd   = fmt(today);

    var overlay = document.createElement('div');
    overlay.id  = 'swap-report-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9100;display:flex;align-items:center;justify-content:center';

    var inp = 'width:120px;padding:4px 6px;background:var(--bg);color:var(--fg);border:1px solid var(--panel-border);border-radius:4px;font-size:12px;font-family:inherit';
    var inpW = 'width:150px;padding:4px 6px;background:var(--bg);color:var(--fg);border:1px solid var(--panel-border);border-radius:4px;font-size:12px;font-family:inherit';
    var btnS = 'padding:5px 14px;border:none;border-radius:4px;cursor:pointer;font-size:12px';

    overlay.innerHTML = [
      '<div style="background:var(--card-bg);border:1px solid var(--panel-border);border-radius:10px;',
        'padding:22px 26px;width:900px;max-width:95vw;max-height:88vh;display:flex;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,.45)">',
      /* 헤더 */
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">',
        '<h3 style="margin:0;font-size:16px">🔁 Swap 리포트</h3>',
        '<button onclick="document.getElementById(\'swap-report-overlay\').remove()" ',
          'style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--text-muted);line-height:1">✕</button>',
      '</div>',
      /* 조회 조건 */
      '<div style="background:var(--sidebar-bg);border:1px solid var(--panel-border);border-radius:6px;padding:12px 16px;margin-bottom:12px">',
        '<div style="font-size:12px;color:var(--text-muted);font-weight:600;margin-bottom:10px">조회 조건</div>',
        '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">',
          '<label style="font-size:12px">시작일<br><input id="sr-start" type="date" value="'+defStart+'" style="'+inp+'"></label>',
          '<label style="font-size:12px">종료일<br><input id="sr-end"   type="date" value="'+defEnd+'"   style="'+inp+'"></label>',
          '<label style="font-size:12px">고객사<br><input id="sr-cust"  type="text" placeholder="전체"   style="'+inpW+'"></label>',
          '<label style="font-size:12px">LOT NO<br><input id="sr-lot"   type="text" placeholder="전체"   style="'+inpW+'"></label>',
          '<label style="font-size:12px">작업자<br><input id="sr-op"    type="text" placeholder="전체"   style="'+inpW+'"></label>',
          '<div style="margin-top:14px">',
            '<button onclick="swapReportSearch()" style="'+btnS+';background:var(--accent);color:#fff">🔍 조회</button>',
          '</div>',
        '</div>',
      '</div>',
      /* 카운트 + 내보내기 */
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">',
        '<span id="sr-count" style="font-size:12px;color:var(--text-muted)">— 건</span>',
        '<button onclick="swapReportExport()" style="'+btnS+';background:var(--success,#4caf50);color:#fff">📥 Excel 내보내기</button>',
      '</div>',
      /* 테이블 */
      '<div style="overflow:auto;flex:1;border:1px solid var(--panel-border);border-radius:6px">',
        '<table class="data-table" id="sr-table" style="width:100%;min-width:720px">',
          '<thead><tr>',
            '<th style="text-align:center;white-space:nowrap">#</th>',
            '<th style="text-align:center;white-space:nowrap">SWAP_AT</th>',
            '<th style="text-align:center;white-space:nowrap">LOT NO</th>',
            '<th style="text-align:center;white-space:nowrap">CUSTOMER</th>',
            '<th style="text-align:center;white-space:nowrap">OPERATOR</th>',
            '<th style="text-align:center;white-space:nowrap">EXPECTED UID</th>',
            '<th style="text-align:center;white-space:nowrap">SCANNED UID</th>',
            '<th style="text-align:center;white-space:nowrap">REASON</th>',
          '</tr></thead>',
          '<tbody id="sr-tbody"><tr><td colspan="8" style="text-align:center;padding:30px;color:var(--text-muted)">조회 조건을 입력하고 [🔍 조회]를 누르세요.</td></tr></tbody>',
        '</table>',
      '</div>',
      '</div>'
    ].join('');

    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e){ if(e.target===overlay) overlay.remove(); });
  }

  window.swapReportSearch = function() {
    var start  = (document.getElementById('sr-start') || {}).value || '';
    var end    = (document.getElementById('sr-end')   || {}).value || '';
    var cust   = (document.getElementById('sr-cust')  || {}).value || '';
    var lot    = (document.getElementById('sr-lot')   || {}).value || '';
    var op     = (document.getElementById('sr-op')    || {}).value || '';

    if (!start || !end) { showToast('warn','시작일과 종료일을 입력하세요'); return; }

    var tbody = document.getElementById('sr-tbody');
    var cnt   = document.getElementById('sr-count');
    if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-muted)">⏳ 조회 중...</td></tr>';
    if (cnt)   cnt.textContent = '조회 중...';

    var url = API + '/api/action2/swap-report?start_date=' + encodeURIComponent(start) +
              '&end_date=' + encodeURIComponent(end) +
              '&customer=' + encodeURIComponent(cust) +
              '&lot_no='   + encodeURIComponent(lot)  +
              '&operator=' + encodeURIComponent(op);

    fetch(url)
      .then(function(r){ return r.json(); })
      .then(function(res){
        var rows = (res.data && res.data.rows) || [];
        if (cnt) cnt.textContent = rows.length + '건';
        if (!tbody) return;
        if (!rows.length) {
          tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:30px;color:var(--text-muted)">📭 조회 결과 없음</td></tr>';
          return;
        }
        tbody.innerHTML = rows.map(function(r, i){
          var td = function(v){ return '<td style="text-align:center;white-space:nowrap">' + escapeHtml(String(v||'')) + '</td>'; };
          return '<tr>' +
            td(i+1) + td(r.created_at) + td(r.lot_no) + td(r.customer) + td(r.operator) +
            '<td style="text-align:center;font-family:monospace;font-size:11px">' + escapeHtml(String(r.expected_uid||'')) + '</td>' +
            '<td style="text-align:center;font-family:monospace;font-size:11px">' + escapeHtml(String(r.scanned_uid||'')) + '</td>' +
            td(r.reason) + '</tr>';
        }).join('');
      })
      .catch(function(e){
        if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:red;padding:20px">❌ 조회 실패: ' + escapeHtml(String(e)) + '</td></tr>';
        showToast('error','Swap 리포트 조회 실패');
      });
  };

  window.swapReportExport = function() {
    var start  = (document.getElementById('sr-start') || {}).value || '';
    var end    = (document.getElementById('sr-end')   || {}).value || '';
    var cust   = (document.getElementById('sr-cust')  || {}).value || '';
    var lot    = (document.getElementById('sr-lot')   || {}).value || '';
    var op     = (document.getElementById('sr-op')    || {}).value || '';
    if (!start || !end) { showToast('warn','시작일과 종료일을 입력하세요'); return; }
    var url = API + '/api/action2/swap-report/export?fmt=xlsx&start_date=' + encodeURIComponent(start) +
              '&end_date=' + encodeURIComponent(end) +
              '&customer=' + encodeURIComponent(cust) +
              '&lot_no='   + encodeURIComponent(lot)  +
              '&operator=' + encodeURIComponent(op);
    sqmDownloadFileUrl(url, 'Swap_리포트_' + start + '_' + end + '.xlsx');
  };

"""

if ANCHOR3 in c:
    c = c.replace(ANCHOR3, SWAP_FUNC + "  function _fixLotIntegrityClose()", 1)
    print("PATCH 3 OK: showSwapReportModal 삽입", flush=True)
else:
    print("PATCH 3 FAIL: 앵커 못 찾음", flush=True); sys.exit(1)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)
print(f"Done. {len(c):,} bytes.", flush=True)
