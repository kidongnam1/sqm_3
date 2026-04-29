# -*- coding: utf-8 -*-
"""
4 Carriers x 4 Doc Types x 3 Methods comparison
Methods: 1) Coordinate  2) Gemini  3) Groq
Output: HTML report
"""
import os, sys, time, configparser, traceback, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FIXTURE = os.path.join(ROOT, "tests", "fixtures")

cfg = configparser.ConfigParser()
cfg.read(os.path.join(ROOT, "settings.ini"), encoding="utf-8")

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "") or cfg.get("Gemini", "api_key", fallback="")
GROQ_KEY   = os.environ.get("GROQ_API_KEY", "")   or cfg.get("Groq",   "api_key", fallback="")

DOCS = [
    ("ONE",    "DO",  "ONE_DO.pdf"),
    ("ONE",    "BL",  "ONE_BL.pdf"),
    ("ONE",    "FA",  "ONE_FA.pdf"),
    ("ONE",    "PL",  "ONE_PL.pdf"),
    ("HAPAG",  "DO",  "HAPAG_DO.pdf"),
    ("HAPAG",  "BL",  "HAPAG_BL.pdf"),
    ("HAPAG",  "FA",  "HAPAG_FA.pdf"),
    ("HAPAG",  "PL",  "HAPAG_PL.pdf"),
    ("MAERSK", "DO",  "MAERSK_DO.pdf"),
    ("MAERSK", "BL",  "MAERSK_BL.pdf"),
    ("MAERSK", "FA",  "MAERSK_FA.pdf"),
    ("MAERSK", "PL",  "MAERSK_PL.pdf"),
    ("MSC",    "DO",  "MSC_DO.pdf"),
    ("MSC",    "BL",  "MSC_BL.pdf"),
    ("MSC",    "FA",  "MSC_FA.pdf"),
    ("MSC",    "PL",  "MSC_PL.pdf"),
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

# ── 1. Coordinate parser ──────────────────────────────────────────────────────
def run_coord(carrier, doc_type, pdf_path):
    from parsers.document_parser_modular import DocumentParser
    p = DocumentParser()
    t0 = time.time()
    try:
        if doc_type == "DO": r = p.parse_do(pdf_path)
        elif doc_type == "BL": r = p.parse_bl(pdf_path)
        elif doc_type == "FA": r = p.parse_invoice(pdf_path)
        else:                  r = p.parse_packing_list(pdf_path)
        elapsed = time.time() - t0
        if r is None:
            return None, elapsed, "None 반환"
        return r, elapsed, None
    except Exception as e:
        return None, time.time()-t0, str(e)[:80]

# ── 2. Gemini parser ──────────────────────────────────────────────────────────
def run_gemini(carrier, doc_type, pdf_path):
    if not GEMINI_KEY:
        return None, 0, "API KEY 없음"
    t0 = time.time()
    try:
        from features.ai.gemini_parser import GeminiDocumentParser
        p = GeminiDocumentParser(api_key=GEMINI_KEY)
        if doc_type == "DO": r = p.parse_do(pdf_path)
        elif doc_type == "BL": r = p.parse_bl(pdf_path)
        elif doc_type == "FA": r = p.parse_invoice(pdf_path)
        else:                  r = p.parse_packing_list(pdf_path)
        elapsed = time.time() - t0
        if r is None:
            return None, elapsed, "None 반환"
        return r, elapsed, None
    except Exception as e:
        return None, time.time()-t0, str(e)[:100]

# ── 3. Groq parser ────────────────────────────────────────────────────────────
def run_groq(carrier, doc_type, pdf_path):
    if not GROQ_KEY:
        return None, 0, "API KEY 없음 (Windows 환경변수 GROQ_API_KEY 필요)"
    t0 = time.time()
    try:
        from features.ai.groq_parser import create_groq_parser
        p = create_groq_parser(api_key=GROQ_KEY)
        if doc_type == "DO": r = p.parse_do(pdf_path)
        elif doc_type == "BL": r = p.parse_bl(pdf_path)
        elif doc_type == "FA": r = p.parse_invoice(pdf_path)
        else:                  r = p.parse_packing_list(pdf_path)
        elapsed = time.time() - t0
        if r is None:
            return None, elapsed, "None 반환"
        return r, elapsed, None
    except Exception as e:
        return None, time.time()-t0, str(e)[:100]

# ── field extractor ───────────────────────────────────────────────────────────
def extract(result, field):
    if result is None:
        return ""
    if field == "container_count":
        c = getattr(result, "containers", []) or []
        return str(len(c))
    if field == "lot_count":
        lots = getattr(result, "lots", None) or getattr(result, "lot_numbers", []) or []
        return str(len(lots))
    v = getattr(result, field, "")
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v) if v not in (None, "") else ""

# ── run all ───────────────────────────────────────────────────────────────────
results = []
total = len(DOCS)
for i, (carrier, doc_type, fname) in enumerate(DOCS):
    pdf_path = os.path.join(FIXTURE, fname)
    print(f"[{i+1:02d}/{total}] {carrier} {doc_type} ...", end=" ", flush=True)
    if not os.path.exists(pdf_path):
        results.append((carrier, doc_type, fname, None, 0, "파일없음",
                                                   None, 0, "파일없음",
                                                   None, 0, "파일없음"))
        print("SKIP (no file)")
        continue

    r1, t1, e1 = run_coord(carrier, doc_type, pdf_path)
    print(f"COORD={'OK' if r1 else 'FAIL'}", end=" ", flush=True)

    r2, t2, e2 = run_gemini(carrier, doc_type, pdf_path)
    print(f"GEMINI={'OK' if r2 else 'FAIL'}", end=" ", flush=True)

    r3, t3, e3 = run_groq(carrier, doc_type, pdf_path)
    print(f"GROQ={'OK' if r3 else 'FAIL'}")

    results.append((carrier, doc_type, fname, r1, t1, e1, r2, t2, e2, r3, t3, e3))

# ── HTML report ───────────────────────────────────────────────────────────────
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

carrier_colors = {
    "ONE": "#1a3a5c", "HAPAG": "#7a1c1c",
    "MAERSK": "#1c4a7a", "MSC": "#1c5c2c"
}

def cell(val, ok_val=None):
    if val == "":
        return '<td class="empty">-</td>'
    if ok_val and val == ok_val:
        return f'<td class="match">{val}</td>'
    return f'<td>{val}</td>'

def status_cell(r, err):
    if r is not None:
        return '<td class="ok">✅ OK</td>'
    if err and "KEY 없음" in err:
        return f'<td class="nokey">🔑 {err}</td>'
    if err:
        return f'<td class="fail">❌ {err}</td>'
    return '<td class="fail">❌</td>'

def time_cell(t, r):
    if r is None: return '<td class="na">-</td>'
    return f'<td class="time">{t:.2f}s</td>'

rows_html = []
for (carrier, doc_type, fname, r1, t1, e1, r2, t2, e2, r3, t3, e3) in results:
    fields = FIELDS[doc_type]
    color = carrier_colors.get(carrier, "#333")
    n = len(fields)

    # header row
    rows_html.append(f'''
    <tr class="doc-header">
      <td rowspan="{n+2}" class="carrier-cell" style="background:{color}">{carrier}<br><span class="doctype">{doc_type}</span></td>
      <td colspan="2" class="method-label coord-label">① 좌표 파싱</td>
      <td colspan="2" class="method-label gemini-label">② Gemini API</td>
      <td colspan="2" class="method-label groq-label">③ Groq API</td>
    </tr>
    <tr class="status-row">
      {status_cell(r1,e1)}{time_cell(t1,r1)}
      {status_cell(r2,e2)}{time_cell(t2,r2)}
      {status_cell(r3,e3)}{time_cell(t3,r3)}
    </tr>''')

    for field in fields:
        v1 = extract(r1, field)
        v2 = extract(r2, field)
        v3 = extract(r3, field)
        # 일치 여부 표시
        def styled(v, ref):
            if not v: return '<td class="empty">-</td>'
            if ref and v == ref: return f'<td class="match">{v}</td>'
            if ref and v != ref and ref != "": return f'<td class="diff">{v}</td>'
            return f'<td>{v}</td>'
        rows_html.append(f'''
    <tr>
      <td class="field-name">{field}</td>
      <td class="v1">{v1 or "-"}</td>
      {styled(v2, v1)}
      {styled(v3, v1)}
    </tr>''')

    rows_html.append('<tr class="spacer"><td colspan="7"></td></tr>')

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>SQM v8.6.5 — 파싱 방식 3종 비교표</title>
<style>
  body {{ font-family: 'Malgun Gothic', Arial, sans-serif; font-size:12px;
         background:#1a1a2e; color:#e0e0e0; margin:0; padding:16px; }}
  h1 {{ color:#7ec8e3; font-size:18px; margin-bottom:4px; }}
  .meta {{ color:#888; font-size:11px; margin-bottom:16px; }}
  .legend {{ display:flex; gap:12px; margin-bottom:12px; flex-wrap:wrap; }}
  .legend span {{ padding:3px 10px; border-radius:4px; font-size:11px; }}
  table {{ border-collapse:collapse; width:100%; }}
  th {{ background:#2a2a4a; color:#7ec8e3; padding:6px 10px; text-align:left;
        position:sticky; top:0; z-index:10; }}
  td {{ padding:4px 8px; border-bottom:1px solid #333; vertical-align:middle; }}
  .carrier-cell {{ font-weight:bold; font-size:13px; color:#fff; text-align:center;
                   width:60px; border-right:2px solid #555; }}
  .doctype {{ font-size:16px; font-weight:bold; }}
  .doc-header td {{ background:#252540; }}
  .method-label {{ font-weight:bold; font-size:11px; text-align:center; padding:4px; }}
  .coord-label {{ background:#1a3a1a; color:#7ec87e; }}
  .gemini-label {{ background:#3a1a1a; color:#e87e7e; }}
  .groq-label {{ background:#1a2a3a; color:#7eaee8; }}
  .status-row td {{ text-align:center; font-size:11px; }}
  .field-name {{ color:#aaa; font-size:11px; width:120px; }}
  .v1 {{ color:#7ec87e; font-weight:bold; }}
  .ok {{ color:#7ec87e; }}
  .match {{ color:#7ec87e; }}
  .diff {{ color:#e8a07e; font-weight:bold; }}
  .fail {{ color:#e87e7e; font-size:10px; }}
  .nokey {{ color:#888; font-size:10px; }}
  .na {{ color:#555; }}
  .empty {{ color:#555; }}
  .time {{ color:#888; font-size:10px; }}
  .spacer td {{ height:10px; background:#111; }}
  .summary {{ background:#252540; border-radius:8px; padding:12px; margin-bottom:16px;
              display:flex; gap:20px; flex-wrap:wrap; }}
  .summary-item {{ text-align:center; }}
  .summary-item .num {{ font-size:24px; font-weight:bold; }}
  .summary-item .lbl {{ font-size:11px; color:#888; }}
  .coord-num {{ color:#7ec87e; }}
  .gemini-num {{ color:#e87e7e; }}
  .groq-num {{ color:#7eaee8; }}
</style>
</head>
<body>
<h1>SQM v8.6.5 — 파싱 방식 3종 비교표</h1>
<div class="meta">생성: {now} &nbsp;|&nbsp; 4 선사 × 4 문서 = 16건 &nbsp;|&nbsp;
① 좌표 파싱 &nbsp; ② Gemini API &nbsp; ③ Groq API</div>

<div class="legend">
  <span style="background:#1a3a1a;color:#7ec87e">🟢 일치 (기준값과 동일)</span>
  <span style="background:#3a2a1a;color:#e8a07e">🟠 불일치 (기준값과 다름)</span>
  <span style="background:#3a1a1a;color:#e87e7e">🔴 파싱 실패</span>
  <span style="background:#252540;color:#888">⚪ 데이터 없음</span>
  <span style="background:#1a2a3a;color:#7eaee8">🔵 기준값 (좌표 파싱)</span>
</div>

<div class="summary">
  <div class="summary-item">
    <div class="num coord-num">{sum(1 for r in results if r[3] is not None)}/16</div>
    <div class="lbl">① 좌표 파싱 성공</div>
  </div>
  <div class="summary-item">
    <div class="num gemini-num">{sum(1 for r in results if r[6] is not None)}/16</div>
    <div class="lbl">② Gemini 성공</div>
  </div>
  <div class="summary-item">
    <div class="num groq-num">{sum(1 for r in results if r[9] is not None)}/16</div>
    <div class="lbl">③ Groq 성공</div>
  </div>
  <div class="summary-item">
    <div class="num" style="color:#7ec8e3">Gemini KEY: {'✅ 있음' if GEMINI_KEY else '❌ 없음'}</div>
    <div class="lbl">Groq KEY: {'✅ 있음' if GROQ_KEY else '❌ 없음 (Win ENV 필요)'}</div>
  </div>
</div>

<table>
<thead>
  <tr>
    <th>선사/문서</th>
    <th>필드</th>
    <th>① 좌표 값</th>
    <th>② Gemini 값</th>
    <th>③ Groq 값</th>
  </tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</body>
</html>"""

out = os.path.join(ROOT, "REPORTS", "parse_comparison_3method.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n✅ 리포트 저장: {out}")
print(f"좌표: {sum(1 for r in results if r[3] is not None)}/16")
print(f"Gemini: {sum(1 for r in results if r[6] is not None)}/16")
print(f"Groq: {sum(1 for r in results if r[9] is not None)}/16")
