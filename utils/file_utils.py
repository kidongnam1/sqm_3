"""
SQM - 파일/경로 유틸 (P2 config 분할)
=====================================
smart_path_recovery, get_recent_files, safe_file_backup.
경로는 인자로 받거나, None일 때 config에서 lazy 로드 (순환 참조 방지).
"""

import shutil
import time
from pathlib import Path
from typing import List, Optional, Tuple


def smart_path_recovery(
    invalid_path: str,
    file_extension: Optional[str] = None,
    base_dir: Optional[Path] = None,
) -> str:
    """
    유효하지 않은 경로에서 유사한 파일 자동 검색.

    Args:
        invalid_path: 유효하지 않은 파일 경로
        file_extension: 찾을 파일 확장자 (예: '.xlsx', '.pdf')
        base_dir: 검색 기준 디렉토리 (None이면 config.BASE_DIR 사용)

    Returns:
        복구된 경로 또는 빈 문자열
    """
    if not invalid_path:
        return ""

    invalid_path = Path(invalid_path)
    if invalid_path.exists():
        return str(invalid_path)

    parent_dir = invalid_path.parent
    if not parent_dir.exists():
        if base_dir is None:
            import config
            base_dir = config.BASE_DIR
        parent_dir = base_dir

    ext = file_extension if file_extension is not None else (invalid_path.suffix or ".*")
    try:
        pattern = f"*{ext}" if ext != ".*" else "*"
        candidates = list(parent_dir.glob(pattern))
        if not candidates:
            return ""

        original_name = invalid_path.stem.lower()
        best_match = None
        best_score = 0.0
        for candidate in candidates:
            if candidate.is_file():
                name = candidate.stem.lower()
                common = sum(1 for c in original_name if c in name)
                score = common / max(len(original_name), len(name), 1)
                if score > best_score:
                    best_score = score
                    best_match = candidate

        if best_match and best_score >= 0.3:
            return str(best_match)
        candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return str(candidates[0]) if candidates else ""
    except (ValueError, TypeError, AttributeError) as e:
        import logging
        logging.getLogger(__name__).debug(f"경로 복구 오류: {e}")
        return ""


def get_recent_files(
    directory: Optional[str] = None,
    extension: Optional[str] = None,
    limit: int = 10,
) -> List[str]:
    """
    최근 파일 목록 반환.

    Args:
        directory: 검색 디렉토리 (None이면 config.OUTPUT_DIR)
        extension: 확장자 필터
        limit: 최대 개수

    Returns:
        최근 파일 경로 목록
    """
    if directory is None:
        import config
        directory = config.OUTPUT_DIR
    search_dir = Path(directory)
    if not search_dir.exists():
        return []
    try:
        pattern = f"*{extension}" if extension else "*"
        files = [f for f in search_dir.glob(pattern) if f.is_file()]
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return [str(f) for f in files[:limit]]
    except (OSError, IOError, PermissionError):
        return []


def safe_file_backup(
    source_path: str,
    backup_dir: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    PermissionError 방지 안전 백업.

    Args:
        source_path: 백업할 파일 경로
        backup_dir: 백업 디렉토리 (None이면 config.BACKUP_DIR)

    Returns:
        (success, backup_path 또는 error_message)
    """
    source = Path(source_path)
    if not source.exists():
        return False, f"파일 없음: {source_path}"

    if backup_dir is None:
        import config
        backup_dir = config.BACKUP_DIR
    backup_directory = Path(backup_dir)
    backup_directory.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_name = f"{source.stem}_{timestamp}{source.suffix}"
    backup_path = backup_directory / backup_name

    max_retries = 3
    retry_delay = 0.5
    for attempt in range(max_retries):
        try:
            try:
                with open(source, "rb"):
                    pass
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return False, f"파일 사용 중: {source_path}"

            shutil.copy2(source, backup_path)
            return True, str(backup_path)
        except PermissionError as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return False, f"권한 오류: {e}"
        except (OSError, IOError, PermissionError) as e:
            return False, f"백업 오류: {e}"

    return False, "백업 실패 (최대 재시도 초과)"
