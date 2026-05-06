"""
Frontend connection smoke tests.

Verifies that the FastAPI backend correctly serves the frontend static assets
that the PyWebView window will load. Run with the backend running:
    (start SQM main_webview.py in another terminal first)
    python -m pytest tests/test_frontend_connection.py -v
"""
import re
import urllib.error
import urllib.request

import pytest

BASE_URL = "http://127.0.0.1:8765"
TIMEOUT = 2

# Critical JS modules that must load for the frontend to function.
# Discovered from frontend/index.html <script src=...> tags.
CRITICAL_JS_MODULES = [
    "js/sqm-core.js",
    "js/sqm-inventory.js",
    "js/sqm-allocation.js",
    "js/sqm-picked.js",
    "js/sqm-logistics.js",
    "js/sqm-tonbag.js",
    "js/sqm-onestop-inbound.js",
]


def _get(url, timeout=TIMEOUT):
    """GET a URL and return (status_code, body_bytes). Raises ConnectionError on refusal."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        # HTTP errors (e.g. 404, 500) — still a response, return status with empty body
        return e.code, b""
    except (urllib.error.URLError, ConnectionRefusedError, OSError) as e:
        # Backend not running / unreachable — re-raise as ConnectionError so tests can skip
        raise ConnectionError(str(e))


def test_index_html_loads():
    """GET / returns 200 and the body looks like the SQM index page (contains <html and 'SQM')."""
    try:
        status, body = _get(f"{BASE_URL}/")
    except ConnectionError:
        pytest.skip("backend not running")

    assert status == 200, f"GET / returned {status}, expected 200"
    text = body.decode("utf-8", errors="replace")
    assert "<html" in text.lower(), "Response body does not contain '<html' tag"
    assert "sqm" in text.lower(), "Response body does not contain 'SQM' (case-insensitive)"


def test_critical_js_modules_load():
    """Each critical JS module referenced by index.html returns 200 from the backend."""
    try:
        # Probe one URL first to detect "backend not running" early
        _get(f"{BASE_URL}/{CRITICAL_JS_MODULES[0]}")
    except ConnectionError:
        pytest.skip("backend not running")

    failures = []
    for path in CRITICAL_JS_MODULES:
        url = f"{BASE_URL}/{path}"
        try:
            status, _ = _get(url)
        except ConnectionError:
            pytest.skip("backend not running")
        if status != 200:
            failures.append(f"{path} -> {status}")

    assert not failures, f"Critical JS modules did not return 200: {failures}"


def test_api_health_endpoint():
    """GET /api/health returns 200 — this is what wait_for_api polls during startup."""
    try:
        status, _ = _get(f"{BASE_URL}/api/health")
    except ConnectionError:
        pytest.skip("backend not running")

    assert status == 200, f"GET /api/health returned {status}, expected 200"


def test_no_404_in_index_html():
    """Parse index.html, extract every <script src=...> and <link href=...> path,
    and verify each non-CDN asset returns 200. CDN URLs (http(s)://...) are skipped."""
    try:
        status, body = _get(f"{BASE_URL}/")
    except ConnectionError:
        pytest.skip("backend not running")

    assert status == 200, f"GET / returned {status}, expected 200"
    html = body.decode("utf-8", errors="replace")

    # Extract <script src="..."> paths
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    # Extract <link ... href="..."> paths
    link_hrefs = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)

    all_paths = script_srcs + link_hrefs

    failures = []
    checked = 0
    for raw_path in all_paths:
        # Skip CDN / external URLs
        if raw_path.startswith("http://") or raw_path.startswith("https://") or raw_path.startswith("//"):
            continue
        # Skip data URIs
        if raw_path.startswith("data:"):
            continue
        # Strip leading slash so we can join cleanly with BASE_URL
        path = raw_path.lstrip("/")
        url = f"{BASE_URL}/{path}"
        try:
            asset_status, _ = _get(url)
        except ConnectionError:
            pytest.skip("backend not running")
        checked += 1
        if asset_status != 200:
            failures.append(f"{raw_path} -> {asset_status}")

    assert checked > 0, "No local assets were found in index.html to verify"
    assert not failures, f"Some assets referenced by index.html did not return 200: {failures}"
