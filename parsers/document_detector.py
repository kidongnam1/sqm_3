"""
SQM Inventory - 점수 기반 문서 감지 모듈
DocumentDetector: 파일명, 헤더, 패턴, 키워드 점수를 합산하여 문서 유형 판별

버전: 2.5.4
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """문서 유형 열거형"""
    INVOICE = "INVOICE"
    PACKING_LIST = "PACKING_LIST"
    BL = "BL"  # Bill of Lading
    DO = "DO"  # Delivery Order
    COA = "COA"  # Certificate of Analysis
    UNKNOWN = "UNKNOWN"


@dataclass
class ScoreEntry:
    """점수 항목"""
    source: str  # FILENAME, HEADER, PATTERN, KEYWORD
    points: int
    reason: str


@dataclass
class DetectionResult:
    """문서 감지 결과"""
    document_type: DocumentType
    confidence: float  # 0.0 ~ 1.0
    scores: Dict[DocumentType, int] = field(default_factory=dict)
    score_details: List[ScoreEntry] = field(default_factory=list)
    text_sample: str = ""

    def generate_report(self) -> str:
        """감지 리포트 생성"""
        lines = [
            "═" * 56,
            "📄 문서 감지 리포트",
            "═" * 56,
            f"결과: {self.document_type.value} (신뢰도: {self.confidence:.0%})",
            "",
            "📊 타입별 점수:",
        ]

        # 점수 내림차순 정렬
        sorted_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        for doc_type, score in sorted_scores:
            marker = "  ★" if doc_type == self.document_type else "   "
            lines.append(f"{marker} {doc_type.value}: {score}점")

        lines.append("")
        lines.append("📋 점수 근거 (Top 10):")

        # 점수 근거 상위 10개
        sorted_details = sorted(self.score_details, key=lambda x: x.points, reverse=True)[:10]
        for i, entry in enumerate(sorted_details, 1):
            lines.append(f"  {i}. [{entry.source}] +{entry.points}점: {entry.reason}")

        if self.text_sample:
            lines.append("")
            lines.append("📝 텍스트 샘플 (첫 200자):")
            lines.append(f"  {self.text_sample[:200]}...")

        lines.append("═" * 56)
        return "\n".join(lines)


class DocumentDetector:
    """
    점수 기반 문서 유형 감지기
    
    점수 체계:
    - 파일명 패턴: +50점 (최고 우선순위)
    - 헤더 고유 문구: +30점
    - 필드 패턴: +15점
    - 공통 키워드: +5점
    """

    # 파일명 패턴 (+50점)
    FILENAME_PATTERNS: Dict[DocumentType, List[str]] = {
        DocumentType.INVOICE: [
            r"_FA\b", r"_INV\b", r"INVOICE", r"FACTURA", r"_CI\b",
            r"COMMERCIAL[_\s]?INV",
        ],
        DocumentType.PACKING_LIST: [
            r"_PL\b", r"PACKING[_\s]?LIST", r"PKG[_\s]?LIST", r"_PKL\b",
        ],
        DocumentType.BL: [
            r"_BL\b", r"B[/]?L\b", r"BILL[_\s]?OF[_\s]?LADING", r"_BOL\b",
        ],
        DocumentType.DO: [
            r"_DO\b", r"DELIVERY[_\s]?ORDER", r"D[/]?O\b",
        ],
        DocumentType.COA: [
            r"_COA\b", r"CERTIFICATE[_\s]?OF[_\s]?ANALYSIS", r"ANALYSIS[_\s]?CERT",
        ],
    }

    # 헤더 고유 문구 (+30점) - 문서 상단에서만 나타나는 고유 문구
    HEADER_PATTERNS: Dict[DocumentType, List[str]] = {
        DocumentType.INVOICE: [
            r"COMMERCIAL\s+INVOICE",
            r"FACTURA\s+COMERCIAL",
            r"TAX\s+INVOICE",
            r"PROFORMA\s+INVOICE",
            r"INVOICE\s+NO[.:]",
        ],
        DocumentType.PACKING_LIST: [
            r"PACKING\s+LIST",
            r"LISTA\s+DE\s+EMPAQUE",
            r"DETAILED\s+PACKING",
        ],
        DocumentType.BL: [
            r"BILL\s+OF\s+LADING",
            r"MULTIMODAL\s+TRANSPORT",
            r"OCEAN\s+BILL",
            r"SEA\s+WAYBILL",
            r"B/L\s+NO[.:]",
        ],
        DocumentType.DO: [
            r"DELIVERY\s+ORDER",
            r"ORDEN\s+DE\s+ENTREGA",
            r"D/O\s+NO[.:]",
            r"RELEASE\s+ORDER",
        ],
        DocumentType.COA: [
            r"CERTIFICATE\s+OF\s+ANALYSIS",
            r"CERTIFICADO\s+DE\s+AN[AÁ]LISIS",
            r"QUALITY\s+CERTIFICATE",
            r"TEST\s+REPORT",
        ],
    }

    # 필드 패턴 (+15점) - 특정 문서에서 자주 나타나는 필드
    FIELD_PATTERNS: Dict[DocumentType, List[str]] = {
        DocumentType.INVOICE: [
            r"FOB\s+VALUE",
            r"UNIT\s+PRICE",
            r"TOTAL\s+AMOUNT",
            r"PAYMENT\s+TERMS",
            r"INCOTERMS",
            r"BANK\s+DETAILS",
        ],
        DocumentType.PACKING_LIST: [
            r"GROSS\s+WEIGHT",
            r"NET\s+WEIGHT",
            r"CBM",
            r"NO[.\s]+OF\s+PACKAGES",
            r"DIMENSIONS",
            r"MARKS\s+(&|AND)\s+NOS",
        ],
        DocumentType.BL: [
            r"SHIPPER",
            r"CONSIGNEE",
            r"NOTIFY\s+PARTY",
            r"PORT\s+OF\s+LOADING",
            r"PORT\s+OF\s+DISCHARGE",
            r"VESSEL\s+NAME",
            r"VOYAGE\s+NO",
            r"FREIGHT\s+PREPAID",
            r"FREIGHT\s+COLLECT",
        ],
        DocumentType.DO: [
            r"CONTAINER\s+NO",
            r"SEAL\s+NO",
            r"TERMINAL",
            r"PICKUP\s+DATE",
            r"DELIVERY\s+TO",
        ],
        DocumentType.COA: [
            r"LOT\s+NO",
            r"BATCH\s+NO",
            r"SPECIFICATION",
            r"TEST\s+METHOD",
            r"RESULT",
            r"PURITY",
            r"MOISTURE",
        ],
    }

    # 공통 키워드 (+5점)
    COMMON_KEYWORDS: Dict[DocumentType, List[str]] = {
        DocumentType.INVOICE: [
            "INVOICE", "AMOUNT", "PRICE", "VALUE", "PAYMENT", "USD", "EUR",
        ],
        DocumentType.PACKING_LIST: [
            "WEIGHT", "PACKAGE", "CARTON", "PALLET", "KG", "MT",
        ],
        DocumentType.BL: [
            "VESSEL", "VOYAGE", "LADEN", "BOARD", "CARRIER", "SHIPPING",
        ],
        DocumentType.DO: [
            "DELIVERY", "RELEASE", "PICKUP", "TERMINAL", "CONTAINER",
        ],
        DocumentType.COA: [
            "ANALYSIS", "QUALITY", "SPECIFICATION", "TEST", "PURITY", "RESULT",
        ],
    }

    def __init__(self, min_confidence_gap: int = 10):
        """
        Args:
            min_confidence_gap: 1위와 2위 점수 차이가 이 값 미만이면 UNKNOWN 반환
        """
        self.min_confidence_gap = min_confidence_gap

    def detect(self, text: str, filename: str = "") -> DetectionResult:
        """
        문서 유형 감지
        
        Args:
            text: 문서 텍스트 내용
            filename: 파일명 (옵션)
        
        Returns:
            DetectionResult: 감지 결과
        """
        scores: Dict[DocumentType, int] = {dt: 0 for dt in DocumentType if dt != DocumentType.UNKNOWN}
        details: List[ScoreEntry] = []

        # 텍스트 정규화
        text_upper = text.upper()
        text_normalized = re.sub(r'\s+', ' ', text_upper)

        # 1. 파일명 패턴 검사 (+50점)
        if filename:
            filename_upper = filename.upper()
            for doc_type, patterns in self.FILENAME_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, filename_upper, re.IGNORECASE):
                        scores[doc_type] += 50
                        details.append(ScoreEntry(
                            source="FILENAME",
                            points=50,
                            reason=f"파일명 패턴 매칭: {pattern}"
                        ))
                        break  # 파일명당 하나의 패턴만 적용

        # 2. 헤더 고유 문구 검사 (+30점) - 상단 1000자에서만 검색
        header_text = text_normalized[:1000]
        for doc_type, patterns in self.HEADER_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, header_text, re.IGNORECASE):
                    scores[doc_type] += 30
                    details.append(ScoreEntry(
                        source="HEADER",
                        points=30,
                        reason=f"헤더 고유 문구: {pattern}"
                    ))

        # 3. 필드 패턴 검사 (+15점)
        for doc_type, patterns in self.FIELD_PATTERNS.items():
            matched_count = 0
            for pattern in patterns:
                if re.search(pattern, text_normalized, re.IGNORECASE):
                    matched_count += 1
                    if matched_count <= 3:  # 최대 3개까지만 점수 부여
                        scores[doc_type] += 15
                        details.append(ScoreEntry(
                            source="PATTERN",
                            points=15,
                            reason=f"필드 패턴: {pattern}"
                        ))

        # 4. 공통 키워드 검사 (+5점)
        for doc_type, keywords in self.COMMON_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_upper:
                    scores[doc_type] += 5
                    details.append(ScoreEntry(
                        source="KEYWORD",
                        points=5,
                        reason=f"키워드: {keyword}"
                    ))

        # 결과 판정
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_type, top_score = sorted_scores[0]
        second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

        # 신뢰도 계산
        total_score = sum(scores.values())
        confidence = top_score / total_score if total_score > 0 else 0.0

        # 점수 차이가 너무 작으면 UNKNOWN
        if top_score == 0 or (top_score - second_score) < self.min_confidence_gap:
            final_type = DocumentType.UNKNOWN
            confidence = 0.0
        else:
            final_type = top_type

        return DetectionResult(
            document_type=final_type,
            confidence=confidence,
            scores=scores,
            score_details=details,
            text_sample=text[:200] if text else ""
        )

    def detect_from_file(self, filepath: str, text: str = "") -> DetectionResult:
        """
        파일 경로에서 문서 유형 감지
        
        Args:
            filepath: 파일 경로
            text: 이미 추출된 텍스트 (없으면 빈 문자열)
        
        Returns:
            DetectionResult: 감지 결과
        """
        filename = Path(filepath).name
        return self.detect(text, filename)


# 편의 함수
def detect_document_type(text: str, filename: str = "") -> DocumentType:
    """
    간단한 문서 유형 감지
    
    Args:
        text: 문서 텍스트
        filename: 파일명 (옵션)
    
    Returns:
        DocumentType: 감지된 문서 유형
    """
    detector = DocumentDetector()
    result = detector.detect(text, filename)
    return result.document_type


def detect_with_report(text: str, filename: str = "") -> Tuple[DocumentType, str]:
    """
    문서 유형 감지 + 리포트 반환
    
    Args:
        text: 문서 텍스트
        filename: 파일명 (옵션)
    
    Returns:
        Tuple[DocumentType, str]: (문서 유형, 리포트 문자열)
    """
    detector = DocumentDetector()
    result = detector.detect(text, filename)
    return result.document_type, result.generate_report()


# 테스트 코드
if __name__ == "__main__":
    # 테스트 케이스
    test_cases = [
        {
            "filename": "2200033057_FA.pdf",
            "text": "COMMERCIAL INVOICE\nFOB VALUE: USD 50,000\nPAYMENT TERMS: T/T"
        },
        {
            "filename": "2200033057_PL.pdf",
            "text": "PACKING LIST\nGROSS WEIGHT: 25,000 KG\nNET WEIGHT: 24,500 KG"
        },
        {
            "filename": "2200033057_BL.pdf",
            "text": "BILL OF LADING\nSHIPPER: SQM CHILE\nCONSIGNEE: TO ORDER\nVESSEL: EVER GIVEN"
        },
    ]

    detector = DocumentDetector()

    for case in test_cases:
        result = detector.detect(case["text"], case["filename"])
        logger.debug(f"{result.generate_report()}")
