"""
SQM Inventory - Log Tab
=======================

v3.6.0 - UI 통일성 적용
- 간격 표준화 (Spacing)
- 테마 색상 대응 (ThemeColors)
- 폰트 스케일링 (FontScale)
"""

# ══════════════════════════════════════════════════════════════
# 🎨 색상 사용 원칙 (v3.8.0 — 절대 준수)
# ══════════════════════════════════════════════════════════════
# ✅ 올바른 방법: tc() 함수 사용 (라이트/다크 자동 전환)
#     from gui_app_modular.utils.ui_constants import tc
#     label.config(fg=tc('text_primary'), bg=tc('bg_primary'))
#     entry.config(fg=tc('text_primary'), bg=tc('bg_entry'))
#     frame.config(bg=tc('bg_secondary'))
#
# ❌ 금지: 하드코딩 색상 사용
#     label.config(fg=tc('text_primary'))         # 다크 배경에서 안 보임
#     label.config(fg=tc('text_primary'))         # 라이트 배경에서 안 보임
#     label.config(bg=tc('bg_primary'))       # 라이트 모드에서 검은 배경
#
# 📋 주요 tc() 키:
#     text_primary   — 일반 텍스트 (라이트: #2c3e50  다크: #FF8C00)
#     text_secondary — 보조 텍스트
#     text_muted     — 비활성 텍스트 (gray 대체)
#     bg_primary     — 기본 배경
#     bg_secondary   — 보조 배경
#     bg_card        — 카드/패널 배경
#     bg_entry       — 입력창 배경
#     success        — 성공 (녹색 계열)
#     warning        — 경고 (주황 계열)
#     danger         — 오류 (빨간 계열)
#     info           — 정보 (파란 계열)
# ══════════════════════════════════════════════════════════════

import logging
from datetime import datetime
from tkinter import END

from ..utils.ui_constants import is_dark, CustomMessageBox, apply_tooltip

logger = logging.getLogger(__name__)


class LogTabMixin:
    """
    Log tab mixin
    
    Mixed into SQMInventoryApp class
    """

    def _setup_log_tab(self) -> None:
        """Setup activity log tab"""
        from ..utils.constants import BOTH, LEFT, RIGHT, VERTICAL, X, Y, tk, ttk
        from ..utils.ui_constants import FontScale, Spacing

        # === UI 통일성: 폰트 스케일 ===
        try:
            dpi = self.root.winfo_fpixels('1i')
        except (ImportError, ModuleNotFoundError):
            dpi = 96
        fonts = FontScale(dpi)

        # === UI 통일성: 간격 표준화 ===
        # 탭 헤더 (v7.6.0 심플화)
        try:
            from ..utils.ui_constants import make_tab_header, ThemeColors
            _is_dark_log = is_dark()
            make_tab_header(self.tab_log, "📝 Activity Log",
                            status_color='#64748b', is_dark=_is_dark_log)
        except Exception:
            logger.debug("[SUPPRESSED] exception in log_tab.py")  # noqa
        # Header frame
        header_frame = ttk.Frame(self.tab_log)
        header_frame.pack(fill=X, pady=(0, Spacing.XS))

        _lbl_log = ttk.Label(header_frame, text="Activity Log", font=fonts.body(bold=True))
        _lbl_log.pack(side=LEFT)
        apply_tooltip(_lbl_log, "시스템·작업·오류 로그가 시간순으로 표시됩니다. 정보/성공/경고/오류 수준별로 색상이 다릅니다.")

        # Buttons
        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=RIGHT)

        _btn_clear = ttk.Button(btn_frame, text="Clear", command=self._clear_log)
        _btn_clear.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(_btn_clear, "화면에 표시된 로그 내용을 모두 지웁니다. 파일에는 영향을 주지 않습니다.")
        _btn_export = ttk.Button(btn_frame, text="Export", command=self._export_log)
        _btn_export.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(_btn_export, "현재 로그를 텍스트 파일로 저장합니다. 저장 위치는 선택 대화상자에서 지정할 수 있습니다.")

        # Log text area
        log_frame = ttk.Frame(self.tab_log)
        log_frame.pack(fill=BOTH, expand=True)

        self.log_text = tk.Text(log_frame, wrap='word', height=20, state='disabled', font=fonts.mono())
        scrollbar = tk.Scrollbar(log_frame, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # === UI 통일성: 테마 색상 대응 ===
        self._configure_log_tags()

    def _configure_log_tags(self) -> None:
        """로그 태그 색상 설정 (테마 대응)"""
        from ..utils.ui_constants import ThemeColors

        # v9.1: is_dark() 전역 함수로 통일
        from gui_app_modular.utils.ui_constants import is_dark as _is_dark_fn, tc
        is_dark = _is_dark_fn()

        if is_dark:
            # 다크 모드 색상
            self.log_text.tag_configure('info', foreground=tc('text_primary'))
            self.log_text.tag_configure('success', foreground=tc('success'))  # 밝은 녹색
            self.log_text.tag_configure('warning', foreground=tc('warning'))  # 밝은 주황
            self.log_text.tag_configure('error', foreground=tc('danger'))    # 밝은 빨강
            self.log_text.tag_configure('timestamp', foreground=tc('text_muted'))
        else:
            # 라이트 모드 색상
            self.log_text.tag_configure('info', foreground=tc('text_primary'))
            self.log_text.tag_configure('success', foreground=tc('success'))
            self.log_text.tag_configure('warning', foreground=tc('warning'))
            self.log_text.tag_configure('error', foreground=tc('danger'))
            self.log_text.tag_configure('timestamp', foreground=tc('text_muted'))

    def _log(self, message: str, level: str = 'info', where: str = None, what: str = None) -> None:
        """
        Add message to activity log.
        
        Args:
            message: Log message
            level: 'info', 'success', 'warning', 'error'
            where: 발생 위치(모듈/화면/단계). 경고·에러 시 표시 권장.
            what: 무슨 작업 중이었는지. 경고·에러 시 표시 권장.
        """
        if where or what:
            prefix = []
            if where:
                prefix.append(where)
            if what:
                prefix.append(what + " 중")
            message = " ".join(prefix) + ": " + message
        if not hasattr(self, 'log_text'):
            logger.debug(f"[{level.upper()}] {message}")
            return

        timestamp = datetime.now().strftime('%H:%M:%S')

        # Determine tag based on message content or level
        tag = level
        if 'OK' in message or 'success' in message.lower() or 'complete' in message.lower():
            tag = 'success'
        elif 'WARNING' in message or 'warning' in message.lower():
            tag = 'warning'
        elif 'X ' in message or 'error' in message.lower() or 'failed' in message.lower():
            tag = 'error'

        try:
            self.log_text.config(state='normal')
            self.log_text.insert(END, f"[{timestamp}] ", 'timestamp')
            self.log_text.insert(END, f"{message}\n", tag)
            self.log_text.see(END)
            self.log_text.config(state='disabled')

            # Also log to Python logger
            log_level = {
                'info': logging.INFO,
                'success': logging.INFO,
                'warning': logging.WARNING,
                'error': logging.ERROR,
            }.get(tag, logging.INFO)

            logger.log(log_level, message)

        except (RuntimeError, ValueError) as e:
            logger.debug(f"Log error: {e}")
            logger.debug(f"[{timestamp}] {message}")

    def _clear_log(self) -> None:
        """Clear activity log"""
        if hasattr(self, 'log_text'):
            self.log_text.config(state='normal')
            self.log_text.delete('1.0', 'end')
            self.log_text.config(state='disabled')
            self._log("Log cleared")

    def _export_log(self) -> None:
        """Export activity log to file"""
        from ..utils.constants import filedialog

        if not hasattr(self, 'log_text'):
            return

        file_path = filedialog.asksaveasfilename(
            parent=getattr(self, "root", None),
            title="Save Log File",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if not file_path:
            return

        try:
            content = self.log_text.get('1.0', 'end')
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self._log(f"Log exported: {file_path}")
            CustomMessageBox.showinfo(self.root, "Export Complete", f"Log exported to:\n{file_path}")

        except (OSError, IOError, PermissionError) as e:
            self._log(f"X Export failed: {e}")
            CustomMessageBox.showerror(self.root, "Export Failed", f"Failed to export log:\n{e}")

    def _set_status_log(self, message: str) -> None:
        """Set status bar message (LogTab version - use StatusBarMixin instead)"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
        if hasattr(self, 'root'):
            self.root.update_idletasks()

    def _start_task(self, task_name: str, status_message: str) -> None:
        """Start a task with progress indication"""
        self._set_status(status_message)
        self._log(f"Starting: {task_name}")

        if hasattr(self, 'progress_bar'):
            self.progress_bar['value'] = 0
            self.progress_bar['maximum'] = 100

    def _update_task_progress(self, value: int, log_message: str = '', status_message: str = '') -> None:
        """Update task progress"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar['value'] = value

        if status_message:
            self._set_status(status_message)

        if log_message:
            self._log(log_message)

        if hasattr(self, 'root'):
            self.root.update_idletasks()

    def _update_progress(self, value: int, message: str = '', detail: str = '') -> None:
        """Update progress (호환성 래퍼)"""
        self._update_task_progress(value, message, detail or message)

    def _end_task(self, success: bool, message: str) -> None:
        """End a task"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar['value'] = 100 if success else 0

        self._set_status(message)
        self._log(message)

        if hasattr(self, 'root'):
            self.root.update_idletasks()
