"""
SQM v5.9.7 — 스플릿 패널 (마스터-상세)
=======================================
- ttk.PanedWindow 기반 드래그 가능한 스플릿 바
- 접기/펼치기 버튼 지원
- 상단=마스터, 하단=상세(톤백/Allocation 이력)
"""

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)


class MasterDetailSplitPanel(ttk.Frame):
    """
    마스터-상세 스플릿 패널.
    - master_frame: 상단 영역 (메인 테이블)
    - detail_frame: 하단 영역 (선택 행의 상세 테이블)
    - 드래그로 비율 조절, 접기/펼치기 버튼
    """

    def __init__(self, parent, detail_title: str = "상세", master_weight: int = 3,
                 detail_weight: int = 1,
                 master_minsize: int = 0, detail_minsize: int = 0,
                 start_collapsed: bool = True,
                 **kwargs):
        super().__init__(parent, **kwargs)

        self._detail_title = detail_title
        self._master_weight = master_weight
        self._detail_weight = detail_weight
        self._master_minsize = master_minsize
        self._detail_minsize = detail_minsize
        self._detail_collapsed = False
        self._saved_detail_weight = detail_weight
        self._start_collapsed = start_collapsed

        # ttk.PanedWindow (세로: 상단=마스터, 하단=상세)
        self._paned = ttk.PanedWindow(self, orient='vertical')

        # 마스터 영역 컨테이너
        # v6.4.0 FIX: ttk.PanedWindow.add()는 minsize 미지원 (Python 3.14 TclError)
        #             add() 후 pane()으로 별도 설정
        self._master_container = ttk.Frame(self._paned)
        self._paned.add(self._master_container, weight=master_weight)
        if master_minsize > 0:
            try:
                self._paned.pane(self._master_container, minsize=master_minsize)
            except Exception:
                try:
                    if hasattr(self._paned, 'paneconfigure'):
                        self._paned.paneconfigure(self._master_container, minsize=master_minsize)
                except Exception as _e:
                    logger.debug(f"master_minsize 설정 실패(무시): {_e}")

        # 상세 영역: 헤더바(제목+접기버튼) + 본문
        self._detail_wrapper = ttk.Frame(self._paned)
        self._detail_header = ttk.Frame(self._detail_wrapper)
        self._detail_header.pack(fill='x', padx=2, pady=(2, 0))

        self._detail_title_var = tk.StringVar(value=detail_title)
        self._lbl_title = ttk.Label(
            self._detail_header,
            textvariable=self._detail_title_var,
            font=('맑은 고딕', 10, 'bold')
        )
        self._lbl_title.pack(side='left', padx=4, pady=4)

        self._btn_toggle = ttk.Button(
            self._detail_header,
            text="▼ 접기",
            width=8,
            command=self._toggle_detail
        )
        self._btn_toggle.pack(side='right', padx=4, pady=2)

        self._detail_body = ttk.Frame(self._detail_wrapper)
        self._detail_body.pack(fill='both', expand=True)

        # 접힌 상태에서 보여줄 펼치기 바 (버튼이 여기 있어야 접힌 후에도 클릭 가능)
        self._expand_bar = ttk.Frame(self._paned)
        self._btn_expand = ttk.Button(
            self._expand_bar,
            text="▶ 상세 펼치기",
            command=self._toggle_detail
        )
        self._btn_expand.pack(padx=8, pady=6)

        self._paned.add(self._detail_wrapper, weight=detail_weight)
        if detail_minsize > 0:
            try:
                self._paned.pane(self._detail_wrapper, minsize=detail_minsize)
            except Exception as _e:
                logger.debug(f"detail_minsize 설정 실패(무시): {_e}")

        self._paned.pack(fill='both', expand=True)

        # v8.1.3 UI-5: 기본 접힘
        if self._start_collapsed:
            self.after(100, self._collapse_detail)

    def _collapse_detail(self):
        """상세 패널을 접힌 상태로 전환"""
        if not self._detail_collapsed:
            self._toggle_detail()

    def get_master_container(self) -> ttk.Frame:
        """마스터 영역에 위젯을 넣을 프레임 반환"""
        return self._master_container

    def get_detail_container(self) -> ttk.Frame:
        """상세 영역 본문에 위젯을 넣을 프레임 반환"""
        return self._detail_body

    def set_detail_title(self, title: str) -> None:
        """상세 패널 제목 설정"""
        self._detail_title_var.set(title)

    def _toggle_detail(self) -> None:
        """상세 패널 접기/펼치기"""
        try:
            if self._detail_collapsed:
                self._paned.remove(self._expand_bar)
                self._paned.add(self._detail_wrapper, weight=self._saved_detail_weight)
                self._btn_toggle.config(text="▼ 접기")
                self._detail_collapsed = False
            else:
                self._saved_detail_weight = self._detail_weight
                self._paned.remove(self._detail_wrapper)
                self._paned.add(self._expand_bar, weight=0)
                self._detail_collapsed = True
        except tk.TclError as e:
            logger.debug(f"스플릿 토글: {e}")

    def is_detail_collapsed(self) -> bool:
        return self._detail_collapsed
