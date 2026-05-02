# Phase 1-D: 파서 무결성 감사 결과
날짜: 2026-04-30

---

## 체크1: bl_mixin ONE 수정
파일: `parsers/document_parser_modular/bl_mixin.py`

**CARRIER_RE ONEY 패턴:** [PASS]
- `CARRIER_RE` 컴파일 정규식에 `ONEY[A-Z0-9]{8,15}` 및 `ONEU[A-Z0-9]{6,10}` 두 패턴 모두 포함 (line 61)

**BL_FORMAT_MAP ONE→ONEY 12자리:** [PASS]
- `BL_FORMAT_MAP['ONE'] = [('ONEY', 12)]` (line 51)
- 주석: `# ONEYSCLG01825300 형식 (ONEY+8~12자리)` — 실제 접두사 'ONEY', 숫자길이 12 지정

**_detect_carrier_from_words ONE 자동감지:** [PASS]
- `"ONE-LINE.COM"` 또는 `"OCEAN NETWORK EXPRESS"` 키워드 감지 → "ONE" 반환 (line 405)
- `re.search(r"\bONEY[A-Z0-9]{6,15}\b", _ft)` 패턴으로 ONEY 접두사 BL 번호 감지 → "ONE" 반환 (line 408)
- 두 경로 모두 활성화 상태

---

## 체크2: ai_fallback mrn/msn 힌트
파일: `parsers/document_parser_modular/ai_fallback.py`

`_CARRIER_HINTS` 딕셔너리의 DO 섹션 분석 (line 36~85):

**MAERSK:** [PASS]
- DO 힌트: "Also extract MRN (수입신고번호, Korean customs reference, e.g. '25MAEU K2161') and MSN (적하목록번호, manifest serial, numeric 3-5 digits) if present." (line 46~48)

**MSC:** [PASS]
- DO 힌트: "Also extract MRN (e.g. '25MSCU K1234' or '26MSCU K5678') and MSN (numeric 3-5 digits) from the MRN-MSN row if present." (line 55~58)

**HAPAG:** [PASS]
- DO 힌트: "Also extract MRN (Korean customs ref, e.g. '26HLCU K9401I') and MSN (numeric 3-5 digits) from the MRN row near the top." (line 65~68)

**ONE:** [PASS]
- DO 힌트: "Also extract MRN (e.g. '26HDM UK026I', split tokens must be joined) and MSN (numeric 3-5 digits after '-' separator) from MRN-MSN row." (line 79~82)

추가 확인: `build_ai_hint()` 함수에서 `doc_type == "DO"` 조건 시 공통 mrn/msn 추출 지시도 삽입됨 (line 114~119).

---

## 체크3: parse_alarm.py 완결성
파일: `utils/parse_alarm.py`

**ParseAlarm dataclass (level/field/message 필드):** [PASS]
- `@dataclass class ParseAlarm` 존재, `level`, `field`, `message`, `doc_type`, `carrier` 필드 모두 확인 (line 33~39)

**AlarmReport dataclass (has_critical/has_warning/criticals/warnings/to_dict):** [PASS]
- `@dataclass class AlarmReport` 존재 (line 43)
- `has_critical` property (line 47), `has_warning` property (line 51), `criticals` property (line 55), `warnings` property (line 59), `to_dict()` 메서드 (line 73) 모두 확인

**check_bl 함수:** [PASS]
- `def check_bl(result, carrier_id="")` 존재 (line 102)

**check_do 함수:** [PASS]
- `def check_do(result, carrier_id="")` 존재 (line 145)

**check_invoice 함수:** [PASS]
- `def check_invoice(result, carrier_id="")` 존재 (line 202)

**check_packing 함수:** [PASS]
- `def check_packing(result, carrier_id="")` 존재 (line 227)

**check_do에서 mrn/msn CRITICAL 체크:** [PASS]
- mrn 없으면 CRITICAL: `_add(r, CRITICAL, "mrn", "MRN(수입신고번호) 추출 실패 — 통관 처리 불가", dt, ca)` (line 174)
- msn 없으면 CRITICAL: `_add(r, CRITICAL, "msn", "MSN(적하목록번호) 추출 실패 — 통관 처리 불가", dt, ca)` (line 178)

**check_packing에서 mxbg_pallet==0 CRITICAL 체크:** [PASS]
- `missing_mxbg` 리스트로 `mxbg_pallet`이 0(falsy)인 LOT 수집 후 CRITICAL 추가 (line 241~247)
- `_add(r, CRITICAL, "mxbg_pallet", f"MXBG(톤백수) 없는 LOT {len(missing_mxbg)}개: ... — 톤백 생성 불가", dt, ca)`

---

## 체크4: inbound.py 연결
파일: `backend/api/inbound.py`

**"from utils.parse_alarm import" 구문:** [PASS]
- `from utils.parse_alarm import check_bl, check_do, check_invoice, check_packing` (line 659)

**check_bl 호출:** [PASS]
- `"bl": check_bl(parsed["bl"], tpl_carrier_id)` (line 661)

**check_do 호출:** [PASS]
- `"do": check_do(parsed["do"], tpl_carrier_id)` (line 662)

**check_invoice 호출:** [PASS]
- `"invoice": check_invoice(parsed["invoice"], tpl_carrier_id)` (line 663)

**check_packing 호출:** [PASS]
- `"pl": check_packing(parsed["packing_list"], tpl_carrier_id)` (line 664)

**parse_alarms 키 응답 JSON 포함:** [PASS]
- `"parse_alarms": { k: v.to_dict() for k, v in _alarm_reports.items() }` (line 885~887)
- `"parse_alarms_summary": { ... }` 도 함께 포함 (line 888~895)

**CRITICAL 알람 → warn_messages 추가:** [PASS]
- CRITICAL 항목: `_warn_messages.append(f"[{_doc_key.upper()} CRITICAL] {_a.field}: {_a.message}")` (line 669)
- WARNING 항목도 동일 패턴으로 추가 (line 671)

---

## 체크5: 4선사 × 4서류 파싱 매트릭스

### 분석 기준
- **좌표(COORD)**: 해당 선사 전용 좌표 테이블/함수 존재
- **AI(GEMINI/MULTI)**: ai_fallback.py의 `_CARRIER_HINTS` 또는 공통 AI fallback 경로 커버
- ✅ = 좌표 파싱 + AI fallback 모두 커버
- 🟡 = AI fallback만 커버 (좌표 없음)
- ❌ = 커버 없음

### BL (bl_mixin.py)
- MAERSK: `CARRIER_COORD_TABLE["MAERSK"]` 7개 필드 좌표 + `BL_FORMAT_MAP['MAERSK']` + AI hint
- MSC: `CARRIER_COORD_TABLE["MSC"]` 6개 필드 좌표 + `BL_FORMAT_MAP['MSC']` + AI hint
- HAPAG: `CARRIER_COORD_TABLE["HAPAG"]` 7개 필드 좌표 + `BL_FORMAT_MAP['HAPAG']` + AI hint
- ONE: `CARRIER_COORD_TABLE["ONE"]` 8개 필드 좌표 + `BL_FORMAT_MAP['ONE']` + AI hint

### DO (do_mixin.py)
- MAERSK: `_parse_do_maersk_coord()` 전용 함수, mrn/msn 직접 좌표 추출 + AI hint
- MSC: `_parse_do_msc_coord()` 전용 함수, mrn/msn 정규식 추출 + AI hint
- HAPAG: `_parse_do_hapag_coord()` 전용 함수, mrn/msn 좌표 추출 + AI hint
- ONE: `_parse_do_one_coord()` 전용 함수, mrn/msn 정규식 추출 + AI hint

### FA / Invoice (invoice_mixin.py)
- Invoice는 SQM SALAR SpA 단일 공급자 고정 양식 → 선사 무관한 좌표 파싱 (`parse_invoice`)
- AI fallback: `parse_invoice_ai()` 호출 경로 존재 (line 295~299)
- 4선사 모두 동일 FA 양식 사용 → 선사 구분 없이 커버

### PL / Packing List (packing_mixin.py)
- Packing List도 SQM SALAR SpA 단일 공급자 고정 양식 → 선사 무관한 좌표 파싱 (`parse_packing_list`)
- HAPAG 전용 처리 흔적 있음: `# HAPAG split format: 'HAMU' + '272359-6'` 주석 (line 292)
- AI fallback: `parse_packing_list_ai()` 경로 존재

|         | BL  | DO  | FA  | PL  |
|---------|-----|-----|-----|-----|
| MAERSK  | ✅  | ✅  | ✅  | ✅  |
| MSC     | ✅  | ✅  | ✅  | ✅  |
| HAPAG   | ✅  | ✅  | ✅  | ✅  |
| ONE     | ✅  | ✅  | ✅  | ✅  |

**범례:** ✅ = 좌표 파싱(1차) + AI fallback(2차) 모두 커버

---

## 종합 판정: GREEN

### 근거
- 체크1~4 전 항목 PASS (총 17개 세부 항목)
- ONE 선사 BL 파싱: CARRIER_RE, BL_FORMAT_MAP, _detect_carrier_from_words 3중 경로 모두 정상
- 4선사 DO mrn/msn: 좌표 파싱(1차)과 AI hint(2차) 이중 커버
- parse_alarm.py: 7개 구조체/함수 전부 완성, mrn/msn CRITICAL + mxbg_pallet CRITICAL 체크 활성
- inbound.py: parse_alarm 4종 연결 + warn_messages + parse_alarms JSON key 응답 완비

### 주의 사항 (YELLOW 경계)
1. **MSC DO mrn 정규식**: `r'(\d{2}MSCU[A-Z0-9]+)\s*/\s*(\d+)'` — MSCU 접두사 고정. MEDU/MSDU 접두사 MSC D/O는 패턴 미매칭 가능. 실제 샘플 확인 권장.
2. **ONE DO mrn 정규식**: `r'(\d{2}[A-Z0-9 ]{3,20})\s+-\s+(\d{3,6})'` — 공백 포함 형태로 PyMuPDF 분리 토큰 재조합 로직 있으나, 토큰 분리 패턴 변화 시 실패 가능. 실샘플 검증 권장.
3. **BL_FORMAT_MAP ONE `12자리`**: prefix='ONEY' + n=12 이지만 주석에 "ONEY+8~12자리"로 되어있어 8~11자리 BL은 `_extract_by_bl_format`에서 미매칭. 그러나 `CARRIER_RE`의 `ONEY[A-Z0-9]{8,15}` 폴백이 커버하므로 실용상 문제없음.
