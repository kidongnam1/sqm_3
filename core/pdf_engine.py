# -*- coding: utf-8 -*-
"""
core/pdf_engine.py
==================
SQM v8.6.7 — PDF 처리 공통 엔진 (PC / Android Termux 호환)

목적:
    PyMuPDF(fitz)가 설치된 PC 환경과
    pdf2image로 대체한 Android Termux 환경에서
    동일한 인터페이스로 PDF 처리를 수행한다.

사용법:
    from core.pdf_engine import pdf_to_images, pdf_to_text, PDF_ENGINE

    # PDF → 이미지 변환
    images = pdf_to_images("path/to/file.pdf", dpi=300)
    for img_bytes in images:
        # img_bytes: PNG bytes

    # PDF → 텍스트 추출
    pages = pdf_to_text("path/to/file.pdf")
    for page_text in pages:
        print(page_text)

    # 현재 엔진 확인
    print(PDF_ENGINE)  # "pymupdf" 또는 "pdf2image"

작성일: 2026-04-04
"""

import io
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── 엔진 감지 ────────────────────────────────────────────────
try:
    import fitz  # PyMuPDF
    PDF_ENGINE = "pymupdf"
    logger.debug("[pdf_engine] PyMuPDF(fitz) 감지 → PC 모드")
except ImportError:
    fitz = None
    PDF_ENGINE = "pdf2image"
    logger.debug("[pdf_engine] PyMuPDF 없음 → pdf2image 모드 (Android)")

try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


# ── 공개 API ─────────────────────────────────────────────────

def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[bytes]:
    """
    PDF 파일을 페이지별 PNG bytes 리스트로 변환.

    Args:
        pdf_path: PDF 파일 경로
        dpi    : 해상도 (기본 300)

    Returns:
        List[bytes]: 각 페이지의 PNG bytes

    Raises:
        ImportError: PDF 처리 엔진이 없을 때
        FileNotFoundError: PDF 파일이 없을 때
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 파일 없음: {pdf_path}")

    if PDF_ENGINE == "pymupdf":
        return _pymupdf_to_images(str(path), dpi)
    elif HAS_PDF2IMAGE:
        return _pdf2image_to_images(str(path), dpi)
    else:
        raise ImportError(
            "PDF 이미지 변환 엔진이 없습니다.\n"
            "PC:      pip install pymupdf\n"
            "Android: pip install pdf2image"
        )


def pdf_to_text(pdf_path: str) -> List[str]:
    """
    PDF 파일에서 페이지별 텍스트 추출.

    Args:
        pdf_path: PDF 파일 경로

    Returns:
        List[str]: 각 페이지의 텍스트
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 파일 없음: {pdf_path}")

    if PDF_ENGINE == "pymupdf":
        return _pymupdf_to_text(str(path))
    elif HAS_PDFPLUMBER:
        return _pdfplumber_to_text(str(path))
    else:
        raise ImportError(
            "PDF 텍스트 추출 엔진이 없습니다.\n"
            "pip install pdfplumber"
        )


def pdf_page_count(pdf_path: str) -> int:
    """PDF 페이지 수 반환."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 파일 없음: {pdf_path}")

    if PDF_ENGINE == "pymupdf":
        doc = fitz.open(str(path))
        count = len(doc)
        doc.close()
        return count
    elif HAS_PDFPLUMBER:
        with pdfplumber.open(str(path)) as pdf:
            return len(pdf.pages)
    else:
        raise ImportError("PDF 엔진이 없습니다.")


def open_pdf(pdf_path: str):
    """
    PDF 문서 객체 반환 (저수준 접근용).

    Returns:
        pymupdf 환경: fitz.Document
        pdf2image 환경: pdfplumber.PDF
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 파일 없음: {pdf_path}")

    if PDF_ENGINE == "pymupdf":
        return fitz.open(str(path))
    elif HAS_PDFPLUMBER:
        return pdfplumber.open(str(path))
    else:
        raise ImportError("PDF 엔진이 없습니다.")


def is_available() -> bool:
    """PDF 처리 가능 여부 반환."""
    return PDF_ENGINE == "pymupdf" or HAS_PDF2IMAGE


def engine_info() -> dict:
    """현재 엔진 정보 반환."""
    return {
        "engine"      : PDF_ENGINE,
        "pymupdf"     : PDF_ENGINE == "pymupdf",
        "pdf2image"   : HAS_PDF2IMAGE,
        "pdfplumber"  : HAS_PDFPLUMBER,
        "available"   : is_available(),
    }


# ── 내부 구현 ─────────────────────────────────────────────────

def _pymupdf_to_images(pdf_path: str, dpi: int) -> List[bytes]:
    """PyMuPDF로 PDF → PNG bytes 변환 (PC 전용)."""
    result = []
    doc = fitz.open(pdf_path)
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        for page in doc:
            pix = page.get_pixmap(matrix=mat)
            result.append(pix.tobytes("png"))
    finally:
        doc.close()
    logger.debug(f"[pdf_engine] pymupdf → {len(result)}페이지 변환 완료")
    return result


def _pdf2image_to_images(pdf_path: str, dpi: int) -> List[bytes]:
    """pdf2image로 PDF → PNG bytes 변환 (Android 대체)."""
    from pdf2image import convert_from_path
    pages = convert_from_path(pdf_path, dpi=dpi)
    result = []
    for page in pages:
        buf = io.BytesIO()
        page.save(buf, format="PNG")
        result.append(buf.getvalue())
    logger.debug(f"[pdf_engine] pdf2image → {len(result)}페이지 변환 완료")
    return result


def _pymupdf_to_text(pdf_path: str) -> List[str]:
    """PyMuPDF로 텍스트 추출 (PC 전용)."""
    result = []
    doc = fitz.open(pdf_path)
    try:
        for page in doc:
            result.append(page.get_text())
    finally:
        doc.close()
    return result


def _pdfplumber_to_text(pdf_path: str) -> List[str]:
    """pdfplumber로 텍스트 추출 (Android 대체)."""
    result = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            result.append(page.extract_text() or "")
    return result
