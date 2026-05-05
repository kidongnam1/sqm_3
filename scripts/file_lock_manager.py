#!/usr/bin/env python3
"""
Simple file-level lock manager for multi-session editing safety.

Usage examples:
  python scripts/file_lock_manager.py acquire --file frontend/js/sqm-tonbag.js --session ruby-A
  python scripts/file_lock_manager.py status  --file frontend/js/sqm-tonbag.js
  python scripts/file_lock_manager.py release --file frontend/js/sqm-tonbag.js --session ruby-A
  python scripts/file_lock_manager.py list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOCK_DIR = ROOT / ".locks" / "files"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_target(file_arg: str) -> str:
    p = Path(file_arg)
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    else:
        p = p.resolve()
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def lock_name(target: str) -> str:
    digest = hashlib.sha1(target.encode("utf-8")).hexdigest()[:12]
    safe = target.replace("/", "__").replace(":", "_")
    if len(safe) > 80:
        safe = safe[:80]
    return f"{safe}__{digest}.lock.json"


def lock_path_for(target: str) -> Path:
    return LOCK_DIR / lock_name(target)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    os.replace(temp, path)


@dataclass
class Context:
    session: str
    operator: str
    pid: int
    host: str


def build_context(session: str | None, operator: str | None) -> Context:
    return Context(
        session=(session or "default").strip() or "default",
        operator=(operator or os.getenv("USERNAME") or os.getenv("USER") or "unknown").strip(),
        pid=os.getpid(),
        host=socket.gethostname(),
    )


def cmd_acquire(args: argparse.Namespace) -> int:
    target = normalize_target(args.file)
    lock_path = lock_path_for(target)
    ctx = build_context(args.session, args.operator)

    if lock_path.exists():
        existing = load_json(lock_path)
        owner = existing.get("owner_session")
        if owner == ctx.session:
            existing["updated_at"] = now_iso()
            existing["owner_pid"] = ctx.pid
            save_json_atomic(lock_path, existing)
            print(f"REENTER_OK {target} (session={ctx.session})")
            return 0
        print(f"LOCKED {target}")
        print(f"  owner_session: {existing.get('owner_session')}")
        print(f"  owner_operator: {existing.get('owner_operator')}")
        print(f"  owner_host: {existing.get('owner_host')}")
        print(f"  acquired_at: {existing.get('acquired_at')}")
        return 2

    payload = {
        "target": target,
        "owner_session": ctx.session,
        "owner_operator": ctx.operator,
        "owner_pid": ctx.pid,
        "owner_host": ctx.host,
        "acquired_at": now_iso(),
        "updated_at": now_iso(),
    }
    save_json_atomic(lock_path, payload)
    print(f"ACQUIRED {target} (session={ctx.session})")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    target = normalize_target(args.file)
    lock_path = lock_path_for(target)
    ctx = build_context(args.session, args.operator)

    if not lock_path.exists():
        print(f"NO_LOCK {target}")
        return 0

    existing = load_json(lock_path)
    owner = existing.get("owner_session")
    if not args.force and owner != ctx.session:
        print(f"DENIED {target}")
        print(f"  owner_session: {owner}")
        print(f"  your_session: {ctx.session}")
        print("  hint: use --force if manual cleanup is needed")
        return 3

    lock_path.unlink(missing_ok=True)
    print(f"RELEASED {target}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    target = normalize_target(args.file)
    lock_path = lock_path_for(target)
    if not lock_path.exists():
        print(f"FREE {target}")
        return 0
    existing = load_json(lock_path)
    print(f"LOCKED {target}")
    print(json.dumps(existing, ensure_ascii=False, indent=2))
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(LOCK_DIR.glob("*.lock.json"))
    if not files:
        print("NO_LOCKS")
        return 0
    for p in files:
        try:
            d = load_json(p)
            print(f"- {d.get('target')} | session={d.get('owner_session')} | at={d.get('acquired_at')}")
        except Exception:
            print(f"- (broken) {p.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="File lock manager for concurrent sessions.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_acquire = sub.add_parser("acquire", help="Acquire lock for a file")
    p_acquire.add_argument("--file", required=True, help="Target file path (absolute or relative)")
    p_acquire.add_argument("--session", default="default", help="Session id/name")
    p_acquire.add_argument("--operator", default=None, help="Operator name")
    p_acquire.set_defaults(func=cmd_acquire)

    p_release = sub.add_parser("release", help="Release lock for a file")
    p_release.add_argument("--file", required=True, help="Target file path (absolute or relative)")
    p_release.add_argument("--session", default="default", help="Session id/name")
    p_release.add_argument("--operator", default=None, help="Operator name")
    p_release.add_argument("--force", action="store_true", help="Force release lock owned by another session")
    p_release.set_defaults(func=cmd_release)

    p_status = sub.add_parser("status", help="Check lock status for a file")
    p_status.add_argument("--file", required=True, help="Target file path")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="List all current locks")
    p_list.set_defaults(func=cmd_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

