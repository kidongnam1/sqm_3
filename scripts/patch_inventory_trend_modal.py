#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
재고 추이 전용 모달
1. ENDPOINTS: onInventoryTrend / onStockTrendChart → JS 'inventory-trend-modal'
2. dispatchAction 분기 추가
3. showInventoryTrendModal() 함수 삽입
   - /api/q/inventory-trend 조회
   - 데이터 없음: 안내 + "오늘 스냅샷 생성" 버튼
   - 데이터 있음: 표 + 간단한 CSS 막대 차트
"""
import sys

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    c = f.read()
print(f"Size: {len(c):,}", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1: ENDPOINTS 수정
# ─────────────────────────────────────────────────────────────────────────────
OLD1 = "    'onInventoryTrend':  {m:'GET',  u:'/api/q/inventory-trend',                  lbl:'재고 추이 차트'},"
NEW1 = "    'onInventoryTrend':  {m:'JS',   u:'inventory-trend-modal',                   lbl:'재고 추이 차트'},"
if OLD1 in c:
    c = c.replace(OLD1, NEW1, 1); print("PATCH 1a OK", flush=True)
else:
    print("PATCH 1a FAIL"); sys.exit(1)

OLD2 = "    'onStockTrendChart':   {m:'GET', u:'/api/q/inventory-trend',                   lbl:'📊 재고 추이 차트'},"
NEW2 = "    'onStockTrendChart':   {m:'JS',  u:'inventory-trend-modal',                    lbl:'📊 재고 추이 차트'},"
if OLD2 in c:
    c = c.replace(OLD2, NEW2, 1); print("PATCH 1b OK", flush=True)
else:
    print("PATCH 1b FAIL"); sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2: dispatchAction 분기 추가 (swap-report-modal 뒤에)
# ─────────────────────────────────────────────────────────────────────────────
OLD3 = (
    "      if (conf.u === 'swap-report-modal') {\n"
    "        showSwapReportModal();\n"
    "        return;\n"
    "      }"
)
NEW3 = (
    "      if (conf.u === 'swap-report-modal') {\n"
    "        showSwapReportModal();\n"
    "        return;\n"
    "      }\n"
    "      if (conf.u === 'inventory-trend-modal') {\n"
    "        showInventoryTrendModal();\n"
    "        return;\n"
    "      }"
)
if OLD3 in c:
    c = c.replace(OLD3, NEW3, 1); print("PATCH 2 OK", flush=True)
else:
    print("PATCH 2 FAIL"); sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 3: showInventoryTrendModal() 함수 삽입 (showSwapReportModal 앞에)
# ─────────────────────────────────────────────────────────────────────────────
ANCHOR3 = "  /* ═══════════════════════════════════════════════════════════════\n     Swap 리포트 모달"
TREND_FUNC = r"""  /* ═══════════════════════════════════════════════════════════════
     재고 추이 차트 모달 — chart.md ①② 구현
     GET  /api/q/inventory-trend    → 스냅샷 목록 + chart data
     POST /api/q/create-snapshot    → 오늘 스냅샷 생성
  ═══════════════════════════════════════════════════════════════ */
  function showInventoryTrendModal() {
    var overlay = document.createElement('div');
    overlay.id  = 'inv-trend-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9300;display:flex;align-items:center;justify-content:center';
    overlay.innerHTML = [
      '<div style="background:var(--card-bg);border:1px solid var(--panel-border);border-radius:10px;',
        'padding:22px 26px;width:860px;max-width:95vw;max-height:90vh;display:flex;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,.45)">',
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">',
        '<div>',
          '<h3 style="margin:0;font-size:16px">📊 재고 추이 차트</h3>',
          '<div style="font-size:11px;color:var(--text-muted);margin-top:2px">매일 시작 시 자동 저장 — inventory_snapshot 기반</div>',
        '</div>',
        '<div style="display:flex;gap:8px;align-items:center">',
          '<button onclick="invTrendCreateSnapshot()" style="padding:5px 12px;background:var(--success,#4caf50);color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px">📸 오늘 스냅샷 생성</button>',
          '<button onclick="document.getElementById(\'inv-trend-overlay\').remove()" style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--text-muted);line-height:1">✕</button>',
        '</div>',
      '</div>',
      '<div id="inv-trend-body" style="flex:1;overflow-y:auto">',
        '<div style="text-align:center;padding:40px;color:var(--text-muted)">⏳ 로딩 중...</div>',
      '</div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e){ if(e.target===overlay) overlay.remove(); });
    invTrendLoad();
  }

  window.invTrendLoad = function() {
    var body = document.getElementById('inv-trend-body');
    if (!body) return;
    body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>';
    fetch(API + '/api/q/inventory-trend')
      .then(function(r){ return r.json(); })
      .then(function(res){
        var items = (res && res.data && res.data.items) || [];
        var chart = (res && res.data && res.data.chart) || {};
        if (!items.length) {
          body.innerHTML = [
            '<div style="text-align:center;padding:50px 20px">',
              '<div style="font-size:48px;margin-bottom:16px">📸</div>',
              '<h4 style="margin:0 0 10px;font-size:16px">스냅샷 데이터가 없습니다</h4>',
              '<p style="color:var(--text-muted);font-size:13px;margin:0 0 20px">',
                '앱이 시작될 때 자동으로 오늘 스냅샷이 저장됩니다.<br>',
                '지금 바로 생성하려면 아래 버튼을 누르세요.',
              '</p>',
              '<button onclick="invTrendCreateSnapshot()" style="padding:8px 20px;background:var(--accent);color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px">',
                '📸 오늘 스냅샷 생성',
              '</button>',
            '</div>'
          ].join('');
          return;
        }
        /* 최대값 계산 (막대 너비 비율용) */
        var maxMt = 0;
        items.forEach(function(r){ if ((r.total_weight_mt||0) > maxMt) maxMt = r.total_weight_mt||0; });
        /* 표 + 간단 막대 차트 */
        var rows = items.map(function(r, i){
          var tot = r.total_weight_mt || 0;
          var avl = r.available_weight_mt || 0;
          var pck = r.picked_weight_mt || 0;
          var barW = maxMt > 0 ? Math.round((tot / maxMt) * 200) : 0;
          var avlW = maxMt > 0 ? Math.round((avl / maxMt) * 200) : 0;
          var pckW = maxMt > 0 ? Math.round((pck / maxMt) * 200) : 0;
          var isToday = r.snapshot_date === new Date().toISOString().slice(0,10);
          return '<tr style="' + (isToday ? 'background:rgba(33,150,243,.08)' : '') + '">' +
            '<td style="text-align:center;white-space:nowrap;font-weight:'+(isToday?'600':'400')+'">' +
              escapeHtml(r.snapshot_date||'') + (isToday ? ' <span style="font-size:10px;color:var(--accent)">(오늘)</span>' : '') +
            '</td>' +
            '<td style="text-align:right">' + (r.total_lots||0) + '</td>' +
            '<td style="text-align:right">' + (r.total_tonbags||0) + '</td>' +
            /* 총재고 */
            '<td style="text-align:right;white-space:nowrap">' + tot.toFixed(2) + ' MT</td>' +
            /* 막대 시각화 */
            '<td style="padding:4px 8px">' +
              '<div style="display:flex;flex-direction:column;gap:2px;min-width:220px">' +
                '<div title="총재고" style="height:6px;background:#2196f3;width:'+barW+'px;border-radius:3px"></div>' +
                '<div title="판매가능" style="height:6px;background:#4caf50;width:'+avlW+'px;border-radius:3px"></div>' +
                '<div title="피킹/출고대기" style="height:6px;background:#ff9800;width:'+pckW+'px;border-radius:3px"></div>' +
              '</div>' +
            '</td>' +
            '<td style="text-align:right;white-space:nowrap;color:#4caf50">' + avl.toFixed(2) + ' MT</td>' +
            '<td style="text-align:right;white-space:nowrap;color:#ff9800">' + pck.toFixed(2) + ' MT</td>' +
            '</tr>';
        }).join('');

        body.innerHTML = [
          /* 범례 */
          '<div style="display:flex;gap:16px;margin-bottom:10px;font-size:12px;flex-wrap:wrap">',
            '<span><span style="display:inline-block;width:14px;height:8px;background:#2196f3;border-radius:2px;margin-right:4px"></span>총재고</span>',
            '<span><span style="display:inline-block;width:14px;height:8px;background:#4caf50;border-radius:2px;margin-right:4px"></span>판매가능</span>',
            '<span><span style="display:inline-block;width:14px;height:8px;background:#ff9800;border-radius:2px;margin-right:4px"></span>피킹/출고대기</span>',
            '<span style="margin-left:auto;color:var(--text-muted)">총 '+items.length+'일 데이터</span>',
          '</div>',
          '<div style="overflow-x:auto">',
          '<table class="data-table" style="width:100%">',
            '<thead><tr>',
              '<th style="text-align:center">날짜</th>',
              '<th style="text-align:center">LOT 수</th>',
              '<th style="text-align:center">톤백 수</th>',
              '<th style="text-align:center">총재고</th>',
              '<th style="text-align:center;min-width:230px">추이 막대</th>',
              '<th style="text-align:center">판매가능</th>',
              '<th style="text-align:center">피킹/출고대기</th>',
            '</tr></thead>',
            '<tbody>' + rows + '</tbody>',
          '</table></div>'
        ].join('');
      })
      .catch(function(e){
        if (body) body.innerHTML = '<div style="text-align:center;color:red;padding:40px">❌ 로드 실패: '+escapeHtml(String(e))+'</div>';
      });
  };

  window.invTrendCreateSnapshot = function() {
    showToast('info', '⏳ 오늘 스냅샷 생성 중...');
    fetch(API + '/api/q/create-snapshot?force=false', {method:'POST'})
      .then(function(r){ return r.json(); })
      .then(function(res){
        if (res && res.ok === false) {
          showToast('warn', res.error || '스냅샷 생성 실패');
          return;
        }
        var d = (res && res.data) || {};
        if (d.created === false) {
          showToast('info', '이미 오늘 스냅샷이 있습니다. (force=true로 덮어쓰기 가능)');
        } else {
          showToast('success', '스냅샷 생성 완료 — ' + (d.date||'') + ' / ' + (d.total_lots||0) + ' LOT / ' + ((d.total_weight_kg||0)/1000).toFixed(2) + ' MT');
        }
        invTrendLoad();  /* 목록 새로고침 */
      })
      .catch(function(e){
        showToast('error', '스냅샷 생성 오류: ' + escapeHtml(String(e)));
      });
  };

"""

if ANCHOR3 in c:
    c = c.replace(ANCHOR3, TREND_FUNC + "  /* ═══════════════════════════════════════════════════════════════\n     Swap 리포트 모달", 1)
    print("PATCH 3 OK: showInventoryTrendModal 삽입", flush=True)
else:
    print("PATCH 3 FAIL: 앵커 못 찾음", flush=True); sys.exit(1)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)
print(f"Done. {len(c):,} bytes.", flush=True)
