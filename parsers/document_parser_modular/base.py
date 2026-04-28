"""
SQM 재고관리 시스템 - 문서 파서 기본 클래스
============================================

v3.6.0: document_parser_v2.py에서 분리

모듈 개요:
    문서 파서의 공통 기능을 제공합니다.
    - PDF 진단 (텍스트/이미지 판별)
    - 텍스트 추출
    - 문서 유형 감지

작성자: Ruby (남기동)
버전: v3.6.0
"""

import logging
import os
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# PDF 처리
try:
    from core.pdf_engine import open_pdf
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# Gemini API
try:
    HAS_NEW_GENAI = True
except ImportError:
    HAS_NEW_GENAI = False

# 점수 기반 문서 감지기
try:
    from ..document_detector import DocumentDetector, DocumentType
    HAS_DOCUMENT_DETECTOR = True
except ImportError:
    HAS_DOCUMENT_DETECTOR = False
    DocumentDetector = None
    DocumentType = None


class DocumentParserBase:
    """
    문서 파서 기본 클래스

    PDF 진단, 텍스트 추출, 문서 유형 감지 등 공통 기능을 제공합니다.

    Attributes:
        provider: AI provider ('gemini'|'openai'|'anthropic')
        gemini_api_key: Gemini API 키 (하위 호환)
        errors: 에러 목록
        warnings: 경고 목록

    Example:
        >>> parser = DocumentParserBase(gemini_api_key='your_key')
        >>> parser = DocumentParserBase(provider='openai', api_key='sk-...')
        >>> diagnosis = parser.diagnose_pdf('document.pdf')
        >>> print(diagnosis['detected_type'])
    """

    def __init__(
        self,
        gemini_api_key: str = None,
        *,
        provider: str = None,
        api_key: str = None,
    ):
        """
        Args:
            gemini_api_key: Gemini API 키 (하위 호환 — provider/api_key 미지정 시 사용)
            provider: AI provider ('gemini'|'openai'|'anthropic'). 미지정 시 ai_provider_config에서 읽기
            api_key: provider에 해당하는 API 키. 미지정 시 ai_provider_config에서 읽기

        Raises:
            ImportError: PyMuPDF가 설치되지 않은 경우
        """
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF가 설치되지 않았습니다: pip install pymupdf")

        # ── provider 결정 ──────────────────────────────────────────────────
        if provider:
            self.provider = provider.strip().lower()
        elif gemini_api_key:
            # 하위 호환: gemini_api_key만 주어진 경우
            self.provider = "gemini"
        else:
            # ai_provider_config에서 active_provider 읽기
            try:
                from react_api.services.ai_provider_config import get_ai_config
                cfg = get_ai_config()
                self.provider = cfg.get("active_provider", "gemini") or "gemini"
            except Exception:
                self.provider = "gemini"

        # ── API 키 결정 ────────────────────────────────────────────────────
        if api_key:
            _resolved_key = api_key.strip()
        elif gemini_api_key and self.provider == "gemini":
            _resolved_key = gemini_api_key.strip()
        else:
            try:
                from react_api.services.ai_provider_config import get_api_key
                _resolved_key = get_api_key(self.provider) or ""
            except Exception:
                _resolved_key = ""

        # 하위 호환: gemini_api_key 속성 유지
        self.gemini_api_key = _resolved_key if self.provider == "gemini" else (gemini_api_key or "")
        self._ai_api_key = _resolved_key

        self.errors: List[str] = []
        self.warnings: List[str] = []

    def _get_ai_key(self, provider: str = None) -> str:
        """현재 설정된 provider의 API 키 반환."""
        p = (provider or self.provider or "gemini").lower()
        if p == self.provider:
            return self._ai_api_key or ""
        try:
            from react_api.services.ai_provider_config import get_api_key
            return get_api_key(p) or ""
        except Exception:
            return ""

    def _get_ai_model(self, provider: str = None) -> str:
        """현재 설정된 provider의 모델명 반환."""
        p = (provider or self.provider or "gemini").lower()
        try:
            from react_api.services.ai_provider_config import get_ai_config
            cfg = get_ai_config()
            return cfg.get("models", {}).get(p, "") or ""
        except Exception:
            return ""

    # ---------------------------------------------------------------------
    # API-Only Parsing Gate
    # ---------------------------------------------------------------------
    def _require_gemini_api_key(self):
        """AI API 키 존재 여부 검증 게이트 (하위 호환 명칭 유지).

        - 키가 없으면 즉시 하드-스톱(예외)합니다.
        - 호출부(UI/엔진)에서 예외를 잡아 사용자에게 안내하도록 설계합니다.
        """
        key = self._ai_api_key or ""
        if not key or key.startswith('your-'):
            provider_name = self.provider.capitalize() if self.provider else "AI"
            raise RuntimeError(
                f"{provider_name} API Key가 필요합니다. "
                "설정(도구/설정 메뉴)에서 API Key를 입력한 뒤 다시 시도하세요."
            )

    def _gemini_with_retry(self, fn, *args, retries: int = 3, wait_seconds: float = 1.0, **kwargs):
        """Gemini 호출을 재시도 래핑합니다.

        - 네트워크/일시 장애/쿼터 등으로 발생하는 예외를 일정 횟수 재시도합니다.
        - API-only 정책에서 "실패 시 즉시 중단"은 유지하되, 현장 업무 중단을 줄이기 위한 최소 재시도입니다.

        Args:
            fn: 호출할 함수(예: gemini_parser.parse_packing_list)
            retries: 최대 시도 횟수(기본 3)
            wait_seconds: 재시도 간 대기(기본 1초)
        """
        last_err = None
        for i in range(max(1, int(retries))):
            try:
                return fn(*args, **kwargs)
            except (ValueError, TypeError, KeyError) as e:
                last_err = e
                logger.warning(f"[GEMINI] 호출 실패 ({i+1}/{retries}): {type(e).__name__}: {e}")
                if i < retries - 1 and wait_seconds:
                    try:
                        time.sleep(float(wait_seconds))
                    except (ValueError, TypeError, KeyError) as _e:
                        logger.debug(f"Suppressed: {_e}")
        raise last_err

    def diagnose_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        PDF 파일 진단 - 텍스트/이미지 판별
        
        Args:
            pdf_path: PDF 파일 경로
        
        Returns:
            Dict 포함 키:
                - is_text_pdf: 텍스트 PDF 여부
                - is_image_pdf: 이미지 PDF 여부
                - text_length: 추출된 텍스트 길이
                - page_count: 페이지 수
                - detected_type: 감지된 문서 유형
                - needs_gemini: Gemini API 필요 여부
        """
        doc = None
        try:
            doc = open_pdf(pdf_path)
            total_text = ""
            page_count = len(doc)

            for page in doc:
                total_text += page.get_text()

            text_length = len(total_text.strip())
            is_text_pdf = text_length > 200
            is_image_pdf = text_length < 200

            # 문서 유형 추정 (텍스트 PDF인 경우만)
            detected_type = "UNKNOWN"
            if is_text_pdf:
                detected_type = self._detect_document_type(total_text, pdf_path)

            return {
                'is_text_pdf': is_text_pdf,
                'is_image_pdf': is_image_pdf,
                'text_length': text_length,
                'page_count': page_count,
                'detected_type': detected_type,
                'needs_gemini': is_image_pdf
            }

        except (ValueError, TypeError, AttributeError) as e:
            self.errors.append(f"PDF 진단 실패: {e}")
            logger.error(f"PDF 진단 실패: {pdf_path} - {e}")
            return {
                'is_text_pdf': False,
                'is_image_pdf': True,
                'text_length': 0,
                'page_count': 0,
                'detected_type': 'UNKNOWN',
                'needs_gemini': True,
                'error': str(e)
            }
        finally:
            if doc is not None:
                try:
                    doc.close()
                except (ValueError, TypeError, AttributeError) as e:
                    logging.debug(f"PDF 닫기 실패 (무시됨): {e}")

    def _detect_document_type(self, text: str, file_path: str) -> str:
        """
        문서 유형 자동 감지
        
        점수 기반 감지기 사용, 실패 시 레거시 방식으로 폴백
        
        Args:
            text: PDF에서 추출한 텍스트
            file_path: 파일 경로 (로깅용)
        
        Returns:
            str: 'INVOICE', 'PACKING_LIST', 'BL', 'DO', 'UNKNOWN' 중 하나
        """
        if HAS_DOCUMENT_DETECTOR and DocumentDetector:
            try:
                detector = DocumentDetector()
                result = detector.detect(text, file_path)

                if result.confidence >= 0.5:
                    logger.info(f"[DETECT] 점수 기반 감지 성공: {result.doc_type.name} ({result.confidence:.1%})")
                    return result.doc_type.name
                else:
                    logger.warning(f"[DETECT] 점수 기반 감지 신뢰도 낮음: {result.confidence:.1%}, 폴백 시도")
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"[DETECT] 점수 기반 감지 실패: {e}, 레거시 방식 사용")

        return self._detect_document_type_legacy(text, file_path)

    def _detect_document_type_legacy(self, text: str, file_path: str) -> str:
        """
        레거시 문서 유형 감지 (정규식 기반)
        
        Args:
            text: PDF 텍스트
            file_path: 파일 경로
        
        Returns:
            str: 문서 유형
        """
        text_lower = text.lower()
        filename_lower = os.path.basename(file_path).lower()

        # 파일명 기반 우선 감지
        if 'invoice' in filename_lower or 'fa' in filename_lower:
            return 'INVOICE'
        if 'packing' in filename_lower or 'pl' in filename_lower:
            return 'PACKING_LIST'
        if 'bl' in filename_lower or 'lading' in filename_lower:
            return 'BL'
        if 'do' in filename_lower or 'delivery' in filename_lower:
            return 'DO'

        # 텍스트 내용 기반 감지
        invoice_keywords = ['factura', 'invoice', 'commercial invoice', 'proforma']
        packing_keywords = ['packing list', 'lista de empaque', 'folio']
        bl_keywords = ['bill of lading', 'b/l', 'shipper', 'consignee', 'notify party']
        do_keywords = ['delivery order', 'd/o', 'arrival', 'free time']

        scores = {
            'INVOICE': sum(1 for kw in invoice_keywords if kw in text_lower),
            'PACKING_LIST': sum(1 for kw in packing_keywords if kw in text_lower),
            'BL': sum(1 for kw in bl_keywords if kw in text_lower),
            'DO': sum(1 for kw in do_keywords if kw in text_lower)
        }

        max_type = max(scores, key=scores.get)
        if scores[max_type] > 0:
            logger.info(f"[DETECT] 레거시 감지: {max_type} (점수: {scores})")
            return max_type

        return 'UNKNOWN'

    def _extract_text(self, pdf_path: str) -> str:
        """
        PDF에서 전체 텍스트 추출
        
        Args:
            pdf_path: PDF 파일 경로
        
        Returns:
            str: 추출된 텍스트
        """
        doc = None
        try:
            doc = open_pdf(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text
        finally:
            if doc is not None:
                doc.close()
    # DEAD CODE REMOVED v8.6.4: _extract_text_all_pages()
    # 사유: 전체 코드베이스에서 호출 없음 (2026-03-28 감사)
    # 원본 20줄 제거


    def _pdf_to_images(self, pdf_path: str, max_pages: int = 5) -> List[bytes]:
        """
        PDF를 이미지로 변환 (Gemini Vision용)
        
        Args:
            pdf_path: PDF 파일 경로
            max_pages: 최대 변환 페이지 수
        
        Returns:
            List[bytes]: PNG 이미지 바이트 목록
        """
        doc = None
        try:
            doc = open_pdf(pdf_path)
            images = []

            for i, page in enumerate(doc):
                if i >= max_pages:
                    break

                # 고해상도 렌더링 (300 DPI)
                mat = fitz.Matrix(300/72, 300/72)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                images.append(img_bytes)

            return images
        finally:
            if doc is not None:
                doc.close()
