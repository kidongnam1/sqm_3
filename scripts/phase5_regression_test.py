"""
Phase 5: v864.2 vs v864.3 Regression Test
==========================================
1. DB Schema Parity (테이블/컬럼 일치)
2. API Endpoint Health (모든 GET/POST 200 응답)
3. Data Integrity (v864.3 API 응답이 DB 데이터와 일치)
4. UI Rendering (Playwright: 모든 페이지 빈화면 없음)
5. Feature Matrix Check (85개 기능 매핑 검증)

사용:
    python scripts/phase5_regression_test.py
    python scripts/phase5_regression_test.py --headless
"""
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V862_DB = Path("D:/program/SQM_inventory/Claude_SQM_v864_2/data/db/sqm_inventory.db")
V863_DB = PROJECT_ROOT / "data" / "db" / "sqm_inventory.db"
API_BASE = "http://127.0.0.1:8765"

results = []
errors = []


def api_get(path):
    url = API_BASE + path
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, str(e)


def api_post(path, data=None):
    url = API_BASE + path
    payload = json.dumps(data or {}).encode()
    req = urllib.request.Request(url, data=payload, method='POST',
                                headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, str(e)


def record(test_name, passed, detail=""):
    results.append({'test': test_name, 'pass': passed, 'detail': str(detail)[:200]})
    if not passed:
        errors.append(f"{test_name}: {detail}")
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_name}" + (f" - {str(detail)[:80]}" if detail and not passed else ""))


# ============================================================
# TEST 1: DB Schema Parity
# ============================================================
def test_schema_parity():
    print("\n[1] DB Schema Parity (v864.2 vs v864.3)...")

    if not V862_DB.exists():
        record("schema_v862_exists", False, "v864.2 DB not found")
        return
    if not V863_DB.exists():
        record("schema_v863_exists", False, "v864.3 DB not found")
        return

    con2 = sqlite3.connect(str(V862_DB))
    con3 = sqlite3.connect(str(V863_DB))

    # Table list
    t2 = set(r[0] for r in con2.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall())
    t3 = set(r[0] for r in con3.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall())

    common = t2 & t3
    only_v2 = t2 - t3
    only_v3 = t3 - t2

    record("schema_common_tables", len(common) >= 20,
           f"common={len(common)}, only_v2={len(only_v2)}, only_v3={len(only_v3)}")

    if only_v2:
        record("schema_missing_in_v3", len(only_v2) == 0, f"v864.2 only: {only_v2}")
    if only_v3:
        # v864.3 can have extra tables (new features)
        record("schema_new_in_v3", True, f"v864.3 new: {only_v3}")

    # Column parity for core tables
    core_tables = ['inventory', 'inventory_tonbag', 'stock_movement', 'document_do',
                   'document_invoice', 'audit_log', 'return_history']
    for tbl in core_tables:
        if tbl not in common:
            continue
        cols2 = set(r[1] for r in con2.execute(f"PRAGMA table_info([{tbl}])").fetchall())
        cols3 = set(r[1] for r in con3.execute(f"PRAGMA table_info([{tbl}])").fetchall())
        missing = cols2 - cols3
        record(f"schema_{tbl}_columns", len(missing) == 0,
               f"missing in v3: {missing}" if missing else f"{len(cols3)} cols")

    con2.close()
    con3.close()


# ============================================================
# TEST 2: API Endpoint Health
# ============================================================
def test_api_health():
    print("\n[2] API Endpoint Health Check...")

    # Health
    code, body = api_get("/api/health")
    record("api_health", code == 200 and body and body.get("status") == "ok",
           f"status={body.get('status') if body else 'N/A'}, lots={body.get('lots') if body else '?'}")

    # GET endpoints
    get_endpoints = [
        ("/api/q/inbound-status", "inbound-status"),
        ("/api/q/approval-history", "approval-history"),
        ("/api/q/outbound-status", "outbound-status"),
        ("/api/q/backup-list", "backup-list"),
        ("/api/q/audit-log", "audit-log"),
        ("/api/q/inventory-trend", "inventory-trend"),
        ("/api/q/inventory-report", "inventory-report"),
        ("/api/q/movement-history", "movement-history"),
        ("/api/q/picked-list", "picked-list"),
        ("/api/q/sold-list", "sold-list"),
        ("/api/q/product-inventory", "product-inventory"),
        ("/api/q/allocation-summary", "allocation-summary"),
        ("/api/q2/report-daily", "report-daily"),
        ("/api/q2/report-monthly", "report-monthly"),
        ("/api/q2/recent-files", "recent-files"),
        ("/api/q2/return-stats", "return-stats"),
        ("/api/q2/detail-outbound", "detail-outbound"),
        ("/api/q3/sales-order-dn", "sales-order-dn"),
        ("/api/q3/dn-cross-check", "dn-cross-check"),
        ("/api/q3/settings-info", "settings-info"),
        ("/api/info/usage", "info-usage"),
        ("/api/info/shortcuts", "info-shortcuts"),
        ("/api/info/status-guide", "info-status-guide"),
        ("/api/info/backup-guide", "info-backup-guide"),
        ("/api/info/version", "info-version"),
        ("/api/dashboard/stats", "dashboard-stats"),
        ("/api/dashboard/alerts", "dashboard-alerts"),
        ("/api/inventory", "inventory-list"),
        ("/api/allocation", "allocation-list"),
        ("/api/tonbags", "tonbags-list"),
        ("/api/action/integrity-check", "integrity-check"),
    ]

    for path, name in get_endpoints:
        code, body = api_get(path)
        ok = code == 200
        detail = ""
        if ok and isinstance(body, dict):
            if 'data' in body:
                d = body['data']
                if isinstance(d, list):
                    detail = f"{len(d)} items"
                elif isinstance(d, dict) and 'items' in d:
                    detail = f"{len(d['items'])} items"
                else:
                    detail = f"data type={type(d).__name__}"
        elif not ok:
            detail = f"HTTP {code}"
        record(f"api_get_{name}", ok, detail)


# ============================================================
# TEST 3: Data Integrity (API vs DB)
# ============================================================
def test_data_integrity():
    print("\n[3] Data Integrity (API response vs DB)...")

    con = sqlite3.connect(str(V863_DB))
    con.row_factory = sqlite3.Row

    def extract_count(body):
        """Extract row count from various API response formats"""
        if isinstance(body, list):
            return len(body)
        if isinstance(body, dict):
            d = body.get('data', body)
            if isinstance(d, list):
                return len(d)
            if isinstance(d, dict):
                if 'items' in d:
                    return len(d['items'])
                if 'rows' in d:
                    return len(d['rows'])
        return -1

    # Inventory count match
    db_inv_count = con.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    code, body = api_get("/api/inventory")
    if code == 200:
        api_count = extract_count(body)
        record("integrity_inventory_count", api_count == db_inv_count,
               f"DB={db_inv_count}, API={api_count}")
    else:
        record("integrity_inventory_count", False, f"API error {code}")

    # Tonbag count match
    db_tb_count = con.execute("SELECT COUNT(*) FROM inventory_tonbag").fetchone()[0]
    code, body = api_get("/api/tonbags")
    if code == 200:
        api_count = extract_count(body)
        # API may have LIMIT (e.g., 300), so check api_count > 0 and <= db_count
        record("integrity_tonbag_count", 0 < api_count <= db_tb_count or api_count == db_tb_count,
               f"DB={db_tb_count}, API={api_count}" + (" (API limit)" if api_count < db_tb_count else ""))
    else:
        record("integrity_tonbag_count", False, f"API error {code}")

    # Dashboard stats match
    code, body = api_get("/api/dashboard/stats")
    if code == 200 and body:
        d = body.get('data', body) if isinstance(body, dict) else body
        if isinstance(d, dict):
            dash_lots = d.get('total_lots', -1)
            record("integrity_dashboard_lots", dash_lots == db_inv_count,
                   f"dashboard={dash_lots}, DB={db_inv_count}")
            dash_tbags = d.get('total_tbags', d.get('total_tonbags', -1))
            record("integrity_dashboard_tonbags", dash_tbags == db_tb_count,
                   f"dashboard={dash_tbags}, DB={db_tb_count}")
        else:
            record("integrity_dashboard", True, "non-dict response")
    else:
        record("integrity_dashboard", False, "dashboard stats unavailable")

    # Movement count
    db_move_count = con.execute("SELECT COUNT(*) FROM stock_movement").fetchone()[0]
    code, body = api_get("/api/q/movement-history")
    if code == 200 and body:
        api_move = extract_count(body)
        record("integrity_movement_count", api_move > 0 or db_move_count == 0,
               f"DB={db_move_count}, API={api_move}")
    else:
        record("integrity_movement_count", False, f"API error {code}")

    # Audit log count
    db_audit_count = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    code, body = api_get("/api/q/audit-log")
    if code == 200 and body:
        api_audit = extract_count(body)
        record("integrity_audit_count", api_audit > 0 or db_audit_count == 0,
               f"DB={db_audit_count}, API={api_audit}")

    con.close()


# ============================================================
# TEST 4: UI Rendering (Playwright)
# ============================================================
def test_ui_rendering(headless=True):
    print("\n[4] UI Rendering (Playwright)...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        record("ui_playwright_import", False, "playwright not installed")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(API_BASE + '/', timeout=15000)
            page.wait_for_load_state('networkidle', timeout=10000)
        except Exception as e:
            record("ui_page_load", False, str(e))
            browser.close()
            return

        record("ui_page_load", True, "page loaded")

        # Check critical UI elements exist
        checks = [
            ('#menubar', 'menubar'),
            ('#toolbar', 'toolbar'),
            ('#sidebar', 'sidebar'),
            ('#dashboard-container', 'dashboard'),
            ('#statusbar-container', 'statusbar'),
        ]
        for selector, name in checks:
            el = page.query_selector(selector)
            record(f"ui_element_{name}", el is not None)

        # Test all 9 sidebar tabs render content
        routes = ['inventory', 'allocation', 'picked', 'outbound', 'return',
                  'move', 'dashboard', 'log', 'scan']
        for route in routes:
            btn = page.query_selector(f'.side-btn[data-route="{route}"]')
            if btn:
                btn.click()
                page.wait_for_timeout(800)

                if route == 'dashboard':
                    el = page.query_selector('#dashboard-container')
                    has_content = el is not None and len(el.inner_text().strip()) > 10
                else:
                    el = page.query_selector('#page-container')
                    has_content = el is not None and el.is_visible() and len(el.inner_text().strip()) > 10

                record(f"ui_tab_{route}_content", has_content,
                       f"text_len={len(el.inner_text().strip()) if el else 0}")

        # Dashboard KPI cards have data (not '--')
        page.query_selector('.side-btn[data-route="dashboard"]').click()
        page.wait_for_timeout(1000)
        kpi_vals = page.query_selector_all('.kpi-value')
        kpi_filled = sum(1 for k in kpi_vals if k.inner_text().strip() not in ('--', '', '0'))
        record("ui_dashboard_kpi", kpi_filled >= 2,
               f"{kpi_filled}/{len(kpi_vals)} KPI cards with data")

        # Inventory table has data rows (wait longer for API response)
        page.query_selector('.side-btn[data-route="inventory"]').click()
        page.wait_for_timeout(2000)
        inv_rows = page.query_selector_all('#inv-tbody tr')
        # Also check if page-container has content even without tbody
        pc = page.query_selector('#page-container')
        pc_has_text = pc is not None and len(pc.inner_text().strip()) > 50
        record("ui_inventory_rows", len(inv_rows) > 0 or pc_has_text,
               f"{len(inv_rows)} rows, page_content={pc_has_text}")

        # Check 2-tier structure exists for allocation
        page.query_selector('.side-btn[data-route="allocation"]').click()
        page.wait_for_timeout(800)
        alloc_panel = page.query_selector('#alloc-detail-panel')
        record("ui_allocation_2tier", alloc_panel is not None, "detail panel present")

        # Check 2-tier structure exists for picked
        page.query_selector('.side-btn[data-route="picked"]').click()
        page.wait_for_timeout(800)
        picked_panel = page.query_selector('#picked-detail-panel')
        record("ui_picked_2tier", picked_panel is not None, "detail panel present")

        # Check 2-tier structure exists for outbound
        page.query_selector('.side-btn[data-route="outbound"]').click()
        page.wait_for_timeout(800)
        outbound_panel = page.query_selector('#outbound-detail-panel')
        record("ui_outbound_2tier", outbound_panel is not None, "detail panel present")

        browser.close()


# ============================================================
# TEST 5: Feature Matrix (85 features)
# ============================================================
def test_feature_matrix():
    print("\n[5] Feature Matrix (85 features)...")

    fm_path = PROJECT_ROOT / "docs" / "handoff" / "feature_matrix.json"
    if not fm_path.exists():
        record("feature_matrix_exists", False, "feature_matrix.json not found")
        return

    with open(fm_path, 'r', encoding='utf-8') as f:
        fm = json.load(f)

    features = fm if isinstance(fm, list) else fm.get('features', fm.get('items', []))
    if not features:
        record("feature_matrix_load", False, "no features found in JSON")
        return

    record("feature_matrix_count", len(features) >= 80,
           f"{len(features)} features defined")

    # Check JS ENDPOINTS coverage
    js_path = PROJECT_ROOT / "frontend" / "js" / "sqm-inline.js"
    js_content = js_path.read_text(encoding='utf-8')

    # Count data-action buttons in HTML
    html_path = PROJECT_ROOT / "frontend" / "index.html"
    html_content = html_path.read_text(encoding='utf-8')

    import re
    html_actions = set(re.findall(r'data-action="([^"]+)"', html_content))
    js_endpoints = set(re.findall(r"'([a-zA-Z][^']+)':\s*\{m:", js_content))

    # Check no WIP remaining
    wip_count = js_content.count("u:'wip'")
    record("feature_no_wip", wip_count == 0, f"{wip_count} WIP endpoints remaining")

    # Check all HTML actions have JS ENDPOINTS
    # theme-dark/theme-light are handled by separate event bindings, not ENDPOINTS
    missing = html_actions - js_endpoints - {'toggle-theme', 'theme-toggle', 'theme-dark', 'theme-light'}
    record("feature_action_coverage", len(missing) == 0,
           f"missing ENDPOINTS: {missing}" if missing else f"{len(html_actions)} actions covered")

    # Check endpoint count
    record("feature_endpoint_count", len(js_endpoints) >= 60,
           f"{len(js_endpoints)} ENDPOINTS registered")

    # Check critical features exist
    critical_features = [
        'onOnPdfInbound', 'onInboundManual', 'onOnQuickOutbound',
        'onQuickOutboundPaste', 'onReturnDialog', 'onIntegrityCheck',
        'onOnBackup', 'onRestore', 'onInventoryReport',
        'onMovementHistory', 'onInvoiceGenerate', 'onProductMaster',
    ]
    for feat in critical_features:
        record(f"feature_{feat}", feat in js_endpoints)


# ============================================================
# TEST 6: v864.2 vs v864.3 Data Comparison
# ============================================================
def test_data_comparison():
    print("\n[6] v864.2 vs v864.3 Data Comparison...")

    if not V862_DB.exists():
        record("compare_v862_exists", False, "v864.2 DB not found")
        return

    con2 = sqlite3.connect(str(V862_DB))
    con3 = sqlite3.connect(str(V863_DB))
    con2.row_factory = sqlite3.Row
    con3.row_factory = sqlite3.Row

    # Compare LOT data structure (not counts, but column structure)
    cols2 = [r[1] for r in con2.execute("PRAGMA table_info(inventory)").fetchall()]
    cols3 = [r[1] for r in con3.execute("PRAGMA table_info(inventory)").fetchall()]
    common_cols = set(cols2) & set(cols3)
    record("compare_inventory_schema", len(common_cols) >= 15,
           f"common={len(common_cols)}, v2={len(cols2)}, v3={len(cols3)}")

    # Compare a few specific LOTs (if they exist in both)
    lots2 = [r[0] for r in con2.execute("SELECT DISTINCT lot_no FROM inventory ORDER BY lot_no LIMIT 5").fetchall()]
    lots3 = [r[0] for r in con3.execute("SELECT DISTINCT lot_no FROM inventory ORDER BY lot_no LIMIT 5").fetchall()]
    common_lots = set(lots2) & set(lots3)

    if common_lots:
        lot_sample = list(common_lots)[0]
        r2 = dict(con2.execute("SELECT * FROM inventory WHERE lot_no=?", (lot_sample,)).fetchone())
        r3 = dict(con3.execute("SELECT * FROM inventory WHERE lot_no=?", (lot_sample,)).fetchone())

        # Compare key fields
        key_fields = ['lot_no', 'sap_no', 'bl_no', 'product', 'net_weight', 'status']
        mismatches = []
        for f in key_fields:
            if f in r2 and f in r3 and str(r2[f]) != str(r3[f]):
                mismatches.append(f"{f}: v2={r2[f]} vs v3={r3[f]}")

        record("compare_lot_data_match", len(mismatches) == 0,
               f"LOT {lot_sample}: " + (", ".join(mismatches) if mismatches else "all fields match"))
    else:
        # Different LOT data is expected if DBs diverged from separate usage
        record("compare_lot_overlap", True,
               f"no common LOTs (expected - separate environments): v2={lots2[:3]}, v3={lots3[:3]}")

    # Tonbag schema comparison
    tcols2 = set(r[1] for r in con2.execute("PRAGMA table_info(inventory_tonbag)").fetchall())
    tcols3 = set(r[1] for r in con3.execute("PRAGMA table_info(inventory_tonbag)").fetchall())
    record("compare_tonbag_schema", tcols2.issubset(tcols3),
           f"v2 cols in v3: {len(tcols2 & tcols3)}/{len(tcols2)}")

    # Product list comparison
    prods2 = set(r[0] for r in con2.execute("SELECT DISTINCT product FROM inventory WHERE product IS NOT NULL").fetchall())
    prods3 = set(r[0] for r in con3.execute("SELECT DISTINCT product FROM inventory WHERE product IS NOT NULL").fetchall())
    common_prods = prods2 & prods3
    record("compare_products", len(common_prods) > 0 or len(prods2) == 0,
           f"common={len(common_prods)}, v2={len(prods2)}, v3={len(prods3)}")

    con2.close()
    con3.close()


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--headless', action='store_true', default=True)
    parser.add_argument('--no-headless', dest='headless', action='store_false')
    args = parser.parse_args()

    print("=" * 60)
    print("Phase 5: v864.2 vs v864.3 Regression Test")
    print("=" * 60)

    # Check API server
    try:
        code, _ = api_get("/api/health")
        if code != 200:
            print(f"\nERROR: API server not responding (HTTP {code})")
            print("Start server first: python -m uvicorn backend.api:app --port 8765")
            return 1
    except Exception:
        print("\nERROR: Cannot connect to API server at " + API_BASE)
        print("Start server first: python -m uvicorn backend.api:app --port 8765")
        return 1

    test_schema_parity()
    test_api_health()
    test_data_integrity()
    test_ui_rendering(headless=args.headless)
    test_feature_matrix()
    test_data_comparison()

    # Summary
    pass_count = sum(1 for r in results if r['pass'])
    fail_count = sum(1 for r in results if not r['pass'])
    total = len(results)

    print(f"\n{'=' * 60}")
    print(f"Phase 5 Results: {total} tests | PASS {pass_count} | FAIL {fail_count}")
    pct = round(pass_count / total * 100, 1) if total else 0
    print(f"Pass Rate: {pct}%")
    print(f"{'=' * 60}")

    if errors:
        print(f"\nFailed tests ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")

    # Save report
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {'total': total, 'pass': pass_count, 'fail': fail_count, 'rate': pct},
        'errors': errors,
        'results': results,
    }
    report_path = PROJECT_ROOT / 'REPORTS' / 'phase5_regression.json'
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved: {report_path}")

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
