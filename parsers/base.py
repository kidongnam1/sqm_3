"""
SQM 재고관리 - 파서 기본 클래스
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional


class BaseParser(ABC):
    """파서 기본 클래스"""

    def __init__(self):
        self.source_file: Optional[str] = None
        self.errors: list = []

    @abstractmethod
    def parse(self, file_path: str) -> Any:
        """파일 파싱 (서브클래스에서 구현)"""
        raise NotImplementedError("하위 클래스에서 구현 필요")

    @abstractmethod
    def validate(self, data: Any) -> bool:
        """데이터 유효성 검증"""
        raise NotImplementedError("하위 클래스에서 구현 필요")

    def get_file_extension(self, file_path: str) -> str:
        """파일 확장자 반환"""
        return Path(file_path).suffix.lower()

    def add_error(self, message: str):
        """에러 추가"""
        self.errors.append(message)

    def clear_errors(self):
        """에러 초기화"""
        self.errors.clear()

    def has_errors(self) -> bool:
        """에러 존재 여부"""
        return len(self.errors) > 0
