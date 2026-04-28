"""
SQM 재고관리 - 메뉴 항목 단일 정의 (Menu Registry)
=================================================

custom_menubar.py 와 menu_mixin.py 의 네이티브 메뉴가 동일한 항목을 표시하도록
'파일' 메뉴 내 입고/출고 항목을 여기서만 정의합니다.
새 메뉴 항목은 이 파일에만 추가하면 두 메뉴에 모두 반영됩니다.

각 항목: (라벨, app 메서드명, optional?)
- optional=True 이면 app에 해당 메서드가 있을 때만 메뉴에 추가됩니다.
"""

# 입고 서브메뉴에 들어갈 항목 (순서 유지, v6.0.6 3단계: 단일 소스)
# optional=True 이면 app에 해당 메서드가 있을 때만 메뉴에 추가
FILE_MENU_INBOUND_ITEMS = [
    # v8.3.3 Pro UX: 물류 앱 기준 재편 — 핵심 동작 우선, 관리 기능 후단
    # ── ① 핵심 입고 ────────────────────────────────────────────────
    ("📄  PDF 스캔 입고",           "_on_pdf_inbound"),
    ("📊  엑셀 파일 수동 입고",     "_bulk_import_inventory_simple"),
    None,
    # ── ② D/O · 위치 연결 ──────────────────────────────────────────
    ("📋  D/O 후속 연결",           "_on_do_update"),
    ("📍  톤백 위치 매핑",          "_on_tonbag_location_upload",   True),
    ("✅  대량 이동 승인",          "_on_move_approval_queue",       True),
    None,
    # ── ③ 반품 ─────────────────────────────────────────────────────
    ("🔄  반품 (재입고)",           "_show_return_dialog"),
    ("📂  반품 입고 (Excel)",       "_on_return_inbound_upload"),
    ("📊  반품 사유 통계",          "_show_return_statistics"),
    None,
    # ── ④ 조회 ─────────────────────────────────────────────────────
    ("📋  입고 현황 조회",          "_bulk_import_inventory",        True),
    None,
    # ── ⑤ 관리 ─────────────────────────────────────────────────────
    ("📝  입고 파싱 템플릿 관리",   "_on_inbound_template_manage"),
    ("📦  제품 마스터 관리",        "_show_product_master"),
    ("⚙️  이메일 설정",             "_show_email_config"),
    None,
    # ── ⑥ 정합성 ───────────────────────────────────────────────────
    ("🔍  정합성 검증 (시각화)",    "_on_integrity_report_v760"),
    ("🛠️  LOT 상태 정합성 복구",   "_on_fix_lot_status_integrity"),
]

# 입고 > 반품(재입고) 서브메뉴
FILE_MENU_INBOUND_RETURN_SUB_ITEMS = [
    ("📝 소량 반품 (1~2건)", 0),
    ("📂 다량 반품 (Excel)", 1),
]

# 출고 메뉴 — v8.3.3: 즉시 출고 최우선
FILE_MENU_OUTBOUND_ITEMS = [
    # ── ① 즉시 출고 ─────────────────────────────────────────────────
    ("🚀  즉시 출고 (원스톱)",        "_on_s1_onestop_outbound"),
    ("📤  빠른 출고 (붙여넣기)",      "_on_quick_outbound_paste"),
    None,
    # ── ② 스캔 · 피킹 ──────────────────────────────────────────────
    ("📋  Picking List 업로드 (PDF)", "_on_picking_list_upload"),
    ("📊  바코드 스캔 업로드",        "_on_barcode_scan_upload"),
    ("📷  스캔 탭으로 이동",          "_on_go_scan_tab"),
    None,
    # ── ③ Allocation (사전 예약 필요 시) ───────────────────────────
    ("📋  Allocation 입력",           "_on_allocation_input_unified"),
    ("✅  승인 대기",                 "_show_allocation_approval_queue", True),
    ("📌  예약 반영 (승인분)",        "_apply_approved_allocation",       True),
    ("📜  승인 이력 조회",            "_show_allocation_approval_history",True),
    ("📋  판매 배정 탭으로 이동",     "_on_go_allocation_tab"),
    None,
    # ── ④ 조회 / 기타 ───────────────────────────────────────────────
    ("📋  출고 현황 조회",            "_show_outbound_history",           True),
    ("📊  Sales Order 업로드",        "_on_sales_order_upload",           True),
    ("🔁  Swap 리포트",               "_show_swap_report_dialog",         True),
    ("📦  출고 피킹 템플릿 관리",     "_on_picking_template_manage"),
]

FILE_MENU_EXPORT_ITEMS = [
    ("📋 통관요청 양식", 1),
    ("📊 루비리 양식", 2),
    ("🎒 톤백 현황", 4),
    ("⭐ 통합 현황", 6),
]

# 파일 > 백업 공통 항목 (toolbar/custom/native 공용)
# 각 항목: (라벨, app 메서드명)
FILE_MENU_BACKUP_ITEMS = [
    ("💾 백업 생성", "_on_backup_click"),
    ("🔄 복원", "_on_restore_click"),
    ("📋 백업 목록", "_show_backup_list"),
]

# ─────────────────────────────────────────────────────────────────────────────
# AI 파싱 도구 메뉴 항목 (🤖 Gemini AI 서브메뉴) — v6.4.0
# ─────────────────────────────────────────────────────────────────────────────
FILE_MENU_AI_TOOLS_ITEMS = [
    ('🚢 선사 BL 등록 도구', '_on_bl_carrier_register', True),
    ('🔬 선사 패턴 분석',    '_on_bl_carrier_analyze',  True),
]

# 도구 메뉴 — 감사로그 / 정합성 / 통계
FILE_MENU_TOOLS_ITEMS = [
    ('📋 감사 로그 조회 / Export', '_s1_open_audit_viewer', True),  # v7.6.0
]

# ═══════════════════════════════════════════════════════════════════════════
# Phase 1-A (v8.1.4): 메뉴 단일화 — toolbar / custom_menubar 공용 정의
# ═══════════════════════════════════════════════════════════════════════════

# ── 재고 메뉴 (toolbar [4] 📊 재고 ▼) ──────────────────────────────
# 각 항목: (라벨, app 메서드명, optional?, kwargs?)
MENU_STOCK_ITEMS = [
    ("📊 LOT 리스트 Excel",  "_on_export_click",  False, {"option": 3}),
    ("🎒 톤백리스트 Excel",  "_on_export_click",  False, {"option": 4}),
    None,
    ("📋 출고 현황 조회",    "_show_outbound_history",  True),
    ("📊 재고 추이 차트",    "_show_snapshot_chart",    True),
]

# ── 보고서 메뉴 (toolbar [5] 📝 보고서 ▼) ────────────────────────
MENU_REPORT_ITEMS = [
    ("📄 거래명세서 생성",    "_generate_outbound_invoice"),
    None,
    # ── v8.6.0: 출고 보고서 (Excel + PDF 동시 생성) ──────────────────
    ("📦 Detail of Outbound",  "_on_detail_of_outbound_report"),
    ("📋 Sales Order DN",      "_on_sales_order_dn_report"),
    ("🔍 DN 교차검증",           "_on_dn_cross_check"),         # v8.6.4: 고객 DN vs SQM DB
    None,
    ("📝 고객 보고서 생성",   "_generate_customer_report",  True),
    ("📂 보고서 양식 관리",   "_manage_report_templates",   True),
    None,
    ("📋 보고서 이력 조회",   "_show_report_history",       True),
    ("📦 재고 현황 보고서",   "_generate_inventory_pdf_report"),
    ("📈 입출고 내역",        "_generate_transaction_pdf"),
    ("📅 월간 실적 PDF",      "_generate_monthly_pdf_v398", True),
    ("📊 일일 현황 PDF",      "_generate_daily_pdf_v398",   True),
    ("🔖 LOT 상세",           "_generate_lot_detail_pdf"),
]

# ── 설정/도구 메뉴 정적 항목 (toolbar [6] 🔧 설정/도구 ▼) ─────────
# 동적 항목(테마, 글꼴, 체크버튼)은 빌더에서 직접 생성
MENU_SETTINGS_ITEMS = [
    ("🔄 새로고침 (F5)",          "_refresh_all_data"),
    ("💾 현재 창 크기 저장",      "_on_save_window_size"),
    ("↩️ 기본 창 크기 초기화",    "_on_reset_window_size"),
    None,
    ("📦 제품 마스터 관리",       "_show_product_master"),
    ("📊 제품별 재고 현황",       "_show_product_inventory_report"),
    ("📋 D/O 후속 연결",          "_on_do_update"),
    # v8.7.0 [FIX B-1]: features_v2_mixin._show_stock_alerts 메뉴 연결 복구
    #   (로우스톡·장기재고·유통기한 알림 팝업 — 과거 구현됐으나 UI 연결 누락 상태였음)
    ("🔔 재고 알림 조회",         "_show_stock_alerts"),
    None,
    ("🩺 데이터 정합성 검사",     "_run_integrity_check"),
    ("🔍 정합성 검사/복구",       "_on_integrity_check"),
    ("🔧 DB 최적화",              "_on_optimize_db"),
    ("📋 로그 정리",              "_on_cleanup_logs"),
    ("ℹ️ DB 정보",                "_show_db_info"),
]

# ── 도움말 메뉴 (toolbar [7] ❓ 도움말 ▼) ────────────────────────
MENU_HELP_ITEMS = [
    ("📖 사용법",                 "_show_help"),
    ("⌨️ 단축키 안내",            "_show_shortcuts"),
    None,
    ("📊 STATUS 상태값 안내",     "_show_status_guide",    True),
    ("💾 DB 백업/복구 가이드",    "_show_backup_guide",    True),
    None,
    ("ℹ️ 시스템 정보",            "_show_system_info",     True),
    ("📝 버전 정보",              "_show_about"),
]
