# -*- coding: utf-8 -*-
"""
SQM 재고관리 - 메뉴 설정 Mixin
==============================

v3.0 - ttkbootstrap 기반 커스텀 메뉴바
v2.9.91 - gui_app.py에서 분리

메뉴바 구성, 단축키 설정
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
import os
import configparser
import sqlite3

from ..utils.ui_constants import CustomMessageBox
logger = logging.getLogger(__name__)


class MenuMixin:
    """
    메뉴 설정 Mixin
    
    SQMInventoryApp 클래스에 mix-in 됩니다.
    v3.0: ttkbootstrap 기반 커스텀 메뉴바 사용
    """
    
    # 메뉴바 스타일: 'custom' (ttkbootstrap) 또는 'native' (tk.Menu)
    MENUBAR_STYLE = 'custom'

    def _get_return_doc_review_pending_count(self, days: int = 30) -> int:
        """최근 N일 반품 문서점검 대기건(RETURN_DOC_REVIEW) 개수."""
        try:
            row = self.engine.db.fetchone(
                """
                SELECT COUNT(*) AS cnt
                FROM stock_movement
                WHERE movement_type = 'RETURN_DOC_REVIEW'
                  AND DATE(created_at) >= DATE('now', ?)
                """,
                (f"-{int(days)} days",),
            )
            if not row:
                return 0
            return int((row.get('cnt') if isinstance(row, dict) else row[0]) or 0)
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError, TypeError, KeyError, AttributeError) as e:
            logger.debug(f"반품 문서점검 카운트 조회 오류: {e}")
            return 0

    @staticmethod
    def _format_return_review_badge(count: int) -> str:
        """
        반품 문서점검 메뉴 배지 문자열.
        - 0건: 표시 없음
        - 1~4건: 🟡 [N]
        - 5건 이상: 🔴 [N]
        """
        if count <= 0:
            return ""
        icon = "🔴" if count >= 5 else "🟡"
        return f" {icon} [{count}]"

    def _is_developer_mode_enabled(self) -> bool:
        """settings.ini [ui] developer_mode 플래그."""
        cfg = configparser.ConfigParser()
        try:
            cfg.read(os.path.join(os.getcwd(), 'settings.ini'), encoding='utf-8')
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            logger.debug(f"개발자 모드 설정 읽기 실패(무시): {e}")
            return False
        return cfg.getboolean('ui', 'developer_mode', fallback=False)

    def _set_developer_mode_enabled(self, enabled: bool) -> bool:
        """개발자 모드 플래그 저장."""
        cfg = configparser.ConfigParser()
        settings_path = os.path.join(os.getcwd(), 'settings.ini')
        try:
            cfg.read(settings_path, encoding='utf-8')
            if not cfg.has_section('ui'):
                cfg.add_section('ui')
            cfg.set('ui', 'developer_mode', '1' if enabled else '0')
            with open(settings_path, 'w', encoding='utf-8') as f:
                cfg.write(f)
            return True
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"개발자 모드 설정 저장 실패: {e}", exc_info=True)
            return False
    
    def _setup_menu(self) -> None:
        """메뉴 구성"""
        if self.MENUBAR_STYLE == 'custom':
            self._setup_custom_menu()
        else:
            self._setup_native_menu()
    
    def _setup_custom_menu(self) -> None:
        """v3.0: ttkbootstrap 커스텀 메뉴바"""
        try:
            from .custom_menubar import CustomMenuBar
            
            self.custom_menubar = CustomMenuBar(self.root, self)
            self.recent_menu = self.custom_menubar.get_recent_menu()
            
            self._log("✅ 커스텀 메뉴바 적용")
            logger.info("커스텀 메뉴바 생성 완료")
            
        except (ImportError, ModuleNotFoundError) as e:
            logger.error(f"커스텀 메뉴바 생성 실패: {e}, 네이티브 메뉴바 사용")
            self._setup_native_menu()
    
    def _setup_native_menu(self) -> None:
        """기존 네이티브 메뉴바 (fallback)"""
        from ..utils.constants import tk
        from ..utils.constants import (
            HAS_GEMINI, HAS_DB_PROTECTION, HAS_FEATURES, HAS_FEATURES_V2
        )
        
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # =====================================================
        # 파일 메뉴
        # =====================================================
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="파일", menu=file_menu)
        
        from ..menu_registry import (
            FILE_MENU_INBOUND_ITEMS,
            FILE_MENU_INBOUND_RETURN_SUB_ITEMS,
            FILE_MENU_OUTBOUND_ITEMS,
            FILE_MENU_EXPORT_ITEMS,
            FILE_MENU_BACKUP_ITEMS,
        )
        
        file_menu.add_command(
            label="📥 PDF 입고  (Ctrl+I)",
            command=self._on_pdf_inbound
        )
        
        # 출고 서브메뉴 — menu_registry 단일 소스 (Picking List 등 누락 방지)
        outbound_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="📤 출고", menu=outbound_menu)
        for entry in FILE_MENU_OUTBOUND_ITEMS:
            if entry is None:
                outbound_menu.add_separator()
                continue
            label, method_name = entry[0], entry[1]
            optional = entry[2] if len(entry) > 2 else False
            if optional and (not hasattr(self, method_name) or not callable(getattr(self, method_name))):
                continue
            cmd = getattr(self, method_name, None)
            if callable(cmd):
                outbound_menu.add_command(label=label, command=cmd)
        
        file_menu.add_separator()
        
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="📂 최근 파일", menu=self.recent_menu)
        self._update_recent_files_menu()
        
        file_menu.add_separator()
        
        # 업로드 메뉴 — menu_registry 기반 (입고 + 출고 동일 목록)
        _font = ('맑은 고딕', 14)
        upload_menu = tk.Menu(file_menu, tearoff=0, font=_font)
        file_menu.add_cascade(label="📥 업로드 메뉴", menu=upload_menu)
        for entry in FILE_MENU_INBOUND_ITEMS:
            if entry is None:
                upload_menu.add_separator()
                continue
            if entry[1] == "_show_return_dialog":
                continue
            label, method_name = entry[0], entry[1]
            cmd = getattr(self, method_name, None)
            if callable(cmd):
                upload_menu.add_command(label="  " + label, command=cmd, font=_font)
        upload_menu.add_separator()
        for entry in FILE_MENU_OUTBOUND_ITEMS:
            if entry is None:
                upload_menu.add_separator()
                continue
            label, method_name = entry[0], entry[1]
            optional = entry[2] if len(entry) > 2 else False
            if optional and (not hasattr(self, method_name) or not callable(getattr(self, method_name))):
                continue
            cmd = getattr(self, method_name, None)
            if callable(cmd):
                upload_menu.add_command(label="  " + label, command=cmd, font=_font)
        upload_menu.add_separator()
        _return_cmd = getattr(self, "_show_return_dialog", None)
        pending = self._get_return_doc_review_pending_count(30)
        return_label = f"  🔄 반품 (재입고){self._format_return_review_badge(pending)}"
        if callable(_return_cmd):
            return_sub = tk.Menu(upload_menu, tearoff=0, font=_font)
            upload_menu.add_cascade(label=return_label, menu=return_sub, font=_font)
            for sub_label, mode in FILE_MENU_INBOUND_RETURN_SUB_ITEMS:
                return_sub.add_command(label="  " + sub_label, command=lambda md=mode: _return_cmd(md), font=_font)
        else:
            upload_menu.add_command(
                label=return_label,
                command=lambda: CustomMessageBox.showinfo(self.root, "반품", "반품 기능 필요"),
                font=_font
            )
        
        export_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="💾 내보내기  (Ctrl+E)", menu=export_menu)
        for label, option in FILE_MENU_EXPORT_ITEMS:
            export_menu.add_command(label=label, command=lambda op=option: self._on_export_click(op))
        
        file_menu.add_separator()
        
        backup_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="🔐 백업  (Ctrl+B)", menu=backup_menu)
        for label, method_name in FILE_MENU_BACKUP_ITEMS:
            cmd = getattr(self, method_name, None)
            if callable(cmd):
                backup_menu.add_command(label=label, command=cmd)
        
        file_menu.add_separator()
        file_menu.add_command(label="종료", command=self.root.quit)

        # =====================================================
        # 보고서 메뉴 (거래 명세서 등)
        # =====================================================
        report_top_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="보고서", menu=report_top_menu)
        report_top_menu.add_command(label="📄 거래 명세서", command=self._generate_invoice_pdf)
        report_top_menu.add_command(label="📦 재고 현황", command=self._generate_inventory_pdf)
        report_top_menu.add_command(label="📈 입출고 내역", command=self._generate_transaction_pdf)
        report_top_menu.add_command(label="🔖 LOT 상세", command=self._generate_lot_detail_pdf)
        
        # =====================================================
        # 도구 메뉴
        # =====================================================
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="도구", menu=tools_menu)
        
        # v5.9.0: 컨테이너 구분 → 필터바 초기화 옆으로 이동 (변수만 초기화)
        if not hasattr(self, '_container_suffix_var'):
            self._container_suffix_var = tk.BooleanVar(value=True)
        tools_menu.add_command(label="📦 제품 마스터 관리", command=self._show_product_master)
        tools_menu.add_command(label="📊 제품별 재고 현황", command=self._show_product_inventory_report)
        tools_menu.add_separator()
        tools_menu.add_command(label="📋 D/O 후속 연결", command=self._on_do_update)
        tools_menu.add_separator()
        
        pdf_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="📄 PDF/이미지 변환", menu=pdf_menu)
        pdf_menu.add_command(label="→ Excel", command=self._convert_pdf_to_excel)
        pdf_menu.add_command(label="→ Word", command=self._convert_pdf_to_word)
        pdf_menu.add_separator()
        pdf_menu.add_command(label="📁 일괄 변환", command=self._batch_convert_pdf_excel)
        pdf_menu.add_command(label="🔍 분석", command=self._analyze_pdf)
        tools_menu.add_separator()
        
        report_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="📋 PDF 보고서", menu=report_menu)
        report_menu.add_command(label="📦 재고 현황", command=self._generate_inventory_pdf)
        report_menu.add_command(label="📈 입출고 내역", command=self._generate_transaction_pdf)
        report_menu.add_command(label="🔖 LOT 상세", command=self._generate_lot_detail_pdf)
        tools_menu.add_separator()
        
        if HAS_GEMINI:
            api_menu = tk.Menu(tools_menu, tearoff=0)
            tools_menu.add_cascade(label="🤖 Gemini", menu=api_menu)
            self._gemini_var = tk.BooleanVar(value=getattr(self, 'use_gemini', False))
            api_menu.add_checkbutton(label="API 사용", variable=self._gemini_var, command=self._toggle_gemini)
            api_menu.add_separator()
            api_menu.add_command(label="💬 AI 채팅", command=self._open_ai_chat)
            api_menu.add_command(label="⚙️ 설정", command=self._show_api_settings)
            api_menu.add_command(label="🔬 테스트", command=self._test_gemini_api)
            tools_menu.add_separator()
        
        if HAS_DB_PROTECTION:
            db_menu = tk.Menu(tools_menu, tearoff=0)
            tools_menu.add_cascade(label="🛡️ DB 보호", menu=db_menu)
            db_menu.add_command(label="🔍 무결성 검증", command=self._verify_db_integrity)
            db_menu.add_command(label="📋 작업 로그", command=self._show_action_log)
            db_menu.add_command(label="💾 로그 내보내기", command=self._export_action_log)
            db_menu.add_separator()
            db_menu.add_command(label="🔄 체크섬 갱신", command=self._update_checksum)
            tools_menu.add_separator()
        
        tools_menu.add_command(label="🔍 DB 검사", command=self._on_integrity_check)
        tools_menu.add_command(label="🔧 DB 최적화", command=self._on_optimize_db)
        tools_menu.add_separator()
        tools_menu.add_command(label="📋 로그 정리", command=self._on_cleanup_logs)
        tools_menu.add_command(label="ℹ️ DB 정보", command=self._show_db_info)
        tools_menu.add_separator()
        if self._is_developer_mode_enabled():
            tools_menu.add_command(label="🗑️ 테스트 DB 초기화 (데이터 삭제)", command=self._show_test_db_reset_popup)
        
        if HAS_FEATURES:
            tools_menu.add_separator()
            adv_menu = tk.Menu(tools_menu, tearoff=0)
            tools_menu.add_cascade(label="✨ 고급", menu=adv_menu)
            adv_menu.add_command(label="🔬 입고 검증", command=self._dry_run_inbound)
            adv_menu.add_command(label="🔬 출고 검증", command=self._dry_run_outbound)
            adv_menu.add_separator()
            adv_menu.add_command(label="🩺 전체 진단", command=self._run_self_test)
            adv_menu.add_command(label="🧪 단위 테스트", command=self._open_test_runner)
        
        # =====================================================
        # 보기 메뉴 — v8.1.7: 영문 9탭 구조 (사이드바 6 + 메뉴 전용 3)
        # =====================================================
        def _go(tab_attr: str):
            tab = getattr(self, tab_attr, None)
            if tab and self.notebook.winfo_exists():
                try:
                    self.notebook.select(tab)
                except Exception as e:
                    logger.warning(f'[UI] menu_mixin: {e}')
        def _add_tab_cmd(label: str, tab_attr: str, optional: bool = False):
            if optional and not getattr(self, tab_attr, None):
                return
            view_menu.add_command(label=label, command=lambda a=tab_attr: _go(a))

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="🔄 Refresh (F5)", command=self._refresh_inventory)
        view_menu.add_separator()
        _add_tab_cmd("📦 Inventory",  "tab_inventory")
        _add_tab_cmd("📋 Allocation", "tab_allocation")
        _add_tab_cmd("🚛 Picked",     "tab_picked")
        _add_tab_cmd("📤 Outbound",   "tab_sold")
        _add_tab_cmd("🔄 Return",     "tab_return")
        _add_tab_cmd("🔀 Move",       "tab_move")
        view_menu.add_separator()
        _add_tab_cmd("📊 Dashboard",  "tab_dashboard")
        _add_tab_cmd("📝 Log",        "tab_log")
        _add_tab_cmd("📷 Scan",       "tab_scan", optional=True)
        view_menu.add_separator()
        view_menu.add_command(label="🎨 Theme", command=self._show_theme_selector)

        # v2.7 메뉴 — v8.1.5: features_v2 미사용으로 제거 확정 (기동님 2026-03-23)
        
        # =====================================================
        # 도움말 메뉴
        # =====================================================
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="도움말", menu=help_menu)
        help_menu.add_command(label="⌨️ 단축키", command=self._show_shortcuts)
        help_menu.add_command(label="📖 설명서", command=self._show_manual)
        help_menu.add_separator()
        help_menu.add_command(label="🔬 API 테스트", command=self._test_gemini_api_connection)
        help_menu.add_separator()
        help_menu.add_command(label="ℹ️ 정보", command=self._show_about)
    

    def _show_shortcuts(self) -> None:
        """단축키 안내"""

        
        shortcuts_text = """
📌 SQM 재고관리 단축키

━━━━━━━━━━━━━━━━━━━━━━━━━━
Ctrl+I    입고 파일 업로드
Ctrl+O    간편 출고
Ctrl+E    Excel 내보내기
Ctrl+B    백업 생성
Ctrl+F    검색창 포커스
F5        새로고침
━━━━━━━━━━━━━━━━━━━━━━━━━━

더블클릭    LOT 상세 / 선택
드래그      파일 업로드
        """
        CustomMessageBox.showinfo(self.root, "⌨️ 단축키", shortcuts_text)
    
    def _show_about(self) -> None:
        """v6.4.0: 버전 정보 + CHANGELOG 탭 다이얼로그"""
        import tkinter as _tk
        from tkinter import ttk as _ttk
        import tkinter.scrolledtext as _st
        import os as _os

        try:
            from ..utils.constants import __version__, APP_NAME
        except ImportError:
            __version__, APP_NAME = "6.4.0", "SQM 재고관리"


        dlg = create_themed_toplevel(self.root)
        dlg.title(f"ℹ️ {APP_NAME}  v{__version__}")
        dlg.geometry("680x520")
        dlg.resizable(True, True)
        try:
            dlg.transient(self.root)
            dlg.grab_set()
        except Exception:
            logger.debug("[SUPPRESSED] exception in menu_mixin.py")  # noqa

        nb = _ttk.Notebook(dlg)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # ── 탭1: 버전 정보 ──────────────────────────────────
        tab_info = _ttk.Frame(nb)
        nb.add(tab_info, text="  ℹ️ 버전 정보  ")

        info_box = _st.ScrolledText(
            tab_info, font=("맑은 고딕", 12), wrap="word",
            height=20, relief="flat", padx=12, pady=8
        )
        info_box.pack(fill="both", expand=True)
        info_box.insert("end",
            f"{APP_NAME}\n"
            f"버전: {__version__}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "(주)지와이로지스  광양 물류창고\n\n"
            "주요 기능:\n"
            "  • LOT 기반 탄산리튬 · 황산니켈 재고 관리\n"
            "  • PDF 4종 서류 AI 파싱 (Gemini Vision)\n"
            "  • BL 선사별 파싱 레지스트리 (MSC · Maersk · HMM · CMA · ONE)\n"
            "  • 입고/출고 원스톱 워크플로우\n"
            "  • Excel 내보내기 · 바코드 스캔 검증\n"
            "  • 감사 추적 (audit_log 전체 기록)\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "개발: Ruby  |  기동님 SQM 프로젝트\n"
            "pytest: 82/82 PASS  |  Python 3.12+\n"
        )
        info_box.config(state="disabled")

        # ── 탭2: CHANGELOG ──────────────────────────────────
        tab_cl = _ttk.Frame(nb)
        nb.add(tab_cl, text="  📋 CHANGELOG  ")

        cl_box = _st.ScrolledText(
            tab_cl, font=("Consolas", 11), wrap="word",
            height=20, relief="flat", padx=12, pady=8
        )
        cl_box.pack(fill="both", expand=True)

        # CHANGELOG.md 파일 탐색 (실행 파일 기준 2단계 위)
        _cl_paths = [
            _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                         '..', '..', '..', 'CHANGELOG.md'),
            _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                         '..', '..', 'CHANGELOG.md'),
            _os.path.join(_os.getcwd(), 'CHANGELOG.md'),
        ]
        _cl_text = None
        for _p in _cl_paths:
            _p = _os.path.normpath(_p)
            if _os.path.exists(_p):
                try:
                    with open(_p, encoding='utf-8') as _fh:  # P1-10: with 문으로 파일 닫기 보장
                        _cl_text = _fh.read()
                    break
                except Exception:
                    logger.debug("[SUPPRESSED] exception in menu_mixin.py")  # noqa

        if _cl_text:
            cl_box.insert("end", _cl_text)
        else:
            cl_box.insert("end",
                "CHANGELOG.md 파일을 찾을 수 없습니다.\n\n"
                "프로젝트 루트 디렉토리에 CHANGELOG.md 를 배치하세요.\n"
                "(SQM_v640_FINAL_ALL_v2.zip 포함됨)"
            )
        cl_box.config(state="disabled")

        # ── 닫기 버튼 ────────────────────────────────────────
        _tk.Button(
            dlg, text="  ✕ 닫기  ", command=dlg.destroy,
            font=("맑은 고딕", 11), padx=10, pady=4, cursor="hand2"
        ).pack(pady=(0, 8))
    
    def _show_manual(self) -> None:
        """사용 설명서 표시"""
        import os
        import subprocess
        import platform
        
        manual_path = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'USER_MANUAL_KR.md')
        
        if os.path.exists(manual_path):
            if platform.system() == 'Windows':
                os.startfile(manual_path)
            elif platform.system() == 'Darwin':
                subprocess.run(['open', manual_path])
            else:
                subprocess.run(['xdg-open', manual_path])
        else:

            CustomMessageBox.showinfo(self.root, "설명서", "사용 설명서를 찾을 수 없습니다.\ndocs/USER_MANUAL_KR.md")