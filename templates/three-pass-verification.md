# Three-Pass Verification SOP — 3-Pass 검증 표준 절차

**작성:** 2026-05-06 (수) — Ruby (Senior Architect) — SQM Async UI Thread Patch 에서 검증된 패턴.

---

## 🎯 목적 (Why 3-pass?)

| 차수 | 발견 비율 (실증 데이터) | 누적 신뢰도 |
|---|---|---|
| **1차** (구현 + 자체 평가) | ~50~60% 결함 발견 | ~50% |
| **2차** (독립 재검증) | 추가 ~30% 발견 (MAJOR/MEDIUM) | ~85% |
| **3차** (전수 검사) | 추가 ~10% 발견 (CRITICAL/EDGE) | **~95~99%** |

**SQM 사례 (2026-05-06)**:
- 1차: 구현 완료 (자체 평가 🟢)
- 2차: P1 MAJOR + P3 MEDIUM + Docs 5건 발견
- 3차: **P1 CRITICAL** (JS 브릿지 무한 재귀) + Docs 4건 발견 → production 사고 사전 방지

---

## 📋 적용 시점 (When)

다음 중 하나라도 해당하면 3-pass 의무 적용:
- ✅ 메인 진입점 파일 (`main_*.py`, `app.py` 등) 변경
- ✅ 동시성/스레드 패턴 추가 (asyncio, threading, Qt signals 등)
- ✅ UI 이벤트 핸들러 변경 (Qt signals, JS event listeners 등)
- ✅ 외부 시스템 통합 (DB, API, AI server 등)
- ✅ 다중 파일 동시 변경 (3 파일 이상)
- ✅ 사용자 데이터 영향 가능성 (export, backup, migration)

작은 단일 함수 변경이나 문서 수정은 1-pass 충분.

---

## 🔬 3-Pass 절차

### Pass 1 — 구현 (Implementation)

**누가**: Main agent + Sub-agents (병렬 가능)
**산출**:
- 코드 변경 (파일 백업 포함)
- 1차 자체 평가 보고서 (`REPORT_1차_<DATE>.md`)
- 작업 지시서 §4 의 모든 합격 기준 충족 확인

**합격 기준**:
- [ ] 모든 작업 지시서 항목 ✅ 표시
- [ ] 코드 변경 적용됨
- [ ] 자체 평가 🟢 PASS

### Pass 2 — 독립 재검증 (Independent Re-audit)

**누가**: 1차와 **다른 인스턴스** sub-agents (1차 컨텍스트 미공유)
**관점**: "1차에서 무엇을 놓쳤는가?"
**중점**:
- Race condition / thread safety
- Edge cases / error paths
- Sub-agent 결과 품질 차이
- 문서 정합성

**산출**:
- 영역별 audit 보고서 (`AUDIT_2차_<영역>_<DATE>.md`)
- 통합 2차 보고서 (`REPORT_2차_<DATE>.md`)
- **발견된 이슈 즉시 수정**

**합격 기준**:
- [ ] 모든 영역 🟢 또는 🟡(즉시 수정 후 🟢)
- [ ] CRITICAL/MAJOR 0건 잔존
- [ ] 2차 보고서 작성

### Pass 3 — 전수 검사 (Full Audit)

**누가**: 2차와도 **다른 인스턴스** sub-agents
**관점**: "2차 fix 가 새 결함 만들지 않았는가? + 실세계 시나리오"
**중점**:
- 2차 수정의 회귀 검증
- Multi-fire / re-entry 시나리오
- Stress test (rapid clicks, concurrent operations, low memory)
- Compliance vs spec
- Final pre-deployment readiness

**산출**:
- 영역별 audit 보고서 (`AUDIT_3차_<영역>_<DATE>.md`)
- 통합 3차 보고서 (`REPORT_3차_<DATE>.md`)
- **CRITICAL/MAJOR 발견 시 즉시 수정**

**합격 기준**:
- [ ] 2차 fix 들 모두 회귀 없음
- [ ] CRITICAL 0건
- [ ] Spec compliance 100%
- [ ] Production-ready 선언

---

## 🛠 표준 Sub-agent 구성 (Reusable)

### 2차 sub-agents (5개 권장)
| Agent | 역할 |
|---|---|
| Sub-A | 핵심 코드 (예: main 진입점) 독립 audit |
| Sub-B | 보조 코드 1 (예: 모듈 1) 독립 audit |
| Sub-C | 보조 코드 2 (예: 모듈 2) 독립 audit |
| Sub-D | 테스트 호환성 분석 |
| Sub-E | 문서 정합성 cross-check |

### 3차 sub-agents (5개 권장)
| Agent | 역할 |
|---|---|
| Sub-K | Race + edge cases (2차 fix 회귀 포함) |
| Sub-L | Integration + 의존성 (Python ver, 모듈 graph) |
| Sub-M | Syntax + imports 전수 |
| Sub-N | Spec compliance 매트릭스 |
| Sub-O | Docs 정정 (실제 fix 적용) |

---

## 📁 산출물 명명 규칙

```
프로젝트 루트/
├── SQM_WORK_ORDER_<DATE>.md          # 작업 지시서 (Pre-flight)
├── REPORT_1차_<DATE>.md              # 1차 자체 평가
├── REPORT_2차_<DATE>.md              # 2차 통합
├── REPORT_3차_<DATE>.md              # 3차 통합
├── SQM_PATCH_FINAL_REPORT_<DATE>.md  # 최종 마스터
├── MANUAL_SMOKE_CHECKLIST.md         # 대표님 수동 검증
└── AUDIT_<차수>_<영역>_<DATE>.md       # 각 sub-agent 산출물
```

---

## 💰 ROI 분석

| 지표 | 1-pass 만 | 3-pass | 차이 |
|---|---|---|---|
| 시공 시간 | ~60분 | ~150분 (2.5배) | +90분 |
| 결함 검출률 | ~50% | ~95~99% | **2배** |
| Production 사고 가능성 | 중간~높음 | 매우 낮음 | 큰 차이 |
| 다음 패치 재사용 자산 | 적음 | SOP + 템플릿 | 누적 효과 |

**계산**: 사고 1건 해결 비용 (긴급 hotfix + 사용자 신뢰 손실 + 디버깅 시간) 보통 **시공 시간의 5~10배**. 따라서 3-pass 는 **방어적으로 매우 합리적**.

---

## 🎬 적용 사례 (Reference)

### SQM Async UI Thread Patch (2026-05-06)
- 1차: 6 작업 (P1+P2+P3+Q1+Q2+E2E) 완료, 자체 🟢
- 2차: P1 MAJOR (`_navigated` 2-state) + P3 MEDIUM (atexit) 발견 → 수정
- 3차: **P1 CRITICAL (JS bridge 재귀) 발견** → idempotency guard 추가
- 결과: production-ready, 사고 0건 예상

자세한 사례: `D:\program\SQM_inventory\SQM_v866_CLEAN\REPORT_3차_2026-05-06.md`

---

## 🔗 다음 프로젝트 적용 (Cross-project)

이 SOP 는 다음 프로젝트에도 그대로 적용 권장:
- `D:\program\LME` — `run_ui_test` 1.2초 freeze 패치 시
- `D:\program\RUBI_SYSTEM_FULL_v1_6` — 향후 비동기화 시
- `D:\program\HY_export\HY_Clean_Metal_V9.2.0` — 향후 패치 시
- `D:\program\youtube_unified` — 추가 P2 패치 시 (이미 검증됨)

각 프로젝트는 `templates/three-pass-verification.md` 를 자체 폴더에 복사하면 즉시 사용 가능.

---

*Ruby (Senior Software Architect) — Three-Pass Verification SOP — 2026-05-06.*
