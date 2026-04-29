"""
v864.3 Phase 5 자동 검증 스크립트
=================================

전체 FastAPI 엔드포인트를 TestClient 로 호출하여 응답 체크.
- GET: 200 OK 기대 (일부 빈 DB 에서 404/500 허용)
- POST 신규 12개: 200 ok:true OR 의도된 4xx/NOT_READY
- POST 기존 NOT_READY 44개: 200 ok:false code:NOT_READY

결과:
- REPORTS/phase5_verify_<ts>.json  (기계 판독용)
- REPORTS/phase5_verify_<ts>.md    (사람 판독용)
- 종료 코드 0 (PASS) / 1 (FAIL)

사용:
    python scripts/verify_endpoints.py
    python scripts/verify_endpoints.py --verbose
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 인코딩 안전
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("SQM_CAPTURE_STDIO", "0")
os.environ.setdefault("SQM_LOG_LEVEL", "CRITICAL")


# ────────────────────────────────────────────────────────────
# 검증 대상 엔드포인트 정의
# ────────────────────────────────────────────────────────────
GET_ENDPOINTS = [
    # 대시보드
    "/api/dashboard/kpi",
    "/api/dashboard/stats",
    "/api/dashboard/alerts",
    # Health
    "/api/health",
    # Queries
    "/api/q/inbound-status",
    "/api/q/outbound-status",
    "/api/q/movement-history",
    "/api/q/audit-log?limit=10",
    "/api/q/inventory-report",
    "/api/q/inventory-trend",
    "/api/q/product-inventory",
    "/api/q/approval-history",
    # Queries 2
    "/api/q2/recent-files",
    "/api/q2/return-stats",
    "/api/q2/report-daily",
    "/api/q2/report-monthly",
    "/api/q2/outbound-confirm-list",
    "/api/q2/detail-outbound",
    # Queries 3
    "/api/q3/sales-order-dn",
    "/api/q3/dn-cross-check",
    # Actions
    "/api/action/integrity-check",
    "/api/action/export-lot-excel",
    # Inventory / Allocation / Tonbags
    "/api/inventory",
    "/api/allocation",
    # v864.3 Phase 4-B 신규
    "/api/outbound/quick/info?lot_no=NO_EXIST",
    "/api/outbound/picked-summary",
    "/api/log/ping",
    # Info (system-info is in actions router)
    "/api/action/system-info",
    "/api/info/version",
    "/api/info/shortcuts",
    "/api/info/status-guide",
    "/api/info/backup-guide",
    "/api/info/usage",
]

# v864.3 Phase 4-B 신규 POST — 스모크 테스트 (정상/실패 시나리오)
NEW_POST_TESTS = [
    {
        "id": "F001-pdf-empty",
        "method": "POST",
        "url": "/api/inbound/pdf-upload",
        "files": {"file": ("empty.pdf", b"", "application/pdf")},
        "expect_status": 400,
    },
    {
        "id": "F001-pdf-notpdf",
        "method": "POST",
        "url": "/api/inbound/pdf-upload",
        "files": {"file": ("fake.pdf", b"not-a-pdf", "application/pdf")},
        "expect_status": 400,
    },
    {
        "id": "F002-bulk-empty",
        "method": "POST",
        "url": "/api/inbound/bulk-import-excel",
        "files": {"file": ("empty.xlsx", b"", "application/octet-stream")},
        "expect_status": 400,
    },
    {
        "id": "F002-bulk-badext",
        "method": "POST",
        "url": "/api/inbound/bulk-import-excel",
        "files": {"file": ("bad.txt", b"x", "text/plain")},
        "expect_status": 400,
    },
    {
        "id": "F003-do-update-missing",
        "method": "POST",
        "url": "/api/action3/do-update",
        "json": {},
        "expect_status": 400,
    },
    {
        "id": "F007-return-bad",
        "method": "POST",
        "url": "/api/inbound/return-excel",
        "files": {"file": ("bad.txt", b"x", "text/plain")},
        "expect_status": 400,
    },
    {
        "id": "F014-alloc-empty",
        "method": "POST",
        "url": "/api/allocation/bulk-import-excel",
        "files": {"file": ("empty.xlsx", b"", "application/octet-stream")},
        "expect_status": 400,
    },
    {
        "id": "F015-quick-validation",
        "method": "POST",
        "url": "/api/outbound/quick",
        "json": {"lot_no": "", "count": 1, "customer": ""},
        "expect_status": 422,
    },
    {
        "id": "F015-quick-nolot",
        "method": "POST",
        "url": "/api/outbound/quick",
        "json": {"lot_no": "NO_EXIST_LOT", "count": 1, "customer": "TEST"},
        "expect_status": 200,  # 엔진이 거절 → ok:false
        "expect_ok": False,
    },
    {
        "id": "F016-quick-paste-empty",
        "method": "POST",
        "url": "/api/outbound/quick-paste",
        "json": {"rows": [], "customer": "TEST"},
        "expect_status": 422,  # min_length=1
    },
    {
        "id": "F017-picking-empty",
        "method": "POST",
        "url": "/api/outbound/picking-list-pdf",
        "files": {"file": ("empty.pdf", b"", "application/pdf")},
        "expect_status": 400,
    },
    {
        "id": "F022-apply-approved",
        "method": "POST",
        "url": "/api/allocation/apply-approved",
        "json": {},
        "expect_status": 200,
        "expect_ok": None,  # True OR False 모두 허용
    },
    {
        "id": "F028-confirm-blocked",
        "method": "POST",
        "url": "/api/outbound/confirm",
        "json": {"lot_no": "", "force_all": False},
        "expect_status": 200,
        "expect_ok": False,
        "expect_code": "CONFIRM_ALL_BLOCKED",
    },
    {
        "id": "F028-confirm-nolot",
        "method": "POST",
        "url": "/api/outbound/confirm",
        "json": {"lot_no": "NO_EXIST", "force_all": False},
        "expect_status": 200,
        "expect_ok": False,
    },
    {
        "id": "F004-tonbag-empty",
        "method": "POST",
        "url": "/api/tonbag/location-upload",
        "files": {"file": ("empty.xlsx", b"", "application/octet-stream")},
        "expect_status": 400,
    },
]

# [Sprint 0] NOT_READY_POST_SAMPLES emptied — backend/api/menubar.py was the 62-endpoint
# NotReadyError stub set, now deleted. Real menu action routing lives under /api/inbound,
# /api/outbound, /api/allocation, /api/action*, /api/q*.
NOT_READY_POST_SAMPLES: list[str] = []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    args = parser.parse_args()

    print("=" * 70)
    print(" v864.3 Phase 5 — 엔드포인트 자동 검증")
    print("=" * 70)

    # FastAPI 로드
    try:
        from fastapi.testclient import TestClient

        from backend.api import app
    except Exception as e:
        print(f"❌ FastAPI 로드 실패: {e}")
        return 1

    client = TestClient(app)
    results = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "get_endpoints": [],
        "new_post_tests": [],
        "not_ready_samples": [],
        "summary": {},
    }

    total = 0
    pass_ = 0
    fail_ = 0

    # 1. GET 엔드포인트
    print("\n[1] GET 엔드포인트 검증")
    print("-" * 70)
    for url in GET_ENDPOINTS:
        total += 1
        try:
            r = client.get(url)
            status = r.status_code
            ok = 200 <= status < 300
            if ok:
                pass_ += 1
                mark = "✅"
            else:
                # 일부 GET 은 DB 없음 등으로 500 가능 — verbose 에서만 FAIL 처리
                fail_ += 1
                mark = "❌"
            if args.verbose or not ok:
                print(f"  {mark} GET {url:<55} {status}")
            results["get_endpoints"].append({
                "url": url, "status": status, "ok": ok,
            })
        except Exception as e:
            fail_ += 1
            print(f"  💥 GET {url:<55} EXCEPTION: {e}")
            results["get_endpoints"].append({"url": url, "error": str(e)})

    # 2. 신규 POST 스모크 테스트
    print("\n[2] v864.3 Phase 4-B 신규 POST 스모크")
    print("-" * 70)
    for t in NEW_POST_TESTS:
        total += 1
        try:
            kwargs = {}
            if "json" in t:
                kwargs["json"] = t["json"]
            if "files" in t:
                kwargs["files"] = t["files"]
            r = client.request(t["method"], t["url"], **kwargs)

            expected_status = t.get("expect_status")
            status_match = (expected_status is None) or (r.status_code == expected_status)

            body = None
            ok_match = True
            code_match = True
            try:
                body = r.json()
                if "expect_ok" in t and t["expect_ok"] is not None:
                    ok_match = (body.get("ok") == t["expect_ok"])
                if "expect_code" in t:
                    detail = body.get("detail") or {}
                    code_match = (detail.get("code") == t["expect_code"])
            except Exception:
                pass

            passed = status_match and ok_match and code_match
            if passed:
                pass_ += 1
                mark = "✅"
            else:
                fail_ += 1
                mark = "❌"
            print(f"  {mark} {t['id']:<28} {t['method']} {t['url']:<40} {r.status_code} (expect {expected_status})")
            results["new_post_tests"].append({
                **t, "got_status": r.status_code, "passed": passed,
                "body_keys": list(body.keys()) if isinstance(body, dict) else None,
            })
        except Exception as e:
            fail_ += 1
            print(f"  💥 {t['id']:<28} EXCEPTION: {e}")
            results["new_post_tests"].append({**t, "error": str(e)})

    # 3. NOT_READY 샘플
    print("\n[3] 기존 POST NOT_READY 투명화 샘플")
    print("-" * 70)
    for url in NOT_READY_POST_SAMPLES:
        total += 1
        try:
            r = client.post(url, json={})
            body = r.json() if r.status_code == 200 else None
            is_not_ready = (
                r.status_code == 200
                and body
                and body.get("ok") is False
                and (body.get("detail") or {}).get("code") == "NOT_READY"
            )
            if is_not_ready:
                pass_ += 1
                mark = "✅ NOT_READY"
            else:
                fail_ += 1
                mark = "❌"
            if args.verbose or not is_not_ready:
                print(f"  {mark} POST {url:<50} {r.status_code}")
            results["not_ready_samples"].append({
                "url": url, "status": r.status_code, "is_not_ready": is_not_ready,
            })
        except Exception as e:
            fail_ += 1
            print(f"  💥 POST {url:<50} EXCEPTION: {e}")

    # 요약
    results["summary"] = {
        "total": total, "pass": pass_, "fail": fail_,
        "pass_rate": round(pass_ / total * 100, 1) if total else 0,
    }
    print("\n" + "=" * 70)
    print(f"총 {total} 건 · ✅ PASS {pass_} · ❌ FAIL {fail_} · {results['summary']['pass_rate']}%")
    print("=" * 70)

    # 리포트 저장
    reports_dir = PROJECT_ROOT / "REPORTS"
    reports_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = reports_dir / f"phase5_verify_{ts}.json"
    md_path = reports_dir / f"phase5_verify_{ts}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Phase 5 자동 검증 결과\n\n")
        f.write(f"**실행**: {results['started_at']}\n\n")
        f.write(f"## 요약\n- 총: {total} · PASS: {pass_} · FAIL: {fail_}\n")
        f.write(f"- PASS 비율: {results['summary']['pass_rate']}%\n\n")
        f.write(f"## GET ({len(GET_ENDPOINTS)}개)\n")
        for g in results["get_endpoints"]:
            mark = "✅" if g.get("ok") else "❌"
            f.write(f"- {mark} GET {g['url']} → {g.get('status', 'ERR')}\n")
        f.write(f"\n## 신규 POST ({len(NEW_POST_TESTS)}개)\n")
        for t in results["new_post_tests"]:
            mark = "✅" if t.get("passed") else "❌"
            f.write(f"- {mark} {t['id']} → {t.get('got_status', 'ERR')}\n")
        f.write(f"\n## NOT_READY 샘플 ({len(NOT_READY_POST_SAMPLES)}개)\n")
        for s in results["not_ready_samples"]:
            mark = "✅" if s.get("is_not_ready") else "❌"
            f.write(f"- {mark} {s['url']}\n")

    print(f"\n📝 결과 저장:\n  - {json_path}\n  - {md_path}")

    return 0 if fail_ == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
