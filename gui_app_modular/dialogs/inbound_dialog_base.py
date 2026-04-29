"""
SQM v4.0.1 — 입고 다이얼로그 공통 베이스
==========================================

onestop_inbound.py 공통 코드 추출 (v5.6.7: inbound_preview 제거됨):
- _empty_row: 빈 행 생성
- _log_safe: 안전 로그
- _update_progress: 프로그레스 바 갱신
- _on_cancel: 취소 처리
"""

import logging

logger = logging.getLogger(__name__)


class InboundDialogBase:
    """입고 다이얼로그 공통 기능"""

    def _empty_row(self, col_count: int = None) -> tuple:
        """빈 행 생성 (트리뷰용)"""
        n = col_count or len(getattr(self, '_columns', []))
        if n <= 0:
            n = 18
        return tuple([''] * n)

    def _log_safe(self, msg: str) -> None:
        """안전한 로그 출력 (위젯 파괴 후에도 안전)"""
        try:
            if hasattr(self, 'log_text') and self.log_text and self.log_text.winfo_exists():
                self.log_text.configure(state='normal')
                self.log_text.insert('end', msg + '\n')
                self.log_text.see('end')
                self.log_text.configure(state='disabled')
        except (RuntimeError, ValueError) as _e:
            logger.debug(f'Suppressed: {_e}')
        logger.info(msg)

    def _update_progress(self, current: int, total: int, msg: str = '') -> None:
        """프로그레스 바 업데이트"""
        try:
            if hasattr(self, 'progress') and self.progress:
                pct = int((current / max(total, 1)) * 100)
                self.progress['value'] = pct
            if hasattr(self, 'progress_label') and self.progress_label:
                label_text = f"{current}/{total}"
                if msg:
                    label_text += f" - {msg}"
                self.progress_label.configure(text=label_text)
        except (ValueError, TypeError, KeyError) as _e:
            logger.debug(f'Suppressed: {_e}')

    def _on_cancel(self) -> None:
        """취소 버튼 처리"""
        try:
            if hasattr(self, 'dialog') and self.dialog:
                self.dialog.destroy()
        except (ValueError, TypeError, KeyError) as _e:
            logger.debug(f'Suppressed: {_e}')
