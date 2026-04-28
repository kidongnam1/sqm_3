"""
Excel 파일 열기/읽기 시 동일 이름 파일 열림 처리

같은 이름의 파일이 Excel 등에서 열려 있으면 PermissionError 발생.
에러 대신 사용자에게 "순번 붙여서 오픈할까요?" 또는 "파일 닫은 후 다시 시도" 안내.
"""
import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

MSG_SAME_OPEN = (
    "같은 이름의 파일이 열려있습니다.\n"
    "파일 이름에 순번을 붙여서 오픈할까요?"
)
MSG_CLOSE_RETRY = "파일을 닫은 후 다시 시도하세요."

# 하위 호환 별칭
_MSG_SAME_OPEN = MSG_SAME_OPEN
_MSG_CLOSE_RETRY = MSG_CLOSE_RETRY


def _get_path_with_sequence(original_path: str) -> str:
    """경로에 순번 추가 (file.xlsx → file_1.xlsx, 이미 있으면 _2, _3...)"""
    p = Path(original_path)
    parent = p.parent
    stem = p.stem
    ext = p.suffix
    for n in range(1, 100):
        candidate = parent / f"{stem}_{n}{ext}"
        if not candidate.exists():
            return str(candidate)
    return str(parent / f"{stem}_99{ext}")


def get_unique_excel_path(desired_path: str) -> str:
    """
    같은 이름의 Excel 파일이 있으면 숫자를 붙인 새 경로 반환.
    기존 파일은 덮어쓰지 않고, 새 파일은 file_1.xlsx, file_2.xlsx ... 로 저장.

    Args:
        desired_path: 사용자가 지정한 저장 경로 (예: C:/data/report.xlsx)

    Returns:
        존재하지 않으면 desired_path 그대로, 존재하면 stem_1.xlsx, stem_2.xlsx 중 비어 있는 첫 경로
    """
    p = Path(desired_path)
    if not p.exists():
        return desired_path
    return _get_path_with_sequence(desired_path)


def _try_copy_open_file(original_path: str, dest_path: str) -> bool:
    """열린 파일 복사 시도 (Excel이 읽기 공유 모드면 복사 가능)"""
    try:
        shutil.copy2(original_path, dest_path)
        return True
    except (OSError, IOError, PermissionError) as e:
        logger.debug(f"파일 복사 실패: {e}")
        return False


def open_excel_with_fallback(
    parent,
    file_path: str,
    *,
    ask_yes: Callable[[str, str], bool],
) -> bool:
    """
    Excel 파일을 기본 앱으로 열기. PermissionError 시 순번 붙여서 열기 제안.

    Returns:
        True: 열기 성공 (원본 또는 복사본)
        False: 사용자 취소 또는 실패
    """
    import platform
    import subprocess

    def _do_open(path: str) -> bool:
        try:
            if platform.system() == 'Windows':
                os.startfile(os.path.normpath(path))
            elif platform.system() == 'Darwin':
                subprocess.run(['open', path], check=False)
            else:
                subprocess.run(['xdg-open', path], check=False)
            return True
        except (OSError, IOError, PermissionError) as e:
            logger.debug(f"파일 열기 실패: {e}")
            return False

    if _do_open(file_path):
        return True

    if not ask_yes("파일 열기", MSG_SAME_OPEN):
        return False

    copy_path = _get_path_with_sequence(file_path)
    if not _try_copy_open_file(file_path, copy_path):
        return False
    return _do_open(copy_path)


def read_excel_with_fallback(
    parent,
    file_path: str,
    read_func: Callable[[str], Any],
    *,
    ask_yes: Callable[[str, str], bool],
    show_error: Callable[[str, str], None],
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Excel 읽기. PermissionError 시 순번 붙인 복사본으로 읽기 제안.

    Args:
        parent: 다이얼로그 부모
        file_path: 원본 경로
        read_func: 읽기 함수 (path -> df 등)
        ask_yes: (title, message) -> bool
        show_error: (title, message)

    Returns:
        (결과, 사용된_경로) — 실패 시 (None, None)
    """
    try:
        result = read_func(file_path)
        return (result, file_path)
    except (OSError, IOError, PermissionError) as e:
        logger.debug(f"Excel 읽기 실패: {e}")

    if not ask_yes("파일 읽기", MSG_SAME_OPEN):
        show_error("파일 읽기", MSG_CLOSE_RETRY)
        return (None, None)

    copy_path = _get_path_with_sequence(file_path)
    if not _try_copy_open_file(file_path, copy_path):
        show_error("파일 읽기", MSG_CLOSE_RETRY)
        return (None, None)
    try:
        result = read_func(copy_path)
        return (result, copy_path)
    except (OSError, IOError, PermissionError) as e:
        logger.debug(f"복사본 읽기 실패: {e}")
        show_error("파일 읽기", MSG_CLOSE_RETRY)
        return (None, None)
