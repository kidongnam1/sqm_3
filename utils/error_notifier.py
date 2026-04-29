# -*- coding: utf-8 -*-
"""
utils/error_notifier.py — SQM v8.3.0
======================================
에러 발생 시 이메일 알림 모듈

사용 예:
    from utils.error_notifier import notify_error, notify_integrity_fail

    # 정합성 오류 알림
    notify_integrity_fail('GY-2026-001', ['무게 불일치: 500kg vs 499kg'])

    # 파싱 실패 알림
    notify_error('PARSING_FAIL', 'MEDUFP963988_DO.pdf 파싱 실패')

설정 (config.py에 추가):
    NOTIFY_EMAIL_ENABLED = True
    NOTIFY_EMAIL_TO      = 'kidongnam1@gmail.com'
    NOTIFY_EMAIL_FROM    = 'sqm-alert@yourdomain.com'
    NOTIFY_SMTP_HOST     = 'smtp.gmail.com'
    NOTIFY_SMTP_PORT     = 587
    NOTIFY_SMTP_USER     = 'sqm-alert@yourdomain.com'
    NOTIFY_SMTP_PASS     = 'your_app_password'
"""

import logging
import smtplib
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── 알림 레벨 상수 ────────────────────────────────────────────────
LEVEL_INFO    = 'INFO'
LEVEL_WARNING = 'WARNING'
LEVEL_ERROR   = 'ERROR'
LEVEL_CRITICAL = 'CRITICAL'


def _load_notify_config() -> dict:
    """config.py에서 알림 설정 로드. 없으면 기본값."""
    cfg = {
        'enabled':   False,
        'to':        '',
        'from_addr': 'sqm-noreply@localhost',
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': 587,
        'smtp_user': '',
        'smtp_pass': '',
    }
    try:
        import config as _cfg
        cfg['enabled']   = getattr(_cfg, 'NOTIFY_EMAIL_ENABLED', False)
        cfg['to']        = getattr(_cfg, 'NOTIFY_EMAIL_TO', '')
        cfg['from_addr'] = getattr(_cfg, 'NOTIFY_EMAIL_FROM', cfg['from_addr'])
        cfg['smtp_host'] = getattr(_cfg, 'NOTIFY_SMTP_HOST', cfg['smtp_host'])
        cfg['smtp_port'] = getattr(_cfg, 'NOTIFY_SMTP_PORT', cfg['smtp_port'])
        cfg['smtp_user'] = getattr(_cfg, 'NOTIFY_SMTP_USER', '')
        cfg['smtp_pass'] = getattr(_cfg, 'NOTIFY_SMTP_PASS', '')
    except ImportError:
        pass  # noqa: intentional — optional dependency
    return cfg


def _send_email(subject: str, body_html: str, cfg: dict) -> bool:
    """SMTP 이메일 전송."""
    if not cfg.get('enabled') or not cfg.get('to'):
        logger.debug("[Notify] 이메일 알림 비활성화 또는 수신자 미설정")
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = cfg['from_addr']
        msg['To']      = cfg['to']
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        with smtplib.SMTP(cfg['smtp_host'], cfg['smtp_port'], timeout=10) as server:
            server.ehlo()
            server.starttls()
            if cfg.get('smtp_user') and cfg.get('smtp_pass'):
                server.login(cfg['smtp_user'], cfg['smtp_pass'])
            server.sendmail(cfg['from_addr'], cfg['to'], msg.as_string())

        logger.info(f"[Notify] 이메일 전송 완료 → {cfg['to']}: {subject}")
        return True
    except Exception as e:
        logger.warning(f"[Notify] 이메일 전송 실패: {e}")
        return False


def _build_html(
    title: str,
    level: str,
    items: List[str],
    detail: Optional[str] = None,
) -> str:
    """이메일 HTML 본문 생성."""
    color_map = {
        LEVEL_INFO:     '#2196F3',
        LEVEL_WARNING:  '#FF9800',
        LEVEL_ERROR:    '#F44336',
        LEVEL_CRITICAL: '#9C27B0',
    }
    color = color_map.get(level, '#607D8B')
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    rows = ''.join(f'<li style="margin:4px 0">{item}</li>' for item in items)
    detail_block = (
        f'<pre style="background:#f5f5f5;padding:10px;border-radius:4px;'
        f'font-size:12px;overflow-x:auto">{detail}</pre>'
        if detail else ''
    )

    return f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px">
  <div style="background:{color};color:#fff;padding:12px 16px;border-radius:6px 6px 0 0">
    <h2 style="margin:0;font-size:18px">⚠️ SQM 재고관리 시스템 알림</h2>
    <p style="margin:4px 0;font-size:13px;opacity:.85">{level} — {now_str}</p>
  </div>
  <div style="border:1px solid #ddd;border-top:none;padding:16px;border-radius:0 0 6px 6px">
    <h3 style="color:{color};margin-top:0">{title}</h3>
    <ul style="padding-left:20px">{rows}</ul>
    {detail_block}
    <hr style="border:none;border-top:1px solid #eee;margin:16px 0">
    <p style="font-size:11px;color:#999">
      광양 창고 SQM 재고관리 시스템 자동 발송 메일입니다.<br>
      발신 전용 메일입니다. 회신하지 마세요.
    </p>
  </div>
</body></html>"""


def notify_error(
    event_type: str,
    message: str,
    level: str = LEVEL_ERROR,
    detail: Optional[str] = None,
) -> bool:
    """
    일반 에러 알림.

    Args:
        event_type : 이벤트 구분 (예: 'PARSING_FAIL', 'DB_ERROR')
        message    : 알림 메시지
        level      : LEVEL_* 상수
        detail     : 추가 상세 (traceback 등)
    """
    cfg = _load_notify_config()
    subject = f"[SQM {level}] {event_type}"
    body = _build_html(
        title  = f"{event_type}: {message}",
        level  = level,
        items  = [message],
        detail = detail,
    )
    return _send_email(subject, body, cfg)


def notify_integrity_fail(
    lot_no: str,
    errors: List[str],
    warnings: Optional[List[str]] = None,
) -> bool:
    """
    LOT 정합성 오류 알림.

    Args:
        lot_no   : 오류 발생 LOT 번호
        errors   : 오류 메시지 목록
        warnings : 경고 메시지 목록
    """
    cfg = _load_notify_config()
    subject = f"[SQM ERROR] 정합성 오류 — {lot_no}"
    items = [f"🔴 {e}" for e in errors]
    if warnings:
        items += [f"🟡 {w}" for w in warnings]

    body = _build_html(
        title  = f"LOT {lot_no} 정합성 오류 감지",
        level  = LEVEL_ERROR,
        items  = items,
    )
    # 로그에도 기록
    logger.error(f"[Notify] 정합성 오류 — {lot_no}: {errors}")
    return _send_email(subject, body, cfg)


def notify_parsing_fail(
    filename: str,
    doc_type: str,
    reason: str,
) -> bool:
    """
    문서 파싱 실패 알림.

    Args:
        filename : 파싱 실패 파일명
        doc_type : 'BL' | 'DO' | 'PL' | 'Invoice'
        reason   : 실패 원인
    """
    cfg = _load_notify_config()
    subject = f"[SQM WARNING] {doc_type} 파싱 실패 — {filename}"
    body = _build_html(
        title  = f"{doc_type} 파싱 실패",
        level  = LEVEL_WARNING,
        items  = [
            f"파일: {filename}",
            f"문서 종류: {doc_type}",
            f"원인: {reason}",
        ],
    )
    logger.warning(f"[Notify] 파싱 실패 — {filename} ({doc_type}): {reason}")
    return _send_email(subject, body, cfg)


def notify_daily_summary(
    date_str: str,
    inbound_cnt: int,
    outbound_cnt: int,
    return_cnt: int,
    total_weight_kg: float,
    errors: Optional[List[str]] = None,
) -> bool:
    """
    일별 처리 요약 알림.

    Args:
        date_str        : 날짜 문자열 (예: '2026-03-23')
        inbound_cnt     : 입고 건수
        outbound_cnt    : 출고 건수
        return_cnt      : 반품 건수
        total_weight_kg : 당일 처리 총 중량
        errors          : 당일 발생 오류 목록
    """
    cfg = _load_notify_config()
    subject = f"[SQM 일보] {date_str} 처리 현황"
    items = [
        f"📥 입고: {inbound_cnt}건",
        f"📤 출고: {outbound_cnt}건",
        f"🔄 반품: {return_cnt}건",
        f"⚖️  처리 총중량: {total_weight_kg:,.0f} kg",
    ]
    if errors:
        items.append(f"⚠️ 오류 {len(errors)}건 발생")
        items += [f"   · {e}" for e in errors[:5]]

    body = _build_html(
        title  = f"{date_str} 광양 창고 처리 현황",
        level  = LEVEL_INFO,
        items  = items,
    )
    return _send_email(subject, body, cfg)
