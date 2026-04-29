"""
SQM Inventory - Settings Dialogs
================================

v3.6.0 - UI 통일성 적용
- 다이얼로그 크기 표준화 (DialogSize)
- 간격 표준화 (Spacing)
- 폰트 스케일링 (FontScale)
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import is_dark  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import logging
import os

from ..utils.ui_constants import (
    CustomMessageBox,
    Spacing,
    apply_tooltip,
    setup_dialog_geometry_persistence,
)

logger = logging.getLogger(__name__)


class SettingsDialogMixin:
    """
    Settings dialogs mixin
    
    Mixed into SQMInventoryApp class
    """

    def _show_api_settings(self) -> None:
        """v3.9.7: API 키 보안 설정 다이얼로그"""
        from ..utils.constants import BOTH, LEFT, RIGHT, YES, W, X, tk, ttk
        from ..utils.ui_constants import ThemeColors

        try:
            from core.config import (
                API_KEY_SOURCE,
                GEMINI_API_KEY,
                GEMINI_MODEL,
                save_api_key_secure,
                save_gemini_model,
            )
        except ImportError:
            CustomMessageBox.showerror(self.root, "Error", "Config module not found")
            return

        dialog = create_themed_toplevel(self.root)
        dialog.title("🔐 API 키 보안 설정")
        setup_dialog_geometry_persistence(dialog, "settings_dialog", self.root, "large")
        dialog.minsize(400, 350)
        dialog.transient(self.root)
        dialog.grab_set()

        _is_dark = is_dark()
        _bg = ThemeColors.get('bg_card', _is_dark)
        _fg = ThemeColors.get('text_primary', _is_dark)
        dialog.configure(bg=_bg)

        # 헤더 (v8.7.0 Phase2: ThemeColors, Phase3: Spacing)
        header = tk.Frame(dialog, bg=ThemeColors.get('info', _is_dark), pady=Spacing.SM)
        header.pack(fill=X)
        tk.Label(header, text="🔐 Gemini API 키 설정", bg=ThemeColors.get('info', _is_dark), fg=ThemeColors.get('badge_text', _is_dark),
                 font=('맑은 고딕', 13, 'bold')).pack()

        body = tk.Frame(dialog, bg=_bg, padx=Spacing.LG, pady=Spacing.MD)
        body.pack(fill=BOTH, expand=YES)

        # 현재 상태
        masked = (GEMINI_API_KEY[:10] + "..." + GEMINI_API_KEY[-4:]) if GEMINI_API_KEY and len(GEMINI_API_KEY) > 14 else "미설정"
        source_map = {'ENV': '🟢 환경변수 (가장 안전)', 'KEYRING': '🟢 OS 자격증명', 'INI': '🟡 settings.ini (평문)', 'NONE': '🔴 미설정'}
        source_text = source_map.get(API_KEY_SOURCE, '🔴 미설정')

        info_frame = tk.Frame(body, bg=_bg)
        info_frame.pack(fill=X, pady=(0, Spacing.SM))

        _l1 = tk.Label(info_frame, text="현재 API 키:", bg=_bg, fg=_fg, font=('맑은 고딕', 10))
        _l1.pack(anchor=W)
        apply_tooltip(_l1, "현재 로드된 API 키의 마스킹된 표시입니다. 새 키를 입력한 뒤 저장하면 교체됩니다.")
        tk.Label(info_frame, text=f"  {masked}", bg=_bg, fg=ThemeColors.get('statusbar_progress'), font=('맑은 고딕', 10, 'bold')).pack(anchor=W)
        tk.Label(info_frame, text=f"  저장 위치: {source_text}", bg=_bg, fg=_fg, font=('맑은 고딕', 10)).pack(anchor=W)
        tk.Label(info_frame, text=f"  모델: {GEMINI_MODEL}", bg=_bg, fg=ThemeColors.get('text_muted', _is_dark), font=('맑은 고딕', 10)).pack(anchor=W)

        ttk.Separator(body).pack(fill=X, pady=Spacing.SM)

        # 모델 변경 (다음 실행부터 적용)
        _l_model = tk.Label(body, text="Gemini 모델 (변경 시 저장 후 다음 실행부터 적용):", bg=_bg, fg=_fg, font=('맑은 고딕', 10))
        _l_model.pack(anchor=W)
        apply_tooltip(_l_model, "사용할 Gemini 모델명(예: gemini-2.5-flash). 변경 후 저장하면 다음 실행부터 적용됩니다.")
        model_var = tk.StringVar(value=GEMINI_MODEL or "gemini-2.5-flash")
        model_entry = ttk.Entry(body, textvariable=model_var, width=55)
        model_entry.pack(fill=X, pady=Spacing.XS)
        apply_tooltip(model_entry, "Gemini API 모델 이름을 입력하세요. 예: gemini-2.5-flash, gemini-1.5-pro")

        ttk.Separator(body).pack(fill=X, pady=Spacing.SM)

        # 새 API 키 입력
        _l_key = tk.Label(body, text="새 API 키 입력:", bg=_bg, fg=_fg, font=('맑은 고딕', 10))
        _l_key.pack(anchor=W)
        apply_tooltip(_l_key, "Google AI Studio에서 발급한 API 키(AIza로 시작)를 입력한 뒤 저장을 누르세요.")
        key_var = tk.StringVar()
        key_entry = ttk.Entry(body, textvariable=key_var, width=55, show='●')
        key_entry.pack(fill=X, pady=Spacing.XS)
        apply_tooltip(key_entry, "새 API 키를 입력하세요. '키 표시'를 켜면 입력 내용을 확인할 수 있습니다.")

        # 보기/숨김 토글
        show_var = tk.BooleanVar(value=False)
        def toggle_show():
            key_entry.config(show='' if show_var.get() else '●')
        _chk_show = ttk.Checkbutton(body, text="키 표시", variable=show_var, command=toggle_show)
        _chk_show.pack(anchor=W)
        apply_tooltip(_chk_show, "체크하면 API 키가 평문으로 보입니다. 입력 확인 후 해제하는 것을 권장합니다.")

        # 저장 방식 선택
        _l_method = tk.Label(body, text="저장 방식:", bg=_bg, fg=_fg, font=('맑은 고딕', 10))
        _l_method.pack(anchor=W, pady=(Spacing.SM, 0))
        apply_tooltip(_l_method, "API 키 저장 위치. 자동은 OS keyring 우선, 실패 시 settings.ini에 저장됩니다.")
        method_var = tk.StringVar(value='auto')
        methods_frame = tk.Frame(body, bg=_bg)
        methods_frame.pack(fill=X, pady=Spacing.XS)
        _rb_auto = ttk.Radiobutton(methods_frame, text="🔒 자동 (keyring 우선)", variable=method_var, value='auto')
        _rb_auto.pack(anchor=W)
        apply_tooltip(_rb_auto, "OS 자격증명(keyring)에 저장을 시도하고, 실패 시 settings.ini에 저장합니다. 권장.")
        _rb_ini = ttk.Radiobutton(methods_frame, text="📄 settings.ini", variable=method_var, value='ini')
        _rb_ini.pack(anchor=W)
        apply_tooltip(_rb_ini, "API 키를 settings.ini 파일에 평문으로 저장합니다. 보안상 주의가 필요합니다.")

        result_label = tk.Label(body, text="", bg=_bg, fg=_fg, font=('맑은 고딕', 10))
        result_label.pack(anchor=W, pady=Spacing.XS)

        def save_key():
            key = key_var.get().strip()
            model_str = model_var.get().strip()
            if key:
                if not key.startswith('AIza'):
                    result_label.config(text="⚠️ Google API 키 형식이 아닙니다 (AIza...)", fg=ThemeColors.get('statusbar_icon_warn', _is_dark))
                    return
                method = save_api_key_secure(key)
                if method == 'KEYRING':
                    result_label.config(text="✅ API 키·모델 저장됨 (다음 실행부터 모델 적용)", fg=ThemeColors.get('badge_db'))
                elif method == 'INI':
                    result_label.config(text="✅ API 키·모델 저장됨 (다음 실행부터 모델 적용)", fg=ThemeColors.get('badge_db', _is_dark))
                else:
                    result_label.config(text="❌ API 키 저장 실패", fg=ThemeColors.get('statusbar_icon_err'))
            if model_str:
                if save_gemini_model(model_str):
                    if not key:
                        result_label.config(text="✅ 모델 저장됨 (다음 실행부터 적용)", fg=ThemeColors.get('badge_db'))
                elif not key:
                    result_label.config(text="❌ 모델 저장 실패", fg=ThemeColors.get('statusbar_icon_err'))
            if not key and not model_str:
                result_label.config(text="⚠️ API 키 또는 모델을 입력하세요", fg=ThemeColors.get('statusbar_icon_err'))

        btn_frame = tk.Frame(body, bg=_bg)
        btn_frame.pack(fill=X, pady=Spacing.SM)
        _btn_save = ttk.Button(btn_frame, text="💾 저장", command=save_key, width=12)
        _btn_save.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(_btn_save, "입력한 API 키와 모델을 선택한 저장 방식으로 저장합니다. 다음 실행부터 적용됩니다.")
        _btn_close = ttk.Button(btn_frame, text="닫기", command=dialog.destroy, width=12)
        _btn_close.pack(side=RIGHT, padx=Spacing.XS)
        apply_tooltip(_btn_close, "설정 창을 닫습니다. 저장하지 않은 변경 내용은 반영되지 않습니다.")

        dialog.bind('<Escape>', lambda e: dialog.destroy())

    def _show_gemini_api_required(self) -> None:
        """Show Gemini API required warning"""


        if getattr(self, 'gemini_required_warning_shown', False):
            return
        self.gemini_required_warning_shown = True

        guide_msg = """Gemini API Key Required!

For accurate data extraction from PDF documents,
Gemini API is required.

Without API key, these features are limited:
  X SAP NO extraction
  X Salar Invoice No extraction  
  X Ship date/arrival date extraction
  X LOT SQM extraction
  X Product name extraction

========================================

Setup Instructions:

1. Open settings.ini file
2. Enter API_KEY in [GEMINI] section

========================================

Sample:

[GEMINI]
API_KEY = AIzaSyA1B2C3D4E5F6G7H8I9J0...

========================================

Get free API key:
https://aistudio.google.com/apikey

========================================

Open settings.ini now?
"""
        if CustomMessageBox.askyesno(self.root, "Gemini API Required", guide_msg):
            try:
                from core.config import SETTINGS_FILE
                os.startfile(SETTINGS_FILE)
            except (ImportError, ModuleNotFoundError) as e:
                self._log(f"WARNING Failed to open settings.ini: {e}")

        self._set_status("WARNING Gemini API key required - Limited functionality")

    def _show_gemini_api_guide(self) -> None:
        """Compatibility redirect to _show_gemini_api_required"""
        self._show_gemini_api_required()

    def _toggle_gemini(self) -> None:
        """Toggle Gemini API usage (v3.6.9: Client 재초기화 연동)"""


        if hasattr(self, '_gemini_var'):
            self.use_gemini = self._gemini_var.get()

            if self.use_gemini:
                # v3.6.9: Client 재초기화 (API 키 변경 반영)
                self._reinit_gemini_clients()
                self._log("Gemini API enabled")
                CustomMessageBox.showinfo(self.root, "Gemini API", "Gemini API is now enabled")
            else:
                self._log("Gemini API disabled")
                CustomMessageBox.showinfo(self.root, "Gemini API", "Gemini API is now disabled")

    def _reinit_gemini_clients(self) -> None:
        """v3.6.9: 모든 Gemini Client를 재초기화 (API 키 변경 시)
        
        메인 UI는 변경하지 않고, 백엔드의 Client 인스턴스만 리셋합니다.
        다음 API 호출 시 새로운 키로 Client가 자동 생성됩니다.
        """
        try:
            # 1. 싱글턴 Client 리셋
            try:
                from features.ai.gemini_utils import reset_gemini_client
                reset_gemini_client()
                logger.info("Gemini 싱글턴 Client 리셋 완료")
            except ImportError as _e:
                logger.debug(f"settings_dialog: {_e}")

            # 2. document_parser의 gemini 리셋
            if hasattr(self, 'document_parser') and self.document_parser:
                if hasattr(self.document_parser, 'gemini') and self.document_parser.gemini:
                    if hasattr(self.document_parser.gemini, '_init_client'):
                        self.document_parser.gemini._init_client()
                        logger.info("DocumentParser Gemini 리셋 완료")

            # 3. AI chat engine 리셋 (있는 경우)
            if hasattr(self, 'chat_engine') and self.chat_engine:
                if hasattr(self.chat_engine, '_init_gemini'):
                    self.chat_engine._init_gemini()
                    logger.info("ChatEngine Gemini 리셋 완료")

            self._log("OK Gemini API Client 재초기화 완료")

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Gemini 재초기화 실패: {e}")
            self._log(f"WARNING Gemini 재초기화 실패: {e}")

    def _test_gemini_api(self) -> None:
        """Test Gemini API connection (v3.6.9: 백그라운드 스레드)"""

        self._log("Testing Gemini API connection...")
        self._set_status("Testing API...")

        import threading

        def _do_test():
            try:
                from core.config import GEMINI_API_KEY, GEMINI_MODEL

                if not GEMINI_API_KEY or GEMINI_API_KEY.startswith('your-'):
                    self.root.after(0, lambda: CustomMessageBox.showerror(self.root, "API Test",
                        "API 키가 설정되지 않았습니다.\n\n"
                        "settings.ini 또는 환경변수 GEMINI_API_KEY를 확인하세요."))
                    self.root.after(0, lambda: self._set_status("Ready"))
                    return

                import time
                start = time.time()

                from google import genai
                client = genai.Client(api_key=GEMINI_API_KEY)

                model_name = GEMINI_MODEL or "gemini-2.5-flash"
                response = client.models.generate_content(
                    model=model_name,
                    contents="Hello, respond with just 'OK'"
                )

                elapsed_ms = int((time.time() - start) * 1000)

                if response.text:
                    self.root.after(0, lambda: self._log(
                        f"OK Gemini API 연결 성공! (모델: {model_name}, {elapsed_ms}ms)"))
                    self.root.after(0, lambda: CustomMessageBox.showinfo(self.root, "API 테스트",
                        f"✅ Gemini API 연결 성공!\n\n"
                        f"모델: {model_name}\n"
                        f"응답 시간: {elapsed_ms}ms\n"
                        f"응답: {response.text[:50]}"))
                else:
                    self.root.after(0, lambda: CustomMessageBox.showerror(self.root, "API 테스트",
                        "❌ API 응답이 없습니다."))

            except ImportError:
                self.root.after(0, lambda: CustomMessageBox.showerror(self.root, "API 테스트",
                    "google-genai 패키지가 필요합니다.\n\npip install google-genai"))
            except (RuntimeError, ValueError) as e:
                err_msg = str(e)
                err_lower = err_msg.lower()

                # v3.6.9: 에러별 구체적 안내
                if '401' in err_lower or 'unauthorized' in err_lower or 'invalid api key' in err_lower:
                    user_msg = (
                        "❌ API 키가 유효하지 않습니다.\n\n"
                        "확인 사항:\n"
                        "• settings.ini의 api_key 값\n"
                        "• 환경변수 GEMINI_API_KEY\n\n"
                        "새 키 발급:\n"
                        "https://aistudio.google.com/apikey"
                    )
                elif '429' in err_lower or 'rate limit' in err_lower or 'quota' in err_lower:
                    user_msg = (
                        "⚠️ API 호출 한도를 초과했습니다.\n\n"
                        "• 잠시 후 다시 시도해주세요\n"
                        "• Google AI Studio에서 할당량 확인\n"
                        "• 무료 플랜: 분당 15회 제한"
                    )
                elif '503' in err_lower or 'unavailable' in err_lower:
                    user_msg = (
                        "⚠️ Gemini API 서비스가 일시 중단 중입니다.\n\n"
                        "• Google 서버 상태를 확인하세요\n"
                        "• 잠시 후 다시 시도해주세요"
                    )
                elif '404' in err_lower or 'not found' in err_lower:
                    user_msg = (
                        f"❌ 모델을 찾을 수 없습니다.\n\n"
                        f"설정된 모델: {model_name}\n\n"
                        f"settings.ini에서 model 값을 확인하세요.\n"
                        f"권장: gemini-2.5-flash"
                    )
                elif 'timeout' in err_lower:
                    user_msg = (
                        "⏱️ API 응답 시간이 초과되었습니다.\n\n"
                        "• 네트워크 연결을 확인하세요\n"
                        "• VPN 사용 시 끄고 재시도"
                    )
                else:
                    user_msg = f"API 테스트 실패:\n{err_msg}"

                self.root.after(0, lambda: self._log(f"X API 테스트 실패: {err_msg}"))
                self.root.after(0, lambda msg=user_msg: CustomMessageBox.showerror(
                    self.root, "API 테스트", msg))
            finally:
                self.root.after(0, lambda: self._set_status("Ready"))

        thread = threading.Thread(target=_do_test, daemon=True)
        thread.start()

    def _test_gemini_api_connection(self) -> None:
        """Test Gemini API connection (background)"""
        if not hasattr(self, 'document_parser') or not self.document_parser:
            self._log("WARNING Gemini API: Parser not initialized")
            return

        self._log("Checking Gemini API connection...")

        def test_connection():
            """Background API test"""
            try:
                if hasattr(self.document_parser, 'gemini') and self.document_parser.gemini:
                    result = self.document_parser.gemini.is_available()
                    return result
                return False
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"API test error: {e}")
                return False

        def on_complete(result):
            """Test complete callback"""
            if result:
                self._log("OK Gemini API connected")
            else:
                self._log("WARNING Gemini API not available")

        # Run in background
        if hasattr(self, '_run_background'):
            self._run_background(test_connection, on_complete)
        else:
            result = test_connection()
            on_complete(result)

    def _open_ai_chat(self) -> None:
        """v4.1.2: AI 재고 질의 채팅 — API 키 없으면 설정 안내"""

        from ..utils.constants import HAS_GEMINI

        if not HAS_GEMINI:
            CustomMessageBox.showinfo(self.root, "🤖 AI 어시스턴트",
                "Gemini API 키가 설정되지 않았습니다.\n\n"
                "설정 방법:\n"
                "1. 🔧 도구 → 🤖 AI 어시스턴트 → ⚙️ API 설정\n"
                "2. Google AI Studio에서 API 키 발급\n"
                "   (https://aistudio.google.com)\n"
                "3. API 키 입력 후 저장\n"
                "4. 프로그램 재시작")
            return

        try:
            from features.ai.gemini_chat_gui import GeminiChatWindow

            db_path = getattr(self, 'db_path', None)
            if not db_path and hasattr(self, 'engine') and hasattr(self.engine, 'db'):
                db_path = self.engine.db.db_path

            GeminiChatWindow(parent=self.root, db_path=db_path)
            self._log("AI 채팅 창 열림")

        except ImportError as e:
            self._log(f"❌ AI 채팅 모듈 로드 실패: {e}")
            CustomMessageBox.showerror(self.root, "오류",
                f"AI 채팅 모듈을 불러올 수 없습니다.\n\n{e}")
        except (RuntimeError, ValueError, TypeError, OSError) as e:
            self._log(f"❌ AI 채팅 창 오류: {e}")
            CustomMessageBox.showerror(self.root, "오류", f"AI 채팅 창 오류:\n{e}")

    def _on_container_suffix_toggle(self) -> None:
        """Toggle container suffix display (-1, -2, etc)"""
        if hasattr(self, '_container_suffix_var'):
            show_suffix = self._container_suffix_var.get()
            self._log(f"Container suffix display: {'ON' if show_suffix else 'OFF'}")
            self._safe_refresh()
    def _format_container_no(self, container_no: str) -> str:
        """Format container number based on display setting"""
        if not container_no:
            return ''

        # Check if suffix should be hidden
        if hasattr(self, '_container_suffix_var') and not self._container_suffix_var.get():
            # Remove -1, -2 suffix
            if '-' in container_no:
                parts = container_no.rsplit('-', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    return parts[0]

        return container_no

    # ─────────────────────────────────────────────────────────────────────
    # v6.4.0: BL 선사 도구 메뉴 핸들러
    # ─────────────────────────────────────────────────────────────────────
    def _on_bl_carrier_register(self) -> None:
        """선사 BL/DO 규칙 관리 v9.0 탭 분리"""
        import tkinter as tk
        from tkinter import ttk, messagebox

        parent = getattr(self, "root", getattr(self, "parent", None))
        db     = getattr(self, "db", None) or getattr(getattr(self, "engine", None), "db", None)
        if not db:
            messagebox.showerror("오류", "DB 연결이 없습니다.", parent=parent)
            return

        for sql in [
            """CREATE TABLE IF NOT EXISTS carrier_bl_rule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                carrier_id TEXT NOT NULL,
                carrier_name TEXT DEFAULT "",
                doc_type TEXT NOT NULL DEFAULT "BL",
                anchor_label TEXT DEFAULT "",
                pattern_desc TEXT DEFAULT "",
                regex_pattern TEXT NOT NULL,
                extraction_method TEXT DEFAULT "anchor_regex",
                field_name TEXT DEFAULT "bl_no",
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime("now")))
            """,
            "ALTER TABLE carrier_bl_rule ADD COLUMN doc_type TEXT DEFAULT 'BL'",
            "ALTER TABLE carrier_bl_rule ADD COLUMN field_name TEXT DEFAULT 'bl_no'",
        ]:
            try:
                db.execute(sql)
            except Exception:
                logger.debug("[SUPPRESSED] exception in settings_dialog.py")  # noqa

        dlg = create_themed_toplevel(parent)
        dlg.title("선사 BL/DO 규칙 관리  v9.0")
        dlg.geometry("980x640")
        dlg.resizable(True, True)
        try:
            dlg.transient(parent)
            dlg.grab_set()
        except Exception:
            logger.debug("[SUPPRESSED] exception in settings_dialog.py")  # noqa

        tk.Label(dlg,
                 text="선사별 BL/DO 추출 규칙   자연어 입력시 자동으로 정규식 변환",
                 font=("맑은 고딕", 11)).pack(pady=(10,4), padx=12, anchor="w")

        nb = ttk.Notebook(dlg)
        nb.pack(fill="both", expand=True, padx=12, pady=4)

        FIELD_OPTIONS = {
            "BL": ["bl_no"],
            "DO": ["bl_no", "do_no", "free_time", "return_yard", "container", "vessel"],
        }
        EXTRACT_METHODS = ["anchor_regex", "waybill_line", "label_right", "date_pattern"]

        def _nat2re(desc):
            import re as _re
            desc = desc.strip()
            if not desc:
                return ""
            if any(ch in desc for ch in ["[","{"]):
                return desc
            tokens = _re.split(r"[+\s]+", desc)
            result = ""
            for tok in tokens:
                tok = tok.strip()
                if not tok:
                    continue
                if _re.match(r"^[A-Z]{2,8}$", tok):
                    result += tok
                    continue
                m = _re.match(r"^알파벳(\d+)$", tok)
                if m:
                    result += "[A-Z]{" + m.group(1) + "}"
                    continue
                m = _re.match(r"^숫자(\d+)$", tok)
                if m:
                    result += "[0-9]{" + m.group(1) + "}"
                    continue
                m = _re.match(r"^영문(\d+)$", tok)
                if m:
                    result += "[A-Z]{" + m.group(1) + "}"
                    continue
                m = _re.match(r"^영문숫자(\d+)$", tok)
                if m:
                    result += "[A-Z0-9]{" + m.group(1) + "}"
                    continue
                if tok in ("날짜", "date"):
                    result += "[0-9]{4}-[0-9]{2}-[0-9]{2}"
                    continue
            return result

        def _build_tab(doc_type):
            tab = tk.Frame(nb)
            label = "📦 BL 규칙" if doc_type == "BL" else "📋 DO 규칙"
            nb.add(tab, text="  " + label + "  ")

            main = tk.Frame(tab)
            main.pack(fill="both", expand=True, padx=8, pady=6)

            left = tk.Frame(main)
            left.pack(side="left", fill="both", expand=True, padx=(0,8))

            cols = ("선사코드","선사명","필드","라벨","패턴설명","정규식","활성")
            tree = ttk.Treeview(left, columns=cols, show="headings", height=13)
            for col, w in zip(cols, [70,85,80,90,130,170,45]):
                tree.heading(col, text=col, anchor='center')
                tree.column(col, width=w, anchor="w")
            vsb = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")

            right = tk.LabelFrame(main, text=" 규칙 입력 ",
                                   font=("맑은 고딕",10,"bold"), width=310)
            right.pack(side="right", fill="y")
            right.pack_propagate(False)

            def mk_entry(row_n, label):
                tk.Label(right, text=label, font=("맑은 고딕",10),
                         anchor="w").grid(row=row_n, column=0, sticky="w", padx=8, pady=3)
                v = tk.StringVar()
                tk.Entry(right, textvariable=v, width=22,
                         font=("맑은 고딕",10)).grid(row=row_n, column=1,
                                                      sticky="ew", padx=8, pady=3)
                return v

            v_cid    = mk_entry(0, "선사코드 *")
            v_cname  = mk_entry(1, "선사명")
            v_anchor = mk_entry(2, "라벨텍스트")

            tk.Label(right, text="필드명", font=("맑은 고딕",10),
                     anchor="w").grid(row=3, column=0, sticky="w", padx=8, pady=3)
            v_field = tk.StringVar(value="bl_no")
            ttk.Combobox(right, textvariable=v_field, width=18,
                         values=FIELD_OPTIONS[doc_type],
                         state="readonly").grid(row=3, column=1, sticky="ew", padx=8, pady=3)

            v_desc  = mk_entry(4, "자연어설명 *")
            v_regex = mk_entry(5, "정규식 (자동)")

            tk.Label(right, text="추출방법", font=("맑은 고딕",10),
                     anchor="w").grid(row=6, column=0, sticky="w", padx=8, pady=3)
            v_method = tk.StringVar(
                value="waybill_line" if doc_type=="BL" else "anchor_regex")
            ttk.Combobox(right, textvariable=v_method, width=18,
                         values=EXTRACT_METHODS,
                         state="readonly").grid(row=6, column=1, sticky="ew", padx=8, pady=3)

            # 좌표 입력 프레임 (추출방법='coord'일 때 활성)
            coord_frame = tk.LabelFrame(right, text="좌표 (%)",
                                         font=("맑은 고딕",9))
            coord_frame.grid(row=7, column=0, columnspan=2,
                             sticky="ew", padx=8, pady=2)
            v_x1 = tk.StringVar(value="")
            v_x2 = tk.StringVar(value="")
            v_y1 = tk.StringVar(value="")
            v_y2 = tk.StringVar(value="")
            for col, (lbl, var) in enumerate([("x1%",v_x1),("x2%",v_x2),
                                               ("y1%",v_y1),("y2%",v_y2)]):
                tk.Label(coord_frame, text=lbl,
                         font=("맑은 고딕",9)).grid(row=0, column=col*2,
                                                     padx=2, pady=2)
                tk.Entry(coord_frame, textvariable=var, width=5,
                         font=("맑은 고딕",9)).grid(row=0, column=col*2+1,
                                                      padx=2, pady=2)

            def _toggle_coord(*_):
                state = "normal" if v_method.get() == "coord" else "disabled"
                for child in coord_frame.winfo_children():
                    try:
                        child.config(state=state)
                    except Exception:
                        logger.debug("[SUPPRESSED] exception in settings_dialog.py")  # noqa
            v_method.trace_add("write", _toggle_coord)
            _toggle_coord()

            v_active = tk.IntVar(value=1)
            tk.Checkbutton(right, text="활성", variable=v_active,
                           font=("맑은 고딕",10)).grid(row=7, column=1, sticky="w", padx=8)

            if doc_type == "BL":
                hint = "예시: 알파벳4+숫자9 / MAEU+숫자9 / 숫자9"
            else:
                hint = "예시: 날짜 / 알파벳5 / HMMU+숫자7"
            tk.Label(right, text=hint, font=("맑은 고딕",9), fg=tc('text_muted'),
                     wraplength=260, justify="left").grid(
                row=8, column=0, columnspan=2, sticky="w", padx=8, pady=4)

            def _auto(*_):
                rx = _nat2re(v_desc.get())
                if rx:
                    v_regex.set(rx)
            v_desc.trace_add("write", _auto)

            def _load():
                for item in tree.get_children():
                    tree.delete(item)
                try:
                    rows = db.execute(
                        "SELECT id, carrier_id, carrier_name, field_name,"
                        " anchor_label, pattern_desc, regex_pattern, is_active"
                        " FROM carrier_bl_rule WHERE doc_type=? ORDER BY carrier_id",
                        (doc_type,)
                    ).fetchall()
                    for r in rows:
                        if hasattr(r, "keys"):
                            d = dict(r)
                        else:
                            keys = ["id","carrier_id","carrier_name","field_name",
                                    "anchor_label","pattern_desc","regex_pattern","is_active"]
                            d = dict(zip(keys, r))
                        tree.insert("", "end", iid=str(d["id"]),
                                    values=(d["carrier_id"], d.get("carrier_name",""),
                                            d.get("field_name","bl_no"),
                                            d.get("anchor_label",""),
                                            d.get("pattern_desc",""),
                                            d.get("regex_pattern",""),
                                            "활성" if d.get("is_active") else "비활성"))
                except Exception as e:
                    messagebox.showerror("오류", str(e), parent=dlg)

            def _sel(event=None):
                sel = tree.selection()
                if not sel:
                    return
                try:
                    r = db.execute(
                        "SELECT carrier_id, carrier_name, anchor_label, pattern_desc,"
                        " regex_pattern, field_name, extraction_method, is_active"
                        " FROM carrier_bl_rule WHERE id=?", (int(sel[0]),)
                    ).fetchone()
                    if r:
                        if hasattr(r, "keys"):
                            d = dict(r)
                        else:
                            keys = ["carrier_id","carrier_name","anchor_label","pattern_desc",
                                    "regex_pattern","field_name","extraction_method","is_active"]
                            d = dict(zip(keys, r))
                        v_cid.set(d["carrier_id"])
                        v_cname.set(d.get("carrier_name",""))
                        v_anchor.set(d.get("anchor_label",""))
                        v_desc.set(d.get("pattern_desc",""))
                        v_regex.set(d.get("regex_pattern",""))
                        v_field.set(d.get("field_name","bl_no"))
                        v_method.set(d.get("extraction_method","anchor_regex"))
                        v_active.set(d.get("is_active", 1))
                        # 좌표 복원
                        for var, key in [(v_x1,"x_min_pct"),(v_x2,"x_max_pct"),
                                         (v_y1,"y_min_pct"),(v_y2,"y_max_pct")]:
                            val_c = d.get(key)
                            var.set(str(val_c) if val_c is not None else "")
                        _toggle_coord()
                except Exception:
                    logger.debug("[SUPPRESSED] exception in settings_dialog.py")  # noqa
            tree.bind("<<TreeviewSelect>>", _sel)

            def _save():
                cid = v_cid.get().strip().upper()
                if not cid:
                    messagebox.showwarning("입력 오류", "선사코드를 입력하세요.", parent=dlg)
                    return
                rx = v_regex.get().strip() or _nat2re(v_desc.get())
                if not rx:
                    messagebox.showwarning("입력 오류", "정규식 또는 자연어를 입력하세요.", parent=dlg)
                    return
                try:
                    sel = tree.selection()
                    if sel:
                        def _f(v):
                            try:
                                return float(v.get().strip()) if v.get().strip() else None
                            except (ValueError, TypeError):
                                return None
                        db.execute(
                            "UPDATE carrier_bl_rule SET carrier_id=?, carrier_name=?,"
                            " anchor_label=?, pattern_desc=?, regex_pattern=?,"
                            " field_name=?, extraction_method=?,"
                            " x_min_pct=?, x_max_pct=?, y_min_pct=?, y_max_pct=?,"
                            " is_active=? WHERE id=?",
                            (cid, v_cname.get().strip(), v_anchor.get().strip(),
                             v_desc.get().strip(), rx, v_field.get(), v_method.get(),
                             _f(v_x1), _f(v_x2), _f(v_y1), _f(v_y2),
                             v_active.get(), int(sel[0]))
                        )
                    else:
                        def _f(v):
                            try:
                                return float(v.get().strip()) if v.get().strip() else None
                            except (ValueError, TypeError):
                                return None
                        db.execute(
                            "INSERT INTO carrier_bl_rule"
                            " (carrier_id, carrier_name, doc_type, anchor_label,"
                            " pattern_desc, regex_pattern, field_name, extraction_method,"
                            " x_min_pct, x_max_pct, y_min_pct, y_max_pct, is_active)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (cid, v_cname.get().strip(), doc_type,
                             v_anchor.get().strip(), v_desc.get().strip(),
                             rx, v_field.get(), v_method.get(),
                             _f(v_x1), _f(v_x2), _f(v_y1), _f(v_y2),
                             v_active.get())
                        )
                    _load()
                    messagebox.showinfo("저장 완료",
                                        cid + " " + doc_type + " 규칙 저장됐습니다.", parent=dlg)
                except Exception as e:
                    messagebox.showerror("저장 오류", str(e), parent=dlg)

            def _del():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("선택 없음", "삭제할 항목을 선택하세요.", parent=dlg)
                    return
                if not messagebox.askyesno("삭제 확인", "삭제하시겠습니까?", parent=dlg):
                    return
                try:
                    db.execute("DELETE FROM carrier_bl_rule WHERE id=?", (int(sel[0]),))
                    _load()
                except Exception as e:
                    messagebox.showerror("삭제 오류", str(e), parent=dlg)

            def _clear():
                for v in (v_cid, v_cname, v_anchor, v_desc, v_regex,
                          v_x1, v_x2, v_y1, v_y2):
                    v.set("")
                v_active.set(1)
                v_field.set("bl_no")
                tree.selection_remove(tree.selection())
                _toggle_coord()

            bf = tk.Frame(tab)
            bf.pack(fill="x", padx=12, pady=(2,8))
            for text, cmd, bg in [
                ("저장",    _save,  "#0066CC"),
                ("삭제",    _del,   "#CC3333"),
                ("새 항목", _clear, "#444444"),
            ]:
                tk.Button(bf, text=text, command=cmd,
                          font=("맑은 고딕",11,"bold"),
                          bg=bg, fg=tc('text_primary'), padx=12, pady=4,
                          cursor="hand2", bd=0).pack(side="left", padx=(0,6))
            _load()

        _build_tab("BL")
        _build_tab("DO")

        tk.Button(dlg, text="닫기", command=dlg.destroy,
                  font=("맑은 고딕",11), padx=16, pady=4,
                  cursor="hand2").pack(pady=(0,8))

    def _on_bl_carrier_analyze(self) -> None:
        """선사 BL 규칙 현황 v9.0"""
        import tkinter as tk
        import tkinter.scrolledtext as st

        parent = getattr(self, 'root', getattr(self, 'parent', None))
        db     = getattr(self, 'db', None) or getattr(getattr(self, 'engine', None), 'db', None)

        dlg = create_themed_toplevel(parent)
        dlg.title("선사 BL 규칙 현황  v9.0")
        dlg.geometry("700x420")
        dlg.resizable(True, True)
        try:
            dlg.transient(parent)
            dlg.grab_set()
        except Exception:
            logger.debug("[SUPPRESSED] exception in settings_dialog.py")  # noqa

        tk.Label(dlg, text="현재 등록된 선사별 BL 번호 추출 규칙",
                 font=("맑은 고딕", 12, "bold")).pack(pady=(12, 4))

        box = st.ScrolledText(dlg, font=("Consolas", 11), height=20)
        box.pack(fill="both", expand=True, padx=12, pady=4)

        try:
            if db:
                rows = db.execute(
                    "SELECT carrier_id, carrier_name, pattern_desc, "
                    "regex_pattern, is_active FROM carrier_bl_rule ORDER BY carrier_id"
                ).fetchall()
                if rows:
                    box.insert("end", f"{'선사코드':<10}{'선사명':<16}{'자연어설명':<20}{'정규식':<25}활성\n")
                    box.insert("end", "-"*75 + "\n")
                    for r in rows:
                        if hasattr(r, 'keys'):
                            r = dict(r)
                        else:
                            r = dict(zip(['carrier_id','carrier_name',
                                          'pattern_desc','regex_pattern','is_active'], r))
                        box.insert("end",
                            f"{r['carrier_id']:<10}{r.get('carrier_name',''):<16}"
                            f"{r.get('pattern_desc',''):<20}{r.get('regex_pattern',''):<25}"
                            f"{'활성' if r.get('is_active') else '비활성'}\n")
                else:
                    box.insert("end", "등록된 선사 규칙이 없습니다.\n선사 BL 등록 도구에서 추가하세요.")
            else:
                box.insert("end", "DB 연결 없음")
        except Exception as e:
            box.insert("end", f"조회 오류: {e}")

        tk.Button(dlg, text="닫기", command=dlg.destroy,
                  font=("맑은 고딕", 11), padx=12, pady=4,
                  cursor="hand2").pack(pady=6)
