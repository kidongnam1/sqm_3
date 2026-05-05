# v866 웹 테이블 가운데 정렬 문제와 해결 작업

## 1. 문제 요약

프로그램 실행 후 여러 테이블 메뉴에서 데이터가 가운데 정렬되지 않고 있다.

이 문제는 단순히 CSS 한 줄이 빠져서 생긴 문제가 아니라,
각 화면과 모달에서 테이블을 만드는 방식이 서로 다르기 때문에 발생한다.

현재 v866 웹에는 다음처럼 여러 종류의 테이블 렌더링 방식이 섞여 있다.

- 공통 `.data-table` 클래스를 쓰는 테이블
- `.data-table` 없이 직접 만든 테이블
- JS 문자열 안에서 `<td style="text-align:right">`처럼 인라인 정렬을 넣은 테이블
- 모달 안에서 별도 HTML 문자열로 만든 테이블
- 페이지별로 직접 렌더링하는 Inventory, Allocation, Picked, Outbound, Return 등의 테이블
- 웹 CSS와 무관한 Tk GUI `Treeview` 테이블

따라서 `.data-table td { text-align: center; }` 같은 CSS만 추가해도 모든 화면에 적용되지 않는다.

## 2. 현재 가운데 정렬이 안 되는 이유

핵심 이유는 테이블 정렬 규칙이 통일되어 있지 않기 때문이다.

대표 원인은 다음과 같다.

- 일부 테이블에는 `.data-table` 클래스가 없다.
- 일부 셀은 `style="text-align:left"` 또는 `style="text-align:right"`를 직접 가진다.
- 일부 숫자 컬럼은 JS 렌더링 코드에서 오른쪽 정렬을 강제한다.
- 일부 모달은 공통 테이블 컴포넌트를 쓰지 않고 HTML 문자열을 직접 만든다.
- 같은 `.data-table`이라도 인라인 스타일이 있으면 CSS와 충돌한다.
- Tk GUI 테이블은 웹 CSS로 제어할 수 없다.

즉, 현재 문제는 "CSS가 약해서"라기보다 "테이블 생성 방식이 분산되어 있어서" 생긴 문제다.

## 3. 해결 방향

해결하려면 테이블 정렬 정책을 하나로 정하고,
모든 웹 테이블 생성 코드를 그 정책에 맞게 정리해야 한다.

권장 정책은 다음과 같다.

- 기본값: 모든 `th`, `td`는 가운데 정렬
- 긴 텍스트 컬럼: 왼쪽 정렬 허용
- 수량, 중량, 금액 같은 숫자 컬럼: 필요 시 오른쪽 정렬 또는 가운데 정렬 중 하나로 통일
- 예외 정렬은 인라인 스타일이 아니라 CSS class로만 처리

## 4. 필요한 작업

### 4.1 공통 CSS 정리

공통 테이블 CSS를 명확하게 만든다.

예:

```css
.data-table th,
.data-table td {
  text-align: center;
  vertical-align: middle;
}

.data-table .cell-left {
  text-align: left;
}

.data-table .cell-right,
.data-table .cell-num {
  text-align: right;
}

.data-table .cell-center {
  text-align: center;
}
```

### 4.2 모든 웹 테이블에 `.data-table` 부여

JS에서 테이블을 만들 때 가능한 한 모두 아래 형태를 사용하게 한다.

```html
<table class="data-table">
```

`.data-table`이 없는 테이블은 공통 CSS가 적용되지 않으므로 누락 화면이 계속 생긴다.

### 4.3 인라인 정렬 제거

JS 문자열 안의 다음 패턴을 정리해야 한다.

```html
<td style="text-align:left">
<td style="text-align:right">
<td style="text-align:center">
<th style="text-align:right">
```

이런 코드는 CSS보다 우선하거나 CSS와 충돌한다.

권장 변경:

```html
<td class="cell-left">
<td class="cell-right">
<td class="cell-center">
<td class="cell-num">
```

### 4.4 화면별 점검

아래 화면을 각각 확인해야 한다.

- Inventory
- Allocation
- Picked
- Outbound
- Return
- Move
- Dashboard
- Log
- Scan
- 제품/품목 관련 모달
- LOT 상세 모달
- Allocation 승인/이력 모달
- 보고서/정합성/DB 정보 모달

### 4.5 예외 컬럼 정의

모든 셀을 무조건 가운데 정렬하면 오히려 보기 나쁜 컬럼도 있다.

예외 후보:

- LOT NO: 가운데 또는 고정폭
- 제품명/Product: 왼쪽 정렬 가능
- 고객명/SOLD TO: 왼쪽 정렬 가능
- 비고/Remark: 왼쪽 정렬 가능
- 중량/수량/금액: 오른쪽 정렬 또는 가운데 정렬 중 정책 선택 필요

이 예외는 인라인 스타일이 아니라 class로 관리해야 한다.

## 5. 작업 방식

이 작업은 단순 CSS 수정이 아니다.

다음 두 영역을 같이 건드려야 한다.

- `frontend/css/v864-layout.css`
- `frontend/js/sqm-inline.js`

필요하면 다음 파일들도 확인해야 한다.

- `frontend/index.html`
- `frontend/js/pages/*.js`
- `frontend/js/handlers/*.js`

## 6. 서브 에이전트 팀이 필요한가?

이 작업은 범위가 넓다.

특히 `frontend/js/sqm-inline.js` 안에 테이블 HTML 문자열이 많이 들어 있고,
화면별로 정렬 방식이 제각각일 수 있다.

따라서 "정말 모든 테이블을 빠짐없이 정리"하려면 서브 에이전트 팀을 쓰는 것이 좋다.

권장 방식:

- 단일 작업자: 빠른 1차 정리 가능
- 서브 에이전트 팀: 누락 화면까지 잡는 철저한 정리에 적합

## 7. 권장 서브 에이전트 분담

서브 에이전트를 쓴다면 3명 정도가 적당하다.

### 담당 1: Inventory / Allocation / Picked / Outbound

담당 범위:

- 재고 관련 메인 화면
- Allocation 화면
- Picked 화면
- Outbound 화면
- 주요 대형 테이블

목표:

- `.data-table` 누락 확인
- 인라인 `text-align` 제거
- 숫자/텍스트 컬럼 class 정리

### 담당 2: Return / Move / Log / Scan / Dashboard

담당 범위:

- Return 화면
- Move 화면
- Log 화면
- Scan 화면
- Dashboard 내부 테이블

목표:

- 메인 탭 테이블 정렬 통일
- 작은 표, 상태 표, 이력 표까지 확인

### 담당 3: 모달 / 보고서 / 상세 팝업

담당 범위:

- LOT 상세 모달
- 제품/품목 모달
- Allocation 승인/이력 모달
- 보고서 모달
- 정합성/DB/설정 관련 모달

목표:

- 모달 안의 직접 HTML 테이블 정리
- 공통 class 적용
- 예외 컬럼 class 적용

## 8. 단일 작업으로 할 경우

단일 작업으로도 가능하다.

다만 이 경우에는 한 번에 완벽하게 모든 화면을 잡기보다,
아래 순서로 진행하는 것이 안전하다.

1. 공통 CSS class 정의
2. `sqm-inline.js`의 주요 테이블부터 정리
3. Inventory, Allocation, Outbound 화면 우선 확인
4. 모달 테이블 정리
5. 남은 화면을 검색 기반으로 추가 정리

단일 작업은 빠르지만 누락 가능성이 있다.

## 9. 결론

이 문제를 제대로 해결하려면 "모든 테이블은 공통 클래스와 공통 정렬 정책을 따른다"는 원칙으로 정리해야 한다.

단순히 CSS만 고치면 일부 화면에는 적용되지만,
JS 안에 인라인 정렬이 남아 있거나 `.data-table`이 빠진 화면은 계속 어긋난다.

따라서 철저하게 하려면 서브 에이전트 3명 정도로 나누는 방식이 가장 안전하고,
빠른 1차 개선만 목표라면 단일 작업으로도 가능하다.
