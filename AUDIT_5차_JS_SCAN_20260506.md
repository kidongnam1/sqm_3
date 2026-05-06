# SQM Frontend JS — 5차 Re-Entry Guard Audit
**Date:** 2026-05-06  **Auditor:** Claude (subagent)
**Trigger:** 3차 audit found `console.error` recursion bug in `main_webview.py` embedded JS. This scan checks all loaded SQM frontend JS files for the same class of pywebview `loaded`-event re-entry hazards.

---

## 1. Verdict: NO `__SQM_*_INSTALLED__` GUARDS EXIST ANYWHERE

`grep -r "__SQM_.*_INSTALLED__" frontend/js/` → **0 matches**.
Every file relies on top-level IIFE execution being one-shot. Under pywebview, `loaded` fires on every navigation/reload — these IIFEs can re-run.

---

## 2. Per-File Pattern Table

| File | Top-level IIFE | doc/window addEventListener | window.X = ... assigns | Function-wrap recursion risk | Has guard? | Severity |
|---|---|---|---|---|---|---|
| sqm-core.js | line 6 | 14 (lines 50,120,126,131,135,136,137,320,400,466,530,581,582,974,1039) | 28 | NO (clean function decls) | NONE | **HIGH** |
| sqm-inventory.js | line 2 | 0 | 12 | NO (local alias only) | NONE | MEDIUM |
| sqm-allocation.js | line 2 | 1 (line 644, conditional) | 28 | NO (local alias only) | NONE | MEDIUM |
| sqm-picked.js | line 2 | 0 | 3 | NO (local alias only) | NONE | LOW |
| sqm-logistics.js | line 2 | 0 | 16 | NO (local alias only) | NONE | LOW |
| sqm-tonbag.js | line 2 | 6 (lines 91,96,110,121,4266,4294,4409,4440) + setInterval@4414 | 83 | NO (local alias only) | NONE | **HIGH** |
| sqm-onestop-inbound.js | line 10 | 4 (lines 1319,1324,1377,1382) | 35 | NO | NONE | MEDIUM |
| sqm-inline.js | line 6 | 16 (50,120-137,320,400,466,530,580,581,1925,2664,2669,2683,2694,6855,6883,6997,7032) + setInterval@7002 | 131 | NO (local alias only) | NONE | **CRITICAL** |

**Note on the wrap pattern (`var X = function(){ return window.X.apply(...) }`):** present in 6 satellite files, ~70 occurrences total. These are *local IIFE-scoped aliases to window globals*, not the self-referential recursion bug from `main_webview.py`. They will **not** infinitely recurse. They will, however, be redefined every time the IIFE re-runs (harmless except for memory churn).

---

## 3. HIGH-Severity Findings

### H1. sqm-inline.js — re-entrant IIFE installs ~16 listeners + persistent setInterval each load
File: `D:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js`
Top-level IIFE at line 6 has no guard. Each pywebview `loaded` re-execution duplicates:
- All 16 `document.addEventListener` / `window.addEventListener` registrations
- A 30-second `setInterval` (line 7002) — never cleared
- The `boot()` call (line 7032/7034) — runs `renderPage` again

```js
// line 7002 — accumulates a new 30s interval per page reload
setInterval(function(){
  var auto = document.getElementById('sb-auto-refresh');
  if (auto && auto.checked && document.visibilityState !== 'hidden') {
    loadAlerts(); refreshStatusbar();
    if (_currentRoute==='dashboard') loadKpi();
  }
}, 30000);
```
**Fix:** wrap entire IIFE body with `if (window.__SQM_INLINE_INSTALLED__) return; window.__SQM_INLINE_INSTALLED__ = true;` and clear `_kpiTimer` / `_sidebarBadgeTimer` / new local `_autoRefreshTimer` before recreating.

### H2. sqm-core.js — 14 unguarded global key/click/mouse listeners
File: `D:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-core.js`
Lines 120,126,131,135,136,137,320,400,466,530,581,582,1039 register global handlers (mouseover, mouseout, mousemove, mousedown, click x3, keydown x4, contextmenu) with no guard. Each `loaded` event piles on duplicates → ESC/Enter/contextmenu fire 2x, 3x... after each navigation.
Plus `setInterval` at lines 1006, 1011 inside `startKpiPolling()` already self-clears (`if (_kpiTimer) clearInterval`) — those two are safe.
**Fix:** guard the IIFE (line 6) the same way.

### H3. sqm-tonbag.js — 6 listeners + uncleared setInterval
File: `D:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-tonbag.js`
Same shape as sqm-inline.js: bare IIFE, document/window listeners (lines 91,96,110,121,4266,4294,4409,4440), unguarded `setInterval` at 4414, and a `boot()` call at 4444.

---

## 4. MEDIUM/LOW Findings

- **sqm-onestop-inbound.js** — 4 mousemove/mouseup listeners (drag handlers, lines 1319–1382). Will accumulate, dragging gets multi-fired.
- **sqm-allocation.js** — `setTimeout(..., function(){ document.addEventListener('click', closeHandler); }, 10)` on line 644 — only fires when a popup is opened, lower priority but the closeHandler is anonymous so cannot easily be removed.
- **sqm-inline.js line 1925** + **sqm-tonbag.js line 1925-equivalent** — same pattern.
- **All 8 satellite IIFEs** redefine ~70 local `var X = function(){ window.X.apply(...) }` aliases each load — harmless functionally, but noise.

---

## 5. Summary Counts

| Metric | Count |
|---|---|
| Top-level IIFEs (sqm-*.js) | 8 |
| Global listeners (window/document.addEventListener) | ~41 in sqm-*.js (excluding .bak/.pre_parity_patch) |
| Function-wrap aliases (local, non-recursive) | ~70 |
| `window.X = ...` global assignments | 336 across 8 files |
| `setInterval` calls without explicit clear | 3 (sqm-core ×0 — has clear; sqm-inline:7002; sqm-tonbag:4414; sqm-inline:852 — has clear) |
| **Files WITH `__SQM_*_INSTALLED__` guard** | **0** |
| **Files WITHOUT guard** | **8 / 8** |

---

## 6. Recommended Patch Priority

1. **sqm-inline.js** (CRITICAL, first) — largest blast radius: 16 listeners, persistent setInterval, full app boot sequence runs again. This file alone causes the most observable misbehavior on second load.
2. **sqm-core.js** (HIGH) — every other file depends on its globals; ESC/keydown/contextmenu/click handlers all get duplicated.
3. **sqm-tonbag.js** (HIGH) — second `setInterval` accumulator; mirror of sqm-inline issues.
4. **sqm-onestop-inbound.js** (MEDIUM) — drag handlers.
5. **sqm-allocation.js / inventory.js / picked.js / logistics.js** (LOW) — no listener accumulation; only IIFE-internal alias re-definition. Patch with the standard guard but lowest urgency.

---

## 7. Standard Guard Template (per request)

```js
/* at very top of each IIFE body, immediately after 'use strict'; */
if (window.__SQM_<COMPONENT>_INSTALLED__) {
  console.warn('[SQM] <component> IIFE re-entry blocked');
  return;
}
window.__SQM_<COMPONENT>_INSTALLED__ = true;
```

Where `<COMPONENT>` ∈ `INLINE | CORE | TONBAG | ONESTOP | ALLOC | INV | PICKED | LOGISTICS`.

---
*No JS file was modified by this scan — read-only audit per instructions.*
