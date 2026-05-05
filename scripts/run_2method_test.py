# -*- coding: utf-8 -*-
"""
SQM v8.6.5 — 2방식 파서 정확도 비교
① 좌표 파싱 (기준값) vs ② Gemini
"""
import os, sys, time, configparser, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURE = os.path.join(ROOT, "tests", "fixtures")

cfg = configparser.ConfigParser()
cfg.read(os.path.join(ROOT, "settings.ini"), encoding="utf-8")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY","") or cfg.get("Gemini","api_key",fallback="")

DOCS = [
    ("ONE","DO","ONE_DO.pdf"), ("ONE","BL","ONE_BL.pdf"),
    ("ONE","FA","ONE_FA.pdf"), ("ONE","PL","ONE_PL.pdf"),
    ("HAPAG","DO","HAPAG_DO.pdf"), ("HAPAG","BL","HAPAG_BL.pdf"),
    ("HAPAG","FA","HAPAG_FA.pdf"), ("HAPAG","PL","HAPAG_PL.pdf"),
    ("MAERSK","DO","MAERSK_DO.pdf"), ("MAERSK","BL","MAERSK_BL.pdf"),
    ("MAERSK","FA","MAERSK_FA.pdf"), ("MAERSK","PL","MAERSK_PL.pdf"),
    ("MSC","DO","MSC_DO.pdf"), ("MSC","BL","MSC_BL.pdf"),
    ("MSC","FA","MSC_FA.pdf"), ("MSC","PL","MSC_PL.pdf"),
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

def get_val(result, field):
    if result is None: return ""
    if field == "container_count":
        return str(len(getattr(result,"containers",[]) or []))
    if field == "lot_count":
        lots = getattr(result,"lots",None) or getattr(result,"lot_numbers",[]) or []
        return str(len(lots))
    v = getattr(result, field, "")
    if hasattr(v,"isoformat"): return v.isoformat()
    return str(v).strip() if v not in (None,"") else ""

def run_one(label, fn, doc_type, pdf_path):
    t0 = time.time()
    try:
        r = fn(doc_type, pdf_path)
        return r, time.time()-t0, None
    except Exception as e:
        return None, time.time()-t0, str(e)[:80]

print(f"Gemini KEY: {'있음' if GEMINI_KEY else '없음'}")
print()

# --- 파서 imports ---
from parsers.document_parser_modular import DocumentParser
dispatch = {"DO":"parse_do","BL":"parse_bl","FA":"parse_invoice","PL":"parse_packing_list"}

if GEMINI_KEY:
    from features.ai.gemini_parser import GeminiDocumentParser
    gem_parser = GeminiDocumentParser(api_key=GEMINI_KEY)

rows = []
for carrier, doc_type, fname in DOCS:
    pdf = os.path.join(FIXTURE, fname)
    if not os.path.exists(pdf):
        print(f"SKIP (파일없음): {fname}")
        rows.append((carrier, doc_type, None, 0, None, 0, "파일없음", "N/A", FIELDS[doc_type]))
        continue

    # ① 좌표 파싱
    coord_parser = DocumentParser()
    coord_r, coord_t, coord_e = run_one(
        "좌표",
        lambda dt, p: getattr(DocumentParser(), dispatch[dt])(p),
        doc_type, pdf
    )

    # ② Gemini
    if GEMINI_KEY:
        gem_r, gem_t, gem_e = run_one(
            "Gemini",
            lambda dt, p: getattr(gem_parser, dispatch[dt])(p),
            doc_type, pdf
        )
    else:
        gem_r, gem_t, gem_e = None, 0, "KEY없음"

    # 정확도 계산
    fields = FIELDS[doc_type]
    coord_ok = sum(1 for f in fields if get_val(coord_r, f) != "") if coord_r else 0
    match = 0
    if coord_r and gem_r:
        match = sum(1 for f in fields
                    if get_val(coord_r, f).lower() == get_val(gem_r, f).lower())
    if gem_r:
        gem_acc = f"{match/len(fields)*100:.0f}%"
    elif gem_e == "KEY없음":
        gem_acc = "N/A"
    else:
        gem_acc = "FAIL"

    print(f"{carrier:6s} {doc_type} | 좌표={'OK' if coord_r else 'NG'} ({coord_ok}/{len(fields)}) | "
          f"Gemini={'OK '+gem_acc if gem_r else gem_e[:20]} | "
          f"coord_e={coord_e or '-'}")
    rows.append((carrier, doc_type, coord_r, coord_t, gem_r, gem_t, gem_e, gem_acc, fields))

# --- 결과 테이블 출력 ---
print()
print("=" * 70)
print("| 선사   | 문서 | 필드수 | 좌표(기준)     | Gemini 정확도(%)")
print("|--------|------|--------|----------------|------------------")

total_coord_ok = 0
total_coord_total = 0
gem_accs = []
coord_ok_count = 0
coord_total_count = 0

for row in rows:
    carrier, doc_type, coord_r, coord_t, gem_r, gem_t, gem_e, gem_acc, fields = row
    n = len(fields)
    coord_filled = sum(1 for f in fields if get_val(coord_r, f) != "") if coord_r else 0
    coord_str = f"OK {coord_filled}/{n}" if coord_r else f"NG 0/{n}"
    gem_str = gem_acc if gem_r else (gem_e[:10] if gem_e else "N/A")

    total_coord_ok += coord_filled
    total_coord_total += n
    coord_ok_count += (1 if coord_r else 0)
    coord_total_count += 1

    if gem_r and gem_acc not in ("N/A", "FAIL"):
        try:
            gem_accs.append(float(gem_acc.strip('%')))
        except:
            pass

    print(f"| {carrier:<6s} | {doc_type:<4s} | {n:<6d} | {coord_str:<14s} | {gem_str}")

# 합계
avg_gem = f"{sum(gem_accs)/len(gem_accs):.0f}%" if gem_accs else "N/A"
coord_pct = f"{total_coord_ok/total_coord_total*100:.0f}%" if total_coord_total else "N/A"
print("|--------|------|--------|----------------|------------------")
print(f"| 합계   |      | {total_coord_total:<6d} | {coord_pct:<14s} | {avg_gem}")
print("=" * 70)
print()
print("[완료] run_2method_test.py 종료")
