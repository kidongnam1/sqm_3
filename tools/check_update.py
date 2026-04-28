#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQM v864.3 — 업데이트 체크 (Tier 3 S2)
======================================
시작 시 또는 메뉴 호출 시 새 버전이 있는지 확인.
- GitHub Release HEAD 또는 내부 서버 endpoint 체크
- 신버전 발견 시 사장님께 안내 + 다운로드 URL

작성: Ruby, 2026-04-21
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Optional

CURRENT_VERSION = "8.6.4.3"
UPDATE_URL = "http://127.0.0.1:8765/api/system/version"  # 자체 서버 사용 시


def fetch_remote_version(url: str = UPDATE_URL, timeout: float = 3.0) -> Optional[dict]:
    """원격 서버에서 최신 버전 정보 조회"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SQM/8.6.4.3"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def is_newer(remote: str, local: str = CURRENT_VERSION) -> bool:
    """semver 기반 비교 (a.b.c.d)"""
    try:
        r = [int(x) for x in remote.split(".")]
        l = [int(x) for x in local.split(".")]
        return tuple(r) > tuple(l)
    except Exception:
        return False


def check() -> dict:
    info = fetch_remote_version()
    if not info:
        return {"available": False, "current": CURRENT_VERSION, "reason": "원격 미응답"}
    remote = info.get("version", "")
    if not remote:
        return {"available": False, "current": CURRENT_VERSION}
    return {
        "available": is_newer(remote),
        "current": CURRENT_VERSION,
        "remote": remote,
        "url": info.get("download_url", ""),
        "notes": info.get("notes", ""),
    }


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
