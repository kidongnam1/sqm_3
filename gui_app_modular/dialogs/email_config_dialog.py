# -*- coding: utf-8 -*-
"""
email_config_dialog.py — SQM 이메일 설정 GUI (v7.5.0)

Gmail 앱 비밀번호 기반 SMTP 설정 편집 + 테스트 발송.
"""
from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import logging
import tkinter as tk

logger = logging.getLogger(__name__)


class EmailConfigDialog:
    """이메일 알림 설정 GUI 다이얼로그."""

    def __init__(self, parent, current_theme: str = 'darkly'):
        try:
            import ttkbootstrap as ttk
        except ImportError:
            import tkinter.ttk as ttk

        try:
            from features.notifications.return_alert_email import (
                load_email_config, save_email_config
            )
            self._load = load_email_config
            self._save = save_email_config
        except ImportError as e:
            import tkinter.messagebox as msgbox
            msgbox.showerror("오류", f"이메일 모듈 로드 실패:\n{e}", parent=parent)
            return

        self.parent = parent
        self.cfg = self._load()

        self.popup = create_themed_toplevel(parent)
        self.popup.title("⚙️ 이메일 알림 설정")
        self.popup.resizable(True, True)
        self.popup.grab_set()

        try:
            from ..utils.dialog_utils import center_dialog
            center_dialog(self.popup, 480, 480)
        except Exception:
            self.popup.geometry("480x480")

        self._build_ui(ttk)

    # ──────────────────────────────────────────────
    def _build_ui(self, ttk) -> None:
        pad = {'padx': 10, 'pady': 4}

        frame = ttk.Frame(self.popup)
        frame.pack(fill='both', expand=True, padx=16, pady=12)

        # 활성화 체크박스
        self._enabled_var = tk.BooleanVar(value=self.cfg.get('enabled', False))
        ttk.Checkbutton(frame, text="✅ 이메일 알림 활성화", variable=self._enabled_var).grid(
            row=0, column=0, columnspan=2, sticky='w', **pad)

        # 필드 목록
        fields = [
            ('SMTP 서버', 'smtp_host', 'smtp.gmail.com'),
            ('포트',      'smtp_port', '587'),
            ('Gmail 계정', 'smtp_user', 'example@gmail.com'),
            ('앱 비밀번호 (16자리)', 'smtp_pass', ''),
            ('발신자 주소', 'from_addr', ''),
            ('수신자 (쉼표 구분)', 'recipients_str', ''),
            ('회사명', 'company_name', '(주)지와이로지스'),
            ('창고명', 'warehouse', '광양 창고'),
            ('반품 임계 건수', 'threshold_count', '3'),
            ('조회 기간 (일)', 'threshold_days', '30'),
        ]

        self._vars: dict = {}
        for i, (label, key, placeholder) in enumerate(fields, start=1):
            ttk.Label(frame, text=label + ':').grid(row=i, column=0, sticky='e', **pad)
            var = tk.StringVar()
            # 수신자는 list → 쉼표 문자열
            if key == 'recipients_str':
                val = ', '.join(self.cfg.get('recipients', []))
            else:
                val = str(self.cfg.get(key, placeholder))
            var.set(val)
            show = '*' if key == 'smtp_pass' else ''
            entry = ttk.Entry(frame, textvariable=var, width=34, show=show)
            entry.grid(row=i, column=1, sticky='w', **pad)
            self._vars[key] = var

        # 가이드
        guide = ttk.Label(frame,
            text="💡 Gmail 앱 비밀번호: Google 계정 → 보안 → 앱 비밀번호",
            foreground=tc('text_muted'), font=('맑은 고딕', 10))
        guide.grid(row=len(fields)+1, column=0, columnspan=2, pady=(4, 8))

        # 버튼
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(fields)+2, column=0, columnspan=2, pady=8)

        ttk.Button(btn_frame, text="💾 저장",     command=self._on_save,   bootstyle='success').pack(side='left', padx=6)
        ttk.Button(btn_frame, text="📧 테스트 발송", command=self._on_test, bootstyle='info').pack(side='left', padx=6)
        ttk.Button(btn_frame, text="✖ 닫기",     command=self.popup.destroy).pack(side='left', padx=6)

    # ──────────────────────────────────────────────
    def _collect(self) -> dict:
        """UI → dict 변환."""
        cfg = {}
        cfg['enabled'] = self._enabled_var.get()
        for key, var in self._vars.items():
            if key == 'recipients_str':
                cfg['recipients'] = [e.strip() for e in var.get().split(',') if e.strip()]
            elif key in ('smtp_port', 'threshold_count', 'threshold_days'):
                try:
                    cfg[key] = int(var.get())
                except ValueError:
                    cfg[key] = self.cfg.get(key, 0)
            else:
                cfg[key] = var.get().strip()
        return cfg

    def _on_save(self) -> None:
        import tkinter.messagebox as msgbox
        cfg = self._collect()
        if self._save(cfg):
            self.cfg = cfg
            msgbox.showinfo("저장 완료", "이메일 설정이 저장되었습니다.", parent=self.popup)
        else:
            msgbox.showerror("저장 실패", "설정 파일 저장에 실패했습니다.", parent=self.popup)

    def _on_test(self) -> None:
        import tkinter.messagebox as msgbox
        cfg = self._collect()
        if not cfg.get('enabled'):
            msgbox.showwarning("비활성화", "먼저 '이메일 알림 활성화'를 체크하세요.", parent=self.popup)
            return
        if not cfg.get('smtp_pass') or not cfg.get('recipients'):
            msgbox.showwarning("설정 미완성", "앱 비밀번호와 수신자를 입력하세요.", parent=self.popup)
            return
        try:
            import smtplib, ssl
            from email.mime.text import MIMEText
            msg = MIMEText("SQM 이메일 테스트 발송입니다.", 'plain', 'utf-8')
            msg['Subject'] = "[SQM] 이메일 테스트"
            msg['From'] = cfg.get('from_addr') or cfg.get('smtp_user', '')
            msg['To'] = ', '.join(cfg['recipients'])
            ctx = ssl.create_default_context()
            with smtplib.SMTP(cfg['smtp_host'], int(cfg['smtp_port']), timeout=10) as s:
                s.starttls(context=ctx)
                s.login(cfg['smtp_user'], cfg['smtp_pass'])
                s.sendmail(msg['From'], cfg['recipients'], msg.as_string())
            msgbox.showinfo("테스트 성공", "테스트 이메일이 발송되었습니다!", parent=self.popup)
        except smtplib.SMTPAuthenticationError:
            msgbox.showerror("인증 실패", "Gmail 앱 비밀번호를 확인하세요.\n(일반 비밀번호 불가)", parent=self.popup)
        except Exception as e:
            msgbox.showerror("발송 실패", f"테스트 발송 실패:\n{e}", parent=self.popup)
