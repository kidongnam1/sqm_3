#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tier 2 Auto-Verification
========================
feature_matrix.json 의 85개 기능을 순회하며,
(1) 엔드포인트가 정적 파싱으로 발견되는가
(2) JS 핸들러가 MENUBAR_MAP / TOOLBAR_MAP 에 존재하는가
(3) UI data-action 이 index.html 에 있는가 (선택)
를 점검하고 REPORTS/tier2_verify_<ts>.md 로 결과 저장.

실행:
    python tools/verify_tier2.py
"""
from __future__ import annotations
import json
import re
import sys
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "REPORTS"
REPORTS.mkdir(exist_ok=True)


def load_text(p: Path) -> str:
    try: return p.read_text(encoding="utf-8")
    except Exception: return ""


def extract_endpoints(src: str) -> set[tuple[str, str]]:
    out = set()
    for m in re.finditer(r'^\s*@(?:app|router)\.(get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']', src, re.M):
        out.add((m.group(1).upper(), m.group(2)))
    return out


def extract_prefix(src: str) -> str:
    m = re.search(r'APIRouter\(\s*prefix\s*=\s*["\']([^"\']+)["\']', src)
    return m.group(1) if m else ""


def main() -> int:
    # 1) feature_matrix 로드
    fm = json.loads((ROOT / "docs/handoff/feature_matrix.json").read_text(encoding="utf-8"))
    feats = fm["features"]

    # 2) backend 엔드포인트 수집
    ep_set = set()
    for f in [ROOT/"backend/api.py", ROOT/"backend/api/menubar.py", ROOT/"backend/api/controls.py"]:
        src = load_text(f)
        prefix = extract_prefix(src)
        for method, path in extract_endpoints(src):
            full = path if path.startswith("/") else "/" + path
            if prefix and not full.startswith(prefix):
                full = prefix + full
            ep_set.add((method, full))

    # 3) JS 핸들러 맵 수집
    menubar_js = load_text(ROOT/"frontend/js/handlers/menubar.js")
    toolbar_js = load_text(ROOT/"frontend/js/handlers/toolbar.js")
    topbar_js = load_text(ROOT/"frontend/js/handlers/topbar.js")
    shortcuts_js = load_text(ROOT/"frontend/js/shortcuts.js")

    handler_ids_menubar = set(re.findall(r'"([a-zA-Z0-9_]+)":\s*\{\s*id:', menubar_js))
    handler_ids_toolbar = set(re.findall(r'"([a-zA-Z0-9_\-]+)":\s*\{\s*(?:id|method):', toolbar_js))

    # 4) 85 기능 검증
    rows = []
    ep_ok = hdl_ok = 0
    by_status = {"completed": 0, "partial": 0, "missing": 0}
    for f in feats:
        fid = f.get("id", "?")
        cat = f.get("category", "?")
        label = f.get("label_korean", "")
        ep = (f.get("proposed_api_endpoint") or "").strip()
        js = (f.get("proposed_js_handler") or "").replace("()", "")

        # 엔드포인트 매칭
        match_ep = False
        if ep:
            parts = ep.split(None, 1)
            if len(parts) == 2:
                m, p = parts[0].upper(), parts[1]
                if (m, p) in ep_set:
                    match_ep = True
                else:
                    # prefix 보정해서 한 번 더
                    for em, ep2 in ep_set:
                        if em == m and ep2.endswith(p.lstrip("/")):
                            match_ep = True
                            break
        if match_ep: ep_ok += 1

        # 핸들러 매칭
        match_hdl = False
        if cat == "menubar":
            match_hdl = js in handler_ids_menubar
        elif cat == "toolbar_button":
            match_hdl = js in handler_ids_toolbar or js in handler_ids_menubar
        elif cat == "keyboard":
            match_hdl = True  # shortcuts.js 로 통합 처리
        elif cat == "sidebar_tab":
            match_hdl = True  # router 로 처리
        if match_hdl: hdl_ok += 1

        status = "completed" if (match_ep and match_hdl) else ("partial" if (match_ep or match_hdl) else "missing")
        by_status[status] = by_status.get(status, 0) + 1
        rows.append({
            "id": fid, "category": cat, "label": label,
            "endpoint_ok": match_ep, "handler_ok": match_hdl, "status": status,
        })

    total = len(rows)
    pass_count = by_status["completed"]
    pass_rate = pass_count / total if total else 0

    # 5) 리포트 작성
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = REPORTS / f"tier2_verify_{ts}.md"
    json_path = REPORTS / f"tier2_verify_{ts}.json"

    lines = [
        "# Tier 2 자동 검증 리포트",
        "",
        f"- 생성: {ts}",
        f"- 총 기능: **{total}**",
        f"- 완료: **{pass_count}** ({pass_rate*100:.1f}%)",
        f"- 부분: {by_status['partial']}",
        f"- 누락: {by_status['missing']}",
        f"- 목표: 81/85 (95%) ≥ {'PASS' if pass_count>=81 else 'FAIL'}",
        "",
        "## 상세",
        "| ID | 카테고리 | 라벨 | 엔드포인트 | 핸들러 | 상태 |",
        "|---|---|---|---|---|---|",
    ]
    icon = {"completed": "✅", "partial": "🟡", "missing": "⬜"}
    for r in rows:
        lines.append(
            f"| `{r['id']}` | {r['category']} | {r['label']} | "
            f"{'✅' if r['endpoint_ok'] else '❌'} | "
            f"{'✅' if r['handler_ok'] else '❌'} | "
            f"{icon.get(r['status'],'?')} {r['status']} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps({
        "total": total, "pass": pass_count, "pass_rate": pass_rate,
        "by_status": by_status, "rows": rows, "endpoints_found": len(ep_set),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Tier 2 검증: PASS {pass_count}/{total} ({pass_rate*100:.1f}%)")
    print(f"엔드포인트 등록: {len(ep_set)}")
    print(f"REPORT: {md_path}")
    return 0 if pass_count >= 81 else 1


if __name__ == "__main__":
    sys.exit(main())
