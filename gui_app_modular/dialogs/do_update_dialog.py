"""
SQM 재고관리 - D/O 후속 연결 다이얼로그 (v5.6.6)
==================================================

입고 완료 후 D/O가 나중에 도착한 경우,
기존 LOT에 도착일/Free Time 정보를 UPDATE하는 전용 다이얼로그.

흐름:
  1. D/O PDF 파일 선택
  2. Gemini 파싱 → BL No., 도착일, Free Time 추출
  3. BL No. 기준으로 DB에서 LOT 매칭
  4. 미리보기 → 확인 → UPDATE
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
import os
import sqlite3
import threading
from datetime import datetime as _dt
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

from core.constants import DEFAULT_WAREHOUSE
from core.types import norm_bl_no, norm_bl_no_for_query, norm_container_no
from engine_modules.constants import MOVEMENT_DO_UPDATE


class DOUpdateDialog:
    """D/O 후속 연결 다이얼로그"""

    def __init__(self, parent, engine, log_fn=None, app=None):
        self.parent = parent
        self.engine = engine
        self.app = app
        self._log = log_fn or (lambda msg, **kw: logger.info(msg))

        self.file_path = None
        self.do_data = None
        self.matched_lots = []
        self._diff_rows = []
        self._match_method = ""
        self._last_backup_path = ""

        self.dialog = None
        self.tree = None
        self.btn_parse = None
        self.btn_apply = None

    def show(self) -> None:
        """다이얼로그 표시"""
        self._create_dialog()

    def _create_dialog(self) -> None:
        """UI 구성"""
        from ..utils.constants import (
            BOTH,
            LEFT,
            RIGHT,
            W,
            X,
            Y,
            tk,
            ttk,
        )
        from ..utils.ui_constants import (
            ThemeColors,
            setup_dialog_geometry_persistence,
        )

        self.dialog = create_themed_toplevel(self.parent)
        self.dialog.title("📋 D/O 후속 연결 — SQM v6.2.3")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        setup_dialog_geometry_persistence(self.dialog, "do_update_dialog", self.parent, "medium")

        _is_dark = ThemeColors.is_dark_theme(
            getattr(self.app, 'current_theme', 'darkly') if self.app else 'darkly')
        bg = ThemeColors.get('bg_card', _is_dark)
        ThemeColors.get('text_primary', _is_dark)
        self.dialog.configure(bg=bg)

        # ── 상단: 파일 선택 ──
        top_frame = ttk.Frame(self.dialog, padding=10)
        top_frame.pack(fill=X)

        ttk.Label(top_frame, text="📋 D/O (인도지시서) PDF:").pack(side=LEFT)
        self.file_label = ttk.Label(top_frame, text="파일을 선택하세요", width=50)
        self.file_label.pack(side=LEFT, padx=5)
        ttk.Button(top_frame, text="📂 파일 선택", command=self._select_file).pack(side=LEFT)

        # ── 중단: 파싱 결과 ──
        info_frame = ttk.LabelFrame(self.dialog, text="📊 D/O 파싱 결과", padding=10)
        info_frame.pack(fill=X, padx=10, pady=5)

        self.info_labels = {}
        for key, label in [('bl_no', 'B/L No.'), ('arrival_date', '입항일'),
                           ('free_time_date', 'Free Time 만료'), ('free_time', 'Free Time (일)'),
                           ('warehouse', '창고')]:
            row = ttk.Frame(info_frame)
            row.pack(fill=X, pady=1)
            ttk.Label(row, text=f"  {label}:", width=18, anchor=W).pack(side=LEFT)
            lbl = ttk.Label(row, text="—", anchor=W)
            lbl.pack(side=LEFT)
            self.info_labels[key] = lbl

        # ── 매칭 LOT 리스트 ──
        tree_frame = ttk.LabelFrame(self.dialog, text="📦 매칭된 LOT 목록", padding=5)
        tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        columns = ('lot_no', 'bl_no', 'product', 'net_weight', 'status', 'arrival_before')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=8)
        for col, hdr, w in [('lot_no', 'LOT No.', 130), ('bl_no', 'B/L No.', 120),
                             ('product', '제품', 120), ('net_weight', 'NET(Kg)', 90),
                             ('status', '상태', 80), ('arrival_before', '기존 입항일', 100)]:
            self.tree.heading(col, text=hdr, anchor='center')
            self.tree.column(col, width=w, anchor='center')
        sb_y = tk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        sb_x = tk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb_y.pack(side=RIGHT, fill=Y)
        # v8.1.9: TreeviewTotalFooter
        try:
            from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter as _TTF
            _footer = _TTF(
                tree_frame, self.tree,
                summable_column_ids=['net_weight'],
                column_display_names={'net_weight': 'NET(kg)'},
                column_formats={'net_weight': ',.0f'},
            )
            _footer.pack(fill='x')
            self._footer_tree = _footer
        except Exception as e:
            logger.warning(f'[UI] do_update_dialog: {e}')
        sb_x.pack(side=tk.BOTTOM, fill=tk.X)

        # ── 하단: 버튼 ──
        btn_frame = ttk.Frame(self.dialog, padding=10)
        btn_frame.pack(fill=X)

        self.status_label = ttk.Label(btn_frame, text="D/O PDF를 선택한 후 파싱하세요")
        self.status_label.pack(side=LEFT, padx=5)

        ttk.Button(btn_frame, text="❌ 닫기", command=self.dialog.destroy).pack(side=RIGHT, padx=5)
        self.btn_apply = ttk.Button(btn_frame, text="✅ 적용", command=self._apply_update, state='disabled')
        self.btn_apply.pack(side=RIGHT, padx=5)
        self.btn_parse = ttk.Button(btn_frame, text="🔍 파싱", command=self._start_parsing, state='disabled')
        self.btn_parse.pack(side=RIGHT, padx=5)

    def _select_file(self) -> None:
        """PDF 파일 선택"""
        from ..utils.constants import filedialog
        path = filedialog.askopenfilename(
            parent=self.parent,
            title="D/O PDF 선택",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if path:
            self.file_path = path
            self.file_label.configure(text=os.path.basename(path))
            self.btn_parse.configure(state='normal')
            self.status_label.configure(text="🔍 파싱 버튼을 클릭하세요")

    def _start_parsing(self) -> None:
        """파싱 시작 (백그라운드)"""
        if not self.file_path:
            return
        self.btn_parse.configure(state='disabled')
        self.status_label.configure(text="⏳ D/O 파싱 중...")
        threading.Thread(target=self._parse_thread, daemon=True).start()

    def _parse_thread(self) -> None:
        """백그라운드 파싱"""
        try:
            from ..utils.constants import GEMINI_API_KEY, HAS_GEMINI
            if not HAS_GEMINI or not GEMINI_API_KEY:
                self._update_ui(lambda: self.status_label.configure(
                    text="❌ Gemini API Key 필요"))
                return

            from parsers.document_parser_modular import DocumentParserV3 as DocumentParserV2  # v7.5.0: V3 마이그레이션
            parser = DocumentParserV2(gemini_api_key=GEMINI_API_KEY)

            do_data = None
            if hasattr(parser, 'parse_do'):
                do_data = parser.parse_do(self.file_path)
            elif hasattr(parser, 'parse_document'):
                do_data = parser.parse_document(self.file_path, doc_type='DO')

            if do_data:
                self.do_data = do_data
                self._update_ui(self._display_results)
            else:
                self._update_ui(lambda: self.status_label.configure(
                    text="❌ D/O 파싱 실패 — 결과 없음"))

        except Exception as e:
            logger.error(f"D/O 파싱 오류: {e}", exc_info=True)
            msg = f"❌ 파싱 오류: {e}"
            self._update_ui(lambda m=msg: self.status_label.configure(text=m))

    def _update_ui(self, fn):
        """메인 스레드에서 UI 업데이트"""
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.after(0, fn)

    def _display_results(self) -> None:
        """파싱 결과 표시 + LOT 매칭"""
        do = self.do_data

        # D/O 정보 표시
        bl_no = str(getattr(do, 'bl_no', '') or '')
        arrival = str(getattr(do, 'arrival_date', '') or '')
        # v8.7.0 [FIX D-1.1]: DOData의 실제 필드는 warehouse_name / warehouse_code
        warehouse = str(
            getattr(do, 'warehouse_name', '')
            or getattr(do, 'warehouse_code', '')
            or DEFAULT_WAREHOUSE
        )

        # Free Time 계산
        ft_date = ''
        ft_days = 0
        ft_infos = getattr(do, 'free_time_info', []) or []
        if ft_infos:
            for ft in ft_infos:
                ftd = getattr(ft, 'free_time_date', '') or (
                    ft.get('free_time_date', '') if isinstance(ft, dict) else '')
                if ftd:
                    ft_date = str(ftd)
                    break
        # v8.7.0 [FIX D-1.2]: DOData에 free_time_date 필드 없음 — dead fallback 제거.
        #   정상 경로는 free_time_info[].free_time_date 루프(위 블록). 예비 fallback은 불필요.

        if ft_date and arrival:
            try:
                _ft_dt = _dt.strptime(str(ft_date)[:10], '%Y-%m-%d').date()
                _arr_dt = _dt.strptime(str(arrival)[:10], '%Y-%m-%d').date()
                ft_days = max(0, (_ft_dt - _arr_dt).days)
            except (ValueError, TypeError):
                ft_days = 0

        self.info_labels['bl_no'].configure(text=bl_no or '—')
        self.info_labels['arrival_date'].configure(text=arrival or '—')
        self.info_labels['free_time_date'].configure(text=ft_date or '—')
        self.info_labels['free_time'].configure(text=f"{ft_days}일" if ft_days > 0 else '—')
        self.info_labels['warehouse'].configure(text=warehouse)

        # 파싱 결과 저장 (적용 시 사용)
        self._parsed_bl = bl_no
        self._parsed_arrival = arrival
        self._parsed_ft_date = ft_date
        self._parsed_ft_days = ft_days
        self._parsed_warehouse = warehouse

        # BL No. + (필요 시) Container 보조 매칭
        self.matched_lots = []
        self._diff_rows = []
        self._match_method = ""
        self.tree.delete(*self.tree.get_children())

        if not bl_no:
            self.status_label.configure(text="⚠️ B/L No.가 없어 LOT 매칭 불가")
            return

        try:
            rows, method = self._match_lots_for_do(bl_no, do)
            self._match_method = method
            if rows:
                self.matched_lots = rows
                self._diff_rows = self._build_diff_rows(rows)
                for r in rows:
                    self.tree.insert('', 'end', values=(
                        r.get('lot_no', ''),
                        r.get('bl_no', ''),
                        r.get('product', ''),
                        f"{float(r.get('net_weight', 0) or 0):,.1f}",
                        r.get('status', ''),
                        r.get('arrival_date', '') or '없음',
                    ))
                will_update = len([d for d in self._diff_rows if d.get('changed_fields')])
                skipped = len(self._diff_rows) - will_update
                self.status_label.configure(
                    text=f"✅ {len(rows)}개 매칭 ({method}) | 업데이트 예정 {will_update} | 스킵 {skipped}")
                self.btn_apply.configure(state='normal')
            else:
                self.status_label.configure(text=f"⚠️ BL '{bl_no}' 매칭 LOT 없음 (정규화 exact + BL+Container 보조)")

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"LOT 매칭 오류: {e}")
            self.status_label.configure(text=f"❌ DB 오류: {e}")

    def _apply_update(self) -> None:
        """매칭된 LOT에 D/O 정보 UPDATE"""
        from ..utils.ui_constants import CustomMessageBox

        if not self.matched_lots:
            return

        if not self._diff_rows:
            self._diff_rows = self._build_diff_rows(self.matched_lots)

        update_targets = [d for d in self._diff_rows if d.get('changed_fields')]
        skipped_same = len(self._diff_rows) - len(update_targets)
        if not update_targets:
            CustomMessageBox.showinfo(self.dialog, "D/O 적용", "변경할 값이 없습니다. (모든 LOT가 기존값과 동일)")
            return

        preview_lines = []
        for d in update_targets[:20]:
            field_changes = ", ".join(
                f"{f}: {d['old'].get(f, '') or '—'} -> {d['new'].get(f, '') or '—'}"
                for f in d.get('changed_fields', [])
            )
            preview_lines.append(f"- {d.get('lot_no', '')}: {field_changes}")
        if len(update_targets) > 20:
            preview_lines.append(f"... 외 {len(update_targets) - 20}건")

        count = len(self.matched_lots)
        confirm_text = (
            f"{count}개 매칭 LOT 중 {len(update_targets)}개를 업데이트합니다.\n"
            f"(기존값 동일로 스킵: {skipped_same}건)\n"
            f"매칭 방식: {self._match_method or 'unknown'}\n\n"
            f"[변경 Diff 미리보기]\n" + "\n".join(preview_lines) + "\n\n"
            "진행 전 DB 백업 스냅샷을 자동 생성합니다.\n"
            "진행하시겠습니까?"
        )
        if not CustomMessageBox.askyesno(self.dialog, "D/O 적용 확인 (Diff 검토)", confirm_text):
            return

        # 업데이트 전 스냅샷 백업(실패 시 중단)
        backup_path = None
        if hasattr(self.engine, 'db') and hasattr(self.engine.db, 'create_backup'):
            backup_path = self.engine.db.create_backup("before_do_followup_update")
        if not backup_path:
            CustomMessageBox.showerror(
                self.dialog, "백업 실패",
                "업데이트 전 백업 스냅샷 생성에 실패했습니다.\n안전을 위해 적용을 중단합니다."
            )
            return
        self._last_backup_path = str(backup_path)

        updated = 0
        verify_mismatch = []
        _now_str = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
        _source_file = self.file_path or ''
        try:
            with self.engine.db.transaction():
                for d in update_targets:
                    lot_no = d.get('lot_no', '')
                    updates = []
                    params = []
                    new_data = d.get('new', {})
                    for col in ('arrival_date', 'free_time', 'free_time_date', 'con_return', 'warehouse'):
                        if col in d.get('changed_fields', []):
                            updates.append(f"{col} = ?")
                            params.append(new_data.get(col, ''))

                    if updates:
                        updates.append("updated_at = ?")
                        params.append(_dt.now().strftime('%Y-%m-%d %H:%M:%S'))
                        sql = f"UPDATE inventory SET {', '.join(updates)} WHERE lot_no = ?"
                        params.append(lot_no)
                        self.engine.db.execute(sql, tuple(params))
                        updated += 1
                        self._log(
                            f"  ✅ LOT {lot_no} 업데이트: {', '.join(d.get('changed_fields', []))}"
                        )
                        # 감사 이력은 best-effort로 기록하고, 실패해도 본 UPDATE는 유지
                        _changed_summary = '; '.join(
                            f"{f}: {d['old'].get(f, '') or ''} -> {d['new'].get(f, '') or ''}"
                            for f in d.get('changed_fields', [])
                        )
                        try:
                            self.engine.db.execute(
                                "INSERT INTO stock_movement "
                                "(lot_no, movement_type, qty_kg, source_type, source_file, remarks, created_at) "
                                "VALUES (?, ?, 0, 'DO_FOLLOWUP', ?, ?, ?)",
                                (lot_no, MOVEMENT_DO_UPDATE, _source_file, _changed_summary, _now_str)
                            )
                        except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError) as _sm_e:
                            logger.debug(f"stock_movement DO_UPDATE 기록 스킵: {_sm_e}")

            # 사후 검증 리포트(업데이트 건수/스킵/불일치)
            for d in update_targets:
                lot_no = d.get('lot_no', '')
                rec = self.engine.db.fetchone(
                    "SELECT arrival_date, free_time, free_time_date, con_return, warehouse "
                    "FROM inventory WHERE lot_no = ?",
                    (lot_no,),
                ) or {}
                for col in d.get('changed_fields', []):
                    expected = str(d.get('new', {}).get(col, '') or '')
                    actual = str((rec.get(col, '') if hasattr(rec, 'get') else '') or '')
                    if actual != expected:
                        verify_mismatch.append({
                            'lot_no': lot_no, 'column': col, 'expected': expected, 'actual': actual,
                        })

            mismatch_cnt = len(verify_mismatch)
            self._log(
                f"📋 D/O 후속 연결 완료: 매칭 {count}건 / 업데이트 {updated}건 / "
                f"스킵 {skipped_same}건 / 불일치 {mismatch_cnt}건"
            )
            self._log(f"🧷 사전 백업 스냅샷: {self._last_backup_path}")
            if mismatch_cnt:
                for mm in verify_mismatch[:10]:
                    self._log(
                        f"  ⚠️ 검증 불일치 LOT={mm['lot_no']} {mm['column']} "
                        f"(예상={mm['expected']} / 실제={mm['actual']})"
                    )

            CustomMessageBox.showinfo(self.dialog, "D/O 적용 완료",
                f"✅ 적용 완료\n\n"
                f"- 매칭: {count}건\n"
                f"- 업데이트: {updated}건\n"
                f"- 스킵(동일값): {skipped_same}건\n"
                f"- 검증 불일치: {mismatch_cnt}건\n\n"
                f"백업: {os.path.basename(self._last_backup_path) if self._last_backup_path else '-'}")

            # 새로고침
            if self.app:
                self.app._safe_refresh()
            self.dialog.destroy()

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"D/O 적용 오류: {e}", exc_info=True)
            self._log(f"❌ D/O 적용 실패 (롤백됨): {e}")
            CustomMessageBox.showerror(self.dialog, "오류", f"D/O 적용 실패:\n{e}")

    def _to_row_dict(self, row) -> Dict:
        if hasattr(row, 'keys'):
            return dict(row)
        return {
            'lot_no': row[0], 'bl_no': row[1], 'product': row[2],
            'net_weight': row[3], 'status': row[4], 'arrival_date': row[5],
            'free_time': row[6], 'free_time_date': row[7], 'con_return': row[8],
            'warehouse': row[9], 'container_no': row[10],
        }

    def _extract_do_container_set(self, do) -> set:
        containers = set()
        for c in (getattr(do, 'containers', []) or []):
            cno = getattr(c, 'container_no', '') if hasattr(c, 'container_no') else (c.get('container_no', '') if isinstance(c, dict) else '')
            std = norm_container_no(cno)
            if std:
                containers.add(std)
        return containers

    def _match_lots_for_do(self, bl_no: str, do) -> Tuple[List[Dict], str]:
        bl_raw = str(bl_no or '').strip()
        if not bl_raw:
            return [], ""
        bl_std = norm_bl_no_for_query(bl_raw) or ''  # v9.0: 조회용 숫자만
        container_set = self._extract_do_container_set(do)

        base_sql = (
            "SELECT lot_no, bl_no, product, net_weight, status, arrival_date, "
            "free_time, free_time_date, con_return, warehouse, container_no "
            "FROM inventory WHERE COALESCE(lot_no,'') <> '' "
        )

        # 1) raw exact (DB 우선)
        raw_rows = self.engine.db.fetchall(
            base_sql + "AND COALESCE(bl_no, '') = ? COLLATE NOCASE ORDER BY lot_no",
            (bl_raw,)
        ) or []
        selected = [self._to_row_dict(r) for r in raw_rows]
        method = "raw_exact_bl" if selected else ""

        # 2) normalized exact (후보만 가져와 Python 정규화 비교)
        if not selected and bl_std:
            candidates = self.engine.db.fetchall(
                base_sql + "AND COALESCE(bl_no, '') <> '' AND (bl_no LIKE ? OR bl_no LIKE ?) ORDER BY lot_no",
                (f"%{bl_raw}%", f"%{bl_std}%")
            ) or []
            selected = []
            for r in candidates:
                row_d = self._to_row_dict(r)
                if (norm_bl_no_for_query(row_d.get('bl_no', '')) or '') == bl_std:  # v9.0
                    selected.append(row_d)
            method = "normalized_exact_bl" if selected else ""

        # 3) container 보조 매칭
        if container_set and selected:
            narrowed = [
                r for r in selected
                if (norm_container_no(r.get('container_no', '')) or '') in container_set
            ]
            if narrowed:
                selected = narrowed
                method = f"{method}+container"
        elif container_set and not selected and bl_std:
            aux_candidates = self.engine.db.fetchall(
                base_sql + "AND COALESCE(bl_no, '') <> '' AND (bl_no LIKE ? OR bl_no LIKE ?) ORDER BY lot_no",
                (f"%{bl_raw}%", f"%{bl_std}%")
            ) or []
            selected = []
            for r in aux_candidates:
                row_d = self._to_row_dict(r)
                if (norm_bl_no_for_query(row_d.get('bl_no', '')) or '') == bl_std and (  # v9.0
                    norm_container_no(row_d.get('container_no', '')) or ''
                ) in container_set:
                    selected.append(row_d)
            if selected:
                method = "normalized_bl+container_aux"

        # lot_no 중복 제거
        uniq = {}
        for r in selected:
            lot_no = str(r.get('lot_no', '') or '').strip()
            if lot_no and lot_no not in uniq:
                uniq[lot_no] = r
        return list(uniq.values()), method

    def _build_diff_rows(self, rows: List[Dict]) -> List[Dict]:
        new_arrival = str(self._parsed_arrival or '').strip()[:10]
        new_ft_days = int(self._parsed_ft_days or 0) if int(self._parsed_ft_days or 0) > 0 else None
        new_ft_date = str(self._parsed_ft_date or '').strip()[:10]
        new_warehouse = str(self._parsed_warehouse or '').strip()

        out = []
        for r in rows:
            old_data = {
                'arrival_date': str(r.get('arrival_date', '') or '')[:10],
                'free_time': str(r.get('free_time', '') or ''),
                'free_time_date': str(r.get('free_time_date', '') or '')[:10],
                'con_return': str(r.get('con_return', '') or '')[:10],
                'warehouse': str(r.get('warehouse', '') or ''),
            }
            new_data = dict(old_data)
            if new_arrival:
                new_data['arrival_date'] = new_arrival
            if new_ft_days is not None:
                new_data['free_time'] = str(new_ft_days)
            if new_ft_date:
                new_data['free_time_date'] = new_ft_date
                new_data['con_return'] = new_ft_date
            if new_warehouse:
                new_data['warehouse'] = new_warehouse

            changed_fields = [k for k in old_data.keys() if str(old_data.get(k, '') or '') != str(new_data.get(k, '') or '')]
            out.append({
                'lot_no': str(r.get('lot_no', '') or ''),
                'old': old_data,
                'new': new_data,
                'changed_fields': changed_fields,
            })
        return out
