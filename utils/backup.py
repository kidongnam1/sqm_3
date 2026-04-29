"""
SQM 재고관리 - 자동 백업 모듈 (v2.9.43)

기능:
- 프로그램 시작 시 DB 자동 백업
- 날짜별 백업 파일 관리
- 오래된 백업 자동 정리

Author: Ruby
Version: 2.4.2
Date: 2026-01-09
"""

import glob
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

# 설정 import
try:
    from core.config import (
        BACKUP_DIR,
        BACKUP_ENABLED,
        BACKUP_INTERVAL_HOURS,
        BACKUP_MAX_COUNT,
        DB_PATH,
    )
except ImportError:
    # 기본값
    try:
        from config import DB_PATH
    except ImportError:
        DB_PATH = Path(__file__).parent.parent / "data" / "db" / "sqm_inventory.db"
        BACKUP_DIR = Path(__file__).parent.parent / "backup"
        BACKUP_ENABLED = True
        BACKUP_MAX_COUNT = 5
        BACKUP_INTERVAL_HOURS = 24

logger = logging.getLogger(__name__)


class BackupManager:
    """데이터베이스 백업 관리자"""

    def __init__(
        self,
        db_path: Path = None,
        backup_dir: Path = None,
        max_count: int = None,
        interval_hours: int = None
    ):
        """
        백업 관리자 초기화

        Args:
            db_path: 데이터베이스 파일 경로
            backup_dir: 백업 저장 디렉토리
            max_count: 최대 백업 파일 수
            interval_hours: 최소 백업 간격 (시간)
        """
        self.db_path = Path(db_path) if db_path else Path(DB_PATH)
        self.backup_dir = Path(backup_dir) if backup_dir else Path(BACKUP_DIR)
        self.max_count = max_count or BACKUP_MAX_COUNT
        self.interval_hours = interval_hours or BACKUP_INTERVAL_HOURS

        # 백업 디렉토리 생성
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def should_backup(self) -> Tuple[bool, str]:
        """
        백업이 필요한지 확인

        Returns:
            (should_backup, reason): 백업 필요 여부와 이유
        """
        if not BACKUP_ENABLED:
            return False, "백업 비활성화됨"

        if not self.db_path.exists():
            return False, f"DB 파일 없음: {self.db_path}"

        # 최신 백업 파일 확인
        latest_backup = self._get_latest_backup()

        if latest_backup is None:
            return True, "백업 파일 없음 - 첫 백업"

        # 마지막 백업 시간 확인
        backup_time = self._get_backup_time(latest_backup)
        if backup_time is None:
            return True, "백업 시간 파싱 실패 - 새 백업"

        # 간격 확인
        elapsed = datetime.now() - backup_time
        if elapsed > timedelta(hours=self.interval_hours):
            return True, f"마지막 백업 후 {elapsed.total_seconds() / 3600:.1f}시간 경과"

        return False, f"최근 백업 존재 ({elapsed.total_seconds() / 60:.0f}분 전)"

    def create_backup(self, force: bool = False) -> Tuple[bool, str]:
        """
        데이터베이스 백업 생성

        Args:
            force: 간격 무시하고 강제 백업

        Returns:
            (success, message): 성공 여부와 메시지
        """
        try:
            # 백업 필요 여부 확인
            if not force:
                should, reason = self.should_backup()
                if not should:
                    logger.info(f"백업 스킵: {reason}")
                    return True, reason

            # DB 파일 존재 확인
            if not self.db_path.exists():
                msg = f"DB 파일이 존재하지 않습니다: {self.db_path}"
                logger.warning(msg)
                return False, msg

            # 백업 파일명 생성 (날짜_시간)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"sqm_inventory_{timestamp}.db"
            backup_path = self.backup_dir / backup_name

            # 파일 복사
            shutil.copy2(self.db_path, backup_path)

            # 파일 크기 확인
            backup_size = backup_path.stat().st_size
            size_str = self._format_size(backup_size)

            logger.info(f"✅ 백업 완료: {backup_name} ({size_str})")

            # 오래된 백업 정리
            self._cleanup_old_backups()

            return True, f"백업 완료: {backup_name} ({size_str})"

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            msg = f"백업 실패: {str(e)}"
            logger.error(msg, exc_info=True)
            return False, msg

    def restore_backup(self, backup_file: str = None) -> Tuple[bool, str]:
        """
        백업에서 복원

        Args:
            backup_file: 복원할 백업 파일명 (미지정시 최신)

        Returns:
            (success, message): 성공 여부와 메시지
        """
        try:
            if backup_file:
                backup_path = self.backup_dir / backup_file
            else:
                backup_path = self._get_latest_backup()

            if backup_path is None or not backup_path.exists():
                return False, "복원할 백업 파일이 없습니다"

            # 현재 DB 백업 (복원 전)
            if self.db_path.exists():
                temp_backup = self.db_path.with_suffix('.db.before_restore')
                shutil.copy2(self.db_path, temp_backup)

            # 복원
            shutil.copy2(backup_path, self.db_path)

            logger.info(f"✅ 복원 완료: {backup_path.name}")
            return True, f"복원 완료: {backup_path.name}"

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            msg = f"복원 실패: {str(e)}"
            logger.error(msg, exc_info=True)
            return False, msg

    # REMOVED v8.6.4: duplicate list_backups()

    def _get_latest_backup(self) -> Optional[Path]:
        """최신 백업 파일 경로 반환"""
        pattern = str(self.backup_dir / "sqm_inventory_*.db")
        files = sorted(glob.glob(pattern), reverse=True)
        return Path(files[0]) if files else None

    def _get_backup_time(self, backup_path: Path) -> Optional[datetime]:
        """백업 파일명에서 시간 추출"""
        try:
            # sqm_inventory_20260108_123456.db
            name = backup_path.stem  # sqm_inventory_20260108_123456
            parts = name.split('_')
            if len(parts) >= 3:
                date_str = parts[-2]  # 20260108
                time_str = parts[-1]  # 123456
                return datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
        except ValueError as e:  # v2.4.5 수정: 날짜 파싱 실패
            logger.debug(f"[backup] 무시: {e}")

        # 파일 수정 시간 사용
        return datetime.fromtimestamp(backup_path.stat().st_mtime)

    def _cleanup_old_backups(self):
        """오래된 백업 파일 정리"""
        try:
            backups = self.list_backups()

            if len(backups) <= self.max_count:
                return

            # 오래된 것부터 삭제
            to_delete = backups[self.max_count:]

            for backup in to_delete:
                try:
                    os.remove(backup['path'])
                    logger.info(f"🗑️ 오래된 백업 삭제: {backup['filename']}")
                except (OSError, IOError, PermissionError) as e:
                    logger.warning(f"백업 삭제 실패: {backup['filename']} - {e}")

        except (OSError, IOError, PermissionError) as e:
            logger.warning(f"백업 정리 실패: {e}")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """파일 크기 포맷팅"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


# =============================================================================
# 편의 함수
# =============================================================================

_backup_manager = None

def get_backup_manager() -> BackupManager:
    """전역 백업 관리자 반환"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager


def auto_backup_on_startup() -> Tuple[bool, str]:
    """
    프로그램 시작 시 자동 백업 실행

    Returns:
        (success, message): 결과
    """
    manager = get_backup_manager()
    return manager.create_backup(force=False)


def force_backup() -> Tuple[bool, str]:
    """
    강제 백업 실행 (간격 무시)

    Returns:
        (success, message): 결과
    """
    manager = get_backup_manager()
    return manager.create_backup(force=True)


def list_backups() -> List[dict]:
    """백업 목록 조회"""
    manager = get_backup_manager()
    return manager.list_backups()


def restore_latest() -> Tuple[bool, str]:
    """최신 백업에서 복원"""
    manager = get_backup_manager()
    return manager.restore_backup()


# =============================================================================
# 테스트
# =============================================================================

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    logger.debug("=" * 60)
    logger.debug("  SQM 재고관리 - 백업 테스트")
    logger.debug("=" * 60)

    # 백업 실행
    success, msg = auto_backup_on_startup()
    logger.debug(f"\n자동 백업: {msg}")

    # 백업 목록
    logger.debug("\n백업 목록:")
    for backup in list_backups():
        logger.debug(f"  - {backup['filename']} ({backup['size_str']}) - {backup['created_str']}")


# ═══════════════════════════════════════════════════════════
# v5.2.0: 공용 백업 정리 함수 (4곳 중복 해소)
# ═══════════════════════════════════════════════════════════

def cleanup_old_backups_in_dir(backup_dir: str, max_count: int = 10,
                                extension: str = '.db') -> int:
    """
    지정 디렉토리에서 오래된 백업 파일 정리 (공용)
    
    Args:
        backup_dir: 백업 디렉토리 경로
        max_count: 최대 보관 수
        extension: 백업 파일 확장자
        
    Returns:
        삭제된 파일 수
    """
    deleted = 0
    try:
        if not os.path.isdir(backup_dir):
            return 0
        backups = sorted([
            f for f in os.listdir(backup_dir)
            if f.endswith(extension)
        ])
        while len(backups) > max_count:
            old = backups.pop(0)
            old_path = os.path.join(backup_dir, old)
            try:
                os.remove(old_path)
                deleted += 1
                logger.info(f"🗑️ 오래된 백업 삭제: {old}")
            except (OSError, IOError, PermissionError) as e:
                logger.warning(f"백업 삭제 실패: {old} - {e}")
    except (OSError, IOError, PermissionError) as e:
        logger.warning(f"백업 정리 실패: {e}")
    return deleted
