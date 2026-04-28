# -*- coding: utf-8 -*-
"""
scripts/smoke_test.py
=====================
Standalone smoke test runner for SQM v864.3.

Runs WITHOUT pytest and WITHOUT a live server. Uses FastAPI's TestClient
to drive the ASGI app in-process.

Usage:
    python scripts/smoke_test.py

Exit codes:
    0 — all checks passed
    1 — at least one check failed (including backend import failure)

Every probe is wrapped in try/except so the script never prints a raw
traceback: a crash is reported as FAIL with the exception type.
"""
from __future__ import annotations

import os
import sys
import traceback
from typing import Callable, List, Tuple


# ---------------------------------------------------------------------------
# sys.path — add project root (parent of this scripts/ directory)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
_results: List[Tuple[str, bool, str]] = []


def _record(name: str, ok: bool, note: str = "") -> None:
    _results.append((name, ok, note))
    marker = "PASS" if ok else "FAIL"
    line = f"[{marker}] {name}"
    if note:
        line += f" — {note}"
    print(line)


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------
def _probe(name: str, fn: Callable[[], Tuple[bool, str]]) -> None:
    """Run a probe; any exception becomes a FAIL."""
    try:
        ok, note = fn()
    except Exception as e:  # noqa: BLE001
        ok, note = False, f"{type(e).__name__}: {e}"
        # Keep the traceback out of stdout but log to stderr for debugging.
        traceback.print_exc(file=sys.stderr)
    _record(name, ok, note)


def _build_client():
    """Import backend.api and return (client, app). Raises on failure."""
    from fastapi.testclient import TestClient  # noqa: WPS433 — local import by design
    from backend.api import app  # noqa: WPS433

    return TestClient(app), app


def _check_import() -> Tuple[bool, str]:
    import backend.api  # noqa: F401 — import for side effect
    return True, "backend.api imported"


def _check_health(client) -> Tuple[bool, str]:
    r = client.get("/api/health")
    ok = r.status_code == 200
    return ok, f"HTTP {r.status_code}"


def _check_dashboard(client) -> Tuple[bool, str]:
    r = client.get("/api/dashboard/stats")
    ok = r.status_code == 200
    return ok, f"HTTP {r.status_code}"


def _check_inventory(client) -> Tuple[bool, str]:
    r = client.get("/api/inventory")
    ok = r.status_code == 200
    return ok, f"HTTP {r.status_code}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 60)
    print("SQM v864.3 — Phase 0 Smoke Test (standalone)")
    print("=" * 60)

    # Step 1: import check
    _probe("import backend.api", _check_import)
    import_ok = _results[-1][1]
    if not import_ok:
        _summary()
        return 1

    # Step 2: build TestClient (separate probe so we isolate client-build errors)
    client = None

    def _build() -> Tuple[bool, str]:
        nonlocal client
        client, _app = _build_client()
        return True, "TestClient ready"

    _probe("build TestClient", _build)
    if client is None:
        _summary()
        return 1

    # Step 3: endpoint probes
    _probe("GET /api/health", lambda: _check_health(client))
    _probe("GET /api/dashboard/stats", lambda: _check_dashboard(client))
    _probe("GET /api/inventory", lambda: _check_inventory(client))

    return _summary()


def _summary() -> int:
    total = len(_results)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = total - passed
    print("-" * 60)
    print(f"Summary: {passed}/{total} passed, {failed} failed")
    print("-" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
