# SQM JS Re-entry Guard 표준 패턴

**작성:** 2026-05-06 (수) — Ruby (Senior Architect) — 3차 검증에서 발견된 JS 브릿지 재귀 버그를 계기로 표준화.

---

## 🚨 적용 대상 (Trigger)

다음 패턴이 보이면 반드시 idempotency guard 적용:

1. **함수 wrapping**: `var _orig = something; something = function() { ... return _orig.apply(...); }` 류
2. **DOM 이벤트 리스너 등록**: `window.addEventListener("xxx", handler)` — 같은 이벤트에 같은 핸들러 누적 등록
3. **글로벌 객체 변경**: `window.foo = bar` 류
4. **CSS / style 주입**: `document.head.appendChild(<style>)`
5. **IIFE 내부 setup 로직** — pywebview/Electron 의 `loaded` 이벤트는 SPA 라우팅·load_url·페이지 새로고침 시 **여러 번 발화** 가능

---

## 📋 표준 패턴 (Boilerplate)

### Pattern A — 단일 가드 (간단)

```javascript
(function setupSomething() {
    if (window.__SQM_<COMPONENT>_INSTALLED__) {
        console.log("[SQM] <Component> already installed — skip");
        return;
    }
    window.__SQM_<COMPONENT>_INSTALLED__ = true;

    // ... actual setup code ...
})();
```

**플레이스홀더**:
- `<COMPONENT>` = 대문자 영문 (예: `BRIDGE`, `KEYBOARD_SHORTCUTS`, `THEME_LISTENER`)

**예시 (실제 적용된 코드, main_webview.py:432)**:
```javascript
(function installErrorBridge() {
    if (window.__SQM_BRIDGE_INSTALLED__) {
        console.log("[SQM] Error bridge already installed — skip");
        return;
    }
    window.__SQM_BRIDGE_INSTALLED__ = true;

    // ... bridge install code ...
})();
```

### Pattern B — 버전 체크 (개선 가능 시 재설치)

```javascript
(function setupSomething() {
    var REQUIRED_VERSION = 2;  // 버전 올리면 강제 재설치
    if (window.__SQM_<COMPONENT>_VERSION__ === REQUIRED_VERSION) {
        return;  // 이미 최신
    }
    // 이전 버전 cleanup
    if (typeof window.__SQM_<COMPONENT>_CLEANUP__ === "function") {
        try { window.__SQM_<COMPONENT>_CLEANUP__(); } catch(_) {}
    }
    window.__SQM_<COMPONENT>_VERSION__ = REQUIRED_VERSION;

    // ... setup code ...

    // cleanup function for future re-installation
    window.__SQM_<COMPONENT>_CLEANUP__ = function() { /* unwire */ };
})();
```

### Pattern C — 핸들러 누적 방지

```javascript
(function setupListeners() {
    if (window.__SQM_<COMPONENT>_HANDLERS__) {
        return;
    }
    var handlers = {
        click: function(e) { /* ... */ },
        keydown: function(e) { /* ... */ }
    };
    window.__SQM_<COMPONENT>_HANDLERS__ = handlers;

    document.addEventListener("click", handlers.click);
    document.addEventListener("keydown", handlers.keydown);
})();
```

---

## 🚫 절대 금지 안티 패턴

```javascript
// ❌ BAD — wrap 누적 → 재귀
var _origErr = console.error;
console.error = function() {
    return _origErr.apply(console, arguments);
};

// ❌ BAD — 핸들러 무한 누적
window.addEventListener("error", function(e) { ... });

// ❌ BAD — 동일 효과 다중 적용 (IIFE 안에 가드 없으면 매번 setup)
(function() { setupX(); })();
```

---

## ✅ 코드 리뷰 체크리스트

JS 브릿지/스크립트 PR 리뷰 시 다음 확인:

- [ ] `window.__SQM_*_INSTALLED__` 또는 동등한 가드 존재
- [ ] 가드 미통과 시 `console.log(... already installed — skip)` 로 가시성 확보
- [ ] 가드 통과 후 즉시 플래그 set (race condition 방지)
- [ ] 핸들러/리스너는 누적 없이 등록 보장
- [ ] 함수 wrapping 시 한 번만 wrap 보장

---

## 📚 적용 이력

| 날짜 | 위치 | 사유 |
|---|---|---|
| 2026-05-06 | `main_webview.py:432` (JS 에러 브릿지) | 3차 감사에서 console.error 무한 재귀 버그 발견 — `__SQM_BRIDGE_INSTALLED__` 가드 추가 |

---

## 🔍 SQM 다른 JS 위치 검토 권장

다음 위치에 동일 패턴 적용 검토 필요 (다음 세션):
- `frontend/js/sqm-core.js` — 글로벌 초기화 로직 검토
- `frontend/js/sqm-inline.js` — 인라인 스크립트 검토
- 모든 `addEventListener` 호출 지점 — 누적 등록 가능성

검색 명령:
```powershell
cd D:\program\SQM_inventory\SQM_v866_CLEAN\frontend
findstr /S /N /R "addEventListener\|console\.error\s*=" js\*.js
```

---

*Ruby (Senior Software Architect) — JS 재진입 가드 표준 패턴 — 2026-05-06.*
