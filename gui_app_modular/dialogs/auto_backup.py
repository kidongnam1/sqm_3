"""
SQM v3.8.4 — 자동 백업 설정 다이얼로그 + 스케줄러
"""
from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from ..utils.custom_messagebox import CustomMessageBox
from ..utils.ui_constants import (
    setup_dialog_geometry_persistence,
)

logger = logging.getLogger(__name__)

# 자동 백업 설정 파일
AUTO_BACKUP_CONFIG = 'auto_backup_config.json'

# 기본 설정
DEFAULT_CONFIG = {
    'enabled': False,
    'interval_minutes': 240,   # 4시간
    'retention_days': 7,
    'backup_dir': 'data/db/backups/auto',
    'max_backups': 50,
}

# 간격 옵션
INTERVAL_OPTIONS = [
    ('30분', 30),
    ('1시간', 60),
    ('2시간', 120),
    ('4시간', 240),
    ('8시간', 480),
    ('매일 (24시간)', 1440),
]

# 보관 기간 옵션
RETENTION_OPTIONS = [
    ('3일', 3),
    ('7일', 7),
    ('14일', 14),
    ('30일', 30),
    ('무제한', 0),
]


def load_auto_backup_config() -> dict:
    """자동 백업 설정 로드"""
    try:
        if os.path.exists(AUTO_BACKUP_CONFIG):
            with open(AUTO_BACKUP_CONFIG, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 기본값 병합
                merged = {**DEFAULT_CONFIG, **config}
                return merged
    except (OSError, IOError, PermissionError) as e:
        logger.error(f"자동 백업 설정 로드 오류: {e}")
    return DEFAULT_CONFIG.copy()


def save_auto_backup_config(config: dict) -> None:
    """자동 백업 설정 저장"""
    try:
        with open(AUTO_BACKUP_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"자동 백업 설정 저장: {config}")
    except (OSError, IOError, PermissionError) as e:
        logger.error(f"자동 백업 설정 저장 오류: {e}")


class AutoBackupScheduler:
    """자동 백업 스케줄러 (tkinter after 기반)"""

    def __init__(self, root, engine, log_fn=None):
        self.root = root
        self.engine = engine
        self._log = log_fn or (lambda msg: logger.info(msg))
        self._timer_id = None
        self._config = load_auto_backup_config()
        self._running = False

    def start(self) -> None:
        """스케줄러 시작 (설정이 enabled일 때만)"""
        if not self._config.get('enabled', False):
            return

        self._running = True
        interval_ms = self._config['interval_minutes'] * 60 * 1000
        self._schedule_next(interval_ms)

        interval_text = self._get_interval_text()
        self._log(f"⏰ 자동 백업 활성화: {interval_text}마다")
        logger.info(f"자동 백업 시작: {interval_text}")

    def stop(self) -> None:
        """스케줄러 중지"""
        self._running = False
        if self._timer_id:
            try:
                self.root.after_cancel(self._timer_id)
            except (ValueError, TypeError, AttributeError) as _e:
                logger.debug(f"auto_backup: {_e}")
            self._timer_id = None
        logger.info("자동 백업 중지")

    def restart(self) -> None:
        """설정 변경 후 재시작"""
        self.stop()
        self._config = load_auto_backup_config()
        self.start()

    def _schedule_next(self, interval_ms: int) -> None:
        """다음 백업 예약"""
        if not self._running:
            return
        self._timer_id = self.root.after(interval_ms, self._execute_backup)

    def _execute_backup(self) -> None:
        """백업 실행 + v5.0.3: 무결성 검증"""
        if not self._running:
            return

        try:
            backup_dir = Path(self._config.get('backup_dir', 'data/db/backups/auto'))
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"auto_backup_{timestamp}.db"

            result = self.engine.create_backup("auto")

            if result.get('success'):
                backup_path = result.get('path')

                # v5.0.3: 백업 검증
                try:
                    from utils.backup_validator import BackupValidator

                    validation = BackupValidator.quick_validate(backup_path)

                    if validation['valid']:
                        self._log(f"✅ 자동 백업 완료 (검증 OK): {os.path.basename(backup_path)}")
                        logger.info(f"자동 백업 + 검증 성공: {backup_path}")
                    else:
                        self._log(f"⚠️ 백업 완료했으나 검증 실패: {validation['message']}")
                        logger.warning(f"백업 검증 실패: {validation['message']}")

                        # 검증 실패 시 재시도
                        logger.info("백업 재시도...")
                        result = self.engine.create_backup("auto_retry")
                        if result.get('success'):
                            retry_validation = BackupValidator.quick_validate(result.get('path'))
                            if retry_validation['valid']:
                                self._log("✅ 백업 재시도 성공")
                            else:
                                self._log("❌ 백업 재시도도 실패")

                except ImportError:
                    # 검증 모듈 없으면 기본 동작
                    self._log(f"⏰ 자동 백업 완료: {result.get('path', backup_name)}")
                    logger.info(f"자동 백업 성공: {result.get('path')}")

                # 오래된 백업 정리
                self._cleanup_old_backups()
            else:
                self._log(f"⏰ 자동 백업 실패: {result.get('error', '알 수 없는 오류')}")
                logger.error(f"자동 백업 실패: {result.get('error')}")

        except (OSError, RuntimeError) as e:
            self._log(f"⏰ 자동 백업 오류: {e}")
            logger.error(f"자동 백업 오류: {e}", exc_info=True)

        # v6.3.5: WAL PASSIVE checkpoint — 백업 직후 WAL 파일 내용을 main DB에 병합
        # PASSIVE: 쓰기 중인 트랜잭션을 차단하지 않으므로 성능 영향 없음
        # 효과: WAL 파일이 무한히 커지는 것을 방지 → 다음 백업 파일 크기 안정화
        try:
            if (
                hasattr(self, 'engine') and self.engine
                and hasattr(self.engine, 'db') and self.engine.db
                and hasattr(self.engine.db, '_local')
                and hasattr(self.engine.db._local, 'conn')
                and self.engine.db._local.conn
            ):
                self.engine.db._local.conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                logger.debug("[AutoBackup] WAL checkpoint(PASSIVE) 완료")
        except Exception as _wal_e:
            logger.debug(f"[AutoBackup] WAL checkpoint 실패(무시): {_wal_e}")

        # 다음 백업 예약
        interval_ms = self._config['interval_minutes'] * 60 * 1000
        self._schedule_next(interval_ms)

    def _cleanup_old_backups(self) -> None:
        """오래된 자동 백업 파일 정리"""
        retention_days = self._config.get('retention_days', 7)
        if retention_days == 0:  # 무제한
            return

        max_backups = self._config.get('max_backups', 50)
        backup_dir = Path(self._config.get('backup_dir', 'data/db/backups/auto'))

        if not backup_dir.exists():
            return

        now = datetime.now()
        auto_backups = sorted(
            backup_dir.glob('auto_backup_*.db'),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        deleted = 0
        for i, backup_file in enumerate(auto_backups):
            age_days = (now - datetime.fromtimestamp(backup_file.stat().st_mtime)).days

            if age_days > retention_days or i >= max_backups:
                try:
                    backup_file.unlink()
                    deleted += 1
                except (OSError, RuntimeError) as e:
                    logger.debug(f"백업 삭제 실패: {e}")

        if deleted > 0:
            logger.info(f"오래된 자동 백업 {deleted}개 삭제")

    def _get_interval_text(self) -> str:
        """간격을 텍스트로"""
        minutes = self._config.get('interval_minutes', 240)
        for text, mins in INTERVAL_OPTIONS:
            if mins == minutes:
                return text
        return f"{minutes}분"


class AutoBackupSettingsDialog:
    """자동 백업 설정 다이얼로그"""

    def __init__(self, parent, scheduler=None):
        self.parent = parent
        self.scheduler = scheduler
        self.config = load_auto_backup_config()

    def show(self) -> None:
        """다이얼로그 표시"""
        import tkinter as tk
        from tkinter import ttk

        self.dialog = create_themed_toplevel(self.parent)
        self.dialog.title("⏰ 자동 백업 설정")
        setup_dialog_geometry_persistence(self.dialog, "auto_backup_dialog", self.parent, "large")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        main = ttk.Frame(self.dialog, padding=20)
        main.pack(fill='both', expand=True)

        # 활성화 체크박스
        self.enabled_var = tk.BooleanVar(value=self.config.get('enabled', False))
        chk = ttk.Checkbutton(main, text="자동 백업 활성화",
                              variable=self.enabled_var,
                              command=self._toggle_state)
        chk.pack(anchor='w', pady=(0, 15))

        # 설정 프레임
        self.settings_frame = ttk.LabelFrame(main, text="설정", padding=10)
        self.settings_frame.pack(fill='x', pady=(0, 10))

        # 백업 간격
        row1 = ttk.Frame(self.settings_frame)
        row1.pack(fill='x', pady=5)
        ttk.Label(row1, text="백업 간격:", width=12).pack(side='left')

        self.interval_var = tk.StringVar()
        current_mins = self.config.get('interval_minutes', 240)
        for text, mins in INTERVAL_OPTIONS:
            if mins == current_mins:
                self.interval_var.set(text)
                break
        else:
            self.interval_var.set('4시간')

        interval_combo = ttk.Combobox(
            row1, textvariable=self.interval_var,
            values=[opt[0] for opt in INTERVAL_OPTIONS],
            state='readonly', width=20
        )
        interval_combo.pack(side='left', padx=(5, 0))

        # 보관 기간
        row2 = ttk.Frame(self.settings_frame)
        row2.pack(fill='x', pady=5)
        ttk.Label(row2, text="보관 기간:", width=12).pack(side='left')

        self.retention_var = tk.StringVar()
        current_days = self.config.get('retention_days', 7)
        for text, days in RETENTION_OPTIONS:
            if days == current_days:
                self.retention_var.set(text)
                break
        else:
            self.retention_var.set('7일')

        retention_combo = ttk.Combobox(
            row2, textvariable=self.retention_var,
            values=[opt[0] for opt in RETENTION_OPTIONS],
            state='readonly', width=20
        )
        retention_combo.pack(side='left', padx=(5, 0))

        # 백업 경로
        row3 = ttk.Frame(self.settings_frame)
        row3.pack(fill='x', pady=5)
        ttk.Label(row3, text="백업 경로:", width=12).pack(side='left')

        self.path_var = tk.StringVar(value=self.config.get('backup_dir', 'data/db/backups/auto'))
        ttk.Entry(row3, textvariable=self.path_var, width=25).pack(side='left', padx=(5, 0))

        # v3.9.7: 최근 백업 목록
        backup_list_frame = ttk.LabelFrame(main, text="📂 최근 백업", padding=8)
        backup_list_frame.pack(fill='x', pady=(5, 5))

        self._backup_list_text = tk.Text(backup_list_frame, height=5, width=50,
                                          state='disabled', wrap='word',
                                          font=('Consolas', 10))
        self._backup_list_text.pack(fill='x')
        self._load_backup_list()

        # 상태 표시
        self.status_label = ttk.Label(main, text="", foreground=tc('text_muted'))
        self.status_label.pack(anchor='w', pady=(5, 0))
        self._update_status()

        # 버튼
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(10, 0))

        # v3.9.7: 즉시 백업 버튼 추가
        ttk.Button(btn_frame, text="🔄 지금 백업", command=self._do_instant_backup).pack(side='left')
        ttk.Button(btn_frame, text="저장", command=self._save).pack(side='right', padx=(5, 0))
        ttk.Button(btn_frame, text="취소", command=self.dialog.destroy).pack(side='right')

        self._toggle_state()

    def _toggle_state(self) -> None:
        """활성화 상태에 따라 설정 프레임 활성/비활성"""
        enabled = self.enabled_var.get()
        state = 'normal' if enabled else 'disabled'
        for child in self.settings_frame.winfo_children():
            for widget in child.winfo_children():
                try:
                    widget.configure(state=state)
                except (RuntimeError, ValueError) as _e:
                    logger.debug(f"auto_backup: {_e}")
        self._update_status()

    def _update_status(self) -> None:
        """상태 텍스트 업데이트"""
        if self.enabled_var.get():
            self.status_label.config(text="✅ 자동 백업이 활성화됩니다", foreground=tc('success'))
        else:
            self.status_label.config(text="⛔ 자동 백업이 비활성화됩니다", foreground=tc('text_muted'))

    def _save(self) -> None:
        """설정 저장"""
        # 간격 변환
        interval_text = self.interval_var.get()
        interval_mins = 240
        for text, mins in INTERVAL_OPTIONS:
            if text == interval_text:
                interval_mins = mins
                break

        # 보관 기간 변환
        retention_text = self.retention_var.get()
        retention_days = 7
        for text, days in RETENTION_OPTIONS:
            if text == retention_text:
                retention_days = days
                break

        config = {
            'enabled': self.enabled_var.get(),
            'interval_minutes': interval_mins,
            'retention_days': retention_days,
            'backup_dir': self.path_var.get(),
            'max_backups': 50,
        }

        save_auto_backup_config(config)

        # 스케줄러 재시작
        if self.scheduler:
            self.scheduler.restart()

        self.dialog.destroy()

    def _load_backup_list(self) -> None:
        """v3.9.7: 최근 백업 목록 표시"""
        self._backup_list_text.config(state='normal')
        self._backup_list_text.delete('1.0', 'end')

        backup_dir = Path(self.config.get('backup_dir', 'data/db/backups/auto'))
        if not backup_dir.exists():
            self._backup_list_text.insert('end', '백업 없음')
            self._backup_list_text.config(state='disabled')
            return

        backups = sorted(backup_dir.glob('*.db'), key=lambda f: f.stat().st_mtime, reverse=True)

        if not backups:
            self._backup_list_text.insert('end', '백업 없음')
        else:
            for b in backups[:5]:
                size_kb = b.stat().st_size / 1024
                mod_time = datetime.fromtimestamp(b.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                self._backup_list_text.insert('end', f"  {mod_time}  {b.name}  ({size_kb:.0f}KB)\n")
            if len(backups) > 5:
                self._backup_list_text.insert('end', f"  ... +{len(backups)-5}개 더")

        self._backup_list_text.config(state='disabled')

    def _do_instant_backup(self) -> None:
        """v3.9.7: 즉시 백업 실행"""
        if self.scheduler and hasattr(self.scheduler, 'engine'):
            try:
                result = self.scheduler.engine.create_backup("manual_instant")
                if result and result.get('success'):
                    CustomMessageBox.showinfo(
                        self.root, "백업 완료",
                        f"백업이 생성되었습니다.\n\n{result.get('path', '')}"
                    )
                    self._load_backup_list()
                else:
                    CustomMessageBox.showwarning(
                        self.root, "백업 실패",
                        result.get('error', '알 수 없는 오류')
                    )
            except (RuntimeError, ValueError) as e:
                CustomMessageBox.show_detailed_error(self.root, "오류", str(e), exception=e)
        else:
            CustomMessageBox.showinfo(self.root, "안내", "엔진이 초기화되지 않았습니다.")
