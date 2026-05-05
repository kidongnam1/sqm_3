"""
Tk GUI Excel 파일 정렬 패치 스크립트
모든 gui_app_modular 내 wb.save() 직전에
apply_sqm_workbook_alignment(wb) 호출을 삽입합니다.
"""
from __future__ import annotations
import re
import sys

TARGETS = [
    "gui_app_modular/handlers/outbound_handlers.py",
    "gui_app_modular/dialogs/allocation_template_dialog.py",
    "gui_app_modular/handlers/inbound_handlers.py",
    "gui_app_modular/mixins/validation_mixin.py",
    "gui_app_modular/dialogs/allocation_dialog.py",
    "gui_app_modular/handlers/outbound_template_mixin.py",
    "gui_app_modular/dialogs/return_statistics_dialog.py",
    "gui_app_modular/dialogs/inbound_history_dialog.py",
    "gui_app_modular/dialogs/product_inventory_report.py",
    "gui_app_modular/dialogs/integrity_v760_dialog.py",
    "gui_app_modular/mixins/advanced_dialogs_mixin.py",
    "gui_app_modular/dialogs/inbound_upload_mixin.py",
    "gui_app_modular/dialogs/lot_status_dialog.py",
    "gui_app_modular/utils/tonbag_location_uploader.py",
    "gui_app_modular/handlers/import_handlers.py",
]

IMPORT_LINE = "from utils.sqm_excel_alignment import apply_sqm_workbook_alignment\n"
ALIGNMENT_MARKER = "apply_sqm_workbook_alignment(wb)"

def patch_file(path: str) -> tuple[int, bool]:
    """Returns (save_calls_patched, already_had_import)"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    already_import = IMPORT_LINE.strip() in content
    already_patched = ALIGNMENT_MARKER in content

    if already_patched and already_import:
        return (0, True)

    # 1. wb.save() 직전에 정렬 호출 삽입 (아직 없는 경우만)
    patched = 0
    if not already_patched:
        def insert_alignment(m: re.Match) -> str:
            indent = m.group(1)
            wb_var = m.group(2)
            rest = m.group(3)
            call_line = f"{indent}try:\n{indent}    from utils.sqm_excel_alignment import apply_sqm_workbook_alignment\n{indent}    apply_sqm_workbook_alignment({wb_var})\n{indent}except Exception:\n{indent}    pass\n{indent}{wb_var}.save({rest}\n"
            return call_line

        new_content, patched = re.subn(
            r"^( *)(wb)\.save\(([^\n]+)\n",
            insert_alignment,
            content,
            flags=re.MULTILINE,
        )
        content = new_content

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    return (patched, already_import)


def main():
    total_patched = 0
    for path in TARGETS:
        try:
            n, had_import = patch_file(path)
            status = f"patched {n} save(s)" if n else "already patched"
            print(f"  OK  {path} — {status}")
            total_patched += n
        except FileNotFoundError:
            print(f"  SKIP {path} (not found)")
        except Exception as e:
            print(f"  ERR  {path}: {e}")
    print(f"\n완료: 총 {total_patched}개 wb.save() 직전에 정렬 삽입")


if __name__ == "__main__":
    main()
