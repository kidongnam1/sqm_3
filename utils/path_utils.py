"""Path utilities (v5.3.4)

Goal:
- Make REPORTS/settings.ini path stable even when the app is launched from shortcuts or different working dirs.
"""

import logging
import os

logger = logging.getLogger(__name__)


def get_app_base_dir(fallback: str | None = None) -> str:
    """Return base directory for the app.
    Priority:
    1) Directory that contains this file (utils/path_utils.py) -> app package directory
    2) Current working directory
    3) fallback
    """
    try:
        here = os.path.abspath(os.path.dirname(__file__))
        # go up to code root: .../utils -> ...
        base = os.path.abspath(os.path.join(here, os.pardir))
        return base
    except (OSError, ValueError, TypeError) as e:
        logger.debug(f"Suppressed: get_app_base_dir(__file__) 실패: {e}")
    try:
        return os.getcwd()
    except (OSError, ValueError, TypeError) as e:
        logger.debug(f"Suppressed: getcwd() 실패: {e}")
    return fallback or "."

def resolve_reports_dir(settings_ini_path: str | None = None, default_name: str = "REPORTS") -> str:
    """Resolve reports directory.
    - Reads [paths] reports_dir from settings.ini if present
    - If relative, resolves against app base dir
    """
    import configparser

    base = get_app_base_dir()
    ini = settings_ini_path or os.path.join(base, "settings.ini")
    reports_dir = default_name
    try:
        cfg = configparser.ConfigParser()
        cfg.read(ini, encoding="utf-8")
        reports_dir = cfg.get("paths", "reports_dir", fallback=default_name) or default_name
    except (OSError, ValueError, TypeError):
        reports_dir = default_name

    if not os.path.isabs(reports_dir):
        reports_dir = os.path.join(base, reports_dir)
    return os.path.abspath(reports_dir)
