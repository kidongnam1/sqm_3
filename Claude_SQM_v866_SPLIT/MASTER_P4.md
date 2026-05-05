# SQM v866 MASTER-P4: Phase 4 (QA + ZIP + DONE)
**이 파일이 마지막 단계입니다**
**모든 검증 통과 시 DONE.md 생성**

---
## 절대 원칙 (항상 적용)
- pytest 44 passed 유지 (감소 불가)
- node --check 전체 통과
- 패치 ZIP 폴더 구조 포함 필수
- 에러 시 RETRY 3회 + Ruby 즉시 수정 후 다음 TASK 진행 (중단 금지)
- error_report.md는 기록용으로만 사용 (작성해도 STOP하지 말 것)

---
## 체크포인트 규칙
완료 시: progress.txt 에 "DONE: [TASK명]" 추가

---
# PHASE 4 — 통합 검증 + EXE 빌드 (Agent D)

## P4-TASK-01: 교차검증 5항목

```bash
# ① SQL 오염 확인
grep -rn "\-\-" backend/api/ --include="*.py" | grep -v "^.*#" | grep -v "\.pyc"

# ② SOLD 전환 경로 확인
grep -rn "SOLD\|confirm_outbound" backend/api/ --include="*.py"
# → scan_api.py 에만 있어야 함

# ③ 미들웨어 등록 확인
grep -n "exception_handler\|add_middleware" backend/api/__init__.py

# ④ 전체 문법 검사
find backend -name "*.py" | xargs python -m py_compile
find frontend/js -name "*.js" | xargs node --check

# ⑤ 대용량 파일 크기 확인
python -c "import os; s=os.path.getsize('frontend/js/sqm-inline.js'); print(f'sqm-inline.js: {s:,} bytes'); assert s > 200000, '파일 붕괴!'"

출력:
=== 교차검증 결과 ===
① SQL 오염: [OK]/[FAIL]
② SOLD 경로: [OK]/[FAIL]
③ 미들웨어: [OK]/[FAIL]
④ 문법검사: [OK]/[FAIL]
⑤ 파일크기: [OK]/[FAIL]
```

## P4-TASK-02: pytest 기준 유지 확인

```bash
python -m pytest tests/test_phase5_parity.py -v --tb=short
# 기준: 44 passed 유지 (신규 추가 가능, 감소 불가)

# 전체 테스트
python -m pytest tests/ -q --tb=short 2>&1 | tail -5
```

## P4-TASK-03: UI 스모크 체크 요청

```
python scripts/telegram_notify.py smoke

기동님께 30초 확인 요청:
[ ] main_webview.py 실행 → 브라우저 창 열림
[ ] 사이드바 9개 탭 표시
[ ] Inventory 탭 데이터 로드
[ ] 상단 메뉴 드롭다운 열림
[ ] Dashboard KPI 숫자 표시

기동님 '확인완료' 답장 → P4-TASK-04 진행
이상 발견 → 해당 페이지 Agent A 재작업
```

## P4-TASK-04: 패치 ZIP 생성

```
파일명: Claude_SQM_v866_PATCH.zip

포함 파일 (변경된 것만):
Claude_SQM_v866_PATCH\
  backend\api\
    scan_api.py          ← 신규
    integrity_api.py     ← 신규
    carriers.py          ← 수정
    __init__.py          ← 라우터 추가
  frontend\js\
    api-client.js        ← 수정
    sqm-inline.js        ← 수정 (IIFE 버그)
    pages\
      inventory.js       ← 수정
      dashboard.js       ← 수정
      scan.js            ← 수정
    handlers\
      menubar.js         ← 수정
  config_logging.py      ← 수정
  scripts\
    telegram_notify.py   ← 신규 추가

[주의] 폴더 구조 반드시 포함. 파일만 단독 삽입 금지.
```

## P4-TASK-05: DONE.md + 완료 알림

```markdown
# SQM v866 Sub-Agent Team 작업 완료
날짜: {날짜}
팀: MASTER + Agent A/B/C/D/E

## 완료 내역
Phase 0: 환경 검증 [OK]
Phase 0 (Agent E): 6방식 파서 비교 [OK 또는 PARTIAL]
  - 최고 정확도 방식: [방식명] ([%]%)
  - 권장 방식: [방식명]
  - 결과: REPORTS/parse_comparison_6method_final.html
Phase 1: 버그 수정 3건 [OK]
  - carriers.py GET 쓰기 버그
  - config_logging.py CP949
  - sqm-inline.js _zFloatTop IIFE
Phase 2: 백엔드 API 보완 [OK]
  - scan_api.py 신규
  - integrity_api.py 신규
Phase 3: 프론트엔드 JS 완성 [OK]
  - inventory.js 실데이터 연결
  - dashboard.js KPI + 30초 갱신
  - scan.js 4버튼 연결
Phase 4: 교차검증 통과 [OK]

## 테스트 결과
pytest test_phase5_parity.py: 44 passed (기준 유지)

## 패치 파일
Claude_SQM_v866_PATCH.zip

## 다음 작업 권장 (Ruby)
1. Phase 6: PyInstaller EXE 빌드
2. 파서 비교 결과 기반 기본 파싱 방식 확정 (settings.ini 반영)
3. inbound.py 예외 pass → 단계별 실패 사유 명시
```

DONE.md 생성 후:
```
python scripts/telegram_notify.py done
```

---

## 🎯 완수율 분석

| 구성 요소 | 차단하는 실패 | 기여 |
|----------|-------------|------|
| SKILL.md + MASTER.md | 도메인/순서 혼란 | +30% |
| RETRY Protocol | 단순 코드 에러 | +15% |
| run_master.bat | 프로세스 중단 | +10% |
| progress.txt | 세션 끊김 | +10% |
| SUMMARY.md | 컨텍스트 소실 | +5% |
| env_check | 환경 불일치 | +8% |
| 판단 트리거 | 판단 불가 에러 | +4% |
| UI 스모크 체크 | UI 렌더링 오류 | +2% |
| Telegram SYNC | BLOCKED 빠른 해소 | +3% |
| v866 실구조 반영 | 경로/파일 오류 | +10% |
| **합계** | | **~97%** |

---

*SQM v866 Sub-Agent Team MASTER — Ruby 2026-05-01*
*실제 폴더 구조 분석 기반 (v8.6.5, Phase 5 완료 상태)*

