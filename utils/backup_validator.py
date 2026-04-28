"""
SQM v5.0.3 - 백업 검증 및 자동 복구 유틸리티
============================================

백업 파일 무결성 검증 및 자동 복구 기능
"""

import hashlib
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class BackupValidator:
    """백업 파일 검증 및 복구"""

    @staticmethod
    def calculate_checksum(file_path: str) -> Optional[str]:
        """
        파일 체크섬 계산 (SHA256)
        
        Args:
            file_path: 파일 경로
            
        Returns:
            체크섬 문자열 또는 None
        """
        try:
            sha256_hash = hashlib.sha256()

            with open(file_path, "rb") as f:
                # 1MB씩 읽어서 해시 계산
                for byte_block in iter(lambda: f.read(1024 * 1024), b""):
                    sha256_hash.update(byte_block)

            return sha256_hash.hexdigest()

        except (OSError, IOError) as e:
            logger.error(f"체크섬 계산 실패: {e}")
            return None

    @staticmethod
    def validate_db_integrity(db_path: str) -> Tuple[bool, str]:
        """
        SQLite DB 무결성 검사
        
        Args:
            db_path: DB 파일 경로
            
        Returns:
            (성공 여부, 메시지)
        """
        if not os.path.exists(db_path):
            return False, "파일이 존재하지 않음"

        try:
            # 1. 파일 크기 확인
            file_size = os.path.getsize(db_path)
            if file_size == 0:
                return False, "빈 파일"

            # 2. SQLite 헤더 확인
            with open(db_path, 'rb') as f:
                header = f.read(16)
                if header[:16] != b'SQLite format 3\x00':
                    return False, "SQLite 형식이 아님"

            # 3. PRAGMA integrity_check
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()

            conn.close()

            if result and result[0] == 'ok':
                return True, "정상"
            else:
                return False, f"무결성 검사 실패: {result}"

        except sqlite3.DatabaseError as e:
            return False, f"DB 오류: {e}"
        except (sqlite3.OperationalError, ValueError, OSError) as e:
            return False, f"검증 오류: {e}"

    @staticmethod
    def validate_db_structure(db_path: str, expected_tables: list) -> Tuple[bool, str]:
        """
        DB 테이블 구조 확인
        
        Args:
            db_path: DB 파일 경로
            expected_tables: 필수 테이블 목록
            
        Returns:
            (성공 여부, 메시지)
        """
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 테이블 목록 조회
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)

            existing_tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            # 필수 테이블 확인
            missing_tables = set(expected_tables) - existing_tables

            if missing_tables:
                return False, f"누락된 테이블: {', '.join(missing_tables)}"

            return True, f"{len(existing_tables)}개 테이블 확인"

        except (sqlite3.OperationalError, ValueError, OSError) as e:
            return False, f"구조 검증 오류: {e}"

    @staticmethod
    def quick_validate(db_path: str) -> Dict:
        """
        빠른 검증 (무결성 + 기본 구조)
        
        Args:
            db_path: DB 파일 경로
            
        Returns:
            검증 결과 딕셔너리
        """
        result = {
            'valid': False,
            'file_exists': False,
            'file_size': 0,
            'integrity_ok': False,
            'structure_ok': False,
            'checksum': None,
            'message': '',
            'checked_at': datetime.now().isoformat()
        }

        try:
            # 파일 존재 확인
            if not os.path.exists(db_path):
                result['message'] = "파일 없음"
                return result

            result['file_exists'] = True
            result['file_size'] = os.path.getsize(db_path)

            # 무결성 검사
            integrity_ok, integrity_msg = BackupValidator.validate_db_integrity(db_path)
            result['integrity_ok'] = integrity_ok

            if not integrity_ok:
                result['message'] = integrity_msg
                return result

            # 기본 구조 확인 (핵심 테이블만)
            expected_tables = ['inventory', 'inventory_tonbag', 'stock_movement']
            structure_ok, structure_msg = BackupValidator.validate_db_structure(
                db_path, expected_tables
            )
            result['structure_ok'] = structure_ok

            if not structure_ok:
                result['message'] = structure_msg
                return result

            # 체크섬 계산
            result['checksum'] = BackupValidator.calculate_checksum(db_path)

            # 모두 성공
            result['valid'] = True
            result['message'] = "검증 성공"

        except (sqlite3.OperationalError, ValueError, OSError) as e:
            result['message'] = f"검증 오류: {e}"
            logger.error(f"백업 검증 오류: {e}", exc_info=True)

        return result


class AutoRecovery:
    """자동 복구 시스템"""

    def __init__(self, db_path: str, backup_dir: str):
        self.db_path = db_path
        self.backup_dir = backup_dir

    def check_and_recover(self) -> Tuple[bool, str]:
        """
        DB 상태 확인 및 필요시 자동 복구
        
        Returns:
            (복구 필요 여부, 메시지)
        """
        # 1. 현재 DB 검증
        validation = BackupValidator.quick_validate(self.db_path)

        if validation['valid']:
            return False, "DB 정상"

        # 2. DB 손상 - 복구 필요
        logger.warning(f"DB 손상 감지: {validation['message']}")

        # 3. 최신 백업 찾기
        latest_backup = self._find_latest_valid_backup()

        if not latest_backup:
            return False, "복구 가능한 백업 없음"

        # 4. 백업에서 복구
        try:
            # 손상된 DB 백업 (디버깅용)
            corrupted_backup = f"{self.db_path}.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists(self.db_path):
                os.rename(self.db_path, corrupted_backup)
                logger.info(f"손상된 DB 보관: {corrupted_backup}")

            # 백업에서 복원
            import shutil
            shutil.copy2(latest_backup, self.db_path)

            # 복원 검증
            restored_validation = BackupValidator.quick_validate(self.db_path)

            if restored_validation['valid']:
                logger.info(f"자동 복구 성공: {latest_backup}")
                return True, f"복구 완료 (백업: {os.path.basename(latest_backup)})"
            else:
                return False, "복구 후 검증 실패"

        except (sqlite3.OperationalError, ValueError, OSError) as e:
            logger.error(f"자동 복구 실패: {e}")
            return False, f"복구 오류: {e}"

    def _find_latest_valid_backup(self) -> Optional[str]:
        """
        가장 최신의 유효한 백업 파일 찾기
        
        Returns:
            백업 파일 경로 또는 None
        """
        try:
            if not os.path.exists(self.backup_dir):
                return None

            # 백업 파일 목록 (최신순)
            backups = sorted([
                os.path.join(self.backup_dir, f)
                for f in os.listdir(self.backup_dir)
                if f.endswith('.db')
            ], key=os.path.getmtime, reverse=True)

            # 유효한 백업 찾기
            for backup_path in backups:
                validation = BackupValidator.quick_validate(backup_path)

                if validation['valid']:
                    logger.info(f"유효한 백업 발견: {backup_path}")
                    return backup_path
                else:
                    logger.warning(f"백업 손상: {backup_path} - {validation['message']}")

            return None

        except (sqlite3.OperationalError, ValueError, OSError) as e:
            logger.error(f"백업 검색 오류: {e}")
            return None


__all__ = ['BackupValidator', 'AutoRecovery']
