"""UI debug utilities (v5.3.6)

Writes lightweight UI anomaly logs (menu bg resets etc.) into REPORTS directory.
"""

import json
import logging
import os
from datetime import datetime

from utils.path_utils import resolve_reports_dir

logger = logging.getLogger(__name__)

def log_ui_event(event: str, payload: dict | None = None) -> None:
    """Append a UI debug event as one json line."""
    try:
        reports_dir = resolve_reports_dir()
        os.makedirs(reports_dir, exist_ok=True)
        fn = os.path.join(reports_dir, "ui_debug_v5.3.6.jsonl")
        rec = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event": event,
            "payload": payload or {},
        }
        with open(fn, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except (ValueError, TypeError, AttributeError) as _e:
        logger.debug(f"Suppressed: {_e}")

def safe_widget_bg(w) -> str | None:
    try:
        if w is None:
            return None
        return str(w.cget("bg"))
    except (ValueError, TypeError, AttributeError):
        return None
