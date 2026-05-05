# 메뉴 마우스 Hover 색상 반전 로직 정리

## 1. 사용자가 말한 문제

상단 메인 메뉴에서 하위 메뉴를 한 번 클릭한 뒤 마우스를 위아래로 움직이면,
실제로 마우스가 올라간 메뉴의 하위 메뉴는 열리지만 색상 반전은 처음 클릭했던 메뉴에 남아 있어 헷갈릴 수 있었다.

즉, 메뉴 표시 상태와 색상 강조 상태가 서로 다르게 보이는 문제가 있었다.

## 2. 현재 수정된 적용 범위

이번에 수정한 로직은 상단 메인 메뉴의 하위 메뉴에 공통 적용된다.

적용 대상 구조는 다음과 같다.

- `.menu-btn`
- `.menu-dropdown`
- `.submenu-parent`
- `.submenu-parent-btn`
- `.submenu-dropdown`

따라서 아래 상단 메뉴 안의 오른쪽으로 펼쳐지는 하위 메뉴들은 공통으로 영향을 받는다.

- 파일
- 입고
- 출고
- 재고
- 보고서
- 설정/도구
- 도움말

예를 들면 다음 메뉴들이 해당된다.

- 백업
- 내보내기
- 신규 입고
- D/O
- 정합성
- Allocation
- PICKING LIST
- 제품 관리
- DB

## 3. 수정된 동작

마우스가 하위 메뉴 항목 위로 이동하면 해당 항목이 현재 hover 대상으로 지정된다.

이때 이전에 클릭되어 남아 있던 하위 메뉴의 강조 상태는 제거되고,
현재 마우스가 올라간 하위 메뉴에 색상 반전이 적용된다.

따라서 화면에서는 다음처럼 보이게 된다.

- 마우스가 올라간 하위 메뉴가 즉시 강조된다.
- 이전에 클릭했던 하위 메뉴의 색상 반전은 남지 않는다.
- 오른쪽으로 열리는 하위 메뉴와 왼쪽 부모 메뉴의 강조 색상이 서로 맞게 움직인다.

## 4. 수정된 파일

상단 메인 메뉴의 하위 메뉴 hover 동기화는 아래 파일에 반영되어 있다.

- `frontend/js/sqm-inline.js`
- `frontend/css/v864-layout.css`

## 5. 사이드바 메뉴는 별도 구조

왼쪽 사이드바 메뉴는 상단 메인 메뉴와 구조가 다르다.

상단 메뉴는 다음 구조를 사용한다.

- `.menu-btn`
- `.menu-dropdown`
- `.submenu-parent`
- `.submenu-dropdown`

반면 사이드바는 다음 구조를 사용한다.

- `.side-btn`

현재 사이드바 메뉴는 `Inventory`, `Allocation`, `Picked`, `Outbound`, `Return`, `Move`, `Dashboard`, `Log`, `Scan`처럼 단일 버튼 구조이며,
상단 메뉴처럼 오른쪽으로 펼쳐지는 하위 메뉴 구조가 아니다.

그래서 이번 상단 메뉴 하위 메뉴 hover 동기화 로직은 사이드바에는 직접 적용되지 않는다.

## 6. 사이드바에도 hover 시 active 색상처럼 반전하려면

사이드바에도 마우스를 올렸을 때 현재 선택된 active 메뉴처럼 색상이 반전되게 만들 수 있다.

필요한 변경은 CSS 중심이다.

예상 규칙은 다음과 같은 방향이다.

```css
.side-btn:hover {
  background: var(--sidebar-active-bg);
  color: var(--sidebar-active-fg);
}
```

이렇게 하면 마우스를 올린 사이드바 버튼도 active 메뉴와 같은 색상으로 반전된다.

단, 현재 선택된 페이지를 나타내는 `.side-btn.active` 상태와 마우스 hover 상태가 시각적으로 같아지므로,
사용자는 "현재 선택된 메뉴"와 "마우스가 올라간 메뉴"를 색상만으로는 구분하기 어려울 수 있다.

이를 피하려면 다음처럼 active와 hover를 약간 다르게 줄 수도 있다.

```css
.side-btn:hover {
  background: var(--btn-hover);
  color: var(--sidebar-fg);
}

.side-btn.active {
  background: var(--sidebar-active-bg);
  color: var(--sidebar-active-fg);
}
```

정리하면 선택지는 두 가지다.

- hover도 active와 완전히 같은 색으로 반전
- hover는 약하게 강조하고, active만 강한 색으로 유지

사용자가 원하는 "사이드바에도 hover 시 active 색상처럼 반전"은 첫 번째 방식이다.

## 7. 반영 방식

상단 메인 메뉴 하위 메뉴 문제는 이미 수정되어 있다.

사이드바 hover 색상까지 동일하게 맞추려면 `frontend/css/v864-layout.css`에서 `.side-btn:hover` 규칙을 active 색상 기준으로 바꾸면 된다.

이 변경은 CSS 변경이므로 보통 프로그램 전체 재시작 없이 화면 새로고침 `F5`로 반영될 수 있다.
다만 캐시나 WebView 상태 때문에 바로 보이지 않으면 프로그램을 닫았다가 다시 열면 확실하게 반영된다.
