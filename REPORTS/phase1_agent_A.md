# Phase 1-A: JS 정적 분석 결과
날짜: 2026-04-30

---

## 체크1: JS 문법 (node --check)

| 파일 | 결과 | 상세 |
|---|---|---|
| `frontend/js/sqm-inline.js` | **FAIL** | line 5730 — SyntaxError: Invalid or unexpected token |
| `frontend/js/sqm-onestop-inbound.js` | **FAIL** | line 1323 — SyntaxError: Invalid or unexpected token |
| `frontend/js/handlers/menubar.js` | **PASS** | 이상 없음 |

### 원인 분석 (중요)
두 파일 모두 **파일 말미에 null 바이트(`\x00`) 오염** 발생. CLAUDE.md에 기록된 "파일잘림/null바이트 오염" 재발.

```
sqm-inline.js:
  - 파일 총 크기: 334,720 bytes
  - 유효 JS 코드 종료: byte 321,223 (line 5729, "})();\n")
  - null 바이트 구간: byte 321,223 ~ 334,720 (13,497 null bytes)
  - JS 코드 자체는 완전함 (})(); 로 정상 종료 확인)

sqm-onestop-inbound.js:
  - 파일 총 크기: 94,718 bytes
  - 유효 JS 코드 종료: byte 77,962 (line 1322, "})();\n")
  - null 바이트 구간: byte 77,962 ~ 94,718 (16,756 null bytes)
  - JS 코드 자체는 완전함 (})(); 로 정상 종료 확인)
```

> **브라우저 영향:** PyWebView 내장 브라우저(WebKit/Chromium)는 null 바이트를 만나면
> 해당 지점에서 파싱을 중단하므로, 실제 실행 시 `})();` 이후 null 구간은 무시됨.
> 즉 **기능상 치명적 오류는 아니나**, node --check는 엄격하게 오류 처리함.
> 수정 권장: Python 스크립트로 null 바이트 제거 후 재저장.

---

## 체크2: data-action 커버리지

- **index.html 내 data-action 총 선언:** 86개 (84 unique, 2개 중복)
- **sqm-inline.js 내 커버 여부:** 84/84 — **누락 없음**

### 중복 선언 (주의)
| data-action | 위치 |
|---|---|
| `onIntegrityCheck` | 입고 메뉴 > 입고 설정 (line 114) + 관리 메뉴 > 데이터 관리 (line 255) |
| `onSalesOrderDN` | 출고 메뉴 > SO 관리 (line 158) + 보고서 메뉴 > 문서 (line 200) |

> 중복 자체는 기능 오류를 일으키지 않음. 동일 핸들러가 두 메뉴에서 호출되는 의도적 배치일 가능성 높음.

---

## 체크3: Dead Code (상위 10)

총 정의된 public 함수: 98개. 이 중 **index.html에서 직접 참조되지 않는** 함수는 98개 전부
(IIFE 구조상 내부 함수는 HTML에서 직접 호출하지 않으므로 정상).

### 진짜 Dead Code — JS 내부에서도 호출 0회인 함수 (7개)

| 함수명 | 판정 |
|---|---|
| `commit` | Dead — 정의만 있고 호출 없음 |
| `enableTableSort` | Dead — 정의만 있고 호출 없음 |
| `fetchLotInfo` | Dead — 정의만 있고 호출 없음 |
| `initSqmTooltip` | Dead — 정의만 있고 호출 없음 |
| `scheduleSummary` | Dead — 정의만 있고 호출 없음 |
| `showPdfInboundUploadModal` | Dead — 정의만 있고 호출 없음 (주의: `onOnPdfInbound`와 별개) |
| `updatePreview` | Dead — 정의만 있고 호출 없음 |

> 이 7개는 제거하거나 미완성 기능이면 TODO 주석 추가 권장.
> 빌드 크기에 영향은 미미하나 코드 명확성 저하.

---

## 체크4: 코드 품질 지표

| 항목 | sqm-inline.js | sqm-onestop-inbound.js | 합계 |
|---|---|---|---|
| `console.error` 개수 | 0 | 0 | **0** |
| `TODO` / `FIXME` 주석 | 0 | 0 | **0** |

> console.error 0건은 **긍정적** 신호 — 에러 처리가 toast/UI로 통일되어 있음을 시사.
> TODO/FIXME 0건은 **양면적** — 미완성 코드가 숨겨져 있을 가능성 (dead code 7개와 연계).

---

## 종합 판정: **YELLOW**

| 항목 | 점수 | 사유 |
|---|---|---|
| JS 문법 | YELLOW | 2/3 FAIL — null 바이트 오염이 원인. JS 코드 자체는 정상 |
| data-action 커버리지 | GREEN | 84/84 완전 커버 |
| Dead Code | YELLOW | 7개 미호출 함수 존재 |
| 코드 품질 | GREEN | console.error 0, TODO 0 |

### 권장 조치 (우선순위 순)

1. **[HIGH] null 바이트 제거** — sqm-inline.js, sqm-onestop-inbound.js 두 파일
   ```python
   # Python 원자적 수정 절차 (CLAUDE.md 규칙 준수)
   with open('sqm-inline.js', 'rb') as f: data = f.read()
   clean = data.split(b'\x00')[0]  # null 이전까지만 유지
   with open('sqm-inline.js', 'wb') as f: f.write(clean)
   # 이후 node --check 재검증 필수
   ```

2. **[MEDIUM] 중복 data-action 의도 확인** — `onIntegrityCheck`, `onSalesOrderDN`
   의도적 중복이면 주석으로 명시, 아니면 하나 제거.

3. **[LOW] Dead function 정리** — 7개 함수 삭제 또는 TODO 주석 추가
   특히 `showPdfInboundUploadModal`은 `onOnPdfInbound`와 관계 확인 필요.
