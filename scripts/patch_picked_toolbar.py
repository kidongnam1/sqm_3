# -*- coding: utf-8 -*-
"""Picked 탭 툴바 복구 (취소/전체선택/Excel 버튼 추가)"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    c = f.read()

OLD = """  function loadPickedPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class=\"page\" data-page=\"picked\">',
      '<div style=\"display:flex;align-items:center;gap:12px;padding:8px 0 12px\">',
      '  <h2 style=\"margin:0\">🚛 Picked - 피킹 완료 (화물 결정)</h2>',
      '  <button class=\"btn btn-secondary\" onclick=\"renderPage(\'picked\')\" style=\"margin-left:auto\">🔁 새로고침</button>',
      '</div>',
      '<div id=\"picked-loading\" style=\"padding:40px;text-align:center;color:var(--text-muted)\">⏳ 데이터 로딩 중...</div>',
      '<div style=\"overflow-x:auto\">',
      '  <table class=\"data-table\" id=\"picked-table\" style=\"display:none\">',
      '  <thead><tr><th></th><th>LOT No</th><th>피킹No</th><th>고객사</th><th>톤백수</th><th>중량(kg)</th><th>피킹일</th></tr></thead>',
      '  <tbody id=\"picked-tbody\"></tbody>',
      '  </table>',
      '</div>',
      '<div class=\"empty\" id=\"picked-empty\" style=\"display:none;padding:60px;text-align:center\">📭 피킹 데이터 없음</div>',
      '<div id=\"picked-detail-panel\" style=\"display:none;margin-top:16px;border-top:2px solid var(--border);padding-top:16px\">',
      '  <h3 id=\"picked-detail-title\" style=\"margin:0 0 12px 0\">톤백 상세</h3>',
      '  <div id=\"picked-detail-content\"></div>',
      '</div>',
      '</section>'
    ].join('');"""

NEW = """  function loadPickedPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class=\"page\" data-page=\"picked\">',
      '<div style=\"display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:8px 0 10px;border-bottom:1px solid var(--border);margin-bottom:8px\">',
      '  <span style=\"font-weight:700;font-size:15px\">🚛 판매화물 결정 LOT 리스트</span>',
      '  <button class=\"btn btn-secondary btn-sm\" onclick=\"renderPage(\'picked\')\">🔁 새로고침</button>',
      '  <button class=\"btn btn-warning btn-sm\" onclick=\"window.pickedCancelSale()\">↩ 판매화물 검정 취소 (→ 판매 배정)</button>',
      '  <label style=\"display:flex;align-items:center;gap:4px;cursor:pointer;font-size:13px\">',
      '    <input type=\"checkbox\" id=\"picked-chk-all\" onchange=\"window.pickedToggleAll(this.checked)\"> 전체 선택',
      '  </label>',
      '  <span style=\"margin-left:auto;display:flex;gap:6px\">',
      '    <button class=\"btn btn-secondary btn-sm\" onclick=\"window.pickedExportExcel()\">📊 Excel 내보내기</button>',
      '  </span>',
      '</div>',
      '<div id=\"picked-summary-bar\" style=\"display:none;padding:4px 8px;background:var(--surface);border:1px solid var(--border);border-radius:4px;font-size:12px;margin-bottom:6px\">',
      '  Σ 건수: <b id=\"picked-sum-count\">0</b> &nbsp;|&nbsp; Σ 중량: <b id=\"picked-sum-kg\">0</b> kg',
      '</div>',
      '<div id=\"picked-loading\" style=\"padding:40px;text-align:center;color:var(--text-muted)\">⏳ 데이터 로딩 중...</div>',
      '<div style=\"overflow-x:auto\">',
      '  <table class=\"data-table\" id=\"picked-table\" style=\"display:none\">',
      '  <thead><tr>',
      '    <th style=\"width:32px\"></th>',
      '    <th style=\"text-align:center\">No.</th>',
      '    <th style=\"text-align:center\">LOT NO</th>',
      '    <th style=\"text-align:center\">피킹No</th>',
      '    <th style=\"text-align:center\">고객사</th>',
      '    <th style=\"text-align:center\">톤백수</th>',
      '    <th style=\"text-align:center\">중량(kg)</th>',
      '    <th style=\"text-align:center\">피킹일</th>',
      '  </tr></thead>',
      '  <tbody id=\"picked-tbody\"></tbody>',
      '  </table>',
      '</div>',
      '<div class=\"empty\" id=\"picked-empty\" style=\"display:none;padding:60px;text-align:center\">📭 피킹 데이터 없음</div>',
      '<div id=\"picked-detail-panel\" style=\"display:none;margin-top:16px;border-top:2px solid var(--border);padding-top:16px\">',
      '  <h3 id=\"picked-detail-title\" style=\"margin:0 0 12px 0\">톤백 상세</h3>',
      '  <div id=\"picked-detail-content\"></div>',
      '</div>',
      '</section>'
    ].join('');"""

if OLD in c:
    c2 = c.replace(OLD, NEW, 1)
    with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
        f.write(c2)
    print('OK: Picked 탭 툴바 복구 완료 (취소/전체선택/Excel 버튼 추가)')
else:
    print('FAIL: 패턴 못 찾음')
    idx = c.find('function loadPickedPage()')
    if idx >= 0:
        print('loadPickedPage 위치:', idx)
        print(repr(c[idx:idx+400]))
    else:
        print('함수 자체가 없음')
