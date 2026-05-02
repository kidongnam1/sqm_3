"""
Treeview 전역 순번 열 자동 적용 유틸리티.

- show='headings' 테이블에만 '#0' 트리 컬럼을 '순번'으로 노출
- insert/delete 시 자동 재번호
- 이미 순번 유사 컬럼이 있으면 중복 적용 생략
"""

from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)


_ROWNO_SKIP_COLS = {"no", "no.", "row_num", "rowno", "index", "순번"}


def _iter_widgets(root) -> Iterable:
    stack = [root]
    while stack:
        w = stack.pop()
        yield w
        try:
            children = w.winfo_children()
        except Exception:
            children = []
        stack.extend(children)


def _has_builtin_row_column(tree) -> bool:
    try:
        cols = [str(c).strip().lower() for c in tree.cget("columns")]
    except Exception:
        return False
    return any(c in _ROWNO_SKIP_COLS for c in cols)


def _renumber_tree(tree) -> None:
    """데이터 행만 1부터 번호. 합계 등 `total` 태그 행은 순번 비움."""
    try:
        seq = 0
        for iid in tree.get_children(""):
            tags = tree.item(iid, "tags") or ()
            if isinstance(tags, str):
                tags = (tags,) if tags else ()
            if "total" in tags:
                tree.item(iid, text="")
            else:
                seq += 1
                tree.item(iid, text=str(seq))
    except Exception as e:
        logger.debug(f"[rowno] renumber skip: {e}")


def _wrap_tree_methods(tree) -> None:
    if getattr(tree, "_rowno_wrapped", False):
        return
    try:
        original_insert = tree.insert
        original_delete = tree.delete

        def _insert(*args, **kwargs):
            iid = original_insert(*args, **kwargs)
            _renumber_tree(tree)
            return iid

        def _delete(*args, **kwargs):
            result = original_delete(*args, **kwargs)
            _renumber_tree(tree)
            return result

        tree.insert = _insert
        tree.delete = _delete
        tree._rowno_wrapped = True
    except Exception as e:
        logger.debug(f"[rowno] wrap skip: {e}")


def _apply_to_tree(tree) -> None:
    if getattr(tree, "_rowno_enabled", False):
        return
    if _has_builtin_row_column(tree):
        return
    try:
        show = str(tree.cget("show") or "")
    except Exception:
        return
    # headings 포함 모드면 적용 (예: 'headings', 'tree headings')
    if "headings" not in show:
        return
    try:
        # tree 컬럼이 숨겨져 있으면 노출
        if "tree" not in show:
            tree.configure(show="tree headings")
        tree.heading("#0", text="순번", anchor='center')
        tree.column("#0", width=58, minwidth=48, stretch=False, anchor="center")
        tree._rowno_enabled = True
        _wrap_tree_methods(tree)
        _renumber_tree(tree)
    except Exception as e:
        logger.debug(f"[rowno] apply skip: {e}")


def install_global_row_number_tree(root) -> None:
    """앱 전체 Treeview에 순번 열 자동 적용."""
    if getattr(root, "_rowno_installed", False):
        return
    root._rowno_installed = True

    def _scan():
        try:
            try:
                from gui_app_modular.utils.ui_constants import (
                    apply_treeview_center_alignment,
                )
            except ImportError:
                apply_treeview_center_alignment = None  # type: ignore
            for w in _iter_widgets(root):
                if str(getattr(w, "winfo_class", lambda: "")()) == "Treeview":
                    _apply_to_tree(w)
                    if apply_treeview_center_alignment:
                        try:
                            apply_treeview_center_alignment(w)
                        except Exception as e:
                            logger.debug(f"[rowno] center_align skip: {e}")
        except Exception as e:
            logger.debug(f"[rowno] scan skip: {e}")
        finally:
            try:
                if root and root.winfo_exists():
                    root.after(800, _scan)
            except Exception:
                logger.debug("[SUPPRESSED] exception in global_row_number_tree.py")  # noqa

    try:
        root.after(200, _scan)
    except Exception as e:
        logger.debug(f"[rowno] install skip: {e}")
