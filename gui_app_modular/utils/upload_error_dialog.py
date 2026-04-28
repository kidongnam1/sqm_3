"""
SQM 재고관리 시스템 - 업로드 실패 상세 팝업
==========================================

v4.2.1: 업로드 실패 시 상세 원인 및 해결 방법 표시

작성자: Ruby
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import tkinter as tk
from tkinter import scrolledtext, ttk


class UploadErrorDialog:
    """업로드 실패 상세 팝업"""

    def __init__(
        self,
        parent,
        title: str = "업로드 실패",
        error_message: str = "",
        copyable: bool = True
    ):
        """
        Args:
            parent: 부모 윈도우
            title: 다이얼로그 제목
            error_message: 오류 메시지 (포맷팅된 전체 메시지)
            copyable: 복사 버튼 표시 여부
        """
        self.parent = parent
        self.title_text = title
        self.error_message = error_message
        self.copyable = copyable
        self.dialog = None

    def show(self) -> None:
        """팝업 표시"""
        from .ui_constants import apply_modal_window_options
        self.dialog = create_themed_toplevel(self.parent)
        self.dialog.title(self.title_text)
        self.dialog.geometry("700x600")
        self.dialog.resizable(True, True)  # v9.0: 크기 조절 허용
        self.dialog.minsize(400, 300)  # v9.0: 최소 크기
        apply_modal_window_options(self.dialog)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # 화면 중앙 배치
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (600 // 2)
        self.dialog.geometry(f"700x600+{x}+{y}")

        self._create_widgets()

        # ESC 키로 닫기
        self.dialog.bind('<Escape>', lambda e: self.dialog.destroy())

        # 포커스 설정
        self.dialog.focus_set()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 제목 레이블
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        title_label = ttk.Label(
            title_frame,
            text=f"❌ {self.title_text}",
            font=('맑은 고딕', 14, 'bold')
        )
        title_label.pack(side=tk.LEFT)

        # 구분선
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=(0, 10))

        # 스크롤 가능한 텍스트 영역
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.text_area = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=('맑은 고딕', 10),
            height=20,
            width=80,
            relief=tk.SOLID,
            borderwidth=1
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)

        # 오류 메시지 삽입
        self.text_area.insert('1.0', self.error_message)
        self.text_area.config(state=tk.DISABLED)  # 읽기 전용

        # 텍스트 색상 및 스타일 적용
        self._apply_text_styles()

        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # 복사 버튼
        if self.copyable:
            copy_btn = ttk.Button(
                button_frame,
                text="📋 오류 내용 복사",
                command=self._copy_to_clipboard,
                width=20
            )
            copy_btn.pack(side=tk.LEFT, padx=5)

        # 닫기 버튼
        close_btn = ttk.Button(
            button_frame,
            text="확인",
            command=self.dialog.destroy,
            width=15
        )
        close_btn.pack(side=tk.RIGHT, padx=5)

    def _apply_text_styles(self) -> None:
        """텍스트 스타일 적용"""
        self.text_area.config(state=tk.NORMAL)

        # 태그 정의
        self.text_area.tag_config('title', font=('맑은 고딕', 12, 'bold'), foreground=tc('danger'))
        self.text_area.tag_config('section', font=('맑은 고딕', 10, 'bold'), foreground=tc('info'))
        self.text_area.tag_config('solution', font=('맑은 고딕', 10), foreground=tc('success'))
        self.text_area.tag_config('example', font=('맑은 고딕', 10), foreground=tc('info'), background=tc('bg_secondary'))
        self.text_area.tag_config('separator', font=('맑은 고딕', 10), foreground=tc('text_muted'))

        # 패턴 매칭으로 스타일 적용
        self.text_area.get('1.0', tk.END)

        # 제목 (❌로 시작하는 줄)
        start = '1.0'
        while True:
            start = self.text_area.search('❌', start, tk.END)
            if not start:
                break
            end = f"{start} lineend"
            self.text_area.tag_add('title', start, end)
            start = f"{start}+1c"

        # 섹션 (💡, 📌로 시작하는 줄)
        for icon in ['💡', '📌', '📋', '📞']:
            start = '1.0'
            while True:
                start = self.text_area.search(icon, start, tk.END)
                if not start:
                    break
                end = f"{start} lineend"
                self.text_area.tag_add('section', start, end)
                start = f"{start}+1c"

        # 구분선
        start = '1.0'
        while True:
            start = self.text_area.search('===', start, tk.END)
            if not start:
                break
            end = f"{start} lineend"
            self.text_area.tag_add('separator', start, end)
            start = f"{start}+1c"

        start = '1.0'
        while True:
            start = self.text_area.search('---', start, tk.END)
            if not start:
                break
            end = f"{start} lineend"
            self.text_area.tag_add('separator', start, end)
            start = f"{start}+1c"

        self.text_area.config(state=tk.DISABLED)

    def _copy_to_clipboard(self) -> None:
        """클립보드에 복사"""
        try:
            self.dialog.clipboard_clear()
            self.dialog.clipboard_append(self.error_message)
            self.dialog.update()

            # 복사 완료 메시지 (간단하게)
            from .custom_messagebox import CustomMessageBox
            CustomMessageBox.showinfo(
                self.dialog,
                "복사 완료",
                "오류 내용이 클립보드에 복사되었습니다.\n\n"
                "메모장이나 이메일에 붙여넣으세요."
            )
        except (ValueError, TypeError, AttributeError) as e:
            from .custom_messagebox import CustomMessageBox
            CustomMessageBox.showerror(
                self.dialog,
                "복사 실패",
                f"클립보드 복사 실패:\n{e}"
            )


def show_upload_error_dialog(
    parent,
    title: str,
    error_message: str
) -> None:
    """
    업로드 실패 팝업 표시 (간편 함수)
    
    Args:
        parent: 부모 윈도우
        title: 제목
        error_message: 오류 메시지
    """
    dialog = UploadErrorDialog(parent, title, error_message)
    dialog.show()


# 테스트
if __name__ == '__main__':
    root = tk.Tk()
    root.title("Test")
    root.geometry("400x300")
    root.resizable(True, True)  # v9.0: 크기 조절 허용
    root.minsize(400, 300)  # v9.0: 최소 크기

    test_message = """==================================================
📋 업로드 실패 요약
==================================================
전체 행: 10개
실패: 5개
성공: 5개

--------------------------------------------------
❌ 1. LOT NO 누락 (3건)
--------------------------------------------------
LOT NO 컬럼이 비어있거나 누락되었습니다.

실패 행:
  • 행 2, LOT NO: 
  • 행 5, LOT NO: 
  • 행 8, LOT NO: 

💡 해결 방법:
  • LOT NO는 10자리 숫자 필수입니다.
  • 예시: 1125072340
  • 빈 셀이 없는지 확인하세요.

📌 예시:
  1125072340

--------------------------------------------------
❌ 2. 날짜 형식 오류 (2건)
--------------------------------------------------
날짜가 올바른 형식이 아닙니다.

실패 행:
  • 행 3, ARRIVAL: 2025-13-01
  • 행 6, ARRIVAL: 20250101

💡 해결 방법:
  • 형식: YYYY-MM-DD (년-월-일)
  • 월: 01~12, 일: 01~31
  • 예시: 2025-01-15
  • 슬래시(/) 대신 하이픈(-) 사용

📌 예시:
  2025-01-15 (O) / 2025/01/15 (X) / 20250115 (X)

==================================================
📞 추가 도움이 필요하면 관리자에게 문의하세요.
=================================================="""

    def show_test():
        show_upload_error_dialog(root, "입고 Excel 업로드 실패", test_message)

    btn = ttk.Button(root, text="오류 팝업 테스트", command=show_test)
    btn.pack(pady=50)

    root.mainloop()
