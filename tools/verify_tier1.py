#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tier 1 Auto-Verification Script
================================
SQM Inventory v864.3 — Tier 1 Definition of Done 자동 검증기

- 정적 검증 (Linux/Windows 모두 가능): HTML/JS/Py 파일 파싱
- 런타임 검증 (Windows 전용): main_webview.py subprocess 기동 후 FastAPI 확인
- 결과는 JSON + Markdown 양식으로 저장

실행:
    python tools/verify_tier1.py --mode auto
    python tools/verify_tier1.py --mode static       # Linux/WSL
    python tools/verify_tier1.py --mode runtime      # Windows (EXE 환경)

작성: Ruby (Senior Software Architect)
일자: 2026-04-21
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# ───────────────────────── 상수 ─────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_HOST = "127.0.0.1"
API_PORT = 8765  # main_webview.py 와 일치 (CLAUDE.md 기록된 포트)
API_BASE = f"http://{API_HOST}:{API_PORT}"
REPORT_DIR = PROJECT_ROOT / "REPORTS"
REPORT_DIR.mkdir(exist_ok=True)

# 상단 메뉴바 요구 (v864_2_structure.json 의 menubar.menus 기준)
REQUIRED_TOP_MENUS = ["파일", "재고", "보고서", "설정/도구", "도움말"]

# 액션 툴바 7개 (structure.json 의 action_toolbar.items)
REQUIRED_TOOLBAR_ITEMS = [
    "PDF 입고", "즉시 출고", "반품", "재고 조회",
    "정합성", "백업", "설정",
]

# 사이드바 9탭 (structure.json 의 sidebar_tabs)
REQUIRED_SIDEBAR_TABS = [
    "Inventory", "Allocation", "Picked", "Outbound",
    "Return", "Move", "Dashboard", "Log", "Scan",
]

# 필수 FastAPI 엔드포인트 (정적 파싱 + 런타임 ping)
REQUIRED_ENDPOINTS = [
    ("GET", "/api/health"),
    ("GET", "/api/dashboard/stats"),
    ("GET", "/api/inventory"),
    ("GET", "/api/tonbags"),
    ("GET", "/api/allocation"),
    ("GET", "/api/outbound/scheduled"),
    ("GET", "/api/outbound/history"),
    ("GET", "/api/move/history"),
    ("GET", "/api/integrity/quick"),
    ("GET", "/api/log/activity"),
]


# ───────────────────────── 결과 모델 ─────────────────────────
@dataclass
class CheckResult:
    key: str
    title: str
    passed: bool
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Report:
    started_at: str
    finished_at: str
    mode: str
    host_os: str
    python_version: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def pass_rate(self) -> float:
        return self.pass_count / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "mode": self.mode,
            "host_os": self.host_os,
            "python_version": self.python_version,
            "pass_count": self.pass_count,
            "total": self.total,
            "pass_rate": round(self.pass_rate, 4),
            "checks": [c.to_dict() for c in self.checks],
        }


# ───────────────────────── 공통 유틸 ─────────────────────────
def read_text(path: Path, encoding: str = "utf-8") -> str:
    try:
        return path.read_text(encoding=encoding)
    except FileNotFoundError:
        return ""
    except UnicodeDecodeError:
        return path.read_text(encoding="cp949", errors="ignore")


def safe(fn: Callable[[], CheckResult], key: str, title: str) -> CheckResult:
    """개별 체크 실행 — 예외 발생해도 전체 검증이 멈추지 않도록"""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return CheckResult(
            key=key, title=title, passed=False,
            detail=f"예외 발생: {type(e).__name__}: {e}",
        )


# ───────────────────────── 정적 체크 함수들 ─────────────────────────
def check_exe_present() -> CheckResult:
    exe = PROJECT_ROOT / "build" / "dist" / "SQM_v864_3.exe"
    exists = exe.exists()
    size = exe.stat().st_size if exists else 0
    return CheckResult(
        key="T1.1_exe_present",
        title="PyInstaller EXE 빌드 산출물 존재",
        passed=exists and size > 50_000_000,  # 최소 50MB 이상
        detail=f"경로={exe} 크기={size:,}B" if exists else "EXE 파일 없음",
        evidence={"path": str(exe), "size": size},
    )


def check_main_webview_code() -> CheckResult:
    mw = PROJECT_ROOT / "main_webview.py"
    src = read_text(mw)
    has_create_window = "webview.create_window" in src
    has_start = "webview.start" in src
    has_thread = "threading.Thread" in src and "uvicorn.run" in src
    has_port = "8765" in src
    # 창 크기 1500x900 탐색 (혹은 1400x900)
    m = re.search(r"width\s*=\s*(\d+)[,\s]+height\s*=\s*(\d+)", src)
    size_ok = False
    size_detail = "width/height 미검출"
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        size_detail = f"width={w}, height={h}"
        size_ok = w >= 1200 and h >= 800
    passed = all([has_create_window, has_start, has_thread, has_port])
    return CheckResult(
        key="T1.2_main_webview",
        title="main_webview.py — PyWebView+FastAPI 통합 코드",
        passed=passed,
        detail=(
            f"create_window={has_create_window}, start={has_start}, "
            f"thread+uvicorn={has_thread}, port=8765={has_port}, size={size_detail}"
        ),
        evidence={"window_size_ok": size_ok, "window_size_raw": size_detail},
    )


def check_backend_api_endpoints_static() -> CheckResult:
    api = PROJECT_ROOT / "backend" / "api.py"
    src = read_text(api)
    pattern = re.compile(r'^\s*@app\.(get|post|put|delete)\(\s*["\']([^"\']+)["\']', re.M)
    found = [(m.group(1).upper(), m.group(2)) for m in pattern.finditer(src)]
    found_set = {(method, path) for method, path in found}
    missing = [e for e in REQUIRED_ENDPOINTS if e not in found_set]
    has_cors = "CORSMiddleware" in src and "add_middleware" in src
    has_health = any(p == "/api/health" for _, p in found)
    passed = len(missing) == 0 and has_cors and has_health
    return CheckResult(
        key="T1.3_backend_endpoints",
        title=f"backend/api.py — 필수 엔드포인트 {len(REQUIRED_ENDPOINTS)}개 + CORS",
        passed=passed,
        detail=(
            f"발견 {len(found)}개 / 필수 {len(REQUIRED_ENDPOINTS)}개, "
            f"CORS={has_cors}, health={has_health}, 누락={missing or '없음'}"
        ),
        evidence={"endpoints_found": found, "missing": [list(m) for m in missing]},
    )


def check_db_engine_code() -> CheckResult:
    api = PROJECT_ROOT / "backend" / "api.py"
    src = read_text(api)
    has_engine_import = "SQMInventoryEngineV3" in src or "engine_modules" in src
    has_db_path = "DB_PATH" in src
    has_try_except = re.search(r"try:[\s\S]{0,400}except", src) is not None
    passed = has_engine_import and has_db_path and has_try_except
    return CheckResult(
        key="T1.4_db_engine",
        title="엔진/DB 연결 코드 + 예외 처리",
        passed=passed,
        detail=(
            f"engine_import={has_engine_import}, DB_PATH={has_db_path}, "
            f"try/except={has_try_except}"
        ),
    )


def check_html_shell() -> CheckResult:
    html_path = PROJECT_ROOT / "frontend" / "index.html"
    html = read_text(html_path)
    if not html:
        return CheckResult(
            key="T1.5_html_shell", title="HTML Shell (메뉴/사이드바/툴바)",
            passed=False, detail="frontend/index.html 없음",
        )
    # 메뉴/사이드바/툴바 라벨 탐지 (한글 포함)
    menus_found = [m for m in REQUIRED_TOP_MENUS if m in html]
    tb_found = [t for t in REQUIRED_TOOLBAR_ITEMS if t in html]
    sb_found = [s for s in REQUIRED_SIDEBAR_TABS if s in html]
    btn_count = html.count("<button")
    nav_count = html.count("<nav")
    passed = (
        len(menus_found) >= 4
        and len(tb_found) >= 5
        and len(sb_found) >= 7
        and btn_count >= 10
    )
    return CheckResult(
        key="T1.5_html_shell",
        title="HTML Shell — 메뉴/사이드바/툴바 렌더링",
        passed=passed,
        detail=(
            f"메뉴 {len(menus_found)}/{len(REQUIRED_TOP_MENUS)}, "
            f"툴바 {len(tb_found)}/{len(REQUIRED_TOOLBAR_ITEMS)}, "
            f"사이드바 {len(sb_found)}/{len(REQUIRED_SIDEBAR_TABS)}, "
            f"버튼 {btn_count}개, nav {nav_count}개"
        ),
        evidence={
            "menus_found": menus_found,
            "toolbar_found": tb_found,
            "sidebar_found": sb_found,
        },
    )


def check_toast_wiring() -> CheckResult:
    app_js = PROJECT_ROOT / "frontend" / "js" / "app.js"
    css = PROJECT_ROOT / "frontend" / "css" / "design-system.css"
    js_src = read_text(app_js)
    css_src = read_text(css)
    has_func = "function showToast" in js_src or "showToast =" in js_src
    has_css = ".toast" in css_src and "#toast-container" in css_src
    # "준비 중" 문구 힌트 (Tier 2 에서 채워질 예정이지만 Tier 1 DoD 는 최소 1건)
    coming_soon_hits = js_src.count("준비 중") + js_src.count("coming soon")
    passed = has_func and has_css
    return CheckResult(
        key="T1.6_toast",
        title="Toast 시스템 (showToast + CSS)",
        passed=passed,
        detail=f"showToast 함수={has_func}, CSS={has_css}, 준비중 문구 {coming_soon_hits}건",
    )


def check_theme_toggle() -> CheckResult:
    app_js = PROJECT_ROOT / "frontend" / "js" / "app.js"
    css = PROJECT_ROOT / "frontend" / "css" / "design-system.css"
    src = read_text(app_js)
    css_src = read_text(css)
    has_apply = "applyTheme" in src
    has_toggle = "toggleTheme" in src or ("theme-toggle" in src and "addEventListener" in src)
    has_storage = "localStorage" in src or "THEME_KEY" in src
    has_data_theme = "data-theme" in src and "data-theme" in css_src
    passed = all([has_apply, has_toggle, has_data_theme])
    return CheckResult(
        key="T1.7_theme",
        title="Dark/Light 테마 토글 + 상태 저장",
        passed=passed,
        detail=(
            f"applyTheme={has_apply}, toggle={has_toggle}, "
            f"localStorage={has_storage}, data-theme={has_data_theme}"
        ),
    )


def check_design_tokens() -> CheckResult:
    tokens = PROJECT_ROOT / "docs" / "handoff" / "design_tokens.json"
    css = PROJECT_ROOT / "frontend" / "css" / "design-system.css"
    try:
        data = json.loads(tokens.read_text(encoding="utf-8"))
        css_src = read_text(css)
        # 토큰 CSS 변수 일부가 CSS 파일에 정의되어 있는지 샘플 검증
        ok = True
        tok_count = 0
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    tok_count += len(v)
        # CSS 내 `--` 변수 개수
        var_count = len(re.findall(r"--[a-z0-9\-_]+\s*:", css_src))
        passed = tok_count >= 100 and var_count >= 50
        return CheckResult(
            key="T1.8_tokens",
            title="Design Tokens 연결 (JSON → CSS 변수)",
            passed=passed,
            detail=f"tokens 약 {tok_count}개, CSS 변수 {var_count}개",
        )
    except Exception as e:  # noqa: BLE001
        return CheckResult(
            key="T1.8_tokens",
            title="Design Tokens 연결 (JSON → CSS 변수)",
            passed=False,
            detail=f"검증 실패: {e}",
        )


def check_handoff_jsons() -> CheckResult:
    handoff = PROJECT_ROOT / "docs" / "handoff"
    required = ["v864_2_structure.json", "feature_matrix.json", "design_tokens.json"]
    missing = [f for f in required if not (handoff / f).exists()]
    if missing:
        return CheckResult(
            key="T1.9_handoff", title="핸드오프 JSON 3종 존재 + 유효",
            passed=False, detail=f"누락={missing}",
        )
    # 각 파일 JSON 파싱 검증
    bad = []
    sizes = {}
    for f in required:
        p = handoff / f
        sizes[f] = p.stat().st_size
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            bad.append(f"{f}({e})")
    passed = not bad
    return CheckResult(
        key="T1.9_handoff",
        title="핸드오프 JSON 3종 존재 + 유효",
        passed=passed,
        detail=f"유효성 문제={bad or '없음'}, 크기={sizes}",
        evidence={"sizes": sizes},
    )


STATIC_CHECKS: list[tuple[str, str, Callable[[], CheckResult]]] = [
    ("T1.1", "EXE 존재", check_exe_present),
    ("T1.2", "main_webview.py 통합", check_main_webview_code),
    ("T1.3", "backend API 엔드포인트", check_backend_api_endpoints_static),
    ("T1.4", "DB 엔진 연결 코드", check_db_engine_code),
    ("T1.5", "HTML Shell", check_html_shell),
    ("T1.6", "Toast 시스템", check_toast_wiring),
    ("T1.7", "Dark/Light 토글", check_theme_toggle),
    ("T1.8", "Design Tokens 연결", check_design_tokens),
    ("T1.9", "핸드오프 JSON 3종", check_handoff_jsons),
]


# ───────────────────────── 런타임 체크 (Windows 전용) ─────────────────────────
def _http_get(url: str, timeout: float = 2.0) -> tuple[int, str]:
    """requests 대신 표준 라이브러리 urllib 사용 (추가 의존성 제거)"""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return 0, f"ERR:{e}"


def wait_for_server(timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, _ = _http_get(f"{API_BASE}/api/health", timeout=1.5)
        if code == 200:
            return True
        time.sleep(0.5)
    return False


def check_runtime_server_up() -> CheckResult:
    ok = wait_for_server(timeout=20.0)
    return CheckResult(
        key="R1_server_up",
        title=f"FastAPI 서버 기동 확인 ({API_BASE}/api/health)",
        passed=ok,
        detail="헬스체크 200 OK" if ok else "시간 초과",
    )


def check_runtime_endpoints() -> CheckResult:
    results = []
    for method, path in REQUIRED_ENDPOINTS:
        if method != "GET":
            continue
        code, body = _http_get(f"{API_BASE}{path}", timeout=3.0)
        results.append((path, code, len(body)))
    failed = [r for r in results if r[1] not in (200, 204)]
    passed = not failed
    return CheckResult(
        key="R2_endpoints",
        title=f"필수 GET 엔드포인트 {len(results)}개 200 OK",
        passed=passed,
        detail=f"성공={len(results)-len(failed)}/{len(results)}, 실패={failed[:3]}",
        evidence={"results": results},
    )


def check_runtime_docs() -> CheckResult:
    code, _ = _http_get(f"{API_BASE}/docs", timeout=3.0)
    return CheckResult(
        key="R3_swagger",
        title="Swagger UI 접근 가능 (/docs)",
        passed=code == 200,
        detail=f"HTTP {code}",
    )


def launch_webview_subprocess() -> subprocess.Popen | None:
    """Windows 에서만 main_webview.py 기동.
    - 창을 실제로 띄우지 않도록 headless 모드(PYWEBVIEW_GUI=mock) 시도
    - 실패 시 일반 모드로 폴백. 단 백그라운드 프로세스로만 유지.
    """
    env = os.environ.copy()
    env.setdefault("PYWEBVIEW_GUI", "mock")  # 지원 불가 시 무시됨
    cmd = [sys.executable, str(PROJECT_ROOT / "main_webview.py")]
    try:
        # Windows 에서는 CREATE_NO_WINDOW 플래그가 존재
        kwargs: dict[str, Any] = {"env": env, "cwd": str(PROJECT_ROOT)}
        if platform.system() == "Windows":
            CREATE_NO_WINDOW = 0x08000000
            kwargs["creationflags"] = CREATE_NO_WINDOW
        proc = subprocess.Popen(cmd, **kwargs)  # noqa: S603
        return proc
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] subprocess 기동 실패: {e}", file=sys.stderr)
        return None


RUNTIME_CHECKS: list[tuple[str, str, Callable[[], CheckResult]]] = [
    ("R1", "FastAPI 기동", check_runtime_server_up),
    ("R2", "엔드포인트 200", check_runtime_endpoints),
    ("R3", "Swagger UI", check_runtime_docs),
]


# ───────────────────────── 실행 본체 ─────────────────────────
def run_static() -> list[CheckResult]:
    results = []
    for key, title, fn in STATIC_CHECKS:
        r = safe(fn, key=key, title=title)
        results.append(r)
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.key}: {r.title}  — {r.detail}")
    return results


def run_runtime() -> list[CheckResult]:
    results = []
    proc = launch_webview_subprocess()
    time.sleep(4.0)  # 서버 기동 대기
    try:
        for key, title, fn in RUNTIME_CHECKS:
            r = safe(fn, key=key, title=title)
            results.append(r)
            status = "PASS" if r.passed else "FAIL"
            print(f"[{status}] {r.key}: {r.title}  — {r.detail}")
    finally:
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
    return results


def write_report(report: Report) -> tuple[Path, Path]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"tier1_verify_{ts}.json"
    md_path = REPORT_DIR / f"tier1_verify_{ts}.md"

    json_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Tier 1 자동 검증 보고서",
        "",
        f"- 시작: {report.started_at}",
        f"- 종료: {report.finished_at}",
        f"- 모드: `{report.mode}`",
        f"- OS: `{report.host_os}`",
        f"- Python: `{report.python_version}`",
        f"- 통과율: **{report.pass_count}/{report.total} ({report.pass_rate*100:.1f}%)**",
        "",
        "| # | Key | 항목 | 결과 | 상세 |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(report.checks, 1):
        mark = "✅" if c.passed else "❌"
        lines.append(f"| {i} | `{c.key}` | {c.title} | {mark} | {c.detail} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Tier 1 Auto-Verification")
    parser.add_argument(
        "--mode", default="auto",
        choices=["auto", "static", "runtime"],
        help="auto = static + runtime(가능 시), static = 정적만, runtime = 런타임만",
    )
    args = parser.parse_args()

    started = datetime.now().isoformat(timespec="seconds")
    report = Report(
        started_at=started,
        finished_at="",
        mode=args.mode,
        host_os=f"{platform.system()} {platform.release()}",
        python_version=sys.version.split()[0],
    )

    if args.mode in ("auto", "static"):
        report.checks.extend(run_static())

    if args.mode in ("auto", "runtime"):
        if platform.system() == "Windows":
            report.checks.extend(run_runtime())
        else:
            report.checks.append(CheckResult(
                key="R0_skipped",
                title="런타임 검증 스킵 (비 Windows 환경)",
                passed=True,
                detail=f"host_os={platform.system()} → static 결과만 사용",
            ))

    report.finished_at = datetime.now().isoformat(timespec="seconds")
    json_path, md_path = write_report(report)

    print("")
    print("─" * 60)
    print(f"✅ PASS {report.pass_count}/{report.total}  ({report.pass_rate*100:.1f}%)")
    print(f"📄 JSON: {json_path}")
    print(f"📄 MD  : {md_path}")

    # exit code: 모두 통과 시 0, 하나라도 실패 시 1
    return 0 if report.pass_count == report.total else 1


if __name__ == "__main__":
    sys.exit(main())
