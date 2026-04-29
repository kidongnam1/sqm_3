# -*- coding: utf-8 -*-
"""
SQM v8.6.5 - 4선사 x 4문서 x 6방식 파싱 비교표
Windows PowerShell: python scripts\run_comparison_windows.py
결과: REPORTS\parse_comparison_5method.html
"""
import os, sys, time, datetime, configparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURE = os.path.join(ROOT, "tests", "fixtures")

cfg = configparser.ConfigParser()
cfg.read(os.path.join(ROOT, "settings.ini"), encoding="utf-8")

GEMINI_KEY     = os.environ.get("GEMINI_API_KEY","")     or cfg.get("Gemini",    "api_key", fallback="")
GROQ_KEY       = os.environ.get("GROQ_API_KEY","")       or cfg.get("Groq",       "api_key", fallback="")
XAI_KEY        = os.environ.get("XAI_API_KEY","")        or cfg.get("xAI",        "api_key", fallback="")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY","") or cfg.get("OpenRouter", "api_key", fallback="")
OPENAI_KEY     = os.environ.get("OPENAI_API_KEY","")     or cfg.get("OpenAI",     "api_key", fallback="")

print("=" * 60)
print("  SQM v8.6.5 — 6방식 파싱 비교")
print("=" * 60)
print(f"  ① 좌표 파싱  : 항상 실행 (로컬)")
print(f"  ② Gemini     : {'OK ' + GEMINI_KEY[:16]+'...'     if GEMINI_KEY     else 'KEY없음'}")
print(f"  ③ Groq       : {'OK ' + GROQ_KEY[:16]+'...'       if GROQ_KEY       else 'KEY없음'}")
print(f"  ④ xAI Grok   : {'OK ' + XAI_KEY[:16]+'...'        if XAI_KEY        else 'KEY없음'}")
print(f"  ⑤ OpenRouter : {'OK ' + OPENROUTER_KEY[:16]+'...' if OPENROUTER_KEY else 'KEY없음'}")
print(f"  ⑥ OpenAI    : {'OK ' + OPENAI_KEY[:16]+'...'      if OPENAI_KEY     else 'KEY없음 (env OPENAI_API_KEY)'}")
print()

DOCS = [
    ("ONE",    "DO","ONE_DO.pdf"),    ("ONE",    "BL","ONE_BL.pdf"),
    ("ONE",    "FA","ONE_FA.pdf"),    ("ONE",    "PL","ONE_PL.pdf"),
    ("HAPAG",  "DO","HAPAG_DO.pdf"),  ("HAPAG",  "BL","HAPAG_BL.pdf"),
    ("HAPAG",  "FA","HAPAG_FA.pdf"),  ("HAPAG",  "PL","HAPAG_PL.pdf"),
    ("MAERSK", "DO","MAERSK_DO.pdf"), ("MAERSK", "BL","MAERSK_BL.pdf"),
    ("MAERSK", "FA","MAERSK_FA.pdf"), ("MAERSK", "PL","MAERSK_PL.pdf"),
    ("MSC",    "DO","MSC_DO.pdf"),    ("MSC",    "BL","MSC_BL.pdf"),
    ("MSC",    "FA","MSC_FA.pdf"),    ("MSC",    "PL","MSC_PL.pdf"),
]
FIELDS = {
    "DO":["bl_no","vessel","voyage","port_of_loading","port_of_discharge",
          "arrival_date","gross_weight_kg","container_count","mrn","msn"],
    "BL":["bl_no","vessel","voyage","port_of_loading","port_of_discharge",
          "gross_weight_kg","carrier_id"],
    "FA":["sap_no","invoice_no","bl_no","quantity_mt","unit_price",
          "total_amount","currency","gross_weight_kg","net_weight_kg",
          "package_count","lot_count"],
    "PL":["folio","total_lots","total_net_weight_kg","total_gross_weight_kg",
          "total_maxibag","container_count"],
}

def _dispatch(doc_type, parser, pdf_path):
    fn = {"DO":parser.parse_do,"BL":parser.parse_bl,
          "FA":parser.parse_invoice,"PL":parser.parse_packing_list}
    return fn[doc_type](pdf_path)

def _run(label, fn, doc_type, pdf_path):
    t0 = time.time()
    try:
        r = fn(doc_type, pdf_path)
        elapsed = time.time() - t0
        if r is None:
            return None, elapsed, "None 반환"
        return r, elapsed, None
    except Exception as e:
        return None, time.time()-t0, str(e)

def run_coord(doc_type, pdf_path):
    from parsers.document_parser_modular import DocumentParser
    return _run("좌표", lambda dt,p: _dispatch(dt, DocumentParser(), p), doc_type, pdf_path)

def run_gemini(doc_type, pdf_path):
    if not GEMINI_KEY: return None, 0, "KEY없음"
    try:
        from features.ai.gemini_parser import GeminiDocumentParser
        return _run("Gemini", lambda dt,p: _dispatch(dt, GeminiDocumentParser(api_key=GEMINI_KEY), p), doc_type, pdf_path)
    except Exception as e:
        return None, 0, str(e)

def _run_oai_compat(name, base_url, model, key, doc_type, pdf_path):
    if not key: return None, 0, f"KEY없음"
    from features.ai.openai_compatible_parser import OpenAICompatibleTextParser
    p = OpenAICompatibleTextParser(provider_name=name, base_url=base_url, model=model, api_key=key)
    return _run(name, lambda dt,pdf: _dispatch(dt, p, pdf), doc_type, pdf_path)

def run_groq(doc_type, pdf_path):
    return _run_oai_compat("Groq","https://api.groq.com/openai/v1","llama-3.3-70b-versatile",GROQ_KEY,doc_type,pdf_path)

def run_xai(doc_type, pdf_path):
    return _run_oai_compat("xAI","https://api.x.ai/v1","grok-beta",XAI_KEY,doc_type,pdf_path)

def run_openrouter(doc_type, pdf_path):
    return _run_oai_compat("OpenRouter","https://openrouter.ai/api/v1","mistralai/mistral-7b-instruct:free",OPENROUTER_KEY,doc_type,pdf_path)

def run_openai(doc_type, pdf_path):
    return _run_oai_compat("OpenAI","https://api.openai.com/v1","gpt-4o-mini",OPENAI_KEY,doc_type,pdf_path)

def extract(result, field):
    if result is None: return ""
    if field == "container_count":
        return str(len(getattr(result,"containers",[]) or []))
    if field == "lot_count":
        lots = getattr(result,"lots",None) or getattr(result,"lot_numbers",[]) or []
        return str(len(lots))
    v = getattr(result, field, "")
    if hasattr(v,"isoformat"): return v.isoformat()
    return str(v) if v not in (None,"") else ""

# ── 실행 ─────────────────────────────────────────────────────────────────────
results = []
for i,(carrier,doc_type,fname) in enumerate(DOCS):
    pdf_path = os.path.join(FIXTURE, fname)
    print(f"[{i+1:02d}/16] {carrier:6s} {doc_type}  ", end="", flush=True)
    if not os.path.exists(pdf_path):
        print("SKIP (파일없음)")
        results.append((carrier,doc_type,fname)+(None,0,"파일없음")*6)
        continue
    r1,t1,e1 = run_coord(doc_type, pdf_path);      print(f"좌표={'OK' if r1 else 'NG'} ",end="",flush=True)
    r2,t2,e2 = run_gemini(doc_type, pdf_path);     print(f"Gem={'OK' if r2 else 'NG'} ", end="",flush=True)
    r3,t3,e3 = run_groq(doc_type, pdf_path);       print(f"Groq={'OK' if r3 else 'NG'} ",end="",flush=True)
    r4,t4,e4 = run_xai(doc_type, pdf_path);        print(f"xAI={'OK' if r4 else 'NG'} ", end="",flush=True)
    r5,t5,e5 = run_openrouter(doc_type, pdf_path); print(f"OR={'OK' if r5 else 'NG'} ",  end="",flush=True)
    r6,t6,e6 = run_openai(doc_type, pdf_path);     print(f"OAI={'OK' if r6 else 'NG'}")
    results.append((carrier,doc_type,fname, r1,t1,e1, r2,t2,e2, r3,t3,e3, r4,t4,e4, r5,t5,e5, r6,t6,e6))

# ── HTML 생성 ─────────────────────────────────────────────────────────────────
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
ok = [sum(1 for r in results if r[3+i*3] is not None) for i in range(6)]
CC = {"ONE":"#0d3b6e","HAPAG":"#6e0d0d","MAERSK":"#0d4a6e","MSC":"#0d6e2e"}

def e(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace('"',"&quot;")

def sc(r, err, t):
    """status + time — single cell"""
    tm = f"<br><small>{t:.1f}s</small>" if r else ""
    if r is not None:
        return f'<td class="ok">✅ OK{tm}</td>'
    if err and "KEY없음" in err:
        return f'<td class="nk">🔑 KEY없음</td>'
    msg = e(err or "")
    return f'<td class="fail" title="{msg}">❌<br><small style="font-size:9px;color:#e88">{e((err or "")[:60])}</small></td>'

def vc(v, ref):
    if not v: return '<td class="em">-</td>'
    if ref and v == ref: return f'<td class="mt">{e(v)}</td>'
    if ref and v != ref: return f'<td class="df" title="기준: {e(ref)}">{e(v)}</td>'
    return f'<td>{e(v)}</td>'

rows = []
for row in results:
    carrier,doc_type = row[0],row[1]
    r1,t1,e1 = row[3],row[4],row[5]
    r2,t2,e2 = row[6],row[7],row[8]
    r3,t3,e3 = row[9],row[10],row[11]
    r4,t4,e4 = row[12],row[13],row[14]
    r5,t5,e5 = row[15],row[16],row[17]
    r6,t6,e6 = row[18],row[19],row[20]
    fields = FIELDS[doc_type]
    color  = CC.get(carrier,"#333")
    n      = len(fields)
    # method header + status row (각 1셀씩 — 정렬 일치)
    rows.append(f"""
<tr class="hdr">
  <td rowspan="{n+2}" class="carr" style="background:{color}">{carrier}<br><b>{doc_type}</b></td>
  <td class="ml c1">① 좌표</td>
  <td class="ml c2">② Gemini</td>
  <td class="ml c3">③ Groq<br><small>llama-3.3-70b</small></td>
  <td class="ml c4">④ xAI<br><small>grok-beta</small></td>
  <td class="ml c5">⑤ OpenRouter<br><small>mistral-7b</small></td>
  <td class="ml c6">⑥ OpenAI<br><small>gpt-4o-mini</small></td>
</tr>
<tr class="strow">
  {sc(r1,e1,t1)}{sc(r2,e2,t2)}{sc(r3,e3,t3)}{sc(r4,e4,t4)}{sc(r5,e5,t5)}{sc(r6,e6,t6)}
</tr>""")
    for field in fields:
        v1,v2,v3,v4,v5,v6 = (extract(r,field) for r in (r1,r2,r3,r4,r5,r6))
        rows.append(f"""
<tr>
  <td class="fn">{field}</td>
  <td class="v1">{e(v1) if v1 else "-"}</td>
  {vc(v2,v1)}{vc(v3,v1)}{vc(v4,v1)}{vc(v5,v1)}{vc(v6,v1)}
</tr>""")
    rows.append('<tr class="sp"><td colspan="8"></td></tr>')

html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<title>SQM v8.6.5 파싱 6방식 비교</title>
<style>
body{{font-family:'Malgun Gothic',sans-serif;font-size:12px;background:#12121f;color:#ddd;padding:16px;margin:0}}
h1{{color:#7ec8e3;font-size:20px;margin-bottom:4px}}
.meta{{color:#666;font-size:11px;margin-bottom:14px}}
.sum{{display:flex;gap:16px;background:#1e1e35;border-radius:8px;padding:14px;margin-bottom:14px;flex-wrap:wrap}}
.si{{text-align:center}}.si .n{{font-size:24px;font-weight:bold}}.si .l{{font-size:10px;color:#888}}
.c1n{{color:#7ec87e}}.c2n{{color:#e87e7e}}.c3n{{color:#7eaee8}}
.c4n{{color:#e8c87e}}.c5n{{color:#c87ee8}}.c6n{{color:#7ee8d8}}
.leg{{display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap}}
.leg span{{padding:2px 10px;border-radius:4px;font-size:11px}}
table{{border-collapse:collapse;width:100%}}
th{{background:#1e1e35;color:#7ec8e3;padding:6px 10px;text-align:left;position:sticky;top:0;z-index:9}}
td{{padding:4px 8px;border-bottom:1px solid #2a2a3a;vertical-align:middle}}
.carr{{font-size:13px;color:#fff;text-align:center;width:55px;border-right:2px solid #444;font-weight:bold}}
.hdr td{{background:#1a1a30}}
.ml{{font-weight:bold;font-size:11px;text-align:center;padding:4px;width:120px}}
.c1{{background:#122012;color:#7ec87e}}.c2{{background:#201212;color:#e87e7e}}
.c3{{background:#121a28;color:#7eaee8}}.c4{{background:#201c12;color:#e8c87e}}
.c5{{background:#1a1228;color:#c87ee8}}.c6{{background:#0f1e1e;color:#7ee8d8}}
.strow td{{text-align:center;font-size:11px;vertical-align:middle}}
.fn{{color:#999;width:130px;font-size:11px}}
.v1{{color:#7ec87e;font-weight:bold;width:120px}}
.ok{{color:#7ec87e}}.fail{{color:#e87e7e;font-size:10px;line-height:1.3}}
.nk{{color:#777;font-size:10px}}
.mt{{color:#7ec87e}}.df{{color:#f0a060;font-weight:bold}}.em{{color:#444}}
.sp td{{height:8px;background:#0d0d1a}}
small{{font-size:9px;color:#888}}
</style></head><body>
<h1>SQM v8.6.5 — 파싱 6방식 비교표</h1>
<div class="meta">생성: {now} | 4선사×4문서=16건 | ①좌표 ②Gemini ③Groq ④xAI ⑤OpenRouter ⑥OpenAI</div>
<div class="sum">
  <div class="si"><div class="n c1n">{ok[0]}/16</div><div class="l">① 좌표</div></div>
  <div class="si"><div class="n c2n">{ok[1]}/16</div><div class="l">② Gemini</div></div>
  <div class="si"><div class="n c3n">{ok[2]}/16</div><div class="l">③ Groq</div></div>
  <div class="si"><div class="n c4n">{ok[3]}/16</div><div class="l">④ xAI</div></div>
  <div class="si"><div class="n c5n">{ok[4]}/16</div><div class="l">⑤ OpenRouter</div></div>
  <div class="si"><div class="n c6n">{ok[5]}/16</div><div class="l">⑥ OpenAI</div></div>
</div>
<div class="leg">
  <span style="background:#122012;color:#7ec87e">🟢 일치 (좌표와 동일)</span>
  <span style="background:#302010;color:#f0a060">🟠 불일치 (값이 다름)</span>
  <span style="background:#201010;color:#e87e7e">🔴 실패 (❌에 마우스 올리면 에러 표시)</span>
  <span style="background:#1a1a30;color:#aaa">⚫ 데이터 없음</span>
</div>
<table>
<thead><tr>
  <th>선사/문서</th>
  <th>필드</th>
  <th>① 좌표값</th>
  <th>② Gemini</th>
  <th>③ Groq</th>
  <th>④ xAI</th>
  <th>⑤ OpenRouter</th>
  <th>⑥ OpenAI</th>
</tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></body></html>"""

out = os.path.join(ROOT,"REPORTS","parse_comparison_5method.html")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out,"w",encoding="utf-8") as f:
    f.write(html)

print(f"\n{'='*60}")
print(f"  ① 좌표       : {ok[0]}/16")
print(f"  ② Gemini     : {ok[1]}/16")
print(f"  ③ Groq       : {ok[2]}/16")
print(f"  ④ xAI Grok   : {ok[3]}/16")
print(f"  ⑤ OpenRouter : {ok[4]}/16")
print(f"  ⑥ OpenAI    : {ok[5]}/16")
print(f"{'='*60}")
print(f"  보고서: {out}")
