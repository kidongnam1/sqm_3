#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQM v864.3 — 자동 롤백 (Tier 3 S4)
===================================
설치 실패 / DB 손상 / 잘못된 마이그레이션 시 이전 백업으로 복원.

사용:
    python tools/rollback.py --to-backup latest
    python tools/rollback.py --to-backup 2026-04-20
    python tools/rollback.py --list

작성: Ruby, 2026-04-21
"""
from __future__ import annotations
import argparse
import os
import shutil
import sys
import json
from datetime import datetime
from pathlib import Path

# 백업 위치 — Windows %APPDATA%\SQM\backups
APPDATA = Path(os.environ.get("APPDATA", os.path.expanduser("~/.config")))
BACKUP_DIR = APPDATA / "SQM" / "backups"
DB_PATH = APPDATA / "SQM" / "sqm.db"


def list_backups() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)


def cmd_list():
    backups = list_backups()
    if not backups:
        print(f"백업 없음 ({BACKUP_DIR})")
        return
    print(f"백업 {len(backups)}개:")
    for b in backups:
        size = b.stat().st_size
        mtime = datetime.fromtimestamp(b.stat().st_mtime)
        print(f"  {b.name:30s}  {size:>12,} B  {mtime.isoformat(timespec='seconds')}")


def cmd_rollback(target: str) -> int:
    backups = list_backups()
    if not backups:
        print("ERROR: 백업이 없습니다.", file=sys.stderr)
        return 1

    if target == "latest":
        chosen = backups[0]
    else:
        # 날짜 매칭 (YYYY-MM-DD)
        candidates = [b for b in backups if target in b.name]
        if not candidates:
            print(f"ERROR: '{target}' 매칭 백업 없음", file=sys.stderr)
            return 1
        chosen = candidates[0]

    print(f"롤백 대상: {chosen}")
    print(f"현재 DB:   {DB_PATH}")

    # 안전을 위해 현재 DB 를 사이드 백업
    if DB_PATH.exists():
        side = DB_PATH.parent / f"sqm_pre_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(DB_PATH, side)
        print(f"사이드 백업: {side}")

    # 복원
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chosen, DB_PATH)
    print(f"OK 복원 완료. 프로그램 재시작 권장.")

    # 결과 기록
    log_file = DB_PATH.parent / "rollback.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(),
            "from": str(chosen),
            "to": str(DB_PATH),
        }, ensure_ascii=False) + "\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--to-backup", help="latest 또는 YYYY-MM-DD")
    p.add_argument("--list", action="store_true", help="가능한 백업 목록")
    args = p.parse_args()
    if args.list or not args.to_backup:
        cmd_list()
        return 0
    return cmd_rollback(args.to_backup)


if __name__ == "__main__":
    sys.exit(main())
