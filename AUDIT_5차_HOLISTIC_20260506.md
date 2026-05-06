# AUDIT 5차 — Holistic System Integration Review (2026-05-06)

## System-level integration verdict: 🟡 (yellow — ship-able, with caveats)

P1+P2+P3 compose cleanly: no shared-state collisions, no import-time
side-effect ordering hazards. main_webview.py does NOT import database.py
or ollama_manager.py at the top level — both are pulled in lazily by
backend.api inside `_setup_backend`'s background thread, so the
ThreadPoolExecutor in database.py is created off the main thread, after
the splash window is already live. Good.

Yellow because: (a) `_db_executor` is a module-level singleton that
spawns only on first `import database`, but if any test imports it
without ever shutting down, atexit will fire on test teardown — fine,
but worth noting. (b) The 3-state phase machine in main_webview is
correct but fragile — a 4th `on_loaded` (e.g. user clicks an internal
link that triggers a full reload) will hit the `main` branch and the
idempotency guard alone keeps it safe.

## Thread budget analysis (peak)

| Thread | Count | Origin |
|---|---|---|
| Main (webview UI loop) | 1 | main_webview.main() |
| sqm-backend-bootstrap | 1 | P1 daemon |
| uvicorn server + workers | 1–3 | uvicorn default loop + h11 |
| on_window_started (webview internal) | 1 | webview.start() callback |
| sqm-db- pool | 4 | P3 ThreadPoolExecutor |
| ollama-start-async (on demand) | 0–1 | P2 |
| FastAPI request handler threads | up to ~40 | uvicorn anyio default |

**Peak realistic: ~10–12 threads idle, ~50 under load.** Well within
Windows limits. No conflict between `_db_executor` (4 workers) and
uvicorn's anyio threadpool — they run independent SQLite connections via
thread-local in `database.py:conn`. No budget concern.

## Logging adequacy

- `wait_for_api` success: logs the URL that responded — sufficient.
- 9s success: only the success log, no timing — **gap**: cannot tell
  from logs whether startup was fast or slow.
- timeout: logs `WARN` then `ERROR` then drives `phase=error`. Good.
- Silent failure scan: `urllib.request.urlopen(... ).catch(function(_){})` 
  in the JS bridge swallows fetch errors — by design (avoids recursion)
  but means lost error reports are invisible. ollama_manager
  `start_ollama_server` swallows return-False on `(OSError, ValueError)`
  with a warning — acceptable.
- No log line marks transitions splash→main or main→error in
  on_window_started other than the navigate log.

## Documentation gaps

- `_phase` 3-state values (`splash`/`main`/`error`) are documented in
  the comment block at line 405–408. **Adequate.**
- Idempotency guard rationale (line 436–442) explicitly cites the
  recursion bug. **Excellent.**
- `_db_executor` module-level lifetime is **not** documented — a new
  developer cannot tell from comments that the 4 worker threads live
  for the entire process. atexit registration is mentioned but not
  *why* `wait=False` was chosen.
- `db_execute_async` docstring does not warn that `on_done` runs on the
  worker thread, not the UI thread (the ollama_manager docstring DOES
  warn). Inconsistent.

## Test coverage gaps

Q1 covers HTTP smoke only. Untested:

1. **3-state phase transitions** — mock `webview.Window` and assert
   `on_loaded` does the right thing in each phase.
2. **JS bridge idempotency guard** — call `on_loaded` twice with
   `_phase[0]="main"`; verify `evaluate_js` is invoked twice but the
   resulting JS would set `__SQM_BRIDGE_INSTALLED__` only once
   (integration test inside a real webview, or a JS-only unit test).
3. **Ollama async callback marshalling** — call
   `start_ollama_server_async` with a mock `on_done`, assert it's
   invoked exactly once with a bool, on a non-main thread.
4. **db_execute_async future delivery** — submit a task that raises;
   verify both `fut.exception()` and `on_done(exc)` receive it.
5. **db_execute_async on_done failure** — verify a raising `on_done`
   does not crash the worker (logger.exception path).
6. **wait_for_api fallback** — backend exposes only `/` not
   `/api/health`; verify the second probe URL succeeds.

## Top 3 recommendations

1. **Add a single timing log** in `wait_for_api`: capture
   `start = time.time()` at entry and log `f"API ready in {elapsed:.2f}s"`
   so production logs distinguish 0.5s from 9s startups.
2. **Document `_db_executor` lifetime** with one comment block above
   line 865 explaining: module-level singleton, 4 threads alive for
   process lifetime, `wait=False` chosen because workers may be in
   sqlite retry loops at shutdown.
3. **Add a thread-marshalling note** to `db_execute_async` docstring
   matching the one in `start_ollama_server_async` — for pywebview
   callers, `on_done` runs on a worker thread; UI mutations need
   `window.evaluate_js(...)` (which IS thread-safe).
