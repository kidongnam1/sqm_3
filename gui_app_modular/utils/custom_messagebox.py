"""
SQM v4.0.2 — CustomMessageBox
===============================

ui_constants.py에서 분리
"""
from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging

from .ui_constants import (
    ColumnWidth,
    FontScale,
    Spacing,
    ThemeColors,
    UICalculator,
    DialogSize,
    apply_modal_window_options,
    center_dialog,
)

logger = logging.getLogger(__name__)


class CustomMessageBox:
    """
    커스텀 메시지박스 - 메시지와 버튼 간격 조절 가능
    
    표준 messagebox 대비 장점:
    - 메시지-버튼 간격 조절 가능
    - UI 통일성 (폰트, 간격, 테마) 적용
    - 부모 창 중앙 배치
    
    사용법:
        from gui_app_modular.utils.ui_constants import CustomMessageBox
        
        # 정보 메시지
        CustomMessageBox.showinfo(parent, "제목", "메시지 내용")
        
        # 확인 질문 (Yes/No)
        result = CustomMessageBox.askyesno(parent, "확인", "진행하시겠습니까?")
        if result:
            # Yes 선택
            pass
    """

    # 메시지-버튼 간격 (픽셀) - 이 값을 조절하면 됩니다
    MESSAGE_BUTTON_GAP = 12  # 기본값: 12px (좁은 간격)

    # 아이콘 이모지
    ICONS = {
        'info': 'ℹ️',
        'warning': '⚠️',
        'error': '❌',
        'question': '❓',
    }

    @classmethod
    def _create_dialog(cls, parent, title: str, message: str,
                       icon_type: str = 'info',
                       buttons: list = None,
                       default_button: int = 0) -> any:
        """
        공통 다이얼로그 생성
        
        Args:
            parent: 부모 창
            title: 제목
            message: 메시지 내용
            icon_type: 'info', 'warning', 'error', 'question'
            buttons: 버튼 목록 [('텍스트', 반환값), ...]
            default_button: 기본 선택 버튼 인덱스
            
        Returns:
            선택한 버튼의 반환값
        """
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError:
            # 폴백: 표준 messagebox 사용
            from tkinter import messagebox
            if icon_type == 'info':
                messagebox.showinfo(title, message)
                return True
            elif icon_type == 'warning':
                messagebox.showwarning(title, message)
                return True
            elif icon_type == 'error':
                messagebox.showerror(title, message)
                return True
            elif icon_type == 'question':
                return messagebox.askyesno(title, message)
            return None

        if buttons is None:
            buttons = [('확인', True)]

        result = [None]  # 결과 저장용 (클로저)

        # 다이얼로그 생성
        dialog = create_themed_toplevel(parent)
        dialog.title(title)
        dialog.transient(parent)
        dialog.grab_set()
        apply_modal_window_options(dialog)

        # 폰트 스케일
        try:
            dpi = parent.winfo_fpixels('1i')
        except (RuntimeError, ValueError):
            dpi = 96
        fonts = FontScale(dpi)

        # 테마 확인
        try:
            current_theme = getattr(parent, 'current_theme', None)
            if current_theme is None:
                # 부모의 부모에서 찾기
                app = getattr(parent, 'master', parent)
                current_theme = getattr(app, 'current_theme', 'darkly')
        except (RuntimeError, ValueError):
            current_theme = 'darkly'

        # 메인 프레임
        main_frame = ttk.Frame(dialog, padding=Spacing.MD)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 상단: 아이콘 + 메시지
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # 아이콘
        icon = cls.ICONS.get(icon_type, 'ℹ️')
        icon_label = ttk.Label(content_frame, text=icon, font=('', 24))
        icon_label.pack(side=tk.LEFT, padx=(0, Spacing.SM))

        # 메시지
        msg_label = ttk.Label(
            content_frame,
            text=message,
            font=fonts.body(),
            wraplength=350,  # 긴 메시지 줄바꿈
            justify=tk.LEFT
        )
        msg_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ═══ 핵심: 메시지-버튼 간격 ═══
        # 이 값을 조절하면 메시지와 버튼 사이 간격이 변경됩니다
        gap_frame = ttk.Frame(main_frame, height=cls.MESSAGE_BUTTON_GAP)
        gap_frame.pack(fill=tk.X)
        gap_frame.pack_propagate(False)  # 고정 높이 유지

        # 하단: 버튼들
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        def on_button_click(value):
            result[0] = value
            dialog.destroy()

        # 버튼 생성 (오른쪽 정렬)
        for i, (text, value) in enumerate(reversed(buttons)):
            btn = ttk.Button(
                button_frame,
                text=text,
                command=lambda v=value: on_button_click(v),
                width=10
            )
            btn.pack(side=tk.RIGHT, padx=(Spacing.XS, 0))

            # 기본 버튼 포커스
            if i == len(buttons) - 1 - default_button:
                btn.focus_set()

        # ESC로 닫기 (취소/아니오와 동일)
        cancel_value = buttons[-1][1] if len(buttons) > 1 else buttons[0][1]
        dialog.bind('<Escape>', lambda e: on_button_click(cancel_value))

        # Enter로 기본 버튼 선택
        dialog.bind('<Return>', lambda e: on_button_click(buttons[default_button][1]))

        # 다이얼로그 크기 계산 및 중앙 배치
        dialog.update_idletasks()

        # 최소 크기 보장
        width = max(dialog.winfo_width(), 300)
        height = max(dialog.winfo_height(), 120)
        dialog.geometry(f"{width}x{height}")

        # 부모 창 중앙 배치
        center_dialog(dialog, parent)

        # 모달 대기
        dialog.wait_window()

        return result[0]

    @classmethod
    def showinfo(cls, parent, title: str, message: str) -> bool:
        """정보 메시지 표시"""
        return cls._create_dialog(parent, title, message, 'info', [('확인', True)])

    @classmethod
    def showwarning(cls, parent, title: str, message: str) -> bool:
        """경고 메시지 표시"""
        return cls._create_dialog(parent, title, message, 'warning', [('확인', True)])

    @classmethod
    def showerror(cls, parent, title: str, message: str) -> bool:
        """오류 메시지 표시"""
        return cls._create_dialog(parent, title, message, 'error', [('확인', True)])

    @classmethod
    def show_detailed_error(cls, parent, title: str, message: str,
                            exception: Exception = None, suggestion: str = None) -> bool:
        """v4.0.0: 상세 에러 팝업 (위치, 원인, 해결책 포함)"""
        import traceback

        detail_parts = [message]

        if exception:
            # 에러 타입과 위치
            tb = traceback.extract_tb(exception.__traceback__)
            if tb:
                last = tb[-1]
                detail_parts.append(f"\n📍 위치: {last.filename}:{last.lineno}")
                detail_parts.append(f"📍 함수: {last.name}()")
                if last.line:
                    detail_parts.append(f"📍 코드: {last.line.strip()}")

            detail_parts.append(f"\n❌ 오류 타입: {type(exception).__name__}")
            detail_parts.append(f"❌ 오류 내용: {str(exception)}")

        if suggestion:
            detail_parts.append(f"\n💡 해결책: {suggestion}")
        else:
            # 자동 해결책 제안
            if exception:
                err_type = type(exception).__name__
                auto_suggest = {
                    'FileNotFoundError': '파일 경로를 확인하세요.',
                    'PermissionError': '파일이 다른 프로그램에서 열려있는지 확인하세요.',
                    'sqlite3.OperationalError': 'DB 파일이 손상되었을 수 있습니다. 백업에서 복원하세요.',
                    'ValueError': '입력 데이터 형식을 확인하세요.',
                    'KeyError': '필수 필드가 누락되었습니다. 데이터를 확인하세요.',
                    'ConnectionError': '네트워크 연결을 확인하세요.',
                    'TypeError': '데이터 타입 불일치. 입력값을 확인하세요.',
                }
                hint = auto_suggest.get(err_type, 'F5를 눌러 새로고침 후 재시도하세요.')
                detail_parts.append(f"\n💡 해결책: {hint}")

        full_msg = '\n'.join(detail_parts)
        return cls._create_dialog(parent, title, full_msg, 'error', [('확인', True)])

    @classmethod
    def askyesno(cls, parent, title: str, message: str) -> bool:
        """Yes/No 질문 (True/False 반환)"""
        return cls._create_dialog(
            parent, title, message, 'question',
            [('예', True), ('아니오', False)],
            default_button=0
        )

    @classmethod
    def askokcancel(cls, parent, title: str, message: str) -> bool:
        """확인/취소 질문 (True/False 반환)"""
        return cls._create_dialog(
            parent, title, message, 'question',
            [('확인', True), ('취소', False)],
            default_button=0
        )

    @classmethod
    def askyesnocancel(cls, parent, title: str, message: str):
        """Yes/No/Cancel 질문 (True/False/None 반환)"""
        return cls._create_dialog(
            parent, title, message, 'question',
            [('예', True), ('아니오', False), ('취소', None)],
            default_button=0
        )

    @classmethod
    def askstring(cls, parent, title: str, prompt: str, initial: str = "", show=None):
        """
        한 줄 문자열 입력 (create_themed_toplevel + ttk, 테마 대비 유지).
        확인: 입력값(빈 문자열 가능), 취소·닫기: None.
        show: 예) '*' → 비밀번호 마스킹 (simpledialog.askstring show= 호환).
        """
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError:
            from tkinter import simpledialog
            return simpledialog.askstring(
                title, prompt, initialvalue=initial, parent=parent, show=show
            )

        out = [None]

        # 부모 없으면 Tk 기본 루트 사용 (None이면 winfo_fpixels → AttributeError로 버튼 콜백 전체 실패 가능)
        wm_parent = parent
        try:
            if wm_parent is None:
                wm_parent = tk._default_root  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug(f"askstring wm_parent resolve: {e}")
            wm_parent = parent
        if wm_parent is None:
            from tkinter import simpledialog
            return simpledialog.askstring(
                title, prompt, initialvalue=initial, parent=None, show=show
            )

        dialog = create_themed_toplevel(wm_parent)
        dialog.title(title)
        try:
            dialog.transient(wm_parent)
        except tk.TclError as e:
            logger.debug(f"askstring transient: {e}")
        dialog.grab_set()
        apply_modal_window_options(dialog)

        try:
            dpi = wm_parent.winfo_fpixels("1i")
        except (RuntimeError, ValueError, tk.TclError, AttributeError, TypeError):
            dpi = 96
        fonts = FontScale(dpi)

        main = ttk.Frame(dialog, padding=Spacing.MD)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text=prompt, font=fonts.body(), wraplength=400, justify=tk.LEFT).pack(
            anchor=tk.W, fill=tk.X, pady=(0, Spacing.SM)
        )
        var = tk.StringVar(value=initial or "")
        ent_kw = {"textvariable": var, "width": 44, "font": fonts.body()}
        if show:
            ent_kw["show"] = show
        ent = ttk.Entry(main, **ent_kw)
        ent.pack(fill=tk.X, pady=(0, Spacing.MD))
        ent.focus_set()
        try:
            ent.select_range(0, tk.END)
        except tk.TclError:
            pass  # TclError: widget destroyed
        gap = ttk.Frame(main, height=cls.MESSAGE_BUTTON_GAP)
        gap.pack(fill=tk.X)
        gap.pack_propagate(False)

        bf = ttk.Frame(main)
        bf.pack(fill=tk.X)

        def _ok():
            out[0] = var.get()
            dialog.destroy()

        def _cancel():
            out[0] = None
            dialog.destroy()

        ttk.Button(bf, text="확인", command=_ok, width=10).pack(side=tk.RIGHT, padx=(Spacing.XS, 0))
        ttk.Button(bf, text="취소", command=_cancel, width=10).pack(side=tk.RIGHT, padx=(Spacing.XS, 0))

        dialog.bind("<Return>", lambda e: _ok())
        dialog.bind("<Escape>", lambda e: _cancel())

        dialog.update_idletasks()
        w = max(dialog.winfo_width(), 380)
        h = max(dialog.winfo_height(), 140)
        dialog.geometry(f"{w}x{h}")
        center_dialog(dialog, wm_parent)
        try:
            dialog.lift(wm_parent)
        except tk.TclError as e:
            logger.debug(f"askstring lift: {e}")
        try:
            dialog.focus_force()
        except tk.TclError as e:
            logger.debug(f"askstring focus_force: {e}")
        dialog.wait_window()
        return out[0]

    @classmethod
    def set_gap(cls, pixels: int) -> None:
        """
        메시지-버튼 간격 설정
        
        Args:
            pixels: 간격 (픽셀), 기본값 12
            
        사용법:
            CustomMessageBox.set_gap(8)   # 좁은 간격
            CustomMessageBox.set_gap(16)  # 넓은 간격
        """
        cls.MESSAGE_BUTTON_GAP = max(4, min(pixels, 48))  # 4~48px 범위


# ═══════════════════════════════════════════════════════════════
# 테스트
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.debug("=" * 60)
    logger.debug("  SQM v3.5 UI 통일성 모듈 테스트")
    logger.debug("=" * 60)

    # UICalculator 테스트
    calc = UICalculator()
    logger.debug("\n[UICalculator]")
    logger.debug(f"  화면: {calc.screen_width}x{calc.screen_height}")
    logger.debug(f"  DPI: {calc.dpi}")
    logger.debug(f"  스케일: {calc.combined_scale:.2f}")
    logger.debug(f"  메인창 권장: {calc.get_main_window_size()}")

    # FontScale 테스트
    fonts = FontScale(dpi=120)
    logger.debug("\n[FontScale] (DPI=120)")
    logger.debug(f"  제목: {fonts.title()}")
    logger.debug(f"  본문: {fonts.body()}")
    logger.debug(f"  모노: {fonts.mono()}")

    # Spacing 테스트
    logger.debug("\n[Spacing]")
    logger.debug(f"  SM: {Spacing.SM}px")
    logger.debug(f"  MD: {Spacing.MD}px")
    logger.debug(f"  다이얼로그 패딩: {Spacing.Padding.DIALOG}px")

    # DialogSize 테스트
    logger.debug("\n[DialogSize]")
    for size in ['small', 'medium', 'large']:
        config = DialogSize.CONFIGS[size]
        logger.debug(f"  {size}: min={config.min_size}, max={config.max_size}")

    # ColumnWidth 테스트
    logger.debug("\n[ColumnWidth]")
    for field in ['lot_no', 'weight', 'customer']:
        width = ColumnWidth.get(field)
        anchor = ColumnWidth.get_anchor(field)
        logger.debug(f"  {field}: {width}px ({anchor})")

    # ThemeColors 테스트
    logger.debug("\n[ThemeColors]")
    logger.debug(f"  available (light): {ThemeColors.get('available', False)}")
    logger.debug(f"  available (dark):  {ThemeColors.get('available', True)}")

    # CustomMessageBox 테스트
    logger.debug("\n[CustomMessageBox]")
    logger.debug(f"  메시지-버튼 간격: {CustomMessageBox.MESSAGE_BUTTON_GAP}px")

    logger.debug("\n✅ 테스트 완료!")
