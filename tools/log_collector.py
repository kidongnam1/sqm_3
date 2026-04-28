#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQM v864.3 — 진단 로그 수집기 (Tier 3 S4)
==========================================
사장님이 "이상해" 하실 때 한 번에:
- 앱/API 로그
- DB 메타정보 (크기, 테이블 목록, 행 수)
- 시스템 정보 (Python, OS, 디스크)
- settings.ini 사본
- 최근 24시간 REPORTS

→ %TEMP%/sqm_diagnostics_<ts>.zip 생성
→ 이 파일을 개발자(Ruby)에게 전달

작성: Ruby, 2026-04-21
"""
from __future__ import annotations
import json
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

APPDATA = Path(os.environ.get("APPDATA", os.path.expanduser("~/.config")))
SQM_DATA = APPDATA / "SQM"
LOGS_DIR = SQM_DATA / "logs"
DB_PATH = SQM_DATA / "sqm.db"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def collect_system_info() -> dict:
    info = {
        "ts": datetime.now().isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "node": platform.node(),
        "appdata": str(APPDATA),
        "project_root": str(PROJECT_ROOT),
    }
    try:
        info["disk_total_gb"] = round(shutil.disk_usage(str(SQM_DATA))[0] / (1024**3), 2)
        info["disk_free_gb"] = round(shutil.disk_usage(str(SQM_DATA))[2] / (1024**3), 2)
    except Exception:
        pass
    try:
        import psutil  # type: ignore
        info["cpu_pct"] = psutil.cpu_percent(interval=0.1)
        info["mem_pct"] = psutil.virtual_memory().percent
    except ImportError:
        info["psutil"] = "not installed"
    return info


def collect_db_meta(db_path: Path) -> dict:
    if not db_path.exists():
        return {"exists": False}
    out = {
        "exists": True,
        "size_mb": round(db_path.stat().st_size / (1024**2), 2),
        "modified": datetime.fromtimestamp(db_path.stat().st_mtime).isoformat(),
        "tables": [],
    }
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for (name,) in cur.fetchall():
                try:
                    cur.execute(f'SELECT COUNT(*) FROM "{name}"')
                    cnt = cur.fetchone()[0]
                except Exception:
                    cnt = -1
                out["tables"].append({"name": name, "rows": cnt})
    except Exception as e:
        out["error"] = str(e)
    return out


def collect_recent_files(directory: Path, max_age_hours: int = 24) -> list[Path]:
    if not directory.exists():
        return []
    cutoff = time.time() - max_age_hours * 3600
    return [p for p in directory.glob("**/*") if p.is_file() and p.stat().st_mtime > cutoff]


def main() -> int:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_zip = Path(tempfile.gettempdir()) / f"sqm_diagnostics_{ts}.zip"

    sys_info = collect_system_info()
    db_meta = collect_db_meta(DB_PATH)
    recent_logs = collect_recent_files(LOGS_DIR, 24)
    recent_reports = collect_recent_files(PROJECT_ROOT / "REPORTS", 24)

    summary = {
        "generated": ts,
        "system": sys_info,
        "database": db_meta,
        "recent_log_count": len(recent_logs),
        "recent_report_count": len(recent_reports),
    }

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SUMMARY.json", json.dumps(summary, ensure_ascii=False, indent=2))
        for p in recent_logs:
            try: zf.write(p, arcname=f"logs/{p.name}")
            except Exception: pass
        for p in recent_reports:
            try: zf.write(p, arcname=f"reports/{p.name}")
            except Exception: pass
        # settings.ini 사본
        ini = PROJECT_ROOT / "settings.ini"
        if ini.exists():
            try: zf.write(ini, arcname="settings.ini")
            except Exception: pass

    print(f"OK 진단 ZIP 생성:")
    print(f"  {out_zip}")
    print(f"  로그 {len(recent_logs)}개, 리포트 {len(recent_reports)}개 포함")
    print(f"  → 이 파일을 Ruby 또는 개발자에게 전달하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
