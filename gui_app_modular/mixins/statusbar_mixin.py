"""
SQM Inventory - Status Bar Mixin
================================

v2.9.91 - Extracted from gui_app.py

Status bar with mode indicator, module status, progress bar
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

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import is_dark  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import logging
import sqlite3

from ..utils.ui_constants import (
    CustomMessageBox,
    ThemeColors,
    setup_dialog_geometry_persistence,
)

logger = logging.getLogger(__name__)


class StatusBarMixin:
    """
    Status bar mixin
    
    Mixed into SQMInventoryApp class
    """

    def _setup_status_bar(self) -> None:
        """
        Setup status bar
        
        Layout:
        ┌──────────────────────────────────────────────────────────────────┐
        │ [WRITE] [Modules: 7/8] [Status message] [Progress] [75%] │
        └──────────────────────────────────────────────────────────────────┘
        """
        from ..utils.constants import (
            BOTTOM,
            HORIZONTAL,
            LEFT,
            RIGHT,
            VERTICAL,
            X,
            Y,
            tk,
            ttk,
        )
        try:
            from ..utils.ui_constants import ThemeColors
            _is_dark = is_dark()
            _p = ThemeColors.get_palette(_is_dark)
        except (ImportError, ModuleNotFoundError):
            _p = {'success': '#27ae60', 'warning': '#f39c12', 'danger': '#e74c3c',
                  'text_secondary': '#7f8c8d', 'text_primary': '#2c3e50',
                  'statusbar_icon_ok': '#2ecc71', 'statusbar_icon_warn': '#f39c12',
                  'statusbar_icon_err': '#e74c3c'}

        # Status bar frame
        self.statusbar_frame = ttk.Frame(self.main_frame)
        self.statusbar_frame.pack(fill=X, side=BOTTOM, pady=(5, 0))

        # Separator
        ttk.Separator(self.statusbar_frame, orient=HORIZONTAL).pack(fill=X)

        # Inner container
        status_container = ttk.Frame(self.statusbar_frame, padding=(5, 3))
        status_container.pack(fill=X)

        # Left: Read/Write mode indicator
        self.mode_label = ttk.Label(
            status_container,
            text="WRITE",
            foreground=_p.get('success', 'green'),
            font=("", 9, "bold"),
            width=10,
            anchor="w"
        )
        self.mode_label.pack(side=LEFT, padx=(0, 5))
        self.mode_label.bind("<Button-1>", lambda e: self._toggle_db_mode())

        # Separator
        ttk.Separator(status_container, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=3)

        # Module status
        self.module_status_var = tk.StringVar(value="Modules: checking...")
        self.module_status_label = ttk.Label(
            status_container,
            textvariable=self.module_status_var,
            foreground=tc('text_muted'),
            font=("", 10),
            width=20,
            anchor="w"
        )
        self.module_status_label.pack(side=LEFT, padx=(0, 5))
        self.module_status_label.bind("<Button-1>", lambda e: self._show_module_status_dialog())

        # Separator
        ttk.Separator(status_container, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)

        # Center: Status message
        self.status_var_bar = tk.StringVar(value="Ready")
        status_label = ttk.Label(
            status_container,
            textvariable=self.status_var_bar,
            anchor="w",
            width=30
        )
        status_label.pack(side=LEFT, fill=X, expand=False)

        # U4: 실시간 재고 요약
        ttk.Separator(status_container, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)
        self._inv_summary_var = tk.StringVar(value="📦 LOT: - | 🎒 톤백: - | 💰 재고: - MT")
        self._inv_summary_label = ttk.Label(
            status_container,
            textvariable=self._inv_summary_var,
            font=("맑은 고딕", 9, "bold"),
            foreground=_p.get('text_primary', '#2c3e50'),
            anchor="w"
        )
        self._inv_summary_label.pack(side=LEFT, fill=X, expand=True, padx=(5, 0))

        # v6.7.4: 이동 승인 PENDING 배지
        ttk.Separator(status_container, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)
        self._move_pending_var = tk.StringVar(value="")
        self._move_pending_label = ttk.Label(
            status_container,
            textvariable=self._move_pending_var,
            font=("맑은 고딕", 9, "bold"),
            foreground=tc('warning'),
            cursor="hand2",
            anchor="w"
        )
        self._move_pending_label.pack(side=LEFT, padx=(2, 8))
        self._move_pending_label.bind(
            "<Button-1>",
            lambda e: self._on_move_pending_badge_click()
        )
        self.root.after(5000, self._refresh_move_pending_badge)

        # Right side elements
        right_container = ttk.Frame(status_container)
        right_container.pack(side=RIGHT)

        # v3.9.7: 보안/백업 인디케이터
        indicator_frame = ttk.Frame(right_container)
        indicator_frame.pack(side=LEFT, padx=(0, 10))

        # API 키 보안 상태
        try:
            from core.config import API_KEY_SOURCE
            sec_map = {'ENV': ('🟢', 'ENV'), 'KEYRING': ('🟢', 'KEY'),
                       'INI': ('🟡', 'INI'), 'NONE': ('🔴', 'N/A')}
            sec_icon, sec_text = sec_map.get(API_KEY_SOURCE, ('🔴', '?'))
        except (ImportError, ModuleNotFoundError):
            sec_icon, sec_text = '⚪', '?'

        self._api_status_label = ttk.Label(
            indicator_frame, text=f"{sec_icon}API:{sec_text}",
            font=("", 8), foreground=tc('text_muted'))
        self._api_status_label.pack(side=LEFT, padx=(0, 5))

        # 마지막 백업 시각
        self._backup_status_var = tk.StringVar(value="💾 --:--")
        self._backup_status_label = ttk.Label(
            indicator_frame, textvariable=self._backup_status_var,
            font=("", 8), foreground=tc('text_muted'))
        self._backup_status_label.pack(side=LEFT, padx=(0, 5))

        # v3.9.7: 주기적으로 백업 시각 갱신
        self.root.after(3000, self._update_backup_status_indicator)

        # Task detail label
        self.task_detail_var = tk.StringVar(value="")
        self.task_detail_label = ttk.Label(
            right_container,
            textvariable=self.task_detail_var,
            foreground=tc('text_muted'),
            font=("", 10),
            width=20,
            anchor="e"
        )
        self.task_detail_label.pack(side=LEFT, padx=(0, 10))

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            right_container,
            variable=self.progress_var,
            maximum=100,
            length=150,
            mode='determinate'
        )
        self.progress_bar.pack(side=LEFT, padx=(0, 5))

        # Percentage label
        self.percent_var = tk.StringVar(value="0%")
        percent_label = ttk.Label(
            right_container,
            textvariable=self.percent_var,
            width=5,
            anchor="e"
        )
        percent_label.pack(side=LEFT)

        # Check modules after UI setup
        self.root.after(1000, self._check_module_status)

    def _set_status(self, message: str) -> None:
        """Set status bar message — 동시에 로그 탭에도 기록 (v5.9.9)"""
        if hasattr(self, 'status_var_bar'):
            self.status_var_bar.set(message)
        if message and message.strip() and hasattr(self, '_log'):
            if message.strip() == 'Ready':
                return
            try:
                self._log(message)
            except (RuntimeError, ValueError, AttributeError) as e:
                logger.debug(f"[_set_status] Suppressed: {e}")

    def _update_statusbar_summary(self) -> None:
        """v3.9.4: 상태바 실시간 재고 요약 갱신 (샘플 제외)"""
        if not hasattr(self, '_inv_summary_var'):
            return
        try:
            stats = self.engine.db.fetchone("""
                SELECT COUNT(*) AS lots,
                       COALESCE(SUM(current_weight), 0) AS total_kg
                FROM inventory WHERE status != 'DEPLETED'
            """)
            tb_stats = self.engine.db.fetchone("""
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN status='AVAILABLE' THEN 1 ELSE 0 END) AS avail
                FROM inventory_tonbag
                WHERE COALESCE(is_sample, 0) = 0
            """)
            lots = (stats.get('lots') or 0) if stats else 0
            weight_mt = ((stats.get('total_kg') or 0) / 1000) if stats else 0.0
            tb_total = (tb_stats.get('total') or 0) if tb_stats else 0
            tb_avail = (tb_stats.get('avail') or 0) if tb_stats else 0

            self._inv_summary_var.set(
                f"📦 LOT: {lots:,} | 🎒 톤백: {tb_avail:,}/{tb_total:,} | 💰 재고: {weight_mt:,.1f} MT"
            )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
            logger.debug(f"statusbar_mixin: {_e}")
        if hasattr(self, 'root'):
            self.root.update_idletasks()

    def _set_progress(self, value: float, detail: str = "") -> None:
        """Set progress bar value (0-100)"""
        if hasattr(self, 'progress_var'):
            self.progress_var.set(value)
        if hasattr(self, 'percent_var'):
            self.percent_var.set(f"{int(value)}%")
        if hasattr(self, 'task_detail_var') and detail:
            self.task_detail_var.set(detail)
        if hasattr(self, 'root'):
            self.root.update_idletasks()

    def _reset_progress_statusbar(self) -> None:
        """Reset progress bar"""
        self._set_progress(0, "")

    def _toggle_db_mode(self) -> None:
        """Toggle database read/write mode"""


        current = getattr(self, '_db_write_mode', True)

        if current:
            # Switch to read-only
            if CustomMessageBox.askyesno(self.root, "Read-Only Mode",
                "Switch to read-only mode?\n\n"
                "In read-only mode:\n"
                "- No changes will be saved\n"
                "- Safe for viewing data"):
                self._db_write_mode = False
                self.mode_label.config(text="READ", foreground=ThemeColors.get('warning', getattr(self, '_is_dark', False)))
                self._log("Switched to READ-ONLY mode")
        else:
            # Switch to write mode
            self._db_write_mode = True
            self.mode_label.config(text="WRITE", foreground=ThemeColors.get('success', getattr(self, '_is_dark', False)))
            self._log("Switched to WRITE mode")

    def _check_module_status(self) -> None:
        """Check status of required modules"""
        modules = {
            'pandas': 'pandas',
            'openpyxl': 'openpyxl',
            'reportlab': 'reportlab',
            'PIL': 'PIL',
            'cv2': 'cv2',
            'google.genai': 'google.genai',
            'ttkbootstrap': 'ttkbootstrap',
            'pystray': 'pystray',
        }

        loaded = 0
        total = len(modules)
        missing = []

        for name, import_name in modules.items():
            try:
                __import__(import_name)
                loaded += 1
            except ImportError:
                missing.append(name)

        # Update status
        if loaded == total:
            self.module_status_var.set(f"Modules: {loaded}/{total} OK")
            self.module_status_label.config(foreground=ThemeColors.get('success', getattr(self, '_is_dark', False)))
        elif loaded >= total - 2:
            self.module_status_var.set(f"Modules: {loaded}/{total}")
            self.module_status_label.config(foreground=ThemeColors.get('warning', getattr(self, '_is_dark', False)))
        else:
            self.module_status_var.set(f"Modules: {loaded}/{total} !")
            self.module_status_label.config(foreground=ThemeColors.get('danger', getattr(self, '_is_dark', False)))

        # Store for dialog
        self._module_status = {
            'loaded': loaded,
            'total': total,
            'missing': missing
        }

    def _show_module_status_dialog(self) -> None:
        """Show module status dialog"""
        from ..utils.constants import BOTH, W, tk, ttk

        status = getattr(self, '_module_status', None)
        if not status:
            self._check_module_status()
            status = self._module_status

        dialog = create_themed_toplevel(self.root)
        dialog.title("Module Status")
        dialog.transient(self.root)
        setup_dialog_geometry_persistence(dialog, "module_status_dialog", self.root, "small")

        # Summary
        ttk.Label(dialog,
            text=f"Loaded: {status['loaded']}/{status['total']}",
            font=('', 16, 'bold')).pack(pady=10)

        # Module list
        frame = ttk.LabelFrame(dialog, text="Module Details")
        frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        modules = [
            ('pandas', 'Data processing'),
            ('openpyxl', 'Excel files'),
            ('reportlab', 'PDF generation'),
            ('PIL', 'Image processing'),
            ('cv2', 'OpenCV'),
            ('google.genai', 'Gemini AI'),
            ('ttkbootstrap', 'Modern UI'),
            ('pystray', 'System tray'),
        ]

        for i, (mod, desc) in enumerate(modules):
            try:
                __import__(mod)
                status_text = "OK"
                color = "green"
            except ImportError:
                status_text = "Missing"
                color = "red"

            ttk.Label(frame, text=f"{mod}").grid(row=i, column=0, sticky=W, padx=5, pady=2)
            ttk.Label(frame, text=desc, foreground=tc('text_muted')).grid(row=i, column=1, sticky=W, padx=5)
            ttk.Label(frame, text=status_text, foreground=color).grid(row=i, column=2, padx=5)

        # Missing modules
        if status['missing']:
            ttk.Label(dialog,
                text=f"Missing: {', '.join(status['missing'])}",
                foreground=tc('danger')).pack(pady=5)

            ttk.Label(dialog,
                text="Install with: pip install " + " ".join(status['missing']),
                foreground=tc('text_muted'), font=('', 13)).pack()

        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def _update_backup_status_indicator(self) -> None:
        """v3.9.7: 마지막 백업 시각 인디케이터 갱신"""
        try:
            from datetime import datetime
            from pathlib import Path

            # 자동 백업 디렉토리
            backup_dirs = [
                Path('data/db/backups/auto'),
                Path('data/db/backups'),
            ]

            latest_time = None
            for bd in backup_dirs:
                if bd.exists():
                    for f in bd.glob('*.db'):
                        mt = f.stat().st_mtime
                        if latest_time is None or mt > latest_time:
                            latest_time = mt

            if latest_time:
                dt = datetime.fromtimestamp(latest_time)
                now = datetime.now()
                diff = (now - dt).total_seconds()

                if diff < 3600:
                    time_text = f"{int(diff/60)}분 전"
                    icon = "💾"
                elif diff < 86400:
                    time_text = f"{int(diff/3600)}시간 전"
                    icon = "💾"
                else:
                    time_text = dt.strftime('%m/%d')
                    icon = "⚠️"  # 24시간 이상 경과

                if hasattr(self, '_backup_status_var'):
                    self._backup_status_var.set(f"{icon}{time_text}")
            else:
                if hasattr(self, '_backup_status_var'):
                    self._backup_status_var.set("💾없음")
        except (ValueError, TypeError, KeyError) as _e:
            logger.debug(f"backup_indicator: {_e}")

        # 5분마다 갱신
        try:
            self.root.after(300000, self._update_backup_status_indicator)
        except (ValueError, TypeError, KeyError) as _e:
            logger.debug(f'Suppressed: {_e}')

    def _refresh_move_pending_badge(self) -> None:
        """이동 대기 배지 갱신 (5분마다 자동 호출) — v7.3.1 stub"""
        try:
            # 미처리 이동 건수 조회 (move_batch 테이블)
            count = 0
            try:
                # v8.0.2 [P7]: get_pending_batch_moves() 연결
                engine = getattr(self, 'engine', None)
                if engine and hasattr(engine, 'get_pending_batch_moves'):
                    pending = engine.get_pending_batch_moves() or []
                    count = len(pending)
                else:
                    row = self.engine.db.fetchone(
                        "SELECT COUNT(*) FROM move_batch WHERE status='PENDING'"
                    ) if engine else None
                    count = (row[0] if row else 0) if row else 0
            except Exception:
                logger.debug("[SUPPRESSED] exception in statusbar_mixin.py")  # noqa

            if hasattr(self, '_move_pending_var'):
                self._move_pending_var.set(f"📦 이동대기 {count}건" if count else "")
        except Exception as _e:
            logger.debug(f"_refresh_move_pending_badge: {_e}")
        finally:
            # 5분마다 재호출
            try:
                self.root.after(300000, self._refresh_move_pending_badge)
            except Exception:
                logger.debug("[SUPPRESSED] exception in statusbar_mixin.py")  # noqa

    def _on_move_pending_badge_click(self) -> None:
        """이동 대기 배지 클릭 — v7.3.1 stub"""
        try:
            self._safe_call('_on_show_move_pending')
        except Exception as _e:
            logger.debug(f"_on_move_pending_badge_click: {_e}")
