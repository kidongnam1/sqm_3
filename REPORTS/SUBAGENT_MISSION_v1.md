# SQM v865 — Sub-Agent 팀 작업 지시서 v1
**작성일:** 2026-04-29  
**작성자:** Ruby (Senior Software Architect)  
**승인자:** Nam Ki-dong (사장님)  
**목적:** PDF 파싱 정확도 검증 + 파싱 방식 선택 UI 개선 + 안정성 보완

---

## 📌 핵심 방향 (변경 불가 원칙)

> **좌표 등록 방식(①)은 항상 기본값(ON). 나머지 AI 방식(②~⑤)은 사용자가 선택.**  
> 초보자 = 전부 ON. 숙련자 = 필요한 것만 ON. 시스템은 ON된 것만 순서대로 실행.

---

## 👥 에이전트 역할 분리

### Agent A — 파싱 정확도 검증 (테스트 전담)
**임무:** 16개 픽스처 PDF × 활성 파싱 방식으로 실제 파싱 실행 → 정확도 측정 → 결과표 작성

#### 테스트 대상 PDF (tests/fixtures/)
| # | 파일 | 선사 | 문서 종류 |
|---|---|---|---|
| 1 | HAPAG_DO.pdf | Hapag-Lloyd | D/O (인도지시서) |
| 2 | MAERSK_DO.pdf | Maersk | D/O |
| 3 | MSC_DO.pdf | MSC | D/O |
| 4 | ONE_DO.pdf | ONE | D/O |
| 5 | HAPAG_BL.pdf | Hapag-Lloyd | B/L |
| 6 | MAERSK_BL.pdf | Maersk | B/L |

> ※ DO 4종 + BL 2종 = **6케이스** (FA/PL은 Phase 2에서)

#### 활성 파싱 방식
| 방식 | 상태 | 비고 |
|---|---|---|
| ① 좌표 등록 | ✅ 항상 실행 | 기본값, API 비용 없음 |
| ② Gemini | ✅ | api_key 갱신 필요 |
| ③ Groq | ⚠️ | 키 폐기됨, 새 키 발급 후 활성화 |
| ④ xAI | ✅ | settings.ini에 키 있음 |
| ⑤ OpenRouter | ✅ | deepseek/deepseek-r1:free |
| ⑥ OpenAI | 🔴 보류 | 크레딧 없음 |

#### 정확도 측정 기준
각 방식이 추출한 필드값을 **정답(Ground Truth)과 비교**:

| 필드 | DO 정답 예시 | 중요도 |
|---|---|---|
| container_no | HLXU1234567 | ★★★ |
| vessel_name | EVER GIVEN | ★★★ |
| voyage_no | 123E | ★★ |
| arrival_date | 2025-01-15 | ★★★ |
| do_no | DOC-2025-001 | ★★ |
| shipper | ABC COMPANY | ★ |
| consignee | XYZ CO LTD | ★ |

#### 반복 검증
- AI 방식: **3회 반복** (API 비용 감안, 5회 대신 3회로 조정)
- 좌표 방식: 1회 (결정적 — 항상 같은 값)
- 결과: **평균 정확도 % 계산**

#### 산출물
- `REPORTS/accuracy_validation_YYYYMMDD.md` — 방식별 정확도 표
- `REPORTS/ground_truth.json` — 정답 데이터셋 (재사용 가능)

---

### Agent B — 파싱 선택 UI 구조 개선 (프론트엔드 전담)
**임무:** 파싱 방식 선택 체크박스 UI를 "좌표 기본 고정 + 나머지 선택형"으로 재구성

#### 현재 구조 (변경 전)
```
[ ] ① 좌표 등록   [ ] ② Gemini   [ ] ③ Groq   [ ] ④ xAI   [ ] ⑤ OpenRouter
```

#### 목표 구조 (변경 후)
```
[✅ 항상 ON] ① 좌표 등록 (기본값 — 해제 불가)
───────────────────────────────────────────
선택 옵션 (초보자: 전부 ON 권장 / 숙련자: 필요한 것만)
[☑] ② Gemini       [☑] ③ Groq
[☑] ④ xAI          [☑] ⑤ OpenRouter
───────────────────────────────────────────
[초보자 모드 (전체 ON)] [숙련자 모드 (좌표만)]  ← 빠른 설정 버튼
```

#### 수정 파일
- `frontend/js/sqm-inline.js` (300KB+ → **Python 패치 스크립트 필수**, Edit 툴 금지)
- `frontend/index.html` (UI 마크업)
- `backend/api/inbound.py` (선택된 방식만 실행하는 로직)

#### 로직 변경
```python
# inbound.py — 선택된 방식만 실행
def run_selected_methods(doc_type, pdf_path, methods: list):
    results = {}
    results['coord'] = run_coord(doc_type, pdf_path)  # 항상 실행
    if 'gemini' in methods:   results['gemini']      = run_gemini(...)
    if 'groq' in methods:     results['groq']        = run_groq(...)
    if 'xai' in methods:      results['xai']         = run_xai(...)
    if 'openrouter' in methods: results['openrouter'] = run_openrouter(...)
    return results
```

---

### Agent C — 안정성 & UX 감사 (코드 리뷰 전담)
**임무:** 현재 파싱 파이프라인의 잠재 위험 요소 발굴 + 개선안 제시

#### 검토 항목
1. **Dead Code 탐지** — 사용되지 않는 파싱 함수/임포트
2. **예외 처리 누락** — try/except 없는 API 호출 지점
3. **타임아웃 미설정** — AI API 호출 시 무한 대기 가능성
4. **UI/Logic 분리 위반** — sqm-inline.js에 비즈니스 로직 혼입 여부
5. **결과 캐싱 없음** — 같은 PDF를 반복 파싱 시 API 비용 낭비
6. **Toast 누락** — 파싱 실패 시 사용자에게 알림이 없는 경우

#### 산출물
- `REPORTS/stability_audit_YYYYMMDD.md` — 위험도별 이슈 목록

---

## 🚦 실행 순서 (의존성)

```
[사전조건]
  └── Groq 새 키 발급 (사장님 직접)
  └── settings.ini 키 전체 확인

[Agent A] 정확도 검증  ──┐
[Agent B] UI 구조 개선  ──┼──▶ [통합 검증] ──▶ [GitHub 커밋]
[Agent C] 안정성 감사  ──┘
```
A/B/C는 **병렬 실행 가능** (서로 파일 충돌 없음)

---

## ⚠️ 작업 제약 (절대 규칙)

1. `sqm-inline.js` (300KB↑) → **Edit 툴 직접 수정 금지** → Python 패치 스크립트로
2. `engine_modules/`, `features/`, `parsers/`, `utils/` 원본 → **수정 금지**
3. 색상/폰트 → `design-tokens.css` 변수만 사용
4. `settings.ini` → **git 커밋 금지** (API 키 포함)
5. 새 파일 추가 전 → Glob/Grep으로 중복 확인 필수

---

## 📁 산출물 요약

| 파일 | 담당 에이전트 | 저장 위치 |
|---|---|---|
| accuracy_validation_YYYYMMDD.md | Agent A | REPORTS/ |
| ground_truth.json | Agent A | tests/fixtures/ |
| stability_audit_YYYYMMDD.md | Agent C | REPORTS/ |
| UI 수정 (index.html, sqm-inline.js) | Agent B | frontend/ |
| inbound.py 선택 실행 로직 | Agent B | backend/api/ |

---

**버전:** v1  
**다음 버전 예정:** 검증 결과 반영 후 v2 (FA/PL 추가, 4선사 전체 확장)
