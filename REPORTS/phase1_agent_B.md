# Phase 1-B: Python 정적 분석 결과
날짜: 2026-04-30

---

## 체크1: 컴파일 검사

| 결과 | 파일 | 비고 |
|---|---|---|
| [PASS] | backend/api/inventory_api.py | |
| [PASS] | backend/api/dashboard.py | |
| [PASS] | backend/api/__init__.py | |
| [PASS] | utils/parse_alarm.py | |
| [PASS] | parsers/document_parser_modular/bl_mixin.py | |
| [PASS] | parsers/document_parser_modular/ai_fallback.py | |
| [PASS] | tools/fix_carrier_rules_one.py | |
| **[FAIL]** | **backend/api/inbound.py** | **SyntaxError — line 1946** |
| [MISSING] | backend/api/menubar.py | 파일 자체가 없음 (CLAUDE.md에 제거됨 기록) |

### inbound.py SyntaxError 상세
```
File "backend/api/inbound.py", line 1946
    result = _db_update_lots(con, "container_no", container_nos, update_dic
                            ^
SyntaxError: '(' was never closed
```
**원인:** `inbound_bl()` 함수 마지막 줄(파일 끝 = line 1945)에서 `_db_update_lots(` 호출의 괄호가 닫히지 않은 채 파일이 잘림. 파일이 1945줄에서 미완성 상태로 끊겨 있음.

**영향:** `inbound_bl` 엔드포인트(`POST /bl`) 완전 미구현. FastAPI 시작 시 `inbound router load failed` 경고 출력 후 해당 라우터 전체 미등록.

---

## 체크2: FastAPI 라우터

총 **23개** `app.include_router()` 호출 / 실제 파일 존재: **20개** / 누락 파일: **0개**

> 참고: `inventory_api.py`에서 5개 라우터(inv/alloc/tb/scan/health)를 한 번에 등록. `menubar.py`는 CLAUDE.md에 "제거됨"으로 기록되어 있으며 `__init__.py`에도 등록되지 않음.

| 라우터 변수명 | 파일 | 파일 존재 |
|---|---|---|
| debug_log_router | backend/api/debug_log.py | OK |
| allocation_router | backend/api/allocation_api.py | OK |
| outbound_api_router | backend/api/outbound_api.py | OK |
| tonbag_api_router | backend/api/tonbag_api.py | OK |
| controls_router | backend/api/controls.py | OK |
| dashboard_kpi_router | backend/api/dashboard.py | OK |
| info_router | backend/api/info.py | OK |
| queries_router | backend/api/queries.py | OK |
| actions_router | backend/api/actions.py | OK |
| optional_router | backend/api/optional.py | OK |
| queries2_router | backend/api/queries2.py | OK |
| actions2_router | backend/api/actions2.py | OK |
| queries3_router | backend/api/queries3.py | OK |
| actions3_router | backend/api/actions3.py | OK |
| settings_router | backend/api/settings.py | OK |
| inbound_router | backend/api/inbound.py | OK (단, SyntaxError로 로드 실패) |
| inv_router / alloc_router / tb_router / scan_router / health_router | backend/api/inventory_api.py | OK |
| carriers_router | backend/api/carriers.py | OK |
| ai_gemini_router | backend/api/ai_gemini.py | OK |
| (errors) | backend/common/errors.py | OK |

---

## 체크3: Import 의존성

inbound.py 상단 import 목록 및 존재 여부:

| 결과 | 모듈 | 비고 |
|---|---|---|
| [OK] | base64, json, logging, re, tempfile, os, math | 표준 라이브러리 |
| [OK] | fastapi, pydantic, typing | 외부 패키지 |
| **[OK]** | fitz (PyMuPDF) | 설치 확인됨 |
| **[MISSING]** | google.genai | `pip install google-genai` 필요. Gemini AI 기능 사용 시 ImportError 발생 |
| [OK] | pandas | 설치 확인됨 |
| [OK] | features.ai.gemini_utils | features/ai/gemini_utils.py 존재 |
| [OK] | parsers.pdf_parser | parsers/pdf_parser.py 존재 |
| [OK] | backend.api (engine, ENGINE_AVAILABLE) | backend/api/__init__.py 존재 |
| [OK] | features.parsers.return_inbound_parser | features/parsers/return_inbound_parser.py 존재 |
| [OK] | features.parsers.return_inbound_engine | features/parsers/return_inbound_engine.py 존재 |
| [OK] | parsers.document_parser_modular.parser | parsers/document_parser_modular/parser.py 존재 |
| [OK] | config.DB_PATH | config.py 존재 |
| [OK] | utils.parse_alarm | utils/parse_alarm.py 존재 |
| [OK] | parsers.cross_check_engine | parsers/cross_check_engine.py 존재 |
| [OK] | utils.date_utils | utils/date_utils.py 존재 |

**중복 import 경고 (품질 이슈, 오류는 아님):**
- `from backend.api import engine, ENGINE_AVAILABLE` — 4회 중복
- `import base64` / `import base64 as _b64` — 2회 중복
- `from utils.date_utils import normalize_date_str as _norm_date_str` — 2회 중복
- `from utils.date_utils import calculate_free_days as _calc_free_days` — 2회 중복
- `from parsers.document_parser_modular.parser import DocumentParserV3` — 2회 중복
- `from parsers.pdf_parser import PDFParser` — 2회 중복

---

## 체크4: Exception 처리

inbound.py 엔드포인트 12개 전수 확인:

| 결과 | 라인 | 함수명 |
|---|---|---|
| [OK — try/except 있음] | L256 | bulk_import_excel |
| [OK — try/except 있음] | L389 | return_inbound_excel |
| [OK — try/except 있음] | L498 | pdf_inbound_upload |
| [OK — try/except 있음] | L1093 | pdf_inbound |
| [OK — try/except 있음] | L1505 | get_inbound_templates |
| [OK — try/except 있음] | L1557 | create_template |
| [OK — try/except 있음] | L1582 | update_template |
| [OK — try/except 있음] | L1609 | delete_template |
| [OK — try/except 있음] | L1629 | template_from_pdf |
| [OK — try/except 있음] | L1711 | templates_from_excel |
| [OK — try/except 있음] | L1817 | inbound_invoice |
| [OK — try/except 있음] | L1901 | inbound_bl (파일 잘림으로 미완성) |

**try/except 있음: 12개 / 없음: 0개**

> 단, `inbound_bl`(L1901)은 try 블록 내부에서 파일이 잘려 있어 except 절이 존재하지 않음 — SyntaxError의 직접 원인.

---

## 체크5: parse_alarm.py 완결성

| 결과 | 항목 |
|---|---|
| [OK] | check_bl 함수 존재 |
| [OK] | check_do 함수 존재 |
| [OK] | check_invoice 함수 존재 |
| [OK] | check_packing 함수 존재 |
| [OK] | AlarmReport.to_dict() 메서드 존재 |

**[PASS]** — 5/5 모두 존재, 컴파일도 정상.

---

## 종합 판정: YELLOW

| 항목 | 판정 | 심각도 |
|---|---|---|
| 체크1: 컴파일 | FAIL (1개) | 높음 — inbound.py SyntaxError |
| 체크2: 라우터 등록 | PASS (23개, 파일 누락 0) | 정상 |
| 체크3: Import 의존성 | YELLOW (1개 누락) | 중간 — google.genai 미설치 |
| 체크4: Exception 처리 | PASS (12/12) | 정상 |
| 체크5: parse_alarm.py | PASS (5/5) | 정상 |

### 필수 조치 항목 (Phase 6 EXE 빌드 전)

1. **[긴급] inbound.py line 1945 복구**
   - `inbound_bl()` 함수의 `_db_update_lots(` 호출이 괄호 미닫힘 + 파일 잘림으로 중단됨
   - 파일 마지막 줄: `result = _db_update_lots(con, "container_no", container_nos, update_dic`
   - `update_dic` → `update_dict` 완성 + `)` 닫기 + except/finally + return 구문 추가 필요
   - **이 버그로 인해 `POST /bl` (B/L PDF 입고) 엔드포인트 전체가 런타임에 미등록됨**

2. **[권장] google.genai 패키지 설치 확인**
   - `pip install google-genai` 또는 `requirements.txt`에 추가
   - 미설치 시 Gemini AI 기능(`/api/ai/*`) ImportError 가능성
   - 단, `ai_gemini.py` 로드는 try/except로 감싸져 있어 서버 기동 자체는 가능

3. **[경미] inbound.py 중복 import 정리**
   - 동일 import 4~2회 중복 — 코드 품질 이슈, 오동작은 없음
