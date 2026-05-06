# SQM v8.6.6 4차 Stress-Test Audit

Date: 2026-05-06  Auditor: 4차 scenario auditor  Scope: P1+P2+P3 patched build

---

## Per-scenario analysis

### 1. Rapid double-click (two .exe instances)
- Likelihood: HIGH (warehouse staff routinely double-click).
- Impact: MEDIUM. Both threads call `kill_zombie_on_port` (line 274). Each scans netstat and tries `taskkill` on the OTHER instance's uvicorn — they can mutually murder each other's backends. Surviving instance then `run_api_server` succeeds; loser's uvicorn raises `OSError: [WinError 10048]`, swallowed by `run_api_server` try/except (line 141-142). Loser's `wait_for_api` times out at 10s → loads error_html (line 532). Two windows visible: one working, one error screen.
- Current handling: Partial. Lines 184-186 self-PID guard prevents self-kill, but cross-instance kill is unprotected.
- Recommendation: Add a single-instance mutex (`CreateMutexW("Global\\SQM_v866")`) at top of `main()`; if already held, show "이미 실행 중" dialog and `os._exit(0)`.

### 2. Network slow (8s API start)
- Likelihood: MEDIUM (cold disk, AV scan, DB connection pool warmup).
- Impact: LOW. Splash spinner animates the full 8s — non-frozen UI. User CAN click X (PyWebView splash window is interactive). If closed mid-wait, `webview.start` returns; `os._exit(0)` (line 558) runs. Backend daemon thread killed by interpreter exit.
- Current handling: Adequate.
- Recommendation: Add elapsed-time text under spinner ("3초 경과...") to reduce hang perception. Optional.

### 3. Mid-load splash close
- Likelihood: MEDIUM.
- Impact: LOW. `on_window_started` thread runs `wait_for_api` then `window.load_url(url)`. If window destroyed first, `load_url` raises — caught by outer try/except (line 550). `_phase[0]` stays at `"splash"` but window is gone, irrelevant. `os._exit(0)` ensures clean shutdown regardless of dirty phase.
- Current handling: Adequate (defensive try/except + os._exit).
- Recommendation: None.

### 4. Backend crash mid-session
- Likelihood: LOW-MEDIUM (DB lock, OOM, network share drop).
- Impact: HIGH. uvicorn dies → all `fetch()` calls return `TypeError: Failed to fetch` → caught by `unhandledrejection` listener (line 468) → POSTs to `/api/log/frontend-error` which ALSO fails (server dead). The `.catch(function(_){})` (line 451) silently drops it. User sees no error UI; buttons just "do nothing".
- Current handling: INSUFFICIENT. Frontend error bridge requires a live backend to surface errors.
- Recommendation: Add a client-side toast/banner in the bridge: when `fetch(/api/log/frontend-error)` rejects, show a fixed-position red banner "백엔드 연결 끊김 — 앱을 재시작하세요." This is a JS-only patch.

### 5. Multi-monitor / DPI mismatch
- Likelihood: MEDIUM (광양창고 likely has mixed monitors).
- Impact: LOW. `load_window_state` clamps to 1024-3840 / 700-2160 (line 106-107) but doesn't validate position vs. current monitor layout. Window may open off-screen if previous monitor disconnected.
- Current handling: Size-clamped; position not stored — PyWebView centers default.
- Recommendation: Cosmetic. None required.

### 6. DB lock during shutdown
- Likelihood: LOW.
- Impact: LOW on Python 3.9+. `_db_executor.shutdown(wait=False)` returns immediately; ThreadPoolExecutor workers are daemon threads on 3.9+ → interpreter exits cleanly. `os._exit(0)` (line 558) bypasses non-daemon waits anyway, so even 3.7/3.8 is safe in this codebase.
- Current handling: Adequate.
- Recommendation: None. (Note: add `python_requires=">=3.9"` in build manifest for safety.)

### 7. Ollama not installed
- Likelihood: HIGH (광양 PCs likely lack Ollama).
- Impact: LOW. `find_ollama_cli()` returns "" → `start_ollama_server()` returns False at line 80 in <100ms. `start_ollama_server_async` calls `on_done(False)` from worker thread. UI handler responsibility — verified module is correct, but caller-side handling NOT audited here. The docstring (lines 121-125) clearly warns about thread marshalling.
- Current handling: Module-level: GOOD. Caller-level: must verify each UI consumer.
- Recommendation: Grep for `start_ollama_server_async` callsites and confirm each `on_done` shows a "AI 사용 불가" toast on `False`.

---

## Top 3 risks (likelihood × impact)

1. **Backend crash silent failure (#4)** — Med likelihood × HIGH impact = **HIGHEST**. User loses work without warning.
2. **Double-instance race (#1)** — HIGH likelihood × MED impact = **HIGH**. Cross-kill can corrupt the "good" instance's state if timing aligns.
3. **Ollama caller handling (#7)** — HIGH likelihood × LOW-MED impact = **MED**. Module is fine; consumer-side gap is the unknown.

## Recommended defensive patches (not applied)

- **P4**: Single-instance mutex in `main()` (Win32 `CreateMutexW`).
- **P5**: JS heartbeat banner — every 30s ping `/api/health`; on N consecutive failures, show fixed red banner with "재시작" button.
- **P6**: Audit all `start_ollama_server_async` callers for `on_done(False)` UI feedback.

P4 and P5 close the two highest-ranked risks with ~30 lines of code each, no breaking changes.
