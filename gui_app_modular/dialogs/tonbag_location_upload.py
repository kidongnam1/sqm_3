"""
SQM 재고관리 시스템 - 톤백 위치 업로드 다이얼로그
=================================================

v4.2.3: Excel 파일 선택 → 미리보기 → 업로드
v5.9.x: 데이터 붙여넣기 / 파일 열기 선택 후 진행

작성자: Ruby
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, ttk
from typing import Optional

logger = logging.getLogger(__name__)


def _open_exported_excel(path: str) -> None:
    """저장한 xlsx를 OS 기본 프로그램으로 연다."""
    import os
    import platform
    import subprocess

    path = os.path.normpath(path)
    try:
        if platform.system() == 'Windows':
            os.startfile(path)
        elif platform.system() == 'Darwin':
            subprocess.run(['open', path], check=False)
        else:
            subprocess.run(['xdg-open', path], check=False)
    except Exception as e:
        logger.warning(f"반영 엑셀 파일 열기 실패: {e}")


def _run_with_data(
    parent,
    engine,
    data,
    callback: Optional[Callable] = None,
    source_excel_path: Optional[str] = None,
):
    """파싱된 데이터로 매칭 → 미리보기 → 업로드 실행."""
    from ..utils.custom_messagebox import CustomMessageBox
    from ..utils.tonbag_location_uploader import TonbagLocationUploader
    from .location_upload_preview import LocationUploadPreviewDialog

    uploader = TonbagLocationUploader(engine)
    result = uploader.validate_and_match(data)

    def on_confirm(matched_data):
        total_target = len(matched_data or [])
        if total_target <= 0:
            CustomMessageBox.showwarning(parent, "매핑 중단", "매핑할 데이터가 없습니다.")
            return

        step_total = 0
        changed_rows = 0
        same_rows = 0
        initial_rows = 0
        for item in matched_data:
            db_loc = (item.get('db_current_location') or '').strip()
            cur_loc = (item.get('current_location') or '').strip()
            moves = [
                (item.get('move_1') or '').strip(),
                (item.get('move_2') or '').strip(),
                (item.get('move_3') or '').strip(),
            ]
            moves = [m for m in moves if m and m != '-']
            if not moves:
                if db_loc and cur_loc and db_loc != cur_loc:
                    changed_rows += 1
                    step_total += 1
                elif (not db_loc) and cur_loc:
                    initial_rows += 1
                else:
                    same_rows += 1
                continue
            stage = db_loc or cur_loc
            local_steps = 0
            for m in moves:
                if m != stage:
                    local_steps += 1
                    stage = m
            step_total += local_steps
            if local_steps > 0:
                changed_rows += 1
            else:
                same_rows += 1

        confirm_message = (
            "아래 내용으로 톤백 위치를 즉시 반영합니다.\n\n"
            f"- 반영 대상: {total_target}건\n"
            f"- 최초 위치 배치: {initial_rows}건\n"
            f"- 위치 변경 행: {changed_rows}건\n"
            f"- 실제 이동 단계(최대3단계): {step_total}건\n"
            f"- 동일(변경 없음): {same_rows}건\n\n"
            "계속 진행하시겠습니까?"
        )
        if not CustomMessageBox.askyesno(parent, "최종 확인", confirm_message):
            return

        # ⑤ v6.6.0: 대량이면 PENDING→Supervisor 승인 워크플로
        # v6.7.7: 5→10으로 조정 (광양 기준 1LOT=톤백10개, LOT단위 이동은 즉시반영)
        # [P3] v6.8.1: 최초 배치(initial_rows)는 Supervisor 승인 면제
        #   입고 후 처음 랙에 놓는 행위는 이동이 아닌 배치 → 즉시 반영이 원칙
        BATCH_THRESHOLD = 10
        _only_initial = (initial_rows == len(matched_data)) and changed_rows == 0
        immediate_apply = not (len(matched_data) >= BATCH_THRESHOLD and not _only_initial)
        if len(matched_data) >= BATCH_THRESHOLD and not _only_initial:
            # submit_batch_move 호출 → PENDING
            batch_result = engine.submit_batch_move(
                validated_items=matched_data,
                reason_code='RELOCATE',
                operator=getattr(engine, '_current_user', 'GUI'),
            )
            if batch_result['success']:
                success = True
                message = (
                    f"✅ 대량 이동 요청 제출 완료\n\n"
                    f"배치 ID: {batch_result['batch_id']}\n"
                    f"총 {len(matched_data)}개 톤백\n\n"
                    f"⚠️ Supervisor 승인 후 실제 반영됩니다.\n"
                    f"[재고관리 → 이동 승인] 메뉴에서 확인하세요."
                )
            else:
                success = False
                message = f"❌ 제출 실패: {batch_result.get('error', '')}"
        else:
            # 소량(4개 이하)은 즉시 반영
            success, message = uploader.update_locations(matched_data)
        if success:
            out_path = None
            if immediate_apply:
                ok_x, _msg_x, out_path = uploader.export_location_reflected_workbook(
                    source_excel_path, matched_data
                )
                if ok_x and out_path:
                    _open_exported_excel(out_path)
                    message = (
                        f"{message}\n\n"
                        f"📄 DB에 반영된 로케이션이 들어간 엑셀을 저장했고 열었습니다.\n"
                        f"{out_path}"
                    )
                elif not ok_x:
                    logger.warning(f"로케이션 반영 엑셀 저장 실패: {_msg_x}")
            CustomMessageBox.showinfo(parent, "완료", message)
            if callback:
                callback()
        else:
            CustomMessageBox.showerror(parent, "실패", message)

    LocationUploadPreviewDialog(parent, result, on_confirm=on_confirm)


def _run_with_data_from_file(parent, engine, data, file_path: str, callback: Optional[Callable] = None):
    """파일 경로를 알고 있을 때 반영 엑셀에 원본 형식을 유지한다."""
    _run_with_data(parent, engine, data, callback=callback, source_excel_path=file_path)


def run_location_upload_with_file(parent, engine, file_path: str, callback: Optional[Callable] = None):
    """지정한 Excel 파일로 로케이션 업로드 플로우 실행 (드래그앤드롭 등에서 호출)."""
    from ..utils.custom_messagebox import CustomMessageBox
    from ..utils.tonbag_location_uploader import TonbagLocationUploader

    uploader = TonbagLocationUploader(engine)
    success, message, data = uploader.parse_excel(file_path)
    if not success or not data:
        CustomMessageBox.showerror(parent, "파싱 실패", message or "데이터가 없습니다.")
        return
    _run_with_data_from_file(parent, engine, data, file_path, callback=callback)


def show_tonbag_location_upload_dialog(
    parent,
    engine,
    callback: Optional[Callable] = None
):
    """
    톤백 위치 업로드: [데이터 붙여넣기] vs [파일 열기] 선택 후 미리보기 → 업로드
    """
    from ..utils.custom_messagebox import CustomMessageBox
    from ..utils.tonbag_location_uploader import TonbagLocationUploader

    # 1) 선택 다이얼로그 — Excel/데이터 입력 원칙 통일 (데이터 붙여넣기 / 파일 업로드)
    from ..utils.ui_constants import (
        UPLOAD_CHOICE_BTN_PASTE,
        UPLOAD_CHOICE_BTN_UPLOAD,
        UPLOAD_CHOICE_HEADER,
        UPLOAD_CHOICE_PASTE,
        UPLOAD_CHOICE_UPLOAD,
        apply_modal_window_options,
    )
    choice_win = create_themed_toplevel(parent)
    choice_win.title("📍 톤백 위치 매핑")
    choice_win.transient(parent)
    apply_modal_window_options(choice_win)
    frm = ttk.Frame(choice_win, padding=20)
    frm.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frm, text=UPLOAD_CHOICE_HEADER, font=("맑은 고딕", 10)).pack(pady=(0, 12))
    ttk.Label(frm, text=UPLOAD_CHOICE_PASTE, font=("맑은 고딕", 9), wraplength=380, justify=tk.LEFT).pack(anchor="w", pady=(0, 6))
    ttk.Label(frm, text=UPLOAD_CHOICE_UPLOAD, font=("맑은 고딕", 9), wraplength=380, justify=tk.LEFT).pack(anchor="w", pady=(0, 12))
    btn_frm = ttk.Frame(frm)
    btn_frm.pack(pady=4)
    chosen = {"value": None}

    def on_paste():
        chosen["value"] = "paste"
        choice_win.destroy()

    def on_file():
        chosen["value"] = "file"
        choice_win.destroy()

    def on_cancel():
        chosen["value"] = None
        choice_win.destroy()

    ttk.Button(btn_frm, text=UPLOAD_CHOICE_BTN_PASTE, command=on_paste).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frm, text=UPLOAD_CHOICE_BTN_UPLOAD, command=on_file).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frm, text="취소", command=on_cancel).pack(side=tk.LEFT, padx=6)
    try:
        from gui_app_modular.utils.ui_constants import setup_dialog_geometry_persistence as _sgp
        _sgp(choice_win, "tonbag_location_choice_win", parent, "medium")
    except Exception as e:
        logger.warning(f'[UI] tonbag_location_upload: {e}')
    choice_win.geometry("+%d+%d" % (parent.winfo_rootx() + 80, parent.winfo_rooty() + 80))
    choice_win.grab_set()
    choice_win.wait_window()
    choice = chosen.get("value")

    if choice == "file":
        file_path = filedialog.askopenfilename(
            parent=parent,
            title="📍 톤백 위치 Excel 파일 선택",
            filetypes=[("Excel 파일", "*.xlsx *.xls"), ("모든 파일", "*.*")]
        )
        if not file_path:
            return
        loading_dialog = create_themed_toplevel(parent)
        loading_dialog.title("처리 중...")
        loading_dialog.geometry("300x100")
        loading_dialog.resizable(True, True)  # v9.0: 크기 조절 허용
        loading_dialog.minsize(400, 300)  # v9.0: 최소 크기
        loading_dialog.transient(parent)
        loading_dialog.grab_set()
        loading_dialog.update_idletasks()
        x = (loading_dialog.winfo_screenwidth() // 2) - 150
        y = (loading_dialog.winfo_screenheight() // 2) - 50
        loading_dialog.geometry(f"+{x}+{y}")
        tk.Label(loading_dialog, text="📂 Excel 파일을 분석 중입니다...", font=("맑은 고딕", 11), pady=20).pack()
        progress = ttk.Progressbar(loading_dialog, mode="indeterminate")
        progress.pack(fill=tk.X, padx=20, pady=10)
        progress.start()
        loading_dialog.update()
        try:
            uploader = TonbagLocationUploader(engine)
            success, message, data = uploader.parse_excel(file_path)
            loading_dialog.destroy()
            if not success:
                CustomMessageBox.showerror(parent, "파싱 실패", message)
                return
            _run_with_data_from_file(parent, engine, data, file_path, callback=callback)
        except (ValueError, TypeError, OSError) as e:
            loading_dialog.destroy()
            logger.error(f"위치 업로드 처리 실패: {e}")
            CustomMessageBox.showerror(parent, "오류", f"처리 중 오류 발생:\n{e}")
        return

    if choice == "paste":
        from ..utils.paste_table_dialog import show_paste_table_dialog

        # 업로드한 형식과 동일: lot_no, tonbag_no, uid, location (SQM 톤백 로케이션 매핑)
        location_columns = [
            ("no", "순번", 70),
            ("lot_no", "lot_no", 120),
            ("tonbag_no", "tonbag_no", 100),
            ("uid", "uid", 140),
            ("location", "location", 120),
        ]

        def on_location_confirm(rows):
            if not rows:
                CustomMessageBox.showwarning(parent, "안내", "데이터가 없습니다.")
                return
            # 붙여넣기 누적(2~3회 이상)된 경우도 현재 표의 모든 행을 그대로 파싱한다.
            uploader = TonbagLocationUploader(engine)
            raw_lines = ["\t".join(["lot_no", "tonbag_no", "uid", "location"])]
            for r in rows:
                raw_lines.append("\t".join([
                    str(r.get("lot_no", "")),
                    str(r.get("tonbag_no", "")),
                    str(r.get("uid", "")),
                    str(r.get("location", "")),
                ]))
            raw = "\n".join(raw_lines)
            success, message, data = uploader.parse_pasted_text(raw)
            if not success:
                CustomMessageBox.showerror(parent, "파싱 실패", message)
                return
            _run_with_data(parent, engine, data, callback=callback)

        show_paste_table_dialog(
            parent,
            title="📍 SQM 톤백 로케이션 매핑 (붙여넣기)",
            columns=location_columns,
            instruction="아래 표에 lot_no, tonbag_no, uid, location 데이터를 붙여넣기(Ctrl+V) 한 뒤 [확인]을 누르면 DB에 반영됩니다. 형식: X-00-00-00 (구역-열-층-칸).",
            confirm_text="확인",
            cancel_text="취소",
            on_confirm=on_location_confirm,
            min_size=(560, 380),
            auto_number_column="no",
        )
        return


# 테스트
if __name__ == '__main__':
    # 간단한 테스트
    logger.debug("톤백 위치 업로드 다이얼로그 모듈")
    logger.debug("show_tonbag_location_upload_dialog() 함수를 메인 앱에서 호출하세요")
