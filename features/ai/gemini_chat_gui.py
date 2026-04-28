"""
SQM 재고관리 - Gemini AI 채팅 GUI (v2.9.43)

대화형 재고 조회 + Excel/PDF 내보내기 GUI
"""
from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import logging
import os
import sqlite3
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

from gui_app_modular.utils.custom_messagebox import CustomMessageBox

logger = logging.getLogger(__name__)

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class GeminiChatWindow:
    """Gemini AI 채팅 윈도우"""

    def __init__(self, parent: tk.Tk = None, db_path: str = None):
        # v8.0.6: DB 수정 엔진 초기화
        self._corrector = None
        self._awaiting_confirm = False  # 승인 대기 상태
        """
        Args:
            parent: 부모 윈도우 (None이면 독립 실행)
            db_path: 데이터베이스 경로
        """
        self.parent = parent
        self.db_path = db_path
        self.chat_engine = None
        self.is_processing = False

        # 독립 실행 또는 자식 윈도우
        if parent is None:
            self.root = tk.Tk()
            self.is_standalone = True
        else:
            self.root = create_themed_toplevel(parent)
            self.is_standalone = False

        self._setup_window()
        self._setup_ui()
        self._init_chat_engine()

    def _setup_window(self):
        """윈도우 설정"""
        self.root.title("🤖 SQM AI 재고 조회")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)

        # 아이콘 (프로젝트 루트 기준, 없으면 무시)
        try:
            _base = Path(__file__).resolve().parent.parent.parent
            _icon = _base / "assets" / "icon.ico"
            if _icon.exists():
                self.root.iconbitmap(str(_icon))
        except (AttributeError, RuntimeError, tk.TclError, OSError) as _e:
            logger.debug(f"[gemini_chat_gui] 아이콘 무시: {_e}")

    def _setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ─────────────────────────────────────────────
        # 상단: 타이틀 + DB 경로
        # ─────────────────────────────────────────────
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text="🤖 AI 재고 조회",
            font=("맑은 고딕", 14, "bold")
        ).pack(side=tk.LEFT)

        # DB 경로 표시
        self.db_label = ttk.Label(
            header_frame,
            text="DB: 연결 안됨",
            foreground=tc('text_muted')
        )
        self.db_label.pack(side=tk.RIGHT)

        # DB 선택 버튼
        ttk.Button(
            header_frame,
            text="DB 선택",
            command=self._select_db
        ).pack(side=tk.RIGHT, padx=5)

        # ─────────────────────────────────────────────
        # 중앙: 채팅 영역
        # ─────────────────────────────────────────────
        chat_frame = ttk.LabelFrame(main_frame, text="대화")
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 채팅 로그
        self.chat_text = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=("맑은 고딕", 10),
            state=tk.DISABLED,
            height=20
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True)

        # 태그 설정 (색상)
        self.chat_text.tag_configure("user", foreground=tc('info'), font=("맑은 고딕", 10, "bold"))
        self.chat_text.tag_configure("assistant", foreground=tc('success'))
        self.chat_text.tag_configure("system", foreground=tc('text_muted'), font=("맑은 고딕", 9, "italic"))
        self.chat_text.tag_configure("error", foreground=tc('danger'))

        # ─────────────────────────────────────────────
        # 하단: 입력 영역
        # ─────────────────────────────────────────────
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        # 입력 필드
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(
            input_frame,
            textvariable=self.input_var,
            font=("맑은 고딕", 11)
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", self._on_send)

        # 전송 버튼
        self.send_btn = ttk.Button(
            input_frame,
            text="전송",
            command=self._on_send,
            width=8
        )
        self.send_btn.pack(side=tk.LEFT)

        # ─────────────────────────────────────────────
        # 하단: 내보내기 버튼들
        # ─────────────────────────────────────────────
        export_frame = ttk.Frame(main_frame)
        export_frame.pack(fill=tk.X)

        ttk.Button(
            export_frame,
            text="📊 Excel 내보내기",
            command=self._export_excel
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            export_frame,
            text="📄 PDF 내보내기",
            command=self._export_pdf
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            export_frame,
            text="🗑️ 대화 지우기",
            command=self._clear_chat
        ).pack(side=tk.LEFT, padx=(0, 5))

        # 상태 표시
        self.status_var = tk.StringVar(value="준비")
        ttk.Label(
            export_frame,
            textvariable=self.status_var,
            foreground=tc('text_muted')
        ).pack(side=tk.RIGHT)

        # ─────────────────────────────────────────────
        # 예시 질문 버튼들
        # ─────────────────────────────────────────────
        example_frame = ttk.LabelFrame(main_frame, text="예시 질문")
        example_frame.pack(fill=tk.X, pady=(10, 0))

        examples = [
            "전체 재고 현황",
            "제품별 재고",
            "저재고 LOT (30% 이하)",
            "리튬카보네이트 재고",
            "SAP별 현황",
            "월별 입고 현황",
        ]

        for i, ex in enumerate(examples):
            btn = ttk.Button(
                example_frame,
                text=ex,
                command=lambda q=ex: self._quick_question(q)
            )
            btn.pack(side=tk.LEFT, padx=2)

        # 초기 메시지
        self._add_message(
            "시스템",
            "안녕하세요! SQM AI 재고 조회입니다.\n"
            "자연어로 질문하시면 재고 정보를 조회해 드립니다.\n\n"
            "예시:\n"
            "• 전체 재고 현황 알려줘\n"
            "• 리튬카보네이트 현재고\n"
            "• 저재고 LOT 목록\n"
            "• 2025년 3월 입고분\n",
            "system"
        )

    def _init_chat_engine(self):
        # v8.0.6: DB 수정 엔진 초기화
        try:
            from features.ai.gemini_db_corrector import GeminiDBCorrector
            gemini_client = getattr(self, '_gemini_client', None) or getattr(self.engine, 'client', None) if hasattr(self, 'engine') else None
            self._corrector = GeminiDBCorrector(
                db_path=self.db_path,
                gemini_client=gemini_client,
            )
        except Exception as _ce:
            import logging
            logging.getLogger(__name__).debug(f"DB Corrector 초기화 무시: {_ce}")
        """채팅 엔진 초기화"""
        if not self.db_path or not os.path.exists(self.db_path):
            self._add_message("시스템", "⚠️ DB를 선택해주세요.", "system")
            return

        try:
            from gemini_chat_query import GeminiChatQuery
            self.chat_engine = GeminiChatQuery(db_path=self.db_path)

            self.db_label.config(text=f"DB: {os.path.basename(self.db_path)}")
            self._add_message("시스템", f"✅ DB 연결됨: {self.db_path}", "system")

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            self._add_message("시스템", f"❌ DB 연결 실패: {e}", "error")

    def _select_db(self):
        """DB 파일 선택"""
        filepath = filedialog.askopenfilename(
            parent=getattr(self, "root", None),
            title="데이터베이스 선택",
            filetypes=[
                ("SQLite DB", "*.db"),
                ("All files", "*.*")
            ]
        )

        if filepath:
            self.db_path = filepath
            self._init_chat_engine()

    def _add_message(self, sender: str, message: str, tag: str = "assistant"):
        """메시지 추가"""
        self.chat_text.config(state=tk.NORMAL)

        timestamp = datetime.now().strftime("%H:%M")

        if sender == "사용자":
            self.chat_text.insert(tk.END, f"\n[{timestamp}] 🧑 ", "user")
            self.chat_text.insert(tk.END, f"{message}\n", "user")
        elif sender == "시스템":
            self.chat_text.insert(tk.END, f"\n{message}\n", tag)
        else:
            self.chat_text.insert(tk.END, f"\n[{timestamp}] 🤖 ", "assistant")
            self.chat_text.insert(tk.END, f"{message}\n", tag)

        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def _on_send(self, event=None):
        """전송 버튼 클릭"""
        question = self.input_var.get().strip()
        if not question:
            return

        if not self.chat_engine:
            CustomMessageBox.warning(None, "경고", "먼저 DB를 선택해주세요.")
            return

        if self.is_processing:
            return

        # 입력 초기화
        self.input_var.set("")

        # 사용자 메시지 표시
        self._add_message("사용자", question, "user")

        # 처리 시작
        self.is_processing = True
        self.status_var.set("조회 중...")
        self.send_btn.config(state=tk.DISABLED)

        # 백그라운드에서 처리
        thread = threading.Thread(target=self._process_question, args=(question,))
        thread.daemon = True
        thread.start()

    def _process_question(self, question: str):
        # v8.0.6: 수정 명령 처리
        q_lower = question.strip().lower()

        # 승인 대기 상태 → 확인/취소 처리
        if self._awaiting_confirm and self._corrector:
            if q_lower in ('확인', 'yes', 'y', '예', '네', 'ok', '승인'):
                result = self._corrector.execute_confirmed()
                self._awaiting_confirm = False
                self._show_result({'answer': result['message'], 'query_type': 'db_correct'})
                return
            elif q_lower in ('취소', 'no', 'n', 'cancel', '아니오', '아니'):
                result = self._corrector.cancel()
                self._awaiting_confirm = False
                self._show_result({'answer': result['message'], 'query_type': 'db_correct'})
                return

        # 수정 명령 감지
        CORRECT_KEYWORDS = ['수정', '변경', '바꿔', '바꾸', '고쳐', '틀렸', '오류', '잘못']
        is_correct_cmd = any(kw in question for kw in CORRECT_KEYWORDS)

        if is_correct_cmd and self._corrector:
            result = self._corrector.analyze_command(question)
            if result['status'] == 'confirm':
                self._awaiting_confirm = True
            self._show_result({'answer': result['message'], 'query_type': 'db_correct'})
            return
        """질문 처리 (백그라운드)"""
        try:
            result = self.chat_engine.ask(question)

            # UI 업데이트 (메인 스레드에서)
            self.root.after(0, lambda: self._show_result(result))

        except (RuntimeError, ValueError) as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self._add_message("시스템", f"❌ 오류: {msg}", "error"))

        finally:
            self.root.after(0, self._finish_processing)

    def _show_result(self, result: dict):
        """결과 표시 (v3.6.9: 응답 시간 표시)"""
        if result['success']:
            self._add_message("AI", result['answer'], "assistant")

            # v3.6.9: 응답 시간 + 건수 표시
            elapsed = result.get('elapsed_ms', 0)
            time_info = f" | ⏱ {elapsed}ms" if elapsed > 0 else ""

            if result['row_count'] > 0:
                self._add_message(
                    "시스템",
                    f"📊 조회 결과: {result['row_count']}건{time_info} (Excel/PDF 내보내기 가능)",
                    "system"
                )
            elif elapsed > 0:
                self._add_message("시스템", f"⏱ 응답 시간: {elapsed}ms", "system")
        else:
            self._add_message("AI", result['answer'], "error")

    def _finish_processing(self):
        """처리 완료"""
        self.is_processing = False
        self.status_var.set("준비")
        self.send_btn.config(state=tk.NORMAL)
        self.input_entry.focus()

    def _quick_question(self, question: str):
        """빠른 질문"""
        self.input_var.set(question)
        self._on_send()

    def _export_excel(self):
        """Excel 내보내기"""
        if not self.chat_engine or not self.chat_engine.last_result:
            CustomMessageBox.info(None, "알림", "먼저 조회를 실행해주세요.")
            return

        if not self.chat_engine.last_result.data:
            CustomMessageBox.info(None, "알림", "내보낼 데이터가 없습니다.")
            return

        filepath = filedialog.asksaveasfilename(
            parent=getattr(self, "root", None),
            title="Excel 저장",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"재고조회_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if filepath:
            result = self.chat_engine.export_to_excel(filepath)
            if os.path.exists(result):
                CustomMessageBox.info(None, "완료", f"Excel 저장 완료!\n{result}")
                self._add_message("시스템", f"📊 Excel 저장: {result}", "system")
            else:
                CustomMessageBox.error(None, "오류", result)

    def _export_pdf(self):
        """PDF 내보내기"""
        if not self.chat_engine or not self.chat_engine.last_result:
            CustomMessageBox.info(None, "알림", "먼저 조회를 실행해주세요.")
            return

        if not self.chat_engine.last_result.data:
            CustomMessageBox.info(None, "알림", "내보낼 데이터가 없습니다.")
            return

        filepath = filedialog.asksaveasfilename(
            parent=getattr(self, "root", None),
            title="PDF 저장",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"재고조회_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

        if filepath:
            result = self.chat_engine.export_to_pdf(filepath)
            if os.path.exists(result):
                CustomMessageBox.info(None, "완료", f"PDF 저장 완료!\n{result}")
                self._add_message("시스템", f"📄 PDF 저장: {result}", "system")
            else:
                CustomMessageBox.error(None, "오류", result)

    def _clear_chat(self):
        """대화 지우기"""
        parent = getattr(self, 'root', self.parent)
        if CustomMessageBox.askyesno(parent, "확인", "대화 내용을 모두 지우시겠습니까?"):
            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete(1.0, tk.END)
            self.chat_text.config(state=tk.DISABLED)

            if self.chat_engine:
                self.chat_engine.clear_history()

            self._add_message("시스템", "대화가 초기화되었습니다.", "system")

    def run(self):
        """실행 (독립 실행 시)"""
        if self.is_standalone:
            self.root.mainloop()


def open_chat_window(parent: tk.Tk = None, db_path: str = None):
    """채팅 윈도우 열기 (외부에서 호출용)"""
    window = GeminiChatWindow(parent=parent, db_path=db_path)
    return window


# ═══════════════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 기본 DB 경로
    default_db = "./test_inventory.db"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    elif os.path.exists(default_db):
        db_path = default_db
    else:
        db_path = None

    window = GeminiChatWindow(db_path=db_path)
    window.run()
