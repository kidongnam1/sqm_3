@echo off
chcp 65001 >nul
echo === Git lock 해제 + 수정 파일 커밋 + push ===
cd /d D:\program\SQM_inventory\SQM_v865_CLEAN

echo [1] index.lock 삭제...
if exist ".git\index.lock" (
    del /f /q ".git\index.lock"
    echo    삭제 완료
) else (
    echo    lock 없음 (정상)
)

echo [2] 수정 파일 add...
git add features\ai\ai_fallback_policy.py
git add parsers\document_parser_modular\ai_fallback.py
git add tests\test_ollama_manager.py
git add tests\test_workflow_stress.py
git add tests\test_ai_fallback_router.py
git add parsers\document_parser_modular\picking_mixin.py
git add parsers\document_parser_modular\do_mixin.py
git add parsers\document_parser_modular\bl_mixin.py
git add parsers\document_parser_modular\packing_mixin.py
git add parsers\document_parser_modular\invoice_mixin.py
git add frontend\js\sqm-inline.js

echo [3] 상태 확인...
git status --short

echo [4] 커밋...
git commit -m "fix: parser bugs - ONE/HAPAG/MAERSK/MSC DO+BL+FA+PL (4 carriers)

do_mixin.py:
- ONE DO: result.voyage_no -> result.voyage (field name fix)
- ONE DO: mrn/msn coord->all_text regex (PyMuPDF char-fragmentation workaround)
- ONE DO: MRN compact normalization '26H D M U K026I' -> '26HDM UK026I'
- HAPAG DO: result.voyage_no -> result.voyage (field name fix)
- HAPAG DO: mrn x-range narrowed 50-67% -> 50-63.5% (exclude '-' separator)
- HAPAG DO: mrn/msn extracted and assigned to DOData
- MAERSK DO: result.voyage_no -> result.voyage (field name fix)
- MSC DO: result.mrn/msn NameError fix (mrn_raw/msn_clean undefined -> init '')
- MSC DO: pol coord (30,58,28,31.5)->(5,25,32,34) CLPAG at x=7.7% y=32.7%
- MSC DO: pod coord (30,58,31,34.5)->(27,50,32,34) KRKAN at x=29.1% y=32.7%

bl_mixin.py:
- CARRIER_RE: HLCU regex extended 6-10 -> 6-15 chars
- HAPAG coord bl_no: x2 97->82% (exclude page number '2/3' at x=84-89%)
- HAPAG coord voyage_no: x2 55->47.5% (exclude 'Place of Delivery' at x=49%)
- HAPAG coord: shipper/consignee region added
- HAPAG coord: gross_weight_p1 region (page 1, European comma-decimal)
- ONE coord: shipper/consignee region added
- ONE coord: gross_weight_p0 region (page 0, dot-decimal)
- MAERSK coord: shipper/consignee region added
- MAERSK coord: gross_weight_p1 region (page 1, American comma-thousands)
- parse_bl: shipper/consignee label prefix stripping added
- parse_bl: gross_weight_coord -> gross_weight_kg extraction
- parse_bl: MAERSK 9-digit bl_no -> MAEU prefix added
- MSC coord vessel: x2 25->17.0 (exclude '-' separator at x=17.7%)
- MSC coord voyage_no: x1 14->18.2 (exclude '-' separator at x=17.7%)
- total_containers regex: \d+ -> [1-9]\d{0,2} (max 3 digits, exclude 4-digit years)

packing_mixin.py:
- Container check digit hyphen: TCLU640435-3 -> TCLU6404353 normalization

invoice_mixin.py:
- v8.6.5: MAERSK 9-digit bl_no -> MAEU prefix via _VESSEL_TO_SCAC vessel lookup

sqm-inline.js:
- v8.6.5: fix parse result table blank bug
  _openParseResultWindow() called BEFORE _onestopRenderPreview()
  so onestop-preview-body exists in DOM when render runs
- also restored from backup (file was truncated at line 6668)

Verified (4 carriers, 4 doc types each):
  ONE DO:     voyage=0012W mrn=26HDM UK026I msn=5019 containers=5
  HAPAG DO:   voyage=2602W mrn=26HLCU9401I msn=6006 pod=KRPUS containers=5
  MAERSK DO:  voyage=614E pod=KRKAN containers=5
  MSC DO:     voyage=FY612A mrn=26MSCU3084I msn=0101 pol=CLPAG pod=KRKAN containers=2
  ONE BL:     bl_no=ONEYSCLG01825300 voyage=2601W gross_wt=102625
  HAPAG BL:   bl_no=HLCUSCL260148627 voyage=2602W gross_wt=102625
  MAERSK BL:  bl_no=MAEU265083673 voyage=607W gross_wt=102625
  MSC BL:     bl_no=MEDUW9018104 vessel=MANZANILLO EXPRESS voyage=2551W gross_wt=41050
  MAERSK FA:  bl_no=MAEU265083673 invoice=17703 gross_wt=102625 amount=1956591.24
  MSC FA:     bl_no=MEDUW9018104 invoice=17586 gross_wt=41050 amount=826005.17
  MAERSK PL:  lots=20 containers=5 gross_wt=102625 maxibag=200
  MSC PL:     lots=8 containers=2 gross_wt=41050 maxibag=80"

echo [5] Push to sqm_3...
git push origin main

echo === 완료 ===
pause
