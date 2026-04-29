"""
SQM v3.9.8 — PDF 재고 보고서 자동 생성
========================================

기능:
- 일별 재고 현황 PDF
- 월별 입출고 실적 PDF
- LOT별 상세 보고서 PDF

reportlab 기반.
"""

import logging
import os
from datetime import datetime
from typing import List, Optional

# v6.5.4: reportlab 공통 임포트 — 함수별 중복 제거
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    _REPORTLAB_OK = True
except ImportError:
    _REPORTLAB_OK = False


logger = logging.getLogger(__name__)


def generate_daily_inventory_report(engine, output_dir: str = 'output/reports') -> Optional[str]:
    """
    일별 재고 현황 PDF 생성
    
    Args:
        engine: SQM 엔진 인스턴스
        output_dir: 출력 디렉토리
    
    Returns:
        생성된 파일 경로 (실패시 None)
    """
    if not _REPORTLAB_OK:
        logger.error("reportlab 미설치: pip install reportlab")
        return None

    # 폰트 등록
    _register_korean_font()

    os.makedirs(output_dir, exist_ok=True)
    today = datetime.now().strftime('%Y%m%d')
    filename = f"SQM_재고현황_{today}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=20*mm, bottomMargin=15*mm
    )

    # 스타일
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'KorTitle', parent=styles['Title'],
        fontName='MalgunGothic' if _has_malgun() else 'Helvetica',
        fontSize=16, spaceAfter=10
    )
    normal_style = ParagraphStyle(
        'KorNormal', parent=styles['Normal'],
        fontName='MalgunGothic' if _has_malgun() else 'Helvetica',
        fontSize=9
    )

    elements = []

    # 제목
    elements.append(Paragraph(
        f"SQM 재고 현황 보고서 — {datetime.now().strftime('%Y-%m-%d')}",
        title_style
    ))
    elements.append(Spacer(1, 5*mm))

    # 요약
    try:
        summary = engine.get_inventory_summary()
        total_lots = summary.get('total_lots', 0)
        avail_lots = summary.get('available_lots', 0)
        total_mt = summary.get('total_current_mt', 0)
        initial_mt = summary.get('total_initial_mt', 0)

        summary_data = [
            ['항목', '수치'],
            ['총 LOT 수', f"{total_lots}개"],
            ['판매가능 LOT', f"{avail_lots}개"],
            ['총 입고량', f"{initial_mt:,.1f} MT"],
            ['현재 잔량', f"{total_mt:,.1f} MT"],
            ['Out %', f"{((initial_mt - total_mt) / max(initial_mt, 1) * 100):,.1f}%"],
        ]

        t = Table(summary_data, colWidths=[100, 120])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'MalgunGothic' if _has_malgun() else 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f6fa')]),
        ]))
        elements.append(t)
    except (ValueError, TypeError, AttributeError) as e:
        elements.append(Paragraph(f"요약 생성 오류: {e}", normal_style))

    elements.append(Spacer(1, 8*mm))

    # LOT별 상세 테이블
    try:
        inventory = engine.get_inventory()

        if inventory:
            elements.append(Paragraph("LOT별 재고 상세", ParagraphStyle(
                'SubTitle', parent=styles['Heading2'],
                fontName='MalgunGothic' if _has_malgun() else 'Helvetica',
                fontSize=12, spaceAfter=5
            )))

            header = ['LOT NO', 'SAP NO', 'PRODUCT', 'STATUS', 'Inbound(MT)', 'Balance(MT)', 'Out %']
            data = [header]
            from .ui_constants import get_status_display as _status_display
            for item in inventory:
                lot_no = item.get('lot_no', '')
                sap_no = item.get('sap_no', '')
                product = item.get('product', '')
                status_raw = item.get('status', '')
                status = _status_display(status_raw) or status_raw
                init_w = float(item.get('initial_weight', 0) or 0) / 1000
                curr_w = float(item.get('current_weight', 0) or 0) / 1000
                pct = ((init_w - curr_w) / max(init_w, 0.001)) * 100

                data.append([
                    str(lot_no), str(sap_no), str(product)[:12],
                    status, f"{init_w:,.1f}", f"{curr_w:,.1f}", f"{pct:.0f}%"
                ])

            col_widths = [75, 70, 65, 55, 50, 50, 40]
            t = Table(data, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, -1), 'MalgunGothic' if _has_malgun() else 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('ALIGN', (3, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (4, 1), (5, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#bdc3c7')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
            ]))
            elements.append(t)
    except (ValueError, KeyError, OSError) as e:
        elements.append(Paragraph(f"상세 테이블 오류: {e}", normal_style))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph(
        f"생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | SQM Inventory Management v3.9.8",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.grey)
    ))

    # v4.0.0: GY Logistics 푸터
    try:
        from .report_footer import add_gy_logistics_footer_pdf
        add_gy_logistics_footer_pdf(elements, styles)
    except (ValueError, TypeError, KeyError) as _e:
        logger.debug(f'Suppressed: {_e}')
    doc.build(elements)
    logger.info(f"PDF 보고서 생성: {filepath}")
    return filepath


def generate_monthly_report(engine, year: int = None, month: int = None,
                            output_dir: str = 'output/reports') -> Optional[str]:
    """월별 입출고 실적 PDF"""
    if not _REPORTLAB_OK:
        return None

    _register_korean_font()

    if not year:
        year = datetime.now().year
    if not month:
        month = datetime.now().month

    os.makedirs(output_dir, exist_ok=True)
    filename = f"SQM_월보_{year}{month:02d}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                           leftMargin=15*mm, rightMargin=15*mm,
                           topMargin=20*mm, bottomMargin=15*mm)

    styles = getSampleStyleSheet()
    fn = 'MalgunGothic' if _has_malgun() else 'Helvetica'

    elements = []
    elements.append(Paragraph(
        f"SQM 월간 실적 보고서 — {year}년 {month}월",
        ParagraphStyle('Title', parent=styles['Title'], fontName=fn, fontSize=16)
    ))
    elements.append(Spacer(1, 8*mm))

    # 해당 월 입출고 데이터 수집
    try:
        movements = engine.db.fetchall("""
            SELECT movement_type, SUM(qty_kg) as total, COUNT(*) as cnt
            FROM stock_movement
            WHERE strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ?
            GROUP BY movement_type
        """, (str(year), f"{month:02d}"))

        data = [['구분', '건수', '수량 (kg)', '수량 (MT)']]
        for m in movements:
            mt = dict(m)
            qty = float(mt.get('total', 0) or 0)
            cnt = int(mt.get('cnt', 0) or 0)
            data.append([
                str(mt.get('movement_type', '')),
                f"{cnt}건",
                f"{qty:,.0f}",
                f"{qty/1000:,.2f}"
            ])

        if len(data) == 1:
            data.append(['(데이터 없음)', '-', '-', '-'])

        t = Table(data, colWidths=[80, 60, 80, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), fn),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(t)
    except (ValueError, KeyError, OSError) as e:
        elements.append(Paragraph(f"데이터 조회 오류: {e}",
                                  ParagraphStyle('err', parent=styles['Normal'], fontName=fn, fontSize=9)))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph(
        f"생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | SQM v6.2.3",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.grey)
    ))

    # v4.0.0: GY Logistics 푸터
    try:
        from .report_footer import add_gy_logistics_footer_pdf
        add_gy_logistics_footer_pdf(elements, styles)
    except (ValueError, TypeError, KeyError) as _e:
        logger.debug(f'Suppressed: {_e}')
    doc.build(elements)
    logger.info(f"월간 보고서 생성: {filepath}")
    return filepath


# === v4.1.1: 출고확인서 PDF ===

def generate_outbound_confirmation(engine, lot_no: str, tonbag_ids: List[int] = None,
                                    customer: str = '', output_dir: str = 'output/reports') -> Optional[str]:
    """
    출고확인서 PDF 생성
    
    Args:
        engine: SQM 엔진
        lot_no: LOT 번호
        tonbag_ids: 출고 톤백 sub_lt 목록 (None이면 PICKED 전부)
        customer: 고객명
        output_dir: 출력 디렉토리
    """
    if not _REPORTLAB_OK:
        return None

    _register_korean_font()
    fn = 'MalgunGothic' if _has_malgun() else 'Helvetica'

    # LOT 정보
    lot_info = engine.db.fetchone("SELECT * FROM inventory WHERE lot_no = ?", (lot_no,))
    if not lot_info:
        return None

    # 톤백 정보
    if tonbag_ids:
        placeholders = ','.join('?' * len(tonbag_ids))
        tonbags = engine.db.fetchall(
            f"SELECT * FROM inventory_tonbag WHERE lot_no = ? AND sub_lt IN ({placeholders})",
            [lot_no] + list(tonbag_ids))
    else:
        tonbags = engine.db.fetchall(
            "SELECT * FROM inventory_tonbag WHERE lot_no = ? AND status IN ('PICKED','SHIPPED','CONFIRMED')",
            (lot_no,))

    if not tonbags:
        return None

    os.makedirs(output_dir, exist_ok=True)
    today = datetime.now().strftime('%Y%m%d')
    filename = f"출고확인서_{lot_no}_{today}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=20*mm, bottomMargin=15*mm)

    styles = getSampleStyleSheet()
    elements = []

    # 제목
    elements.append(Paragraph("출 고 확 인 서",
        ParagraphStyle('Title', parent=styles['Title'], fontName=fn, fontSize=20,
                       spaceAfter=5, alignment=1)))
    elements.append(Paragraph("Outbound Confirmation",
        ParagraphStyle('SubTitle', parent=styles['Normal'], fontName=fn, fontSize=10,
                       textColor=colors.grey, alignment=1)))
    elements.append(Spacer(1, 8*mm))

    # 기본 정보 테이블
    product = lot_info.get('product', '-') or '-'
    sap_no = lot_info.get('sap_no', '-') or '-'
    bl_no = lot_info.get('bl_no', '-') or '-'
    container = lot_info.get('container_no', '-') or '-'

    info_data = [
        ['LOT NO', str(lot_no), '제품명', str(product)],
        ['SAP NO', str(sap_no), 'B/L NO', str(bl_no)],
        ['CONTAINER', str(container), '고객명', str(customer or '-')],
        ['출고일', datetime.now().strftime('%Y-%m-%d'), '문서번호', f"OUT-{today}-{lot_no[-4:]}"],
    ]

    t = Table(info_data, colWidths=[70, 130, 70, 130])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), fn),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#34495e')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6*mm))

    # 톤백 상세
    elements.append(Paragraph("출고 톤백 상세",
        ParagraphStyle('H2', parent=styles['Heading2'], fontName=fn, fontSize=12, spaceAfter=3)))

    tb_data = [['No.', '톤백#', '중량(kg)', '중량(MT)', '상태', '비고']]
    total_kg = 0.0
    for idx, tb in enumerate(tonbags, 1):
        w = float(tb.get('weight', 0) or (tb[6] if not isinstance(tb, dict) else 0))
        st = tb.get('status', '') if isinstance(tb, dict) else (tb[7] if len(tb) > 7 else '')
        sub = tb.get('sub_lt', '') if isinstance(tb, dict) else (tb[5] if len(tb) > 5 else '')
        rem = tb.get('remarks', '') if isinstance(tb, dict) else ''
        total_kg += w
        tb_data.append([str(idx), str(sub), f"{w:,.1f}", f"{w/1000:,.3f}", str(st), str(rem)[:20]])

    tb_data.append(['', '합계', f"{total_kg:,.1f}", f"{total_kg/1000:,.3f}", f"{len(tonbags)}개", ''])

    t = Table(tb_data, colWidths=[30, 50, 80, 70, 70, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), fn),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
        ('ALIGN', (4, 0), (4, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#bdc3c7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f5f6fa')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
        ('FONTNAME', (0, -1), (-1, -1), fn),
    ]))
    elements.append(t)

    elements.append(Spacer(1, 15*mm))

    # 서명란
    sig_data = [
        ['출고 담당', '', '인수 담당', ''],
        ['서명:', '_____________', '서명:', '_____________'],
        ['일자:', datetime.now().strftime('%Y.%m.%d'), '일자:', '____.____.____'],
    ]
    t = Table(sig_data, colWidths=[60, 120, 60, 120])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), fn),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)

    # 푸터
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(
        f"생성: {datetime.now().strftime('%Y-%m-%d %H:%M')} | SQM Inventory v4.1.1 | GY Logistics",
        ParagraphStyle('Footer', parent=styles['Normal'], fontName=fn, fontSize=7,
                       textColor=colors.grey, alignment=1)))

    try:
        from .report_footer import add_gy_logistics_footer_pdf
        add_gy_logistics_footer_pdf(elements, styles)
    except (ValueError, TypeError, KeyError, ImportError) as _e:
        logger.debug(f"Suppressed: {_e}")

    doc.build(elements)
    logger.info(f"출고확인서 생성: {filepath}")
    return filepath


def generate_transaction_statement(engine, customer: str = '',
                                    date_from: str = '', date_to: str = '',
                                    output_dir: str = 'output/reports') -> Optional[str]:
    """
    거래명세서 PDF 생성
    
    Args:
        engine: SQM 엔진
        customer: 고객명 필터
        date_from/date_to: 기간 필터
        output_dir: 출력 디렉토리
    """
    if not _REPORTLAB_OK:
        return None

    _register_korean_font()
    fn = 'MalgunGothic' if _has_malgun() else 'Helvetica'

    # 출고 데이터 조회
    query = """
        SELECT t.lot_no, t.sub_lt, t.weight, t.status, t.picked_to,
               t.picked_date, t.outbound_date, t.sale_ref,
               i.product, i.sap_no, i.container_no
        FROM inventory_tonbag t
        JOIN inventory i ON t.lot_no = i.lot_no
        WHERE t.status IN ('PICKED','SHIPPED','CONFIRMED')
    """
    params = []
    if customer:
        query += " AND t.picked_to LIKE ?"
        params.append(f"%{customer}%")
    if date_from:
        query += " AND COALESCE(t.outbound_date, t.picked_date) >= ?"
        params.append(date_from)
    if date_to:
        query += " AND COALESCE(t.outbound_date, t.picked_date) <= ?"
        params.append(date_to)
    query += " ORDER BY COALESCE(t.outbound_date, t.picked_date) DESC"

    records = engine.db.fetchall(query, params)

    os.makedirs(output_dir, exist_ok=True)
    today = datetime.now().strftime('%Y%m%d')
    cust_tag = customer.replace(' ', '_')[:10] if customer else 'ALL'
    filename = f"거래명세서_{cust_tag}_{today}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=18*mm, bottomMargin=12*mm)

    styles = getSampleStyleSheet()
    elements = []

    # 제목
    elements.append(Paragraph("거 래 명 세 서",
        ParagraphStyle('Title', parent=styles['Title'], fontName=fn, fontSize=20,
                       spaceAfter=3, alignment=1)))
    elements.append(Paragraph("Transaction Statement",
        ParagraphStyle('Sub', parent=styles['Normal'], fontName=fn, fontSize=10,
                       textColor=colors.grey, alignment=1)))
    elements.append(Spacer(1, 6*mm))

    # 헤더 정보
    period_str = ''
    if date_from and date_to:
        period_str = f"{date_from} ~ {date_to}"
    elif date_from:
        period_str = f"{date_from} ~ 현재"
    else:
        period_str = "전체 기간"

    info_data = [
        ['수신', str(customer or '(전체)'), '기간', period_str],
        ['발신', 'GY Logistics', '문서일', datetime.now().strftime('%Y-%m-%d')],
    ]
    t = Table(info_data, colWidths=[50, 150, 50, 150])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), fn),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#34495e')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6*mm))

    # 거래 내역 테이블
    header = ['No.', 'LOT NO', '제품', 'SAP NO', '톤백#', '중량(kg)', '출고처', '출고일']
    data = [header]
    total_kg = 0.0

    for idx, r in enumerate(records, 1):
        w = float(r.get('weight', 0) or (r[2] if not isinstance(r, dict) else 0))
        total_kg += w
        lot = r.get('lot_no', '') if isinstance(r, dict) else r[0]
        sub = r.get('sub_lt', '') if isinstance(r, dict) else r[1]
        prod = (r.get('product', '') if isinstance(r, dict) else r[8]) or ''
        sap = (r.get('sap_no', '') if isinstance(r, dict) else r[9]) or ''
        p_to = (r.get('picked_to', '') if isinstance(r, dict) else r[4]) or ''
        o_date = (r.get('outbound_date', '') or r.get('picked_date', '')) if isinstance(r, dict) else (r[6] or r[5] or '')

        data.append([
            str(idx), str(lot), str(prod)[:15], str(sap),
            str(sub), f"{w:,.1f}", str(p_to)[:15], str(o_date)[:10]
        ])

    if not records:
        data.append(['', '(해당 거래 없음)', '', '', '', '', '', ''])

    data.append(['', '합계', '', '', f"{len(records)}건", f"{total_kg:,.1f}", f"{total_kg/1000:,.3f} MT", ''])

    t = Table(data, colWidths=[28, 68, 60, 55, 35, 55, 60, 55], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), fn),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (4, 0), (5, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#bdc3c7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f5f6fa')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
    ]))
    elements.append(t)

    # 푸터
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(
        f"생성: {datetime.now().strftime('%Y-%m-%d %H:%M')} | SQM v6.2.3 | GY Logistics",
        ParagraphStyle('Footer', parent=styles['Normal'], fontName=fn, fontSize=7,
                       textColor=colors.grey, alignment=1)))

    doc.build(elements)
    logger.info(f"거래명세서 생성: {filepath}")
    return filepath


def generate_lot_outbound_history_pdf(engine, lot_no: str, history: List[dict],
                                      output_path: str = None) -> Optional[str]:
    """
    LOT 출고 이력 PDF 생성 (톤백·샘플 출고/예약 이력)
    """
    if not _REPORTLAB_OK:
        return None

    _register_korean_font()
    fn = 'MalgunGothic' if _has_malgun() else 'Helvetica'

    lot_info = engine.db.fetchone("SELECT product FROM inventory WHERE lot_no = ?", (lot_no,))
    product = (lot_info.get('product', '-') or '-') if lot_info else '-'

    if not output_path:
        os.makedirs('output/reports', exist_ok=True)
        output_path = os.path.join('output/reports', f"출고이력_{lot_no}_{datetime.now().strftime('%Y%m%d')}.pdf")

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=18*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"LOT 출고 이력 — {lot_no}",
        ParagraphStyle('Title', parent=styles['Title'], fontName=fn, fontSize=14)))
    elements.append(Paragraph(f"{product}  |  {len(history)}건",
        ParagraphStyle('Sub', parent=styles['Normal'], fontName=fn, fontSize=10, textColor=colors.grey)))
    elements.append(Spacer(1, 6*mm))

    tb_data = [['No.', '톤백#', '중량(kg)', '구분', '상태', '출고처', '출고/예정일']]
    from .ui_constants import get_status_display
    for idx, row in enumerate(history, 1):
        is_sample = row.get('is_sample') or 0
        tb_type = '샘플' if is_sample else '정규'
        _st = str(row.get('tonbag_status', '')).strip()
        st = get_status_display(_st) or _st
        tb_data.append([
            str(idx), str(row.get('sub_lt', '')),
            f"{float(row.get('weight', 0) or 0):,.0f}",
            tb_type, st,
            str(row.get('customer', ''))[:15],
            str(row.get('out_date', ''))[:10]
        ])

    if not tb_data or len(tb_data) == 1:
        tb_data.append(['', '이력 없음', '', '', '', '', ''])

    t = Table(tb_data, colWidths=[30, 50, 70, 45, 50, 90, 75])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), fn),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#bdc3c7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f6fa')]),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8*mm))
    elements.append(Paragraph(f"(주) 지와이로지스  {datetime.now().strftime('%Y')}년 {datetime.now().strftime('%m')}월 {datetime.now().strftime('%d')}일",
        ParagraphStyle('Footer', parent=styles['Normal'], fontName=fn, fontSize=7, textColor=colors.grey)))
    doc.build(elements)
    logger.info(f"LOT 출고 이력 PDF: {output_path}")
    return output_path


# === 유틸 ===

def _has_malgun() -> bool:
    """맑은 고딕 등록 여부"""
    try:
        from reportlab.pdfbase import pdfmetrics
        return 'MalgunGothic' in pdfmetrics.getRegisteredFontNames()
    except (ImportError, ModuleNotFoundError):
        return False

def _register_korean_font() -> None:
    """한국어 폰트 등록"""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        if 'MalgunGothic' in pdfmetrics.getRegisteredFontNames():
            return

        font_paths = [
            'C:/Windows/Fonts/malgun.ttf',
            '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
            '/System/Library/Fonts/AppleGothic.ttf',
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                pdfmetrics.registerFont(TTFont('MalgunGothic', fp))
                return
    except (OSError, IOError, PermissionError) as e:
        logger.debug(f"한국어 폰트 등록 실패: {e}")
