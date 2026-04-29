# -*- coding: utf-8 -*-
"""
SQM Inventory - Key Bindings Mixin
==================================

v2.9.91 - Extracted from gui_app.py

Keyboard shortcuts and hotkey handling
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import logging
from ..utils.ui_constants import CustomMessageBox, apply_modal_window_options, setup_dialog_geometry_persistence

logger = logging.getLogger(__name__)


class KeyBindingsMixin:
    """
    Keyboard shortcuts mixin
    
    Mixed into SQMInventoryApp class
    """
    
    def _setup_keybindings(self) -> None:
        """Setup all keyboard shortcuts"""
        # File operations
        self.root.bind('<Control-o>', self._on_open_file)
        self.root.bind('<Control-O>', self._on_open_file)
        self.root.bind('<Control-s>', self._on_save)
        self.root.bind('<Control-S>', self._on_save)
        self.root.bind('<Control-Shift-s>', self._on_save_as)
        self.root.bind('<Control-Shift-S>', self._on_save_as)
        
        # Search
        self.root.bind('<Control-f>', self._focus_search)
        self.root.bind('<Control-F>', self._focus_search)
        
        # Refresh
        self.root.bind('<F5>', self._on_refresh_all)
        self.root.bind('<Control-r>', self._on_refresh_all)
        self.root.bind('<Control-R>', self._on_refresh_all)
        
        # Navigation — v8.1.7: Ctrl+1~9 (9탭 구조)
        self.root.bind('<Control-Tab>',       self._next_tab)
        self.root.bind('<Control-Shift-Tab>', self._prev_tab)
        self.root.bind('<Control-1>', lambda e: self._goto_tab(0))  # Inventory
        self.root.bind('<Control-2>', lambda e: self._goto_tab(1))  # Allocation
        self.root.bind('<Control-3>', lambda e: self._goto_tab(2))  # Picked
        self.root.bind('<Control-4>', lambda e: self._goto_tab(3))  # Outbound
        self.root.bind('<Control-5>', lambda e: self._goto_tab(4))  # Return
        self.root.bind('<Control-6>', lambda e: self._goto_tab(5))  # Move
        self.root.bind('<Control-7>', lambda e: self._goto_tab(6))  # Dashboard
        self.root.bind('<Control-8>', lambda e: self._goto_tab(7))  # Log
        self.root.bind('<Control-9>', lambda e: self._goto_tab(8))  # Scan (optional)
        
        # Window
        self.root.bind('<F11>', self._toggle_fullscreen)
        self.root.bind('<Escape>', self._on_escape)
        self.root.bind('<Control-q>', self._on_force_quit)
        self.root.bind('<Control-Q>', self._on_force_quit)
        
        # Quick actions
        self.root.bind('<Control-n>', self._on_new_inbound)
        self.root.bind('<Control-N>', self._on_new_inbound)
        self.root.bind('<Control-e>', self._on_export)
        self.root.bind('<Control-E>', self._on_export)
        self.root.bind('<Control-b>', self._on_backup)
        self.root.bind('<Control-B>', self._on_backup)
        
        # Help
        self.root.bind('<F1>', self._show_help)
        
        # 테스트 DB 초기화 단축키 제거 — Ctrl+Shift+X로 실수 시 DB 파일(.db/.shm/.wal) 삭제 사고 방지.
        # 초기화는 메뉴(데이터베이스 > 테스트 DB 초기화)에서만 호출 가능.
        # self.root.bind('<Control-Shift-X>', self._show_test_db_reset_popup)
        
        self._log("Keyboard shortcuts configured")
    
    def _on_open_file(self, event=None) -> None:
        """Open file (Ctrl+O)"""
        if hasattr(self, '_hide_empty_state_hint'):
            self._hide_empty_state_hint()
        from ..utils.constants import filedialog

        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Open File",
            filetypes=[
                ("All supported", "*.pdf *.xlsx *.xls"),
                ("PDF files", "*.pdf"),
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            import os
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.pdf':
                self._process_inbound(file_path)
            elif ext in ('.xlsx', '.xls'):
                self._process_excel_inbound(file_path)
    
    def _on_save(self, event=None) -> None:
        """Save (Ctrl+S) - Quick export"""
        self._on_export_click(option=3)
    
    def _on_save_as(self, event=None) -> None:
        """Save As (Ctrl+Shift+S) - Export with dialog"""
        self._on_export_click(option=7)
    
    def _focus_search(self, event=None) -> None:
        """Focus search entry (Ctrl+F)"""
        if hasattr(self, 'search_var'):
            # Try to find and focus search entry
            for tab in self.notebook.tabs():
                tab_widget = self.notebook.nametowidget(tab)
                for child in tab_widget.winfo_children():
                    if hasattr(child, 'winfo_children'):
                        for subchild in child.winfo_children():
                            if isinstance(subchild, self.root.nametowidget('.').__class__):
                                # Found entry widget
                                subchild.focus_set()
                                if hasattr(subchild, 'select_range'):
                                    subchild.select_range(0, 'end')
                                return
    
    def _on_refresh_all(self, event=None) -> None:
        """Refresh all tabs (F5, Ctrl+R)"""
        self._refresh_inventory()
        self._refresh_tonbag()
        if hasattr(self, '_refresh_summary'):
            self._refresh_summary()
        # v3.6.2: 대시보드 + 피봇도 새로고침
        if hasattr(self, '_refresh_dashboard'):
            try:
                self._refresh_dashboard()
            except (AttributeError, RuntimeError) as _e:
                logger.debug(f"Dashboard refresh on F5: {_e}")
        self._log("All tabs refreshed")
    
    # v8.1.7: 탭 순서 — 사이드바 워크플로우 6탭 + 메뉴 전용 3탭
    _TAB_ORDER = [
        "tab_inventory",    # Ctrl+1  📦 Inventory
        "tab_allocation",   # Ctrl+2  📋 Allocation
        "tab_picked",       # Ctrl+3  🚛 Picked
        "tab_sold",         # Ctrl+4  📤 Outbound
        "tab_return",       # Ctrl+5  🔄 Return
        "tab_move",         # Ctrl+6  🔀 Move (신규)
        "tab_dashboard",    # Ctrl+7  📊 Dashboard (메뉴 전용)
        "tab_log",          # Ctrl+8  📝 Log (메뉴 전용)
        "tab_scan",         # Ctrl+9  📷 Scan (optional)
    ]

    def _visible_tabs(self) -> list:
        """notebook에 실제 등록된 탭 위젯 목록 (순서 보장)"""
        tabs = []
        for attr in self._TAB_ORDER:
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            try:
                # notebook.tabs()는 등록된 탭의 tk 경로 문자열 목록
                if str(widget) in self.notebook.tabs():
                    tabs.append(widget)
            except Exception as e:
                logger.warning(f'[UI] keybindings_mixin: {e}')
        return tabs

    def _next_tab(self, event=None) -> None:
        """Go to next tab (Ctrl+Tab) — 위젯 참조 방식 v8.1.6"""
        if not hasattr(self, 'notebook'):
            return
        tabs = self._visible_tabs()
        if not tabs:
            return
        try:
            current = self.notebook.select()  # 현재 탭의 tk 경로
            current_idx = next(
                (i for i, t in enumerate(tabs) if str(t) == current), 0
            )
            self.notebook.select(tabs[(current_idx + 1) % len(tabs)])
        except Exception as e:
            logger.warning(f'[UI] keybindings_mixin: {e}')
    def _prev_tab(self, event=None) -> None:
        """Go to previous tab (Ctrl+Shift+Tab) — 위젯 참조 방식 v8.1.6"""
        if not hasattr(self, 'notebook'):
            return
        tabs = self._visible_tabs()
        if not tabs:
            return
        try:
            current = self.notebook.select()
            current_idx = next(
                (i for i, t in enumerate(tabs) if str(t) == current), 0
            )
            self.notebook.select(tabs[(current_idx - 1) % len(tabs)])
        except Exception as e:
            logger.warning(f'[UI] keybindings_mixin: {e}')
    def _goto_tab(self, index: int) -> None:
        """Go to specific tab (Ctrl+1~8) — 위젯 참조 방식 v8.1.6"""
        if not hasattr(self, 'notebook'):
            return
        tabs = self._visible_tabs()
        if 0 <= index < len(tabs):
            try:
                self.notebook.select(tabs[index])
            except Exception as e:
                logger.warning(f'[UI] keybindings_mixin: {e}')
    def _toggle_fullscreen(self, event=None) -> None:
        """Toggle fullscreen (F11)"""
        is_fullscreen = getattr(self, '_is_fullscreen', False)
        self._is_fullscreen = not is_fullscreen
        self.root.attributes('-fullscreen', self._is_fullscreen)
    
    def _on_force_quit(self, event=None) -> None:
        """강제 종료 (Ctrl+Q)"""
        try:
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            logger.debug(f"Force quit: {e}")
            import sys
            sys.exit(0)

    def _on_escape(self, event=None) -> None:
        """Handle Escape key"""
        # Exit fullscreen if active
        if getattr(self, '_is_fullscreen', False):
            self._is_fullscreen = False
            self.root.attributes('-fullscreen', False)
            return
        
        # Clear search
        if hasattr(self, 'search_var') and self.search_var.get():
            self.search_var.set('')
            self._refresh_inventory()
            return
        
        # Clear tonbag search
        if hasattr(self, 'tonbag_search_var') and self.tonbag_search_var.get():
            self.tonbag_search_var.set('')
            self._refresh_tonbag()
    
    def _on_new_inbound(self, event=None) -> None:
        """New inbound (Ctrl+N)"""
        if hasattr(self, '_hide_empty_state_hint'):
            self._hide_empty_state_hint()
        if hasattr(self, '_on_pdf_inbound'):
            self._on_pdf_inbound()
    
    def _on_export(self, event=None) -> None:
        """Export (Ctrl+E)"""
        self._on_export_click(option=3)
    
    def _on_backup(self, event=None) -> None:
        """Backup (Ctrl+B)"""
        if hasattr(self, '_on_backup_click'):
            self._on_backup_click()
    
    def _show_help(self, event=None) -> None:
        """Show help dialog (F1)"""

        
        help_text = """SQM Inventory Management System
        
Keyboard Shortcuts:
═══════════════════════════════════════

File Operations:
  Ctrl+O       Open file (PDF/Excel)
  Ctrl+S       Quick export
  Ctrl+Shift+S Export with options
  Ctrl+N       New inbound
  Ctrl+E       Export inventory
  Ctrl+B       Create backup

Navigation:
  Ctrl+Tab     Next tab
  Ctrl+Shift+Tab  Previous tab
  Ctrl+1~5     Go to tab 1~5

Search:
  Ctrl+F       Focus search
  Escape       Clear search

Window:
  F5           Refresh all
  F11          Toggle fullscreen
  Escape       Exit fullscreen

Help:
  F1           Show this help

═══════════════════════════════════════
v2.9.91 - SQM Inventory System
"""
        CustomMessageBox.showinfo(self.root, "Help", help_text)
    

    def _select_all_treeview(self, tree) -> None:
        """Select all items in treeview"""
        items = tree.get_children()
        tree.selection_set(items)
    
    def _copy_treeview_selection(self, tree) -> None:
        """Copy selected treeview items to clipboard"""
        selection = tree.selection()
        if not selection:
            return
        
        # Build text from selection
        lines = []
        for item_id in selection:
            values = tree.item(item_id, 'values')
            if values:
                lines.append('\t'.join(str(v) for v in values))
        
        if lines:
            text = '\n'.join(lines)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._log(f"Copied {len(lines)} rows to clipboard")

    def _show_test_db_reset_popup(self, event=None) -> None:
        """테스트 DB 초기화 전 확인 팝업 (메뉴에서 호출, 단축키는 실수 방지로 제거됨)"""
        from ..utils.constants import tk, ttk
        popup = create_themed_toplevel(self.root)
        popup.title("테스트 DB 초기화")
        apply_modal_window_options(popup)
        popup.transient(self.root)
        popup.grab_set()
        setup_dialog_geometry_persistence(popup, "test_db_reset_dialog", self.root, "small")
        frame = ttk.Frame(popup, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="테스트용 데이터베이스를 초기화합니다.\n모든 재고·톤백·출고 데이터가 삭제됩니다.",
                  font=('맑은 고딕', 11), wraplength=360).pack(anchor='w', pady=(0, 12))
        ttk.Label(frame, text="정말 데이터베이스를 지우시겠습니까?",
                  font=('맑은 고딕', 10), foreground=tc('warning')).pack(anchor='w', pady=(0, 16))
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        def do_reset():
            popup.destroy()
            self._reset_test_db()
        ttk.Button(btn_frame, text="예, 초기화", command=do_reset, width=18).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="취소", command=popup.destroy, width=10).pack(side=tk.LEFT)
        popup.bind('<Escape>', lambda e: popup.destroy())
        popup.protocol("WM_DELETE_WINDOW", popup.destroy)

    def _reset_test_db(self) -> None:
        """테스트 DB 초기화 — SQLite만 지원. 연결 종료 후 파일 삭제·재생성."""
        import os
        import shutil
        import sqlite3
        from datetime import datetime
        if not getattr(self, 'engine', None):
            self._log("⚠️ 엔진이 없습니다.")
            return
        db_path_engine = getattr(self.engine, 'db_path', None)
        db_path_app = getattr(self, 'db_path', None)
        if not db_path_engine or db_path_engine == ':memory:':
            self._log("⚠️ 메모리 DB 또는 경로 없음 — 초기화 불가")
            return
        if getattr(self.engine, 'db_type', 'sqlite') != 'sqlite':
            self._log("⚠️ 테스트 DB 초기화는 SQLite에서만 지원합니다.")
            return
        path = os.path.abspath(db_path_engine)
        if db_path_app:
            path_app = os.path.abspath(db_path_app)
            if path_app != path:
                # 경로 불일치 시 실제 사용 중인 엔진 경로를 단일 소스로 강제
                self._log(f"⚠️ DB 경로 불일치 감지 — engine={path}, app={path_app}. engine 경로로 통일합니다.")
        self.db_path = path

        if not os.path.isfile(path):
            self._log("⚠️ DB 파일이 없습니다.")
            return
        # v6.3.5: close() → close_all()
        # 이유: threading.local()로 스레드마다 독립 연결이 생성됨
        #       close()는 호출 스레드(메인) 연결만 닫아 다른 스레드 연결이
        #       파일을 열고 있으면 Windows WinError 32가 발생
        #       close_all()은 전체 연결 + WAL checkpoint를 수행
        try:
            if hasattr(self.engine, 'db') and hasattr(self.engine.db, 'close_all'):
                self.engine.db.close_all()
            elif hasattr(self.engine, 'db') and hasattr(self.engine.db, 'close'):
                self.engine.db.close()  # fallback
        except Exception as e:
            logger.debug(f"DB close_all: {e}")

        backup_dir = os.path.join(os.path.dirname(path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f"sqm_before_reset_{stamp}.db")
        try:
            shutil.copy2(path, backup_path)
            self._log(f"백업: {backup_path}")
        except OSError as e:
            logger.warning(f"백업 실패: {e}")

        # SQLite 잔존 파일까지 함께 삭제 (WAL/SHM/JOURNAL/CHECKSUM)
        cleanup_targets = [
            path,
            f"{path}-wal",
            f"{path}-shm",
            f"{path}-journal",
            f"{path}.checksum",
        ]
        remove_errors = []
        import time
        for target in cleanup_targets:
            if not os.path.exists(target):
                continue
            # v6.3.5: 삭제 실패 시 0.5초 대기 후 1회 재시도
            # (백그라운드 스레드가 연결 종료 완료를 기다리는 시간)
            last_err = None
            for attempt in range(2):
                try:
                    os.remove(target)
                    self._log(f"🧹 삭제: {target}")
                    last_err = None
                    break
                except OSError as e:
                    last_err = e
                    if attempt == 0:
                        logger.debug(f"DB 삭제 실패(0.5초 대기 후 재시도): {target}")
                        # P1-3: UI 스레드 sleep 제거 — 퍼스트 이벤트 처리 후 돈당 문제없음
                        # time.sleep(0.5) ← 제거 (OS가 취소 상태에서 500ms 이내 GC 모드로 파일 해제)
            if last_err:
                remove_errors.append((target, str(last_err)))
        if remove_errors:
            first_target, first_err = remove_errors[0]
            self._log(f"❌ DB 파일 삭제 실패: {first_target} / {first_err}")
            CustomMessageBox.showerror(
                self.root,
                "테스트 DB 초기화",
                f"파일이 사용 중이거나 권한이 없습니다.\n{first_target}\n{first_err}"
            )
            return

        try:
            self._init_engine()
            # 재생성 검증: 무결성 + 핵심 테이블 건수 0 확인
            if not getattr(self, 'engine', None) or not getattr(self.engine, 'db', None):
                raise RuntimeError("엔진 재초기화 후 DB 연결이 없습니다.")
            new_path = os.path.abspath(getattr(self.engine, 'db_path', ''))
            if new_path != path:
                raise RuntimeError(f"재초기화 DB 경로 불일치: expected={path}, actual={new_path}")

            integ = self.engine.db.fetchone("PRAGMA integrity_check") or {}
            integ_ok = str(integ.get('integrity_check', '') or '').lower() == 'ok'
            if not integ_ok:
                raise RuntimeError(f"PRAGMA integrity_check 실패: {integ}")

            inv_cnt = self.engine.db.fetchone("SELECT COUNT(*) AS cnt FROM inventory") or {}
            ton_cnt = self.engine.db.fetchone("SELECT COUNT(*) AS cnt FROM inventory_tonbag") or {}
            out_cnt = self.engine.db.fetchone("SELECT COUNT(*) AS cnt FROM outbound") or {}
            inv_n = int(inv_cnt.get('cnt', 0) or 0)
            ton_n = int(ton_cnt.get('cnt', 0) or 0)
            out_n = int(out_cnt.get('cnt', 0) or 0)
            if inv_n != 0 or ton_n != 0 or out_n != 0:
                raise RuntimeError(
                    f"초기화 검증 실패: inventory={inv_n}, tonbag={ton_n}, outbound={out_n}"
                )

            self._log("✅ 테스트 DB 초기화 완료.")
            self._refresh_inventory()
            self._refresh_tonbag()
            if hasattr(self, '_refresh_dashboard') and callable(self._refresh_dashboard):
                try:
                    self._refresh_dashboard()
                except Exception as _e:
                    logger.debug(f"Dashboard refresh: {_e}")
            CustomMessageBox.showinfo(
                self.root,
                "테스트 DB 초기화",
                "데이터베이스가 초기화되었습니다.\n"
                "검증 완료: integrity_check=ok, inventory/tonbag/outbound=0건\n"
                "재고·톤백 화면이 갱신됩니다."
            )
        except (sqlite3.Error, OSError, RuntimeError, ValueError, TypeError) as e:
            logger.error(f"테스트 DB 초기화 오류: {e}", exc_info=True)
            msg = f"엔진 재생성 실패:\n{e}"
            # 원클릭 롤백: 초기화 직전 백업 자동 복원
            if backup_path and os.path.isfile(backup_path):
                if CustomMessageBox.askyesno(
                    self.root,
                    "테스트 DB 초기화 실패",
                    f"{msg}\n\n초기화 전 백업으로 자동 복원하시겠습니까?\n{backup_path}"
                ):
                    try:
                        # 복원 전 현재 연결 정리
                        if getattr(self, 'engine', None) and hasattr(self.engine, 'db') and hasattr(self.engine.db, 'close'):
                            try:
                                self.engine.db.close()
                            except Exception as _e:
                                logger.debug(f"롤백 전 DB close 실패(무시): {_e}")

                        # 찌꺼기 파일 정리 후 백업 복원
                        rollback_targets = [
                            path,
                            f"{path}-wal",
                            f"{path}-shm",
                            f"{path}-journal",
                            f"{path}.checksum",
                        ]
                        for target in rollback_targets:
                            try:
                                if os.path.exists(target):
                                    os.remove(target)
                            except OSError as _e:
                                logger.debug(f"롤백 전 파일 정리 실패(무시): {target} / {_e}")

                        shutil.copy2(backup_path, path)
                        self.db_path = path
                        self._init_engine()

                        # 복원 검증
                        integ = self.engine.db.fetchone("PRAGMA integrity_check") or {}
                        integ_ok = str(integ.get('integrity_check', '') or '').lower() == 'ok'
                        if not integ_ok:
                            raise RuntimeError(f"롤백 후 integrity_check 실패: {integ}")

                        self._refresh_inventory()
                        self._refresh_tonbag()
                        if hasattr(self, '_refresh_dashboard') and callable(self._refresh_dashboard):
                            try:
                                self._refresh_dashboard()
                            except Exception as _e:
                                logger.debug(f"Dashboard refresh(rollback): {_e}")

                        self._log(f"♻️ 롤백 복원 완료: {backup_path}")
                        CustomMessageBox.showinfo(
                            self.root,
                            "롤백 복원 완료",
                            "초기화 실패로 인해 백업에서 자동 복원했습니다.\n"
                            "재고·톤백 화면을 갱신했습니다."
                        )
                        return
                    except (sqlite3.Error, OSError, RuntimeError, ValueError, TypeError) as re:
                        logger.error(f"롤백 복원 실패: {re}", exc_info=True)
                        CustomMessageBox.showerror(
                            self.root,
                            "롤백 복원 실패",
                            f"자동 복원에 실패했습니다.\n수동 복원이 필요합니다.\n\n백업 파일:\n{backup_path}\n\n오류:\n{re}"
                        )
                        return
            CustomMessageBox.showerror(self.root, "테스트 DB 초기화", msg)
