"""
SQM v3.9.8 — PDF 재고 현황 보고서 생성기
==========================================

tkinter Canvas 기반 (외부 라이브러리 불필요)
→ HTML → PDF 변환 or 직접 Excel 보고서
"""

from engine_modules.constants import STATUS_AVAILABLE, STATUS_PICKED
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class PDFReportMixin:
    """PDF/HTML 재고 보고서 생성 Mixin"""

    def _generate_inventory_pdf_report(self) -> None:
        """v3.9.8: 재고 현황 PDF/HTML 보고서 생성"""
        from ..utils.ui_constants import CustomMessageBox

        try:
            # 데이터 수집
            stats = self._collect_report_data()
            if not stats:
                CustomMessageBox.showwarning(self.root, "경고", "보고서 데이터를 수집할 수 없습니다.")
                return

            # HTML 보고서 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_dir = os.path.join('output', 'reports')
            os.makedirs(report_dir, exist_ok=True)

            html_path = os.path.join(report_dir, f'inventory_report_{timestamp}.html')
            self._write_html_report(html_path, stats)

            # 결과 알림
            CustomMessageBox.showinfo(
                self.root, "보고서 생성 완료",
                f"재고 현황 보고서가 생성되었습니다.\n\n📄 {html_path}\n\n브라우저에서 열겠습니까?"
            )

            # 브라우저에서 열기
            try:
                import webbrowser
                webbrowser.open(os.path.abspath(html_path))
            except (OSError, IOError, PermissionError) as _e:
                logger.debug(f'Suppressed: {_e}')

            self._log(f"📊 재고 보고서 생성: {html_path}")

        except (OSError, IOError, PermissionError) as e:
            logger.error(f"보고서 생성 오류: {e}", exc_info=True)
            CustomMessageBox.showerror(self.root, "오류", f"보고서 생성 실패: {e}")

    def _collect_report_data(self) -> dict:
        """보고서용 데이터 수집"""
        try:
            db = self.engine.db

            # 재고 요약
            inv_summary = db.fetchone("""
                SELECT 
                    COUNT(*) as total_lots,
                    SUM(CASE WHEN status='AVAILABLE' THEN 1 ELSE 0 END) as avail_lots,
                    SUM(CASE WHEN status='DEPLETED' THEN 1 ELSE 0 END) as depleted_lots,
                    ROUND(COALESCE(SUM(initial_weight), 0) / 1000, 1) as total_initial_mt,
                    ROUND(COALESCE(SUM(current_weight), 0) / 1000, 1) as total_current_mt,
                    ROUND(COALESCE(SUM(picked_weight), 0) / 1000, 1) as total_picked_mt
                FROM inventory
                WHERE COALESCE(is_sample, 0) = 0
            """)

            # 톤백 요약
            tb_summary = db.fetchone("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status='AVAILABLE' THEN 1 ELSE 0 END) as available,
                    SUM(CASE WHEN status='PICKED' THEN 1 ELSE 0 END) as picked,
                    SUM(CASE WHEN status='SHIPPED' THEN 1 ELSE 0 END) as shipped
                FROM inventory_tonbag
                WHERE COALESCE(is_sample, 0) = 0
            """)

            # 제품별 재고
            products = db.fetchall("""
                SELECT 
                    product_code as product, 
                    COUNT(*) as lot_count,
                    ROUND(SUM(current_weight)/1000, 1) as current_mt
                FROM inventory
                WHERE COALESCE(is_sample, 0) = 0 AND status = 'AVAILABLE'
                GROUP BY product_code
                ORDER BY current_mt DESC
            """)

            # LOT 상세
            lots = db.fetchall("""
                SELECT 
                    lot_no, sap_no, bl_no, product_code, container_no,
                    status, ROUND(initial_weight, 0) as init_w,
                    ROUND(current_weight, 0) as curr_w,
                    mxbg_pallet, warehouse, arrival_date
                FROM inventory
                WHERE COALESCE(is_sample, 0) = 0
                ORDER BY lot_no
            """)

            return {
                'summary': dict(inv_summary) if inv_summary else {},
                'tonbag': dict(tb_summary) if tb_summary else {},
                'products': [dict(p) for p in (products or [])],
                'lots': [dict(l) for l in (lots or [])],
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"보고서 데이터 수집 오류: {e}")
            return None

    def _write_html_report(self, path: str, data: dict) -> None:
        """HTML 보고서 작성 (브라우저/PDF 인쇄 가능)"""
        s = data['summary']
        tb = data['tonbag']

        init_mt = float(s.get('total_initial_mt', 0) or 0)
        curr_mt = float(s.get('total_current_mt', 0) or 0)
        out_mt = init_mt - curr_mt
        pct = (out_mt / init_mt * 100) if init_mt > 0 else 0

        lots_html = ""
        for lot in data['lots']:
            status = lot.get('status', '')
            sc = '#27ae60' if status == STATUS_AVAILABLE else ('#e67e22' if status == STATUS_PICKED else '#e74c3c')
            lots_html += f"""
            <tr>
                <td>{lot.get('lot_no','')}</td>
                <td>{lot.get('sap_no','')}</td>
                <td>{lot.get('bl_no','')}</td>
                <td>{lot.get('product_code','')}</td>
                <td>{lot.get('container_no','')}</td>
                <td style="color:{sc};font-weight:bold">{status}</td>
                <td style="text-align:right">{float(lot.get('init_w',0)):,.0f}</td>
                <td style="text-align:right">{float(lot.get('curr_w',0)):,.0f}</td>
                <td>{lot.get('warehouse','')}</td>
                <td>{lot.get('arrival_date','')}</td>
            </tr>"""

        products_html = ""
        for p in data['products']:
            products_html += f"""
            <tr>
                <td>{p.get('product','')}</td>
                <td style="text-align:right">{p.get('lot_count',0)}</td>
                <td style="text-align:right">{float(p.get('current_mt',0)):,.1f} MT</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>SQM 재고 현황 보고서</title>
<style>
    @media print {{ body {{ margin: 10mm; }} }}
    body {{ font-family: '맑은 고딕', sans-serif; color: #2c3e50; max-width: 1000px; margin: 0 auto; padding: 20px; }}
    h1 {{ color: #2980b9; border-bottom: 3px solid #2980b9; padding-bottom: 10px; }}
    h2 {{ color: #34495e; margin-top: 30px; }}
    .cards {{ display: flex; gap: 15px; flex-wrap: wrap; margin: 20px 0; }}
    .card {{ flex: 1; min-width: 150px; padding: 15px; border-radius: 8px; color: white; text-align: center; }}
    .card .value {{ font-size: 24px; font-weight: bold; }}
    .card .label {{ font-size: 12px; opacity: 0.9; }}
    .progress {{ background: #ecf0f1; border-radius: 10px; height: 25px; margin: 10px 0; overflow: hidden; }}
    .progress-bar {{ height: 100%; border-radius: 10px; text-align: center; color: white; line-height: 25px; font-weight: bold; }}
    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px; }}
    th {{ background: #34495e; color: white; padding: 8px 6px; text-align: left; }}
    td {{ padding: 6px; border-bottom: 1px solid #ecf0f1; }}
    tr:hover {{ background: #f8f9fa; }}
    .footer {{ text-align: center; color: #95a5a6; margin-top: 30px; font-size: 11px; }}
</style>
</head>
<body>
<h1>📦 SQM 재고 현황 보고서</h1>
<p style="color:#7f8c8d">생성일시: {data['generated_at']} | SQM Inventory Management System</p>

<div class="cards">
    <div class="card" style="background:#3498db">
        <div class="value">{s.get('total_lots',0)}</div>
        <div class="label">총 LOT</div>
    </div>
    <div class="card" style="background:#27ae60">
        <div class="value">{curr_mt:,.1f} MT</div>
        <div class="label">현재 재고</div>
    </div>
    <div class="card" style="background:#e67e22">
        <div class="value">{out_mt:,.1f} MT</div>
        <div class="label">총 출고</div>
    </div>
    <div class="card" style="background:#9b59b6">
        <div class="value">{tb.get('available',0)}/{tb.get('total',0)}</div>
        <div class="label">판매가능/전체 톤백</div>
    </div>
</div>

<h2>📊 출고 진행률</h2>
<div class="progress">
    <div class="progress-bar" style="width:{pct:.0f}%;background:{'#27ae60' if pct < 50 else '#e67e22' if pct < 90 else '#e74c3c'}">
        {pct:.1f}%
    </div>
</div>
<p>입고: {init_mt:,.1f} MT | 출고: {out_mt:,.1f} MT | 잔량: {curr_mt:,.1f} MT</p>

<h2>📦 제품별 재고</h2>
<table>
<tr><th>제품</th><th style="text-align:right">LOT 수</th><th style="text-align:right">현재 재고</th></tr>
{products_html}
</table>

<h2>📋 LOT 상세 ({len(data['lots'])}건)</h2>
<table>
<tr><th>LOT NO</th><th>SAP NO</th><th>BL NO</th><th>제품</th><th>컨테이너</th>
    <th>상태</th><th style="text-align:right">Inbound(Kg)</th><th style="text-align:right">Balance(Kg)</th>
    <th>창고</th><th>입항일</th></tr>
{lots_html}
</table>

<div class="footer">
    SQM Inventory Management System v3.9.8 | Generated at {data['generated_at']}
</div>
</body></html>"""

        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
