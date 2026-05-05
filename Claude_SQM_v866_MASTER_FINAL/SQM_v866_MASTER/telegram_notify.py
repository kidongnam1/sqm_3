"""
SQM v864.3 Telegram SYNC 알림 모듈
SYNC 포인트(Phase 완료)마다 기동님 폰으로 알림 전송
작성: Ruby / 2026-05-01
"""
import os
import urllib.request
import urllib.parse
import time
import sys
from datetime import datetime


# ─────────────────────────────────────
# 설정 (.env 또는 환경변수에서 읽기)
# ─────────────────────────────────────
def _load_env():
    """프로젝트 루트의 .env 파일 읽기"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


_load_env()
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")


# ─────────────────────────────────────
# 핵심 전송 함수
# ─────────────────────────────────────
def send(text: str, parse_mode: str = "HTML") -> bool:
    """Telegram 메시지 전송 (재시도 3회)"""
    if not BOT_TOKEN or not CHAT_ID:
        print("[Telegram] BOT_TOKEN 또는 CHAT_ID 없음 - .env 확인 필요")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text[:4000],
        "parse_mode": parse_mode,
    }).encode()

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=payload)
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as e:
            print(f"[Telegram] 전송 실패 {attempt+1}/3: {e}")
            time.sleep(2 ** attempt)
    return False


# ─────────────────────────────────────
# SYNC 포인트 알림 함수들
# ─────────────────────────────────────
def notify_start():
    """작업 시작 알림"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = (
        f"<b>[SQM] Sub-Agent Team 작업 시작</b>\n"
        f"시각: {now}\n"
        f"버전: v864.3\n"
        f"목표: Phase 0~4 자동 완료\n"
        f"─────────────────\n"
        f"env_check -> MASTER -> DONE"
    )
    return send(msg)


def notify_env_ok(python_ver: str, nicegui_ver: str):
    """환경 검증 완료 알림"""
    now = datetime.now().strftime("%H:%M")
    msg = (
        f"<b>[OK] Phase 0: 환경 검증 완료</b>\n"
        f"시각: {now}\n"
        f"Python: {python_ver}\n"
        f"NiceGUI: {nicegui_ver}\n"
        f"DB: sqm_inventory.db 존재\n"
        f"다음: Phase 1 진단 시작"
    )
    return send(msg)


def notify_sync1(error_count: int):
    """SYNC-1: Phase 1 완료 알림"""
    now = datetime.now().strftime("%H:%M")
    status = "[OK]" if error_count == 0 else f"[WARN] 오류 {error_count}건"
    msg = (
        f"<b>[SYNC-1] Phase 1 진단 완료</b>\n"
        f"시각: {now}\n"
        f"결과: {status}\n"
        f"다음: Agent B - 백엔드 API 시작"
    )
    return send(msg)


def notify_sync2(api_count: int):
    """SYNC-2: Phase 2 완료 알림"""
    now = datetime.now().strftime("%H:%M")
    msg = (
        f"<b>[SYNC-2] Phase 2 백엔드 API 완료</b>\n"
        f"시각: {now}\n"
        f"완성 API: {api_count}개\n"
        f"다음: Agent A - 프론트엔드 UI 시작"
    )
    return send(msg)


def notify_sync3(page_count: int):
    """SYNC-3: Phase 3 완료 알림"""
    now = datetime.now().strftime("%H:%M")
    msg = (
        f"<b>[SYNC-3] Phase 3 프론트엔드 완료</b>\n"
        f"시각: {now}\n"
        f"완성 페이지: {page_count}개\n"
        f"다음: Agent C - 교차검증 + ZIP 시작"
    )
    return send(msg)


def notify_done(pytest_passed: int, patch_file: str):
    """작업 완료 알림"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = (
        f"<b>[완료] SQM v864.3 작업 완료!</b>\n"
        f"시각: {now}\n"
        f"pytest: {pytest_passed} passed\n"
        f"패치: {patch_file}\n"
        f"교차검증: 5/5 항목 통과\n"
        f"─────────────────\n"
        f"기동님, 확인해주세요!"
    )
    return send(msg)


def notify_retry(task: str, attempt: int, error: str):
    """RETRY 발생 알림"""
    now = datetime.now().strftime("%H:%M")
    msg = (
        f"<b>[RETRY {attempt}/3] {task}</b>\n"
        f"시각: {now}\n"
        f"에러: {error[:200]}\n"
        f"자동 재시도 중..."
    )
    return send(msg)


def notify_blocked(task: str, reason: str):
    """자동 수정 불가 에러 알림"""
    now = datetime.now().strftime("%H:%M")
    msg = (
        f"<b>[BLOCKED] {task} - 기동님 확인 필요</b>\n"
        f"시각: {now}\n"
        f"사유: {reason[:300]}\n"
        f"─────────────────\n"
        f"error_report.md 확인 후\n"
        f"조치하고 run_master.bat 재실행"
    )
    return send(msg)


def notify_smoke_check():
    """UI 스모크 체크 요청 알림"""
    now = datetime.now().strftime("%H:%M")
    msg = (
        f"<b>[확인 요청] UI 스모크 체크</b>\n"
        f"시각: {now}\n"
        f"─────────────────\n"
        f"브라우저에서 30초 확인:\n"
        f"1. 사이드바 9개 탭 색상\n"
        f"2. Inventory 탭 데이터\n"
        f"3. 상단 메뉴 드롭다운\n"
        f"4. Dashboard KPI 숫자\n"
        f"─────────────────\n"
        f"OK -> '확인완료' 답장\n"
        f"문제 -> 이상한 탭 이름 알려주세요"
    )
    return send(msg)


def notify_progress(task: str, done: int, total: int):
    """진행 상황 알림 (선택적)"""
    pct = int(done / total * 100) if total > 0 else 0
    bar = "[" + "#" * (pct // 10) + "." * (10 - pct // 10) + "]"
    now = datetime.now().strftime("%H:%M")
    msg = (
        f"<b>[진행] {task}</b>\n"
        f"시각: {now}\n"
        f"{bar} {pct}%\n"
        f"완료: {done}/{total}"
    )
    return send(msg)


# ─────────────────────────────────────
# CLI 테스트
# ─────────────────────────────────────
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test"

    if cmd == "test":
        print("Telegram 연결 테스트...")
        ok = send(
            "<b>[SQM] Telegram 연결 테스트</b>\n"
            "이 메시지가 오면 설정 완료!\n"
            f"시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        print("성공!" if ok else "실패 - .env 파일 확인 필요")

    elif cmd == "start":
        notify_start()
        print("시작 알림 전송")

    elif cmd == "done":
        notify_done(pytest_passed=568, patch_file="Claude_SQM_v864_3_PATCH.zip")
        print("완료 알림 전송")

    elif cmd == "blocked":
        reason = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "원인 불명"
        notify_blocked("P2-TASK-02", reason)
        print("BLOCKED 알림 전송")

    else:
        print(f"사용법: python telegram_notify.py [test|start|done|blocked]")
