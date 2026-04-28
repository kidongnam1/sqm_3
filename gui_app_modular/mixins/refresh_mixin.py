# -*- coding: utf-8 -*-
"""
SQM Inventory - Refresh and Filter Mixin
========================================

v2.9.91 - Extracted from gui_app.py

Data refresh, filtering, and sorting functions
"""

import logging
from ..utils.custom_messagebox import CustomMessageBox

logger = logging.getLogger(__name__)


class RefreshMixin:
    """
    Refresh and filter mixin

    Mixed into SQMInventoryApp class
    """

    # ★ S2-1: 레거시 함수 4개 삭제됨 (호출처 0건 확인)
    # 삭제: _on_search_legacy, _on_status_filter_legacy,
    #        _on_tonbag_search_legacy, _on_tonbag_filter_legacy
    # 이유: InventoryTabMixin / TonbagTabMixin이 대체

    # v8.6.5 PERF-2: dirty flag 시스템
    _ALL_TAB_NAMES = (
        'inventory', 'allocation', 'picked', 'sold',
        'tonbag', 'outbound_scheduled', 'dashboard', 'cargo_overview',
    )

    def _init_dirty_tabs(self) -> None:
        """dirty flag 초기화 (main_app.__init__에서 호출)"""
        self._dirty_tabs: set = set()

    def _mark_tabs_dirty(self, *tab_names: str) -> None:
        """지정 탭을 dirty로 표시 — 탭 전환 시 새로고침"""
        if not tab_names:
            tab_names = self._ALL_TAB_NAMES
        if not hasattr(self, '_dirty_tabs'):
            self._dirty_tabs = set()
        self._dirty_tabs.update(tab_names)

    def _refresh_dirty_current_tab(self) -> None:
        """현재 활성 탭이 dirty면 새로고침 (<<NotebookTabChanged>> 핸들러용)"""
        if not hasattr(self, '_dirty_tabs'):
            return
        notebook = getattr(self, 'notebook', None)
        if not notebook:
            return
        try:
            current = notebook.tab(notebook.select(), 'text') if notebook.select() else ''
        except Exception:
            return
        # 탭 제목 → 내부 이름 매핑
        _tab_map = {
            '재고': 'inventory', '판매배정': 'allocation', '피킹': 'picked',
            '출고완료': 'sold', '톤백': 'tonbag', '출고예정': 'outbound_scheduled',
            '대시보드': 'dashboard', '총괄': 'cargo_overview',
        }
        tab_key = None
        for label, key in _tab_map.items():
            if label in current:
                tab_key = key
                break
        if tab_key and tab_key in self._dirty_tabs:
            self._dirty_tabs.discard(tab_key)
            fn = f'_refresh_{tab_key}'
            if hasattr(self, fn):
                try:
                    getattr(self, fn)()
                except Exception as e:
                    logger.debug(f"[dirty] {fn} refresh failed: {e}")

    def _refresh_main_tabs(self) -> None:
        """상위 메뉴 작업 후 필수 탭 즉시 반영"""
        # v8.6.5 UX-1: busy cursor
        root = getattr(self, 'root', None)
        if root and root.winfo_exists():
            try:
                root.config(cursor='wait')
                root.update_idletasks()
            except Exception as _e:
                logger.debug("[refresh] busy cursor 설정 실패: %s", _e)
        try:
            self._refresh_main_tabs_inner()
        finally:
            if root and root.winfo_exists():
                try:
                    root.config(cursor='')
                except Exception as _e:
                    logger.debug("[refresh] cursor 복원 실패: %s", _e)

    def _refresh_main_tabs_inner(self) -> None:
        """실제 탭 새로고침 로직"""
        for fn in [
            '_refresh_inventory',
            '_refresh_allocation',
            '_refresh_picked',
            '_refresh_sold',
            '_refresh_tonbag',
            '_refresh_outbound_scheduled',
            '_refresh_dashboard',
            '_refresh_cargo_overview',
        ]:
            if hasattr(self, fn):
                try:
                    getattr(self, fn)()
                except (ValueError, TypeError, RuntimeError) as e:
                    logger.debug(f"{fn} refresh skipped: {e}")
        # 전체 새로고침 후 dirty 클리어
        if hasattr(self, '_dirty_tabs'):
            self._dirty_tabs.clear()

    def _deferred_refresh_main_tabs(self, delay_ms: int = 50) -> None:
        """UI 블로킹 방지용 지연 리프레시 (모달/탭 동기화용)"""
        root = getattr(self, 'root', None)
        if root and root.winfo_exists():
            root.after(delay_ms, self._refresh_main_tabs)
        else:
            self._refresh_main_tabs()


    def _safe_refresh(self, delay_ms: int = 50) -> None:
        """
        v6.5.4: 중복 _deferred_refresh/_refresh 패턴 통합 헬퍼.
        26개 파일에서 반복되던 4줄 블록을 1줄로 대체.

            # 이전 (4줄):
            if hasattr(self, '_deferred_refresh_main_tabs'):
                self._deferred_refresh_main_tabs(delay_ms=50)
            elif hasattr(self, '_refresh_main_tabs'):
                self._refresh_main_tabs()

            # 이후 (1줄):
            self._safe_refresh()
        """
        if hasattr(self, '_deferred_refresh_main_tabs'):
            self._deferred_refresh_main_tabs(delay_ms=delay_ms)
        elif hasattr(self, '_refresh_main_tabs'):
            self._refresh_main_tabs()

    def refresh_bus(self, reason: str = "") -> None:
        """표준 새로고침 버스: 주요 탭 갱신을 단일 진입점으로 통합."""
        try:
            self._refresh_main_tabs()
            if reason:
                logger.debug(f"[refresh_bus] ok: {reason}")
        except Exception as e:
            logger.error(f"[refresh_bus] failed: {reason} / {e}", exc_info=True)

    def refresh_bus_deferred(self, reason: str = "", delay_ms: int = 50) -> None:
        """표준 지연 새로고침 버스."""
        root = getattr(self, 'root', None)
        if root and root.winfo_exists():
            root.after(delay_ms, lambda: self.refresh_bus(reason=reason))
        else:
            self.refresh_bus(reason=reason)

    def do_action_tx(
        self,
        action_name: str,
        fn,
        *,
        parent=None,
        refresh_mode: str = "deferred",
        refresh_on_success: bool = True,
        show_error: bool = True,
    ):
        """
        액션 실행 표준 래퍼:
        - 예외 처리 및 에러 표시 표준화
        - 성공 시 refresh_bus(즉시/지연)로 동기화
        """
        try:
            result = fn()
            success = True
            if isinstance(result, dict):
                success = bool(result.get("success", True))
            if success and refresh_on_success:
                if refresh_mode == "immediate":
                    self.refresh_bus(reason=action_name)
                else:
                    self.refresh_bus_deferred(reason=action_name, delay_ms=50)
            return result
        except Exception as e:
            logger.error(f"[do_action_tx] {action_name} failed: {e}", exc_info=True)
            if show_error:
                target = parent if parent is not None else getattr(self, "root", None)
                CustomMessageBox.showerror(target, "작업 실패", f"{action_name}\n\n{e}")
            return {"success": False, "errors": [str(e)]}
    
    def _update_recent_files_menu(self) -> None:
        """Update recent files menu"""
        if not hasattr(self, 'recent_menu'):
            return
        
        # Clear existing items
        self.recent_menu.delete(0, 'end')
        
        # Get recent files (from config or history)
        recent_files = getattr(self, 'recent_files', [])
        
        if not recent_files:
            self.recent_menu.add_command(label="(No recent files)", state='disabled')
            return
        
        for file_path in recent_files[:10]:  # Max 10 files
            filename = file_path.split('/')[-1].split('\\')[-1]
            self.recent_menu.add_command(
                label=filename,
                command=lambda p=file_path: self._open_recent_file(p)
            )
    
    def _open_recent_file(self, file_path: str) -> None:
        """Open recent file"""
        import os
        
        if not os.path.exists(file_path):

            CustomMessageBox.showwarning(self.root, "File Not Found", f"File not found:\n{file_path}")
            return
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            self._process_inbound(file_path)
        elif ext in ('.xlsx', '.xls'):
            self._process_excel_inbound(file_path)
        else:
            self._log(f"WARNING Unsupported file type: {ext}")
    
