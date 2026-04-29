"""
SQM 재고관리 시스템 - Gemini AI 파서 (v2.5.4)

★ 모든 문서 파싱을 Gemini API로 처리 ★

장점:
1. PDF 형식이 달라져도 자동 적응
2. 유럽식/미국식 숫자 자동 인식
3. 이미지 PDF(스캔)도 처리 가능 (Vision)
4. 정규식 유지보수 불필요

사용법:
    from gemini_parser import GeminiDocumentParser
    
    parser = GeminiDocumentParser(api_key="your-api-key")
    
    # Packing List 파싱
    result = parser.parse_packing_list("2200033057_PackingList1.pdf")
    
    # Invoice 파싱
    result = parser.parse_invoice("2200033057_FA.pdf")
    
    # B/L 파싱
    result = parser.parse_bl("2200033057_BL.pdf")
    
    # D/O 파싱
    result = parser.parse_do("MAEU258468669_DO.pdf")

Author: Ruby
Version: 2.5.4
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
try:
    from engine_modules.constants import CUSTOMER_NAME_MAP as _CUST_MAP
except ImportError:
    _CUST_MAP = {}
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _sanitize_prompt_hint(hint: str, max_len: int = 300) -> str:
    """프롬프트 인젝션 방지 — 선사 힌트 정제 (SEC-C2 P0 패치).

    - 길이 제한 (기본 300자)
    - ASCII 제어문자 제거 (탭·줄바꿈 허용)
    - 길이 초과 시 WARNING 로그
    """
    if not hint:
        return ""
    # 제어문자 제거 (탭/LF/CR 허용, 나머지 C0/C1 제거)
    safe = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', hint)
    safe = safe.strip()
    if len(safe) > max_len:
        logger.warning(
            f"[SecPatch] 선사 힌트 길이 초과({len(hint)}자) — {max_len}자로 잘림"
        )
        safe = safe[:max_len]
    return safe


# Gemini API
try:
    from google import genai
    from google.genai import types
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    logger.warning("google-genai 미설치 - pip install google-genai")

# PyMuPDF (PDF → 이미지 변환)
try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logger.warning("PyMuPDF 미설치 - pip install pymupdf")


# =============================================================================
# ★★★ v2.9.52: 유럽식 숫자 변환 유틸리티 ★★★
# =============================================================================

def parse_euro_weight(value) -> float:
    """
    유럽식/미국식 숫자를 올바르게 kg 단위로 변환
    
    유럽식 예시 (칠레 SQM Packing List):
    - 5.001 → 5001 kg (점이 천단위 구분자)
    - 5.131,250 → 5131.250 kg (점이 천단위, 쉼표가 소수점)
    
    미국식 예시:
    - 5,001 → 5001 kg (쉼표가 천단위 구분자)
    - 5,131.250 → 5131.250 kg (쉼표가 천단위, 점이 소수점)
    
    Args:
        value: 문자열 또는 숫자
    
    Returns:
        float: kg 단위 중량
    """
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        # 이미 숫자이면 크기 검증
        # LOT당 일반적으로 4000~6000 kg 범위
        if value < 100:
            # 100 미만이면 MT 단위일 가능성 → kg로 변환
            return value * 1000
        return float(value)

    s = str(value).strip()
    if not s:
        return 0.0

    # 숫자와 구분자만 추출
    s = re.sub(r'[^\d.,]', '', s)

    if not s:
        return 0.0

    try:
        # 케이스 1: 둘 다 있는 경우
        if ',' in s and '.' in s:
            # 어떤게 마지막인지 확인
            last_comma = s.rfind(',')
            last_dot = s.rfind('.')

            if last_comma > last_dot:
                # 유럽식: 5.131,250 → 5131.250
                s = s.replace('.', '')  # 천단위 제거
                s = s.replace(',', '.')  # 소수점 변환
            else:
                # 미국식: 5,131.250 → 5131.250
                s = s.replace(',', '')  # 천단위 제거

        # 케이스 2: 점만 있는 경우
        elif '.' in s:
            parts = s.split('.')
            if len(parts) == 2:
                # 소수점 뒤가 3자리이고, 정수부가 1~3자리면 유럽식 천단위 구분자로 간주
                if len(parts[1]) == 3 and len(parts[0]) <= 3:
                    # 유럽식 천단위: 5.001 → 5001
                    s = s.replace('.', '')
                # 그 외는 소수점으로 처리

        # 케이스 3: 쉼표만 있는 경우
        elif ',' in s:
            parts = s.split(',')
            if len(parts) == 2:
                # 쉼표 뒤가 3자리면 천단위 구분자
                if len(parts[1]) == 3:
                    # 미국식 천단위: 5,001 → 5001
                    s = s.replace(',', '')
                else:
                    # 유럽식 소수점: 5,25 → 5.25
                    s = s.replace(',', '.')
            else:
                # 여러 쉼표: 1,000,000 → 1000000
                s = s.replace(',', '')

        result = float(s)

        # 크기 검증: LOT 중량은 보통 1000~10000 kg
        # 너무 작으면 MT 단위일 가능성
        if result < 100:
            result = result * 1000

        return result

    except (ValueError, TypeError):
        return 0.0


def _make_lot_fingerprint(lot_data: dict) -> str:
    """
    LOT 행 중복 제거용 fingerprint 생성.
    키: lot_no + container_no(공백/하이픈 제거) + net_weight_kg
    """
    if not isinstance(lot_data, dict):
        return ""
    lot_no = str(lot_data.get('lot_no', '') or '').strip().upper()
    container_no = str(lot_data.get('container_no', '') or '').strip().upper()
    container_no = re.sub(r'[\s-]+', '', container_no)
    net_weight_kg = parse_euro_weight(lot_data.get('net_weight_kg', 0))
    return f"{lot_no}|{container_no}|{net_weight_kg:.3f}"


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class LOTItem:
    """
    LOT 상세 정보 (Packing List 1행 = 1 LOTItem)

    Fields:
        list_no       : Packing List 행 번호 (LIST 1, 2 ...)
        container_no  : 컨테이너 번호
        lot_no        : LOT 번호 (10자리, SQM 기준)
        lot_sqm       : LOT SQM (6자리, 공급사 내부 코드)
        mxbg          : 톤백 수량
        net_weight_kg : LOT 순중량 (kg, 소수점 포함)
        gross_weight_kg: LOT 총중량 (kg)
        del_no        : Delivery Number — 납품번호. Packing List의 LOT별
                        납품 문서 번호(SAP 연동 또는 공급사 납품서 번호).
                        항상 기재되지 않으며 현재 DB 미저장(참조용).
        al_no         : Allocation Number — 할당번호. Packing List의 LOT별
                        판매 할당 참조 번호. 고객사별 할당 관리 코드.
                        항상 기재되지 않으며 현재 DB 미저장(참조용).
    """
    list_no: int = 0
    container_no: str = ""
    lot_no: str = ""
    lot_sqm: str = ""
    mxbg: int = 10
    net_weight_kg: float = 0.0
    gross_weight_kg: float = 0.0
    del_no: str = ""   # Delivery Number (납품번호) — Packing List LOT별, DB 미저장
    al_no: str = ""    # Allocation Number (할당번호) — Packing List LOT별, DB 미저장


@dataclass
class PackingListResult:
    """Packing List 파싱 결과"""
    success: bool = False
    folio: str = ""
    product: str = ""
    packing: str = ""
    code: str = ""
    vessel: str = ""
    customer: str = ""
    destination: str = ""
    lots: List[LOTItem] = field(default_factory=list)
    total_net_weight_kg: float = 0.0
    total_gross_weight_kg: float = 0.0
    total_lots: int = 0              # len(lots) 집계 (비교 스크립트 호환용)
    total_maxibag: int = 0           # sum(lot.mxbg for lot in lots) 집계
    containers: List[str] = field(default_factory=list)  # unique container_no 목록
    bag_weight_kg: int = None         # v8.6.1: None=미설정(DEFAULT_TONBAG_WEIGHT fallback)
    raw_response: str = ""
    error_message: str = ""


@dataclass
class InvoiceResult:
    """Invoice 파싱 결과"""
    success: bool = False
    sap_no: str = ""
    invoice_no: str = ""
    bl_no: str = ""
    product: str = ""
    product_code: str = ""
    quantity_mt: float = 0.0
    unit_price: float = 0.0
    total_amount: float = 0.0
    currency: str = "USD"
    incoterm: str = ""
    origin: str = ""
    destination: str = ""
    vessel: str = ""
    net_weight_kg: float = 0.0
    gross_weight_kg: float = 0.0
    package_count: int = 0
    package_type: str = ""
    lot_numbers: List[str] = field(default_factory=list)
    raw_response: str = ""
    error_message: str = ""


@dataclass
class ContainerDetail:
    """컨테이너 상세 정보"""
    container_no: str = ""
    seal_no: str = ""
    weight_kg: float = 0.0
    size_type: str = ""
    free_time: str = ""
    return_place: str = ""


@dataclass
class BLResult:
    """B/L 파싱 결과"""
    success: bool = False
    bl_no: str = ""
    booking_no: str = ""
    sap_no: str = ""
    vessel: str = ""
    voyage: str = ""
    port_of_loading: str = ""
    port_of_discharge: str = ""
    shipper: str = ""
    consignee: str = ""
    containers: List[ContainerDetail] = field(default_factory=list)
    container_numbers: List[str] = field(default_factory=list)  # 단순 목록
    total_containers: int = 0
    total_weight_kg: float = 0.0
    gross_weight_kg: float = 0.0   # alias for total_weight_kg (비교 스크립트 호환용)
    shipped_date: str = ""
    ship_date: str = ""  # BL 선적일 (shipped_date와 동일, 호출부 ship_date 사용)
    shipped_on_board_date: str = ""  # v5.8.6.B: BLData 필드명과 통일
    eta: str = ""
    raw_response: str = ""
    error_message: str = ""
    # v6.4.0: 선사 정보 (bl_carrier_registry 통합)
    carrier_id: str = ""          # 예: "MSC", "MAERSK"
    carrier_name: str = ""        # 예: "Mediterranean Shipping Company"
    bl_equals_booking_no: bool = False  # Maersk처럼 BL No == Booking No인 경우 True


@dataclass
class DOResult:
    """D/O 파싱 결과"""
    success: bool = False
    do_no: str = ""
    bl_no: str = ""
    bl_no_full: str = ""
    vessel: str = ""
    voyage: str = ""
    port_of_loading: str = ""
    port_of_discharge: str = ""
    shipper: str = ""
    consignee: str = ""
    containers: List[ContainerDetail] = field(default_factory=list)
    container_numbers: List[str] = field(default_factory=list)  # 단순 목록
    total_weight_kg: float = 0.0
    gross_weight_kg: float = 0.0   # alias for total_weight_kg (비교 스크립트 호환용)
    mrn: str = ""                  # 세관신고번호 MRN (MSC/HAPAG/ONE D/O 전용)
    msn: str = ""                  # 세관신고번호 MSN (MSC/HAPAG/ONE D/O 전용)
    arrival_date: str = ""
    all_dates_found: List[str] = field(default_factory=list)  # v5.8.6.B: 문서 내 모든 날짜
    issue_date: str = ""
    release_date: str = ""
    raw_response: str = ""
    error_message: str = ""


# =============================================================================
# Gemini Document Parser
# =============================================================================

class GeminiDocumentParser:
    """
    Gemini API 기반 문서 파서
    
    모든 문서(Packing List, Invoice, B/L, D/O)를 
    Gemini AI로 파싱하여 정확도를 높입니다.
    
    ★★★ v2.7.1: 모델 자동 검증 + 대체 로직 추가 ★★★
    """

    # 권장 모델 후보 (우선순위 순) - v3.6.9 업데이트
    FALLBACK_MODELS = [
        "gemini-2.5-flash",        # ★ 프로덕션 권장 (Stable)
        "gemini-2.5-flash-lite",   # 경량 모델
        "gemini-2.0-flash",        # ⚠️ 2026.3.31 종료 예정 (deprecated)
        "gemini-1.5-flash",        # ⚠️ 레거시 (최후 수단)
    ]

    def __init__(self, api_key: Optional[str] = None,
                 db=None) -> None:
        """
        Args:
            api_key: Gemini API Key (없으면 환경변수/config에서 로드)
            db: SQMDatabase 인스턴스 (파싱 통계 기록용, 선택)  # v8.2.4
        """
        if not HAS_GEMINI:
            raise ImportError("google-genai가 필요합니다: pip install google-genai")

        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF가 필요합니다: pip install pymupdf")

        # API Key 로드
        if api_key is None:
            api_key = self._load_api_key()

        if not api_key:
            raise ValueError("Gemini API Key가 필요합니다")

        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.timeout_seconds = 60  # v4.1.7: API 타임아웃 (초) — PDF 이미지 파싱용 확장
        self._db = db  # v8.2.4: 파싱 통계 기록용 DB

        # 설정된 모델 우선 (config/settings.ini/환경변수 GEMINI_MODEL)
        self._preferred_model = self._load_preferred_model()

        # ★★★ v2.7.1: 모델 자동 검증 ★★★
        self.model = self._validate_and_select_model()

        logger.info(f"[GeminiParser] 초기화 완료 (모델: {self.model}, 타임아웃: {self.timeout_seconds}초)")

    def _log_parse_result(self, doc_type: str, source_file: str = '',
                          success: bool = False, bl_no: str = '',
                          lot_count: int = 0, method: str = '',
                          error_msg: str = '', duration_ms: int = 0,
                          carrier_id: str = '') -> None:
        """v8.2.4: 파싱 결과를 parsing_log 테이블에 기록.
        DB 미설정 시 조용히 스킵.
        """
        if not self._db:
            return
        try:
            self._db.execute(
                """INSERT INTO parsing_log
                   (doc_type, source_file, carrier_id, success, bl_no,
                    lot_count, method, error_msg, duration_ms)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (doc_type, source_file or '', carrier_id or '',
                 1 if success else 0, bl_no or '',
                 lot_count, method or '', error_msg or '', duration_ms)
            )
        except Exception as _le:
            logger.debug(f"[GeminiParser] parsing_log 기록 스킵: {_le}")

    def _load_preferred_model(self) -> str | None:
        """config/settings.ini/환경변수 GEMINI_MODEL 반환 (없으면 None)."""
        try:
            from core.config import GEMINI_MODEL
            if GEMINI_MODEL and str(GEMINI_MODEL).strip():
                return str(GEMINI_MODEL).strip()
        except (ValueError, TypeError, KeyError, IndexError) as _e:
            logger.debug(f"Suppressed: {_e}")
        return None

    def _validate_and_select_model(self) -> str:
        """
        v2.7.1: 모델 존재 확인 및 자동 대체
        
        1. 설정된 모델(GEMINI_MODEL) 우선 사용
        2. ListModels로 사용 가능한 모델 확인
        3. 후보(FALLBACK_MODELS) 중 선택
        4. 기본값 반환
        """
        default_model = "gemini-2.5-flash"

        try:
            # 사용 가능한 모델 목록 조회
            available_models = set()
            try:
                models_response = self.client.models.list()
                for model in models_response:
                    model_name = getattr(model, 'name', str(model))
                    # 'models/gemini-1.5-flash' -> 'gemini-1.5-flash'
                    if '/' in model_name:
                        model_name = model_name.split('/')[-1]
                    available_models.add(model_name)

                logger.info(f"[GeminiParser] 사용 가능한 모델 {len(available_models)}개 확인")
            except (ValueError, TypeError, KeyError) as list_error:
                logger.warning(f"[GeminiParser] 모델 목록 조회 실패: {list_error}")
                if self._preferred_model:
                    return self._preferred_model
                return default_model

            # 1순위: 설정된 모델이 사용 가능하면 사용
            if self._preferred_model:
                if self._preferred_model in available_models:
                    logger.info(f"[GeminiParser] 설정 모델 사용: {self._preferred_model}")
                    return self._preferred_model
                for av in available_models:
                    if self._preferred_model in av or av.startswith(self._preferred_model):
                        logger.info(f"[GeminiParser] 설정 모델(부분매칭) 사용: {av}")
                        return av

            # 2순위: 후보 모델 중 사용 가능한 것 선택
            for candidate in self.FALLBACK_MODELS:
                if candidate in available_models:
                    logger.info(f"[GeminiParser] 모델 선택: {candidate}")
                    return candidate

                # 부분 매칭 시도 (gemini-1.5-flash-xxx 형태)
                for available in available_models:
                    if candidate in available or available.startswith(candidate):
                        logger.info(f"[GeminiParser] 모델 선택 (부분매칭): {available}")
                        return available

            # 사용 가능한 모델 중 generateContent 지원하는 것 선택
            for available in available_models:
                if 'gemini' in available.lower() and 'vision' not in available.lower():
                    logger.info(f"[GeminiParser] 대체 모델 선택: {available}")
                    return available

            logger.warning(f"[GeminiParser] 적합한 모델을 찾지 못함, 기본값 사용: {default_model}")
            return default_model

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"[GeminiParser] 모델 검증 오류: {e}")
            return default_model

    def is_available(self) -> bool:
        """API 연결 상태 확인 (v2.7.1 개선)"""
        try:
            # 간단한 테스트 호출
            test_response = self.client.models.generate_content(
                model=self.model,
                contents="Hello"
            )
            return bool(test_response.text)
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"[GeminiParser] API 연결 확인 실패: {e}")

            # 404 오류 시 모델 재선택 시도
            if '404' in str(e) or 'not found' in str(e).lower():
                logger.info("[GeminiParser] 모델 재선택 시도...")
                self.model = self._validate_and_select_model()

            return False

    @property
    def model_name(self) -> str:
        """현재 모델명 반환"""
        return self.model

    def _load_api_key(self) -> str:
        """API Key 로드 (환경변수 → config)"""
        # 1. 환경변수
        key = os.environ.get('GEMINI_API_KEY')
        if key:
            return key

        # 2. config.py
        try:
            from core.config import GEMINI_API_KEY
            if GEMINI_API_KEY:
                return GEMINI_API_KEY
        except ImportError as _e:
            logger.debug(f"[gemini_parser] 무시: {_e}")

        return ""

    def _pdf_to_images(self, pdf_path: str, dpi: int = 150) -> List[bytes]:
        """PDF를 이미지로 변환 (v2.9.41: 안전한 파일 핸들링)"""
        doc = None
        try:
            doc = fitz.open(pdf_path)
            images = []

            for page in doc:
                # 페이지를 이미지로 렌더링
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                images.append(img_bytes)

            return images
        finally:
            if doc:
                doc.close()

    def _call_gemini_pdf(self, prompt: str, pdf_path: str) -> str:
        """v8.0.0 [PDF-DIRECT]: PDF를 이미지 변환 없이 직접 Gemini API로 전송.
        - 텍스트 레이어 보존 → 정확도 향상
        - PyMuPDF 불필요
        - Gemini 1.5/2.0/2.5 모두 application/pdf 지원
        """
        try:
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            logger.info(f"[GeminiParser] PDF 직접 전송: {len(pdf_bytes):,} bytes")
            return self._call_gemini(prompt, pdf_bytes, mime_type='application/pdf')
        except Exception as e:
            logger.warning(f"[GeminiParser] PDF 직접 전송 실패 → 이미지 변환 폴백: {e}")
            # 폴백: 기존 이미지 방식
            images = self._pdf_to_images(pdf_path)
            if not images:
                return ''
            return self._call_gemini(prompt, images[0])

    def _call_gemini(self, prompt: str, image_bytes: bytes = None, mime_type: str = "image/png") -> str:
        """Gemini API 호출
        
        v3.8.4: gemini-2.5-flash thinking model 대응
        - response.text가 빈 경우 candidates[0].content.parts에서 직접 추출
        - image_bytes: PNG/JPEG 등 캡처 이미지 지원 (mime_type 지정 가능)
        """
        try:
            contents = []

            if image_bytes:
                # 이미지 + 텍스트 (캡처 이미지: image/png, image/jpeg 등)
                contents.append(
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type
                    )
                )

            contents.append(prompt)

            # v2.6.0: 타임아웃 적용
            response = self._call_api_with_timeout(contents)

            # v3.8.4: thinking model 대응 - 안전한 텍스트 추출
            text = self._extract_response_text(response)

            if text:
                logger.debug(f"[GeminiParser] 응답 길이: {len(text)} chars")
            else:
                logger.warning("[GeminiParser] 빈 응답 수신")

            return text

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"[GeminiParser] API 호출 오류: {e}")
            raise

    def _extract_response_text(self, response) -> str:
        """Gemini 응답에서 텍스트 안전 추출
        
        gemini-2.5-flash (thinking model) 대응:
        - response.text가 빈 경우 candidates → parts에서 직접 추출
        - thinking part (thought=True)는 건너뛰고 실제 응답만 추출
        """
        # 1차: response.text 시도
        try:
            text = response.text
            if text and text.strip():
                return text.strip()
        except (AttributeError, ValueError, IndexError) as _e:
            logger.debug(f"Suppressed: {_e}")

        # 2차: candidates[0].content.parts에서 직접 추출
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    parts = candidate.content.parts or []
                    text_parts = []
                    for part in parts:
                        # thinking part 건너뛰기
                        if hasattr(part, 'thought') and part.thought:
                            continue
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                    if text_parts:
                        combined = '\n'.join(text_parts).strip()
                        logger.info(f"[GeminiParser] parts에서 텍스트 추출: {len(combined)} chars")
                        return combined
        except (AttributeError, IndexError, TypeError) as e:
            logger.debug(f"[GeminiParser] parts 추출 실패: {e}")

        # 3차: 전체 응답을 문자열로
        try:
            text = str(response)
            if len(text) > 10:
                logger.warning("[GeminiParser] str(response) 폴백 사용")
                return text
        except (ValueError, TypeError, AttributeError) as _e:
            logger.debug(f"Suppressed: {_e}")

        return ""

    def _call_api_with_timeout(self, contents):
        """
        API 호출 (타임아웃 + OCR 자동 튜닝 적용) - v3.0
        
        429 오류 발생 시 자동으로 동시성을 줄이고,
        성공률이 높으면 동시성을 늘립니다.
        """
        import concurrent.futures
        import time

        # OCR 튜너 가져오기
        try:
            from ocr_auto_tuner import get_ocr_tuner
            tuner = get_ocr_tuner()
        except ImportError:
            tuner = None

        def api_call():
            # v5.5.1: gemini-2.5-flash thinking 모델 대응 — thinking이 토큰을 많이 쓰면 JSON이 잘림
            # → max_output_tokens 65536으로 상향, thinking_budget 2048로 제한(단순 추출 작업에 적합)
            thinking_cfg = getattr(types, "ThinkingConfig", None)
            config_kw = {
                "temperature": 0.1,
                "max_output_tokens": 65536,
            }
            if thinking_cfg is not None:
                try:
                    config_kw["thinking_config"] = thinking_cfg(thinkingBudget=2048)
                except (ValueError, TypeError, KeyError, IndexError) as _e:
                    logger.debug(f"ThinkingConfig 미적용(무시): {_e}")
            return self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(**config_kw)
            )

        # 세마포어 획득 (튜너 사용 시)
        if tuner:
            if not tuner.acquire():
                raise Exception("OCR Circuit Breaker가 열려 있습니다. 잠시 후 재시도하세요.")

        start_time = time.time()
        is_429 = False
        success = False

        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(api_call)
                try:
                    result = future.result(timeout=self.timeout_seconds)
                    success = True
                    return result
                except concurrent.futures.TimeoutError:
                    logger.error(f"[GeminiParser] API 타임아웃 ({self.timeout_seconds}초)")
                    raise TimeoutError(f"Gemini API 응답 시간 초과 ({self.timeout_seconds}초)")
        except (ValueError, TypeError, AttributeError) as e:
            error_msg = str(e).lower()
            if '429' in error_msg or 'rate limit' in error_msg or 'quota' in error_msg:
                is_429 = True
                logger.warning("[GeminiParser] 429 Rate Limit 감지")
            raise
        finally:
            response_time = time.time() - start_time

            # 튜너에 결과 기록
            if tuner:
                tuner.record_result(
                    success=success,
                    response_time=response_time,
                    is_429=is_429,
                    error_message="" if success else "API 오류"
                )
                tuner.release()

                # 튜너 상태 로깅 (디버그)
                if logger.isEnabledFor(logging.DEBUG):
                    stats = tuner.stats
                    logger.debug(
                        f"[OCR튜너] 동시성={stats['concurrency']}, "
                        f"성공률={stats['success_rate']:.1%}, "
                        f"응답시간={response_time:.1f}s"
                    )

    def _extract_json(self, text: str) -> Dict:
        """응답에서 JSON 추출
        
        v3.8.4: 다단계 JSON 추출 전략
        1. ```json ... ``` 코드블록 (2.5-flash thinking 대응: 마지막 블록 우선)
        2. ``` ... ``` 일반 코드블록
        3. 전체 텍스트 직접 파싱
        4. { } 브레이스 추출
        """
        if not text or not text.strip():
            logger.warning("[GeminiParser] JSON 추출: 빈 텍스트")
            return {}

        # 1차: ```json ... ``` 블록 (여러 개면 마지막 사용 — gemini-2.5-flash thinking이 앞에 올 수 있음)
        json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', text)
        if json_blocks:
            for block in reversed(json_blocks):
                try:
                    parsed = json.loads(block.strip())
                    if parsed:
                        return parsed
                except json.JSONDecodeError as _e:
                    logger.debug(f"Suppressed: {_e}")

        # 2차: ``` ... ``` 일반 코드블록 (마지막 블록 우선)
        code_blocks = re.findall(r'```\s*([\s\S]*?)\s*```', text)
        if code_blocks:
            for block in reversed(code_blocks):
                if 'json' in block.split('\n')[0].lower():
                    continue
                try:
                    parsed = json.loads(block.strip())
                    if parsed:
                        return parsed
                except json.JSONDecodeError as _e:
                    logger.debug(f"Suppressed: {_e}")

        # 2b: 단일 ``` ... ``` (기존 2차 호환)
        code_match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError as _e:
                logger.debug(f"Suppressed: {_e}")

        # 2c: ```json 뒤만 있고 닫는 ``` 없음 (응답 잘림) — 첫 { 부터 끝까지 추출 후 괄호 복구
        if '```json' in text:
            start = text.find('```json')
            after_marker = text[start + 7:].lstrip()
            first_brace = after_marker.find('{')
            if first_brace >= 0:
                partial = after_marker[first_brace:]
                open_braces = partial.count('{') - partial.count('}')
                open_brackets = partial.count('[') - partial.count(']')
                repair = partial
                for _ in range(open_brackets):
                    repair += ']'
                for _ in range(open_braces):
                    repair += '}'
                try:
                    result = json.loads(repair)
                    if result:
                        logger.info(f"[GeminiParser] 잘린 ```json 블록 복구 성공 (괄호 {open_braces+open_brackets}개 추가)")
                        return result
                except json.JSONDecodeError as _e:
                    logger.debug(f"Suppressed: {_e}")

        # 3차: 전체가 JSON인 경우
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as _e:
            logger.debug(f"Suppressed: {_e}")

        # 4차: 첫 번째 { ~ 마지막 } 추출 (v5.5.2: 후행 콤마 제거 후 재시도)
        first_brace = stripped.find('{')
        last_brace = stripped.rfind('}')
        if first_brace >= 0 and last_brace > first_brace:
            segment = stripped[first_brace:last_brace + 1]
            try:
                return json.loads(segment)
            except json.JSONDecodeError as _e:
                logger.debug(f"Suppressed: {_e}")
            try:
                normalized = re.sub(r',\s*([}\]])', r'\1', segment)
                return json.loads(normalized)
            except json.JSONDecodeError as _e:
                logger.debug(f"Suppressed: {_e}")

        logger.warning(f"[GeminiParser] JSON 파싱 실패 — 응답 미리보기: {text[:200]}...")

        # 5차: v3.8.8 불완전 JSON 복구 (토큰 절단 시 닫는 괄호 추가)
        try:
            first_brace = text.find('{')
            if first_brace >= 0:
                partial = text[first_brace:]
                # 열린 괄호 카운트
                open_braces = partial.count('{') - partial.count('}')
                open_brackets = partial.count('[') - partial.count(']')
                repair = partial
                for _ in range(open_brackets):
                    repair += ']'
                for _ in range(open_braces):
                    repair += '}'
                result = json.loads(repair)
                logger.info(f"[GeminiParser] 불완전 JSON 복구 성공 (괄호 {open_braces+open_brackets}개 추가)")
                return result
        except (json.JSONDecodeError, Exception) as _e:
            logger.debug(f"Suppressed: {_e}")

        return {}

    # =========================================================================
    # Packing List 파싱
    # =========================================================================

    def parse_packing_list(self, pdf_path: str,
                           bag_weight_kg: int = None,  # v8.6.1: None → DEFAULT_TONBAG_WEIGHT fallback
                           gemini_hint: str = '') -> PackingListResult:
        """
        Packing List PDF를 Gemini로 파싱.

        Args:
            pdf_path:       PDF 파일 경로
            bag_weight_kg:  톤백 단가 (500 or 1000) — v7.2.0: 입고 템플릿에서 주입
            gemini_hint:    선사별 추가 힌트 — v7.3.0: 프롬프트 끝에 삽입

        Returns:
            PackingListResult: 파싱 결과
        """
        result = PackingListResult()
        # v8.6.1: None이면 DEFAULT_TONBAG_WEIGHT fallback (build_rule_result에서 expected_per_bag=None 처리됨)
        from engine_modules.constants import DEFAULT_TONBAG_WEIGHT
        result.bag_weight_kg = int(bag_weight_kg) if bag_weight_kg else DEFAULT_TONBAG_WEIGHT

        try:
            logger.info(f"[GeminiParser] Packing List 파싱 시작: {pdf_path}")

            # v8.0.0 [PDF-DIRECT]: PDF 직접 전송 (이미지 변환 제거)
            # 이미지 변환 시 텍스트/표 손실 → LOT 추출 실패 원인
            # Gemini API는 application/pdf 직접 지원
            try:
                images = self._pdf_to_images(pdf_path)  # 다중페이지 폴백용만 유지
            except Exception:
                images = []

            # 프롬프트 (v5.5.2: 강제 스키마 — 오직 JSON만, 설명/마크다운/코드블럭 금지, lots 필수)
            prompt = """오직 JSON만 출력하세요. 설명·마크다운·코드블럭(```) 표시 금지. 반드시 lots 배열을 포함하고, 각 lot에는 lot_no, mxbg, net_weight_kg가 필수입니다.

이 Packing List 문서를 분석하여 아래 JSON 형식으로 정확히 추출해주세요.
표에 LIST 1, 2, ... N처럼 여러 행이 있으면 반드시 모든 행을 빠짐없이 추출하세요. 마지막 행까지 반드시 포함! (v7.3.6)

숫자 형식 주의 (★중요★):
- 유럽식 표기 (5.131,250 = 5131.250)를 숫자로 변환
- Net Weight, Gross Weight는 소수점 포함 kg 단위 (예: 5131.250)
- 소수점 아래 자릿수를 절사하거나 반올림하지 마세요. 원본 그대로 추출!

{
    "folio": "문서 번호 (7자리)",
    "product": "제품명 (예: LITHIUM CARBONATE)",
    "packing": "포장 정보",
    "code": "제품 코드 (MIC로 시작)",
    "vessel": "선박명",
    "customer": "고객사",
    "destination": "목적지",
    "lots": [
        {
            "list_no": 1,
            "container_no": "컨테이너 번호",
            "lot_no": "LOT 번호 (10자리)",
            "lot_sqm": "LOT SQM (6자리)",
            "mxbg": 10,
            "net_weight_kg": 5001.500,
            "gross_weight_kg": 5131.250,
            "del_no": "",
            "al_no": ""
        }
    ],
    "total_net_weight_kg": 100030.000,
    "total_gross_weight_kg": 102625.000
}

위 구조대로 JSON만 출력하세요."""

            # ── v7.3.0: 선사별 Gemini 힌트 주입 (SEC-C2: 인젝션 방지) ──────────
            _safe_pl_hint = _sanitize_prompt_hint(gemini_hint)
            if _safe_pl_hint:
                prompt += f"\n\n<carrier_hint>\n{_safe_pl_hint}\n</carrier_hint>"
                logger.debug(f"[GeminiParser] PL 힌트 주입 ({len(_safe_pl_hint)}자)")

            # v8.0.0 [SMART-PARSE]: 텍스트 우선 → PDF 직접 → 이미지 폴백
            try:
                from parsers.document_parser_modular.base import DocumentParserBase as _Base
                _base_inst = _Base.__new__(_Base)
                response_text = _base_inst._call_gemini_smart(prompt, pdf_path, self)
            except Exception:
                response_text = self._call_gemini_pdf(prompt, pdf_path)
            result.raw_response = response_text

            # v5.5.2: 디버깅 시 Gemini 원문을 파일로 저장 (ON/OFF: config 또는 SQM_SAVE_RAW_GEMINI_RESPONSE=1)
            try:
                from core.config import SAVE_RAW_GEMINI_RESPONSE
                if SAVE_RAW_GEMINI_RESPONSE:
                    log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
                    log_dir.mkdir(parents=True, exist_ok=True)
                    raw_path = log_dir / "raw_pl_response.txt"
                    raw_path.write_text(response_text or "", encoding="utf-8")
                    logger.info(f"[GeminiParser] PL 원문 저장: {raw_path}")
            except (ValueError, TypeError, KeyError, IndexError) as _e:
                logger.debug(f"Suppressed: {_e}")

            # JSON 파싱
            data = self._extract_json(response_text)

            # v5.5.2: LOT 추출 실패 원인 분해 로그 (JSON 파싱 실패 vs lots 비었는지 확정)
            parsed_keys = list(data.keys()) if data else []
            lots = data.get("lots") if data else None
            logger.info(f"[GeminiParser] PL 파싱 검증: parsed_keys={parsed_keys}, type(lots)={type(lots).__name__}, len(lots)={len(lots) if isinstance(lots, list) else 'N/A'}")
            if lots and len(lots) > 0 and isinstance(lots, list):
                first_lot = lots[0]
                first_keys = list(first_lot.keys()) if isinstance(first_lot, dict) else str(type(first_lot))
                logger.info(f"[GeminiParser] PL lots[0] 키: {first_keys}")

            if not data:
                result.error_message = "JSON 추출 실패"
                return result

            # 결과 매핑 (1페이지)
            result.folio = str(data.get('folio', ''))
            result.product = data.get('product', '')
            result.packing = data.get('packing', '')
            result.code = data.get('code', '')
            result.vessel = data.get('vessel', '')
            result.customer = data.get('customer', '')
            result.destination = data.get('destination', '')
            # ★★★ v2.9.52: 유럽식 숫자 변환 적용 ★★★
            result.total_net_weight_kg = parse_euro_weight(data.get('total_net_weight_kg', 0))
            result.total_gross_weight_kg = parse_euro_weight(data.get('total_gross_weight_kg', 0))

            seen_lot_nos = set()
            seen_fingerprints = set()
            def append_lot(lot_data: dict, from_continuation_page: bool = False) -> None:
                lot_no = str(lot_data.get('lot_no', '')).strip()
                fp = _make_lot_fingerprint(lot_data)
                if fp and fp in seen_fingerprints:
                    page_label = "연속페이지" if from_continuation_page else "1페이지"
                    logger.warning(
                        f"[GeminiParser] PL 행 중복 감지({page_label}) -> 스킵: "
                        f"lot_no={lot_no or '-'}, fp={fp}"
                    )
                    return
                if fp:
                    seen_fingerprints.add(fp)
                if lot_no:
                    seen_lot_nos.add(lot_no)
                lot = LOTItem(
                    list_no=int(lot_data.get('list_no', 0)),
                    container_no=str(lot_data.get('container_no', '')),
                    lot_no=lot_no or str(lot_data.get('lot_no', '')),
                    lot_sqm=str(lot_data.get('lot_sqm', '')),
                    mxbg=int(lot_data.get('mxbg', 10)),
                    net_weight_kg=parse_euro_weight(lot_data.get('net_weight_kg', 0)),
                    gross_weight_kg=parse_euro_weight(lot_data.get('gross_weight_kg', 0)),
                    del_no=str(lot_data.get('del_no', '')),
                    al_no=str(lot_data.get('al_no', ''))
                )
                result.lots.append(lot)

            # 1페이지/연속페이지 공통: fingerprint 기반 중복 제거
            for lot_data in data.get('lots', []):
                append_lot(lot_data, from_continuation_page=False)

            # 다중 페이지: 2페이지부터 추가 LOT 추출 (20개 롯트 등이 2페이지에 나뉠 경우 누락 방지)
            prompt_continuation = """오직 JSON만 출력하세요. 설명·마크다운·코드블럭(```) 금지.
이 Packing List의 이어지는 페이지입니다. 이 페이지에 있는 LOT 행만 아래 형식으로 추출하세요.
유럽식 숫자 (5.131,250 = 5131.250)를 숫자로 변환하고, net_weight_kg·gross_weight_kg는 소수점 포함 kg로 넣으세요.
{"lots": [ {"list_no": 1, "container_no": "", "lot_no": "", "lot_sqm": "", "mxbg": 10, "net_weight_kg": 5001.5, "gross_weight_kg": 5131.25, "del_no": "", "al_no": ""} ]}
JSON만 출력하세요."""

            for page_idx in range(1, len(images)):
                try:
                    page_text = self._call_gemini(prompt_continuation, images[page_idx])
                    page_data = self._extract_json(page_text)
                    if not page_data:
                        continue
                    page_lots = page_data.get("lots") if isinstance(page_data.get("lots"), list) else []
                    logger.info(f"[GeminiParser] PL 추가 페이지 {page_idx + 1}: {len(page_lots)} LOT")
                    for lot_data in page_lots:
                        if not isinstance(lot_data, dict):
                            continue
                        # list_no 재부여 (이어지는 번호), 중복은 append_lot 내부에서 fingerprint 스킵
                        lot_data = dict(lot_data)
                        lot_data["list_no"] = len(result.lots) + 1
                        append_lot(lot_data, from_continuation_page=True)
                except (ValueError, TypeError, KeyError) as _e:
                    logger.warning(f"[GeminiParser] PL 페이지 {page_idx + 1} 추출 실패: {_e}")

            # list_no 순서대로 재정렬 및 총중량 재계산
            if result.lots:
                for idx, lot in enumerate(result.lots, 1):
                    lot.list_no = idx
                result.total_net_weight_kg = sum(lot.net_weight_kg for lot in result.lots)
                result.total_gross_weight_kg = sum(lot.gross_weight_kg for lot in result.lots)

            # ★ v8.2.4 [GEMINI-PL-HINT-RETRY]: 힌트 기반 재시도
            # 기존 v7.3.6: 동일 프롬프트 재시도 → 같은 결과 반복 문제
            # 수정: 이미 추출된 LOT 번호를 힌트로 전달 → 누락 행만 요청
            if len(images) == 1 and 0 < len(result.lots) < 30:
                _before_retry = len(result.lots)
                logger.warning(
                    f"[GeminiParser] PL 1페이지 {_before_retry}개 추출 — "
                    f"힌트 기반 재시도 실행 (v8.2.4)"
                )
                try:
                    # 이미 추출된 LOT 번호 목록을 힌트로 구성
                    _known_lots = [str(l.lot_no).strip() for l in result.lots if l.lot_no]
                    _known_str = ', '.join(_known_lots[:15])  # 최대 15개
                    _hint_retry_prompt = (
                        f"{prompt}\n\n"
                        f"[재시도 힌트 — v8.2.4]\n"
                        f"이미 추출된 LOT 번호: {_known_str}\n"
                        f"위 LOT 번호는 이미 있으므로 제외하고, "
                        f"문서에서 아직 추출하지 못한 나머지 LOT만 추출해주세요.\n"
                        f"누락된 LOT가 없으면 빈 lots 배열을 반환하세요."
                    )
                    _retry_text = self._call_gemini(_hint_retry_prompt, images[0])
                    _retry_data = self._extract_json(_retry_text)
                    if _retry_data and isinstance(_retry_data.get('lots'), list):
                        _added = 0
                        for lot_data in _retry_data['lots']:
                            _lot_no = str(lot_data.get('lot_no', '')).strip()
                            if _lot_no and _lot_no not in seen_lot_nos:
                                append_lot(lot_data, from_continuation_page=False)
                                _added += 1
                        if _added > 0:
                            logger.info(
                                f"[GeminiParser] PL 힌트 재시도 성공: "
                                f"{_before_retry}개 → {len(result.lots)}개 (+{_added}개 추가)"
                            )
                            result.total_net_weight_kg   = sum(l.net_weight_kg   for l in result.lots)
                            result.total_gross_weight_kg = sum(l.gross_weight_kg for l in result.lots)
                        else:
                            logger.info(
                                f"[GeminiParser] PL 힌트 재시도: 추가 LOT 없음 "
                                f"({_before_retry}개가 최종)"
                            )
                except Exception as _retry_err:
                    logger.warning(f"[GeminiParser] PL 힌트 재시도 실패(무시): {_retry_err}")

            # lots 집계: total_lots, total_maxibag, containers (비교 스크립트 호환용)
            result.total_lots = len(result.lots)
            result.total_maxibag = sum(lot.mxbg for lot in result.lots)
            _seen_containers: List[str] = []
            for lot in result.lots:
                if lot.container_no and lot.container_no not in _seen_containers:
                    _seen_containers.append(lot.container_no)
            result.containers = _seen_containers

            result.success = len(result.lots) > 0
            # v8.2.4: 파싱 통계 기록
            self._log_parse_result(
                doc_type='PL',
                source_file=os.path.basename(pdf_path) if pdf_path else '',
                success=result.success,
                lot_count=len(result.lots),
                method='gemini',
                error_msg='' if result.success else 'lot_count=0',
            )

            # v2.5.8: 제품명 로깅
            logger.info(f"[GeminiParser] Packing List 완료: {len(result.lots)} LOT, {result.total_net_weight_kg:,.0f}kg, 제품: {result.product or '(없음)'}")

        except (ValueError, TypeError, KeyError) as e:
            result.error_message = str(e)
            logger.error(f"[GeminiParser] Packing List 오류: {e}")

        return result

    # =========================================================================
    # Invoice 파싱
    # =========================================================================

    def parse_invoice(self, pdf_path: str, gemini_hint: str = '') -> InvoiceResult:
        """
        Invoice PDF를 Gemini로 파싱.

        Args:
            pdf_path:    PDF 파일 경로
            gemini_hint: 선사별 추가 힌트 — v7.3.0: 프롬프트 끝에 삽입
        """
        result = InvoiceResult()

        try:
            logger.info(f"[GeminiParser] Invoice 파싱 시작: {pdf_path}")

            images = self._pdf_to_images(pdf_path)
            if not images:
                result.error_message = "PDF 이미지 변환 실패"
                return result

            prompt = """이 Invoice(상업송장/FACTURA) 문서를 분석하여 아래 JSON 형식으로 추출해주세요.

**중요 추출 규칙:**
1. SAP NO는 "Ref.SQM/Our Order" 또는 "Our Order" 필드에서 22로 시작하는 10자리 숫자
   ⚠️ SAP NO(22xxxxxxxx)는 절대 B/L No가 아님 — 혼동 금지
2. LOT 목록은 "N° LOTES:" 뒤에 있으며, 형식은 "LOT번호/중량T" (예: 1125072729/5,001T)
   - LOT 번호만 추출 (10자리 숫자, 11로 시작)
   - 중량 부분(/5,001T)은 제외
3. B/L 번호는 "BL-AWB-CRT Number" 필드에서만 추출
   - 없으면 빈 문자열("")로 반환 — SAP NO를 대신 넣지 말 것
   - B/L No는 보통 9~12자리 숫자 (예: 258468669, 263764814)
   - SAP NO(22xxxxxxxx, 10자리)와 혼동 금지

```json
{
    "sap_no": "22로 시작하는 10자리 (예: 2200033057)",
    "invoice_no": "송장 번호 (예: 16130)",
    "bl_no": "B/L 번호 — 선사 접두사 포함 전체 번호 (예: MAEU265083673, HLCUSCL260148627, MEDUW9018104)",
    "product": "제품명 (예: LITHIUM CARBONATE - BATTERY GRADE - MICRONIZED)",
    "product_code": "제품 코드 (예: MIC9000.00)",
    "quantity_mt": 100.02,
    "unit_price": 9272.00,
    "total_amount": 927385.44,
    "currency": "USD",
    "incoterm": "CIF",
    "origin": "출발지 (예: PUERTO ANGAMOS-CHILE)",
    "destination": "도착지 (예: GWANGYANG-SOUTH KOREA)",
    "vessel": "선박명 (예: CHARLOTTE MAERSK 535W)",
    "net_weight_kg": 100020,
    "gross_weight_kg": 102625,
    "package_count": 200,
    "package_type": "MAXISACO MIC9000, PLASTIC JAR",
    "lot_numbers": ["1125072729", "1125072730", "1125081215", ...]
}
```

모든 LOT 번호를 빠짐없이 추출해주세요. JSON만 응답해주세요."""

            # ── v7.3.0: 선사별 Gemini 힌트 주입 (SEC-C2: 인젝션 방지) ──────────
            _safe_inv_hint = _sanitize_prompt_hint(gemini_hint)
            if _safe_inv_hint:
                prompt += f"\n\n<carrier_hint>\n{_safe_inv_hint}\n</carrier_hint>"
                logger.debug(f"[GeminiParser] Invoice 힌트 주입 ({len(_safe_inv_hint)}자)")

            # v8.0.0 [SMART-PARSE]: 텍스트 우선 → PDF 직접 → 이미지 폴백
            try:
                from parsers.document_parser_modular.base import DocumentParserBase as _Base
                _base_inst = _Base.__new__(_Base)
                response_text = _base_inst._call_gemini_smart(prompt, pdf_path, self)
            except Exception:
                response_text = self._call_gemini_pdf(prompt, pdf_path)
            result.raw_response = response_text

            data = self._extract_json(response_text)

            if data:
                result.sap_no = str(data.get('sap_no', ''))
                result.invoice_no = str(data.get('invoice_no', ''))
                result.bl_no = str(data.get('bl_no', ''))
                result.product = data.get('product', '')
                result.product_code = data.get('product_code', '')
                result.quantity_mt = float(data.get('quantity_mt', 0))
                result.unit_price = float(data.get('unit_price', 0))
                result.total_amount = float(data.get('total_amount', 0))
                result.currency = data.get('currency', 'USD')
                result.incoterm = data.get('incoterm', '')
                result.origin = data.get('origin', '')
                result.destination = data.get('destination', '')
                result.vessel = data.get('vessel', '')
                result.net_weight_kg = parse_euro_weight(data.get('net_weight_kg', 0))
                result.gross_weight_kg = parse_euro_weight(data.get('gross_weight_kg', 0))
                try:
                    result.package_count = int(float(data.get('package_count', 0) or 0))
                except (ValueError, TypeError):
                    result.package_count = 0
                result.package_type = str(data.get('package_type', '') or '')
                result.lot_numbers = [str(x).strip() for x in (data.get('lot_numbers', []) or []) if str(x).strip()]
                result.success = bool(result.sap_no)

            # ── v6.5.0: pdfplumber 정규식 보강 ──────────────────────────────
            # FA의 N° LOTES 줄이 PDF에서 줄바꿈되면 Gemini가 경계 LOT를 누락.
            # pdfplumber로 전체 텍스트에서 10자리 LOT 번호를 직접 추출해 보완.
            try:
                import pdfplumber as _pdfp
                with _pdfp.open(pdf_path) as _pdf:
                    _raw = " ".join(
                        (_page.extract_text() or "") for _page in _pdf.pages
                    )
                # 줄바꿈·공백 정규화 후 10자리 LOT 번호 추출
                _cleaned = re.sub(r'\s+', ' ', _raw)
                _regex_lots = re.findall(r'\b(1[12]\d{8})\b', _cleaned)
                # 중복 제거, 순서 유지
                _seen = set(result.lot_numbers)
                _added = 0
                for _lot in _regex_lots:
                    if _lot not in _seen:
                        _seen.add(_lot)
                        result.lot_numbers.append(_lot)
                        _added += 1
                if _added:
                    logger.info(
                        "[GeminiParser] Invoice pdfplumber 보강: %d개 추가 "
                        "(Gemini %d개 → 합계 %d개)",
                        _added, len(result.lot_numbers) - _added, len(result.lot_numbers)
                    )
            except Exception as _pdf_err:
                logger.debug("[GeminiParser] Invoice pdfplumber 보강 스킵: %s", _pdf_err)

            # Invoice 추가 페이지 LOT 추출 (PL과 동일한 다중 페이지 보강)
            if result.success and len(images) > 1:
                prompt_continuation = """오직 JSON만 출력하세요. 설명·마크다운·코드블럭(```) 금지.
이 Invoice의 이어지는 페이지입니다. 이 페이지에 있는 LOT 번호만 추출하세요.
LOT 형식은 "LOT번호/중량T" 이며 LOT 번호(숫자)만 반환하세요.
{"lot_numbers": ["1125072729", "1125072730"]}
JSON만 출력하세요."""
                seen_lots = set(result.lot_numbers)
                for page_idx in range(1, len(images)):
                    try:
                        page_text = self._call_gemini(prompt_continuation, images[page_idx])
                        page_data = self._extract_json(page_text)
                        if not page_data:
                            continue
                        page_lots = page_data.get("lot_numbers")
                        if not isinstance(page_lots, list):
                            continue
                        added = 0
                        for raw_lot in page_lots:
                            lot_no = str(raw_lot).strip()
                            if not lot_no:
                                continue
                            if lot_no in seen_lots:
                                continue
                            seen_lots.add(lot_no)
                            result.lot_numbers.append(lot_no)
                            added += 1
                        if added:
                            logger.info(f"[GeminiParser] Invoice 추가 페이지 {page_idx + 1}: LOT {added}개 추가")
                    except (ValueError, TypeError, KeyError) as page_err:
                        logger.warning(f"[GeminiParser] Invoice 페이지 {page_idx + 1} LOT 추출 실패: {page_err}")

            logger.info(f"[GeminiParser] Invoice 완료: SAP={result.sap_no}, LOT={len(result.lot_numbers)}개")

        except (ValueError, TypeError, KeyError) as e:
            result.error_message = str(e)
            logger.error(f"[GeminiParser] Invoice 오류: {e}")

        return result

    # =========================================================================
    # B/L 파싱
    # =========================================================================

    def parse_bl(self, pdf_path: str, gemini_hint: str = '') -> BLResult:
        """
        B/L (Bill of Lading) PDF를 Gemini로 파싱
        멀티페이지 지원 (3페이지까지 분석)

        v6.4.0: 선사별 템플릿 레지스트리 통합
          ① pdfplumber로 텍스트 추출 → 선사 자동 탐지 (점수제)
          ② 선사별 정규식으로 BL No 1차 추출 (Gemini 없이 0.01초)
          ③ 선사별 힌트 포함 Gemini 프롬프트 사용
          ④ BL No: 정규식 결과 우선, Gemini 보조
          ⑤ result에 carrier_id/carrier_name/bl_equals_booking_no 저장
        v7.3.0: gemini_hint → 프롬프트 끝에 추가 주입
        """
        result = BLResult()

        try:
            logger.info(f"[GeminiParser] B/L 파싱 시작: {pdf_path}")

            # ── v6.4.0 ①②: 선사 탐지 + BL No 정규식 1차 추출 ──
            _pages_text: list = []
            _tmpl = None
            _bl_no_regex = ""
            try:
                import pdfplumber as _pdfplumber
                with _pdfplumber.open(pdf_path) as _p:
                    _pages_text = [(pg.extract_text() or "") for pg in _p.pages[:3]]
                if _pages_text:
                    from features.ai.bl_carrier_registry import (
                        detect_carrier, extract_bl_no_by_template
                    )
                    _tmpl = detect_carrier(_pages_text[0])
                    if _tmpl:
                        _bl_no_regex = extract_bl_no_by_template(_pages_text, _tmpl)
                        logger.info(
                            f"[GeminiParser] 선사={_tmpl.carrier_name}, "
                            f"BL_regex={_bl_no_regex!r}"
                        )
                        result.carrier_id = getattr(_tmpl, 'carrier_id', '') or getattr(_tmpl, 'carrier_name', '')
            except Exception as _reg_e:
                logger.debug(f"[GeminiParser] 레지스트리 탐지 실패(무시): {_reg_e}")

            images = self._pdf_to_images(pdf_path)
            if not images:
                result.error_message = "PDF 이미지 변환 실패"
                return result

            # ── v6.4.0 ③: 선사별 힌트 포함 프롬프트 생성 ──
            try:
                from features.ai.bl_carrier_registry import build_bl_prompt  # noqa: F811  # v7.3.6: 재정의 의도적
                prompt = build_bl_prompt(_tmpl)
            except Exception:
                prompt = """이 B/L(선하증권/NON-NEGOTIABLE WAYBILL) 문서를 분석하여 아래 JSON 형식으로 추출해주세요.

**중요 추출 규칙:**
1. B/L No는 문서 상단 "B/L No." 필드 (예: 258468669)
2. 컨테이너 번호는 XXXX0000000 형식 (4글자+7숫자)
   - 문서에서 ML-CL 앞에 있는 번호 (예: FFAU5355006, MRKU3714936)
   - 하이픈 없이 추출
3. SAP NO는 2페이지나 3페이지에 22로 시작하는 10자리로 있을 수 있음
4. 컨테이너별 Seal No도 추출 (ML-CL0501798 형식)

```json
{
    "bl_no": "B/L 번호 — 선사 접두사 포함 전체 번호 (예: MAEU265083673, HLCUSCL260148627, MEDUW9018104)",
    "booking_no": "Booking 번호",
    "sap_no": "22로 시작하는 10자리 (있으면)",
    "vessel": "선박명 (예: CHARLOTTE MAERSK)",
    "voyage": "항차 번호 (예: 535W)",
    "port_of_loading": "선적항 (예: Puerto Angamos, Chile)",
    "port_of_discharge": "최종 양하항 Final Port of Discharge (예: GWANGYANG, SOUTH KOREA). 환적항(Transshipment Port)은 제외",
    "shipper": "송하인 (예: SQM SALAR SpA)",
    "consignee": "수하인 (예: SOQUIMICH LLC)",
    "containers": [
        {"container_no": "FFAU5355006", "seal_no": "ML-CL0501798", "weight_kg": 20525},
        {"container_no": "MRKU3714936", "seal_no": "ML-CL0501791", "weight_kg": 20525}
    ],
    "total_containers": 5,
    "total_weight_kg": 102625,
    "gross_weight_kg": 102625,
    "shipped_on_board_date": "★필수★ 선적일 YYYY-MM-DD 또는 NOT_FOUND"
}
```

★★★ shipped_on_board_date (선적일) 추출 규칙 ★★★
- 찾는 위치: "SHIPPED ON BOARD", "ON BOARD DATE", "LADEN ON BOARD", "DATE OF SHIPMENT" 라벨 근처
- 보통 문서 하단 또는 서명 근처에 있습니다
- 형식: 반드시 YYYY-MM-DD로 변환 (예: 2025-09-15)
- "15 SEP 2025" 형식이면 → "2025-09-15"로 변환
- "15/09/2025" 형식이면 → "2025-09-15"로 변환
- 찾지 못하면 "NOT_FOUND"라고 적어주세요. 빈 문자열("") 금지!

모든 컨테이너를 빠짐없이 추출해주세요. JSON만 응답해주세요."""

            # ── v7.3.0: 선사별 Gemini 힌트 주입 (SEC-C2: 인젝션 방지) ──────────
            _safe_bl_hint = _sanitize_prompt_hint(gemini_hint)
            if _safe_bl_hint:
                prompt += f"\n\n<carrier_hint>\n{_safe_bl_hint}\n</carrier_hint>"
                logger.debug(f"[GeminiParser] BL 힌트 주입 ({len(_safe_bl_hint)}자)")

            # 멀티페이지: 최대 3페이지까지 분석
            all_containers = []
            sap_no = ""

            for i, img in enumerate(images[:3]):
                response_text = self._call_gemini(prompt, img)

                if i == 0:
                    result.raw_response = response_text
                else:
                    result.raw_response += f"\n\n--- Page {i+1} ---\n{response_text}"

                data = self._extract_json(response_text)

                if data:
                    # 첫 페이지에서만 기본 정보 추출
                    if i == 0:
                        result.bl_no = str(data.get('bl_no', ''))
                        result.booking_no = str(data.get('booking_no', ''))
                        result.vessel = data.get('vessel', '')
                        result.voyage = data.get('voyage', '')
                        result.port_of_loading = data.get('port_of_loading', '')
                        result.port_of_discharge = data.get('port_of_discharge', '')
                        result.shipper = data.get('shipper', '')
                        result.consignee = data.get('consignee', '')
                        result.total_containers = int(data.get('total_containers', 0))
                        result.total_weight_kg = float(data.get('total_weight_kg', 0))
                        result.gross_weight_kg = result.total_weight_kg  # 비교 스크립트 호환용 alias
                        # carrier_id: Gemini 결과 우선, 없으면 bl_no prefix로 추론
                        _gm_carrier = str(data.get('carrier_id', '') or '')
                        if _gm_carrier and _gm_carrier.upper() != 'UNKNOWN':
                            result.carrier_id = _gm_carrier
                        if not result.carrier_id:
                            _bn = result.bl_no.upper()
                            if _bn.startswith('MAEU'):   result.carrier_id = 'MAERSK'
                            elif _bn.startswith('HLC'):  result.carrier_id = 'HAPAG'
                            elif _bn.startswith('MEDU'): result.carrier_id = 'MSC'
                            elif _bn.startswith('ONE'):  result.carrier_id = 'ONE'
                        result.shipped_date = data.get('shipped_on_board_date', '') or data.get('shipped_date', '') or data.get('ship_date', '')
                        result.ship_date = result.shipped_date  # 호출부 getattr(bl, 'ship_date') 호환
                        result.shipped_on_board_date = result.shipped_date  # BLData 필드 호환

                    # SAP NO 찾기 (어느 페이지에서든)
                    page_sap = str(data.get('sap_no', ''))
                    if page_sap and page_sap.startswith('22') and len(page_sap) == 10:
                        sap_no = page_sap

                    # 컨테이너 수집 (중복 제거)
                    for cont in data.get('containers', []):
                        cont_no = cont.get('container_no', '')
                        if cont_no and cont_no not in [c.container_no for c in all_containers]:
                            all_containers.append(ContainerDetail(
                                container_no=cont_no,
                                seal_no=cont.get('seal_no', ''),
                                weight_kg=float(cont.get('weight_kg', 0))
                            ))

            result.sap_no = sap_no
            result.containers = all_containers
            result.container_numbers = [c.container_no for c in all_containers]

            # ── v6.4.0 ④: BL No 최종 결정 (정규식 우선) ──
            if _bl_no_regex:
                if result.bl_no and result.bl_no != _bl_no_regex:
                    logger.warning(
                        f"[GeminiParser] BL No 불일치: "
                        f"regex={_bl_no_regex!r} vs gemini={result.bl_no!r} "
                        "→ 정규식 결과 사용 (신뢰도 높음)"
                    )
                result.bl_no = _bl_no_regex

            # ── v6.4.0 ⑤: 선사 정보 저장 ──
            if _tmpl:
                result.carrier_id          = _tmpl.carrier_id
                result.carrier_name        = _tmpl.carrier_name
                result.bl_equals_booking_no = _tmpl.bl_equals_booking_no
            else:
                result.carrier_id          = "UNKNOWN"
                result.carrier_name        = ""
                result.bl_equals_booking_no = False

            # ── v8.2.4 힌트 기반 재시도: BL No 미추출 시 ────────────────
            if not result.bl_no and _tmpl and images:
                try:
                    _hint_parts = []
                    if _tmpl.bl_format_hint:
                        _hint_parts.append(
                            f"BL No 형식 예시: {_tmpl.bl_format_hint}"
                        )
                    if _tmpl.bl_no_prompt_hint:
                        _hint_parts.append(_tmpl.bl_no_prompt_hint)
                    _hint_parts.append(
                        "위 문서에서 BL No만 다시 찾아주세요. "
                        "BL No 값만 한 줄로 출력하세요. JSON 불필요."
                    )
                    _retry_prompt = (
                        f"[BL No 재추출 요청 — 선사: {_tmpl.carrier_name}]\n"
                        + "\n".join(_hint_parts)
                    )
                    _retry_text = self._call_gemini(
                        _retry_prompt, images[0]
                    ).strip()
                    # 첫 번째 알파숫자 토큰 추출
                    import re as _re2
                    _m = _re2.search(r'([A-Z0-9]{8,20})', _retry_text)
                    if _m:
                        _candidate = _m.group(1)
                        # BL 토큰 유효성 간단 검증 (날짜/일반단어 제외)
                        _bl_blacklist = {'NOT', 'FOUND', 'NONE', 'NULL', 'JSON', 'BL', 'NO'}
                        if _candidate not in _bl_blacklist:
                            result.bl_no = _candidate
                            logger.info(
                                f"[GeminiParser] BL 재시도 성공: {_candidate!r} "
                                f"(선사={_tmpl.carrier_name})"
                            )
                        else:
                            logger.debug(
                                f"[GeminiParser] BL 재시도 후보 블랙리스트: {_candidate!r}"
                            )
                    else:
                        logger.debug(
                            f"[GeminiParser] BL 재시도 — 유효 토큰 없음: {_retry_text!r}"
                        )
                except Exception as _re_err:
                    logger.debug(f"[GeminiParser] BL 재시도 실패(무시): {_re_err}")

            result.success = bool(result.bl_no)

            logger.info(
                f"[GeminiParser] B/L 완료: "
                f"선사={result.carrier_name or '?':}, "
                f"BL={result.bl_no}, SAP={result.sap_no}, "
                f"컨테이너 {len(result.containers)}개"
            )
            # v8.2.4: 파싱 통계 기록
            self._log_parse_result(
                doc_type='BL',
                source_file=os.path.basename(pdf_path) if pdf_path else '',
                success=result.success,
                bl_no=result.bl_no or '',
                carrier_id=result.carrier_id or '',
                method='regex' if _bl_no_regex else 'gemini',
                error_msg=result.error_message or '',
            )

        except (ValueError, TypeError, KeyError) as e:
            result.error_message = str(e)
            logger.error(f"[GeminiParser] B/L 오류: {e}")
            self._log_parse_result(
                doc_type='BL',
                source_file=os.path.basename(pdf_path) if pdf_path else '',
                success=False,
                error_msg=str(e),
            )

        return result

    # =========================================================================
    # D/O 파싱
    # =========================================================================

    def _get_do_prompt(self) -> str:
        """D/O 파싱용 공통 프롬프트 (PDF/캡처 이미지 공유) — v8.2.4: MSC DO 힌트 강화."""
        return """이 D/O(화물인도지시서/발급확인서) 문서를 분석하여 아래 JSON 형식으로 추출해주세요.
오직 JSON만 출력하세요. 설명·마크다운·코드블럭(```) 금지.

★★★ arrival_date (입항일) — 최우선 추출 필드 ★★★

이 문서에서 가장 중요한 데이터는 arrival_date(선박 입항일)입니다.
반드시 찾아야 합니다.

[찾는 방법 — 아래 순서대로 확인하세요]

STEP 1: 문서 하단 "(For Local Use)" 또는 "참고사항" 섹션에서
        "선박 입항일" 또는 "1. 선박 입항일" 라벨을 찾으세요.

        ⚠️ MSC D/O 주의: "선박 입항일" 바로 아래에 날짜가 없을 수 있습니다!
        MSC D/O 구조 (실제 예시):
          (For Local Use)
          1. 선박 입항일        ← 이 라벨
          3.                    ← MRN/MSN 번호 앞 숫자
          MRN                   ← 세관 번호 라벨
          /
          MSN                   ← 세관 번호 라벨
          2026-03-21            ← ★이것이 arrival_date! (5~7줄 아래)

        Maersk D/O 구조 (일반적):
          (For Local Use)
          1. 선박 입항일
          2025-10-17            ← 바로 아래 줄

STEP 2: STEP 1에서 못 찾으면 다음 라벨 근처를 검색:
        "Arrival Date", "입항일", "입항예정일",
        "ETA", "ETA BUSAN", "ETA(BUSAN)", "ATA", "Vessel Arrival"

STEP 3: 모두 실패하면 "NOT_FOUND"로 적으세요.

★★★ 주의: 다음 날짜와 arrival_date를 혼동하지 마세요! ★★★
- Free Time / 반납기한 컬럼의 날짜 → 컨테이너 "반납기한"입니다 (arrival_date 아님!)
- "발행일" → D/O 발급일입니다 (arrival_date 아님!)
- "출력일시" → 인쇄일입니다 (arrival_date 아님!)
- MRN/MSN 번호 자체 → 세관 신고번호 (날짜 아님, 예: 26MSCU3082I/0001)
arrival_date는 위 날짜들보다 보통 더 이른(과거) 날짜입니다.

[날짜 형식 — 반드시 YYYY-MM-DD로 변환]
- "2025-10-17" → 그대로
- "2025.10.17" → "2025-10-17"
- "17/10/2025" → "2025-10-17"
- "Oct 17, 2025" → "2025-10-17"
- "2025년 10월 17일" → "2025-10-17"

[기타 추출 규칙]
1. D/O No는 문서 상단 (MSC 예: 26032314BIQL, Maersk 예: 241044299)
2. B/L No 형식:
   - MSC: MEDU로 시작하는 알파숫자 (예: MEDUFP963988) — 전체 추출
   - Maersk: 숫자만 추출 (예: MAEU258468669 → 258468669)
3. MRN/MSN 선사별 위치:
   MSC D/O: "(For Local Use)" 섹션의 "3." 다음 줄 (예: 26MSCU3082I / 0001)
   HAPAG D/O: 세관신고번호 섹션에서 "/" 로 구분된 번호
   ONE D/O: "신고번호" 또는 "참고사항" 섹션에서 추출
4. 컨테이너: [A-Z]{4}\\d{7} 형식 (예: MSCU1234567)
5. 씰번호: ML-CL로 시작 (예: ML-CL1234567)
6. con_return_date: 반납기한 YYYY-MM-DD. 컨테이너마다 동일한 경우 모두 같은 날짜 입력
7. 반납지: "반납지" 필드 (예: KRKNYTM, 광양항서부컨테이너터미널)

```json
{
    "do_no": "D/O 번호 (MSC 예: 26032314BIQL, Maersk 예: 241044299)",
    "bl_no": "B/L 번호 — 선사 접두사 포함 전체 번호 (예: MAEU265083673, HLCUSCL260148627, MEDUW9018104, ONEYSCLG01825300)",
    "bl_no_full": "bl_no와 동일한 전체 번호 (접두사 포함)",
    "vessel": "선박명 (예: MSC IRENE 또는 CHARLOTTE MAERSK)",
    "voyage": "항차 (예: FY611A 또는 535W)",
    "port_of_loading": "선적항 (예: CLMJS)",
    "port_of_discharge": "양하항 (예: KRKAN 또는 KRKWY)",
    "shipper": "송하인",
    "consignee": "수하인",
    "mrn": "MRN 번호 — 공백 포함 정확히 추출 (예: 26HDM UK026I, 26MSCU3082I, 26HLCU9401I)",
    "msn": "MSN 번호 (예: 0001, 5019, 6006)",
    "containers": [
        {"container_no": "MSCU1234567", "seal_no": "ML-CL1234567", "size_type": "45G1", "con_return_date": "2026-04-04", "return_place": "광양항서부컨테이너터미널"}
    ],
    "total_weight_kg": 123150,
    "gross_weight_kg": 123150,  // ⚠️ 반드시 KG 단위 (MT 아님). 문서에 MT로 표기된 경우 ×1000 변환 (예: 102.625MT → 102625kg)
    "arrival_date": "★필수★ 입항일 YYYY-MM-DD 또는 NOT_FOUND",
    "issue_date": "D/O 발행일 YYYY-MM-DD",
    "all_dates_found": ["문서에서 발견한 모든 날짜를 YYYY-MM-DD 형식으로 나열"]
}
```

★ arrival_date: 빈 문자열("") 금지, null 금지. 찾으면 YYYY-MM-DD, 못 찾으면 "NOT_FOUND"
★ MSC D/O: arrival_date는 "선박 입항일" 라벨에서 5~7줄 아래 MRN/MSN 사이에 있습니다!
★ all_dates_found: 문서의 모든 날짜를 빠짐없이 나열하세요.
★ containers[].con_return_date: 각 컨테이너의 반납기한. 모두 같으면 동일 날짜 반복 입력.
모든 컨테이너를 빠짐없이 추출해주세요. JSON만 응답해주세요."""

    def _apply_do_json_to_result(self, result: DOResult, data: Dict) -> None:
        """JSON 추출 결과를 DOResult에 매핑 (PDF/이미지 공통)."""
        if not data:
            return
        result.do_no = str(data.get('do_no', ''))
        _bl_raw  = str(data.get('bl_no', '') or '')
        _bl_full = str(data.get('bl_no_full', '') or '')
        # bl_no_full이 있고 더 길면 우선 사용 (선사 접두사 포함 버전)
        result.bl_no = _bl_full if len(_bl_full) > len(_bl_raw) else _bl_raw
        result.bl_no_full = _bl_full or _bl_raw
        result.vessel = data.get('vessel', '')
        result.voyage = data.get('voyage', '')
        result.port_of_loading = data.get('port_of_loading', '')
        result.port_of_discharge = data.get('port_of_discharge', '')
        result.shipper = data.get('shipper', '')
        result.consignee = data.get('consignee', '')
        _raw_w = float(data.get('total_weight_kg', 0) or 0)
        _raw_gw = float(data.get('gross_weight_kg', 0) or _raw_w or 0)
        # MT→KG 자동 보정: 중량이 1000 미만이면 MT로 오인한 것 (예: 102.625 → 102625)
        _cnt = len(data.get('containers', []) or [])
        if 0 < _raw_gw < 1000 and _cnt > 0:
            logger.info(f"[DO] gross_weight_kg={_raw_gw} < 1000 → MT→KG 보정 ({_raw_gw*1000})")
            _raw_gw = _raw_gw * 1000
        if 0 < _raw_w < 1000 and _cnt > 0:
            _raw_w = _raw_w * 1000
        result.total_weight_kg = _raw_w or _raw_gw
        result.gross_weight_kg = _raw_gw or _raw_w  # 비교 스크립트 호환용 alias
        result.mrn = str(data.get('mrn', '') or '')
        result.msn = str(data.get('msn', '') or '')
        arrival = (data.get('arrival_date') or data.get('eta_date') or data.get('eta') or
                  data.get('vessel_arrival') or data.get('eta_busan') or '')
        _arrival_str = str(arrival).strip() if arrival else ''
        result.arrival_date = ''
        if _arrival_str and _arrival_str not in ('NOT_FOUND', 'None', ''):
            try:
                from utils.date_utils import normalize_date
                _d = normalize_date(_arrival_str)
                if _d:
                    result.arrival_date = _d.isoformat()
            except Exception as e:
                logger.debug(f"Suppressed: {e}")
            if not result.arrival_date and re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', _arrival_str[:10]):
                result.arrival_date = _arrival_str[:10]
        result.all_dates_found = data.get('all_dates_found', [])
        result.issue_date = data.get('issue_date', '')
        result.release_date = data.get('release_date', data.get('issue_date', ''))
        _conts = data.get('containers', [])
        for cont in _conts:
            con_return_val = (cont.get('con_return_date', '') or cont.get('free_time_date', '') or
                            cont.get('free_time', '') or cont.get('con_return', '') or
                            cont.get('return_date', '') or cont.get('Free_Time', '') or '')
            if con_return_val and isinstance(con_return_val, str):
                con_return_val = str(con_return_val).strip()[:10]
                if not re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', con_return_val):
                    con_return_val = ''
            cno = cont.get('container_no', '') or ''
            result.containers.append(ContainerDetail(
                container_no=cno,
                seal_no=cont.get('seal_no', ''),
                size_type=cont.get('size_type', ''),
                free_time=con_return_val,
                return_place=cont.get('return_place', '') or cont.get('return_location', '')
            ))
        result.container_numbers = [c.container_no for c in result.containers]
        result.success = bool(result.bl_no or result.do_no)

    def parse_do(self, pdf_path: str) -> DOResult:
        """D/O (Delivery Order) PDF를 Gemini로 파싱."""
        result = DOResult()
        try:
            logger.info(f"[GeminiParser] D/O 파싱 시작: {pdf_path}")
            images = self._pdf_to_images(pdf_path)
            if not images:
                result.error_message = "PDF 이미지 변환 실패"
                return result
            prompt = self._get_do_prompt()
            response_text = self._call_gemini(prompt, images[0])
            result.raw_response = response_text
            data = self._extract_json(response_text)
            self._apply_do_json_to_result(result, data)
            logger.info(f"[GeminiParser] D/O 완료: BL={result.bl_no}")
        except (ValueError, TypeError, AttributeError) as e:
            result.error_message = str(e)
            logger.error(f"[GeminiParser] D/O 오류: {e}")
        return result

    def parse_do_from_image(self, image_bytes: bytes, mime_type: str = "image/png") -> DOResult:
        """D/O 캡처 이미지를 Gemini API로 파싱 (파일 없이 직접 이미지 바이트)."""
        result = DOResult()
        try:
            logger.info("[GeminiParser] D/O 이미지 파싱 시작 (캡처/업로드 이미지)")
            prompt = self._get_do_prompt()
            response_text = self._call_gemini(prompt, image_bytes, mime_type=mime_type)
            result.raw_response = response_text
            data = self._extract_json(response_text)
            self._apply_do_json_to_result(result, data)
            logger.info(f"[GeminiParser] D/O 이미지 파싱 완료: BL={result.bl_no}")
        except (ValueError, TypeError, AttributeError) as e:
            result.error_message = str(e)
            logger.error(f"[GeminiParser] D/O 이미지 오류: {e}")
        return result

    # =========================================================================
    # 자동 문서 유형 감지 및 파싱
    # =========================================================================

    def parse_auto(self, pdf_path: str) -> Dict[str, Any]:
        """
        문서 유형을 자동 감지하여 파싱
        
        Returns:
            dict: {'type': 문서유형, 'result': 파싱결과}
        """
        filename = Path(pdf_path).name.upper()

        # ★★★ v2.9.19: 공백을 언더스코어로 정규화 (현장 파일명 대응) ★★★
        fname = re.sub(r"\s+", "_", filename)
        # ★★★ v2.9.21: 하이픈도 언더스코어로 정규화 (D-O → D_O) ★★★
        fname_normalized = re.sub(r"[-]", "_", fname)

        # 파일명으로 1차 판단 (정규화된 이름 사용)
        if 'PACKING' in fname or '_PL' in fname or 'PACKLIST' in fname:
            doc_type = 'PACKING_LIST'
        elif '_FA' in fname or 'INVOICE' in fname or 'FACTURA' in fname or re.search(r'(^|_)FA(\.|_|$)', fname):
            doc_type = 'INVOICE'
        elif '_BL' in fname or 'BILL' in fname or re.search(r'(^|_)BL(\.|_|$)', fname):
            doc_type = 'BL'
        elif ('_DO' in fname_normalized or 'DELIVERY' in fname or 'D_O' in fname_normalized or
              re.search(r'(^|_)DO(\.|_|$)', fname) or re.search(r'DO\.PDF$', fname) or
              '화물인도' in filename or '발급확인' in filename):
            doc_type = 'DO'
        else:
            # AI로 문서 유형 판단
            doc_type = self._detect_document_type(pdf_path)

        logger.info(f"[GeminiParser] 문서유형 감지: {filename} → {doc_type}")

        # 유형별 파싱
        if doc_type == 'PACKING_LIST':
            result = self.parse_packing_list(pdf_path)
        elif doc_type == 'INVOICE':
            result = self.parse_invoice(pdf_path)
        elif doc_type == 'BL':
            result = self.parse_bl(pdf_path)
        elif doc_type == 'DO':
            result = self.parse_do(pdf_path)
        else:
            result = None

        return {
            'type': doc_type,
            'result': result
        }

    def detect_document_type(self, pdf_path: str) -> str:
        """
        ★★★ v2.9.19: 호환성 메서드 ★★★
        외부 모듈이 detect_document_type()을 호출하는 경우를 지원합니다.
        (GeminiDocumentParser는 _detect_document_type이 private이므로)
        """
        try:
            result = self.parse_auto(pdf_path)
            return result.get("type", "UNKNOWN")
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"[GeminiParser] detect_document_type 오류: {e}")
            return "UNKNOWN"

    def _detect_document_type(self, pdf_path: str) -> str:
        """AI로 문서 유형 감지"""
        try:
            images = self._pdf_to_images(pdf_path, dpi=100)
            if not images:
                return 'UNKNOWN'

            prompt = """이 문서의 유형을 판단해주세요.

다음 중 하나만 응답해주세요:
- PACKING_LIST (패킹리스트, LOT 목록이 있는 문서)
- INVOICE (상업송장, 금액이 있는 문서)
- BL (선하증권, Bill of Lading)
- DO (화물인도지시서, Delivery Order)
- UNKNOWN (알 수 없음)

한 단어만 응답해주세요."""

            response = self._call_gemini(prompt, images[0])
            doc_type = response.strip().upper()

            if doc_type in ['PACKING_LIST', 'INVOICE', 'BL', 'DO']:
                return doc_type

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"[GeminiParser] 문서 유형 감지 실패: {e}")

        return 'UNKNOWN'


# =============================================================================
# 편의 함수
# =============================================================================

_global_parser: Optional[GeminiDocumentParser] = None


def get_gemini_parser(api_key: Optional[str] = None) -> GeminiDocumentParser:
    """전역 Gemini 파서 가져오기"""
    global _global_parser
    if _global_parser is None:
        _global_parser = GeminiDocumentParser(api_key)
    return _global_parser


def parse_with_gemini(pdf_path: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Gemini로 PDF 파싱 (간편 함수)"""
    parser = get_gemini_parser(api_key)
    return parser.parse_auto(pdf_path)


# =============================================================================
# 테스트
# =============================================================================

if __name__ == "__main__":
    logger.debug("=" * 60)
    logger.debug("Gemini Document Parser 테스트")
    logger.debug("=" * 60)

    if not HAS_GEMINI:
        logger.debug("❌ google-genai 미설치")
        logger.debug("   pip install google-genai")
        exit(1)

    if not HAS_PYMUPDF:
        logger.debug("❌ PyMuPDF 미설치")
        logger.debug("   pip install pymupdf")
        exit(1)

    logger.debug("✅ 의존성 확인 완료")
    logger.debug("사용법:")
    logger.debug("  from gemini_parser import GeminiDocumentParser")
    logger.debug("  parser = GeminiDocumentParser(api_key='your-key')")
    logger.debug("  result = parser.parse_packing_list('file.pdf')")
