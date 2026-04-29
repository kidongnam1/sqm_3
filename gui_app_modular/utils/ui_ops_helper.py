"""
UI 운영 편의 모듈 (v3.0)
========================

1. 에러 발생 시 "로그 열기/복사" 버튼
2. 마지막 작업 자동 복구
3. 공유폴더에서 진행률 더 부드럽게
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import json
import logging
import os
import platform
import subprocess
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from gui_app_modular.utils.custom_messagebox import CustomMessageBox

logger = logging.getLogger(__name__)

# Tkinter 임포트
try:
    import tkinter as tk
    from tkinter import scrolledtext, ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False


# =============================================================================
# 1. 에러 다이얼로그 (로그 열기/복사 버튼)
# =============================================================================

class ErrorDialog:
    """
    에러 다이얼로그 with 로그 열기/복사 버튼
    
    사용:
        ErrorDialog.show(root, "오류 발생", exception=e, log_file="app.log")
    """

    @staticmethod
    def show(parent, message: str, details: str = None,
             exception: Exception = None, log_file: str = None,
             on_retry: Callable = None):
        """
        에러 다이얼로그 표시
        
        Args:
            parent: 부모 창
            message: 사용자 메시지
            details: 상세 정보
            exception: 예외 객체
            log_file: 로그 파일 경로
            on_retry: 재시도 콜백
        """
        if not HAS_TK:
            logger.error(f"Error: {message}")
            return

        # 예외에서 상세 정보 추출
        if exception and not details:
            details = ''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__
            ))

        dialog = create_themed_toplevel(parent)
        dialog.title("⚠️ 오류 발생")
        dialog.geometry("550x380")
        dialog.resizable(True, True)  # v9.0: 크기 조절 허용
        dialog.minsize(400, 300)  # v9.0: 최소 크기
        dialog.transient(parent)
        dialog.grab_set()

        # 메인 프레임
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill='both', expand=True)

        # 헤더
        header = ttk.Frame(main_frame)
        header.pack(fill='x', pady=(0, 10))

        ttk.Label(header, text="⚠️", font=('', 28)).pack(side='left')

        msg_frame = ttk.Frame(header)
        msg_frame.pack(side='left', fill='x', expand=True, padx=10)
        ttk.Label(msg_frame, text="오류가 발생했습니다",
                  font=('', 11, 'bold')).pack(anchor='w')
        ttk.Label(msg_frame, text=message, wraplength=400).pack(anchor='w')

        # 상세 정보
        if details:
            detail_frame = ttk.LabelFrame(main_frame, text="상세 정보 (개발자용)")
            detail_frame.pack(fill='both', expand=True, pady=10)

            text_widget = scrolledtext.ScrolledText(
                detail_frame, height=10, font=('Consolas', 10), wrap='word'
            )
            text_widget.pack(fill='both', expand=True, padx=5, pady=5)
            text_widget.insert('1.0', details)
            text_widget.config(state='disabled')

        # 버튼 프레임
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        # 왼쪽 버튼 (로그 관련)
        left_btns = ttk.Frame(btn_frame)
        left_btns.pack(side='left')

        if details:
            def copy_log():
                parent.clipboard_clear()
                parent.clipboard_append(details)
                CustomMessageBox.showinfo(dialog, "복사 완료", "로그가 클립보드에 복사되었습니다.")

            ttk.Button(left_btns, text="📋 로그 복사",
                       command=copy_log).pack(side='left', padx=(0, 5))

        if log_file and os.path.exists(log_file):
            def open_log():
                try:
                    system = platform.system()
                    if system == 'Windows':
                        os.startfile(log_file)
                    elif system == 'Darwin':
                        subprocess.run(['open', log_file])
                    else:
                        subprocess.run(['xdg-open', log_file])
                except (OSError, IOError, PermissionError) as e:
                    CustomMessageBox.show_detailed_error(parent, "오류", str(e), exception=e)

            ttk.Button(left_btns, text="📂 로그 열기",
                       command=open_log).pack(side='left', padx=(0, 5))

        # 오른쪽 버튼
        right_btns = ttk.Frame(btn_frame)
        right_btns.pack(side='right')

        if on_retry:
            def do_retry():
                dialog.destroy()
                on_retry()
            ttk.Button(right_btns, text="🔄 재시도",
                       command=do_retry).pack(side='left', padx=(0, 5))

        ttk.Button(right_btns, text="닫기",
                   command=dialog.destroy).pack(side='left')

        # 중앙 정렬
        dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0,x)}+{max(0,y)}")


def show_error(parent, message: str, exception: Exception = None,
               log_file: str = None, on_retry: Callable = None):
    """간편 에러 표시 함수"""
    ErrorDialog.show(parent, message, exception=exception,
                     log_file=log_file, on_retry=on_retry)


# =============================================================================
# 2. 마지막 작업 자동 복구
# =============================================================================

@dataclass
class WorkState:
    """작업 상태"""
    work_type: str          # inbound, outbound, pdf_parse 등
    started_at: str
    last_updated: str
    status: str             # pending, in_progress, completed, failed
    progress: float         # 0.0 ~ 1.0
    data: Dict[str, Any]
    error: Optional[str] = None


class WorkRecovery:
    """
    작업 복구 관리자
    
    사용:
        recovery = WorkRecovery()
        
        # 작업 시작
        recovery.start_work('inbound', {'files': [...]})
        
        # 진행률 업데이트
        recovery.update_progress(0.5, {'processed': 10})
        
        # 완료
        recovery.complete_work({'result': ...})
        
        # 앱 시작 시 미완료 작업 확인
        if recovery.has_unfinished_work():
            recovery.show_recovery_dialog(root, on_recover=...)
    """

    STATE_FILE = "work_recovery_state.json"

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(__file__), 'data'
        )
        os.makedirs(self.data_dir, exist_ok=True)
        self.state_path = os.path.join(self.data_dir, self.STATE_FILE)
        self._current: Optional[WorkState] = None
        self._lock = threading.Lock()

    def start_work(self, work_type: str, data: Dict[str, Any]) -> str:
        """작업 시작"""
        with self._lock:
            now = datetime.now().isoformat()
            self._current = WorkState(
                work_type=work_type,
                started_at=now,
                last_updated=now,
                status='in_progress',
                progress=0.0,
                data=data
            )
            self._save()
            logger.info(f"[복구] 작업 시작: {work_type}")
            return now

    def update_progress(self, progress: float, data_update: Dict = None):
        """진행률 업데이트"""
        with self._lock:
            if self._current:
                self._current.progress = min(1.0, max(0.0, progress))
                self._current.last_updated = datetime.now().isoformat()
                if data_update:
                    self._current.data.update(data_update)
                self._save()

    def complete_work(self, result: Dict = None):
        """작업 완료"""
        with self._lock:
            if self._current:
                self._current.status = 'completed'
                self._current.progress = 1.0
                if result:
                    self._current.data['result'] = result
                logger.info(f"[복구] 작업 완료: {self._current.work_type}")
                self._current = None
                self._clear()

    def fail_work(self, error: str):
        """작업 실패"""
        with self._lock:
            if self._current:
                self._current.status = 'failed'
                self._current.error = error
                self._save()
                logger.error(f"[복구] 작업 실패: {self._current.work_type} - {error}")

    def has_unfinished_work(self) -> bool:
        """미완료 작업 존재 여부"""
        work = self._load()
        return work is not None and work.status in ('in_progress', 'failed')

    def get_unfinished_work(self) -> Optional[WorkState]:
        """미완료 작업 가져오기"""
        work = self._load()
        if work and work.status in ('in_progress', 'failed'):
            return work
        return None

    def show_recovery_dialog(self, parent,
                              on_recover: Callable[[WorkState], None],
                              on_discard: Callable = None) -> bool:
        """복구 다이얼로그 표시"""
        if not HAS_TK:
            return False

        work = self.get_unfinished_work()
        if not work:
            return False

        dialog = create_themed_toplevel(parent)
        dialog.title("미완료 작업 발견")
        dialog.geometry("420x280")
        dialog.resizable(True, True)  # v9.0: 크기 조절 허용
        dialog.minsize(400, 300)  # v9.0: 최소 크기
        dialog.transient(parent)
        dialog.grab_set()

        result = {'recover': False}

        # 내용
        main = ttk.Frame(dialog, padding=20)
        main.pack(fill='both', expand=True)

        ttk.Label(main, text="🔄", font=('', 32)).pack()
        ttk.Label(main, text="미완료 작업이 있습니다",
                  font=('', 12, 'bold')).pack(pady=(10, 15))

        # 작업 정보
        info = ttk.Frame(main)
        info.pack()

        work_names = {
            'inbound': '입고 처리',
            'outbound': '출고 처리',
            'pdf_parse': 'PDF 파싱',
            'excel_import': 'Excel 가져오기'
        }
        work_name = work_names.get(work.work_type, work.work_type)

        ttk.Label(info, text=f"작업: {work_name}").pack(anchor='w')
        ttk.Label(info, text=f"진행률: {work.progress:.0%}").pack(anchor='w')
        ttk.Label(info, text=f"시작: {work.started_at[:19]}").pack(anchor='w')

        if work.error:
            ttk.Label(info, text=f"오류: {work.error[:40]}...",
                      foreground=tc('danger')).pack(anchor='w')

        ttk.Label(main, text="\n이어서 진행하시겠습니까?").pack()

        # 버튼
        btns = ttk.Frame(main)
        btns.pack(pady=15)

        def do_recover():
            result['recover'] = True
            dialog.destroy()
            on_recover(work)

        def do_discard():
            dialog.destroy()
            self._clear()
            if on_discard:
                on_discard()

        ttk.Button(btns, text="✅ 이어서 진행",
                   command=do_recover).pack(side='left', padx=5)
        ttk.Button(btns, text="❌ 무시",
                   command=do_discard).pack(side='left', padx=5)

        # 중앙
        dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0,x)}+{max(0,y)}")

        parent.wait_window(dialog)
        return result['recover']

    def _save(self):
        """상태 저장"""
        if self._current:
            try:
                with open(self.state_path, 'w', encoding='utf-8') as f:
                    json.dump(asdict(self._current), f, ensure_ascii=False)
            except (OSError, IOError, PermissionError) as e:
                logger.warning(f"[복구] 저장 실패: {e}")

    def _load(self) -> Optional[WorkState]:
        """상태 로드"""
        if not os.path.exists(self.state_path):
            return None
        try:
            with open(self.state_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return WorkState(**data)
        except (OSError, IOError, PermissionError) as e:
            logger.warning(f"[복구] 로드 실패: {e}")
            return None

    def _clear(self):
        """상태 파일 삭제"""
        try:
            if os.path.exists(self.state_path):
                os.remove(self.state_path)
        except (OSError, IOError, PermissionError) as _e:
            logger.warning(f"Suppressed: {_e}")


# =============================================================================
# 3. 부드러운 진행률 (공유폴더 대응)
# =============================================================================

class SmoothProgress:
    """
    부드러운 진행률 표시
    
    공유폴더의 느린 응답에도 부드러운 애니메이션 제공
    
    사용:
        progress = SmoothProgress(progressbar, label)
        progress.start()
        
        # 실제 진행률 설정 (느려도 부드럽게 표시)
        progress.set_progress(0.5, "처리 중...")
        
        progress.complete("완료!")
    """

    def __init__(self, progressbar: 'ttk.Progressbar',
                 label: 'ttk.Label' = None,
                 smoothing: float = 0.15):
        """
        Args:
            progressbar: 진행률 바
            label: 상태 레이블
            smoothing: 부드러움 (0~1, 클수록 빠름)
        """
        self.progressbar = progressbar
        self.label = label
        self.smoothing = smoothing

        self._target = 0.0
        self._current = 0.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stall_time = 0.0
        self._last_target_change = time.time()

        # 초기화
        self.progressbar.configure(mode='determinate', maximum=100, value=0)

    def start(self):
        """애니메이션 시작"""
        self._running = True
        self._current = 0.0
        self._target = 0.0
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self):
        """애니메이션 중지"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)

    def set_progress(self, value: float, status: str = None):
        """
        진행률 설정
        
        Args:
            value: 0.0 ~ 1.0
            status: 상태 메시지
        """
        self._target = max(0.0, min(1.0, value)) * 100
        self._last_target_change = time.time()

        if status and self.label:
            self._safe_update_label(status)

    def set_indeterminate(self, message: str = "처리 중..."):
        """불확정 모드"""
        self.progressbar.configure(mode='indeterminate')
        self.progressbar.start(15)
        if self.label:
            self._safe_update_label(message)

    def complete(self, message: str = "완료"):
        """완료"""
        self._target = 100
        self._current = 100
        self._running = False

        self._safe_update_bar(100)
        if self.label:
            self._safe_update_label(message)

    def _animate(self):
        """애니메이션 루프"""
        while self._running:
            try:
                # 부드러운 보간
                diff = self._target - self._current
                if abs(diff) > 0.5:
                    self._current += diff * self.smoothing
                else:
                    self._current = self._target

                # 정체 감지 (5초 이상 같은 값)
                stall_duration = time.time() - self._last_target_change
                if stall_duration > 5 and self._target < 95:
                    # 정체 시 미세하게 진행 (살아있음 표시)
                    if self._current < self._target + 3:
                        self._current += 0.05

                    if self.label and stall_duration > 3:
                        self._safe_update_label(f"처리 중... ({self._current:.0f}%)")

                # UI 업데이트
                self._safe_update_bar(self._current)

                time.sleep(0.05)  # 20 FPS

            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"[진행률] 애니메이션 오류: {e}")
                time.sleep(0.1)

    def _safe_update_bar(self, value: float):
        """스레드 안전 진행률 업데이트"""
        try:
            self.progressbar.after(0, lambda: self.progressbar.configure(value=value))
        except (ValueError, TypeError, AttributeError) as _e:
            logger.debug(f"Suppressed: {_e}")

    def _safe_update_label(self, text: str):
        """스레드 안전 레이블 업데이트"""
        try:
            self.label.after(0, lambda: self.label.configure(text=text))
        except (ValueError, TypeError, AttributeError) as _e:
            logger.debug(f"Suppressed: {_e}")


# =============================================================================
# 통합 헬퍼
# =============================================================================

class UIOperationsHelper:
    """
    UI 운영 편의 통합 헬퍼
    
    사용:
        helper = UIOperationsHelper(root, progressbar, label)
        
        # 에러 처리
        try:
            risky_operation()
        except (KeyError, ValueError) as e:
            helper.show_error("작업 실패", exception=e)
        
        # 작업 복구
        helper.check_recovery(on_recover=resume_work)
        
        # 진행률
        helper.start_work('inbound', {'files': files})
        helper.update_progress(0.5, "50% 완료")
        helper.complete_work()
    """

    def __init__(self, parent: 'tk.Tk',
                 progressbar: 'ttk.Progressbar' = None,
                 progress_label: 'ttk.Label' = None,
                 log_dir: str = None):
        self.parent = parent
        self.log_dir = log_dir or os.path.join(os.path.dirname(__file__), 'logs')

        # 복구 관리자
        self.recovery = WorkRecovery()

        # 진행률 관리자
        self.progress: Optional[SmoothProgress] = None
        if progressbar:
            self.progress = SmoothProgress(progressbar, progress_label)

    def show_error(self, message: str, exception: Exception = None,
                   on_retry: Callable = None):
        """에러 표시"""
        log_file = self._find_latest_log()
        ErrorDialog.show(self.parent, message, exception=exception,
                        log_file=log_file, on_retry=on_retry)

    def check_recovery(self, on_recover: Callable[[WorkState], None],
                       on_discard: Callable = None) -> bool:
        """미완료 작업 확인"""
        return self.recovery.show_recovery_dialog(
            self.parent, on_recover, on_discard
        )

    def start_work(self, work_type: str, data: Dict = None):
        """작업 시작"""
        self.recovery.start_work(work_type, data or {})
        if self.progress:
            self.progress.start()

    def update_progress(self, progress: float, status: str = None):
        """진행률 업데이트"""
        self.recovery.update_progress(progress)
        if self.progress:
            self.progress.set_progress(progress, status)

    def complete_work(self, result: Dict = None, message: str = "완료"):
        """작업 완료"""
        self.recovery.complete_work(result)
        if self.progress:
            self.progress.complete(message)

    def fail_work(self, error: str, exception: Exception = None):
        """작업 실패"""
        self.recovery.fail_work(error)
        if self.progress:
            self.progress.stop()
        self.show_error(error, exception)

    def _find_latest_log(self) -> Optional[str]:
        """최신 로그 파일 찾기"""
        if not os.path.exists(self.log_dir):
            return None

        logs = [os.path.join(self.log_dir, f)
                for f in os.listdir(self.log_dir) if f.endswith('.log')]

        if not logs:
            return None

        return max(logs, key=os.path.getmtime)


# 테스트
if __name__ == '__main__':
    if HAS_TK:
        root = tk.Tk()
        root.title("UI Helper 테스트")
        root.geometry("400x200")
        root.resizable(True, True)  # v9.0: 크기 조절 허용
        root.minsize(400, 300)  # v9.0: 최소 크기

        # 진행률 바
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)

        label = ttk.Label(frame, text="대기 중...")
        label.pack()

        bar = ttk.Progressbar(frame, length=300)
        bar.pack(pady=10)

        helper = UIOperationsHelper(root, bar, label)

        def test_error():
            try:
                raise ValueError("테스트 에러")
            except (RuntimeError, ValueError) as e:
                helper.show_error("테스트 실패", exception=e)

        def test_progress():
            helper.start_work('test', {})

            def run():
                for i in range(101):
                    helper.update_progress(i/100, f"처리 중... {i}%")
                    time.sleep(0.05)
                helper.complete_work(message="완료!")

            threading.Thread(target=run, daemon=True).start()

        ttk.Button(frame, text="에러 테스트", command=test_error).pack(side='left', padx=5)
        ttk.Button(frame, text="진행률 테스트", command=test_progress).pack(side='left', padx=5)

        root.mainloop()
    else:
        logger.debug("Tkinter 없음")
