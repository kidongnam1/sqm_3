
# ╔══════════════════════════════════════════════════════════════╗
# ║  전체 색상 사용 가이드 (v3.8.0)                             ║
# ╠══════════════════════════════════════════════════════════════╣
# ║  어디서든: from gui_app_modular.utils.ui_constants import tc ║
# ║                                                              ║
# ║  widget.config(fg=tc('text_primary'), bg=tc('bg_primary'))   ║
# ║                                                              ║
# ║  테마 전환 시 자동으로 LIGHT/DARK 팔레트에서 색상 반환       ║
# ║  하드코딩 색상(fg='white', bg='#1a1a1a') 사용 절대 금지      ║
# ╚══════════════════════════════════════════════════════════════╝
"""
SQM Inventory v3.5 - UI 통일성 상수 및 계산기
=============================================

UI 가시성 및 통일성을 위한 중앙 집중식 설정

사용법:
    from gui_app_modular.utils.ui_constants import (
        UICalculator, FontScale, Spacing, ColumnWidth,
        ThemeColors, DialogSize, center_dialog
    )
"""

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 화물(톤백) 상태 표시명 — v7.2.0: OUTBOUND/RETURN 신규 상태 추가
STATUS_DISPLAY = {
    'AVAILABLE': '판매가능',
    'RESERVED': '판매배정',
    'PICKED': '판매화물 결정',
    'OUTBOUND': '출고완료',    # v7.2.0 신규
    'SOLD': '출고완료',        # 하위호환 (OUTBOUND와 동일 표시)
    'RETURN': '반품대기',      # v7.2.0 신규: 반품 입고 후 location 지정 전
    'SHIPPED': '선적',
    'DEPLETED': '소진',
    'RETURNED': '반품',
    'PARTIAL': '부분출고',
}

# 한글 표시명 → DB 값 (필터·다이얼로그 저장 시 사용)
STATUS_DISPLAY_TO_DB = {v: k for k, v in STATUS_DISPLAY.items()}


def get_status_display(status: str) -> str:
    """DB 상태값 → 화면 표시명. 없으면 원문 반환."""
    if not status:
        return ''
    return STATUS_DISPLAY.get(str(status).strip().upper(), str(status))


# ═══════════════════════════════════════════════════════════════
# Excel/데이터 입력 원칙 — 전체 프로그램 통일 (AGENTS.md Upload Principle)
# ═══════════════════════════════════════════════════════════════
# 형식은 프로그램 내장 → 사용자는 [데이터 붙여넣기] 또는 [파일 업로드] 중 하나 선택
UPLOAD_CHOICE_HEADER = "프로그램이 정한 형식은 내장되어 있습니다. 다음 중 하나를 선택하세요."
UPLOAD_CHOICE_PASTE = "① 데이터 붙여넣기: 프로그램 화면에 표가 열립니다. Excel 등에서 복사한 데이터를 붙여넣기(Ctrl+V) 한 뒤 반영합니다."
UPLOAD_CHOICE_UPLOAD = "② 파일 업로드: 이미 채운 엑셀 파일을 선택하여 업로드합니다."
UPLOAD_CHOICE_BTN_PASTE = "📋 데이터 붙여넣기"
UPLOAD_CHOICE_BTN_UPLOAD = "📤 파일 업로드"


# ═══════════════════════════════════════════════════════════════
# 1. 화면 해상도 기반 크기 계산
# ═══════════════════════════════════════════════════════════════

class UICalculator:
    """
    화면 해상도 및 DPI 기반 UI 크기 계산기
    
    사용법:
        calc = UICalculator(root)
        width = calc.scaled(100)  # DPI에 맞게 스케일링된 값
    """

    # 기준 해상도 (Full HD)
    BASE_WIDTH = 1920
    BASE_HEIGHT = 1080
    BASE_DPI = 96

    def __init__(self, root=None):
        if root:
            self.screen_width = root.winfo_screenwidth()
            self.screen_height = root.winfo_screenheight()
            try:
                self.dpi = root.winfo_fpixels('1i')
            except (RuntimeError, ValueError):
                self.dpi = self.BASE_DPI
        else:
            # 기본값
            self.screen_width = self.BASE_WIDTH
            self.screen_height = self.BASE_HEIGHT
            self.dpi = self.BASE_DPI

    @property
    def scale_factor(self) -> float:
        """화면 크기 기반 스케일 팩터"""
        width_scale = self.screen_width / self.BASE_WIDTH
        height_scale = self.screen_height / self.BASE_HEIGHT
        return min(width_scale, height_scale)

    @property
    def dpi_scale(self) -> float:
        """DPI 기반 스케일 팩터"""
        return self.dpi / self.BASE_DPI

    @property
    def combined_scale(self) -> float:
        """통합 스케일 팩터"""
        return max(1.0, self.dpi_scale)  # 최소 1.0 보장

    def scaled(self, value: int) -> int:
        """값을 DPI에 맞게 스케일링"""
        return int(value * self.combined_scale)

    def get_main_window_size(self) -> Tuple[int, int]:
        """메인 윈도우 권장 크기"""
        width = int(self.screen_width * 0.75)
        height = int(self.screen_height * 0.80)

        # 최소/최대 제한
        width = max(1000, min(width, 1800))
        height = max(700, min(height, 1200))

        return width, height

    def get_min_window_size(self) -> Tuple[int, int]:
        """최소 윈도우 크기"""
        return (
            max(1000, int(self.screen_width * 0.5)),
            max(700, int(self.screen_height * 0.5))
        )


# ═══════════════════════════════════════════════════════════════
# 2. 폰트 스케일링
# ═══════════════════════════════════════════════════════════════

class FontStyle(Enum):
    """폰트 스타일 열거형"""
    TITLE = 'title'
    SUBTITLE = 'subtitle'
    HEADING = 'heading'
    BODY = 'body'
    SMALL = 'small'
    TINY = 'tiny'
    MONO = 'mono'


class FontScale:
    """
    DPI 인식 폰트 크기 관리
    
    사용법:
        fonts = FontScale(dpi=120)
        title_font = fonts.get_font(FontStyle.TITLE, 'bold')
        # ('맑은 고딕', 20, 'bold')
    """

    # 기준 폰트 크기 (96 DPI 기준) — v3.8.7: 30% 확대
    BASE_SIZES = {
        FontStyle.TITLE:    21,   # 16 → 21
        FontStyle.SUBTITLE: 18,   # 14 → 18
        FontStyle.HEADING:  16,   # 12 → 16
        FontStyle.BODY:     13,   # 10 → 13
        FontStyle.SMALL:    12,   #  9 → 12
        FontStyle.TINY:     10,   #  8 → 10
        FontStyle.MONO:     13,   # 10 → 13
    }

    # 폰트 패밀리
    FONT_FAMILY = '맑은 고딕'
    MONO_FAMILY = 'Consolas'

    def __init__(self, dpi: float = 96):
        self.dpi = dpi
        self.scale = max(1.0, dpi / 96)

    def get_size(self, style: FontStyle) -> int:
        """스케일링된 폰트 크기 반환"""
        base = self.BASE_SIZES.get(style, 10)
        scaled = int(base * self.scale)
        return max(scaled, 8)  # 최소 8pt

    def get_font(self, style: FontStyle, weight: str = 'normal') -> Tuple[str, int, str]:
        """tkinter 폰트 튜플 반환"""
        size = self.get_size(style)
        family = self.MONO_FAMILY if style == FontStyle.MONO else self.FONT_FAMILY
        return (family, size, weight)

    # 편의 메서드
    def title(self, bold: bool = True) -> Tuple[str, int, str]:
        return self.get_font(FontStyle.TITLE, 'bold' if bold else 'normal')

    def subtitle(self, bold: bool = False) -> Tuple[str, int, str]:
        return self.get_font(FontStyle.SUBTITLE, 'bold' if bold else 'normal')

    def heading(self, bold: bool = True) -> Tuple[str, int, str]:
        return self.get_font(FontStyle.HEADING, 'bold' if bold else 'normal')

    def body(self, bold: bool = False) -> Tuple[str, int, str]:
        return self.get_font(FontStyle.BODY, 'bold' if bold else 'normal')

    def small(self) -> Tuple[str, int, str]:
        return self.get_font(FontStyle.SMALL)

    def mono(self) -> Tuple[str, int, str]:
        return self.get_font(FontStyle.MONO)


# ═══════════════════════════════════════════════════════════════
# 3. 간격 시스템 (8px 그리드)
# ═══════════════════════════════════════════════════════════════

class Spacing:
    """
    8px 그리드 기반 간격 시스템
    
    사용법:
        frame = ttk.Frame(parent, padding=Spacing.MD)
        btn.pack(padx=Spacing.SM, pady=Spacing.XS)
    """

    # 기본 단위
    UNIT = 8

    # 스케일
    XS = UNIT // 2      # 4px
    SM = UNIT           # 8px
    MD = UNIT * 2       # 16px
    LG = UNIT * 3       # 24px
    XL = UNIT * 4       # 32px
    XXL = UNIT * 6      # 48px

    # 용도별 권장값
    class Padding:
        DIALOG = 20         # v8.6.4: 16→20 다이얼로그 내부
        FRAME = 12          # v8.6.4: 8→12 일반 프레임
        LABELFRAME = 20     # v8.6.4: 16→20 LabelFrame 내부
        BUTTON_GROUP = 10   # v8.6.4: 8→10 버튼 사이
        SECTION = 28        # v8.6.4: 24→28 섹션 사이

    # ── v8.1.8: 탭 레이아웃 표준 상수 ──────────────────────────────
    # 모든 탭에 동일하게 적용하여 시각적 일관성 확보
    class Tab:
        """탭 내부 레이아웃 표준값 (Grid 기반). v8.6.4: 여백 대폭 확대."""
        # 탭 전체 가로 패딩
        OUTER_PADX   = 24       # v8.6.4: 6→24 (넉넉한 좌우 여백)
        # 헤더 (make_tab_header)
        HEADER_H     = 44       # v8.6.4: 38→44
        HEADER_PADY  = (8, 12)  # v8.6.4: (0,4)→(8,12) 헤더 상하 여백
        # 버튼바
        BTN_BAR_PADX = (24, 24) # v8.6.4: (6,6)→(24,24)
        BTN_BAR_PADY = (6, 10)  # v8.6.4: (0,4)→(6,10)
        BTN_GAP      = 8        # v8.6.4: 4→8 버튼 사이 간격
        # 필터/검색바 (버튼바 아래)
        FILTER_PADY  = (6, 10)  # v8.6.4: (0,4)→(6,10)
        # 트리뷰 컨테이너
        TREE_PADX    = (24, 24) # v8.6.4: (6,6)→(24,24)
        TREE_PADY    = (6, 16)  # v8.6.4: (0,6)→(6,16)
        # 트리뷰 최소 행 수 — expand=True로 나머지 공간 채움
        TREE_MIN_H   = 15



# ═══════════════════════════════════════════════════════════════
# 4. 다이얼로그 크기
# ═══════════════════════════════════════════════════════════════

@dataclass
class DialogSizeConfig:
    """다이얼로그 크기 설정"""
    width_ratio: float
    height_ratio: float
    min_size: Tuple[int, int]
    max_size: Tuple[int, int]


class DialogSize:
    """
    다이얼로그 크기 계산
    
    사용법:
        width, height = DialogSize.calculate(parent, 'medium')
    """

    CONFIGS = {
        'small': DialogSizeConfig(0.25, 0.20, (350, 200), (500, 350)),
        'medium': DialogSizeConfig(0.40, 0.50, (500, 400), (800, 600)),
        'large': DialogSizeConfig(0.60, 0.70, (700, 500), (1200, 900)),
        'full': DialogSizeConfig(0.85, 0.85, (1000, 700), (1600, 1000)),
    }

    @classmethod
    def calculate(cls, parent, size_type: str = 'medium') -> Tuple[int, int]:
        """부모 창 기준 다이얼로그 크기 계산"""
        config = cls.CONFIGS.get(size_type, cls.CONFIGS['medium'])

        try:
            parent_width = parent.winfo_width()
            parent_height = parent.winfo_height()
        except (RuntimeError, ValueError):
            parent_width = 1200
            parent_height = 800

        width = int(parent_width * config.width_ratio)
        height = int(parent_height * config.height_ratio)

        # 최소/최대 제한
        width = max(config.min_size[0], min(width, config.max_size[0]))
        height = max(config.min_size[1], min(height, config.max_size[1]))

        return width, height

    @classmethod
    def get_geometry(cls, parent, size_type: str = 'medium') -> str:
        """geometry 문자열 반환"""
        width, height = cls.calculate(parent, size_type)
        return f"{width}x{height}"


# ═══════════════════════════════════════════════════════════════
# 5. 컬럼 너비 계산
# ═══════════════════════════════════════════════════════════════

class ColumnWidth:
    """
    테이블 컬럼 너비 계산
    
    사용법:
        width = ColumnWidth.get('lot_no')
        anchor = ColumnWidth.get_anchor('weight')
    """

    # 문자 타입별 평균 너비 (픽셀)
    CHAR_WIDTH = {
        'number': 8,
        'letter': 7,
        'korean': 14,
        'mixed': 10,
    }

    # 필드별 설정
    SPECS = {
        'lot_no': {'type': 'mixed', 'chars': 15, 'min': 120, 'max': 150, 'anchor': 'center'},
        'sap_no': {'type': 'number', 'chars': 12, 'min': 100, 'max': 130, 'anchor': 'center'},
        'bl_no': {'type': 'mixed', 'chars': 12, 'min': 100, 'max': 130, 'anchor': 'center'},
        'weight': {'type': 'number', 'chars': 10, 'min': 80, 'max': 110, 'anchor': 'e'},
        'quantity': {'type': 'number', 'chars': 5, 'min': 50, 'max': 80, 'anchor': 'center'},
        'product': {'type': 'korean', 'chars': 12, 'min': 100, 'max': 200, 'anchor': 'center'},
        'customer': {'type': 'korean', 'chars': 15, 'min': 120, 'max': 250, 'anchor': 'center'},
        'date': {'type': 'number', 'chars': 10, 'min': 85, 'max': 100, 'anchor': 'center'},
        'status': {'type': 'letter', 'chars': 10, 'min': 70, 'max': 100, 'anchor': 'center'},
        'sub_lt': {'type': 'number', 'chars': 3, 'min': 50, 'max': 70, 'anchor': 'center'},
        'location': {'type': 'mixed', 'chars': 8, 'min': 60, 'max': 100, 'anchor': 'center'},
    }

    @classmethod
    def get(cls, field: str, font_size: int = 10) -> int:
        """필드별 권장 너비 계산"""
        spec = cls.SPECS.get(field)
        if not spec:
            return 100

        font_scale = font_size / 10
        char_width = cls.CHAR_WIDTH[spec['type']] * font_scale
        width = int(spec['chars'] * char_width) + 20

        return max(spec['min'], min(width, spec['max']))

    @classmethod
    def get_anchor(cls, field: str) -> str:
        """필드별 정렬 방향"""
        spec = cls.SPECS.get(field, {})
        return spec.get('anchor', 'center')

    @classmethod
    def configure_column(cls, tree, field: str, heading: str, font_size: int = 10):
        """트리뷰 컬럼 설정"""
        width = cls.get(field, font_size)
        anchor = cls.get_anchor(field)
        tree.heading(field, text=heading, anchor='center')
        tree.column(field, width=width, anchor=anchor)


# ═══════════════════════════════════════════════════════════════
# 6. 테마 인식 색상
# ═══════════════════════════════════════════════════════════════

class ThemeColors:
    """
    다크모드 대응 색상 시스템 (v3.6.2: 가독성 대폭 개선)
    
    사용법:
        color = ThemeColors.get('available', is_dark=True)
    """

    LIGHT = {
    # ── v8.6.4 Pro Light — 딥 네이비 × 아이스 화이트 ──────────────────
    # 설계: Bloomberg / SAP Fiori Light — 차분하고 고급진 Business 팔레트
    # 원칙: 툴바/사이드바는 딥 네이비 유지, 콘텐츠는 쿨 아이스 화이트

    # ── Semantic ──────────────────────────────────────────────────────
    'success': '#147848',    # 딥 에메랄드
    'warning': '#a86020',    # 딥 앰버
    'danger':  '#b83030',    # 딥 레드
    'info':    '#1060a8',    # 딥 사파이어
    'primary': '#162040',    # 딥 네이비

    # ── Status 행 배경 ────────────────────────────────────────────────
    'available': '#e4f4ec',  # 소프트 민트
    'picked':    '#ede8f8',  # 소프트 라벤더
    'reserved':  '#faf0e0',  # 소프트 크림
    'shipped':   '#e0eef8',  # 소프트 스카이

    # ── Text ──────────────────────────────────────────────────────────
    'text_on_dark':   '#ffffff',
    'text_primary':   '#162040',
    'text_secondary': '#3d5878',
    'text_muted':     '#7898b8',
    'accent':         '#1460c8',
    'accent_light':   '#4080e0',

    # ── Background ────────────────────────────────────────────────────
    'bg_primary':   '#f0f5fc',   # 쿨 아이스 화이트
    'bg_secondary': '#e4edf8',   # 페일 블루
    'bg_hover':     '#d0dff0',
    'bg_toolbar':   '#162040',   # 딥 네이비
    'bg_card':      '#ffffff',

    # ── Border ────────────────────────────────────────────────────────
    'border':       '#bdd0ea',
    'border_focus': '#1460c8',

    # ── Buttons ───────────────────────────────────────────────────────
    'btn_inbound':        '#147848',
    'btn_inbound_hover':  '#189858',
    'btn_outbound':       '#a86020',
    'btn_outbound_hover': '#c87828',
    'btn_report':         '#1840a0',
    'btn_report_hover':   '#2050c0',
    'btn_neutral':        '#405878',
    'btn_neutral_hover':  '#506888',

    # ── Treeview ──────────────────────────────────────────────────────
    'tree_select_bg':  '#c0d4f0',
    'tree_select_fg':  '#0a1830',
    'tree_stripe':     '#f5f9ff',

    # ── Charts ────────────────────────────────────────────────────────
    'chart_bg':   '#ffffff',
    'chart_grid': '#e4edf8',

    # ── Search bar ────────────────────────────────────────────────────
    'search_bg':          '#ffffff',
    'search_fg':          '#162040',
    'search_border':      '#bdd0ea',
    'search_placeholder': '#7898b8',
    'search_cursor':      '#1460c8',

    # ── Status bar ────────────────────────────────────────────────────
    'statusbar_bg':            '#162040',
    'statusbar_fg':            '#8aaac8',
    'statusbar_icon_ok':       '#147848',
    'statusbar_icon_warn':     '#a86020',
    'statusbar_icon_err':      '#b83030',
    'statusbar_progress':      '#1460c8',
    'statusbar_progress_done': '#147848',
    'statusbar_track':         '#1e2e58',

    # ── Badges ────────────────────────────────────────────────────────
    'badge_db':      '#1060a8',
    'badge_version': '#1840a0',
    'badge_text':    '#ffffff',

    # ── Misc ──────────────────────────────────────────────────────────
    'arrow_separator':    '#bdd0ea',
    'shortcut_text':      '#7898b8',
    'shortcut_text_dim':  '#a0b8d0',
    'canvas_highlight':   '#1460c8',
}

    DARK = {
    # ── v8.6.4 Pro Dark — 딥 미드나잇 × 스틸 블루 ────────────────────
    # 설계: Bloomberg Terminal 수준 — 눈 편안한 딥 네이비 기반
    # 원칙:
    #   1) 배경: 딥 미드나잇 블루 (#0b1322) — 따뜻한 네이비 느낌
    #   2) 강조: 스카이 블루 (#38bdf8) — 눈부심 없는 소프트 시안
    #   3) 레이어: 4단계 (07101e → 0b1322 → 101c34 → 13203c)
    #   4) 카드 색: Muted Pastel — 채도 낮춰 고급스럽게

    # ── Semantic ──────────────────────────────────────────────────────
    'success': '#52c87e',    # 소프트 에메랄드
    'warning': '#e8943a',    # 소프트 테라코타
    'danger':  '#e06868',    # 소프트 레드
    'info':    '#4ab0e8',    # 소프트 스카이
    'primary': '#38bdf8',    # 스카이 블루

    # ── Status 행 배경 ────────────────────────────────────────────────
    'available': '#0d2018',  # 딥 그린 틴트
    'picked':    '#18102e',  # 딥 퍼플 틴트
    'reserved':  '#1e1608',  # 딥 앰버 틴트
    'shipped':   '#0a1826',  # 딥 블루 틴트

    # ── Text ──────────────────────────────────────────────────────────
    'text_on_dark':   '#ffffff',
    'text_primary':   '#dce8fa',   # 눈부심 없는 블루-화이트
    'text_secondary': '#6e92be',   # 스틸 블루
    'text_muted':     '#8098b8',   # 스틸 블루 (v8.6.5: 대비 강화 #364e6e→#8098b8)
    'accent':         '#38bdf8',   # 스카이 블루
    'accent_light':   '#7dd4fa',

    # ── Background (4단계 깊이) ───────────────────────────────────────
    'bg_primary':   '#0b1322',   # 앱 본문
    'bg_secondary': '#101c34',   # 패널
    'bg_hover':     '#182840',   # 호버
    'bg_toolbar':   '#07101e',   # 툴바
    'bg_card':      '#13203c',   # 카드

    # ── Border ────────────────────────────────────────────────────────
    'border':       '#1c3358',
    'border_focus': '#38bdf8',

    # ── Buttons ───────────────────────────────────────────────────────
    'btn_inbound':        '#1a6e40',
    'btn_inbound_hover':  '#228850',
    'btn_outbound':       '#8a5a10',
    'btn_outbound_hover': '#aa7018',
    'btn_report':         '#183898',
    'btn_report_hover':   '#2048b8',
    'btn_neutral':        '#2c4060',
    'btn_neutral_hover':  '#384e78',

    # ── Treeview ──────────────────────────────────────────────────────
    'tree_select_bg':  '#102e58',
    'tree_select_fg':  '#dce8fa',
    'tree_stripe':     '#101c34',

    # ── Charts ────────────────────────────────────────────────────────
    'chart_bg':   '#0b1322',
    'chart_grid': '#1c3358',

    # ── Search bar ────────────────────────────────────────────────────
    'search_bg':          '#13203c',
    'search_fg':          '#dce8fa',
    'search_border':      '#1c3358',
    'search_placeholder': '#6888a8',  # v8.6.5: 대비 강화 (#364e6e→#6888a8)
    'search_cursor':      '#38bdf8',

    # ── Status bar ────────────────────────────────────────────────────
    'statusbar_bg':            '#07101e',
    'statusbar_fg':            '#6e92be',
    'statusbar_icon_ok':       '#52c87e',
    'statusbar_icon_warn':     '#e8943a',
    'statusbar_icon_err':      '#e06868',
    'statusbar_progress':      '#38bdf8',
    'statusbar_progress_done': '#52c87e',
    'statusbar_track':         '#1c3358',

    # ── Badges ────────────────────────────────────────────────────────
    'badge_db':      '#0e5878',
    'badge_version': '#183898',
    'badge_text':    '#ffffff',

    # ── Misc ──────────────────────────────────────────────────────────
    'arrow_separator':   '#1c3358',
    'shortcut_text':     '#6e92be',
    'shortcut_text_dim': '#364e6e',
    'canvas_highlight':  '#38bdf8',
}








    @classmethod
    def is_dark_theme(cls, theme_name: str) -> bool:
        """다크 테마 여부 확인"""
        # v8.6.4: 다크 테마 목록 확장 (PRO DARK 계열 포함)
        _DARK_SET = {
            'darkly', 'cyborg', 'superhero', 'solar', 'vapor',
            'dark', 'pro_dark', 'sqm_dark', 'slate',
            'monokai', 'night', 'dim',
        }
        return theme_name.lower() in _DARK_SET or \
               'dark' in theme_name.lower()

    @classmethod
    def get(cls, key: str, is_dark: bool = False) -> str:
        """현재 테마에 맞는 색상 반환"""
        palette = cls.DARK if is_dark else cls.LIGHT
        return palette.get(key, '#000000')

    @classmethod
    def get_palette(cls, is_dark: bool = False) -> dict:
        """전체 팔레트 반환"""
        return cls.DARK.copy() if is_dark else cls.LIGHT.copy()

    # v8.1.3: 상태 배지 pill 색상 (UI-4)
    STATUS_BADGE = {
        # v8.3.3 Pro Dark: Tailwind 시맨틱 컬러 시스템
        # bg_dark = 행 배경 (Treeview tag), fg_dark = 텍스트/뱃지 글자
        'AVAILABLE': {'bg_light': '#EAF3DE', 'fg_light': '#166534', 'bg_dark': '#052e16', 'fg_dark': '#4ade80'},
        'RESERVED':  {'bg_light': '#EFF6FF', 'fg_light': '#1e40af', 'bg_dark': '#1e1b4b', 'fg_dark': '#a5b4fc'},
        'PICKED':    {'bg_light': '#FFFBEB', 'fg_light': '#92400e', 'bg_dark': '#1c1917', 'fg_dark': '#fcd34d'},
        'OUTBOUND':  {'bg_light': '#F8FAFC', 'fg_light': '#475569', 'bg_dark': '#1e293b', 'fg_dark': '#94a3b8'},
        'RETURN':    {'bg_light': '#FEF2F2', 'fg_light': '#991b1b', 'bg_dark': '#1f0a0a', 'fg_dark': '#fca5a5'},
    }

    @classmethod
    def configure_tags(cls, tree, is_dark: bool = False):
        """트리뷰 상태 태그 설정 (v8.1.3: 상태 배지 pill 색상)"""
        p = cls.DARK if is_dark else cls.LIGHT
        fg = '#f0f0f0' if is_dark else '#1a1a1a'

        # v8.1.3: 배지 색상으로 통일
        for status, colors in cls.STATUS_BADGE.items():
            tag_name = status.lower()
            bg_key = 'bg_dark' if is_dark else 'bg_light'
            fg_key = 'fg_dark' if is_dark else 'fg_light'
            tree.tag_configure(tag_name, background=colors[bg_key], foreground=colors[fg_key])

        # 하위호환: shipped = outbound 색상
        ob = cls.STATUS_BADGE['OUTBOUND']
        tree.tag_configure('shipped',
                          background=ob['bg_dark' if is_dark else 'bg_light'],
                          foreground=ob['fg_dark' if is_dark else 'fg_light'])
        # sold = outbound 하위호환
        tree.tag_configure('sold',
                          background=ob['bg_dark' if is_dark else 'bg_light'],
                          foreground=ob['fg_dark' if is_dark else 'fg_light'])
        # v8.6.5: depleted 대비 강화 (기존 #aaa/#f0f0f0 → 읽기 불가)
        tree.tag_configure('depleted',
                          background='#e8e8e8' if not is_dark else '#1a1a2e',
                          foreground='#666666' if not is_dark else '#9a9ab0')
        tree.tag_configure('stripe', background=p['tree_stripe'], foreground=fg)


# ═══════════════════════════════════════════════════════════════
# 전역 테마 싱글턴 (v9.0 신규)
# 모든 파일이 getattr(self.app, 'current_theme', 'darkly') 대신
# is_dark() / set_global_theme() 을 사용
# ═══════════════════════════════════════════════════════════════
# v8.1.8 BUG-THEME 수정:
#   기본값을 cosmo(light, False)로 두면 테마 로드 전에 tc()를 쓰는
#   위젯들이 잘못된 색상으로 생성되는 문제가 있었음.
#   _load_theme_preference() 기본값이 'cosmo'이므로 False가 맞지만,
#   실제 앱 기동 시 set_global_theme()이 _init_state()에서 즉시 호출되므로
#   초기값 자체의 영향은 최소화됨. 그러나 혹시 import 순서 문제로
#   set_global_theme()이 늦게 호출될 경우를 대비해 darkly(True) 유지.
_GLOBAL_IS_DARK: bool = True   # v8.1.8: darkly 기본 (set_global_theme로 즉시 갱신됨)
_GLOBAL_THEME:   str  = 'darkly'


def set_global_theme(theme_name: str) -> None:
    """앱 테마 변경 시 호출 — 전역 상태 갱신."""
    global _GLOBAL_IS_DARK, _GLOBAL_THEME
    _GLOBAL_THEME   = str(theme_name or 'darkly')  # v8.6.4: 기본 darkly
    _GLOBAL_IS_DARK = ThemeColors.is_dark_theme(_GLOBAL_THEME)



# ══════════════════════════════════════════════════════════════
# v3.8.0: tc() — 테마 자동 대응 색상 편의 함수
# ══════════════════════════════════════════════════════════════
# 사용법:
#   from gui_app_modular.utils.ui_constants import tc
#   label.config(fg=tc('text_primary'), bg=tc('bg_primary'))
#
# 이 함수 하나로 라이트/다크 모드 자동 전환됩니다.
# 하드코딩 색상(fg='white', bg='#1a1a1a')을 절대 사용하지 마세요.
# ══════════════════════════════════════════════════════════════

def tc(key: str, dark: bool = None) -> str:
    """테마 자동 대응 색상 반환.

    Args:
        key:  ThemeColors.LIGHT/DARK 딕셔너리 키
        dark: None → is_dark() 자동 사용, True/False → 직접 지정

    Returns:
        해당 테마의 색상 hex 문자열

    예시:
        label.config(fg=tc('text_primary'))
        frame.config(bg=tc('bg_primary'))
        entry.config(fg=tc('text_primary'), bg=tc('bg_card'),
                     insertbackground=tc('text_primary'))
    """
    _dark = _GLOBAL_IS_DARK if dark is None else dark
    palette = ThemeColors.DARK if _dark else ThemeColors.LIGHT
    color   = palette.get(key)
    if color is None:
        # 공통 키 폴백
        _fallback = {
            'text_primary':   '#dce8fa' if _dark else '#162040',
            'text_secondary': '#6e92be' if _dark else '#3d5878',
            'text_muted':     '#364e6e' if _dark else '#7898b8',
            'text_on_dark':   '#ffffff',
            'text_on_light':  '#1a2744',
            'bg_primary':     '#0b1322' if _dark else '#f0f5fc',
            'bg_secondary':   '#101c34' if _dark else '#e4edf8',
            'bg_card':        '#13203c' if _dark else '#ffffff',
            'bg_entry':       '#1a2a3a' if _dark else '#ffffff',
            'border':         '#1a3a5c' if _dark else '#dce1e5',
            'select_bg':      '#1a3a5c' if _dark else '#d6eaf8',
            'select_fg':      '#FF8C00' if _dark else '#1a5276',
        }
        color = _fallback.get(key, '#888888')
    return color


def tc_pair(key_fg: str, key_bg: str, dark: bool = None) -> tuple:
    """fg, bg 쌍 반환.

    예시:
        fg, bg = tc_pair('text_primary', 'bg_primary')
        widget.config(fg=fg, bg=bg)
    """
    return tc(key_fg, dark), tc(key_bg, dark)


def apply_theme_to_widget(widget, fg_key: str = 'text_primary',
                           bg_key: str = 'bg_primary') -> None:
    """tkinter 위젯에 테마 색상 즉시 적용.

    예시:
        apply_theme_to_widget(my_label)
        apply_theme_to_widget(my_frame, fg_key='text_secondary', bg_key='bg_card')
    """
    try:
        widget.config(fg=tc(fg_key), bg=tc(bg_key))
    except Exception as e:
        logger.warning(f"[UI] apply_theme_to_widget fg/bg config: {e}")  # noqa
        try:
            widget.config(background=tc(bg_key))
        except Exception as e:
            logger.warning(f"[UI] apply_theme_to_widget background fallback config: {e}")  # noqa


def apply_theme_recursive(widget) -> None:
    """위젯과 모든 자식 위젯에 테마 색상 재귀 적용.
    테마 전환 후 호출하면 모든 tk.Widget 색상 갱신.
    """
    import tkinter as tk
    _dark = _GLOBAL_IS_DARK
    fg = tc('text_primary')
    bg = tc('bg_primary')

    try:
        wclass = widget.winfo_class()
        if wclass in ('Label', 'Button', 'Checkbutton', 'Radiobutton',
                       'Message', 'Scale', 'Scrollbar'):
            widget.config(fg=fg, bg=bg)
        elif wclass in ('Frame', 'LabelFrame', 'Canvas', 'Toplevel'):
            widget.config(bg=bg)
        elif wclass == 'Entry':
            widget.config(fg=fg, bg=tc('bg_entry'),
                          insertbackground=fg,
                          selectforeground=tc('select_fg'),
                          selectbackground=tc('select_bg'))
        elif wclass == 'Text':
            widget.config(fg=fg, bg=tc('bg_card'),
                          insertbackground=fg,
                          selectforeground=tc('select_fg'),
                          selectbackground=tc('select_bg'))
        elif wclass == 'Listbox':
            widget.config(fg=fg, bg=tc('bg_card'),
                          selectforeground=tc('select_fg'),
                          selectbackground=tc('select_bg'))
    except Exception as e:
        logger.warning(f"[UI] apply_theme_recursive widget config by class: {e}")  # noqa

    # 재귀 자식 순회
    try:
        for child in widget.winfo_children():
            apply_theme_recursive(child)
    except Exception as e:
        logger.warning(f"[UI] apply_theme_recursive iterating child widgets: {e}")  # noqa


def is_dark() -> bool:
    """현재 다크테마 여부 — 어디서든 호출 가능."""
    return _GLOBAL_IS_DARK


def get_global_theme() -> str:
    """현재 테마 이름 반환."""
    return _GLOBAL_THEME


# ═══════════════════════════════════════════════════════════════
# 6-2. 글로벌 가독성 스타일 (v3.6.2 신규)
# ═══════════════════════════════════════════════════════════════

class ReadableStyle:
    """
    v3.6.2: 전체 앱에 가독성 좋은 스타일을 일괄 적용
    
    - Treeview: 행 높이 28→32px, 교대 줄무늬, 부드러운 선택색
    - Notebook 탭: 패딩 확대, 폰트 개선
    - LabelFrame: 테두리 부드러운 색상
    - Entry/Combobox: 패딩, 포커스 색상
    
    사용법:
        from gui_app_modular.utils.ui_constants import ReadableStyle
        ReadableStyle.apply(root, theme_name='darkly')
    """

    # Treeview 행 높이 (v8.7.0 Phase1: 36px로 가독성 개선)
    ROW_HEIGHT = 40  # v8.6.4: 36→40 (행 간격 여유)

    # 기본 폰트 — v3.8.7: 30% 확대
    FONT_FAMILY = '맑은 고딕'
    FONT_SIZE = 13       # 10 → 13
    HEADING_SIZE = 13    # 10 → 13

    @classmethod
    def apply(cls, root, theme_name: str = 'darkly'):
        """전체 가독성 스타일 적용"""
        try:
            is_dark = ThemeColors.is_dark_theme(theme_name)
            p = ThemeColors.get_palette(is_dark)

            style = None
            try:
                style = root.style  # ttkbootstrap
            except AttributeError:
                try:
                    import tkinter.ttk as _ttk
                    style = _ttk.Style()
                except (RuntimeError, ValueError) as e:
                    logger.debug(f"{type(e).__name__}: {e}")

            if not style:
                logger.warning("Style 객체 없음 - 가독성 스타일 건너뜀")
                return

            # ─── Root Window Background ───
            try:
                root.configure(background=p['bg_primary'])
            except Exception as e:
                logger.warning(f"[UI] ReadableStyle.apply root background config: {e}")  # noqa

            # ─── ttkbootstrap Colors Override (CRITICAL) ───
            if hasattr(style, 'colors'):
                try:
                    # ttkbootstrap의 색상 정의 자체를 변경하여 모든 위젯에 전파되도록 함
                    style.colors.bg = p['bg_primary']
                    style.colors.fg = p['text_primary']
                    style.colors.selectbg = p['tree_select_bg']
                    style.colors.selectfg = p['tree_select_fg']
                    style.colors.border = p['border']
                    style.colors.inputbg = p['bg_secondary']
                    style.colors.inputfg = p['text_primary']
                    
                    # Primary/Secondary 등 주요 색상도 매핑
                    style.colors.primary = p['primary'] 
                    style.colors.secondary = p['bg_secondary']
                    style.colors.success = p['success']
                    style.colors.info = p['info']
                    style.colors.warning = p['warning']
                    style.colors.danger = p['danger']
                    style.colors.light = p['text_primary']
                    style.colors.dark = p['bg_primary']
                    
                    logger.info("✅ ttkbootstrap.style.colors 오버라이드 완료")
                except Exception as _ce:
                    logger.warning(f"ttkbootstrap colors 오버라이드 실패: {_ce}")

            # ─── Treeview ─── (v6.1.1: foreground/background 명시, !selected 추가)
            style.configure(
                'Treeview',
                rowheight=cls.ROW_HEIGHT,
                font=(cls.FONT_FAMILY, cls.FONT_SIZE),
                borderwidth=0,
                relief='flat',
                foreground=p['text_primary'],
                background=p['bg_card'],
                fieldbackground=p['bg_card'],
            )
            style.configure(
                'Treeview.Heading',
                font=(cls.FONT_FAMILY, cls.HEADING_SIZE, 'bold'),
                padding=(8, 6),
                relief='flat',
                foreground=p['text_primary'],
                background=p['bg_secondary'],
            )
            # 헤더 라벨 가운데 정렬 (데이터 셀 anchor는 column() 별도 유지)
            try:
                import tkinter as tk
                style.configure('Treeview.Heading', anchor='center')
            except tk.TclError as e:
                logger.debug(f"[ReadableStyle] Treeview.Heading anchor(center) 무시: {e}")

            style.map(
                'Treeview',
                background=[('selected', p['tree_select_bg'])],
                foreground=[
                    ('selected', p['tree_select_fg']),
                    ('!selected', p['text_primary']),
                ],
            )

            # ─── Frame & Label (Global Background Override) ───
            # 기본 프레임과 라벨도 테마 색상을 따르도록 강제
            style.configure('.', background=p['bg_primary'], foreground=p['text_primary']) # 모든 위젯 기본 배경/글자색
            style.configure('TFrame', background=p['bg_primary'])
            style.configure('TLabel', background=p['bg_primary'], foreground=p['text_primary'])
            style.configure('TLabelframe', background=p['bg_primary'], foreground=p['text_primary'], bordercolor=p['border'])
            style.configure('TLabelframe.Label', background=p['bg_primary'], foreground=p['text_primary'])
            
            # ─── Button (Global Override) ───
            style.configure('TButton', font=(cls.FONT_FAMILY, cls.FONT_SIZE))
            # v8.1.5: 다크 테마에서 주황(warning) 등 단색 버튼 라벨이 배경과 겹쳐 안 보이는 현상 방지
            if is_dark:
                import tkinter as tk
                _bf = '#ffffff'
                for bst in (
                    'TButton', 'TCheckbutton', 'TRadiobutton',
                    'primary.TButton', 'secondary.TButton',
                    'success.TButton', 'info.TButton', 'warning.TButton',
                    'danger.TButton', 'light.TButton', 'dark.TButton',
                    'Toolbutton', 'primary.Toolbutton',
                ):
                    try:
                        style.configure(
                            bst, font=(cls.FONT_FAMILY, cls.FONT_SIZE), foreground=_bf)
                        style.map(
                            bst,
                            foreground=[('disabled', p['text_muted'])],
                        )
                    except tk.TclError:
                        pass  # TclError: widget destroyed
            # ─── Notebook 탭 ───
            style.configure(
                'TNotebook',
                background=p['bg_primary'],
                borderwidth=0
            )
            style.configure(
                'TNotebook.Tab',
                padding=(16, 8),
                font=(cls.FONT_FAMILY, cls.FONT_SIZE),
                background=p['bg_secondary'],
                foreground=p['text_muted']
            )
            style.map(
                'TNotebook.Tab',
                background=[('selected', p['bg_primary'])],
                foreground=[('selected', p['text_primary'])],
                expand=[('selected', [1, 1, 1, 0])]
            )

            # ─── LabelFrame ───
            style.configure(
                'TLabelframe',
                borderwidth=1,
                relief='solid',
            )
            style.configure(
                'TLabelframe.Label',
                font=(cls.FONT_FAMILY, cls.FONT_SIZE, 'bold'),
            )

            # ─── Entry ───
            style.configure(
                'TEntry',
                padding=(6, 4),
            )

            # ─── Combobox ───
            style.configure(
                'TCombobox',
                padding=(6, 4),
            )

            # ─── Separator ───
            style.configure(
                'TSeparator',
                background=p['border'],
            )

            logger.info(f"[v3.6.2] ReadableStyle 적용 완료 (theme={theme_name}, dark={is_dark})")

        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"ReadableStyle 적용 실패: {e}")

    @classmethod
    def get_toolbar_colors(cls, is_dark: bool = False) -> dict:
        """v3.6.2: 눈이 편안한 툴바 색상 팔레트 반환
        
        ⚠ DEPRECATED (v5.5.3 patch_01): toolbar_mixin이 style.colors를 직접 사용.
        하위 호환성을 위해 유지하나, 새 코드에서는 사용하지 마세요.
        """
        p = ThemeColors.get_palette(is_dark)
        return {
            'inbound':  {
                'bg': p['btn_inbound'], 'hover': p['btn_inbound_hover'],
                'text': '#ffffff', 'icon': '📥'
            },
            'outbound': {
                'bg': p['btn_outbound'], 'hover': p['btn_outbound_hover'],
                'text': '#ffffff', 'icon': '📤'
            },
            'report':   {
                'bg': p['btn_report'], 'hover': p['btn_report_hover'],
                'text': '#ffffff', 'icon': '📊'
            },
            'neutral':  {
                'bg': p['btn_neutral'], 'hover': p['btn_neutral_hover'],
                'text': '#ffffff'
            },
            'toolbar_bg':   p['bg_toolbar'],
            'statusbar_bg': p.get('bg_primary', '#2c3e50') if is_dark else '#2c3e50',
        }


# ═══════════════════════════════════════════════════════════════
# 7. 다이얼로그 위치 유틸리티
# ═══════════════════════════════════════════════════════════════

def center_dialog(dialog, parent=None):
    """
    다이얼로그를 부모 창 중앙에 배치
    
    사용법:
        dialog = tk.Toplevel(root)
        dialog.geometry("600x400")
        center_dialog(dialog, root)
    """
    dialog.update_idletasks()

    dialog_width = dialog.winfo_width()
    dialog_height = dialog.winfo_height()

    if parent:
        # 부모 창 중앙
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
    else:
        # 화면 중앙
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()

        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2

    # 화면 범위 내 유지
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()

    x = max(0, min(x, screen_width - dialog_width))
    y = max(0, min(y, screen_height - dialog_height))

    dialog.geometry(f"+{x}+{y}")


def apply_tooltip(widget, text: str, delay: int = 250):
    """
    위젯에 툴팁 적용 (v8.7.0)

    v8.7.0 변경:
      • 위치: 위젯의 **왼쪽 위 11시 방향**으로 멀리 떨어져 가로로 길게 표시
        (위젯 왼쪽에서 30px / 위쪽으로 20px 오프셋 → 클릭 영역 비가림)
      • 3초 경과 시 자동 숨김
      • 마우스 클릭 시 즉시 숨김
      • ttkbootstrap 경로 비활성화 — 항상 커스텀 Toplevel 사용 (위치·타이머 제어)

    사용법:
        apply_tooltip(my_button, '이 버튼은 데이터를 저장합니다')
    """
    # 전역 정책: 툴팁 60자 이내
    if text is None:
        text = ""
    text = str(text).strip()
    if len(text) > 60:
        text = text[:57].rstrip() + "..."

    import tkinter as tk

    def _bind_tk_tooltip(w, tip: str, ms: int):
        tip_win = None
        after_id = None   # show 지연 타이머
        hide_id = None    # 5초 자동 숨김 타이머

        def show():
            nonlocal tip_win, hide_id
            if tip_win:
                return
            try:
                theme_dark = is_dark()
                tip_win = tk.Toplevel(w)
                tip_win.wm_overrideredirect(True)
                tk.Label(
                    tip_win,
                    text=tip,
                    justify="left",
                    background=ThemeColors.get("bg_card", theme_dark),
                    foreground=ThemeColors.get("text_primary", theme_dark),
                    relief="solid",
                    borderwidth=1,
                    font=("맑은 고딕", 9),
                    padx=10,
                    pady=6,
                    wraplength=520,  # 가로로 길게 (10-11시 방향 배치에 최적)
                ).pack()

                # v8.7.0 [UX]: 11시 방향 멀리 배치 (기존 10-11시, 살짝 겹침 → 확실히 떨어진 위치로)
                tip_win.update_idletasks()
                tw = tip_win.winfo_reqwidth()
                th = tip_win.winfo_reqheight()
                wx = w.winfo_rootx()
                wy = w.winfo_rooty()
                sw = w.winfo_screenwidth()
                sh = w.winfo_screenheight()

                # 11시 방향 멀리: 위젯 왼쪽에서 30px 떨어진 자리에 tooltip 오른쪽 끝, 위로 20px
                x = wx - tw - 30
                y = wy - th - 20
                # 화면 밖이면 폴백
                if x < 0:
                    x = max(0, wx - tw + 24)  # 왼쪽 공간 부족 → 위젯 위에 겹치는 백업
                if y < 0:
                    y = wy + w.winfo_height() + 8
                if x + tw > sw:
                    x = sw - tw - 2
                if y + th > sh:
                    y = sh - th - 2

                tip_win.wm_geometry(f"+{x}+{y}")

                # v8.7.0 [UX]: 자동 숨김 3초 (기존 5초)
                hide_id = w.after(3000, cancel)
            except (tk.TclError, RuntimeError, AttributeError) as ex:
                logger.debug("tooltip show: %s", ex)
                return

        def cancel(_event=None):
            nonlocal tip_win, after_id, hide_id
            if after_id:
                try:
                    w.after_cancel(after_id)
                except (tk.TclError, RuntimeError, ValueError) as ex:
                    logger.debug("tooltip after_cancel: %s", ex)
                after_id = None
            if hide_id:
                try:
                    w.after_cancel(hide_id)
                except (tk.TclError, RuntimeError, ValueError) as ex:
                    logger.debug("tooltip hide_cancel: %s", ex)
                hide_id = None
            if tip_win:
                try:
                    tip_win.destroy()
                except (tk.TclError, RuntimeError) as ex:
                    logger.debug("tooltip destroy: %s", ex)
                tip_win = None

        def schedule(_event=None):
            nonlocal after_id
            cancel()
            try:
                after_id = w.after(ms, show)
            except (tk.TclError, RuntimeError) as ex:
                logger.debug("tooltip schedule: %s", ex)

        try:
            w.bind("<Enter>", schedule, add="+")
            w.bind("<Leave>", cancel, add="+")
            w.bind("<Button-1>", cancel, add="+")
            w.bind("<Button-3>", cancel, add="+")  # 우클릭도 숨김
        except (tk.TclError, RuntimeError) as ex:
            logger.debug("tooltip bind: %s", ex)

    try:
        _bind_tk_tooltip(widget, text, max(200, int(delay)))
    except Exception as e:
        logger.debug("apply_tooltip tk fallback: %s", e)


def apply_modal_window_options(dialog) -> None:
    """
    모달 창에 크기 조절 + 최소/최대 버튼 적용.
    resizable(True,True) 및 toolwindow=False(Windows 표준 창 장식).
    """
    try:
        dialog.resizable(True, True)
        try:
            dialog.attributes('-toolwindow', 0)
        except (Exception, AttributeError) as e:
            logger.debug(f"[apply_modal_window_options] Suppressed: {e}")
    except (Exception, AttributeError) as e:
        logger.debug(f"[apply_modal_window_options] Suppressed: {e}")


# tk.Scrollbar 기본 폭 + ttk Scrollbar 두께 (가로·세로 공통 목표 픽셀)
SQM_SCROLLBAR_WIDTH_PX = 24


def _resolve_ttk_style(widget):
    """ttkbootstrap Window.style 또는 ttk.Style(widget) 반환."""
    try:
        import tkinter as tk
        w = widget
        seen = set()
        while w is not None and id(w) not in seen:
            seen.add(id(w))
            st = getattr(w, 'style', None)
            if st is not None:
                return st, tk
            w = getattr(w, 'master', None)
        import tkinter.ttk as ttk
        return ttk.Style(widget), tk
    except Exception as e:
        logger.debug(f"[_resolve_ttk_style] Suppressed: {e}")
        return None, None


def _apply_ttk_scrollbar_thickness(widget, width_px: int) -> None:
    """ttk/ttkbootstrap Vertical·Horizontal 스크롤바 두께 (테마별 thickness/width 키 상이)."""
    st, tk = _resolve_ttk_style(widget)
    if st is None or tk is None:
        return
    for nm in ('Vertical.TScrollbar', 'Horizontal.TScrollbar', 'TScrollbar'):
        for key in ('thickness', 'width'):
            try:
                st.configure(nm, **{key: int(width_px)})
                break
            except tk.TclError:
                continue


def apply_contrast_scrollbar_style(root, theme_name: str = 'darkly') -> None:
    """전역 Scrollbar 대비색/두께 적용 (tk.Scrollbar + ttk Scrollbar)."""
    try:
        is_dark = ThemeColors.is_dark_theme(theme_name)
        trough = '#111111' if is_dark else '#f2f2f2'  # v6.3.2-fix: 반전 수정
        thumb = '#f2f2f2' if is_dark else '#111111'  # v6.3.2-fix: 반전 수정
        active = '#ffffff' if is_dark else '#000000'  # v6.3.2-fix: 반전 수정
        width = SQM_SCROLLBAR_WIDTH_PX

        # 이후 생성되는 Scrollbar 기본값
        root.option_add('*Scrollbar.width', width)
        root.option_add('*Scrollbar.troughColor', trough)
        root.option_add('*Scrollbar.background', thumb)
        root.option_add('*Scrollbar.activeBackground', active)
        root.option_add('*Scrollbar.relief', 'solid')
        root.option_add('*Scrollbar.borderWidth', 1)
        root.option_add('*Scrollbar.highlightThickness', 0)

        _apply_ttk_scrollbar_thickness(root, width)

        # 이미 생성된 Scrollbar에도 즉시 적용
        def _walk(widget):
            try:
                children = widget.winfo_children()
            except Exception as e:
                logger.warning(f"[UI] scrollbar style winfo_children: {e}")  # noqa
                children = []
            for child in children:
                if child.winfo_class() == 'Scrollbar':
                    try:
                        child.configure(
                            width=width,
                            troughcolor=trough,
                            bg=thumb,
                            activebackground=active,
                            relief='solid',
                            bd=1,
                            highlightthickness=0,
                        )
                    except Exception as e:
                        logger.warning(f"[UI] scrollbar style child configure: {e}")  # noqa
                _walk(child)

        _walk(root)
    except Exception as e:
        logger.debug(f"[apply_contrast_scrollbar_style] Suppressed: {e}")


# ═══════════════════════════════════════════════════════════════
# 창 크기 저장/복원 (메인 + 하위/팝업 공통)
# ═══════════════════════════════════════════════════════════════

def _geometry_config_path():
    """window_config.json 경로 (메인 창과 동일)."""
    from pathlib import Path
    try:
        from .constants import WINDOW_CONFIG_FILE
        if WINDOW_CONFIG_FILE:
            return Path(WINDOW_CONFIG_FILE)
    except (ImportError, AttributeError) as e:
        logger.debug(f"[_geometry_config_path] Suppressed: {e}")
    return Path(__file__).resolve().parent.parent.parent / "window_config.json"


def load_all_geometry() -> dict:
    """저장된 창 설정 전체 로드. {'width','height','x','y', 'dialogs': {key: 'WxH+x+y'}}."""
    path = _geometry_config_path()
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.debug(f"Geometry config load: {e}")
    return {}


def save_geometry_config(config: dict) -> None:
    """창 설정 전체 저장. config에 dialogs 등 기존 키 유지."""
    path = _geometry_config_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.debug(f"Geometry config save: {e}")


def load_dialog_geometry(key: str) -> Optional[str]:
    """다이얼로그용 저장된 geometry 문자열. 없으면 None."""
    data = load_all_geometry()
    dialogs = data.get('dialogs') or {}
    return dialogs.get(key)


def save_dialog_geometry(key: str, geometry: str) -> None:
    """다이얼로그 크기/위치 저장. 기존 메인 창 설정은 유지."""
    config = load_all_geometry()
    if 'dialogs' not in config or not isinstance(config['dialogs'], dict):
        config['dialogs'] = {}
    config['dialogs'][key] = geometry
    save_geometry_config(config)


def setup_dialog_geometry_persistence(
    dialog,
    key: str,
    parent,
    default_size_type: str = 'large',
) -> None:
    """
    다이얼로그에 직전 사용 크기 복원 + 닫을 때 저장.
    - key: 창 구분용 (예: 'allocation_dialog', 'picking_preview')
    - default_size_type: 저장값 없을 때 사용할 크기 ('large' 권장)
    """
    apply_modal_window_options(dialog)
    saved = load_dialog_geometry(key)
    if saved and re.match(r'^\d+x\d+(\+-?\d+\+-?\d+)?$', saved.strip()):
        try:
            dialog.geometry(saved)
        except Exception as _ge:
            logging.getLogger(__name__).debug(f"[UI] 다이얼로그 geometry 복원 실패: {_ge}")
    if not saved or not dialog.winfo_geometry().strip():
        w, h = DialogSize.calculate(parent, default_size_type)
        dialog.geometry(f"{w}x{h}")
        center_dialog(dialog, parent)
    dialog.update_idletasks()

    def _on_save_geometry(e=None):
        try:
            g = dialog.winfo_geometry()
            if g and re.match(r'^\d+x\d+', g):
                save_dialog_geometry(key, g)
        except (RuntimeError, Exception) as _e:
            logger.debug(f"[_on_save_geometry] Suppressed: {_e}")

    dialog.bind('<Destroy>', _on_save_geometry, add='+')


def setup_dialog_defaults(dialog, parent, title: str, size_type: str = 'medium'):
    """
    다이얼로그 기본 설정 (크기, 위치, 동작)
    - 크기 조절 가능, 최소/최대 버튼 표시
    """
    # 제목
    dialog.title(title)

    # 크기
    geometry = DialogSize.get_geometry(parent, size_type)
    dialog.geometry(geometry)

    # 크기 조절 + 최소/최대 버튼
    apply_modal_window_options(dialog)

    # 부모 연결
    dialog.transient(parent)
    dialog.grab_set()

    # 중앙 배치
    center_dialog(dialog, parent)

    # ESC로 닫기
    dialog.bind('<Escape>', lambda e: dialog.destroy())

    return dialog


# ═══════════════════════════════════════════════════════════════
# 8. 반응형 레이아웃
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# 전역 인스턴스 (편의용)
# ═══════════════════════════════════════════════════════════════

_ui_calculator: Optional[UICalculator] = None
_font_scale: Optional[FontScale] = None


def init_ui_system(root):
    """UI 시스템 초기화"""
    global _ui_calculator, _font_scale

    _ui_calculator = UICalculator(root)
    _font_scale = FontScale(_ui_calculator.dpi)

    logger.info(f"UI 시스템 초기화: DPI={_ui_calculator.dpi:.0f}, "
                f"Scale={_ui_calculator.combined_scale:.2f}")


def get_ui_calculator() -> UICalculator:
    """UI 계산기 인스턴스"""
    return _ui_calculator or UICalculator()


def get_font_scale() -> FontScale:
    """폰트 스케일 인스턴스"""
    return _font_scale or FontScale()


# ═══════════════════════════════════════════════════════════════
# 8. 커스텀 메시지박스 (간격 조절 가능) — 하위 호환용 지연 로드
# ═══════════════════════════════════════════════════════════════
# v4.0.2: custom_messagebox.py에서 정의. 순환 import 방지를 위해 __getattr__ 로 지연 로드.


def __getattr__(name: str):
    if name == "CustomMessageBox":
        from .custom_messagebox import CustomMessageBox
        return CustomMessageBox
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ═══════════════════════════════════════════════════════════
# v7.6.0 — 공통 탭 헤더 헬퍼 (심플 레이아웃)
# ═══════════════════════════════════════════════════════════

def make_tab_header(parent, title: str, status_color: str = '#3b82f6',
                    count_var=None, is_dark: bool = None, compact: bool = False):
    """탭 상단 표준 헤더 바 — v8.1.8: tc() 색상 시스템 적용, 높이 38px 고정.

    Args:
        parent:       탭 프레임
        title:        탭 제목 (예: "📋 판매배정")
        status_color: 왼쪽 컬러 바 색상
        count_var:    tk.StringVar — 건수 실시간 표시 (옵션)
        is_dark:      None → 전역 _GLOBAL_IS_DARK 자동 사용
        compact:      True면 낮은 높이·좁은 상하 여백 (대시보드 등 본문을 위로 붙일 때)

    Returns:
        header_frame (tk.Frame)
    """
    import tkinter as tk

    # 같은 모듈 내 전역변수/함수 직접 사용 (순환 import 방지)
    _dark = _GLOBAL_IS_DARK if is_dark is None else is_dark
    bg     = tc('bg_secondary', _dark)
    fg     = tc('text_primary',  _dark)
    _palette = ThemeColors.DARK if _dark else ThemeColors.LIGHT
    border = _palette.get('border', '#334155' if _dark else '#e2e8f0')

    _hdr_h = 26 if compact else Spacing.Tab.HEADER_H
    _hdr_pady = (2, 4) if compact else Spacing.Tab.HEADER_PADY
    outer = tk.Frame(parent, bg=border, height=_hdr_h)
    outer.pack(fill='x', padx=0, pady=_hdr_pady)
    outer.pack_propagate(False)

    # 왼쪽 컬러 바
    tk.Frame(outer, bg=status_color, width=5).pack(side='left', fill='y')

    inner = tk.Frame(outer, bg=bg)
    inner.pack(side='left', fill='both', expand=True)

    tk.Label(inner, text=title, bg=bg, fg=fg,
             font=('맑은 고딕', 12, 'bold')).pack(side='left', padx=10)

    if count_var is not None:
        tk.Label(inner, textvariable=count_var, bg=bg, fg=status_color,
                 font=('맑은 고딕', 11, 'bold')).pack(side='right', padx=10)

    return outer

def apply_treeview_theme(tree, is_dark=None):
    """Treeview 상태 태그 색상 설정. is_dark 생략 시 전역 자동 사용."""
    if is_dark is None:
        is_dark = _GLOBAL_IS_DARK
    ThemeColors.configure_tags(tree, is_dark)


# ══════════════════════════════════════════════════════════════
# v9.1: create_themed_toplevel() — 테마 안전 다이얼로그 팩토리
# ══════════════════════════════════════════════════════════════
# 사용법:
#   from gui_app_modular.utils.ui_constants import create_themed_toplevel
#   dialog = create_themed_toplevel(self.root, title="설정")
#
# 이 함수로 만든 Toplevel은 생성 즉시 현재 테마 색상이 적용됩니다.
# tk.Toplevel(self.root) 직접 생성 금지 — 반드시 이 팩토리 사용
# ══════════════════════════════════════════════════════════════

def create_themed_toplevel(parent, title: str = '',
                            width: int = 0, height: int = 0,
                            resizable: tuple = (True, True)) -> 'tk.Toplevel':
    """테마 안전 Toplevel 생성 팩토리 (v9.1).

    생성 즉시:
      1. 현재 테마(라이트/다크) 배경 적용
      2. 타이틀 설정
      3. 모달 크기 설정 (선택)

    기존: dialog = tk.Toplevel(self.root)  ← 테마 보호 없음
    권장: dialog = create_themed_toplevel(self.root, title="...")

    Returns:
        테마 색상이 적용된 tk.Toplevel 인스턴스
    """
    import tkinter as tk
    win = tk.Toplevel(parent)
    if title:
        win.title(title)
    if width and height:
        win.geometry(f"{width}x{height}")
    win.resizable(*resizable)

    # 현재 테마 색상 즉시 적용
    try:
        win.configure(bg=tc('bg_primary'))
    except Exception as e:
        logger.warning(f"[UI] create_themed_toplevel bg config: {e}")  # noqa

    # 열릴 때마다 자식 위젯 색상 갱신 (after 1ms — 위젯 생성 후)
    try:
        from gui_app_modular.utils.theme_refresh import apply_tc_theme_to_all
        win.after(1, lambda: apply_tc_theme_to_all(win))
    except Exception as e:
        logger.warning(f"[UI] create_themed_toplevel theme refresh callback: {e}")  # noqa

    # 이 Toplevel 트리에 스크롤바 폭·대비 재적용 (동기 구성 직후 + 레이아웃 이후)
    try:
        apply_contrast_scrollbar_style(win, get_global_theme())
    except Exception as e:
        logger.warning(f"[UI] create_themed_toplevel scrollbar style: {e}")  # noqa

    def _deferred_scrollbar_style():
        try:
            apply_contrast_scrollbar_style(win, get_global_theme())
        except Exception as e:
            logger.debug(f"[UI] deferred scrollbar style: {e}")

    win.after(120, _deferred_scrollbar_style)

    return win

