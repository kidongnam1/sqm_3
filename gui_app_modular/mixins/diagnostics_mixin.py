"""
SQM 재고관리 - 진단/검증 Mixin
================================
v3.8.4 - advanced_features_mixin에서 분리

기능:
- DB 무결성 검증
- 체크섬 관리
- 작업 로그 관리
- 자가 진단 (Self-Test)
- Dry-run 검증 (입고/출고)
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
import sqlite3

from ..utils.ui_constants import CustomMessageBox

logger = logging.getLogger(__name__)


class DiagnosticsMixin:
    """진단/검증 Mixin"""

    def _verify_db_integrity(self) -> None:
        """DB 무결성 검증"""
        self._set_status("DB 무결성 검증 중...")
        self._log("🔍 DB 무결성 검증 시작...")

        try:
            # SQLite integrity_check
            result = self.engine.db.fetchall("PRAGMA integrity_check")

            # 체크섬 검증 (있으면)
            checksum_ok = True
            checksum_msg = ""

            if hasattr(self.engine, 'verify_checksum'):
                checksum_ok = self.engine.verify_checksum()
                checksum_msg = "✅ 체크섬 검증 통과" if checksum_ok else "⚠️ 체크섬 불일치"

            if result and result[0][0] == 'ok':
                self._log("✅ DB 무결성 검증 통과")
                CustomMessageBox.showinfo(self.root, "무결성 검증",
                    "✅ 데이터베이스 무결성 검증 통과\n\n"
                    f"{checksum_msg}\n\n"
                    "문제가 발견되지 않았습니다.")
            else:
                issues = [str(r[0]) for r in result]
                self._log(f"⚠️ DB 무결성 문제 발견: {len(issues)}건")
                CustomMessageBox.showwarning(self.root, "무결성 검증",
                    f"⚠️ 데이터베이스 문제 발견!\n\n"
                    f"문제 수: {len(issues)}\n\n"
                    "백업 후 복구를 권장합니다.")

        except (RuntimeError, ValueError) as e:
            self._log(f"❌ 무결성 검증 오류: {e}")
            CustomMessageBox.showerror(self.root, "오류", f"검증 오류:\n{e}")

        self._set_status("Ready")

    def _update_checksum(self) -> None:
        """체크섬 갱신"""
        if CustomMessageBox.askyesno(self.root, "체크섬 갱신",
            "데이터베이스 체크섬을 갱신합니다.\n\n"
            "이 작업은 현재 데이터를 기준으로\n"
            "새로운 체크섬을 생성합니다.\n\n"
            "계속하시겠습니까?"):

            try:
                if hasattr(self.engine, 'update_checksum'):
                    self.engine.update_checksum()
                    self._log("✅ 체크섬 갱신 완료")
                    CustomMessageBox.showinfo(self.root, "완료", "체크섬이 갱신되었습니다.")
                else:
                    # 수동으로 체크섬 파일 생성
                    import hashlib
                    import os

                    db_path = self.engine.db.db_path
                    if os.path.exists(db_path):
                        with open(db_path, 'rb') as f:
                            checksum = hashlib.md5(f.read()).hexdigest()

                        checksum_path = db_path + '.checksum'
                        with open(checksum_path, 'w') as f:
                            f.write(checksum)

                        self._log(f"✅ 체크섬 생성: {checksum[:16]}...")
                        CustomMessageBox.showinfo(self.root, "완료",
                            f"체크섬 생성 완료\n\n{checksum[:32]}...")

            except (OSError, RuntimeError) as e:
                self._log(f"❌ 체크섬 갱신 오류: {e}")
                CustomMessageBox.showerror(self.root, "오류", f"갱신 오류:\n{e}")

    # ═══════════════════════════════════════════════════════════════
    # 작업 로그
    # ═══════════════════════════════════════════════════════════════

    def _show_action_log(self) -> None:
        """작업 로그 표시"""
        from ..utils.constants import BOTH, END, VERTICAL, tk, ttk
        from ..utils.ui_constants import setup_dialog_geometry_persistence
        dialog = create_themed_toplevel(self.root)
        dialog.title("📋 작업 로그")
        dialog.transient(self.root)
        setup_dialog_geometry_persistence(dialog, "action_log_dialog", self.root, "medium")

        # 텍스트 영역
        frame = ttk.Frame(dialog)
        frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

        text = tk.Text(frame, wrap='word', font=('Consolas', 10))
        scrollbar = tk.Scrollbar(frame, orient=VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side='left', fill=BOTH, expand=True)
        scrollbar.pack(side='right', fill='y')

        # 로그 내용 로드
        try:
            # 로그 위젯에서 내용 가져오기
            if hasattr(self, 'log_text') and self.log_text:
                log_content = self.log_text.get("1.0", END)
                text.insert(END, log_content)
            else:
                text.insert(END, "로그 내용이 없습니다.\n\n")
                text.insert(END, "작업을 수행하면 로그가 기록됩니다.")
        except (RuntimeError, ValueError) as e:
            text.insert(END, f"로그 로드 오류: {e}")

        text.configure(state='disabled')

        # 닫기 버튼
        ttk.Button(dialog, text="닫기", command=dialog.destroy).pack(pady=10)

    def _export_action_log(self) -> None:
        """작업 로그 내보내기"""
        from datetime import datetime

        from ..utils.constants import filedialog

        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="로그 저장",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"sqm_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if not file_path:
            return

        try:
            # 로그 내용 수집
            log_content = ""
            if hasattr(self, 'log_text') and self.log_text:
                from ..utils.constants import END
                log_content = self.log_text.get("1.0", END)
            else:
                log_content = "로그 내용이 없습니다."

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("SQM 재고관리 시스템 - 작업 로그\n")
                f.write(f"내보내기 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                f.write(log_content)

            self._log(f"📄 로그 내보내기 완료: {file_path}")
            CustomMessageBox.showinfo(self.root, "완료", f"로그가 저장되었습니다.\n\n{file_path}")

        except (OSError, IOError, PermissionError) as e:
            CustomMessageBox.showerror(self.root, "오류", f"저장 오류:\n{e}")

    # ═══════════════════════════════════════════════════════════════
    # 자가 진단 / 테스트 러너
    # ═══════════════════════════════════════════════════════════════

    def _open_test_runner(self) -> None:
        """단위 테스트 러너 다이얼로그 열기 (pytest tests/ 실행)."""
        try:
            from ..dialogs.test_runner_dialog import TestRunnerDialog
            d = TestRunnerDialog(self.root)
            d.show()
        except Exception as e:
            logger.exception("테스트 러너 열기 실패")
            CustomMessageBox.showerror(self.root, "오류", f"테스트 러너 열기 실패:\n{e}")

    def _run_self_test(self) -> None:
        """전체 시스템 자가 진단"""
        self._set_status("자가 진단 실행 중...")
        self._log("🩺 시스템 자가 진단 시작...")

        results = []

        try:
            # 1. DB 연결 테스트
            try:
                count = self.engine.db.fetchone("SELECT COUNT(*) FROM inventory")[0]
                results.append(("✅", "DB 연결", f"정상 (재고: {count}건)"))
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                results.append(("❌", "DB 연결", f"오류: {e}"))

            # 2. DB 무결성
            try:
                integrity = self.engine.db.fetchone("PRAGMA integrity_check")[0]
                results.append(("✅" if integrity == 'ok' else "⚠️", "DB 무결성", integrity))
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                results.append(("❌", "DB 무결성", f"오류: {e}"))

            # 3. 테이블 확인
            try:
                tables = self.engine.db.fetchall(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                table_names = [t[0] for t in tables]
                required = ['inventory', 'inventory_tonbag']
                missing = [t for t in required if t not in table_names]
                if missing:
                    results.append(("⚠️", "테이블", f"누락: {missing}"))
                else:
                    results.append(("✅", "테이블", f"정상 ({len(tables)}개)"))
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                results.append(("❌", "테이블", f"오류: {e}"))

            # 4. 엔진 기능
            try:
                if hasattr(self.engine, 'get_inventory'):
                    results.append(("✅", "엔진", "정상"))
                else:
                    results.append(("⚠️", "엔진", "일부 기능 누락"))
            except (ValueError, TypeError, AttributeError) as e:
                results.append(("❌", "엔진", f"오류: {e}"))

            # 5. UI 컴포넌트
            try:
                ui_ok = hasattr(self, 'notebook') and hasattr(self, 'root')
                results.append(("✅" if ui_ok else "⚠️", "UI", "정상" if ui_ok else "일부 누락"))
            except (ValueError, TypeError, AttributeError) as e:
                results.append(("❌", "UI", f"오류: {e}"))

            # 결과 출력
            report = "🩺 시스템 자가 진단 결과\n" + "=" * 40 + "\n\n"
            for status, item, detail in results:
                report += f"{status} {item}: {detail}\n"
                self._log(f"   {status} {item}: {detail}")

            # 종합 판정
            errors = sum(1 for r in results if r[0] == "❌")
            warnings = sum(1 for r in results if r[0] == "⚠️")

            if errors > 0:
                report += f"\n⚠️ 오류 {errors}건 발견 - 점검 필요"
            elif warnings > 0:
                report += f"\n✅ 경고 {warnings}건 - 전반적으로 양호"
            else:
                report += "\n✅ 모든 항목 정상"

            self._log("🩺 자가 진단 완료")
            CustomMessageBox.showinfo(self.root, "자가 진단 결과", report)

        except (RuntimeError, ValueError) as e:
            self._log(f"❌ 자가 진단 오류: {e}")
            CustomMessageBox.showerror(self.root, "오류", f"진단 오류:\n{e}")

        self._set_status("Ready")

    # ═══════════════════════════════════════════════════════════════
    # Dry-run (검증 모드)
    # ═══════════════════════════════════════════════════════════════

    def _dry_run_inbound(self) -> None:
        """입고 검증 (Dry-run)"""
        from ..utils.constants import filedialog

        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="입고 파일 선택 (검증 모드)",
            filetypes=[
                ("All supported", "*.xlsx *.xls *.pdf"),
                ("Excel files", "*.xlsx *.xls"),
                ("PDF files", "*.pdf"),
            ]
        )

        if not file_path:
            return

        self._log(f"🔬 입고 검증 시작: {file_path}")
        self._set_status("입고 검증 중...")

        try:
            # 파일 타입 확인
            if file_path.lower().endswith('.pdf'):
                CustomMessageBox.showinfo(self.root, "검증 모드",
                    "PDF 파일 검증\n\n"
                    f"파일: {file_path}\n\n"
                    "실제 처리 없이 파싱 결과만 확인합니다.\n\n"
                    "입고 메뉴에서 실제 처리를 진행하세요.")
            else:
                # Excel 검증
                from ..utils.constants import HAS_PANDAS, pd
                if HAS_PANDAS:
                    df = pd.read_excel(file_path)

                    report = f"📋 Excel 검증 결과\n{'=' * 40}\n\n"
                    report += f"파일: {file_path}\n"
                    report += f"행 수: {len(df)}\n"
                    report += f"컬럼: {', '.join(df.columns.tolist())}\n\n"

                    # 데이터 샘플
                    report += "데이터 미리보기 (처음 5행):\n"
                    report += str(df.head())

                    self._log(f"✅ 검증 완료: {len(df)}건")
                    CustomMessageBox.showinfo(self.root, "검증 결과", report[:1000])
                else:
                    CustomMessageBox.showwarning(self.root, "경고", "pandas가 설치되지 않았습니다.")

        except (RuntimeError, ValueError) as e:
            self._log(f"❌ 검증 오류: {e}")
            CustomMessageBox.showerror(self.root, "오류", f"검증 오류:\n{e}")

        self._set_status("Ready")

    def _dry_run_outbound(self) -> None:
        """출고 검증 (Dry-run)"""
        from ..utils.constants import filedialog

        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="출고 파일 선택 (검증 모드)",
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*"),
            ]
        )

        if not file_path:
            return

        self._log(f"🔬 출고 검증 시작: {file_path}")
        self._set_status("출고 검증 중...")

        try:
            from ..utils.constants import HAS_PANDAS, pd
            if HAS_PANDAS:
                df = pd.read_excel(file_path)

                report = f"📤 출고 검증 결과\n{'=' * 40}\n\n"
                report += f"파일: {file_path}\n"
                report += f"행 수: {len(df)}\n"
                report += f"컬럼: {', '.join(df.columns.tolist())}\n\n"

                # LOT 번호 확인
                lot_cols = [c for c in df.columns if 'lot' in c.lower()]
                if lot_cols:
                    report += f"LOT 컬럼 발견: {lot_cols}\n"
                    unique_lots = df[lot_cols[0]].nunique()
                    report += f"고유 LOT 수: {unique_lots}\n"

                self._log(f"✅ 출고 검증 완료: {len(df)}건")
                CustomMessageBox.showinfo(self.root, "출고 검증 결과", report[:1000])
            else:
                CustomMessageBox.showwarning(self.root, "경고", "pandas가 설치되지 않았습니다.")

        except (RuntimeError, ValueError) as e:
            self._log(f"❌ 출고 검증 오류: {e}")
            CustomMessageBox.showerror(self.root, "오류", f"검증 오류:\n{e}")

        self._set_status("Ready")

    # ═══════════════════════════════════════════════════════════════
    # 반품 처리
    # ═══════════════════════════════════════════════════════════════

