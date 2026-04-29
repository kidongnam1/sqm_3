@echo off
chcp 65001 >nul
echo === HAPAG PL fix + 회귀 테스트 추가 커밋 + push ===
cd /d D:\program\SQM_inventory\SQM_v865_CLEAN

echo [1] index.lock 삭제...
if exist ".git\index.lock" (
    del /f /q ".git\index.lock"
    echo    삭제 완료
) else (
    echo    lock 없음 (정상)
)

echo [2] 스테이징 초기화 (D 상태 파일 해제)...
git reset HEAD
echo    reset 완료

echo [3] 수정 파일 add...
git add parsers\document_parser_modular\packing_mixin.py
git add parsers\document_parser_modular\do_mixin.py
git add tests\test_parser_regression.py
git add tests\fixtures\HAPAG_PL.pdf
git add REPORTS\RELEASE_v865_20260429_r3.md

echo [4] 상태 확인...
git status --short

echo [5] 커밋...
git commit -m "fix: packing_mixin+do_mixin - HAPAG PL split container / ONE DO carrier detect

packing_mixin.py:
- Handle split PDF word format: 'HAMU' + '272359-6' as two separate words
- CT_RE single-token match fails -> fallback: FOUR_ALPHA prefix + NUM_PART suffix
- Concatenate prefix+suffix then apply hyphen normalization
- Result: HAMU2050957/HAMU2354538/HAMU2410117/HAMU2655932/HAMU2723596 (5 containers)

do_mixin.py:
- ONE carrier detection: added 'ONEYS' in _txt trigger
- ONE_DO.pdf contains BL no 'ONEYSCLG01825300' -> now correctly routes to _parse_do_one_coord()
- MRN '26HDMUK026I' split into 5 PDF words at y=15.6% -> assembled by coord parser
- No Gemini required for any of the 4 carriers

test_parser_regression.py:
- ONE DO test now active (removed