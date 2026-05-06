"""
SQM Inventory — PyWebView 진입점 (Tkinter 대체)
실행: python main_webview.py

=== v8.6.6 Debug Visibility 패치 (에러 은폐 차단) ===
1. sys.excepthook / threading.excepthook — 미포획 예외 전부 파일 기록
2. FileHandler — 모든 로그를 sqm_debug.log 에 항상 기록 (frozen 아닐 때도)
3. uvicorn log_level="debug" + access_log=True — 백엔드 요청/에러 완전 노출
4. JS window.onerror / unhandledrejection — 프론트 에러 → /api/log/frontend-error 전송
"""
import threading
import time
import os
import sys
import logging
import traceback
import json

# ─────────────────────────────────────────────────────────────
# [Patch 1] 로그 파일 기본 경로 결정 + stdout/stderr 폴백
# ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')
API_HOST = '127.0.0.1'
API_PORT = 8765

# frozen(EXE)이면 exe 옆, 아니면 프로젝트 루트에 로그 파일 생성
if getattr(sys, 'frozen', False):
    LOG_DIR = os.path.dirname(sys.executable)
else:
    LOG_DIR = BASE_DIR
LOG_PATH = os.path.join(LOG_DIR, 'sqm_debug.log')
WINDOW_STATE_PATH = os.path.join(BASE_DIR, 'window_state.json')

# PyInstaller frozen exe (console=False) 에서 stdout/stderr가 None →
# logging StreamHandler가 터지는 것을 방지: 로그 파일로 리다이렉트
if getattr(sys, 'frozen', False) and sys.stdout is None:
    _log_file = open(LOG_PATH, 'a', encoding='utf-8', buffering=1)
    sys.stdout = _log_file
    sys.stderr = _log_file

# ─────────────────────────────────────────────────────────────
# [Patch 2] 로그 설정 — 콘솔 + 파일 동시 기록 (DEBUG 레벨)
# ─────────────────────────────────────────────────────────────
_fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.DEBUG)
# 중복 방지: 기존 핸들러 제거
for _h in list(_root_logger.handlers):
    _root_logger.removeHandler(_h)
# 콘솔 핸들러 (INFO 이상)
_console_h = logging.StreamHandler()
_console_h.setLevel(logging.INFO)
_console_h.setFormatter(logging.Formatter(_fmt))
_root_logger.addHandler(_console_h)
# 파일 핸들러 (DEBUG 이상 전부)
try:
    _file_h = logging.FileHandler(LOG_PATH, encoding='utf-8')
    _file_h.setLevel(logging.DEBUG)
    _file_h.setFormatter(logging.Formatter(_fmt))
    _root_logger.addHandler(_file_h)
except Exception as _e:
    print(f"[WARN] 로그 파일 핸들러 실패: {_e}")

log = logging.getLogger(__name__)
log.info(f"=== SQM v8.6.6 시작 — 로그 파일: {LOG_PATH} ===")

# ─────────────────────────────────────────────────────────────
# [Patch 3] 전역 예외 훅 — 미포획 예외 전부 로그 파일에 기록
# ─────────────────────────────────────────────────────────────
def _excepthook(exc_type, exc_value, exc_tb):
    """메인 스레드의 미포획 예외"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.critical(f"[UNCAUGHT-MAIN] {exc_type.__name__}: {exc_value}\n{tb_text}")

def _thread_excepthook(args):
    """서브 스레드(FastAPI/uvicorn 등)의 미포획 예외"""
    tb_text = "".join(traceback.format_exception(
        args.exc_type, args.exc_value, args.exc_traceback
    ))
    log.critical(
        f"[UNCAUGHT-THREAD] thread={args.thread.name if args.thread else '?'} "
        f"{args.exc_type.__name__}: {args.exc_value}\n{tb_text}"
    )

sys.excepthook = _excepthook
threading.excepthook = _thread_excepthook
log.debug("전역 예외 훅 설치 완료 (main + thread)")

def load_window_state():
    """마지막 창 크기 + 최대화 상태를 window_state.json 에서 불러옴"""
    defaults = (1400, 900, False)
    try:
        with open(WINDOW_STATE_PATH, encoding='utf-8') as f:
            s = json.load(f)
            maximized = bool(s.get('maximized', False))
            if maximized:
                # 최대화 상태였으면 기본 크기로 창을 만들고 나중에 maximize() 호출
                log.info('창 상태 복원: 최대화')
                return 1400, 900, True
            w = int(s.get('width', 1400))
            h = int(s.get('height', 900))
            w = max(1024, min(w, 3840))
            h = max(700,  min(h, 2160))
            log.info(f'창 크기 복원: {w}x{h} (최대화: 아님)')
            return w, h, False
    except FileNotFoundError:
        return defaults
    except Exception as e:
        log.warning(f'window_state.json 로드 실패: {e}')
        return defaults

def save_window_state(width, height, maximized=False):
    """창 크기 + 최대화 상태를 window_state.json 에 저장"""
    try:
        with open(WINDOW_STATE_PATH, 'w', encoding='utf-8') as f:
            json.dump({'width': width, 'height': height, 'maximized': maximized}, f)
        log.debug(f'창 상태 저장: {width}x{height} 최대화={maximized}')
    except Exception as e:
        log.warning(f'창 상태 저장 실패: {e}')

def run_api_server():
    """FastAPI 서버를 별도 스레드에서 실행

    [Patch] v8.6.6: log_level="debug" + access_log=True
    → 모든 HTTP 요청/응답/500 에러 전부 콘솔+파일에 기록
    [P11 PATCH 2026-05-06] uvicorn 로거 propagate 분리
    → 이전: uvicorn INFO 메시지가 SQM root 로거로 propagate 되어 [ERROR] root: 로 이중 표시
    → 수정: uvicorn 자체 로거의 propagate=False 로 SQM 로깅과 분리
    """
    try:
        import uvicorn
        from backend.api import app
        # [P11 PATCH] uvicorn 로거 분리 (SQM root 로거로의 propagate 차단).
        # uvicorn 은 자체 핸들러로 stdout 에 출력하므로 SQM 로깅이 중복 캡처 안 함.
        for _uv_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            logging.getLogger(_uv_logger_name).propagate = False
        uvicorn.run(
            app,
            host=API_HOST,
            port=API_PORT,
            log_level="debug",       # warning → debug (모든 요청 보임)
            access_log=True,         # 요청 로그 활성화
        )
    except Exception as e:
        log.exception(f"API 서버 시작 실패: {e}")

def is_port_open(host, port):
    """TCP 소켓이 LISTEN 상태인지 (다른 프로세스가 점유 중인지) 확인"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        try: s.close()
        except Exception: pass

def kill_zombie_on_port(port):
    """
    Windows 한정: 해당 포트를 LISTEN 하는 프로세스(좀비) 를 종료.
    이전 세션에서 창 X 로 닫고 프로세스가 살아남은 경우 재실행을 가능하게 함.
    """
    if os.name != 'nt':
        return False
    import subprocess, re
    try:
        out = subprocess.check_output(
            ['netstat', '-ano', '-p', 'tcp'],
            text=True, encoding='cp949', errors='ignore'
        )
    except Exception as e:
        log.warning(f"netstat 실패: {e}")
        return False
    killed = False
    for line in out.splitlines():
        if f':{port}' not in line or 'LISTENING' not in line:
            continue
        parts = re.split(r'\s+', line.strip())
        if not parts:
            continue
        pid = parts[-1]
        if not pid.isdigit():
            continue
        # 자기 자신 PID 는 건너뛰기
        if int(pid) == os.getpid():
            continue
        log.warning(f"좀비 uvicorn 감지 (PID={pid}, port={port}) → 종료 시도")
        try:
            subprocess.run(['taskkill', '/F', '/PID', pid],
                           check=False, timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            killed = True
        except Exception as e:
            log.error(f"taskkill PID={pid} 실패: {e}")
    if killed:
        time.sleep(0.7)  # OS 가 포트 놓을 시간
    return killed

def wait_for_api(timeout=10):
    """API 서버가 준비될 때까지 대기. /api/health 없으면 루트 '/' 로 폴백."""
    import urllib.request
    deadline = time.time() + timeout
    probes = [f'http://{API_HOST}:{API_PORT}/api/health',
              f'http://{API_HOST}:{API_PORT}/']
    while time.time() < deadline:
        for url in probes:
            try:
                urllib.request.urlopen(url, timeout=1)
                log.info(f"API 서버 준비 완료 ({url})")
                return True
            except Exception:
                pass
        time.sleep(0.3)
    log.warning("API 서버 연결 타임아웃 — 오프라인 모드로 진행")
    return False

# ===========================================================================
# [P1 PATCH 2026-05-06] 스플래시 창 즉시 표시 (UI thread async)
# ---------------------------------------------------------------------------
# 기존: main() 이 kill_zombie_on_port(최대 5.7s) + wait_for_api(최대 10s) 를
#       메인 스레드에서 동기 호출 -> 사용자는 창이 뜨기 전 최대 ~15.7초 freeze 체감.
# 해결: 백엔드 부트스트랩(좀비 정리 + API 서버 시작)을 백그라운드 스레드로 위임.
#       PyWebView 창은 즉시 SPLASH_HTML 로 표시되며, webview.start(func=...) 콜백에서
#       wait_for_api() 백그라운드 대기 후 실제 URL 로 navigate 한다.
# ===========================================================================

SPLASH_HTML = '''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>SQM Inventory — 시작 중</title>
<style>
  html, body { margin:0; padding:0; height:100vh; background:#070e1a; }
  body {
    color:#e2e8f0;
    font-family:'Segoe UI','Malgun Gothic',sans-serif;
    display:flex; flex-direction:column;
    justify-content:center; align-items:center;
    user-select:none; -webkit-user-select:none;
  }
  h1 { font-size:32px; font-weight:800; margin:0 0 8px; color:#f59e0b; }
  .sub { font-size:16px; color:#94a3b8; margin-bottom:32px; }
  .spinner {
    width:48px; height:48px;
    border:4px solid #1e293b;
    border-top-color:#f59e0b;
    border-radius:50%;
    animation:spin 1s linear infinite;
  }
  @keyframes spin { to { transform:rotate(360deg); } }
  .ver { position:absolute; bottom:20px; right:20px;
         font-size:12px; color:#475569; }
</style>
</head>
<body>
  <h1>SQM Inventory</h1>
  <p class="sub">광양창고 시스템을 시작하는 중...</p>
  <div class="spinner"></div>
  <div class="ver">v8.6.6</div>
</body>
</html>
'''


def main():
    log.info("=== SQM 시작 (Splash 즉시 표시 모드) ===")

    # [P1 PATCH] 백엔드 부트스트랩(좀비 청소 + API 서버 시작)을 백그라운드 스레드로 위임.
    # 메인 스레드는 즉시 webview 창 생성으로 진입 -> 사용자에게 0.3~1초 안에 창이 보임.
    def _setup_backend():
        try:
            if is_port_open(API_HOST, API_PORT):
                log.warning(f"포트 {API_PORT} 선점 상태 -> 좀비 uvicorn 제거")
                kill_zombie_on_port(API_PORT)
                if is_port_open(API_HOST, API_PORT):
                    log.error(
                        f"포트 {API_PORT} 가 여전히 점유됨. 수동 확인 필요:\n"
                        f'  netstat -ano | findstr :{API_PORT}'
                    )
            run_api_server()
        except Exception as e:
            log.exception(f"백엔드 부트스트랩 실패: {e}")

    backend_thread = threading.Thread(
        target=_setup_backend, daemon=True, name="sqm-backend-bootstrap"
    )
    backend_thread.start()
    log.info(f"API 서버 + 좀비 청소 백그라운드 시작 (http://{API_HOST}:{API_PORT})")

    # 3. PyWebView 창 생성 (스플래시 즉시 -> API 준비 후 메인 URL navigate)
    try:
        import webview
        from webview import FileDialog

        class SqmPywebviewApi:
            """JS ↔ Python: 엑셀 다운로드를 네이티브 '다른 이름으로 저장'으로 처리 (Blob 다운로드 미동작 대비)."""

            def save_download_url(
                self,
                url: str,
                suggested_filename: str = "SQM-export.xlsx",
                open_after_save: bool = False,
            ) -> dict:
                """
                엑셀 내보내기 저장.

                BUG-003 수정 (2026-05-04):
                  구: download(timeout=300) → dialog  ← 최대 5분 UI 동결
                  신: dialog 먼저 → download(timeout=60) → write
                     취소 시 불필요한 서버 부하 없음
                """
                try:
                    import urllib.request

                    u = str(url or "").strip()
                    if not u.startswith(("http://127.0.0.1:", "http://localhost:")):
                        return {"ok": False, "error": "로컬 API URL만 허용됩니다."}

                    # 1단계: 저장 경로 선택 (다운로드 없이 즉시 응답)
                    wins = webview.windows
                    if not wins:
                        return {"ok": False, "error": "webview 창이 없습니다."}
                    win = wins[0]

                    fname = (suggested_filename or "SQM-export.xlsx").strip()
                    if not fname.lower().endswith(".xlsx"):
                        fname += ".xlsx"

                    paths = win.create_file_dialog(
                        FileDialog.SAVE,
                        save_filename=fname,
                    )
                    if paths is None:
                        return {"ok": False, "cancelled": True}
                    path = paths[0] if isinstance(paths, (list, tuple)) else paths
                    if not path or not isinstance(path, str):
                        return {"ok": False, "error": "저장 경로를 확인할 수 없습니다."}

                    # 2단계: 다운로드 (dialog 후 → timeout=60s)
                    req = urllib.request.Request(
                        u,
                        headers={"User-Agent": "SQM-PyWebView-Export/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        body = resp.read()
                    if not body:
                        return {"ok": False, "error": "서버 응답이 비어 있습니다."}

                    # 3단계: 파일 기록
                    with open(path, "wb") as f:
                        f.write(body)
                    log.info("PyWebView 엑셀 저장: %d bytes -> %s", len(body), path)

                    opened = False
                    open_error = None
                    if open_after_save:
                        try:
                            if sys.platform == "win32":
                                os.startfile(path)  # noqa: S606
                                opened = True
                            elif sys.platform == "darwin":
                                import subprocess

                                subprocess.run(["open", path], check=False)
                                opened = True
                            else:
                                import subprocess

                                subprocess.run(["xdg-open", path], check=False)
                                opened = True
                        except Exception as oe:
                            open_error = str(oe)
                            log.warning("저장 후 파일 열기 실패: %s", oe)

                    out = {"ok": True, "path": path, "opened": opened}
                    if open_error:
                        out["open_error"] = open_error
                    return out
                except Exception as e:
                    log.exception("save_download_url 실패")
                    return {"ok": False, "error": str(e)}

        index_path = os.path.join(FRONTEND_DIR, 'index.html')
        if not os.path.exists(index_path):
            log.error(f"index.html 없음: {index_path}")
            sys.exit(1)

        # ⚠️ ESM import 가 file:// 에서 CORS 차단되므로 http://127.0.0.1:8765/ 로 서빙
        # FastAPI 가 frontend/ 를 정적 mount 하도록 backend/api.py 에 추가됨
        url = f'http://{API_HOST}:{API_PORT}/'

        _win_w, _win_h, _win_max = load_window_state()
        # [P1 PATCH] url= 대신 html=SPLASH_HTML 로 즉시 표시 (API 대기 없음).
        window = webview.create_window(
            title='SQM Inventory v8.6.6 — 광양창고',
            html=SPLASH_HTML,
            width=_win_w,
            height=_win_h,
            min_size=(1024, 700),
            resizable=True,
            background_color='#070e1a',
            js_api=SqmPywebviewApi(),
        )

        # [P1 PATCH 2차 수정] on_loaded 3-state gating:
        #   "splash" = 1차 발화 (최대화 복원만)
        #   "main"   = 메인 URL 로드 완료 (JS 브릿지 + 에러 후크 설치)
        #   "error"  = 오류 화면 로드 (JS 브릿지 비설치, 죽은 백엔드 fetch 루프 방지)
        _phase = ["splash"]

        def on_loaded():
            if _phase[0] == "splash":
                # 1차 발화: 스플래시 페이지 로드 완료 -> 최대화 복원만 처리.
                if _win_max:
                    try:
                        window.maximize()
                        log.info('창 최대화 복원 완료')
                    except Exception as e:
                        log.warning(f'창 최대화 복원 실패: {e}')
                return

            if _phase[0] == "error":
                # 오류 화면: JS 브릿지 설치하지 않음 (죽은 백엔드에 fetch 루프 방지).
                log.info('on_loaded: error 페이지 로드 — JS 브릿지 비설치')
                return

            # _phase[0] == "main": 실제 메인 URL 로드 완료 -> JS 브릿지 + 에러 후크 설치.
            # (필요 시 메인 URL 로드 후 최대화 재시도는 향후 개선; 현재는 splash 단계 처리로 충분)
            window.evaluate_js(f'''
                window.SQM_API_BASE = "http://{API_HOST}:{API_PORT}";
                console.log("[SQM] API Base:", window.SQM_API_BASE);

                // ── v8.6.6 Debug: JS 에러를 백엔드 로그로 전송 ──
                (function installErrorBridge() {{
                    // [3차 수정 2026-05-06] Idempotency guard.
                    // SPA 라우팅 / link click / load_url 재호출 등으로 on_loaded 가 여러 번
                    // 발화될 때, console.error 래핑이 누적되어 무한 재귀가 발생하는 버그 방지.
                    if (window.__SQM_BRIDGE_INSTALLED__) {{
                        console.log("[SQM] Error bridge already installed — skip");
                        return;
                    }}
                    window.__SQM_BRIDGE_INSTALLED__ = true;

                    function report(payload) {{
                        try {{
                            fetch(window.SQM_API_BASE + "/api/log/frontend-error", {{
                                method: "POST",
                                headers: {{ "Content-Type": "application/json" }},
                                body: JSON.stringify(payload),
                                keepalive: true
                            }}).catch(function(_){{}});
                        }} catch(_) {{}}
                    }}
                    // 1) 동기 JS 에러
                    window.addEventListener("error", function(e) {{
                        report({{
                            kind: "error",
                            message: String(e.message || ""),
                            source: String(e.filename || ""),
                            line: e.lineno || 0,
                            col: e.colno || 0,
                            stack: (e.error && e.error.stack) ? String(e.error.stack) : "",
                            url: String(location.href),
                            ua: String(navigator.userAgent)
                        }});
                    }}, true);
                    // 2) Promise rejection
                    window.addEventListener("unhandledrejection", function(e) {{
                        var r = e.reason || {{}};
                        report({{
                            kind: "unhandledrejection",
                            message: String(r.message || r),
                            stack: r.stack ? String(r.stack) : "",
                            url: String(location.href),
                            ua: String(navigator.userAgent)
                        }});
                    }});
                    // 3) console.error 후크 (원본 호출 유지)
                    var _origErr = console.error;
                    console.error = function() {{
                        try {{
                            var msg = Array.prototype.map.call(arguments, function(a) {{
                                try {{ return typeof a === "string" ? a : JSON.stringify(a); }}
                                catch(_) {{ return String(a); }}
                            }}).join(" ");
                            report({{ kind: "console.error", message: msg, url: String(location.href) }});
                        }} catch(_) {{}}
                        return _origErr.apply(console, arguments);
                    }};
                    console.log("[SQM] Error bridge installed");
                }})();
            ''')

        def on_closing():
            # 창 닫힐 때 크기+최대화 상태 저장
            # evaluate_js() 는 closing 이벤트에서 데드락 -> ctypes 로 대체
            try:
                w = window.width
                h = window.height
                maximized = False
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    screen_w = user32.GetSystemMetrics(0)
                    screen_h = user32.GetSystemMetrics(1)
                    maximized = (w >= screen_w - 30 and h >= screen_h - 80)
                except Exception:
                    pass
                save_window_state(w, h, maximized)
                log.info('on_closing: %dx%d max=%s', w, h, maximized)
            except Exception as e:
                log.warning('on_closing 실패: %s', e)

        window.events.loaded += on_loaded
        window.events.closing += on_closing

        # [P1 PATCH] webview.start(func=...) 콜백으로 API 대기 + URL 네비게이션.
        # 메인 스레드는 webview 이벤트 루프를 돌리고, on_window_started 는 별도 스레드에서 실행됨.
        def on_window_started():
            log.info("on_window_started: API 준비 대기 시작")
            try:
                if wait_for_api(timeout=10):
                    log.info(f"API 준비 완료 -> 메인 URL navigate: {url}")
                    _phase[0] = "main"
                    try:
                        window.load_url(url)
                    except Exception as e:
                        log.exception(f"window.load_url 실패: {e}")
                else:
                    log.error("API 시작 실패 -> 오류 화면 표시")
                    _phase[0] = "error"
                    error_html = (
                        '<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
                        '<title>SQM 시작 실패</title>'
                        '<style>body{background:#070e1a;color:#e2e8f0;'
                        'font-family:"Segoe UI","Malgun Gothic",sans-serif;'
                        'padding:50px;line-height:1.6;}'
                        'h1{color:#fda4af;}code{background:#1e293b;padding:2px 6px;'
                        'border-radius:4px;}</style></head><body>'
                        '<h1>API 서버 시작 실패</h1>'
                        '<p>로그 파일을 확인해 주세요: <code>sqm_debug.log</code></p>'
                        '<p>또는 PowerShell에서: '
                        '<code>netstat -ano | findstr :8765</code> 로 포트 점유 확인.</p>'
                        '</body></html>'
                    )
                    try:
                        window.load_html(error_html)
                    except Exception as e:
                        log.exception(f"오류 HTML 로드 실패: {e}")
            except Exception as e:
                log.exception(f"on_window_started 실패: {e}")

        log.info("PyWebView 창 시작 (Splash 즉시 표시 모드)")
        webview.start(on_window_started, debug=False)
        # 창이 닫히면 webview.start() 반환 → 프로세스 강제 종료
        # (FastAPI daemon 스레드가 살아있어도 깔끔하게 종료)
        log.info("창 닫힘 — 프로세스 종료")
        os._exit(0)

    except ImportError:
        log.error("pywebview 미설치. 설치: pip install pywebview")
        # 폴백: 기본 브라우저로 열기
        import webbrowser
        index_path = os.path.join(FRONTEND_DIR, 'index.html')
        webbrowser.open(f'file:///{index_path}')
        input("브라우저 모드로 실행됨. 종료하려면 Enter...")
    except Exception as e:
        log.exception(f"PyWebView 실행 실패: {e}")

if __name__ == '__main__':
    main()
