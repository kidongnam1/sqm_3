"""
core.config_logging — 로깅 설정 진입점 (P4)
============================================
config_logging 모듈 re-export.
"""
from config_logging import (
    LOG_BACKUP_COUNT,
    LOG_DATE_FORMAT,
    LOG_FILE,
    LOG_FORMAT,
    LOG_KEEP_DAYS,
    LOG_LEVEL,
    LOG_MAX_SIZE_MB,
    setup_logging,
)

__all__ = [
    'setup_logging',
    'LOG_LEVEL',
    'LOG_FORMAT',
    'LOG_DATE_FORMAT',
    'LOG_FILE',
    'LOG_MAX_SIZE_MB',
    'LOG_BACKUP_COUNT',
    'LOG_KEEP_DAYS',
]
