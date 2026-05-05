# -*- coding: utf-8 -*-
"""
sidebar_parity_patch.py
=======================
sqm-inline.js에 Inventory + Allocation 탭 누락 기능을 추가하는 원자적 패치 스크립트.

변경 내용:
  [Inventory]
    1. 상태 필터 + 텍스트 검색 바 추가
    2. LOT 복사 / 행 전체 복사 버튼 추가
    3. 빠른 출고 진입 / 반품 진입 버튼 추가
    4. LOT 이력 조회 버튼 추가

  [Allocation]
    5. SALE REF 일괄 취소 버튼 + 핸들러
    6. 전체 초기화 버튼 + 핸들러
    7. RESERVED→AVAILABLE / PICKED→RESERVED / OUTBOUND→PICKED 되돌리기 버튼 + 핸들러
    8. Excel 내보내기 버튼 + 핸들러
    9. 전체 선택 토글 버튼

실행:
    python scripts/patch_sidebar_parity.py
"""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
JS   = ROOT / "frontend" / "js" / "sqm-inline.js"
BACKUP = JS.with_suffix(".js.pre_parity_patch")

if not JS.exists():
    print(f"[ERROR] 파일 없음: {JS}")
    sys.exit(1)

src = JS.read_text(encoding="utf-8")

original_len = len(src)
changes = []


# ══════════════════════════════════════════════════════════════════════
# PATCH 1 — Inventory 탭: 상태 필터 + 검색 바 추가
# 현재 헤더 div 바로 뒤에 필터 바를 삽입
# ══════════════════════════════════════════════════════════════════════
INV_HEADER_OLD = (
    "        '<div style=\"display:flex;align-items:center;gap:12px;padding:4px 0 10px\">' +\n"
    "        '<h2 style=\"margin:0\">📦 재고 목록 (Inventory)</h2>' +\n"
    "        '<span style=\"font-size:12px;color:var(--text-muted)\">'+rows.length+' LOTs</span>' +\n"
    "        '<button class=\"btn btn-secondary\" onclick=\"renderPage(\\'inventory\\')\" style=\"margin-left:auto\">🔁 새로고침</button>' +\n"
    "        '</div>' +"
)

INV_HEADER_NEW = (
    "        '<div style=\"display:flex;align-items:center;gap:12px;padding:4px 0 10px\">' +\n"
    "        '<h2 style=\"margin:0\">📦 재고 목록 (Inventory)</h2>' +\n"
    "        '<span style=\"font-size:12px;color:var(--text-muted)\" id=\"inv-count-label\">'+rows.length+' LOTs</span>' +\n"
    "        '<button class=\"btn btn-secondary\" onclick=\"renderPage(\\'inventory\\')\" style=\"margin-left:auto\">🔁 새로고침</button>' +\n"
    "        '</div>' +\n"
    "        /* ── 필터 / 검색 바 ── */\n"
    "        '<div id=\"inv-filter-bar\" style=\"display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px\">' +\n"
    "        '  <label style=\"font-size:12px;white-space:nowrap\">상태:</label>' +\n"
    "        '  <select id=\"inv-status-filter\" style=\"font-size:12px;padding:2px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)\" onchange=\"window.invApplyFilter()\">' +\n"
    "        '    <option value=\"\">전체</option>' +\n"
    "        '    <option value=\"AVAILABLE\">AVAILABLE</option>' +\n"
    "        '    <option value=\"RESERVED\">RESERVED</option>' +\n"
    "        '    <option value=\"PICKED\">PICKED</option>' +\n"
    "        '    <option value=\"RETURN\">RETURN</option>' +\n"
    "        '  </select>' +\n"
    "        '  <input id=\"inv-search-input\" type=\"text\" placeholder=\"LOT / SAP / BL / Product 검색...\" ' +\n"
    "        '    style=\"flex:1;min-width:180px;font-size:12px;padding:2px 8px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)\" ' +\n"
    "        '    oninput=\"window.invApplyFilter()\">' +\n"
    "        '  <button class=\"btn btn-ghost\" style=\"font-size:12px\" onclick=\"window.invClearFilter()\">✕ 초기화</button>' +\n"
    "        '</div>' +"
)

if INV_HEADER_OLD in src:
    src = src.replace(INV_HEADER_OLD, INV_HEADER_NEW, 1)
    changes.append("PATCH 1: Inventory 필터/검색 바 추가")
else:
    print("[WARN] PATCH 1 대상 못 찾음 — 수동 확인 필요")


# ══════════════════════════════════════════════════════════════════════
# PATCH 2 — Inventory 탭: 각 행 마지막 <td>에 버튼 추가
# 기존 Detail 버튼만 있던 td를 기능 버튼으로 확장
# ══════════════════════════════════════════════════════════════════════
INV_ROW_BTN_OLD = (
    "          '<td><button class=\"btn btn-ghost btn-xs\" onclick=\"window.showLotDetail(\\''+escapeHtml(r.lot||'')+'\\')\">Detail</button></td>' +"
)

INV_ROW_BTN_NEW = (
    "          '<td style=\"white-space:nowrap\">' +\n"
    "          '<button class=\"btn btn-ghost btn-xs\" onclick=\"window.showLotDetail(\\''+escapeHtml(r.lot||'')+'\\')\" title=\"LOT 상세\">📋</button> ' +\n"
    "          '<button class=\"btn btn-ghost btn-xs\" onclick=\"window.invCopyLot(\\''+escapeHtml(r.lot||'')+'\\')\" title=\"LOT 번호 복사\">📄</button> ' +\n"
    "          '<button class=\"btn btn-ghost btn-xs\" onclick=\"window.invCopyRow(this)\" title=\"행 전체 복사\">📑</button> ' +\n"
    "          '<button class=\"btn btn-ghost btn-xs\" onclick=\"window.invQuickOutbound(\\''+escapeHtml(r.lot||'')+'\\')\" title=\"즉시 출고 진입\" style=\"color:#42a5f5\">🚀</button> ' +\n"
    "          '<button class=\"btn btn-ghost btn-xs\" onclick=\"window.invQuickReturn(\\''+escapeHtml(r.lot||'')+'\\')\" title=\"반품 진입\" style=\"color:#ef5350\">🔄</button> ' +\n"
    "          '<button class=\"btn btn-ghost btn-xs\" onclick=\"window.invShowLotHistory(\\''+escapeHtml(r.lot||'')+'\\')\" title=\"LOT 이력\" style=\"color:#66bb6a\">📊</button>' +\n"
    "          '</td>' +"
)

if INV_ROW_BTN_OLD in src:
    src = src.replace(INV_ROW_BTN_OLD, INV_ROW_BTN_NEW, 1)
    changes.append("PATCH 2: Inventory 행 버튼 확장 (복사/출고/반품/이력)")
else:
    print("[WARN] PATCH 2 대상 못 찾음 — 수동 확인 필요")


# ══════════════════════════════════════════════════════════════════════
# PATCH 3 — Inventory 탭: 필터/검색 핸들러 + 행 버튼 핸들러 삽입
# loadInventoryPage 함수 끝 바로 뒤에 삽입
# ══════════════════════════════════════════════════════════════════════
INV_FUNC_END_MARKER = (
    "    }).catch(function(e){\n"
    "      if (_currentRoute !== route) return;\n"
    "      c.innerHTML = '<div class=\"empty\" style=\"padding:40px;text-align:center\">Load failed: '+escapeHtml(e.message||String(e))+'</div>';\n"
    "      showToast('error', 'Inventory load failed');\n"
    "    });\n"
    "  }\n"
    "\n"
    "  /* ===================================================\n"
    "     7b. PAGE: Allocation\n"
    "     =================================================== */"
)

INV_HANDLERS = """
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
    var text = cells.slice(0, cells.length - 1).map(function(td){ return td.textContent.trim(); }).join('\\t');
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

  window.invShowLotHistory = function(lot) {
    if (!lot) return;
    apiGet('/api/action/lot-detail?lot_no=' + encodeURIComponent(lot)).then(function(res){
      var d = res && res.data ? res.data : res;
      var history = (d.history || d.audit_log || []);
      var lines = history.map(function(h){
        return '[' + (h.created_at||h.action_time||'').slice(0,16) + '] ' + (h.action||'') + ' — ' + (h.note||h.detail||'');
      });
      var msg = lines.length ? lines.join('\\n') : '이력 없음';
      alert('📊 LOT 이력: ' + lot + '\\n\\n' + msg);
    }).catch(function(e){
      showToast('error', 'LOT 이력 조회 실패: ' + (e.message||e));
    });
  };

"""

INV_FUNC_END_REPLACEMENT = INV_HANDLERS + """  /* ===================================================
     7b. PAGE: Allocation
     =================================================== */"""

if "    });\n  }\n\n  /* ===================================================\n     7b. PAGE: Allocation\n     =================================================== */" in src:
    src = src.replace(
        "    });\n  }\n\n  /* ===================================================\n     7b. PAGE: Allocation\n     =================================================== */",
        "    });\n  }\n" + INV_HANDLERS + "\n  /* ===================================================\n     7b. PAGE: Allocation\n     =================================================== */",
        1
    )
    changes.append("PATCH 3: Inventory 필터/검색 핸들러 + 버튼 핸들러 삽입")
else:
    print("[WARN] PATCH 3 대상 못 찾음 — loadInventoryPage 끝 마커 확인 필요")


# ══════════════════════════════════════════════════════════════════════
# PATCH 4 — Allocation 탭 툴바: 누락 버튼 추가
# 기존 툴바의 마지막 버튼(allocResetSelected) 바로 뒤에 삽입
# ══════════════════════════════════════════════════════════════════════
ALLOC_TOOLBAR_OLD = (
    "      '  <button class=\"btn\" onclick=\"window.allocResetSelected()\" title=\"LOT 배정 완전 삭제\">🧹 LOT 초기화</button>',\n"
    "      '</div>',"
)

ALLOC_TOOLBAR_NEW = (
    "      '  <button class=\"btn\" onclick=\"window.allocResetSelected()\" title=\"LOT 배정 완전 삭제\">🧹 LOT 초기화</button>',\n"
    "      '  <span style=\"width:1px;height:22px;background:var(--panel-border);margin:0 4px\"></span>',\n"
    "      '  <button class=\"btn btn-danger\" onclick=\"window.allocResetAll()\" title=\"모든 배정 취소 + AVAILABLE 원복\">⚠️ 전체 초기화</button>',\n"
    "      '  <button class=\"btn\" onclick=\"window.allocCancelBySaleRef()\" title=\"SALE REF 입력 후 해당 배정 전체 취소\">🔖 SALE REF 취소</button>',\n"
    "      '  <button class=\"btn\" onclick=\"window.allocOpenLotOverview()\" title=\"LOT별 배정 현황 팝업\">📦 LOT 현황</button>',\n"
    "      '  <button class=\"btn btn-secondary\" onclick=\"window.allocExportExcel()\" title=\"현재 배정 데이터 Excel 다운로드\">📊 Excel 내보내기</button>',\n"
    "      '</div>',\n"
    "      /* ── 단계 되돌리기 버튼 행 ── */\n"
    "      '<div style=\"display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px\">',\n"
    "      '  <span style=\"font-size:12px;font-weight:600;white-space:nowrap\">&#x21A9; 단계 되돌리기:</span>',\n"
    "      '  <button class=\"btn\" onclick=\"window.allocRevertStep(\\'RESERVED\\')\" style=\"font-size:12px\">RESERVED &rarr; AVAILABLE</button>',\n"
    "      '  <button class=\"btn\" onclick=\"window.allocRevertStep(\\'PICKED\\')\" style=\"font-size:12px\">PICKED &rarr; RESERVED</button>',\n"
    "      '  <button class=\"btn\" onclick=\"window.allocRevertStep(\\'OUTBOUND\\')\" style=\"font-size:12px\">OUTBOUND &rarr; PICKED</button>',\n"
    "      '</div>',"
)

if ALLOC_TOOLBAR_OLD in src:
    src = src.replace(ALLOC_TOOLBAR_OLD, ALLOC_TOOLBAR_NEW, 1)
    changes.append("PATCH 4: Allocation 툴바 버튼 확장 (전체초기화/SALE REF/LOT현황/Excel/되돌리기)")
else:
    print("[WARN] PATCH 4 대상 못 찾음 — allocResetSelected 버튼 이후 마커 확인 필요")


# ══════════════════════════════════════════════════════════════════════
# PATCH 5 — Allocation 핸들러: 새 버튼 핸들러 삽입
# 기존 allocResetSelected 핸들러 직후에 추가
# ══════════════════════════════════════════════════════════════════════
ALLOC_HANDLER_ANCHOR = "  window.allocResetSelected = function() {\n    _allocBulkAction({"

ALLOC_NEW_HANDLERS = """
  /* ── 전체 초기화 ── */
  window.allocResetAll = function() {
    if (!confirm('⚠️ 전체 초기화\\n\\n모든 RESERVED/PICKED/OUTBOUND 배정을 취소하고 AVAILABLE로 원복합니다.\\n(SOLD는 보호됩니다)\\n\\n계속하시겠습니까?')) return;
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
    if (!confirm('🔖 SALE REF 취소\\n\\n"' + saleRef + '" 에 해당하는 모든 배정을 취소하고 AVAILABLE로 원복합니다.\\n계속하시겠습니까?')) return;
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
      alert('📦 LOT 배정 현황 (' + rows.length + '건)\\n\\n' + lines.join('\\n'));
    }).catch(function(e){ showToast('error', 'LOT 현황 실패: ' + (e.message||e)); });
  };

  /* ── Excel 내보내기 ── */
  window.allocExportExcel = function() {
    var url = (typeof API !== 'undefined' ? API : 'http://localhost:8765') + '/api/allocation/export-excel';
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
    if (!confirm('↩️ 단계 되돌리기\\n\\n' + label + '\\n\\n' + fromStatus + ' 상태의 모든 배정을 한 단계 되돌립니다.\\n계속하시겠습니까?')) return;
    apiPost('/api/allocation/revert-step', { from_status: fromStatus })
      .then(function(res){
        if (res.ok === false) { showToast('warn', res.message || '되돌릴 대상 없음'); }
        else { showToast('success', '↩️ ' + (res.message || label + ' 완료')); loadAllocationPage(); }
      })
      .catch(function(e){ showToast('error', '되돌리기 실패: ' + (e.message||e)); });
  };

"""

if ALLOC_HANDLER_ANCHOR in src:
    src = src.replace(ALLOC_HANDLER_ANCHOR, ALLOC_NEW_HANDLERS + ALLOC_HANDLER_ANCHOR, 1)
    changes.append("PATCH 5: Allocation 핸들러 추가 (전체초기화/SALE REF/LOT현황/Excel/되돌리기)")
else:
    print("[WARN] PATCH 5 대상 못 찾음 — allocResetSelected 마커 확인 필요")


# ══════════════════════════════════════════════════════════════════════
# 결과 검증 및 저장
# ══════════════════════════════════════════════════════════════════════
if not changes:
    print("[ERROR] 적용된 패치 없음. 소스가 이미 패치됐거나 마커 불일치.")
    sys.exit(1)

# 백업 저장
BACKUP.write_text(src if len(changes) < 3 else JS.read_text(encoding="utf-8"), encoding="utf-8")

# 바이트 레벨 오염 제거 (bash heredoc \! 오염 방지)
raw = src.encode("utf-8")
raw = raw.replace(bytes([0x5c, 0x21]), bytes([0x21]))
final = raw.decode("utf-8")

JS.write_text(final, encoding="utf-8", newline="\n")

print(f"\n✅ sqm-inline.js 패치 완료 ({len(changes)}개 변경)")
for i, c in enumerate(changes, 1):
    print(f"  {i}. {c}")
print(f"\n  원본 길이: {original_len:,} chars")
print(f"  패치 후 길이: {len(final):,} chars")
print(f"  증가분: +{len(final)-original_len:,} chars")
