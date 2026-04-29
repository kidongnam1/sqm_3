# -*- coding: utf-8 -*-
"""v8.6.5: 다크/라이트 테마 전환 시 추가 색상 오버라이드."""
import logging
logger = logging.getLogger(__name__)


def apply_colorful_overrides(app_self) -> None:
    """테마 전환 후 상태 배지·버튼·탭 색상 강제 적용."""
    try:
        import tkinter.ttk as ttk
        from gui_app_modular.utils.ui_constants import ThemeColors, tc

        root    = getattr(app_self, "root", app_self)
        style   = ttk.Style(root)
        is_dark = getattr(app_self, "_is_dark", None)
        if is_dark is None:
            theme   = getattr(app_self, "current_theme", "darkly")
            is_dark = ThemeColors.is_dark_theme(theme)

        # ── 상태 색상 태그 (Treeview 행) ─────────────────────────────
        STATUS_COLORS = {
            "AVAILABLE": ("#0d2018", "#52c87e") if is_dark else ("#e4f4ec", "#147848"),
            "RESERVED":  ("#1e1608", "#e8943a") if is_dark else ("#faf0e0", "#a86020"),
            "PICKED":    ("#18102e", "#a07ee0") if is_dark else ("#ede8f8", "#6040b0"),
            "OUTBOUND":  ("#0a1826", "#4ab0e8") if is_dark else ("#e0eef8", "#1060a8"),
            "RETURN":    ("#1e0818", "#e06888") if is_dark else ("#fce4ef", "#a03060"),
        }
        for tag, (bg, fg) in STATUS_COLORS.items():
            try:
                style.configure(f"{tag}.Treeview.Row", background=bg, foreground=fg)
            except Exception as _e:
                logger.debug("[theme] style.configure(%s) 실패: %s", tag, _e)

        # ── ttk.Button ────────────────────────────────────────────────
        btn_bg = tc("bg_secondary", is_dark)
        btn_fg = tc("text_primary", is_dark)
        btn_ab = tc("accent", is_dark) if is_dark else "#2563eb"

        style.configure("TButton",
            background=btn_bg,
            foreground=btn_fg,
            relief="flat",
            padding=(10, 6),
            font=('맑은 고딕', 10),
        )
        style.map("TButton",
            background=[("active", btn_ab), ("pressed", btn_ab)],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
        )

        # ── Notebook 탭 — padding (14,6) 으로 탭 글씨 잘림 방지 ──────
        nb_bg  = tc("bg_primary",   is_dark)
        nb_sel = tc("bg_secondary", is_dark)
        style.configure("TNotebook", background=nb_bg)
        style.configure("TNotebook.Tab",
            background=nb_bg,
            foreground=tc("text_secondary", is_dark),
            padding=(14, 6),
            font=('맑은 고딕', 10),
        )
        style.map("TNotebook.Tab",
            background=[("selected", nb_sel)],
            foreground=[("selected", tc("text_primary", is_dark))],
        )

        # ── Label ────────────────────────────────────────────────────
        style.configure("TLabel",
            font=('맑은 고딕', 10),
        )

        # ── Entry ────────────────────────────────────────────────────
        style.configure("TEntry",
            font=('맑은 고딕', 10),
            padding=(4, 4),
        )

        # ── Combobox ─────────────────────────────────────────────────
        style.configure("TCombobox",
            font=('맑은 고딕', 10),
            padding=(4, 4),
        )

        # ── LabelFrame ───────────────────────────────────────────────
        style.configure("TLabelframe.Label",
            font=('맑은 고딕', 10, 'bold'),
        )

    except Exception as e:
        logger.debug(f"[ColorfulOverride] 적용 스킵: {e}")
