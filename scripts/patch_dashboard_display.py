# -*- coding: utf-8 -*-
"""
patch_dashboard_display.py
- "5단계 재고 현황" → "재고 현황"
- renderStatusCards: 톤백/샘플 2행 분리 표시
- view-unit 라디오 버튼 이벤트 리스너 연결 + 기능 구현
"""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
JS   = ROOT / "frontend" / "js" / "sqm-inline.js"
HTML = ROOT / "frontend" / "index.html"

src = JS.read_text(encoding="utf-8")
html = HTML.read_text(encoding="utf-8")
changes = []

# ──────────────────────────────────────────────────────────────────
# PATCH A: "돈백" → "톤백" 오타 수정 (index.html)
# ──────────────────────────────────────────────────────────────────
if '🎒 돈백' in html:
    html = html.replace('🎒 돈백', '🎒 톤백', 1)
    changes.append("PATCH A: index.html '돈백' → '톤백' 오타 수정")
else:
    print("[WARN] PATCH A: '돈백' 문자열 없음 (이미 수정됨?)")

# ──────────────────────────────────────────────────────────────────
# PATCH B: "5단계 재고 현황" → "재고 현황" (sqm-inline.js)
# ──────────────────────────────────────────────────────────────────
OLD_TITLE = "    html += '5\\uB2E8\\uACC4 \\uC7AC\\uACE0 \\uD604\\uD669</h3>';"
NEW_TITLE = "    html += '\\uC7AC\\uACE0 \\uD604\\uD669</h3>';"
if OLD_TITLE in src:
    src = src.replace(OLD_TITLE, NEW_TITLE, 1)
    changes.append("PATCH B: '5단계 재고 현황' → '재고 현황'")
else:
    # 유니코드가 이미 디코딩된 형태일 수도 있으니 한글로도 시도
    if '5단계 재고 현황</h3>' in src:
        src = src.replace('5단계 재고 현황</h3>', '재고 현황</h3>', 1)
        changes.append("PATCH B (KR): '5단계 재고 현황' → '재고 현황'")
    else:
        print("[WARN] PATCH B: '5단계 재고 현황' 문자열 못 찾음")

# ──────────────────────────────────────────────────────────────────
# PATCH C: renderStatusCards — 톤백/샘플 2행 분리 표시
# ──────────────────────────────────────────────────────────────────
OLD_CARD_BODY = (
    "      html += '<div style=\"font-size:22px;font-weight:700;color:var(--text-primary,#e0e0e0)\">'+"
    "s.tonbags+'<span style=\"font-size:12px;font-weight:400;color:var(--text-muted,#888)\"> \\uD1A4\\uBC31</span></div>';\n"
    "      html += '<div style=\"font-size:12px;color:var(--text-muted,#888);margin-top:2px\">'+s.lots+' LOT \\u00B7 '+fmtW(s.weight_kg)+'</div>';"
)
NEW_CARD_BODY = (
    "      var normalBags  = (s.normal_bags  != null ? s.normal_bags  : s.tonbags);\n"
    "      var sampleBags  = (s.sample_bags  != null ? s.sample_bags  : 0);\n"
    "      var normalKg    = (s.normal_kg    != null ? s.normal_kg    : s.weight_kg);\n"
    "      var sampleKg    = (s.sample_kg    != null ? s.sample_kg    : 0);\n"
    "      html += '<div style=\"font-size:22px;font-weight:700;color:var(--text-primary,#e0e0e0)\">'+normalBags+"
    "'<span style=\"font-size:12px;font-weight:400;color:var(--text-muted,#888)\"> \\uD1A4\\uBC31</span></div>';\n"
    "      if (sampleBags > 0) {\n"
    "        html += '<div style=\"font-size:13px;font-weight:600;color:#f59e0b;margin-top:1px\">'+sampleBags+"
    "'<span style=\"font-size:11px;font-weight:400;color:var(--text-muted,#888)\"> \\uC0D8\\uD50C</span></div>';\n"
    "      }\n"
    "      html += '<div style=\"font-size:12px;color:var(--text-muted,#888);margin-top:2px\">'+s.lots+' LOT \\u00B7 '+fmtW(normalKg)+'</div>';\n"
    "      if (sampleBags > 0) {\n"
    "        html += '<div style=\"font-size:11px;color:#f59e0b;margin-top:1px\">\\uC0D8\\uD50C: '+fmtW(sampleKg)+'</div>';\n"
    "      }"
)

if OLD_CARD_BODY in src:
    src = src.replace(OLD_CARD_BODY, NEW_CARD_BODY, 1)
    changes.append("PATCH C: renderStatusCards 톤백/샘플 2행 분리 표시")
else:
    # 한글 직접 포함 버전 시도
    OLD_CARD_KR = (
        "      html += '<div style=\"font-size:22px;font-weight:700;color:var(--text-primary,#e0e0e0)\">'+s.tonbags+"
        "'<span style=\"font-size:12px;font-weight:400;color:var(--text-muted,#888)\"> 톤백</span></div>';\n"
        "      html += '<div style=\"font-size:12px;color:var(--text-muted,#888);margin-top:2px\">'+s.lots+' LOT · '+fmtW(s.weight_kg)+'</div>';"
    )
    NEW_CARD_KR = (
        "      var normalBags = (s.normal_bags != null ? s.normal_bags : s.tonbags);\n"
        "      var sampleBags = (s.sample_bags != null ? s.sample_bags : 0);\n"
        "      var normalKg   = (s.normal_kg   != null ? s.normal_kg   : s.weight_kg);\n"
        "      var sampleKg   = (s.sample_kg   != null ? s.sample_kg   : 0);\n"
        "      html += '<div style=\"font-size:22px;font-weight:700;color:var(--text-primary,#e0e0e0)\">'+normalBags+"
        "'<span style=\"font-size:12px;font-weight:400;color:var(--text-muted,#888)\"> 톤백</span></div>';\n"
        "      if (sampleBags > 0) {\n"
        "        html += '<div style=\"font-size:13px;font-weight:600;color:#f59e0b;margin-top:1px\">'+sampleBags+"
        "'<span style=\"font-size:11px;font-weight:400;color:var(--text-muted,#888)\"> 샘플</span></div>';\n"
        "      }\n"
        "      html += '<div style=\"font-size:12px;color:var(--text-muted,#888);margin-top:2px\">'+s.lots+' LOT · '+fmtW(normalKg)+'</div>';\n"
        "      if (sampleBags > 0) {\n"
        "        html += '<div style=\"font-size:11px;color:#f59e0b;margin-top:1px\">샘플: '+fmtW(sampleKg)+'</div>';\n"
        "      }"
    )
    if OLD_CARD_KR in src:
        src = src.replace(OLD_CARD_KR, NEW_CARD_KR, 1)
        changes.append("PATCH C (KR): renderStatusCards 톤백/샘플 2행 분리 표시")
    else:
        print("[WARN] PATCH C: renderStatusCards 카드 본문 마커 못 찾음")

# ──────────────────────────────────────────────────────────────────
# PATCH D: view-unit 라디오 버튼 이벤트 리스너 연결
# loadDashboardTables 함수 끝 직후에 삽입
# ──────────────────────────────────────────────────────────────────
VIEW_UNIT_HANDLER = """
  /* ── view-unit 라디오 버튼: 톤백/LOT/MT 표시 단위 전환 ──────────────────
     - 돈백(tonbag): 각 상태 카드의 주숫자를 "톤백 수"로 표시
     - LOT:         주숫자를 "LOT 수"로 표시
     - MT:          주숫자를 "중량(MT)"으로 표시 (기본값)
     위 세 모드는 대시보드 status 카드에만 적용됨.
  ─────────────────────────────────────────────────────────────── */
  var _viewUnit = 'mt';  // 기본값: MT

  (function _initViewUnit(){
    var radios = document.querySelectorAll('input[name="view-unit"]');
    if (!radios.length) return;
    radios.forEach(function(r){
      r.addEventListener('change', function(){
        _viewUnit = r.value;
        _applyViewUnit();
      });
    });
  })();

  function _applyViewUnit() {
    var el = document.getElementById('dashboard-detail');
    if (!el) return;
    // 현재 렌더링된 카드들을 다시 렌더하기 위해 stats 재요청
    apiGet('/api/dashboard/stats').then(function(res){
      var d = res.data || res || {};
      var summary = d.status_summary || {};
      var html = '<div style="margin-bottom:16px"><h3 style="margin:0 0 8px 0;font-size:15px;color:var(--text-primary,#e0e0e0)">재고 현황</h3>';
      html += '<div style="display:flex;gap:10px;flex-wrap:wrap">';
      STATUS_CARD_META.forEach(function(m){
        var s = summary[m.key] || {lots:0,tonbags:0,weight_kg:0,normal_bags:0,sample_bags:0,normal_kg:0,sample_kg:0};
        var normalBags = (s.normal_bags != null ? s.normal_bags : s.tonbags);
        var sampleBags = (s.sample_bags || 0);
        var normalKg   = (s.normal_kg   != null ? s.normal_kg   : s.weight_kg);
        var sampleKg   = (s.sample_kg   || 0);

        var bigNum, bigLabel;
        if (_viewUnit === 'tonbag') {
          bigNum = normalBags; bigLabel = '톤백';
        } else if (_viewUnit === 'lot') {
          bigNum = s.lots; bigLabel = 'LOT';
        } else {
          bigNum = fmtW(s.weight_kg); bigLabel = '';
        }

        html += '<div style="flex:1;min-width:160px;background:var(--bg-card,#1e1e2e);border-left:4px solid '+m.color+';border-radius:8px;padding:12px 14px">';
        html += '<div style="font-size:13px;color:'+m.color+';font-weight:700;margin-bottom:6px">'+m.icon+' '+m.label+'</div>';
        if (_viewUnit === 'mt') {
          html += '<div style="font-size:22px;font-weight:700;color:var(--text-primary,#e0e0e0)">'+bigNum+'</div>';
        } else {
          html += '<div style="font-size:22px;font-weight:700;color:var(--text-primary,#e0e0e0)">'+bigNum+'<span style="font-size:12px;font-weight:400;color:var(--text-muted,#888)"> '+bigLabel+'</span></div>';
        }
        if (sampleBags > 0) {
          html += '<div style="font-size:13px;font-weight:600;color:#f59e0b;margin-top:1px">'+sampleBags+'<span style="font-size:11px;font-weight:400;color:var(--text-muted,#888)"> 샘플</span></div>';
        }
        html += '<div style="font-size:12px;color:var(--text-muted,#888);margin-top:2px">'+s.lots+' LOT · '+fmtW(normalKg)+'</div>';
        if (sampleBags > 0) {
          html += '<div style="font-size:11px;color:#f59e0b;margin-top:1px">샘플: '+fmtW(sampleKg)+'</div>';
        }
        html += '</div>';
      });
      html += '</div></div>';
      html += '<div id="dash-matrix-area"></div>';
      html += '<div id="dash-integrity-area"></div>';
      el.innerHTML = html;
      renderProductMatrix(d.product_matrix || []);
      renderIntegrity(d.integrity || {}, d.lot_weight_summary || {});
    }).catch(function(){});
  }

"""

ANCHOR = "  function loadDashboardTables() {"

if VIEW_UNIT_HANDLER not in src and ANCHOR in src:
    src = src.replace(ANCHOR, VIEW_UNIT_HANDLER + ANCHOR, 1)
    changes.append("PATCH D: view-unit 라디오 버튼 이벤트 리스너 연결 (톤백/LOT/MT 전환)")
elif VIEW_UNIT_HANDLER in src:
    print("[INFO] PATCH D: 이미 적용됨")
else:
    print("[WARN] PATCH D: loadDashboardTables 앵커 못 찾음")

# ──────────────────────────────────────────────────────────────────
# 저장 + 검증
# ──────────────────────────────────────────────────────────────────
if not changes:
    print("[ERROR] 적용된 패치 없음")
    sys.exit(1)

# 바이트 레벨 오염 제거
raw = src.encode("utf-8")
raw = raw.replace(bytes([0x5c, 0x21]), bytes([0x21]))
final = raw.decode("utf-8")

JS.write_text(final, encoding="utf-8", newline="\n")
HTML.write_text(html, encoding="utf-8", newline="\n")

print(f"\n✅ 패치 완료 ({len(changes)}개)")
for i, c in enumerate(changes, 1):
    print(f"  {i}. {c}")
