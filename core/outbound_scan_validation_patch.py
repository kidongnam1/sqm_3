# -*- coding: utf-8 -*-
"""SQM outbound scan validation helpers (Ruby patch v1)."""
from __future__ import annotations
from dataclasses import dataclass

ALLOWED_SCAN_STATUSES = {"AVAILABLE", "RESERVED", "PICKED"}
BLOCKED_SCAN_STATUSES = {"SHIPPED", "RETURNED", "HOLD", "DAMAGED"}

@dataclass
class ScanValidationResult:
    success: bool
    level: str
    code: str
    message: str


def is_scannable_status(status: str) -> ScanValidationResult:
    s = str(status or "").strip().upper()
    if s in ALLOWED_SCAN_STATUSES:
        return ScanValidationResult(True, "PASS", "STATUS_SCAN_ALLOWED", f"스캔 허용 상태: {s}")
    if s in BLOCKED_SCAN_STATUSES:
        return ScanValidationResult(False, "HARD_STOP", "STATUS_SCAN_BLOCKED", f"스캔 불가 상태: {s}")
    return ScanValidationResult(False, "HARD_STOP", "STATUS_UNKNOWN_BLOCKED", f"알 수 없는 상태 차단: {s}")


def is_duplicate_scan(scanned_uids: set[str], tonbag_uid: str) -> ScanValidationResult:
    uid = str(tonbag_uid or "").strip()
    if uid in scanned_uids:
        return ScanValidationResult(False, "WARNING", "DUPLICATE_SCAN_DETECTED", f"이미 스캔됨: {uid}")
    return ScanValidationResult(True, "PASS", "UID_NOT_SCANNED_YET", f"신규 스캔: {uid}")
