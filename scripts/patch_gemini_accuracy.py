"""
patch_gemini_accuracy.py — 92.6% → 98%+ 정확도 개선

Fix 1: DO prompt — bl_no 선사 접두사 누락 (HAPAG/MAERSK DO 4건)
Fix 2: DO prompt — gross_weight_kg 단위 혼동 (MAERSK DO 1건)
Fix 3: DO prompt — MRN 공백 보존 (ONE DO 1건)
Fix 4: BL prompt — bl_no 접두사 예시 수정 + port_of_discharge 최종항 명시
Fix 5: Invoice prompt — bl_no 접두사 예시 수정
Fix 6: _apply_do_json_to_result — bl_no_full 우선 + 단위 자동 보정 후처리
Fix 7: parse_bl — carrier_id _tmpl 에서 전파 + bl_no prefix 추론

Usage: python scripts/patch_gemini_accuracy.py [--dry-run]
"""
import sys, shutil, re
from pathlib import Path

DRY_RUN = '--dry-run' in sys.argv
ROOT    = Path(__file__).resolve().parent.parent
TARGET  = ROOT / 'features' / 'ai' / 'gemini_parser.py'

src = open(TARGET, encoding='utf-8').read()
orig_len = len(src)
patches = []

def apply(label, old, new):
    global src
    if old in src:
        src = src.replace(old, new, 1)
        patches.append(label)
    else:
        print(f'[WARN] {label}: anchor not found')

# ══════════════════════════════════════════════════════════════════
# Fix 1+2+3: DO 프롬프트 — bl_no 접두사 + 단위 + MRN 공백
# ══════════════════════════════════════════════════════════════════

OLD_DO_BL = (
    '    "bl_no": "B/L 번호 (MSC: MEDUFP963988 전체, Maersk: 숫자만 258468669)",\n'
    '    "bl_no_full": "B/L 번호 전체 (예: MAEU258468669 또는 MEDUFP963988)",'
)
NEW_DO_BL = (
    '    "bl_no": "B/L 번호 — 선사 접두사 포함 전체 번호 (예: MAEU265083673, HLCUSCL260148627, MEDUW9018104, ONEYSCLG01825300)",\n'
    '    "bl_no_full": "bl_no와 동일한 전체 번호 (접두사 포함)",'
)
apply('Fix1: DO prompt bl_no 접두사 명시', OLD_DO_BL, NEW_DO_BL)

OLD_DO_WEIGHT = '    "total_weight_kg": 123150,\n    "gross_weight_kg": 123150,'
NEW_DO_WEIGHT = (
    '    "total_weight_kg": 123150,\n'
    '    "gross_weight_kg": 123150,'
    '  // ⚠️ 반드시 KG 단위 (MT 아님). 문서에 MT로 표기된 경우 ×1000 변환 (예: 102.625MT → 102625kg)'
)
apply('Fix2: DO prompt gross_weight_kg KG 단위 강제', OLD_DO_WEIGHT, NEW_DO_WEIGHT)

OLD_DO_MRN_HINT = (
    '    "mrn": "MRN 번호 (MSC 전용, 예: 26MSCU3082I)",\n'
    '    "msn": "MSN 번호 (MSC 전용, 예: 0001)",'
)
NEW_DO_MRN_HINT = (
    '    "mrn": "MRN 번호 — 공백 포함 정확히 추출 (예: 26HDM UK026I, 26MSCU3082I, 26HLCU9401I)",\n'
    '    "msn": "MSN 번호 (예: 0001, 5019, 6006)",'
)
apply('Fix3: DO prompt MRN 공백 보존 명시', OLD_DO_MRN_HINT, NEW_DO_MRN_HINT)

# ══════════════════════════════════════════════════════════════════
# Fix 4: BL 기본 프롬프트 — 접두사 예시 + 최종 양하항 명시
# ══════════════════════════════════════════════════════════════════

OLD_BL_BL_NO = '    "bl_no": "B/L 번호 (예: 258468669)",'
NEW_BL_BL_NO = '    "bl_no": "B/L 번호 — 선사 접두사 포함 전체 번호 (예: MAEU265083673, HLCUSCL260148627, MEDUW9018104)",'
apply('Fix4a: BL prompt bl_no 접두사 예시', OLD_BL_BL_NO, NEW_BL_BL_NO)

OLD_BL_DISC = '    "port_of_discharge": "양하항 (예: GWANGYANG, SOUTH KOREA)",'
NEW_BL_DISC = '    "port_of_discharge": "최종 양하항 Final Port of Discharge (예: GWANGYANG, SOUTH KOREA). 환적항(Transshipment Port)은 제외",'
apply('Fix4b: BL prompt port_of_discharge 최종항 명시', OLD_BL_DISC, NEW_BL_DISC)

# ══════════════════════════════════════════════════════════════════
# Fix 5: Invoice 프롬프트 — bl_no 접두사 예시
# ══════════════════════════════════════════════════════════════════

OLD_INV_BL = '    "bl_no": "B/L 번호 (예: 258468669)",'
NEW_INV_BL = '    "bl_no": "B/L 번호 — 선사 접두사 포함 전체 번호 (예: MAEU265083673, HLCUSCL260148627, MEDUW9018104)",'
apply('Fix5: Invoice prompt bl_no 접두사 예시', OLD_INV_BL, NEW_INV_BL)

# ══════════════════════════════════════════════════════════════════
# Fix 6: _apply_do_json_to_result — bl_no_full 우선 + 단위 자동 보정
# ══════════════════════════════════════════════════════════════════

# 6a: bl_no 우선순위: bl_no_full이 있으면 그것을 사용
OLD_DO_APPLY_BL = (
    '        result.do_no = str(data.get(\'do_no\', \'\'))\n'
    '        result.bl_no = str(data.get(\'bl_no\', \'\'))\n'
    '        result.bl_no_full = str(data.get(\'bl_no_full\', \'\'))'
)
NEW_DO_APPLY_BL = (
    '        result.do_no = str(data.get(\'do_no\', \'\'))\n'
    '        _bl_raw  = str(data.get(\'bl_no\', \'\') or \'\')\n'
    '        _bl_full = str(data.get(\'bl_no_full\', \'\') or \'\')\n'
    '        # bl_no_full이 있고 더 길면 우선 사용 (선사 접두사 포함 버전)\n'
    '        result.bl_no = _bl_full if len(_bl_full) > len(_bl_raw) else _bl_raw\n'
    '        result.bl_no_full = _bl_full or _bl_raw'
)
apply('Fix6a: _apply_do_json bl_no_full 우선', OLD_DO_APPLY_BL, NEW_DO_APPLY_BL)

# 6b: gross_weight_kg 단위 자동 보정 (< 1000이면 MT로 오인한 것, ×1000)
OLD_DO_APPLY_WEIGHT = (
    '        result.total_weight_kg = float(data.get(\'total_weight_kg\', 0))\n'
    '        result.gross_weight_kg = result.total_weight_kg  # 비교 스크립트 호환용 alias'
)
NEW_DO_APPLY_WEIGHT = (
    '        _raw_w = float(data.get(\'total_weight_kg\', 0) or 0)\n'
    '        _raw_gw = float(data.get(\'gross_weight_kg\', 0) or _raw_w or 0)\n'
    '        # MT→KG 자동 보정: 중량이 1000 미만이면 MT로 오인한 것 (예: 102.625 → 102625)\n'
    '        _cnt = len(data.get(\'containers\', []) or [])\n'
    '        if 0 < _raw_gw < 1000 and _cnt > 0:\n'
    '            logger.info(f"[DO] gross_weight_kg={_raw_gw} < 1000 → MT→KG 보정 ({_raw_gw*1000})")\n'
    '            _raw_gw = _raw_gw * 1000\n'
    '        if 0 < _raw_w < 1000 and _cnt > 0:\n'
    '            _raw_w = _raw_w * 1000\n'
    '        result.total_weight_kg = _raw_w or _raw_gw\n'
    '        result.gross_weight_kg = _raw_gw or _raw_w  # 비교 스크립트 호환용 alias'
)
apply('Fix6b: _apply_do_json gross_weight MT→KG 자동 보정', OLD_DO_APPLY_WEIGHT, NEW_DO_APPLY_WEIGHT)

# ══════════════════════════════════════════════════════════════════
# Fix 7: parse_bl — carrier_id _tmpl에서 전파 + bl_no prefix 추론
# ══════════════════════════════════════════════════════════════════

# 7a: _tmpl 발견 시 carrier_id 미리 저장 (for later fallback)
OLD_BL_TMPL = (
    '                    _bl_no_regex = extract_bl_no_by_template(_pages_text, _tmpl)\n'
    '                        logger.info(\n'
    '                            f"[GeminiParser] 선사={_tmpl.carrier_name}, "\n'
    '                            f"BL_regex={_bl_no_regex!r}"\n'
    '                        )'
)
# The actual indentation — let me use a different anchor
OLD_BL_TMPL2 = (
    '                    _tmpl = detect_carrier(_pages_text[0])\n'
    '                    if _tmpl:\n'
    '                        _bl_no_regex = extract_bl_no_by_template(_pages_text, _tmpl)\n'
    '                        logger.info(\n'
    '                            f"[GeminiParser] 선사={_tmpl.carrier_name}, "\n'
    '                            f"BL_regex={_bl_no_regex!r}"\n'
    '                        )'
)
NEW_BL_TMPL2 = (
    '                    _tmpl = detect_carrier(_pages_text[0])\n'
    '                    if _tmpl:\n'
    '                        _bl_no_regex = extract_bl_no_by_template(_pages_text, _tmpl)\n'
    '                        logger.info(\n'
    '                            f"[GeminiParser] 선사={_tmpl.carrier_name}, "\n'
    '                            f"BL_regex={_bl_no_regex!r}"\n'
    '                        )\n'
    '                        result.carrier_id = getattr(_tmpl, \'carrier_id\', \'\') or getattr(_tmpl, \'carrier_name\', \'\')'
)
apply('Fix7a: parse_bl carrier_id from _tmpl', OLD_BL_TMPL2, NEW_BL_TMPL2)

# 7b: After Gemini result parsed, infer carrier_id from bl_no prefix if still empty
OLD_BL_CARRIER = (
    '                        result.total_weight_kg = float(data.get(\'total_weight_kg\', 0))\n'
    '                        result.gross_weight_kg = result.total_weight_kg  # 비교 스크립트 호환용 alias'
)
NEW_BL_CARRIER = (
    '                        result.total_weight_kg = float(data.get(\'total_weight_kg\', 0))\n'
    '                        result.gross_weight_kg = result.total_weight_kg  # 비교 스크립트 호환용 alias\n'
    '                        # carrier_id: Gemini 결과 우선, 없으면 bl_no prefix로 추론\n'
    '                        _gm_carrier = str(data.get(\'carrier_id\', \'\') or \'\')\n'
    '                        if _gm_carrier and _gm_carrier.upper() != \'UNKNOWN\':\n'
    '                            result.carrier_id = _gm_carrier\n'
    '                        if not result.carrier_id:\n'
    '                            _bn = result.bl_no.upper()\n'
    '                            if _bn.startswith(\'MAEU\'):   result.carrier_id = \'MAERSK\'\n'
    '                            elif _bn.startswith(\'HLC\'):  result.carrier_id = \'HAPAG\'\n'
    '                            elif _bn.startswith(\'MEDU\'): result.carrier_id = \'MSC\'\n'
    '                            elif _bn.startswith(\'ONE\'):  result.carrier_id = \'ONE\''
)
apply('Fix7b: parse_bl carrier_id from bl_no prefix fallback', OLD_BL_CARRIER, NEW_BL_CARRIER)

# 7c: BL No 정규식 결과 우선 적용 (기존 로직 이후에 덮어쓰기)
# Find the _bl_no_regex override logic
OLD_BL_REGEX_USE = (
    '            # ── v6.4.0 ④: BL No 정규식 결과 우선 ──\n'
)
if OLD_BL_REGEX_USE in src:
    pass  # Already exists, skip
else:
    # Find where regex result is applied
    OLD_BL_SUCCESS = (
        '            result.success = bool(result.bl_no)\n'
        '            result.carrier_name = getattr(_tmpl, \'carrier_name\', \'\') if _tmpl else \'\''
    )
    NEW_BL_SUCCESS = (
        '            # bl_no: 정규식 결과가 있고 더 정확하면 우선 사용\n'
        '            if _bl_no_regex and len(_bl_no_regex) >= len(result.bl_no):\n'
        '                logger.info(f"[GeminiParser] BL No 정규식 우선: {_bl_no_regex!r} (Gemini: {result.bl_no!r})")\n'
        '                result.bl_no = _bl_no_regex\n'
        '            result.success = bool(result.bl_no)\n'
        '            result.carrier_name = getattr(_tmpl, \'carrier_name\', \'\') if _tmpl else \'\''
    )
    apply('Fix7c: parse_bl regex bl_no 우선 적용', OLD_BL_SUCCESS, NEW_BL_SUCCESS)

# ══════════════════════════════════════════════════════════════════
# Write
# ══════════════════════════════════════════════════════════════════
print(f'\nPatches applied ({len(patches)}):')
for p in patches: print(f'  [+] {p}')
print(f'\nSize: {orig_len} -> {len(src)} chars ({len(src)-orig_len:+d})')

if not DRY_RUN:
    shutil.copy2(TARGET, TARGET.with_suffix('.py.bak'))
    print(f'[BAK] gemini_parser.py.bak')
    tmp = TARGET.with_suffix('.py.tmp')
    open(tmp, 'w', encoding='utf-8', newline='\n').write(src)
    tmp.replace(TARGET)
    print(f'[OK] {TARGET.name}')
    print('\nNext: python -m pytest tests/ -q')
else:
    print('[DRY-RUN] no files written')
