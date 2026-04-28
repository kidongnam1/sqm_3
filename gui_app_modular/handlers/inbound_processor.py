"""
SQM 재고관리 - 입고 처리 Mixin (v5.6.5)
========================================

v5.6.5: 입고 경로 단일화
  - 모든 PDF 입고 → OneStopInboundDialog (유일한 경로)
  - Excel 입고 → import_handlers._bulk_import_inventory_simple
  - 서류별 개별 입고(Invoice/BL/DO 단독) 제거 → 원스톱으로 통합
  - 기존 6개 진입점 → 하위호환 래퍼로 _on_pdf_inbound 단일 호출
"""

import logging
import os
from tkinter import filedialog

logger = logging.getLogger(__name__)


class InboundProcessorMixin:
    """입고 처리 Mixin — v5.6.5 단일 경로"""

    # ══════════════════════════════════════════════════════════
    # 유일한 PDF 입고 진입점
    # ══════════════════════════════════════════════════════════

    def _on_pdf_inbound(self, initial_files: dict = None) -> None:
        """v5.6.5: PDF 입고 — OneStopInboundDialog

        FA + PL + BL 필수 (Gate-1), DO 선택.
        initial_files: {'DO': 경로} 등 드래그앤드롭/캡처 이미지 사전 지정.
        """
        self._log("")
        self._log(f"{'=' * 50}")
        self._log("📥 PDF 입고 (원스톱)")
        self._log(f"{'=' * 50}")

        try:
            from ..dialogs.onestop_inbound import OneStopInboundDialog
            dialog = OneStopInboundDialog(
                parent=self.root,
                engine=self.engine,
                log_fn=self._log,
                app=self
            )
            dialog.show(initial_files=initial_files or {})
        except (ImportError, ModuleNotFoundError) as e:
            self._log(f"❌ 원스톱 입고 오류: {e}")
            logger.error(f"원스톱 입고 오류: {e}", exc_info=True)

    def _on_pdf_inbound_quick_folder(self) -> None:
        """빠른 PDF 스캔(폴더): 폴더 1회 선택으로 4종 서류 자동 탐지 후 즉시 파싱."""
        folder = filedialog.askdirectory(parent=self.root, title="빠른 PDF 스캔 폴더 선택")
        if not folder:
            return

        # v6.4.2: 1차 현재 폴더 탐색, 없으면 하위 1단계 자동 재탐색
        candidate_paths = self._collect_candidate_files(folder)
        if not candidate_paths:
            self._log("⚠️ 선택한 폴더(및 하위 1단계)에 PDF/이미지 파일이 없습니다.")
            return

        file_names = [os.path.basename(p) for p in candidate_paths]
        actual_folder = os.path.dirname(candidate_paths[0])

        detected = self._detect_inbound_docs_from_folder(actual_folder, file_names)
        required = ("PACKING_LIST", "INVOICE", "BL")
        missing_required = [k for k in required if k not in detected]
        if missing_required:
            kor = {
                "PACKING_LIST": "Packing List",
                "INVOICE": "Invoice / FA",
                "BL": "Bill of Lading",
                "DO": "Delivery Order",
            }
            miss = ", ".join(kor.get(k, k) for k in missing_required)
            self._log(f"⚠️ 빠른 스캔 중단 — 필수 서류 누락: {miss}")
            self._log(f"📁 탐색 위치: {actual_folder}")
            self._log("   → 해당 폴더에 PL / Invoice(FA) / BL 파일이 있는지 확인해 주세요.")
            return  # ← fallback 없음: 빠른입고는 빠른입고답게 종료

        summary = ", ".join(f"{k}={os.path.basename(v)}" for k, v in detected.items())
        self._log("⚡ 빠른 PDF 스캔: 자동 파싱 모드로 원스톱 창 오픈")
        self._log(f"   탐지 서류: {summary}")
        try:
            from ..dialogs.onestop_inbound import OneStopInboundDialog
            dialog = OneStopInboundDialog(
                parent=self.root,
                engine=self.engine,
                log_fn=self._log,
                app=self
            )
            dialog.show(
                initial_files=detected,
                auto_start_parse=False,   # v8.0.6: 빠른 스캔도 확인창 표시
                skip_parse_confirm=False, # v8.0.6: 확인 팝업 표시
            )
        except (ImportError, ModuleNotFoundError) as e:
            self._log(f"❌ 원스톱 입고 오류: {e}")
            logger.error(f"원스톱 입고 오류: {e}", exc_info=True)

    def _collect_candidate_files(self, folder: str) -> list[str]:
        """위임 → InboundDocDetector.collect_candidate_files()"""
        return self._doc_detector().collect_candidate_files(folder)


    def _detect_inbound_docs_from_folder(
        self, folder: str, file_names: list[str]
    ) -> dict:
        """위임 → InboundDocDetector.detect_from_folder()"""
        return self._doc_detector().detect_from_folder(folder, file_names)


    def _detect_by_pdf_text(
        self, pdf_paths: list, missing_types: list
    ) -> dict:
        """위임 → InboundDocDetector.detect_by_pdf_text()"""
        return self._doc_detector().detect_by_pdf_text(pdf_paths, missing_types)

    def _doc_detector(self):
        """InboundDocDetector 인스턴스 (lazy init, log_fn 바인딩)."""
        if not hasattr(self, '_cached_doc_detector'):
            from ..handlers.inbound_doc_detector import InboundDocDetector
            self._cached_doc_detector = InboundDocDetector(log_fn=self._log)
        return self._cached_doc_detector


    # ══════════════════════════════════════════════════════════
    # 하위 호환 래퍼 — 기존 코드(메뉴/단축키/D&D)에서 호출 유지
    # ══════════════════════════════════════════════════════════

    def _on_onestop_inbound(self) -> None:
        """[하위호환] → _on_pdf_inbound"""
        self._on_pdf_inbound()

    def _on_sequential_inbound(self) -> None:
        """[하위호환] → _on_pdf_inbound"""
        self._on_pdf_inbound()

    def _on_inbound_by_type(self, doc_type: str = '') -> None:
        """[하위호환] 서류별 개별 입고 → 원스톱 통합"""
        self._on_pdf_inbound()

    def _process_inbound(self, pdf_path: str) -> None:
        """[하위호환] 단일 파일 D&D/키보드 → 원스톱"""
        self._on_pdf_inbound()

    # ══════════════════════════════════════════════════════════
    # D/O 후속 연결 (v5.6.6)
    # ══════════════════════════════════════════════════════════

    def _on_do_update(self) -> None:
        """v5.6.6: D/O 후속 연결 — 기존 LOT에 도착일/Free Time UPDATE"""
        self._log("")
        self._log("📋 D/O 후속 연결")

        try:
            from ..dialogs.do_update_dialog import DOUpdateDialog
            dialog = DOUpdateDialog(
                parent=self.root,
                engine=self.engine,
                log_fn=self._log,
                app=self
            )
            dialog.show()
        except (ImportError, ModuleNotFoundError) as e:
            self._log(f"❌ D/O 후속 연결 오류: {e}")
            logger.error(f"D/O 후속 연결 오류: {e}", exc_info=True)
