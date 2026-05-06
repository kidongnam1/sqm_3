# 4차 P1 Fix Verification — `main_webview.py` JS Error Bridge Guard

**Date:** 2026-05-06
**Auditor:** 4차 (4th-pass)
**Target:** `main_webview.py` lines 429–492 (3차 fix verification)

---

## Verdict: 🟢 GREEN — 3차 fix is correct, no new issues

---

## Verification of 3차 fix correctness

Confirmed by reading lines 420–492:

| Check | Result |
|---|---|
| Guard placed **inside** IIFE (line 438, after `(function installErrorBridge() {{`) | ✅ PASS |
| Flag set **immediately** (line 442) **before** `report()` def, `addEventListener` calls, and `console.error` wrap (lines 444–489) | ✅ PASS |
| Early `return` (line 440) prevents ALL re-installation including the `console.error` re-wrap (the actual recursion source) | ✅ PASS |
| `console.log` skip message uses `console.log`, NOT `console.error` — does not feed into the bridge it just skipped | ✅ PASS |
| Namespacing `__SQM_*__` (double-underscore + project prefix + ALL_CAPS) is collision-safe | ✅ PASS |

The fix targets the exact failure mode (cumulative `console.error` wrapping on repeated `on_loaded`).

---

## New issues introduced by 3차 fix

**None of material concern.** Edge cases evaluated:

1. **Foreign script setting `window.__SQM_BRIDGE_INSTALLED__` first** — extremely unlikely (project-prefixed flag, app loads its own pages); worst case is silent no-install of bridge, which is degraded but not broken. Acceptable.
2. **SPA hard reload / page navigation** — pywebview's `on_loaded` re-fires and `window` is fresh per document; the flag resets naturally with the new global object. The guard works *per document*, which is the correct scope.
3. **Flag set but listener registration throws mid-IIFE** — theoretical inconsistent state (flag=true, only `error` listener registered, no `unhandledrejection`, no `console.error` wrap). However, `addEventListener` and assignment to `console.error` cannot throw under normal conditions. Risk: negligible.

---

## Cross-script analysis

Searched `frontend/` for competing handlers:

```
Grep: addEventListener\s*\(\s*["'](error|unhandledrejection)  →  No matches in frontend/**
```

→ No double-registration risk. The bridge in `main_webview.py` is the **sole** global `error` / `unhandledrejection` handler in the codebase. Guard scope is sufficient.

---

## Recommendation

Ship as-is. No further action required for this defect class.

— End of 4차 audit —
