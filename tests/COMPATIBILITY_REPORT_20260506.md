# Compatibility Report — test_smoke_workflow.py vs Async UI Patches

**Date:** 2026-05-06
**Analyst:** Subagent (compatibility review)
**Subject file:** `D:\program\SQM_inventory\SQM_v866_CLEAN\tests\test_smoke_workflow.py`
**Patches under review (applied in parallel):**
- **P1** — `main_webview.py`: restructure `main()` to use splash window pattern; defer `wait_for_api` to background.
- **P2** — `features/ai/ollama_manager.py`: add async variant of `start_ollama_server` (sync preserved).
- **P3** — `engine_modules/database.py`: add async DB helpers (sync functions UNCHANGED).

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| **Total tests analyzed** | 23 |
| **🟢 NONE (safe)** | 23 |
| **🟡 LOW** | 0 |
| **🟠 MEDIUM** | 0 |
| **🔴 HIGH** | 0 |

### Overall Verdict
**All 23 existing smoke tests are GREEN.** The test file operates entirely against the FastAPI backend (`backend.main:app` via `TestClient`) and against the SQLite DB directly (`sqlite3.connect`). It does **not** import from, invoke, or transitively depend on:
- `main_webview.py` (P1)
- `features/ai/ollama_manager.py` (P2)
- `engine_modules/database.py` (P3) — verified by code inspection (test uses raw `sqlite3` only)

The patches modify desktop-shell startup behavior (splash → background API wait) and add **additive-only** async variants. Since async patches are explicitly additive and sync code paths are preserved, none of the test paths shift.

---

## 2. Static Dependency Analysis

### 2.1 Imports in test_smoke_workflow.py
```python
import io
import sqlite3
import sys
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from backend.main import app
```

### 2.2 Touched-by-patch surfaces
| Patched module | Imported by tests? | Indirectly invoked? |
|---|---|---|
| `main_webview.py` | No | No — tests use `TestClient(app)`, never spawn webview |
| `features/ai/ollama_manager.py` | No | Only if `backend.main` imports it at module load. Even so, P2 is **additive** (new async fn), original sync `start_ollama_server` unchanged |
| `engine_modules/database.py` | No | Tests use raw `sqlite3.connect(DB_PATH)`. Backend endpoints may use it, but P3 leaves sync helpers UNCHANGED |

### 2.3 Behavioral dependencies
- **No** test calls `main_webview.main()`.
- **No** test starts a webview window or waits on `wait_for_api`.
- **No** test calls `start_ollama_server` directly.
- **No** test exercises the DB retry path explicitly.
- All HTTP calls are in-process via `TestClient` (no real port binding → no `kill_zombie_on_port`).

---

## 3. Per-Test Analysis Table

| # | Test | What It Verifies | Risk | Reasoning |
|---|---|---|---|---|
| 1 | `TestStep0_InitialState::test_api_health` | `GET /api/dashboard/stats` returns 200 | 🟢 NONE | TestClient in-process; unaffected by webview/splash refactor |
| 2 | `TestStep0_InitialState::test_all_available` | All tonbags AVAILABLE on Day 0 | 🟢 NONE | Pure SQL read via raw sqlite3 |
| 3 | `TestStep0_InitialState::test_no_duplicate_sublot` | No duplicate (lot_no, sub_lt) | 🟢 NONE | Pure SQL read |
| 4 | `TestStep0_InitialState::test_weight_integrity` | header weight == tonbag sum | 🟢 NONE | Pure SQL read |
| 5 | `TestStep0_InitialState::test_sample_bags_present` | One sample bag per LOT | 🟢 NONE | Pure SQL read |
| 6 | `TestStep1_Allocation::test_allocation_upload` | Excel POST → `/api/allocation/bulk-import-excel` | 🟢 NONE | Backend endpoint; no patched code path |
| 7 | `TestStep1_Allocation::test_reserved_count_increased` | RESERVED count > 0 after `apply-approved` | 🟢 NONE | Backend endpoint + SQL read |
| 8 | `TestStep1_Allocation::test_no_duplicate_after_alloc` | No dup post-alloc | 🟢 NONE | Pure SQL read |
| 9 | `TestStep1_Allocation::test_total_tonbag_count_unchanged` | Total = LOTs × 11 | 🟢 NONE | Pure SQL read |
| 10 | `TestStep2_Picking::test_pick_half_of_reserved` | RESERVED → PICKED via `/pick` | 🟢 NONE | Backend endpoint |
| 11 | `TestStep2_Picking::test_picked_count` | PICKED count > 0 | 🟢 NONE | Pure SQL read |
| 12 | `TestStep2_Picking::test_integrity_after_pick` | Total tonbag count unchanged | 🟢 NONE | Pure SQL read |
| 13 | `TestStep3_Outbound::test_confirm_picked_lots` | PICKED → SOLD via `/confirm` | 🟢 NONE | Backend endpoint |
| 14 | `TestStep3_Outbound::test_sold_appears` | SOLD > 0 | 🟢 NONE | Pure SQL read |
| 15 | `TestStep3_Outbound::test_weight_balance_after_outbound` | Active weight > 0 | 🟢 NONE | Pure SQL read |
| 16 | `TestStep4_Return::test_mark_return` | SOLD → RETURN via direct SQL UPDATE | 🟢 NONE | Direct sqlite3 write |
| 17 | `TestStep4_Return::test_return_count` | RETURN > 0 | 🟢 NONE | Pure SQL read |
| 18 | `TestStep4_Return::test_no_duplicate_on_return` | No dup post-return | 🟢 NONE | Pure SQL read |
| 19 | `TestStep5_MoveAndReAvailable::test_return_to_available` | RETURN → AVAILABLE via `/api/inventory/adjust` | 🟢 NONE | Backend endpoint |
| 20 | `TestStep5_MoveAndReAvailable::test_move_location` | Location move via `/api/action2/inventory-move` | 🟢 NONE | Backend endpoint |
| 21 | `TestStep5_MoveAndReAvailable::test_final_state_table` | Final total tonbag = LOTs × 11 | 🟢 NONE | Pure SQL read |
| 22 | `TestStep5_MoveAndReAvailable::test_no_final_duplicate` | Final no dup | 🟢 NONE | Pure SQL read |
| 23 | `TestStep5_MoveAndReAvailable::test_moved_location_recorded` | stock_movement has MOVE rows | 🟢 NONE | Pure SQL read |

> Note: 23 individual test methods across 6 test classes, all 🟢 NONE.

---

## 4. Risk Discussion

### 4.1 Why P1 (main_webview splash) is invisible to tests
Tests boot FastAPI through `TestClient(app)` directly. The desktop entrypoint `main_webview.main()` is never executed. The splash refactor cannot affect import-time behavior of `backend.main` either (those modules are independent).

### 4.2 Why P2 (async ollama) is invisible to tests
- No test calls `start_ollama_server` (sync or async).
- The new async variant is additive; the sync function signature/behavior is preserved.
- If `backend.main` imports `ollama_manager` at module load (for AI features), it imports symbols, not invocations — adding a new async function does not break import.

### 4.3 Why P3 (async DB helpers) is invisible to tests
- Sync DB helpers in `engine_modules/database.py` are explicitly **UNCHANGED**.
- Tests use raw `sqlite3.connect(DB_PATH)` — they bypass the helpers entirely.
- Backend endpoints continue using sync helpers; behavior preserved.

### 4.4 What COULD theoretically affect tests (and doesn't)
| Hypothetical issue | Actual status |
|---|---|
| Splash defers DB init → tests see empty DB | Not applicable: tests don't run splash; DB is pre-populated yesterday |
| Async DB helper accidentally replaces sync version | Out of scope per patch contract (P3 says sync UNCHANGED) |
| Module-load side-effects in patched files | Patches are restructuring/additive; no new top-level side effects expected |
| `wait_for_api` race shifts API readiness | TestClient runs in-process; no port wait |

---

## 5. Recommendations

### 5.1 Tests safe to ignore post-patch
**All 23 tests.** No follow-up needed for the existing smoke suite.

### 5.2 Verify after patch lands (low-effort sanity checks)
1. Run `pytest tests/test_smoke_workflow.py -v` once after each patch is merged. Expect identical pass/fail signature as yesterday.
2. Confirm `from backend.main import app` still succeeds (smoke import test).
3. If `backend.main` does import `ollama_manager` or `engine_modules.database` at module load, do a quick `python -c "from backend.main import app"` to catch import-time regressions.

### 5.3 Suggested ADDITIONAL smoke tests (gap coverage)
The current suite covers backend-only flow. The patches introduce desktop-UI behavior that is **uncovered**. Consider adding a separate file (do **not** modify `test_smoke_workflow.py`):

**Proposed file:** `tests/test_smoke_async_startup.py`

Suggested cases:
1. `test_main_webview_imports_cleanly` — `import main_webview` does not raise; verifies splash refactor didn't break module load.
2. `test_ollama_manager_async_signature` — `inspect.iscoroutinefunction(ollama_manager.start_ollama_server_async)` is True; sync `start_ollama_server` still callable.
3. `test_database_async_helpers_present` — `engine_modules.database` exposes the new async helpers AND the original sync helpers (regression guard for "did we accidentally remove sync?").
4. `test_wait_for_api_is_non_blocking_in_main` — Static check: `main_webview.main` source contains splash+background pattern (e.g., `threading.Thread` / `asyncio.create_task` referenced). This is a sentinel test against accidental revert.
5. `test_kill_zombie_on_port_still_callable` — Smoke import + signature check, since the patch may relocate it.

These are **additive** and would not affect the existing reverse-audit suite.

### 5.4 What NOT to do
- Do **not** modify `test_smoke_workflow.py` to add async checks. Keep it focused on backend workflow regression.
- Do **not** add `pytest-asyncio` to the smoke run unless a new file specifically needs it.
- Do **not** parametrize over sync vs async in workflow tests — workflow logic is sync HTTP only.

---

## 6. Conclusion

The yesterday's reverse-comprehensive-audit smoke suite is **fully insulated** from the three planned async UI thread patches. All 23 tests are 🟢 NONE risk. No code modifications to `test_smoke_workflow.py` are required or recommended. Gap coverage for the new async startup paths should live in a separate, additive test file.

---
*Report generated 2026-05-06 by compatibility analysis subagent.*
