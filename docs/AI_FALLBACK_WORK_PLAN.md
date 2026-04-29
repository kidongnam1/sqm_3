# AI Fallback Parsing — 전체 작업 계획서

> **작성일:** 2026-04-28  
> **작성자:** Ruby (Senior Software Architect)  
> **대상 폴더:** `SQM_v865_CLEAN/`  
> **GitHub:** `sqm_3` main 브랜치

---

## 1. 목표 (Why)

좌표 기반 파싱(coordinate parsing)은 PDF 레이아웃이 조금만 바뀌어도 빈값을 반환한다.  
AI fallback은 이 실패를 자동으로 보완한다.

```
[PDF 입고]
   ↓
좌표 파싱 (1차, 빠름)
   ↓ 실패하면
AI fallback (2차, 정확함)
   ↓
같은 InvoiceData / PackingListData / BLData / DOData 모델 반환
```

---

## 2. 아키텍처 개요

### 파일 위치

```
parsers/document_parser_modular/
├── ai_fallback.py          ← 핵심 (562 lines) ✅ 완료
├── invoice_mixin.py        ← FA 파서 (좌표 기반)
├── packing_mixin.py        ← PL 파서 (좌표 기반)
├── bl_mixin.py             ← BL 파서 (좌표 기반)
└── do_mixin.py             ← DO 파서 (좌표 기반)
```

### ai_fallback.py 제공 함수

| 함수 | 설명 |
|---|---|
| `normalize_carrier_id(carrier_id)` | HLCU→HAPAG, MEDU→MSC 등 alias 정규화 |
| `build_ai_hint(doc_type, carrier_id, partial)` | 선사별 Gemini 프롬프트 hint 생성 |
| `_copy_if_empty(dst, src, fields)` | 좌표 결과 우선, AI 결과로 빈칸 보완 |
| `parse_invoice_ai(owner, pdf_path, ...)` | FA AI 파싱 |
| `parse_packing_list_ai(owner, pdf_path, ...)` | PL AI 파싱 |
| `parse_bl_ai(owner, pdf_path, ...)` | BL AI 파싱 ✅ bl_mixin 연결 완료 |
| `parse_do_ai(owner, pdf_path, ...)` | DO AI 파싱 |
| `parse_inbound_4docs(owner, ...)` | 4종 서류 일괄 파싱 오케스트레이터 |

---

## 3. 현재 연결 상태 (2026-04-28 기준)

| 서류 | 좌표 파싱 | AI fallback 연결 | 상태 |
|---|---|---|---|
| FA (Invoice) | `invoice_mixin.py` | ❌ 미연결 | 🔧 작업 필요 |
| PL (Packing List) | `packing_mixin.py` | ⚠️ 자체 AI 로직 (`_parse_packing_with_ai`) | 🔄 ai_fallback으로 통합 가능 |
| BL (Bill of Lading) | `bl_mixin.py` | ✅ line 230-231 연결 완료 | ✅ |
| DO (Delivery Order) | `do_mixin.py` | ⚠️ `build_ai_hint`만 사용, `parse_do_ai` 미호출 | 🔧 작업 필요 |

---

## 4. 선사 × 서류 지원 매트릭스

### 좌표 기반 파싱 (coordinate parsing)

| 선사 | FA | PL | BL | DO |
|---|---|---|---|---|
| **MAERSK** | ✅ | ✅ | ✅ | ✅ |
| **MSC** | ✅ | ✅ | ✅ | ✅ |
| **HAPAG** | ✅ | ✅ | ✅ | ✅ |
| **ONE** | ✅ | ✅ | ✅ | ✅ |

### AI fallback (Gemini)

| 선사 | FA | PL | BL | DO |
|---|---|---|---|---|
| **MAERSK** | 🔧 연결 예정 | 🔄 통합 예정 | ✅ | 🔧 연결 예정 |
| **MSC** | 🔧 연결 예정 | 🔄 통합 예정 | ✅ | 🔧 연결 예정 |
| **HAPAG** | 🔧 연결 예정 | 🔄 통합 예정 | ✅ | 🔧 연결 예정 |
| **ONE** | 🔧 연결 예정 | 🔄 통합 예정 | ✅ | 🔧 연결 예정 |

---

## 5. 작업 항목 (Task List)

### Task 1: `invoice_mixin.py` AI fallback 연결 [🔧 예정]
- 좌표 파싱 실패 시 (`result.success == False`) `parse_invoice_ai()` 호출
- `partial=result` 전달하여 좌표 추출 성공 필드는 그대로 유지
- 파일 수정: `invoice_mixin.py` (마지막 30줄 부근)

### Task 2: `do_mixin.py` AI fallback 연결 [🔧 예정]
- 현재: `build_ai_hint`만 호출 (line 1037-1038)
- 목표: 파싱 실패 시 `parse_do_ai()` 실제 호출
- 파일 수정: `do_mixin.py` (line 1035~1060 부근)

### Task 3: parity 테스트 작성 [🔧 예정]
- `tests/test_ai_fallback_parity.py`
- 4 서류 × 4 선사 = 최대 16개 조합 검증
- 좌표 결과 ↔ AI 결과 필드 일치 여부 확인
- `@pytest.mark.integration` 마커로 실제 API 호출 테스트 분리

### Task 4: normalization 단위 테스트 [🔧 예정]
- `ai_fallback.py` 내부 함수 단위 테스트
- `_to_float`, `_norm_bl`, `_norm_container`, `_copy_if_empty` 등

---

## 6. 데이터 흐름 (비유: 레스토랑 주문)

```
손님 주문 = PDF 파일
웨이터 = 좌표 파서 (빠르고 효율적)
주방장 = AI fallback (느리지만 어떤 메뉴도 해석 가능)

웨이터가 메뉴를 읽지 못하면 (좌표 실패)
→ 주방장에게 전달 (AI fallback)
→ 웨이터가 가져온 재료는 그대로 사용 (_copy_if_empty)
→ 같은 접시에 담아 제공 (동일한 Data 모델)
```

---

## 7. AI hint 선사별 예시

### MSC BL hint
```
MSC Sea Waybill. BL No usually starts with MEDU or MSCU.
Do not confuse rider-page container numbers with BL No.
```

### HAPAG DO hint
```
HAPAG-Lloyd D/O. BL/SWB No starts with HLCU. 
Extract container list, free time deadline, empty return yard.
```

---

## 8. 테스트 전략

### 레이어 1: 단위 테스트 (API 키 불필요)
- `_to_float("1,234.56")` → `1234.56`
- `_norm_bl("MEDU 9700352")` → `"MEDU9700352"`
- `_copy_if_empty`: dst가 비어있을 때만 src 값 복사
- `build_ai_hint` 출력 형식 검증

### 레이어 2: mock 테스트 (API 키 불필요)
- GeminiDocumentParser를 MagicMock으로 교체
- AI가 반환한 raw JSON → Data 모델로 정규화 검증
- 오류 시나리오 (JSON 파싱 실패, 필드 누락 등)

### 레이어 3: 통합 테스트 (API 키 필요)
- 실제 PDF 파일 + 실제 Gemini API 호출
- `GEMINI_API_KEY` 환경변수 없으면 자동 skip
- `@pytest.mark.integration` 마커

### 레이어 4: 패리티 테스트 (API 키 + 실제 PDF)
- 좌표 파싱 결과 vs AI 파싱 결과 필드 비교
- 핵심 필드 일치 여부: `bl_no`, `sap_no`, `container_count`, `quantity_mt`
- 불일치 시 경고 (에러가 아님 — 레이아웃 변경 가능성)

---

## 9. Git 현황

```
sqm_3 (GitHub)
├── main 브랜치
├── 최신 커밋: Phase 5 회귀 테스트 완료
└── 미커밋: do_mixin sort key 수정, extract_box 추가, test_container.py 50개 테스트
```

**미커밋 항목 git add 방법 (CMD):**
```cmd
cd D:\program\SQM_inventory\SQM_v865_CLEAN
git add utils/container_utils.py
git add parsers/document_parser_modular/do_mixin.py
git add tests/test_container.py
git commit -m "Phase 5b: extract_box fallback + do_mixin sort fix + 50 tests"
git push origin main
```

---

## 10. Phase 6 선행 조건

Phase 6 (EXE 빌드)로 가기 전 완료해야 할 항목:

- [x] Phase 5: 44개 패리티 회귀 테스트 통과
- [x] `ai_fallback.py` 작성 (562 lines)
- [x] `bl_mixin.py` AI fallback 연결
- [ ] `invoice_mixin.py` AI fallback 연결
- [ ] `do_mixin.py` `parse_do_ai` 실제 호출 연결
- [ ] `tests/test_ai_fallback_parity.py` 작성 및 통과
- [ ] git commit (미커밋 항목)

---

## 11. 예상 일정

| 날짜 | 작업 | 예상 소요 |
|---|---|---|
| 2026-04-28 | invoice_mixin + do_mixin 연결, parity 테스트 작성 | 2~3시간 |
| 2026-04-29 | 실제 PDF로 통합 테스트, 오류 수정 | 2~3시간 |
| 2026-04-30 | git commit + Phase 6 EXE 빌드 시작 | 1시간 |

---

*이 문서는 작업 진행에 따라 업데이트됩니다.*
