"""
SQM Inventory v3.5 - 단축키 가이드 및 도움말
UI/UX 개선: 사용자 친화적인 도움말 시스템

v3.6.0 - UI 통일성 적용
- 다이얼로그 크기 표준화 (DialogSize)
- 간격 표준화 (Spacing)
- 폰트 스케일링 (FontScale)
- 중앙 배치 (center_dialog)
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import logging
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Dict, List, Optional, Tuple


from ..utils.custom_messagebox import CustomMessageBox

logger = logging.getLogger(__name__)

# UI 통일성 모듈 임포트
try:
    from ..utils.ui_constants import (
        DialogSize,
        FontScale,
        Spacing,
        ThemeColors,
        apply_modal_window_options,
        apply_tooltip,
        center_dialog,
        setup_dialog_geometry_persistence,
    )
except ImportError:
    # 독립 실행 시 폴백
    DialogSize = None
    Spacing = type('Spacing', (), {'XS': 4, 'SM': 8, 'MD': 16, 'LG': 24})()
    FontScale = None
    center_dialog = None
    setup_dialog_geometry_persistence = None
    apply_tooltip = lambda w, t: None
    apply_modal_window_options = lambda w: None


class ShortcutGuideDialog:
    """
    단축키 가이드 대화상자
    
    사용법:
        dialog = ShortcutGuideDialog(parent_window)
        dialog.show()
    """

    # 단축키 정의
    SHORTCUTS: Dict[str, List[Tuple[str, str]]] = {
        "일반": [
            ("F1", "도움말 / 단축키 가이드"),
            ("F5", "전체 새로고침"),
            ("F11", "전체 화면 토글"),
            ("Ctrl+N", "새 입고 처리 (원스톱)"),
            ("Ctrl+O", "파일 열기"),
            ("Ctrl+S", "현재 탭 저장 / 내보내기"),
            ("Ctrl+B", "백업 생성"),
            ("Escape", "팝업 닫기 / 전체화면 해제"),
        ],
        "입출고": [
            ("Ctrl+I", "입고 파일 업로드"),
            ("Ctrl+E", "Excel 내보내기"),
            ("더블클릭", "LOT 상세보기"),
            ("Enter", "선택 항목 처리 / 분석 실행"),
        ],
        "검색/필터": [
            ("Ctrl+F", "검색창 포커스"),
            ("Ctrl+R", "전체 새로고침"),
            ("Esc", "검색 취소 / 대화상자 닫기"),
        ],
        "시스템": [
            ("Ctrl+Q", "강제 종료"),
        ],
        "데이터": [
            ("Ctrl+C", "선택 항목 복사"),
            ("Ctrl+A", "전체 선택"),
            ("Delete", "선택 항목 삭제"),
        ],
        "탭 이동": [
            ("Ctrl+1", "📦 판매가능"),
            ("Ctrl+2", "📋 판매배정"),
            ("Ctrl+3", "🚛 판매화물 결정"),
            ("Ctrl+4", "✅ 출고"),
            ("Ctrl+5", "📋 총괄 재고 리스트"),
            ("Ctrl+6", "📊 대시보드"),
            ("Ctrl+7", "📝 로그"),
            ("Ctrl+Tab", "다음 탭"),
            ("Ctrl+Shift+Tab", "이전 탭"),
        ],
        "기타": [
            ("드래그", "파일 업로드 (Drag & Drop)"),
        ],
    }

    def __init__(self, parent: tk.Tk, style: str = "darkly"):
        self.parent = parent
        self.style = style
        self.dialog: Optional[tk.Toplevel] = None

    def show(self) -> None:
        """대화상자 표시"""
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.lift()
            self.dialog.focus_set()
            return

        # === UI 통일성: 폰트 스케일 ===
        try:
            dpi = self.parent.winfo_fpixels('1i')
        except (RuntimeError, ValueError):
            dpi = 96

        if FontScale:
            fonts = FontScale(dpi)
        else:
            fonts = None

        # 대화상자 생성
        self.dialog = create_themed_toplevel(self.parent)
        self.dialog.title("⌨️ 단축키 가이드")
        self.dialog.transient(self.parent)
        if setup_dialog_geometry_persistence:
            setup_dialog_geometry_persistence(self.dialog, "shortcut_guide_dialog", self.parent, "large")
        else:
            if DialogSize:
                self.dialog.geometry(DialogSize.get_geometry(self.parent, 'large'))
            else:
                self.dialog.geometry("750x700")
            apply_modal_window_options(self.dialog)
            if center_dialog:
                center_dialog(self.dialog, self.parent)
            else:
                self._center_dialog_window()

        # 아이콘 (있으면)
        try:
            self.dialog.iconbitmap("assets/icon.ico")
        except (ValueError, TypeError, AttributeError) as _e:
            logger.debug(f"Suppressed: {_e}")

        # 컨텐츠 구성
        self._create_widgets(fonts)

        # ESC로 닫기
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())
        self.dialog.bind("<F1>", lambda e: self.dialog.destroy())

        # 포커스
        self.dialog.focus_set()

    def _center_dialog_window(self) -> None:
        """창 중앙 정렬 (폴백)"""
        self.dialog.update_idletasks()
        w = self.dialog.winfo_width()
        h = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (w // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (h // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self, fonts=None) -> None:
        """위젯 생성"""
        # === UI 통일성: 간격 표준화 ===
        main_frame = ttk.Frame(self.dialog, padding=Spacing.SM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 제목
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, Spacing.SM))

        title_font = fonts.heading(bold=True) if fonts else ("맑은 고딕", 16, "bold")
        body_font = fonts.body() if fonts else ("맑은 고딕", 10)
        small_font = fonts.small() if fonts else ("맑은 고딕", 9)

        ttk.Label(
            title_frame,
            text="⌨️ 단축키 가이드",
            font=title_font
        ).pack(side=tk.LEFT)

        ttk.Label(
            title_frame,
            text="SQM Inventory v3.5",
            font=body_font,
            foreground=tc('text_muted')
        ).pack(side=tk.RIGHT)

        # 노트북 (탭)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # 각 카테고리별 탭 생성
        for category, shortcuts in self.SHORTCUTS.items():
            frame = ttk.Frame(notebook, padding=Spacing.SM)
            notebook.add(frame, text=f" {category} ")

            # Treeview로 단축키 목록
            tree = ttk.Treeview(
                frame,
                columns=("shortcut", "description"),
                show="headings",
                height=12
            )
            tree.heading("shortcut", text="단축키", anchor='center')
            tree.heading("description", text="기능", anchor='center')
            tree.column("shortcut", width=120, anchor="center")
            tree.column("description", width=400, anchor="center")

            # 스크롤바
            scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            scrollbar_x = tk.Scrollbar(frame, orient='horizontal', command=tree.xview)
            tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=scrollbar_x.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

            # 데이터 추가
            for shortcut, description in shortcuts:
                tree.insert("", tk.END, values=(shortcut, description))

        # 하단 버튼
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(Spacing.SM, 0))

        _btn_manual = ttk.Button(
            button_frame,
            text="📖 전체 매뉴얼 보기",
            command=self._open_manual,
            bootstyle="info-outline"
        )
        _btn_manual.pack(side=tk.LEFT)
        apply_tooltip(_btn_manual, "사용자 매뉴얼 문서를 엽니다. 입고·출고·보고서 등 기능별 사용법이 안내됩니다.")

        _btn_close_shortcut = ttk.Button(
            button_frame,
            text="닫기",
            command=self.dialog.destroy,
            bootstyle="secondary"
        )
        _btn_close_shortcut.pack(side=tk.RIGHT)
        apply_tooltip(_btn_close_shortcut, "단축키 가이드 창을 닫습니다. Esc 키로도 닫을 수 있습니다.")

        # 팁
        tip_label = ttk.Label(
            button_frame,
            text="💡 팁: F1 키를 눌러 언제든 이 가이드를 열 수 있습니다",
            font=small_font,
            foreground=tc('text_muted')
        )
        tip_label.pack(side=tk.RIGHT, padx=Spacing.MD)

    def _open_manual(self) -> None:
        """매뉴얼 열기"""
        import os
        manual_path = os.path.join(
            os.path.dirname(__file__),
            "docs", "USER_MANUAL_V3_KR.md"
        )
        if os.path.exists(manual_path):
            os.startfile(manual_path)
        else:
            webbrowser.open("https://github.com/user/sqm-inventory/wiki")


class QuickTipOverlay:
    """
    빠른 팁 오버레이
    
    프로그램 시작 시 또는 특정 액션 후 팁 표시
    """

    TIPS = [
        ("💡 빠른 검색", "Ctrl+F를 눌러 현재 탭에서 빠르게 검색하세요"),
        ("📊 대시보드", "대시보드 탭에서 오늘의 입출고 현황을 한눈에 확인하세요"),
        ("🔄 자동 새로고침", "F5를 눌러 모든 데이터를 새로고침할 수 있습니다"),
        ("📁 드래그 앤 드롭", "PDF 파일을 창에 끌어다 놓으면 자동으로 인식됩니다"),
        ("⌨️ 단축키", "F1을 눌러 전체 단축키 목록을 확인하세요"),
        ("💾 자동 백업", "시스템이 24시간마다 자동으로 백업합니다"),
        ("🎨 테마 변경", "Ctrl+T로 테마를 변경할 수 있습니다"),
        ("📤 Excel 내보내기", "Ctrl+Shift+E로 현재 데이터를 Excel로 내보내세요"),
    ]

    def __init__(self, parent: tk.Tk, show_on_start: bool = True):
        self.parent = parent
        self.tip_index = 0
        self.overlay: Optional[tk.Toplevel] = None

        if show_on_start:
            self.parent.after(1500, self.show_tip)

    def show_tip(self, tip_index: Optional[int] = None) -> None:
        """팁 표시"""
        if tip_index is not None:
            self.tip_index = tip_index

        if self.tip_index >= len(self.TIPS):
            self.tip_index = 0

        title, content = self.TIPS[self.tip_index]

        # 기존 오버레이 제거
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.destroy()

        # 오버레이 생성
        self.overlay = create_themed_toplevel(self.parent)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)

        _tip_dark = ThemeColors.is_dark_theme(getattr(self.parent, 'current_theme', 'darkly'))
        _tip_bg = ThemeColors.get('info', _tip_dark)
        _tip_fg = ThemeColors.get('badge_text', _tip_dark)
        # 스타일 (v5.8.7 Phase2: ThemeColors)
        frame = ttk.Frame(self.overlay, padding=Spacing.MD)
        frame.pack(fill=tk.BOTH, expand=True)
        self.overlay.configure(bg=_tip_bg)
        frame.configure(style="info.TFrame")

        ttk.Label(frame, text=title, font=("맑은 고딕", 11, "bold"),
                  foreground=_tip_fg, background=_tip_bg).pack(anchor="center")
        ttk.Label(frame, text=content, font=("맑은 고딕", 13),
                  foreground=_tip_fg, background=_tip_bg, wraplength=300).pack(anchor="center", pady=(Spacing.XS, 0))

        close_btn = ttk.Label(frame, text="✕", font=("맑은 고딕", 12),
                              foreground=_tip_fg, background=_tip_bg, cursor="hand2")
        close_btn.place(relx=1.0, rely=0, anchor="ne")
        close_btn.bind("<Button-1>", lambda e: self._close())

        # 위치 (우하단)
        self.overlay.update_idletasks()
        w = self.overlay.winfo_width()
        h = self.overlay.winfo_height()
        x = self.parent.winfo_screenwidth() - w - 20
        y = self.parent.winfo_screenheight() - h - 60
        self.overlay.geometry(f"+{x}+{y}")

        # 클릭으로 닫기
        self.overlay.bind("<Button-1>", lambda e: self._close())

        # 5초 후 자동 닫기
        self.overlay.after(5000, self._close)

        self.tip_index += 1

    def _close(self) -> None:
        """오버레이 닫기"""
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.destroy()
            self.overlay = None


class WelcomeWizard:
    """
    환영 마법사 (첫 실행 시)
    
    프로그램 기본 사용법 안내
    """

    STEPS = [
        {
            "title": "👋 SQM 재고관리 시스템에 오신 것을 환영합니다!",
            "content": """
SQM Inventory v3.1은 리튬카보네이트와 니켈설페이트 재고를 
효율적으로 관리하는 전문 물류 시스템입니다.

이 가이드를 통해 기본적인 사용법을 알아보세요.
            """,
            "image": None
        },
        {
            "title": "📊 대시보드",
            "content": """
대시보드에서 한눈에 현황을 파악하세요:

• 총 재고 현황 (LOT 수, 중량)
• 오늘의 입고/출고 현황  
• 재고 부족 알림
• 빠른 액션 버튼
            """,
            "image": None
        },
        {
            "title": "📥 입고 처리",
            "content": """
PDF 파일을 드래그 앤 드롭하면 자동으로 인식합니다:

1. Packing List PDF를 창에 끌어다 놓기
2. 자동 파싱된 내용 확인
3. '입고 처리' 버튼 클릭

또는 Ctrl+I로 바로 입고 처리를 시작하세요.
            """,
            "image": None
        },
        {
            "title": "📤 출고 처리",
            "content": """
Allocation Excel 파일로 간편하게 출고하세요:

1. 출고 탭에서 Excel 파일 업로드
2. 미리보기로 출고 내역 확인
3. '출고 처리' 버튼으로 완료

LIFO 방식으로 자동 출고됩니다.
            """,
            "image": None
        },
        {
            "title": "⌨️ 유용한 단축키",
            "content": """
자주 사용하는 단축키:

• F1 - 도움말 / 단축키 가이드
• F5 - 새로고침
• Ctrl+F - 검색
• Ctrl+Shift+E - Excel 내보내기
• Ctrl+1~4 - 탭 이동
            """,
            "image": None
        },
        {
            "title": "🚀 시작할 준비가 되었습니다!",
            "content": """
이제 SQM 재고관리 시스템을 사용할 준비가 되었습니다.

• 궁금한 점은 F1을 눌러 도움말을 확인하세요
• 문제가 발생하면 '도움말 > 문제 신고'를 이용하세요

즐거운 사용 되세요! 🎉
            """,
            "image": None
        },
    ]

    def __init__(self, parent: tk.Tk, on_complete: Optional[callable] = None):
        self.parent = parent
        self.on_complete = on_complete
        self.current_step = 0
        self.dialog: Optional[tk.Toplevel] = None

    def show(self) -> None:
        """마법사 표시"""
        self.dialog = create_themed_toplevel(self.parent)
        self.dialog.title("환영합니다")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        if setup_dialog_geometry_persistence:
            setup_dialog_geometry_persistence(self.dialog, "welcome_wizard_dialog", self.parent, "medium")
        elif DialogSize and center_dialog:
            self.dialog.geometry(DialogSize.get_geometry(self.parent, 'medium'))
            apply_modal_window_options(self.dialog)
            center_dialog(self.dialog, self.parent)
        else:
            self.dialog.geometry("550x400")
            apply_modal_window_options(self.dialog)
            self.dialog.update_idletasks()
            x = (self.dialog.winfo_screenwidth() // 2) - 275
            y = (self.dialog.winfo_screenheight() // 2) - 200
            self.dialog.geometry(f"+{x}+{y}")

        # 컨텐츠 프레임
        self.content_frame = ttk.Frame(self.dialog, padding=20)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # 첫 단계 표시
        self._show_step()

    def _show_step(self) -> None:
        """현재 단계 표시"""
        # 기존 위젯 제거
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        step = self.STEPS[self.current_step]

        # 진행률 표시
        progress_frame = ttk.Frame(self.content_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 15))

        for i in range(len(self.STEPS)):
            color = "primary" if i <= self.current_step else "secondary"
            dot = ttk.Label(
                progress_frame,
                text="●" if i == self.current_step else "○",
                font=("", 12),
                bootstyle=color
            )
            dot.pack(side=tk.LEFT, padx=3)

        ttk.Label(
            progress_frame,
            text=f"{self.current_step + 1} / {len(self.STEPS)}",
            font=("맑은 고딕", 12),
            foreground=tc('text_muted')
        ).pack(side=tk.RIGHT)

        # 제목
        ttk.Label(
            self.content_frame,
            text=step["title"],
            font=("맑은 고딕", 14, "bold")
        ).pack(anchor="center", pady=(0, 10))

        # 내용
        content_label = ttk.Label(
            self.content_frame,
            text=step["content"].strip(),
            font=("맑은 고딕", 13),
            wraplength=500,
            justify=tk.LEFT
        )
        content_label.pack(anchor="center", fill=tk.X, expand=True)

        # 버튼
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        # 건너뛰기
        if self.current_step < len(self.STEPS) - 1:
            ttk.Button(
                button_frame,
                text="건너뛰기",
                command=self._skip,
                bootstyle="secondary-link"
            ).pack(side=tk.LEFT)

        # 이전
        if self.current_step > 0:
            ttk.Button(
                button_frame,
                text="◀ 이전",
                command=self._prev,
                bootstyle="secondary"
            ).pack(side=tk.RIGHT, padx=(5, 0))

        # 다음/완료
        if self.current_step < len(self.STEPS) - 1:
            ttk.Button(
                button_frame,
                text="다음 ▶",
                command=self._next,
                bootstyle="primary"
            ).pack(side=tk.RIGHT)
        else:
            ttk.Button(
                button_frame,
                text="시작하기 🚀",
                command=self._complete,
                bootstyle="success"
            ).pack(side=tk.RIGHT)

    def _next(self) -> None:
        """다음 단계"""
        if self.current_step < len(self.STEPS) - 1:
            self.current_step += 1
            self._show_step()

    def _prev(self) -> None:
        """이전 단계"""
        if self.current_step > 0:
            self.current_step -= 1
            self._show_step()

    def _skip(self) -> None:
        """건너뛰기"""
        self._complete()

    def _complete(self) -> None:
        """완료"""
        self.dialog.destroy()
        if self.on_complete:
            self.on_complete()


class FeedbackDialog:
    """
    피드백/문제 신고 대화상자
    """

    def __init__(self, parent: tk.Tk):
        self.parent = parent
        self.dialog: Optional[tk.Toplevel] = None

    def show(self) -> None:
        """대화상자 표시"""
        self.dialog = create_themed_toplevel(self.parent)
        self.dialog.title("💬 피드백 / 문제 신고")
        self.dialog.transient(self.parent)
        if setup_dialog_geometry_persistence:
            setup_dialog_geometry_persistence(self.dialog, "feedback_dialog", self.parent, "medium")
        elif DialogSize and center_dialog:
            self.dialog.geometry(DialogSize.get_geometry(self.parent, 'medium'))
            apply_modal_window_options(self.dialog)
            center_dialog(self.dialog, self.parent)
        else:
            self.dialog.geometry("500x400")
            apply_modal_window_options(self.dialog)
            self.dialog.update_idletasks()
            x = (self.dialog.winfo_screenwidth() // 2) - 250
            y = (self.dialog.winfo_screenheight() // 2) - 200
            self.dialog.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 유형 선택
        ttk.Label(main_frame, text="피드백 유형:", font=("맑은 고딕", 13, "bold")).pack(anchor="w")

        self.feedback_type = tk.StringVar(value="bug")
        types_frame = ttk.Frame(main_frame)
        types_frame.pack(fill=tk.X, pady=(5, 15))

        for value, text in [("bug", "🐛 버그 신고"), ("feature", "💡 기능 제안"), ("other", "📝 기타")]:
            ttk.Radiobutton(
                types_frame,
                text=text,
                variable=self.feedback_type,
                value=value
            ).pack(side=tk.LEFT, padx=(0, 15))

        # 제목
        ttk.Label(main_frame, text="제목:", font=("맑은 고딕", 13, "bold")).pack(anchor="w")
        self.title_entry = ttk.Entry(main_frame, width=60)
        self.title_entry.pack(fill=tk.X, pady=(5, 15))

        # 내용
        ttk.Label(main_frame, text="상세 내용:", font=("맑은 고딕", 13, "bold")).pack(anchor="w")
        self.content_text = tk.Text(main_frame, height=8, width=60, font=("맑은 고딕", 13))
        self.content_text.pack(fill=tk.BOTH, expand=True, pady=(5, 15))

        # 버튼
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(
            button_frame,
            text="취소",
            command=self.dialog.destroy,
            bootstyle="secondary"
        ).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="제출",
            command=self._submit,
            bootstyle="primary"
        ).pack(side=tk.RIGHT)

    def _submit(self) -> None:
        """피드백 제출"""
        feedback_type = self.feedback_type.get()
        title = self.title_entry.get().strip()
        content = self.content_text.get("1.0", tk.END).strip()

        if not title or not content:
            CustomMessageBox.showwarning(self.parent, "입력 필요", "제목과 내용을 모두 입력해주세요.")
            return

        # 로컬 파일로 저장
        import os
        from datetime import datetime

        feedback_dir = os.path.join(os.path.dirname(__file__), "feedback")
        os.makedirs(feedback_dir, exist_ok=True)

        filename = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(feedback_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"유형: {feedback_type}\n")
            f.write(f"제목: {title}\n")
            f.write(f"날짜: {datetime.now().isoformat()}\n")
            f.write(f"\n내용:\n{content}\n")

        CustomMessageBox.showinfo(self.parent,
            "감사합니다",
            "피드백이 저장되었습니다.\n관리자가 검토 후 조치하겠습니다."
        )
        self.dialog.destroy()


# === 테스트 ===
if __name__ == "__main__":
    import ttkbootstrap as ttkb  # noqa: F811

    root = ttkb.Window(title="UI 테스트", themename="darkly")
    root.geometry("800x600")

    # 버튼들
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Button(
        frame,
        text="단축키 가이드 (F1)",
        command=lambda: ShortcutGuideDialog(root).show(),
        bootstyle="primary"
    ).pack(pady=10)

    ttk.Button(
        frame,
        text="환영 마법사",
        command=lambda: WelcomeWizard(root).show(),
        bootstyle="info"
    ).pack(pady=10)

    ttk.Button(
        frame,
        text="피드백 대화상자",
        command=lambda: FeedbackDialog(root).show(),
        bootstyle="secondary"
    ).pack(pady=10)

    # 팁 오버레이
    QuickTipOverlay(root, show_on_start=True)

    # F1 바인딩
    root.bind("<F1>", lambda e: ShortcutGuideDialog(root).show())

    root.mainloop()
