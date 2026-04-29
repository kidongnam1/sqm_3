import logging

_tree_logger = logging.getLogger(__name__)
# -*- coding: utf-8 -*-
"""
Global editable behavior for ttk.Treeview widgets.

Applies spreadsheet-like interactions to all Treeviews:
- Double click cell edit
- Ctrl+C / Ctrl+X / Ctrl+V
- Delete selected rows (UI only)
- Ctrl+A select all
- Right-click context menu
"""

import tkinter as tk
from tkinter import ttk


def install_global_editable_tree(root) -> None:
    """Install class-level editable bindings for opt-in Treeviews only."""
    if not root or getattr(root, "_global_editable_tree_installed", False):
        return

    def _is_editable_target(tree: ttk.Treeview) -> bool:
        return bool(
            tree
            and isinstance(tree, ttk.Treeview)
            and getattr(tree, "_enable_global_editable", False)
            and not getattr(tree, "_disable_global_editable", False)
        )

    def _tree_columns(tree: ttk.Treeview) -> list[str]:
        return list(tree.cget("columns") or [])

    def _notify_changed(tree: ttk.Treeview) -> None:
        cb = getattr(tree, "_on_tree_data_changed", None)
        if callable(cb):
            try:
                cb()
            except Exception as e:
                _tree_logger.debug(f"[EditableTree] {e}")

    def _cancel_editor(tree: ttk.Treeview) -> None:
        editor = getattr(tree, "_global_cell_editor", None)
        if editor is not None:
            try:
                editor.destroy()
            except Exception as e:
                _tree_logger.debug(f"[EditableTree] {e}")
        tree._global_cell_editor = None
        tree._global_cell_editor_ctx = None

    def _commit_editor(tree: ttk.Treeview) -> None:
        editor = getattr(tree, "_global_cell_editor", None)
        ctx = getattr(tree, "_global_cell_editor_ctx", None)
        if not editor or not ctx:
            return
        row_id, col_name = ctx
        try:
            tree.set(row_id, col_name, editor.get().strip())
        except Exception as e:
            _tree_logger.debug(f"[EditableTree] {e}")
        _cancel_editor(tree)
        _notify_changed(tree)

    def _open_context_menu(tree: ttk.Treeview, x_root: int, y_root: int) -> None:
        menu = getattr(tree, "_global_edit_menu", None)
        if menu is None:
            menu = tk.Menu(tree, tearoff=0)
            menu.add_command(label="행 삭제", command=lambda t=tree: _delete_rows(t))
            menu.add_command(label="복사", command=lambda t=tree: _copy_rows(t))
            menu.add_command(label="잘라내기", command=lambda t=tree: _cut_rows(t))
            menu.add_separator()
            menu.add_command(label="전체 초기화", command=lambda t=tree: _clear_rows(t))
            tree._global_edit_menu = menu
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def _copy_rows(tree: ttk.Treeview) -> None:
        iids = list(tree.selection() or ())
        if not iids:
            return
        cols = _tree_columns(tree)
        lines = []
        for iid in iids:
            vals = tree.item(iid, "values")
            line = "\t".join(str(vals[i]) if i < len(vals) else "" for i in range(len(cols)))
            lines.append(line)
        txt = "\n".join(lines)
        try:
            tree.clipboard_clear()
            tree.clipboard_append(txt)
        except Exception as e:
            _tree_logger.debug(f"[EditableTree] {e}")

    def _delete_rows(tree: ttk.Treeview) -> None:
        for iid in list(tree.selection() or ()):
            try:
                tree.delete(iid)
            except Exception as e:
                _tree_logger.debug(f"[EditableTree] {e}")
        _notify_changed(tree)

    def _cut_rows(tree: ttk.Treeview) -> None:
        _copy_rows(tree)
        _delete_rows(tree)

    def _clear_rows(tree: ttk.Treeview) -> None:
        for iid in list(tree.get_children("") or ()):
            try:
                tree.delete(iid)
            except Exception as e:
                _tree_logger.debug(f"[EditableTree] {e}")
        _notify_changed(tree)

    def _paste_rows(tree: ttk.Treeview) -> None:
        try:
            raw = tree.clipboard_get()
        except Exception:
            return
        text = str(raw or "").strip("\n")
        if not text:
            return
        cols = _tree_columns(tree)
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) == 1 and "," in parts[0]:
                parts = [p.strip() for p in parts[0].split(",")]
            vals = (parts + [""] * len(cols))[:len(cols)]
            try:
                tree.insert("", "end", values=vals)
            except Exception as e:
                _tree_logger.debug(f"[EditableTree] {e}")
        _notify_changed(tree)

    def _on_double_click(event):
        tree = event.widget
        if not _is_editable_target(tree):
            return
        region = tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = tree.identify_row(event.y)
        col_token = tree.identify_column(event.x)
        if not row_id or not col_token:
            return
        col_idx = int(str(col_token).replace("#", "")) - 1
        cols = _tree_columns(tree)
        if col_idx < 0 or col_idx >= len(cols):
            return
        col_name = cols[col_idx]
        if col_name in set(getattr(tree, "_editable_exclude_cols", {"status"})):
            return

        bbox = tree.bbox(row_id, col_token)
        if not bbox:
            return
        x, y, w, h = bbox
        old_val = tree.set(row_id, col_name)

        _cancel_editor(tree)
        editor = ttk.Entry(tree)
        editor.place(x=x, y=y, width=w, height=h)
        editor.insert(0, old_val)
        editor.selection_range(0, tk.END)
        editor.focus_set()
        tree._global_cell_editor = editor
        tree._global_cell_editor_ctx = (row_id, col_name)
        editor.bind("<Return>", lambda _e, t=tree: (_commit_editor(t), "break"))
        editor.bind("<Escape>", lambda _e, t=tree: (_cancel_editor(t), "break"))
        editor.bind("<FocusOut>", lambda _e, t=tree: _commit_editor(t))

    def _on_delete(event):
        tree = event.widget
        if not _is_editable_target(tree):
            return
        _delete_rows(tree)
        return "break"

    def _on_copy(event):
        tree = event.widget
        if not _is_editable_target(tree):
            return
        _copy_rows(tree)
        return "break"

    def _on_cut(event):
        tree = event.widget
        if not _is_editable_target(tree):
            return
        _cut_rows(tree)
        return "break"

    def _on_paste(event):
        tree = event.widget
        if not _is_editable_target(tree):
            return
        _paste_rows(tree)
        return "break"

    def _on_select_all(event):
        tree = event.widget
        if not _is_editable_target(tree):
            return
        all_iids = list(tree.get_children("") or ())
        if all_iids:
            tree.selection_set(all_iids)
        return "break"

    def _on_right_click(event):
        tree = event.widget
        if not _is_editable_target(tree):
            return
        iid = tree.identify_row(event.y)
        if iid:
            tree.selection_set((iid,))
        _open_context_menu(tree, event.x_root, event.y_root)
        return "break"

    root.bind_class("Treeview", "<Double-1>", _on_double_click, add="+")
    root.bind_class("Treeview", "<Delete>", _on_delete, add="+")
    root.bind_class("Treeview", "<Control-c>", _on_copy, add="+")
    root.bind_class("Treeview", "<Control-x>", _on_cut, add="+")
    root.bind_class("Treeview", "<Control-v>", _on_paste, add="+")
    root.bind_class("Treeview", "<Control-a>", _on_select_all, add="+")
    root.bind_class("Treeview", "<Button-3>", _on_right_click, add="+")

    root._global_editable_tree_installed = True
