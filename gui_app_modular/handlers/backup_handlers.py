"""
SQM Inventory - Backup Handlers
===============================

v2.9.91 - Extracted from gui_app.py

Backup, restore, and DB maintenance functions
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import is_dark  # v8.0.9
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from ..utils.ui_constants import (
    CustomMessageBox,
    ThemeColors,
    setup_dialog_geometry_persistence,
)

logger = logging.getLogger(__name__)


class BackupHandlersMixin:
    """
    Backup handlers mixin
    
    Mixed into SQMInventoryApp class
    """

    def _on_backup_click(self) -> None:
        """Create backup button click"""


        self._set_status("Creating backup...")
        self._log("Backup creation started...")

        try:
            # Use engine backup function
            result = self.engine.create_backup("manual")

            if result.get('success'):
                backup_path = result.get('path', 'N/A')
                self._log(f"OK Backup created: {backup_path}")
                CustomMessageBox.showinfo(self.root, "Backup Complete",
                    f"Backup created successfully!\n\nPath: {backup_path}")
            else:
                error = result.get('error', 'Unknown error')
                self._log(f"X Backup failed: {error}")
                CustomMessageBox.showerror(self.root, "Backup Failed", f"Backup error:\n{error}")

        except (RuntimeError, ValueError) as e:
            self._log(f"X Backup error: {e}")
            CustomMessageBox.showerror(self.root, "Error", f"Backup error:\n{e}")

        self._set_status("Ready")

    def _on_restore_click(self) -> None:
        """Restore from backup button click"""
        from ..utils.constants import filedialog

        # Select backup file
        backup_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select Backup File",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
            initialdir="output/backups"
        )

        if not backup_path:
            return

        # Confirm
        if not CustomMessageBox.askyesno(self.root, "Confirm Restore",
            f"Restore from this backup?\n\n"
            f"File: {os.path.basename(backup_path)}\n\n"
            "WARNING: Current data will be overwritten!"):
            return

        self._set_status("Restoring...")
        self._log(f"Restoring from: {backup_path}")

        try:
            result = self.engine.restore_backup(backup_path)

            if result.get('success'):
                self._log("OK Restore complete")
                CustomMessageBox.showinfo(self.root, "Restore Complete",
                    "Restore completed successfully!\n\n"
                    "Application will reload data.")

                # Refresh UI
                self._safe_refresh()
            else:
                error = result.get('error', 'Unknown error')
                self._log(f"X Restore failed: {error}")
                CustomMessageBox.showerror(self.root, "Restore Failed", f"Restore error:\n{error}")

        except (RuntimeError, ValueError) as e:
            self._log(f"X Restore error: {e}")
            CustomMessageBox.showerror(self.root, "Error", f"Restore error:\n{e}")

        self._set_status("Ready")

    def _show_backup_list(self) -> None:
        """Show backup list dialog"""
        from ..utils.constants import BOTH, END, LEFT, RIGHT, VERTICAL, X, Y, tk, ttk

        # Get backup list
        backup_dir = Path("output/backups")
        if not backup_dir.exists():
            backup_dir = Path("data/db/backups")

        backups = []
        if backup_dir.exists():
            for f in backup_dir.glob("*.db"):
                stat = f.stat()
                backups.append({
                    'name': f.name,
                    'path': str(f),
                    'size': stat.st_size,
                    'mtime': datetime.fromtimestamp(stat.st_mtime)
                })

        backups.sort(key=lambda x: x['mtime'], reverse=True)

        # Create dialog (Phase4: 크기 저장/복원)
        dialog = create_themed_toplevel(self.root)
        dialog.title("Backup List")
        dialog.transient(self.root)
        setup_dialog_geometry_persistence(dialog, "backup_list_dialog", self.root, "medium")

        # Treeview
        columns = ('name', 'size', 'date')
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=15)

        tree.heading('name', text='File Name', anchor='center')
        tree.heading('size', text='Size', anchor='center')
        tree.heading('date', text='Date', anchor='center')
        tree.column('name', width=250)
        tree.column('size', width=100, anchor='e')
        tree.column('date', width=150, anchor='center')

        # Scrollbar
        scrollbar = tk.Scrollbar(dialog, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Populate
        for b in backups:
            size_mb = b['size'] / (1024 * 1024)
            tree.insert('', END, values=(
                b['name'],
                f"{size_mb:.2f} MB",
                b['mtime'].strftime('%Y-%m-%d %H:%M')
            ))

        # Summary
        total_size = sum(b['size'] for b in backups) / (1024 * 1024)
        ttk.Label(dialog, text=f"Total: {len(backups)} backups, {total_size:.2f} MB").pack(pady=5)

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=X, pady=5)

        def restore_selected():
            selected = tree.selection()
            if not selected:
                CustomMessageBox.showwarning(self.root, "Select", "Please select a backup to restore")
                return

            item = tree.item(selected[0])
            backup_name = item['values'][0]
            backup_path = backup_dir / backup_name

            dialog.destroy()

            # Trigger restore
            if CustomMessageBox.askyesno(self.root, "Confirm Restore",
                f"Restore from {backup_name}?\n\n"
                "WARNING: Current data will be overwritten!"):
                try:
                    result = self.engine.restore_backup(str(backup_path))
                    if result.get('success'):
                        CustomMessageBox.showinfo(self.root, "Complete", "Restore complete!")
                        self._safe_refresh()
                    else:
                        CustomMessageBox.showerror(self.root, "Failed", f"Restore failed: {result.get('error')}")
                except (RuntimeError, ValueError) as e:
                    CustomMessageBox.showerror(self.root, "Error", f"Restore error: {e}")

        def delete_selected():
            selected = tree.selection()
            if not selected:
                CustomMessageBox.showwarning(self.root, "Select", "Please select a backup to delete")
                return

            item = tree.item(selected[0])
            backup_name = item['values'][0]
            backup_path = backup_dir / backup_name

            if CustomMessageBox.askyesno(self.root, "Confirm Delete", f"Delete {backup_name}?"):
                try:
                    backup_path.unlink()
                    tree.delete(selected[0])
                    self._log(f"Backup deleted: {backup_name}")
                except (ValueError, TypeError, AttributeError) as e:
                    CustomMessageBox.showerror(self.root, "Error", f"Delete error: {e}")

        ttk.Button(btn_frame, text="Restore", command=restore_selected).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete", command=delete_selected).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=RIGHT, padx=5)

    def _show_auto_backup_settings(self) -> None:
        """v3.8.4: 자동 백업 설정 다이얼로그"""
        try:
            from ..dialogs.auto_backup import AutoBackupSettingsDialog
            scheduler = getattr(self, '_auto_backup_scheduler', None)
            dialog = AutoBackupSettingsDialog(self.root, scheduler=scheduler)
            dialog.show()
        except (ImportError, ModuleNotFoundError) as e:
            self._log(f"❌ 자동 백업 설정 오류: {e}")
            logger.error(f"자동 백업 설정 오류: {e}", exc_info=True)

    def _start_auto_backup(self) -> None:
        """v3.8.4: 자동 백업 스케줄러 시작 (앱 시작 시 호출)"""
        try:
            from ..dialogs.auto_backup import AutoBackupScheduler
            self._auto_backup_scheduler = AutoBackupScheduler(
                root=self.root,
                engine=self.engine,
                log_fn=self._log
            )
            self._auto_backup_scheduler.start()
        except (ImportError, ModuleNotFoundError) as e:
            logger.error(f"자동 백업 스케줄러 시작 오류: {e}")

    def _on_optimize_db(self) -> None:
        """Optimize database"""


        if not CustomMessageBox.askyesno(self.root, "DB Optimization",
            "Optimize database?\n\n"
            "This will reclaim unused space and improve performance."):
            return

        self._set_status("Optimizing...")
        self._log("DB optimization started...")

        try:
            # VACUUM
            self.engine.db.execute("VACUUM")
            # ANALYZE
            self.engine.db.execute("ANALYZE")

            self._log("OK DB optimization complete")
            CustomMessageBox.showinfo(self.root, "Complete", "Database optimization complete.")
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            self._log(f"X Optimization error: {e}")
            CustomMessageBox.showerror(self.root, "Error", f"Optimization error:\n{e}")

        self._set_status("Ready")

    def _on_integrity_check(self) -> None:
        """DB integrity check"""


        self._set_status("Checking integrity...")
        self._log("DB integrity check started...")

        try:
            result = self.engine.db.fetchall("PRAGMA integrity_check")

            if result and result[0][0] == 'ok':
                self._log("OK DB integrity check passed")
                CustomMessageBox.showinfo(self.root, "Integrity Check",
                    "OK Database integrity check passed\n\n"
                    "No issues found.")
            else:
                issues = [str(r[0]) for r in result]
                self._log(f"WARNING DB issues found: {len(issues)}")
                for issue in issues[:5]:
                    self._log(f"   - {issue}")

                CustomMessageBox.showwarning(self.root, "Integrity Check",
                    f"WARNING Database issues found!\n\n"
                    f"Issues: {len(issues)}\n\n"
                    "Backup and recovery recommended.")
        except (RuntimeError, ValueError) as e:
            self._log(f"X Integrity check error: {e}")
            CustomMessageBox.showerror(self.root, "Error", f"Integrity check error:\n{e}")

        self._set_status("Ready")

    def _on_cleanup_logs(self) -> None:
        """Clean up old logs"""


        log_dir = Path("logs")
        if not log_dir.exists():
            CustomMessageBox.showinfo(self.root, "Info", "No log directory found")
            return

        # Find old logs (older than 30 days)
        now = datetime.now()
        old_logs = []

        for log_file in log_dir.glob("*.log"):
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            age_days = (now - mtime).days
            if age_days > 30:
                old_logs.append(log_file)

        if not old_logs:
            CustomMessageBox.showinfo(self.root, "Info", "No old logs found (30+ days)")
            return

        if not CustomMessageBox.askyesno(self.root, "Cleanup Logs",
            f"Delete {len(old_logs)} old log files?\n\n"
            "Files older than 30 days will be removed."):
            return

        deleted = 0
        for log_file in old_logs:
            try:
                log_file.unlink()
                deleted += 1
            except (RuntimeError, ValueError) as e:
                logger.error(f"Failed to delete {log_file}: {e}")

        self._log(f"Cleaned up {deleted} old logs")
        CustomMessageBox.showinfo(self.root, "Complete", f"Deleted {deleted} old log files")

    def _show_db_info(self) -> None:
        """v4.0.9: DB 구조 상세 정보 팝업"""
        from ..utils.constants import BOTH, LEFT, RIGHT, VERTICAL, X, Y, tk, ttk

        try:
            db_path = self.engine.db.db_path
            db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
            db_size_mb = db_size / (1024 * 1024)

            dialog = create_themed_toplevel(self.root)
            dialog.title("📊 DB 구조 정보")
            dialog.transient(self.root)
            dialog.grab_set()
            setup_dialog_geometry_persistence(dialog, "db_structure_dialog", self.root, "large")

            _bh_dark = is_dark()
            _h_bg = ThemeColors.get('statusbar_bg', _bh_dark)
            _h_fg = ThemeColors.get('statusbar_fg', _bh_dark)
            _h_fg_sec = ThemeColors.get('text_secondary', _bh_dark)
            # 상단 요약
            header = tk.Frame(dialog, bg=_h_bg, padx=15, pady=10)
            header.pack(fill=X)
            tk.Label(header, text="📊 SQM 데이터베이스 구조", font=('맑은 고딕', 16, 'bold'),
                     bg=_h_bg, fg=_h_fg).pack(anchor='w')
            tk.Label(header, text=f"경로: {db_path}  |  크기: {db_size_mb:.2f} MB  |  엔진: SQLite (WAL)",
                     font=('맑은 고딕', 10), bg=_h_bg, fg=_h_fg_sec).pack(anchor='w', pady=(3,0))

            # 테이블 목록 Treeview
            tree_frame = ttk.Frame(dialog)
            tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

            cols = ('table', 'rows', 'columns', 'description')
            tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=14)
            tree.heading('table', text='테이블명', anchor='center')
            tree.heading('rows', text='행수', anchor='center')
            tree.heading('columns', text='열수', anchor='center')
            tree.heading('description', text='설명', anchor='center')
            tree.column('table', width=200, anchor='w')
            tree.column('rows', width=80, anchor='center')
            tree.column('columns', width=80, anchor='center')
            tree.column('description', width=400, anchor='w')

            sb = tk.Scrollbar(tree_frame, orient=VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.pack(side=LEFT, fill=BOTH, expand=True)
            sb.pack(side=RIGHT, fill=Y)

            # 테이블 설명 매핑
            desc_map = {
                'inventory': '재고 마스터 (LOT 단위) — 핵심 테이블',
                'inventory_tonbag': '톤백 상세 (LOT→톤백 N개, 샘플 구분)',
                'inventory_detail': '입고 상세 (컨테이너별)',
                'inventory_snapshot': '일일 재고 스냅샷 (추이 분석)',
                'shipment': '선적 정보 (B/L, Invoice, 선박)',
                'outbound': '출고 오더 (고객/수량/상태)',
                'outbound_item': '출고 상세 (LOT/수량 매핑)',
                'stock_movement': '재고 이동 이력 (감사 로그)',
                'return_history': '반품(재입고) 이력',
                'picking_list_order': '피킹리스트 오더 (SQM 출고지시서)',
                'picking_list_material': '피킹리스트 자재 상세',
                'picking_list_detail': '피킹리스트 LOT별 상세',
                'sqlite_sequence': '(시스템) 자동증가 관리',
                'sqlite_stat1': '(시스템) 쿼리 최적화 통계',
            }

            import sqlite3 as _sq
            conn = _sq.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [r[0] for r in cursor.fetchall()]

            total_rows = 0
            # v5.6.0: 테이블명 화이트리스트 검증
            ALLOWED_TABLES = {
                'inventory', 'inventory_tonbag', 'inventory_detail', 'inventory_snapshot',
                'stock_movement', 'outbound', 'outbound_item', 'shipment',
                'picking_list_order', 'picking_list_material', 'picking_list_detail',
                'return_history', 'sqlite_sequence', 'sqlite_stat1'
            }
            for t in tables:
                if t not in ALLOWED_TABLES:
                    continue
                cursor.execute(f'PRAGMA table_info("{t}")')
                col_count = len(cursor.fetchall())
                cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
                row_count = cursor.fetchone()[0]
                total_rows += row_count
                desc = desc_map.get(t, '')
                tree.insert('', 'end', values=(t, f"{row_count:,}", col_count, desc))

            conn.close()

            # 하단 요약
            footer = tk.Frame(dialog, bg=_h_bg, padx=15, pady=8)
            footer.pack(fill=X)
            tk.Label(footer, text=f"총 {len(tables)}개 테이블  |  총 {total_rows:,}행  |  인덱스 44개",
                     font=('맑은 고딕', 11, 'bold'), bg=_h_bg, fg=ThemeColors.get('statusbar_icon_ok', _bh_dark)).pack(side=LEFT)

            tk.Button(footer, text="닫기", command=dialog.destroy,
                      font=('맑은 고딕', 10), padx=15).pack(side=RIGHT)
            tk.Button(footer, text="📋 docs/DB_SCHEMA.md 열기",
                      command=lambda: self._open_db_schema_doc(),
                      font=('맑은 고딕', 10), padx=15).pack(side=RIGHT, padx=5)

        except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError, ValueError) as e:
            CustomMessageBox.showerror(self.root, "오류", f"DB 정보 조회 실패:\n{e}")

    def _open_db_schema_doc(self) -> None:
        """DB_SCHEMA.md 파일 열기"""
        import subprocess
        doc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), 'docs', 'DB_SCHEMA.md')
        if os.path.exists(doc_path):
            try:
                subprocess.Popen(['notepad', doc_path])
            except (FileNotFoundError, OSError):
                CustomMessageBox.showinfo(self.root, "안내", f"파일 위치:\n{doc_path}")
        else:
            CustomMessageBox.showwarning(self.root, "안내", f"문서를 찾을 수 없습니다:\n{doc_path}")
