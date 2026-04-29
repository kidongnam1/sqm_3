"""
SQM 재고관리 - 단위 테스트 러너 다이얼로그
==========================================
수정·배포 전 pytest 실행으로 검증할 수 있는 안전망.
메뉴: 고급 → 🧪 단위 테스트
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
import subprocess
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


def _log(msg: str) -> None:
    try:
        logger.debug(msg)
    except Exception as e:
        logger.debug(f"Suppressed: {e}")


def get_tests_dir() -> Path:
    """프로젝트 루트의 tests/ 디렉터리."""
    try:
        root = Path(__file__).resolve().parents[2]
    except ImportError:
        root = Path(__file__).resolve().parents[2]
    return root / "tests"


def run_pytest_sync(tests_dir: Path) -> tuple[int, str]:
    """pytest를 실행하고 (returncode, stdout+stderr) 반환."""
    if not tests_dir.is_dir():
        return -1, f"tests 디렉터리 없음: {tests_dir}"
    cmd = [sys.executable, "-m", "pytest", str(tests_dir), "-v", "--tb=short"]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(tests_dir.parent),
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out
    except subprocess.TimeoutExpired:
        return -1, "타임아웃 (120초)"
    except Exception as e:
        return -1, str(e)


class TestRunnerDialog:
    """
    단위 테스트 실행 다이얼로그.
    Run 버튼으로 pytest tests/ 실행 후 결과를 텍스트 영역에 표시.
    """

    def __init__(self, parent):
        self.parent = parent
        self.win = None
        self._text = None
        self._running = False
        self._tk = None

    def show(self) -> None:
        if self.win is not None and self.win.winfo_exists():
            self.win.lift()
            self.win.focus_force()
            return
        try:
            from ..utils.constants import tk, ttk
            from ..utils.ui_constants import (
                DialogSize,
                Spacing,
                center_dialog,
                setup_dialog_geometry_persistence,
            )
        except ImportError:
            import tkinter as tk
            from tkinter import ttk
            Spacing = type("S", (), {"MD": 16, "SM": 8})()
            center_dialog = lambda w, x, y: None
            setup_dialog_geometry_persistence = None
        self._tk = tk

        self.win = create_themed_toplevel(self.parent)
        self.win.title("🧪 단위 테스트")
        self.win.minsize(400, 300)
        if setup_dialog_geometry_persistence:
            setup_dialog_geometry_persistence(self.win, "test_runner_dialog", self.parent, "medium")
        else:
            try:
                self.win.geometry(DialogSize.get_geometry(self.parent, 'medium'))
            except (NameError, AttributeError):
                self.win.geometry("700x500")

        f = ttk.Frame(self.win, padding=Spacing.MD)
        f.pack(fill=tk.BOTH, expand=True)

        btn_f = ttk.Frame(f)
        btn_f.pack(fill=tk.X, pady=(0, Spacing.SM))
        self._run_btn = ttk.Button(btn_f, text="Run tests (pytest tests/)", command=self._on_run)
        self._run_btn.pack(side=tk.LEFT, padx=(0, Spacing.SM))
        ttk.Button(btn_f, text="닫기", command=self.win.destroy).pack(side=tk.LEFT)

        self._text = tk.Text(f, wrap=tk.WORD, font=("Consolas", 9), state="disabled")
        self._text.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(f)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._text.config(yscrollcommand=sb.set)
        sb.config(command=self._text.yview)

        if not setup_dialog_geometry_persistence:
            try:
                center_dialog(self.win, self.parent)
            except (TypeError, NameError) as e:
                logger.debug(f"Suppressed: {e}")
        self._text.config(state=tk.NORMAL)
        self._text.insert(tk.END, "Run 버튼을 눌러 tests/ 디렉터리 단위 테스트를 실행하세요.\n")
        self._text.config(state="disabled")
        _log("TestRunnerDialog opened")

    def _on_run(self) -> None:
        if self._running or self._text is None or self._tk is None:
            return
        tk = self._tk
        self._running = True
        self._run_btn.config(state=tk.DISABLED)
        self._text.config(state=tk.NORMAL)
        self._text.delete(1.0, tk.END)
        self._text.insert(tk.END, "실행 중... (pytest tests/ -v --tb=short)\n")
        self._text.config(state=tk.DISABLED)
        tests_dir = get_tests_dir()
        thread = threading.Thread(target=self._run_in_thread, args=(tests_dir,), daemon=True)
        thread.start()

    def _run_in_thread(self, tests_dir: Path) -> None:
        code, out = run_pytest_sync(tests_dir)
        try:
            self.win.after(0, lambda: self._show_result(code, out))
        except Exception as e:
            _log(f"TestRunnerDialog result callback: {e}")
        self._running = False
        try:
            tk = getattr(self, "_tk", None)
            btn = self._run_btn
            if tk and btn and self.win:
                self.win.after(0, lambda: btn.config(state=tk.NORMAL))
        except Exception as e:
            logger.debug(f"Suppressed: {e}")

    def _show_result(self, returncode: int, out: str) -> None:
        if self._text is None:
            return
        tk = self._tk
        if tk is None:
            return
        self._text.config(state=tk.NORMAL)
        self._text.delete(1.0, tk.END)
        head = f"종료 코드: {returncode}\n\n"
        self._text.insert(tk.END, head + (out or "(출력 없음)"))
        self._text.see(tk.END)
        self._text.config(state="disabled")
