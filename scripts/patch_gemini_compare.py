"""
patch_gemini_compare.py
  - backend/api/inbound.py : use_gemini Form param + dual-parse + compare response
  - frontend/js/sqm-onestop-inbound.js : Gemini checkbox + compare panel UI

Usage: python scripts/patch_gemini_compare.py [--dry-run]
"""
import sys, shutil
from pathlib import Path

DRY_RUN = '--dry-run' in sys.argv
ROOT    = Path(__file__).resolve().parent.parent
INBOUND = ROOT / 'backend' / 'api' / 'inbound.py'
ONESTOP = ROOT / 'frontend' / 'js' / 'sqm-onestop-inbound.js'

def read(p):
    return open(p, encoding='utf-8').read()

def write_atomic(p, c):
    if DRY_RUN:
        print(f'[DRY-RUN] {p.name} ({len(c)} chars)')
        return
    t = p.with_suffix(p.suffix + '.tmp')
    open(t, 'w', encoding='utf-8', newline='\n').write(c)
    t.replace(p)
    print(f'[OK] {p.name}')

# ── read ───────────────────────────────────────────────────────
be = read(INBOUND)
fe = read(ONESTOP)
be0, fe0 = len(be), len(fe)
patches = []

# ══════════════════════════════════════════════════════════════════
# BACKEND — inbound.py
# ══════════════════════════════════════════════════════════════════

# B1: Add use_gemini Form param to function signature
OLD_SIG = '    manual_con_return: str = Form("", description="manual CON RETURN date (YYYY-MM-DD) fallback when DO absent"),\n):'
NEW_SIG = ('    manual_con_return: str = Form("", description="manual CON RETURN date (YYYY-MM-DD) fallback when DO absent"),\n'
           '    use_gemini: bool = Form(False, description="True=좌표+Gemini 병행 파싱 (비교 모드)"),\n'
           '):')
if OLD_SIG in be:
    be = be.replace(OLD_SIG, NEW_SIG, 1)
    patches.append('B1: use_gemini Form param added')
else:
    print('[WARN] B1: function signature anchor not found')

# B2: After preview_rows loop, add Gemini compare block + update response
# Anchor: the "# 5. PL 데이터 DB 저장" comment that follows preview_rows build
OLD_B2 = '        # 5. PL 데이터 DB 저장 — dry_run=True 면 스킵 (Sprint 1-2-C 기본값)'
NEW_B2 = '''\
        # 4-B. Gemini 병행 파싱 (compare_mode)
        compare_mode = False
        gemini_preview_rows: list = []
        if use_gemini:
            try:
                g_pl = _gemini_parse_pdf(tmp_paths["pl"], pl.filename if pl else "")
                if g_pl is not None:
                    g_rows = getattr(g_pl, "rows", None) or getattr(g_pl, "lots", None) or []
                    for _gi, _gr in enumerate(g_rows, start=1):
                        gemini_preview_rows.append({
                            "no": _gi,
                            "lot_no":     str(_safe_attr(_gr, "lot_no", "lot")).strip(),
                            "sap_no":     str(_safe_attr(_gr, "sap_no") or inv_sap),
                            "bl_no":      str(bl_no),
                            "product":    str(_safe_attr(_gr, "product", "product_name") or tpl_product),
                            "status":     "NEW",
                            "container":  str(_safe_attr(_gr, "container_no", "container")),
                            "code":       str(_safe_attr(_gr, "product_code", "code")),
                            "lot_sqm":    str(_safe_attr(_gr, "lot_sqm")),
                            "mxbg":       str(_safe_attr(_gr, "mxbg_pallet", "maxibag")),
                            "net_kg":     str(_safe_attr(_gr, "net_weight", "net_kg")),
                            "gross_kg":   str(_safe_attr(_gr, "gross_weight", "gross_kg")),
                            "invoice_no": str(inv_no),
                            "ship_date":  str(ship_date),
                            "arrival":    str(arrival),
                            "con_return": str(con_return),
                            "free_time":  str(free_time),
                            "wh":         str(wh),
                            "xc_tag":     None,
                        })
                    compare_mode = len(gemini_preview_rows) > 0
                    logger.info(f"[compare] Gemini PL: {len(gemini_preview_rows)} rows")
                else:
                    _warn_messages.append("Gemini 파싱 실패 (결과 없음) — 좌표 결과만 표시")
            except Exception as _ge:
                logger.warning(f"[compare] Gemini PL error: {_ge}")
                _warn_messages.append(f"Gemini 파싱 오류 ({_ge.__class__.__name__}) — 좌표 결과만 표시")

        # 5. PL 데이터 DB 저장 — dry_run=True 면 스킵 (Sprint 1-2-C 기본값)'''

if OLD_B2 in be:
    be = be.replace(OLD_B2, NEW_B2, 1)
    patches.append('B2: Gemini compare block inserted after preview_rows loop')
else:
    print('[WARN] B2: preview_rows/save anchor not found')

# B3: Add compare_mode fields to response data dict
OLD_B3 = '                "saved_result": (saved_result.get("data") if isinstance(saved_result, dict) else None),'
NEW_B3 = ('                "saved_result": (saved_result.get("data") if isinstance(saved_result, dict) else None),\n'
          '                "compare_mode": compare_mode,\n'
          '                "coord_rows":   preview_rows if compare_mode else [],\n'
          '                "gemini_rows":  gemini_preview_rows,')
if OLD_B3 in be:
    be = be.replace(OLD_B3, NEW_B3, 1)
    patches.append('B3: compare_mode/coord_rows/gemini_rows added to response')
else:
    print('[WARN] B3: response data anchor not found')

# ══════════════════════════════════════════════════════════════════
# FRONTEND — sqm-onestop-inbound.js
# ══════════════════════════════════════════════════════════════════

# F1: Add Gemini checkbox in action buttons HTML (after parse-btn)
OLD_F1 = ("      '    <button class=\"btn btn-primary\" id=\"onestop-parse-btn\" onclick=\"window.onestopParseStart()\" disabled>▶ 파싱 시작</button>',\n"
          "      '    <button class=\"btn\" id=\"onestop-reparse-btn\" onclick=\"window.onestopParseRedo()\" disabled>↻ 다시 파싱</button>',")
NEW_F1 = ("      '    <button class=\"btn btn-primary\" id=\"onestop-parse-btn\" onclick=\"window.onestopParseStart()\" disabled>▶ 파싱 시작</button>',\n"
          "      '    <button class=\"btn\" id=\"onestop-reparse-btn\" onclick=\"window.onestopParseRedo()\" disabled>↻ 다시 파싱</button>',\n"
          "      '    <label id=\"onestop-gemini-label\" style=\"display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--text-muted);cursor:pointer;margin-left:4px\" title=\"좌표 파싱과 Gemini AI 파싱을 동시에 실행하여 결과를 비교합니다\">'\n"
          "        + '<input type=\"checkbox\" id=\"onestop-gemini-check\" style=\"cursor:pointer\"> 🤖 Gemini 비교</label>',")
if OLD_F1 in fe:
    fe = fe.replace(OLD_F1, NEW_F1, 1)
    patches.append('F1: Gemini checkbox added to action buttons')
else:
    print('[WARN] F1: action buttons anchor not found')

# F2: Append use_gemini to FormData in onestopParseStart
OLD_F2 = "    if (window._onestopDbTemplateId) form.append('template_id', String(window._onestopDbTemplateId));"
NEW_F2 = ("    if (window._onestopDbTemplateId) form.append('template_id', String(window._onestopDbTemplateId));\n"
          "    var _geminiCheck = document.getElementById('onestop-gemini-check');\n"
          "    form.append('use_gemini', (_geminiCheck && _geminiCheck.checked) ? 'true' : 'false');")
if OLD_F2 in fe:
    fe = fe.replace(OLD_F2, NEW_F2, 1)
    patches.append('F2: use_gemini appended to FormData')
else:
    print('[WARN] F2: FormData template_id anchor not found')

# F3: In XHR onload handler, detect compare_mode and call compare panel
# Anchor: the line that sets _onestopState.parsed after rows assignment
OLD_F3 = ("        _onestopState.previewRows = rows.slice();  /* 편집 대상 */\n"
          "        _onestopState.originalRows = JSON.parse(JSON.stringify(rows));  /* deep copy */\n"
          "        _onestopState.editedCells = {};\n"
          "        _onestopState.parsed = rows.length > 0;")
NEW_F3 = ("        /* compare_mode: show side-by-side, let user pick */\n"
          "        if (d.compare_mode && d.coord_rows && d.gemini_rows) {\n"
          "          _onestopState.previewRows = d.coord_rows.slice();\n"
          "          _onestopState.originalRows = JSON.parse(JSON.stringify(d.coord_rows));\n"
          "          _onestopState.editedCells = {};\n"
          "          _onestopState.parsed = d.coord_rows.length > 0;\n"
          "          _showGeminiComparePanel(d.coord_rows, d.gemini_rows);\n"
          "        } else {\n"
          "          _onestopState.previewRows = rows.slice();  /* 편집 대상 */\n"
          "          _onestopState.originalRows = JSON.parse(JSON.stringify(rows));  /* deep copy */\n"
          "          _onestopState.editedCells = {};\n"
          "          _onestopState.parsed = rows.length > 0;\n"
          "        }")
if OLD_F3 in fe:
    fe = fe.replace(OLD_F3, NEW_F3, 1)
    patches.append('F3: compare_mode branch added in XHR handler')
else:
    print('[WARN] F3: previewRows assignment anchor not found')

# F4: Add _showGeminiComparePanel function (insert before window._sqmOS export line)
COMPARE_COLS = ['lot_no','container','lot_sqm','mxbg','net_kg','gross_kg','arrival','con_return','free_time','wh']
COMPARE_LABELS = ['LOT No','컨테이너','LOT m²','맥시백','순중량','총중량','입항일','컨반납일','FreeTime','창고']

NEW_COMPARE_FN = (
    "\n"
    "  /* ── Gemini 비교 패널 ─────────────────────────────────────── */\n"
    "  var COMPARE_COLS   = " + repr(COMPARE_COLS) + ";\n"
    "  var COMPARE_LABELS = " + repr(COMPARE_LABELS) + ";\n"
    "\n"
    "  function _showGeminiComparePanel(coordRows, geminiRows) {\n"
    "    var existing = document.getElementById('sqm-gemini-compare');\n"
    "    if (existing) existing.remove();\n"
    "\n"
    "    var p = document.createElement('div');\n"
    "    p.id = 'sqm-gemini-compare';\n"
    "    p.style.cssText = 'position:fixed;top:80px;left:50%;transform:translateX(-50%);width:min(98vw,1300px);max-height:80vh;'\n"
    "      + 'background:var(--bg-card);border:1px solid var(--panel-border);border-radius:10px;'\n"
    "      + 'box-shadow:0 8px 40px rgba(0,0,0,.55);z-index:10060;display:flex;flex-direction:column';\n"
    "\n"
    "    /* header */\n"
    "    p.innerHTML = '<div id=\"sgc-hdr\" style=\"cursor:move;user-select:none;padding:9px 14px;border-bottom:1px solid var(--panel-border);'\n"
    "      + 'display:flex;align-items:center;gap:8px;border-radius:10px 10px 0 0;background:var(--panel)\">'\n"
    "      + '<span style=\"font-weight:700;font-size:13px;flex:1\">🔍 파싱 결과 비교 — 좌: 좌표 등록 / 우: Gemini AI</span>'\n"
    "      + '<button onclick=\"document.getElementById(\\'sqm-gemini-compare\\').remove()\" '\n"
    "      + 'style=\"background:none;border:none;cursor:pointer;color:var(--text-muted);font-size:1.3rem;line-height:1\">✕</button></div>'\n"
    "      + '<div style=\"overflow:auto;flex:1;padding:0\">' + _buildCompareTable(coordRows, geminiRows) + '</div>'\n"
    "      + '<div style=\"padding:10px 14px;border-top:1px solid var(--panel-border);display:flex;gap:10px;justify-content:flex-end;background:var(--panel);border-radius:0 0 10px 10px\">'\n"
    "      + '<span style=\"flex:1;font-size:12px;color:var(--text-muted)\">🟡 노란색 = 두 결과가 다른 셀  · 선택한 결과가 DB 업로드 대상이 됩니다</span>'\n"
    "      + '<button class=\"btn\" onclick=\"_selectCompareResult(\\'coord\\')\" style=\"border:2px solid var(--info,#42a5f5)\">📍 좌표 등록 선택</button>'\n"
    "      + '<button class=\"btn btn-primary\" onclick=\"_selectCompareResult(\\'gemini\\')\">🤖 Gemini 선택</button>'\n"
    "      + '</div>';\n"
    "\n"
    "    document.body.appendChild(p);\n"
    "\n"
    "    /* draggable header */\n"
    "    var drag = {on:false,sx:0,sy:0,ox:0,oy:0};\n"
    "    p.querySelector('#sgc-hdr').addEventListener('mousedown', function(e){\n"
    "      drag.on=true; drag.sx=e.clientX; drag.sy=e.clientY;\n"
    "      var r=p.getBoundingClientRect(); drag.ox=r.left; drag.oy=r.top;\n"
    "      p.style.transform='none'; p.style.left=r.left+'px'; e.preventDefault();\n"
    "    });\n"
    "    document.addEventListener('mousemove', function(e){\n"
    "      if (!drag.on) return;\n"
    "      p.style.left=(drag.ox+(e.clientX-drag.sx))+'px';\n"
    "      p.style.top =(drag.oy+(e.clientY-drag.sy))+'px';\n"
    "    });\n"
    "    document.addEventListener('mouseup', function(){ drag.on=false; });\n"
    "\n"
    "    /* store rows for selection */\n"
    "    p._coordRows  = coordRows;\n"
    "    p._geminiRows = geminiRows;\n"
    "  }\n"
    "\n"
    "  function _buildCompareTable(coordRows, geminiRows) {\n"
    "    var maxLen = Math.max(coordRows.length, geminiRows.length);\n"
    "    var thStyle = 'padding:5px 7px;border:1px solid var(--panel-border);background:var(--panel);font-size:11px;white-space:nowrap';\n"
    "    var tdStyle = 'padding:4px 6px;border:1px solid var(--panel-border);font-size:11px;white-space:nowrap';\n"
    "    var diffStyle = tdStyle + ';background:#fff3cd;color:#7a5c00';\n"
    "\n"
    "    var html = '<table style=\"border-collapse:collapse;width:100%;min-width:900px\">';\n"
    "    /* header row */\n"
    "    html += '<thead><tr>';\n"
    "    html += '<th style=\"' + thStyle + '\">#</th>';\n"
    "    COMPARE_COLS.forEach(function(c, i) {\n"
    "      html += '<th style=\"' + thStyle + ';color:var(--info,#42a5f5)\">' + COMPARE_LABELS[i] + '<br><small style=\"color:var(--text-muted)\">좌표</small></th>';\n"
    "      html += '<th style=\"' + thStyle + ';color:#27ae60\">' + COMPARE_LABELS[i] + '<br><small style=\"color:var(--text-muted)\">Gemini</small></th>';\n"
    "    });\n"
    "    html += '</tr></thead><tbody>';\n"
    "\n"
    "    for (var i = 0; i < maxLen; i++) {\n"
    "      var cr = coordRows[i]  || {};\n"
    "      var gr = geminiRows[i] || {};\n"
    "      html += '<tr>';\n"
    "      html += '<td style=\"' + tdStyle + ';text-align:center;color:var(--text-muted)\">' + (i+1) + '</td>';\n"
    "      COMPARE_COLS.forEach(function(col) {\n"
    "        var cv = String(cr[col] == null ? '' : cr[col]);\n"
    "        var gv = String(gr[col] == null ? '' : gr[col]);\n"
    "        var diff = cv !== gv;\n"
    "        html += '<td style=\"' + (diff ? diffStyle : tdStyle) + '\">' + escapeHtml(cv) + '</td>';\n"
    "        html += '<td style=\"' + (diff ? diffStyle : tdStyle) + '\">' + escapeHtml(gv) + '</td>';\n"
    "      });\n"
    "      html += '</tr>';\n"
    "    }\n"
    "    html += '</tbody></table>';\n"
    "    return html;\n"
    "  }\n"
    "\n"
    "  function _selectCompareResult(which) {\n"
    "    var p = document.getElementById('sqm-gemini-compare');\n"
    "    if (!p) return;\n"
    "    var chosen = which === 'gemini' ? p._geminiRows : p._coordRows;\n"
    "    _onestopState.previewRows  = chosen.slice();\n"
    "    _onestopState.originalRows = JSON.parse(JSON.stringify(chosen));\n"
    "    _onestopState.editedCells  = {};\n"
    "    _onestopState.parsed = chosen.length > 0;\n"
    "    _onestopRenderPreview();\n"
    "    p.remove();\n"
    "    showToast('success', (which === 'gemini' ? '🤖 Gemini' : '📍 좌표 등록') + ' 결과 선택됨 (' + chosen.length + '행)');\n"
    "  }\n"
)

ANCHOR_F4 = "  /* expose state for sqm-inline.js keyboard handler */\n  window._sqmOS = _onestopState;"
if ANCHOR_F4 in fe:
    fe = fe.replace(ANCHOR_F4, NEW_COMPARE_FN + "\n" + ANCHOR_F4, 1)
    patches.append('F4: _showGeminiComparePanel / _buildCompareTable / _selectCompareResult added')
else:
    print('[WARN] F4: _sqmOS export anchor not found')

# ── Write ──────────────────────────────────────────────────────────
print(f'\nPatches applied ({len(patches)}):')
for p in patches: print(f'  [+] {p}')
print(f'\nBackend: {be0} -> {len(be)} chars ({len(be)-be0:+d})')
print(f'Frontend: {fe0} -> {len(fe)} chars ({len(fe)-fe0:+d})')

if not DRY_RUN:
    for src in (INBOUND, ONESTOP):
        shutil.copy2(src, src.with_suffix(src.suffix + '.bak3'))
    print('[BAK] .bak3 backups created')

write_atomic(INBOUND, be)
write_atomic(ONESTOP, fe)
if not DRY_RUN:
    print('\nNext:')
    print('  node --check frontend/js/sqm-onestop-inbound.js')
    print('  python -m pytest tests/ -q')
