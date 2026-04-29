# -*- coding: utf-8 -*-
"""
SQM v8.6.5 - 4선사 x 4문서 x 2방식 파싱 비교표
방식: (1) 좌표 파싱(기준) vs (2) Gemini
결과: REPORTS/parse_comparison_final.html

실행:
  python scripts/run_comparison_6method.py           # 좌표+Gemini
  python scripts/run_comparison_6method.py --no-gemini  # 좌표만
"""
import os, sys, time, datetime, configparser, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURE = os.path.join(ROOT, "tests", "fixtures")

cfg = configparser.ConfigParser()
cfg.read(os.path.join(ROOT, "settings.ini"), encoding="utf-8")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "") or cfg.get("Gemini", "api_key", fallback="").strip()

parser_arg = argparse.ArgumentParser(description="SQM 파싱 비교")
parser_arg.add_argument("--no-gemini", action="store_true", help="Gemini 제외 (좌표만 실행)")
args = parser_arg.parse_args()

print("=" * 60)
print("  SQM v8.6.5 - Parsing Comparison (Coord vs Gemini)")
print("=" * 60)
print(f"  ① 좌표 파싱 : 항상 실행 (로컬, 기준값)")
if args.no_gemini:
    print(f"  ② Gemini    : SKIP (--no-gemini)")
else:
    print(f"  ② Gemini    : {'OK ' + GEMINI_KEY[:16]+'...' if GEMINI_KEY else 'KEY없음 — SKIP'}")
print()

DOCS = [
    ("ONE",    "DO", "ONE_DO.pdf"),    ("ONE",    "BL", "ONE_BL.pdf"),
    ("ONE",    "FA", "ONE_FA.pdf"),    ("ONE",    "PL", "ONE_PL.pdf"),
    ("HAPAG",  "DO", "HAPAG_DO.pdf"),  ("HAPAG",  "BL", "HAPAG_BL.pdf"),
    ("HAPAG",  "FA", "HAPAG_FA.pdf"),  ("HAPAG",  "PL", "HAPAG_PL.pdf"),
    ("MAERSK", "DO", "MAERSK_DO.pdf"), ("MAERSK", "BL", "MAERSK_BL.pdf"),
    ("MAERSK", "FA", "MAERSK_FA.pdf"), ("MAERSK", "PL", "MAERSK_PL.pdf"),
    ("MSC",    "DO", "MSC_DO.pdf"),    ("MSC",    "BL", "MSC_BL.pdf"),
    ("MSC",    "FA", "MSC_FA.pdf"),    ("MSC",    "PL", "MSC_PL.pdf"),
]
FIELDS = {
    "DO": ["bl_no", "vessel", "voyage", "port_of_loading", "port_of_discharge",
           "arrival_date", "gross_weight_kg", "container_count", "mrn", "msn"],
    "BL": ["bl_no", "vessel", "voyage", "port_of_loading", "port_of_discharge",
           "gross_weight_kg", "carrier_id"],
    "FA": ["sap_no", "invoice_no", "bl_no", "quantity_mt", "unit_price",
           "total_amount", "currency", "gross_weight_kg", "net_weight_kg",
           "package_count", "lot_count"],
    "PL": ["folio", "total_lots", "total_net_weight_kg", "total_gross_weight_kg",
           "total_maxibag", "container_count"],
}


def _dispatch(doc_type, parser, pdf_path):
    fn = {"DO": parser.parse_do, "BL": parser.parse_bl,
          "FA": parser.parse_invoice, "PL": parser.parse_packing_list}
    return fn[doc_type](pdf_path)


def _run(label, fn, doc_type, pdf_path):
    t0 = time.time()
    try:
        r = fn(doc_type, pdf_path)
        elapsed = time.time() - t0
        return (r, elapsed, None) if r is not None else (None, elapsed, "None 반환")
    except Exception as ex:
        return None, time.time() - t0, str(ex)[:120]


def run_coord(doc_type, pdf_path):
    from parsers.document_parser_modular import DocumentParser
    return _run("좌표", lambda dt, p: _dispatch(dt, DocumentParser(), p), doc_type, pdf_path)


def run_gemini(doc_type, pdf_path):
    if not GEMINI_KEY:
        return None, 0, "KEY없음"
    try:
        from features.ai.gemini_parser import GeminiDocumentParser
        return _run("Gemini", lambda dt, p: _dispatch(dt, GeminiDocumentParser(api_key=GEMINI_KEY), p), doc_type, pdf_path)
    except Exception as ex:
        return None, 0, str(ex)[:120]


def extract(result, field):
    if result is None:
        return ""
    if field == "container_count":
        return str(len(getattr(result, "containers", []) or []))
    if field == "lot_count":
        lots = getattr(result, "lots", None) or getattr(result, "lot_numbers", []) or []
        return str(len(lots))
    v = getattr(result, field, "")
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v) if v not in (None, "") else ""


# ── 실행 ──────────────────────────────────────────────────────────────────────
print("파싱 시작...")
results = []
for i, (carrier, doc_type, fname) in enumerate(DOCS):
    pdf_path = os.path.join(FIXTURE, fname)
    print(f"[{i+1:02d}/16] {carrier:6s} {doc_type}  ", end="", flush=True)
    if not os.path.exists(pdf_path):
        print("SKIP (파일없음)")
        results.append((carrier, doc_type, fname, None, 0, "파일없음", None, 0, "파일없음"))
        continue

    r1, t1, e1 = run_coord(doc_type, pdf_path)
    print(f"①좌표={'OK' if r1 else 'NG'} ", end="", flush=True)

    if args.no_gemini:
        r2, t2, e2 = None, 0, "SKIP"
    else:
        r2, t2, e2 = run_gemini(doc_type, pdf_path)
    print(f"②Gem={'OK' if r2 else ('SKIP' if e2 in ('KEY없음','SKIP') else 'NG')}")

    results.append((carrier, doc_type, fname, r1, t1, e1, r2, t2, e2))


# ── 정확도 계산 ───────────────────────────────────────────────────────────────
def calc_accuracy(results, method_idx):
    """method_idx: 0=coord(ref), 1=gemini"""
    match = total = 0
    all_skip = True
    for row in results:
        doc_type = row[1]
        base = 3 + method_idx * 3
        r_ref = row[3]
        r_ai  = row[base]
        e_ai  = row[base + 2]
        if e_ai not in ("KEY없음", "SKIP", "파일없음"):
            all_skip = False
        if e_ai in ("KEY없음", "SKIP", "파일없음"):
            continue
        for field in FIELDS[doc_type]:
            v_ref = extract(r_ref, field)
            v_ai  = extract(r_ai,  field)
            total += 1
            if v_ref.strip().lower() == v_ai.strip().lower():
                match += 1
    if all_skip:
        return None, None, "N/A"
    if total == 0:
        return 0, 0, "0%"
    return match, total, f"{match/total*100:.1f}%"


acc_coord  = (None, None, "100% (기준)")
acc_gemini = calc_accuracy(results, 1)

ok_coord  = sum(1 for r in results if r[3] is not None)
ok_gemini = sum(1 for r in results if r[6] is not None)


# ── HTML 생성 ─────────────────────────────────────────────────────────────────
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
CC = {"ONE": "#0d3b6e", "HAPAG": "#6e0d0d", "MAERSK": "#0d4a6e", "MSC": "#0d6e2e"}


def e(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def status_cell(r, err, t):
    if r is not None:
        return f'<td class="ok">✅ OK<br><small>{t:.1f}s</small></td>'
    if err and err in ("KEY없음", "SKIP"):
        return f'<td class="nk">⏭ {err}</td>'
    msg = e(err or "")
    short = e((err or "")[:60])
    return f'<td class="fail" title="{msg}">❌<br><small>{short}</small></td>'


def val_cell(v, ref):
    if not v:
        return '<td class="em">-</td>'
    if ref and v.strip().lower() == ref.strip().lower():
        return f'<td class="mt">{e(v)}</td>'
    if ref and v.strip().lower() != ref.strip().lower():
        return f'<td class="df" title="기준: {e(ref)}">{e(v)}</td>'
    return f'<td>{e(v)}</td>'


table_rows = []
for row in results:
    carrier, doc_type = row[0], row[1]
    r1, t1, e1 = row[3], row[4], row[5]
    r2, t2, e2 = row[6], row[7], row[8]
    fields = FIELDS[doc_type]
    color  = CC.get(carrier, "#333")
    n      = len(fields)

    table_rows.append(f"""
<tr class="hdr">
  <td rowspan="{n+2}" class="carr" style="background:{color}">{carrier}<br><b>{doc_type}</b></td>
  <td class="ml c1">①좌표(기준)</td>
  <td class="ml c2">②Gemini</td>
</tr>""")
    table_rows.append(f'<tr class="strow">{status_cell(r1,e1,t1)}{status_cell(r2,e2,t2)}</tr>')

    for field in fields:
        v1 = extract(r1, field)
        v2 = extract(r2, field)
        table_rows.append(
            f'<tr>'
            f'<td class="fn">{field}</td>'
            f'<td class="v1">{e(v1) if v1 else "-"}</td>'
            f'{val_cell(v2, v1)}'
            f'</tr>'
        )
    table_rows.append('<tr class="sp"><td colspan="4"></td></tr>')

m2, t2_total, p2 = acc_gemini
acc_row = f"""
<tr style="background:#1a1a2e;font-weight:bold;font-size:13px">
  <td class="carr" style="background:#333">정확도<br>합계</td>
  <td class="ok" style="text-align:center">100%<br><small>(기준값)</small></td>
  <td class="{'ok' if p2=='100.0%' else 'df' if p2!='N/A' else 'nk'}" style="text-align:center">
    <b>{p2}</b><br><small>{m2}/{t2_total if t2_total else '-'}</small>
  </td>
</tr>"""

gemini_status = "checked" if not args.no_gemini else ""

html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<title>SQM v8.6.5 파싱 비교 (좌표 vs Gemini)</title>
<style>
body{{font-family:'Malgun Gothic',sans-serif;font-size:12px;background:#12121f;color:#ddd;padding:16px;margin:0}}
h1{{color:#7ec8e3;font-size:20px;margin-bottom:4px}}
.meta{{color:#666;font-size:11px;margin-bottom:10px}}
.sum{{display:flex;gap:16px;background:#1e1e35;border-radius:8px;padding:14px;margin-bottom:10px}}
.si{{text-align:center}}.si .n{{font-size:24px;font-weight:bold}}.si .l{{font-size:10px;color:#888}}
.filter{{background:#1a1a35;border-radius:8px;padding:10px 14px;margin-bottom:10px;display:flex;gap:20px;align-items:center}}
.filter label{{display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px}}
.filter button{{background:#2a4a7a;color:#7ec8e3;border:none;border-radius:4px;padding:4px 12px;cursor:pointer}}
.leg{{display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap}}
.leg span{{padding:2px 10px;border-radius:4px;font-size:11px}}
table{{border-collapse:collapse;width:100%}}
th{{background:#1e1e35;color:#7ec8e3;padding:6px 10px;text-align:left;position:sticky;top:0;z-index:9}}
td{{padding:4px 8px;border-bottom:1px solid #2a2a3a;vertical-align:middle}}
.carr{{font-size:13px;color:#fff;text-align:center;width:60px;border-right:2px solid #444;font-weight:bold}}
.hdr td{{background:#1a1a30}}
.ml{{font-weight:bold;font-size:11px;text-align:center;padding:4px;min-width:120px}}
.c1{{background:#122012;color:#7ec87e}}.c2{{background:#201212;color:#e87e7e}}
.strow td{{text-align:center;font-size:11px}}
.fn{{color:#999;width:140px;font-size:11px}}
.v1{{color:#7ec87e;font-weight:bold;min-width:120px}}
.ok{{color:#7ec87e}}.fail{{color:#e87e7e;font-size:10px;line-height:1.3}}
.nk{{color:#777;font-size:10px}}
.mt{{color:#7ec87e}}.df{{color:#f0a060;font-weight:bold;background:#201808}}.em{{color:#444}}
.sp td{{height:8px;background:#0d0d1a}}
small{{font-size:9px;color:#888}}
</style></head><body>
<h1>SQM v8.6.5 — 파싱 비교: ① 좌표 파싱 vs ② Gemini</h1>
<div class="meta">생성: {now} | 4선사×4문서=16건 | 노란 셀 = 좌표와 다른 값</div>
<div class="sum">
  <div class="si"><div class="n" style="color:#7ec87e">{ok_coord}/16</div><div class="l">① 좌표(기준)</div></div>
  <div class="si"><div class="n" style="color:#e87e7e">{ok_gemini}/16</div><div class="l">② Gemini</div></div>
  <div class="si"><div class="n" style="color:#{'7ec87e' if p2=='100.0%' else 'f0a060' if p2!='N/A' else '888'}">{p2}</div><div class="l">Gemini 정확도</div></div>
</div>
<div class="filter">
  <span style="color:#7ec8e3;font-weight:bold">파싱 결과 표시:</span>
  <label><input type="checkbox" disabled checked> ① 좌표(기준)</label>
  <label><input type="checkbox" id="cb-gemini" {gemini_status} onchange="toggleGemini(this)"> ② Gemini</label>
  <button onclick="document.getElementById('cb-gemini').checked=true;toggleGemini(document.getElementById('cb-gemini'))">전체 표시</button>
</div>
<div class="leg">
  <span style="background:#122012;color:#7ec87e">일치 (좌표와 동일)</span>
  <span style="background:#201808;color:#f0a060">불일치 (값이 다름)</span>
  <span style="background:#201010;color:#e87e7e">실패 (파싱 에러)</span>
  <span style="background:#1a1a30;color:#aaa">빈 값</span>
</div>
<table>
<thead><tr>
  <th>선사/문서</th>
  <th>① 좌표(기준)</th>
  <th class="col-gemini">② Gemini</th>
</tr>
{acc_row}
</thead>
<tbody>{''.join(table_rows)}</tbody>
</table>

<h2 style="color:#7ec8e3;margin-top:20px">정확도 요약</h2>
<table style="width:auto">
<thead><tr><th>방식</th><th>일치 필드</th><th>전체 필드</th><th>정확도(%)</th></tr></thead>
<tbody>
<tr><td>① 좌표 (기준)</td><td>-</td><td>-</td><td class="ok">100% (기준)</td></tr>
<tr><td>② Gemini</td>
  <td>{m2 if m2 is not None else "N/A"}</td>
  <td>{t2_total if t2_total is not None else "N/A"}</td>
  <td class="{'ok' if p2=='100.0%' else 'df' if p2!='N/A' else 'nk'}">{p2}</td>
</tr>
</tbody>
</table>

<script>
function toggleGemini(cb) {{
  document.querySelectorAll('.col-gemini').forEach(function(el) {{
    el.style.display = cb.checked ? '' : 'none';
  }});
  localStorage.setItem('sqm-show-gemini', cb.checked);
}}
(function() {{
  var saved = localStorage.getItem('sqm-show-gemini');
  if (saved === 'false') {{
    var cb = document.getElementById('cb-gemini');
    if (cb) {{ cb.checked = false; toggleGemini(cb); }}
  }}
}})();
</script>
</body></html>"""

out = os.path.join(ROOT, "REPORTS", "parse_comparison_final.html")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8", newline="\n") as f:
    f.write(html)

print(f"\n{'='*60}")
print(f"  ① 좌표 파싱 : {ok_coord}/16 성공")
print(f"  ② Gemini    : {ok_gemini}/16 성공 | 정확도: {p2}")
print(f"{'='*60}")
print(f"  보고서: {out}")
