# SQM Inventory v8.6.6 — Release Notes

**릴리즈일:** 2026-04-30
**브랜치:** main
**커밋 태그:** v8.6.6
**작성자:** Ruby (Senior Software Architect)
**승인자:** Nam Ki-dong (사장님)

---

## 🎯 이번 릴리즈 한 줄 요약

> ONE 선사 BL 파싱 완전 수정 + 전선사 mrn/msn 이중 보장 + 파싱 품질 알람 시스템 도입

---

## 🐛 Bug Fixes

### [CRITICAL] ONE Sea Waybill BL 번호 오파싱 완전 수정
**영향:** ONE 선사 입고 시 BL 번호가 SAP 주문번호(2200034590)로 잘못 파싱되던 문제

**원인 3종:**
1. `CARRIER_RE` 정규식에 `ONEY` 패턴 누락 → `\d{9,15}` 폴백이 SAP 번호를 잡아버림
2. `BL_FORMAT_MAP['ONE']` = `[('ONEU', 7)]` → 실제 형식은 `ONEY + 12자리`
3. `_detect_carrier_from_words()` 자동감지 비활성화 → ONE 선사 좌표 테이블 미사용

**수정 파일:** `parsers/document_parser_modular/bl_mixin.py`
```
CARRIER_RE: ONEY[A-Z0-9]{8,15} 패턴 추가
BL_FORMAT_MAP: ONE → ('ONEY', 12)
_detect_carrier_from_words: ONE-LINE.COM / ONEY 패턴 자동감지 재활성화
```

**검증:** `ONEYSCLG01825300` 정상 파싱 확인 ✅

---

### [CRITICAL] carrier_rules DB — ONE BL 패턴 오등록 수정
**원인:** DB에 `ONEU[A-Z0-9]{6,10}` 패턴 등록 → 실제 BL 미감지

**수정 내용:**
- `ONEY[A-Z0-9]{8,15}` 패턴으로 업데이트
- `carrier_rules` 테이블 신규 생성 (기존 DB에 없던 테이블)
- 5개 선사 기본 규칙 전체 등록 (MAERSK/MSC x2/ONE/HAPAG)

**수정 파일:**
- `backend/api/__init__.py` — `_run_db_migrations()` 자동 패치 추가
- `tools/fix_carrier_rules_one.py` — 수동 실행 스크립트 (신규)

---

## ✨ New Features

### [NEW] 파싱 품질 알람 시스템 (`utils/parse_alarm.py`)
입고 4종 서류(BL/DO/FA/PL) 파싱 결과를 자동 검증하는 알람 엔진

**알람 레벨:**
- 🔴 `CRITICAL` — 즉시 조치 필요 (mrn/msn 미추출, mxbg_pallet=0, BL번호 없음 등)
- 🟡 `WARNING` — 확인 권고 (선적일 없음, vessel 없음 등)
- 🔵 `INFO` — 참고 정보

**주요 체크 항목:**

| 서류 | CRITICAL 조건 | WARNING 조건 |
|---|---|---|
| BL | bl_no 없음 | vessel 없음, ship_date 없음 |
| DO | mrn 없음, msn 없음 | arrival_date 없음, do_no 없음 |
| FA | sap_no 없음, invoice_no 없음 | quantity_mt=0 |
| PL | mxbg_pallet=0인 LOT 존재 | total_lots=0, folio 없음 |

**FastAPI 연결 (`backend/api/inbound.py`):**
- `onestop_inbound_upload` 응답에 `parse_alarms` + `parse_alarms_summary` 추가
- CRITICAL 알람 → `warn_messages`에 자동 포함 → UI Toast 표시

---

### [ENHANCED] Gemini DO hint — mrn/msn 전선사 이중 보장
4개 선사(MAERSK/MSC/HAPAG/ONE) DO hint에 mrn/msn 필수 추출 지시 추가

**수정 파일:** `parsers/document_parser_modular/ai_fallback.py`

**mrn/msn 추출 현황 (v8.6.6 기준):**
| 선사 | 좌표/정규식 | Gemini AI |
|---|---|---|
| MAERSK | ✅ by_xy (x=33~45.5%, y=87.8~89.5%) | ✅ hint 강화 |
| MSC | ✅ regex `\d{2}MSCU[A-Z0-9]+\s*/\s*\d+` | ✅ hint 강화 |
| HAPAG | ✅ by_xy (x=50~63.5%, y=12~14%) | ✅ hint 강화 |
| ONE | ✅ regex `\d{2}[A-Z0-9 ]{3,20}\s+-\s+\d{3,6}` | ✅ hint 강화 |

---

## 🔧 Infrastructure

### CLAUDE.md — Ruby 행동 규칙 A/B/C/D 영구 기록
- Rule A: 추천 먼저, 질문은 그 다음 ("루비의 추천: [선택지] — 이유: [한 줄 근거]")
- Rule B: 기술결정=강하게, 비즈니스결정=옵션 제시
- Rule C: 틀렸을 때 즉시 정정 + CLAUDE.md 자동 기록
- Rule D: 확신 60% 이하 시 "확신 없음 (X%)" 명시

---

## 📊 테스트 현황

| 테스트 | 결과 |
|---|---|
| test_phase5_parity.py (44개 패리티) | 44 passed ✅ |
| BL 파싱 — ONE ONEYSCLG01825300 | ✅ |
| DO mrn/msn — MAERSK | ✅ `26MAEU...` |
| DO mrn/msn — MSC | ✅ `26MSCU...` |
| DO mrn/msn — HAPAG (HLCUSCL260148627) | ✅ `26HLCU9401I / msn=6006` |
| DO mrn/msn — ONE (ONEYSCLG01825300) | ✅ `26HDM UK026I / msn=5019` |
| carrier_rules DB — 5선사 등록 | ✅ |

---

## 🔧 Hotfix — 2026-05-01 (GitHub `main` 동기화)

| 항목 | 내용 |
|------|------|
| **목적** | [kidongnam1/sqm_3](https://github.com/kidongnam1/sqm_3) `main` 브랜치와 로컬 작업 트리 정합성 확보 |
| **API** | `POST /api/inbound/bl` — 핸들러 하단이 잘려 있던 문제 수정 (`update_dict` 인자·성공 응답·`HTTPException`/`finally`·임시 PDF 삭제) |
| **저장소** | `data/db/sqm_inventory.db` 바이너리 Git 추적 제거, 로컬 DB는 `.gitignore`로만 제외 |

---

## 🗺️ 다음 릴리즈 (Phase 6)

- PyInstaller 단일 EXE 빌드
- Windows 배포 패키지 생성
- GY Logis 실사용 전환 준비

---

**전체 진행률:** 약 83% (Phase 0~5 + v8.6.6 버그픽스 완료)
**예상 최종 릴리즈:** 2026-05-09 ~ 2026-05-25
