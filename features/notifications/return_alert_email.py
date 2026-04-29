# -*- coding: utf-8 -*-
"""
SQM v7.5.0 — 반품 이메일 알림 모듈 (SMTP 완성)
================================================
반품 빈도 이상 감지 시 Gmail 앱 비밀번호 기반 SMTP 이메일 발송.

설정 파일: config_email.json (앱 루트 또는 바탕화면 생성 후 복사)
테스트: tests/test_return_enhanced.py → TestReturnEmailAlert
"""

import json
import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
# 설정 파일 경로
# ═══════════════════════════════════════════
_CONFIG_FILENAME = 'config_email.json'
_CONFIG_SEARCH_PATHS = [
    Path('.') / _CONFIG_FILENAME,
    Path(__file__).parent.parent.parent / _CONFIG_FILENAME,
]

_DEFAULT_CONFIG = {
    'enabled': False,
    'smtp_host': 'smtp.gmail.com',
    'smtp_port': 587,
    'smtp_user': '',
    'smtp_pass': '',          # Gmail 앱 비밀번호 (16자리)
    'from_addr': '',
    'recipients': [],         # 수신자 이메일 목록
    'threshold_count': 3,     # N건 이상 반품 시 알림
    'threshold_days': 30,     # 최근 N일 이내
    'company_name': '(주)지와이로지스',
    'warehouse': '광양 창고',
}


# ═══════════════════════════════════════════
# 설정 로드/저장
# ═══════════════════════════════════════════

def load_email_config() -> Dict:
    """config_email.json 로드. 없으면 기본값 반환."""
    for p in _CONFIG_SEARCH_PATHS:
        if p.exists():
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                merged = dict(_DEFAULT_CONFIG)
                merged.update(cfg)
                return merged
            except Exception as e:
                logger.warning(f"config_email.json 로드 실패: {e}")
    return dict(_DEFAULT_CONFIG)


def save_email_config(config: Dict, path: str = None) -> bool:
    """설정 저장."""
    target = Path(path) if path else (_CONFIG_SEARCH_PATHS[1])
    try:
        with open(target, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.info(f"이메일 설정 저장: {target}")
        return True
    except Exception as e:
        logger.error(f"설정 저장 실패: {e}")
        return False


def create_default_email_config(directory: str = '.') -> str:
    """바탕화면 등에 기본 config_email.json 템플릿 생성."""
    path = Path(directory) / _CONFIG_FILENAME
    cfg = dict(_DEFAULT_CONFIG)
    cfg['_guide'] = (
        "smtp_pass: Gmail → 구글 계정 → 보안 → 앱 비밀번호 (16자리) 입력. "
        "enabled를 true로 변경해야 발송됩니다."
    )
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return str(path)


# ═══════════════════════════════════════════
# 알림 감지
# ═══════════════════════════════════════════

def check_return_alerts(engine) -> List[Dict]:
    """반품 이상 감지 — threshold 초과 LOT 목록 반환."""
    config = load_email_config()
    threshold = config.get('threshold_count', 3)
    days = config.get('threshold_days', 30)
    alerts = []
    try:
        rows = engine.db.fetchall(
            """SELECT lot_no, COUNT(*) as cnt, MAX(return_date) as latest
               FROM return_history
               WHERE return_date >= date('now', ? || ' days')
               GROUP BY lot_no
               HAVING COUNT(*) >= ?
               ORDER BY cnt DESC""",
            (f'-{days}', threshold)
        )
        for row in (rows or []):
            r = dict(row) if not isinstance(row, dict) else row
            alerts.append({
                'lot_no': r.get('lot_no', ''),
                'count': int(r.get('cnt', 0)),
                'latest_date': r.get('latest', ''),
            })
    except Exception as e:
        logger.warning(f"[반품알림] 조회 실패: {e}")
    return alerts


# ═══════════════════════════════════════════
# 이메일 발송
# ═══════════════════════════════════════════

def _build_html_body(alerts: List[Dict], config: Dict) -> str:
    """HTML 이메일 본문 생성."""
    company = config.get('company_name', '')
    warehouse = config.get('warehouse', '')
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    rows = ''.join(
        f"<tr><td>{a['lot_no']}</td><td>{a['count']}회</td><td>{a['latest_date']}</td></tr>"
        for a in alerts
    )
    return f"""
<html><body>
<h2>📦 {company} — 반품 경고 알림</h2>
<p>창고: {warehouse} &nbsp;|&nbsp; 발송 시각: {now}</p>
<p>아래 LOT에서 반복 반품이 감지되었습니다. 확인 바랍니다.</p>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
  <tr style="background:#f0f0f0">
    <th>LOT 번호</th><th>반품 횟수</th><th>최근 반품일</th>
  </tr>
  {rows}
</table>
<br><p style="color:gray;font-size:12px">이 메일은 SQM 재고관리 시스템에서 자동 발송되었습니다.</p>
</body></html>"""


def send_return_alert_email(engine, config: Dict = None) -> Dict:
    """반품 알림 이메일 SMTP 발송.

    Returns:
        dict: {'sent': bool, 'alert_count': int, 'message': str, 'error': str}
    """
    if config is None:
        config = load_email_config()

    result = {'sent': False, 'alert_count': 0, 'message': '', 'error': ''}

    if not config.get('enabled', False):
        result['message'] = '이메일 알림 비활성화'
        result['error'] = '이메일 알림 비활성화'
        return result

    alerts = check_return_alerts(engine)
    result['alert_count'] = len(alerts)

    if not alerts:
        result['message'] = '알림 대상 없음'
        return result

    recipients = config.get('recipients', [])
    if not recipients:
        result['error'] = '수신자(recipients) 미설정'
        return result

    smtp_host = config.get('smtp_host', 'smtp.gmail.com')
    smtp_port = int(config.get('smtp_port', 587))
    smtp_user = config.get('smtp_user', '')
    smtp_pass = config.get('smtp_pass', '')
    from_addr = config.get('from_addr', smtp_user)

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[SQM 반품 경고] {len(alerts)}건 반복 반품 감지"
        msg['From'] = from_addr
        msg['To'] = ', '.join(recipients)

        html_body = _build_html_body(alerts, config)
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, recipients, msg.as_string())

        result['sent'] = True
        result['message'] = f'{len(alerts)}건 알림 이메일 발송 완료'
        logger.info(f"[반품알림] 이메일 발송 완료: {len(alerts)}건 → {recipients}")

    except smtplib.SMTPAuthenticationError:
        result['error'] = 'SMTP 인증 실패 — Gmail 앱 비밀번호를 확인하세요.'
        logger.error("[반품알림] SMTP 인증 실패")
    except smtplib.SMTPException as e:
        result['error'] = f'SMTP 오류: {e}'
        logger.error(f"[반품알림] SMTP 오류: {e}")
    except Exception as e:
        result['error'] = f'발송 오류: {e}'
        logger.error(f"[반품알림] 발송 오류: {e}")

    return result
