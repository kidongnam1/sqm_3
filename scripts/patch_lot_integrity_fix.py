#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lot_check.md 지적 사항 수정:
  1) ENDPOINTS 테이블에서 onFixLotIntegrity / onIntegrityRepair 를
     GET integrity-check → JS fix-lot-integrity 로 교체
  2) dispatchAction JS 분기에 fix-lot-integrity 핸들러 추가
  3) showFixLotIntegrityModal() 함수 삽입 (확인 → POST → 결과 표시)
"""
import sys

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    c = f.read()
print(f"Size: {len(c):,}", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1: ENDPOINTS 테이블 — onFixLotIntegrity 수정
# ─────────────────────────────────────────────────────────────────────────────
OLD1 = "    'onFixLotIntegrity': {m:'GET',  u:'/api/action/integrity-check',              lbl:'LOT 정합성 검사'},"
NEW1 = "    'onFixLotIntegrity': {m:'JS',   u:'fix-lot-integrity',                        lbl:'LOT 정합성 복구'},"

if OLD1 in c:
    c = c.replace(OLD1, NEW1, 1)
    print("PATCH 1 OK: onFixLotIntegrity 수정", flush=True)
else:
    print("PATCH 1 FAIL", flush=True); sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2: ENDPOINTS 테이블 — onIntegrityRepair 수정
# ─────────────────────────────────────────────────────────────────────────────
OLD2 = "    'onIntegrityRepair': {m:'GET',  u:'/api/action/integrity-check',                     lbl:'정합성 검사/복구'},"
NEW2 = "    'onIntegrityRepair': {m:'JS',   u:'fix-lot-integrity',                              lbl:'LOT 정합성 복구'},"

if OLD2 in c:
    c = c.replace(OLD2, NEW2, 1)
    print("PATCH 2 OK: onIntegrityRepair 수정", flush=True)
else:
    print("PATCH 2 FAIL", flush=True); sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 3: dispatchAction 안에 fix-lot-integrity JS 분기 추가
#   product-master 분기 바로 앞에 삽입
# ─────────────────────────────────────────────────────────────────────────────
OLD3 = (
    "      if (conf.u === 'product-master') {\n"
    "        showProductMasterModal();\n"
    "        return;\n"
    "      }"
)
NEW3 = (
    "      if (conf.u === 'fix-lot-integrity') {\n"
    "        showFixLotIntegrityModal();\n"
    "        return;\n"
    "      }\n"
    "      if (conf.u === 'product-master') {\n"
    "        showProductMasterModal();\n"
    "        return;\n"
    "      }"
)

if OLD3 in c:
    c = c.replace(OLD3, NEW3, 1)
    print("PATCH 3 OK: dispatchAction 분기 추가", flush=True)
else:
    print("PATCH 3 FAIL", flush=True); sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 4: showFixLotIntegrityModal 함수 삽입
#   showProductMasterModal 선언부 바로 앞에 삽입
# ─────────────────────────────────────────────────────────────────────────────
ANCHOR4 = "  function showProductMasterModal"
FIX_FUNC = """\
  /* ═══════════════════════════════════════════════════════════════
     LOT 정합성 복구 모달 — v864-2 _on_fix_lot_status_integrity 매핑
     POST /api/action/fix-integrity → eng.fix_lot_status_integrity()
  ═══════════════════════════════════════════════════════════════ */
  function showFixLotIntegrityModal() {
    var ok = window.confirm(
      'LOT 상태를 톤백 기준으로 일괄 보정합니다.\\n\\n' +
      '• LOT=SOLD/OUTBOUND 이지만 AVAILABLE 톤백 잔존 → AVAILABLE/PARTIAL\\n' +
      '• LOT=AVAILABLE 이지만 전체 SOLD → OUTBOUND\\n\\n' +
      '계속하시겠습니까?'
    );
    if (!ok) return;
    showToast('info', '⏳ LOT 정합성 복구 실행 중...');
    apiCall('POST', '/api/action/fix-integrity', {})
      .then(function(res) {
        if (!res || res.ok === false) {
          showToast('error', 'LOT 정합성 복구 실패: ' + ((res && res.error) || '알 수 없는 오류'));
          return;
        }
        var d = (res.data) || {};
        var fixed  = d.fixed_count  !== undefined ? d.fixed_count  : (d.repaired || '?');
        var total  = d.total_checked !== undefined ? d.total_checked : '';
        var msg = 'LOT 정합성 복구 완료 — 수정: ' + fixed + '건';
        if (total) msg += ' / 검사: ' + total + '건';
        showToast('success', msg);
        /* 결과 모달 */
        var details = '';
        if (d.details && d.details.length) {
          details = '<ul style="text-align:left;max-height:200px;overflow:auto;padding-left:20px">' +
            d.details.map(function(x){
              return '<li style="font-size:12px;margin:2px 0">' +
                escapeHtml(x.lot_no || x) + ' : ' +
                escapeHtml(x.old_status || '') + ' → ' +
                escapeHtml(x.new_status || '') + '</li>';
            }).join('') + '</ul>';
        }
        var overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9000;display:flex;align-items:center;justify-content:center';
        overlay.innerHTML = [
          '<div style="background:var(--card-bg);border:1px solid var(--panel-border);border-radius:8px;padding:24px 28px;min-width:340px;max-width:480px;box-shadow:0 8px 32px rgba(0,0,0,.4)">',
          '<h3 style="margin:0 0 12px;font-size:16px">🛠 LOT 정합성 복구 결과</h3>',
          '<p style="margin:0 0 10px;font-size:14px">수정된 LOT: <strong>' + fixed + '건</strong>' + (total ? ' / 전체 검사: ' + total + '건' : '') + '</p>',
          details || '<p style="color:var(--text-muted);font-size:13px">수정 대상 없음 (모두 정상)</p>',
          '<div style="text-align:right;margin-top:16px">',
          '<button onclick="this.closest(\'[style*=fixed]\').remove();renderPage(_currentRoute||\'dashboard\')" style="padding:6px 18px;background:var(--accent);color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:13px">확인 &amp; 새로고침</button>',
          '</div></div>'
        ].join('');
        document.body.appendChild(overlay);
        overlay.addEventListener('click', function(e){ if(e.target===overlay) overlay.remove(); });
      })
      .catch(function(e) {
        showToast('error', 'LOT 정합성 복구 오류: ' + (e.message || String(e)));
      });
  }

"""

if ANCHOR4 in c:
    c = c.replace(ANCHOR4, FIX_FUNC + "  function showProductMasterModal", 1)
    print("PATCH 4 OK: showFixLotIntegrityModal 삽입", flush=True)
else:
    print("PATCH 4 FAIL: showProductMasterModal 위치 못 찾음", flush=True); sys.exit(1)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)
print(f"Done. {len(c):,} bytes.", flush=True)
