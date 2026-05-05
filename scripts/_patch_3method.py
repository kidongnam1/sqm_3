# -*- coding: utf-8 -*-
"""run_comparison_windows.py → 3방식 전용 버전으로 패치"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src  = os.path.join(ROOT, "scripts", "run_comparison_windows.py")

with open(src, "r", encoding="utf-8") as f:
    c = f.read()

# ── 1. 제목/주석 ──────────────────────────────────────────────
c = c.replace("4선사 x 4문서 x 6방식 파싱 비교표",
               "4선사 x 4문서 x 3방식 파싱 비교표")
c = c.replace("SQM v8.6.5 — 6방식 파싱 비교",
               "SQM v8.6.5 — 3방식 파싱 비교 (좌표/Gemini/OpenRouter)")

# ── 2. 실행 루프: 6방식 → 3방식 ──────────────────────────────
old_loop = (
    "    r1,t1,e1 = run_coord(doc_type, pdf_path);      print(f\"좌표={'OK' if r1 else 'NG'} \",end=\"\",flush=True)\n"
    "    r2,t2,e2 = run_gemini(doc_type, pdf_path);     print(f\"Gem={'OK' if r2 else 'NG'} \", end=\"\",flush=True)\n"
    "    r3,t3,e3 = run_groq(doc_type, pdf_path);       print(f\"Groq={'OK' if r3 else 'NG'} \",end=\"\",flush=True)\n"
    "    r4,t4,e4 = run_xai(doc_type, pdf_path);        print(f\"xAI={'OK' if r4 else 'NG'} \", end=\"\",flush=True)\n"
    "    r5,t5,e5 = run_openrouter(doc_type, pdf_path); print(f\"OR={'OK' if r5 else 'NG'} \",  end=\"\",flush=True)\n"
    "    r6,t6,e6 = run_openai(doc_type, pdf_path);     print(f\"OAI={'OK' if r6 else 'NG'}\")\n"
    "    results.append((carrier,doc_type,fname, r1,t1,e1, r2,t2,e2, r3,t3,e3, r4,t4,e4, r5,t5,e5, r6,t6,e6))"
)
new_loop = (
    "    r1,t1,e1 = run_coord(doc_type, pdf_path);      print(f\"좌표={'OK' if r1 else 'NG'} \",end=\"\",flush=True)\n"
    "    r2,t2,e2 = run_gemini(doc_type, pdf_path);     print(f\"Gem={'OK' if r2 else 'NG'} \", end=\"\",flush=True)\n"
    "    r3,t3,e3 = run_openrouter(doc_type, pdf_path); print(f\"OR={'OK' if r3 else 'NG'}\")\n"
    "    results.append((carrier,doc_type,fname, r1,t1,e1, r2,t2,e2, r3,t3,e3))"
)
c = c.replace(old_loop, new_loop)

# ── 3. SKIP 행 (파일없음) ──────────────────────────────────────
c = c.replace(
    'results.append((carrier,doc_type,fname)+(None,0,"파일없음")*6)',
    'results.append((carrier,doc_type,fname)+(None,0,"파일없음")*3)'
)

# ── 4. ok[] 계산 ───────────────────────────────────────────────
c = c.replace(
    "ok = [sum(1 for r in results if r[3+i*3] is not None) for i in range(6)]",
    "ok = [sum(1 for r in results if r[3+i*3] is not None) for i in range(3)]"
)

# ── 5. HTML rows 루프: 6방식 → 3방식 ──────────────────────────
old_unpack = (
    "    r1,t1,e1 = row[3],row[4],row[5]\n"
    "    r2,t2,e2 = row[6],row[7],row[8]\n"
    "    r3,t3,e3 = row[9],row[10],row[11]\n"
    "    r4,t4,e4 = row[12],row[13],row[14]\n"
    "    r5,t5,e5 = row[15],row[16],row[17]\n"
    "    r6,t6,e6 = row[18],row[19],row[20]"
)
new_unpack = (
    "    r1,t1,e1 = row[3],row[4],row[5]\n"
    "    r2,t2,e2 = row[6],row[7],row[8]\n"
    "    r3,t3,e3 = row[9],row[10],row[11]"
)
c = c.replace(old_unpack, new_unpack)

# ── 6. 행 내부 method header 셀 (6개 → 3개) ──────────────────
old_mhdr = (
    "  <td class=\"ml c1\">① 좌표</td>\n"
    "  <td class=\"ml c2\">② Gemini</td>\n"
    "  <td class=\"ml c3\">③ Groq<br><small>llama-3.3-70b</small></td>\n"
    "  <td class=\"ml c4\">④ xAI<br><small>grok-beta</small></td>\n"
    "  <td class=\"ml c5\">⑤ OpenRouter<br><small>mistral-7b</small></td>\n"
    "  <td class=\"ml c6\">⑥ OpenAI<br><small>gpt-4o-mini</small></td>\n"
)
new_mhdr = (
    "  <td class=\"ml c1\">① 좌표</td>\n"
    "  <td class=\"ml c2\">② Gemini</td>\n"
    "  <td class=\"ml c3\">③ OpenRouter<br><small>gpt-5.5/qwen3</small></td>\n"
)
c = c.replace(old_mhdr, new_mhdr)

# ── 7. strow: 6셀 → 3셀 ───────────────────────────────────────
c = c.replace(
    "  {sc(r1,e1,t1)}{sc(r2,e2,t2)}{sc(r3,e3,t3)}{sc(r4,e4,t4)}{sc(r5,e5,t5)}{sc(r6,e6,t6)}",
    "  {sc(r1,e1,t1)}{sc(r2,e2,t2)}{sc(r3,e3,t3)}"
)

# ── 8. field 행 값 추출: 6개 → 3개 ───────────────────────────
old_vrow = (
    "        v1,v2,v3,v4,v5,v6 = (extract(r,field) for r in (r1,r2,r3,r4,r5,r6))\n"
    "        rows.append(f\"\"\"\n"
    "<tr>\n"
    "  <td class=\"fn\">{field}</td>\n"
    "  <td class=\"v1\">{e(v1) if v1 else \"-\"}</td>\n"
    "  {vc(v2,v1)}{vc(v3,v1)}{vc(v4,v1)}{vc(v5,v1)}{vc(v6,v1)}\n"
    "</tr>\"\"\")"
)
new_vrow = (
    "        v1,v2,v3 = (extract(r,field) for r in (r1,r2,r3))\n"
    "        rows.append(f\"\"\"\n"
    "<tr>\n"
    "  <td class=\"fn\">{field}</td>\n"
    "  <td class=\"v1\">{e(v1) if v1 else \"-\"}</td>\n"
    "  {vc(v2,v1)}{vc(v3,v1)}\n"
    "</tr>\"\"\")"
)
c = c.replace(old_vrow, new_vrow)

# ── 9. spacer colspan 8 → 5 ───────────────────────────────────
c = c.replace(
    "'<tr class=\"sp\"><td colspan=\"8\"></td></tr>'",
    "'<tr class=\"sp\"><td colspan=\"5\"></td></tr>'"
)

# ── 10. HTML 상단 요약 (6개 → 3개) ───────────────────────────
old_sum = (
    '<div class="sum">\n'
    '  <div class="si"><div class="n c1n">{ok[0]}/16</div><div class="l">① 좌표</div></div>\n'
    '  <div class="si"><div class="n c2n">{ok[1]}/16</div><div class="l">② Gemini</div></div>\n'
    '  <div class="si"><div class="n c3n">{ok[2]}/16</div><div class="l">③ Groq</div></div>\n'
    '  <div class="si"><div class="n c4n">{ok[3]}/16</div><div class="l">④ xAI</div></div>\n'
    '  <div class="si"><div class="n c5n">{ok[4]}/16</div><div class="l">⑤ OpenRouter</div></div>\n'
    '  <div class="si"><div class="n c6n">{ok[5]}/16</div><div class="l">⑥ OpenAI</div></div>\n'
    '</div>'
)
new_sum = (
    '<div class="sum">\n'
    '  <div class="si"><div class="n c1n">{ok[0]}/16</div><div class="l">① 좌표</div></div>\n'
    '  <div class="si"><div class="n c2n">{ok[1]}/16</div><div class="l">② Gemini</div></div>\n'
    '  <div class="si"><div class="n c3n">{ok[2]}/16</div><div class="l">③ OpenRouter</div></div>\n'
    '</div>'
)
c = c.replace(old_sum, new_sum)

# ── 11. HTML thead (6컬럼 → 3컬럼) ───────────────────────────
old_thead = (
    "<thead><tr>\n"
    "  <th>선사/문서</th>\n"
    "  <th>필드</th>\n"
    "  <th>① 좌표값</th>\n"
    "  <th>② Gemini</th>\n"
    "  <th>③ Groq</th>\n"
    "  <th>④ xAI</th>\n"
    "  <th>⑤ OpenRouter</th>\n"
    "  <th>⑥ OpenAI</th>\n"
    "</tr></thead>"
)
new_thead = (
    "<thead><tr>\n"
    "  <th>선사/문서</th>\n"
    "  <th>필드</th>\n"
    "  <th>① 좌표값</th>\n"
    "  <th>② Gemini</th>\n"
    "  <th>③ OpenRouter</th>\n"
    "</tr></thead>"
)
c = c.replace(old_thead, new_thead)

# ── 12. meta 텍스트 ───────────────────────────────────────────
c = c.replace(
    "4선사×4문서=16건 | ①좌표 ②Gemini ③Groq ④xAI ⑤OpenRouter ⑥OpenAI",
    "4선사×4문서=16건 | ① 좌표  ② Gemini  ③ OpenRouter"
)

# ── 13. 출력 파일명 ───────────────────────────────────────────
c = c.replace(
    '"parse_comparison_5method.html"',
    '"parse_comparison_3method_v2.html"'
)

# ── 14. 최종 summary 출력 (6줄 → 3줄) ───────────────────────
old_pr = (
    '  ① 좌표       : {ok[0]}/16"))\n'
    'print(f"  ② Gemini     : {ok[1]}/16"))\n'
    'print(f"  ③ Groq       : {ok[2]}/16"))\n'
    'print(f"  ④ xAI Grok   : {ok[3]}/16"))\n'
    'print(f"  ⑤ OpenRouter : {ok[4]}/16"))\n'
    'print(f"  ⑥ OpenAI    : {ok[5]}/16"))'
)
# 실제 print 구문 찾아서 교체
import re
c = re.sub(
    r'print\(f"  ① 좌표.*?print\(f"  보고서: \{out\}"\)',
    (
        'print(f"  ① 좌표       : {ok[0]}/16")\n'
        'print(f"  ② Gemini     : {ok[1]}/16")\n'
        'print(f"  ③ OpenRouter : {ok[2]}/16")\n'
        "print(f\"{'='*60}\")\n"
        'print(f"  보고서: {out}")'
    ),
    c,
    flags=re.DOTALL
)

with open(src, "w", encoding="utf-8", newline="\n") as f:
    f.write(c)

import py_compile
py_compile.compile(src, doraise=True)
print("run_comparison_windows.py 3방식 패치 완료 — 문법 OK")
