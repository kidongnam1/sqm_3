"""
SQM v6.12.2 — 반품 원인 분석 리포트 PDF 생성
==============================================
reportlab 기반 월간/기간별 반품 분석 PDF.
- 요약 헤더 (기간, 건수, 중량, 반품률)
- 사유별 표 + 비율
- LOT별 Top 10
- 월별 추이 표
- 고객별 Top 10
"""

def _get_malgun_font_paths():
    """플랫폼별 맑은 고딕 폰트 경로 목록 반환."""
    import sys, os
    if sys.platform == 'win32':
        win_fonts = os.environ.get('WINDIR', 'C:/Windows') + '/Fonts'
        return [
            os.path.join(win_fonts, 'malgun.ttf'),
            os.path.join(win_fonts, 'malgunbd.ttf'),
            _get_malgun_font_paths()[0],    # fallback
        ]
    elif sys.platform == 'darwin':
        return [
            '/Library/Fonts/AppleGothic.ttf',
            '/System/Library/Fonts/AppleGothic.ttf',
        ]
    else:  # Linux
        return [
            '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ]

import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def generate_return_report_pdf(engine: Any, save_path: str,
                                start_date: str = '', end_date: str = '') -> str:
    """
    반품 원인 분석 PDF 생성.

    Args:
        engine: get_return_statistics() 메서드를 가진 엔진
        save_path: 저장 경로
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)

    Returns:
        저장된 파일 경로
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError:
        raise ImportError("reportlab 필요: pip install reportlab")

    stats = engine.get_return_statistics(start_date=start_date, end_date=end_date)

    c = canvas.Canvas(save_path, pagesize=A4)
    width, height = A4
    y = height - 30 * mm

    # ─── 한글 폰트 설정 ───
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        # Windows 맑은 고딕
        font_paths = [
            _get_malgun_font_paths()[0],
            'C:/Windows/Fonts/malgunbd.ttf',
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        ]
        _font_registered = False
        for fp in font_paths:
            if os.path.exists(fp):
                pdfmetrics.registerFont(TTFont('Korean', fp))
                _font_registered = True
                break
        if not _font_registered:
            logger.warning("[ReturnPDF] 한글 폰트 미발견 — 기본 폰트 사용")
    except Exception as fe:
        logger.debug(f"[ReturnPDF] 폰트 로드 실패: {fe}")

    def _font(size=10, bold=False):
        try:
            return 'Korean'
        except Exception:
            return 'Helvetica-Bold' if bold else 'Helvetica'

    def _text(x, y_pos, text, size=10, bold=False, color=colors.black):
        c.setFont(_font(size, bold), size)
        c.setFillColor(color)
        c.drawString(x, y_pos, str(text))
        return y_pos

    def _check_page(y_pos, needed=30 * mm):
        if y_pos < needed:
            c.showPage()
            return height - 25 * mm
        return y_pos

    # ═══ 타이틀 ═══
    c.setFillColor(colors.HexColor('#2C3E50'))
    c.rect(15 * mm, y, width - 30 * mm, 18 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont(_font(14, True), 14)
    c.drawString(20 * mm, y + 5 * mm, "SQM 반품 원인 분석 리포트")
    y -= 8 * mm

    # ═══ 요약 ═══
    period = f"{start_date or '전체'} ~ {end_date or '현재'}"
    generated = datetime.now().strftime('%Y-%m-%d %H:%M')
    y -= 5 * mm
    _text(20 * mm, y, f"기간: {period}  |  생성: {generated}", 9)
    y -= 6 * mm
    total_cnt = stats.get('total_count', 0)
    total_kg = stats.get('total_weight_kg', 0)
    _text(20 * mm, y, f"전체 반품: {total_cnt:,}건  |  총 중량: {total_kg:,.0f} kg", 11, bold=True)
    y -= 12 * mm

    # ═══ 1. 사유별 통계 ═══
    y = _check_page(y)
    _text(20 * mm, y, "1. 반품 사유별 분석", 12, bold=True, color=colors.HexColor('#2C3E50'))
    y -= 8 * mm

    # 테이블 헤더
    headers = ['#', '사유', '건수', '중량(kg)', '비율']
    col_x = [20, 30, 100, 140, 185]
    c.setFillColor(colors.HexColor('#34495E'))
    c.rect(18 * mm, y - 1 * mm, width - 36 * mm, 6 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont(_font(9, True), 9)
    for i, h in enumerate(headers):
        c.drawString(col_x[i] * mm, y, h)
    y -= 7 * mm

    total_cnt_safe = total_cnt or 1
    for idx, r in enumerate(stats.get('by_reason', [])[:15], 1):
        y = _check_page(y)
        pct = r['count'] / total_cnt_safe * 100
        vals = [str(idx), r['reason'], f"{r['count']:,}", f"{r['weight_kg']:,.0f}", f"{pct:.1f}%"]
        c.setFillColor(colors.black)
        c.setFont(_font(9), 9)
        for i, v in enumerate(vals):
            c.drawString(col_x[i] * mm, y, v)
        y -= 5 * mm

    y -= 8 * mm

    # ═══ 2. LOT별 Top 10 ═══
    y = _check_page(y)
    _text(20 * mm, y, "2. LOT별 반품 현황 (Top 10)", 12, bold=True, color=colors.HexColor('#2C3E50'))
    y -= 8 * mm

    headers2 = ['#', 'LOT NO', '건수', '중량(kg)', '사유']
    col_x2 = [20, 30, 80, 110, 155]
    c.setFillColor(colors.HexColor('#34495E'))
    c.rect(18 * mm, y - 1 * mm, width - 36 * mm, 6 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont(_font(9, True), 9)
    for i, h in enumerate(headers2):
        c.drawString(col_x2[i] * mm, y, h)
    y -= 7 * mm

    for idx, r in enumerate(stats.get('by_lot', [])[:10], 1):
        y = _check_page(y)
        reasons_short = r['reasons'][:30] + ('...' if len(r['reasons']) > 30 else '')
        vals = [str(idx), r['lot_no'], f"{r['count']:,}", f"{r['weight_kg']:,.0f}", reasons_short]
        c.setFillColor(colors.black)
        c.setFont(_font(9), 9)
        for i, v in enumerate(vals):
            c.drawString(col_x2[i] * mm, y, v)
        y -= 5 * mm

    y -= 8 * mm

    # ═══ 3. 월별 추이 ═══
    y = _check_page(y, 40 * mm)
    _text(20 * mm, y, "3. 월별 반품 추이", 12, bold=True, color=colors.HexColor('#2C3E50'))
    y -= 8 * mm

    headers3 = ['월', '건수', '중량(kg)']
    col_x3 = [20, 60, 100]
    c.setFillColor(colors.HexColor('#34495E'))
    c.rect(18 * mm, y - 1 * mm, 80 * mm, 6 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont(_font(9, True), 9)
    for i, h in enumerate(headers3):
        c.drawString(col_x3[i] * mm, y, h)
    y -= 7 * mm

    for r in stats.get('by_month', []):
        y = _check_page(y)
        vals = [r['month'], f"{r['count']:,}", f"{r['weight_kg']:,.0f}"]
        c.setFillColor(colors.black)
        c.setFont(_font(9), 9)
        for i, v in enumerate(vals):
            c.drawString(col_x3[i] * mm, y, v)
        y -= 5 * mm

    y -= 8 * mm

    # ═══ 4. 고객별 ═══
    y = _check_page(y, 30 * mm)
    _text(20 * mm, y, "4. 고객별 반품 현황 (Top 10)", 12, bold=True, color=colors.HexColor('#2C3E50'))
    y -= 8 * mm

    headers4 = ['#', '고객', '건수']
    col_x4 = [20, 30, 100]
    c.setFillColor(colors.HexColor('#34495E'))
    c.rect(18 * mm, y - 1 * mm, 80 * mm, 6 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont(_font(9, True), 9)
    for i, h in enumerate(headers4):
        c.drawString(col_x4[i] * mm, y, h)
    y -= 7 * mm

    for idx, r in enumerate(stats.get('top_customers', [])[:10], 1):
        y = _check_page(y)
        vals = [str(idx), r['customer'], f"{r['count']:,}"]
        c.setFillColor(colors.black)
        c.setFont(_font(9), 9)
        for i, v in enumerate(vals):
            c.drawString(col_x4[i] * mm, y, v)
        y -= 5 * mm

    # ═══ 푸터 ═══
    c.setFont(_font(8), 8)
    c.setFillColor(colors.grey)
    c.drawString(20 * mm, 15 * mm, f"SQM 재고관리 시스템 — 반품 분석 리포트 | {generated}")

    c.save()
    logger.info(f"[ReturnPDF] 생성 완료: {save_path}")
    return save_path
