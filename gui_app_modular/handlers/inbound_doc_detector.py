"""
SQM 재고관리 - 입고 서류 자동 탐지 모듈 (v6.5.0)
=================================================

inbound_processor.py 에서 탐지 로직 3개를 분리:
  - InboundDocDetector._collect_candidate_files()
  - InboundDocDetector._detect_inbound_docs_from_folder()
  - InboundDocDetector._detect_by_pdf_text()

분리 이유:
  - inbound_processor.py 338줄 → 탐지 전담 모듈로 단일 책임 원칙 적용
  - 독립 테스트 가능 (pytest fixtures 직접 주입)
  - 향후 AI 탐지 엔진 교체 시 이 파일만 수정
"""

import logging
import os
import re

logger = logging.getLogger(__name__)


class InboundDocDetector:
    """입고 서류 자동 탐지 엔진 (파일명 1차 + PDF 텍스트 2차).

    의존성:
      - log_fn: 로그 출력 콜백 (없으면 logger 사용)
      - pdfplumber: 2차 텍스트 탐지에만 필요 (optional)
    """

    # ── 파일명 1차 탐지 키워드 맵 ──────────────────────────────
    # ── v9.0: 파일명 1차 탐지 키워드 맵 (BL 변형 + DO 우선 강화) ──
    FILENAME_KEYWORD_MAP: dict[str, list[str]] = {
        "PACKING_LIST": [
            "packing", "packlist", "p l", " pl ", "포장", "명세서",
        ],
        "INVOICE": [
            "invoice", "inv ", " inv", " fa ", "fa ", "송장", "화인보이스",
        ],
        "BL": [
            "seawaybill", "sea waybill", "billoflading", "bill of lading",
            "b/l", " bl ", " bl.", "선하증권", "선하",
            # 선사별 고유 BL 번호 패턴 (파일명이 선사번호 자체인 경우)
            "medu", "maeu", "maersk", "hmm", "cma", "cgmu", "one ",
        ],
        "DO": [
            "delivery order",   # v9.0: 구체적 표현 먼저 (delivery 단독보다 우선)
            "delivery",
            "d/o", " do ", " do.", "인도", "인도지시서",
            "release order", "cargo release",  # v9.0: DO 추가 신호
        ],
    }

    # ── v9.0: PDF 텍스트 2차 탐지 키워드 맵 (강신호 추가) ──────
    TEXT_KEYWORD_MAP: dict[str, list[str]] = {
        "DO": [   # v9.0: DO를 맨 앞으로 이동 → 우선 판별
            "delivery order", "d/o no", "d/o number",
            "release order", "cargo release",
            "forwarder release", "terminal release",
            "인도지시서", "free time", "container release",
            "container pickup",
        ],
        "BL": [
            "non-negotiable waybill", "sea waybill", "seawaybill",  # v9.0: NON-NEGOTIABLE 강신호
            "bill of lading", "b/l no", "b/l number",              # v9.0: B/L No. 추가
            "선하증권", "maersk", "msc", "hmm", "cma cgm",
            "vessel", "port of loading", "port of discharge",
            "shipper", "consignee", "notify party",
            "signed for the carrier",                               # v9.0: BL 서명 문구
        ],
        "PACKING_LIST": [
            "packing list", "packinglist", "포장명세서", "명세서",
            "net weight", "gross weight", "maxibag", "tonbag",
            "package", "bags", "pallets",                           # v9.0: 포장 단위 추가
        ],
        "INVOICE": [
            "commercial invoice",                                    # v9.0: 구체적 표현 우선
            "invoice no", "invoice number",                         # v9.0: Invoice No. 추가
            "invoice", "factura",
            "export invoice", "송장", "화인보이스",
            "unit price", "total value", "seller", "buyer",         # v9.0: 거래 주체 추가
            "factura de exportacion",
        ],
    }

    # ── 지원 확장자 (대소문자 .lower() 비교) ────────────────────
    EXT_ALLOW: set[str] = {".pdf", ".png", ".jpg", ".jpeg"}

    def __init__(self, log_fn=None):
        self._log_fn = log_fn or (lambda msg: logger.info(msg))

    def _log(self, msg: str) -> None:
        self._log_fn(msg)

    # ══════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════

    def collect_candidate_files(self, folder: str) -> list[str]:
        """1차 현재 폴더 탐색 → 없으면 하위 1단계 폴더 자동 재탐색.

        반환: 발견된 파일 전체 경로 목록 (빈 리스트 = 탐색 실패)

        v6.4.2: 상위 폴더 선택 시에도 하위 폴더 자동 발견
        v6.4.3: 대소문자 확장자 모두 허용 (.PDF / .JPG 등)
        """
        def _files_in(d: str) -> list[str]:
            try:
                return [
                    os.path.join(d, n) for n in os.listdir(d)
                    if os.path.isfile(os.path.join(d, n))
                    and os.path.splitext(n)[1].lower() in self.EXT_ALLOW
                ]
            except Exception:
                return []

        # 1차: 선택 폴더 직접
        files = _files_in(folder)
        if files:
            self._log(f"📂 탐색 위치 (직접): {folder}  ({len(files)}개)")
            return files

        # 2차: 하위 1단계
        self._log("🔍 현재 폴더에 파일 없음 → 하위 폴더 자동 탐색 중...")
        try:
            subdirs = [
                os.path.join(folder, n) for n in os.listdir(folder)
                if os.path.isdir(os.path.join(folder, n))
            ]
        except Exception:
            return []

        for sub in sorted(subdirs, reverse=True):   # 최신(역순) 폴더 우선
            sub_files = _files_in(sub)
            if sub_files:
                self._log(f"📂 탐색 위치 (하위): {sub}  ({len(sub_files)}개)")
                return sub_files

        return []

    def detect_from_folder(self, folder: str, file_names: list[str]) -> dict:
        """파일명 1차 + PDF 텍스트 2차 통합 탐지.

        탐지 우선순위:
          1) 파일명 키워드 (대소문자 무시, 공백 경계 매칭)
          2) BL 번호 자체가 파일명인 경우 (9~12자리 숫자 / MEDU 등)
          3) 미탐지 PDF → pdfplumber 첫 400자 텍스트 탐지

        반환: {"PACKING_LIST": "/path/...", "INVOICE": "...", "BL": "...", "DO": "..."}
        """
        bucket: dict[str, list] = {k: [] for k in self.FILENAME_KEYWORD_MAP}

        for name in file_names:
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in self.EXT_ALLOW:
                continue

            # v9.0: B-L / B.L 변형 표기 사전 정규화
            name_lower = name.lower()
            name_lower = re.sub(r'b[-.]l', 'bl', name_lower)  # B-L/B.L → bl (v9.0)

            # 공백 경계 매칭: "2200034276_BL.pdf" → " 2200034276 bl pdf "
            key_name = " " + re.sub(r"[\s_\-\.]+", " ", name_lower) + " "

            stem = os.path.splitext(name)[0]
            score = os.path.getmtime(path)

            # ── v9.0: DO 우선 체크 (BL 번호 패턴보다 먼저) ──────────────
            # DO 키워드가 파일명에 있으면 BL 번호 패턴보다 DO 우선 적용
            do_keys = self.FILENAME_KEYWORD_MAP.get("DO", [])
            if any(k in key_name for k in do_keys):
                bucket["DO"].append((score, path))
                continue

            # ── v9.0: BL 번호 패턴 (선사코드 포함) ──────────────────────
            # 기존: [A-Z]{4} → 수정: [A-Z]{2,4} (MSC=3자, HMM=3자 대응)
            is_bl_number = bool(
                re.fullmatch(r'\d{9,12}', stem)                    # 9~12자리 숫자
                or re.fullmatch(r'[A-Z]{4}[A-Z0-9]{5,}', stem)      # MEDU/MAEU 4자+
                or re.fullmatch(r'[A-Z]{2,3}[A-Z0-9]{8,12}', stem)  # MSC/HMM 2~3자+
            )

            # v9.0: 'release' 단독 파일명은 BL/DO 확정 불가 → 2차 텍스트 탐지로 보냄
            if is_bl_number:
                if re.search(r'release', key_name) and not re.search(r' bl | do | delivery ', key_name):
                    continue  # 2차 텍스트 탐지로 넘김
                bucket["BL"].append((score, path))
                continue

            # ── 일반 키워드 매칭 (DO 제외, 이미 처리됨) ─────────────────
            for doc_type, keys in self.FILENAME_KEYWORD_MAP.items():
                if doc_type == "DO":
                    continue   # 위에서 이미 처리
                if any(k in key_name for k in keys):
                    bucket[doc_type].append((score, path))

        # 최신 파일 우선 선택
        detected: dict[str, str] = {}
        for doc_type, candidates in bucket.items():
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                detected[doc_type] = candidates[0][1]

        # v6.5.0: 2차 텍스트 탐지 — 파일명으로 못 찾은 서류 대상
        # v9.0: DO도 2차 탐지 대상 포함 + DO 우선 순서
        missing = [k for k in ("DO", "BL", "PACKING_LIST", "INVOICE") if k not in detected]
        if missing:
            assigned = set(detected.values())
            unmatched = [
                os.path.join(folder, n) for n in file_names
                if os.path.splitext(n)[1].lower() == ".pdf"
                and os.path.join(folder, n) not in assigned
                and os.path.isfile(os.path.join(folder, n))
            ]
            if unmatched:
                text_det = self.detect_by_pdf_text(unmatched, missing)
                detected.update(text_det)
                if text_det:
                    summary = ", ".join(
                        f"{k}={os.path.basename(v)}" for k, v in text_det.items()
                    )
                    self._log(f"🔍 PDF 텍스트 2차 탐지: {summary}")

        return detected

    def detect_by_pdf_text(self, pdf_paths: list, missing_types: list) -> dict:
        """PDF 첫 페이지 텍스트 기반 2차 서류 탐지.

        파일명으로 탐지 실패한 PDF(스캔001.pdf 등)를 pdfplumber로
        첫 페이지 400자만 읽어 서류 유형을 판별합니다.

        Args:
            pdf_paths:     아직 분류 안 된 PDF 경로 목록
            missing_types: 아직 탐지 못한 서류 유형 리스트

        Returns:
            {"PACKING_LIST": "/path/...", ...}
        """
        detected: dict[str, str] = {}
        try:
            import pdfplumber
        except ImportError:
            logger.debug("pdfplumber 없음 — PDF 텍스트 2차 탐지 스킵")
            return detected

        for pdf_path in pdf_paths:
            text = ""
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    if pdf.pages:
                        raw = pdf.pages[0].extract_text() or ""
                        text = raw[:800].lower()  # v9.0: 400→800자 (DO/BL 키워드 더 잘 잡힘)
            except Exception as e:
                logger.debug(
                    "PDF 텍스트 추출 실패 [%s]: %s",
                    os.path.basename(pdf_path), e
                )
                continue

            if not text:
                continue

            for doc_type in missing_types:
                if doc_type in detected:
                    continue
                keywords = self.TEXT_KEYWORD_MAP.get(doc_type, [])
                if any(kw in text for kw in keywords):
                    detected[doc_type] = pdf_path
                    logger.info(
                        "PDF 텍스트 탐지: %s → %s",
                        os.path.basename(pdf_path), doc_type
                    )
                    break   # PDF 1개 = 서류 유형 1개

        return detected
