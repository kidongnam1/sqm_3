# v864-3 UI Spec (WebView variant)

Extracted 2026-04-24. Schema parallels `Claude_SQM_v864_2/analysis/v864-2_spec.json`.

## 1. Architecture

| Aspect | v864-2 (Tkinter) | v864-3 (WebView) |
|---|---|---|
| Layout | 7 top-menubar + 9 notebook tabs (no sidebar) | 7 top-menubar + 7-button action toolbar + **9 sidebar tabs** + right-side unit radio |
| Source of truth | `gui_app_modular/toolbar_mixin.py` + `menu_registry.py` + per-tab Python | `frontend/index.html` (static markup) + `frontend/js/sqm-inline.js` (3469 lines, ALL dispatch/modals/pages) |
| Dead code | — | `frontend/js/main.js` + `handlers/{menubar,toolbar,topbar}.js` + `pages/*.js` are ES-modules that index.html does NOT load |
| Backend | in-process engine | FastAPI + pywebview wrapping `http://localhost:8765` |
| Menu backend hook | (N/A) | `backend/api/menubar.py` 634 lines, 62 endpoints — ALL raise NotReadyError; never actually called because sqm-inline routes to `/api/inbound`, `/api/outbound`, `/api/allocation`, `/api/action*`, `/api/q*`, `/api/info` |

## 2. Menubar groups (v864-3)

Order in DOM: 출고 / 파일 / 보고서 / 도구 / View / 도움말 / 품목 → then right-side [🔄 새로고침] [🌙 Dark] [☀️ Light].
Differences vs v864-2:

- No top-level 입고 / 재고 / 검색 groups (입고 items nested under 파일; 재고 split into 도구+품목+View; 🔍 검색 removed entirely)
- New top-level 품목 (3 items) replaces some inventory-drilldown popups
- View menu replaces v864-2 tab-notebook-order selector
- No Gemini AI submenu, no 🚢 BL 선사 도구 submenu, no API settings

### Group counts

| Group | v864-3 items | v864-2 equivalent |
|---|---|---|
| 📤 출고 | 13 | 13 (matches) |
| 📁 파일 | 24 (입고+내보내기+백업+기타 combined) | 9 (file only) + 14 (inbound) = 23 |
| 📝 보고서 | 12 | 16 (report menu) |
| 🔧 도구 | 10 | 21 (settings/tools menu) |
| 👁️ View | 11 | (no equivalent) |
| ❓ 도움말 | 6 | 10 |
| 📦 품목 | 3 | (no equivalent — lived inside inventory tab) |

## 3. Tabs (9, via sidebar)

| Tab | v864-3 source | columns / widgets | v864-2 parity |
|---|---|---|---|
| Inventory | `sqm-inline.js:578-636` | **22** <th> + 새로고침 + per-row Detail button | v864-2 has 24 cols + 24-col sort/filter/status tabs |
| Allocation | `sqm-inline.js:646-756` | 9-col LOT summary + expand → detail panel | v864-2 has 7+6 cols with SALE REF batch cancel, status-revert 3-way buttons, LOT overview popup |
| Picked | `sqm-inline.js:757-917` | LOT summary + detail | v864-2 has 7+7 cols with revert-to-RESERVED |
| Outbound | `sqm-inline.js:987-1090` | LOT summary + detail | v864-2 adds 반품 확정 / 출고 취소 buttons |
| Return | `sqm-inline.js:1091-1131` | simple list | v864-2 has 6-col history + 20-col cargo overview |
| Move | `sqm-inline.js:1132-1192` | movement history list | v864-2 has 7-col with location lookup |
| Dashboard | `sqm-inline.js:423-577` | 4 KPI cards + 5 status cards + product matrix + integrity | v864-2 has 3-zone layout with drill-down popups |
| Log | `sqm-inline.js:1193-1236` | 4-col table (Time/Type/LOT/Detail) + Last 100/500/1000 | v864-2 uses tk.Text with theme-aware tags, Clear/Export |
| Scan | `sqm-inline.js:1241-1372` | Barcode input + 3 quick buttons + history; right-side PDF drop zone (1 file slot) | v864-2 has **5** state-transition buttons + ⚡ 빠른 스캔 + 🔕 무음 toggles |

## 4. Action toolbar (7 buttons)

| Button | data-action | Dispatch |
|---|---|---|
| 📄 PDF 입고 | `tb-pdf-inbound` | JS → showPdfInboundUploadModal (**1 file slot**) |
| 🚀 즉시 출고 | `tb-quick-outbound` | JS → showQuickOutboundModal (form, no file slot) |
| 🔄 반품 | `tb-return` | JS → renderPage('return') *(opens Return TAB, not ReturnDialog)* |
| 📋 재고 조회 | `tb-inventory` | JS → renderPage('inventory') |
| ✅ 정합성 | `tb-integrity` | GET /api/action/integrity-check |
| 💾 백업 | `tb-backup` | POST /api/action/backup-create |
| ⚙️ 설정 | `tb-settings` | POST /api/menu/-on-settings **(NOT_READY — toast-only dead button)** |

## 5. PDF Inbound upload — THE GAP

**v864-2** (`gui_app_modular/dialogs/onestop_inbound.py`, 4302 lines)
- 4 upload slots: ① BL ② Packing List ③ Invoice ④ D/O (optional)
- Per-slot file selection buttons, 📁 멀티 선택, ▶ 파싱 시작, ↻ 다시 파싱, 📋 D/O 나중에, 🚢 선사 재파싱
- 적용 템플릿 Combobox, 🚢 선사 Combobox
- 18-col preview Treeview with inline edit, sort ▲▼, HeaderFilterBar
- undo/redo stack (max 50)
- Parse-error recovery sub-dialog (9 ERROR_CODES)

**v864-3** (`frontend/js/sqm-inline.js:2053` calls `_showPdfUploadModal` at line 1949)
- **1 upload slot** (id `pdf-drop2-input`, accept `.pdf`, line 1961)
- Drag-drop zone + click-to-open file picker
- Uploads to `POST /api/inbound/pdf-upload` (single file multipart)
- No preview table, no per-document-type routing, no template combobox, no carrier combobox, no undo/redo, no error recovery

**The user complaint "v864-2 has 4, v864-3 has 1" is confirmed exact.**

## 6. Dispatch table (sqm-inline.js ~line 3015)

62 actions registered. Classified as:
- `m:'JS'` → native HTML modal (22 actions)
- `m:'GET'` → generic `renderInfoModal(label, url)` that just pretty-prints JSON response (28 actions)
- `m:'POST'` → fire-and-forget API call + toast (12 actions)

Unregistered actions (present in `data-action` but NOT in ENDPOINTS) fall through to `[unregistered]` toast at line 3157.

## 7. Handler mapping (v864-2 → v864-3)

See `v864-3_spec.json` → `"v864_2_handler_map"` for the full table. Highlights:

- `_on_pdf_inbound` → `onOnPdfInbound`
- `_on_s1_onestop_outbound` → `onOnQuickOutbound`
- `_show_return_dialog` → `onReturnDialog` (dual-tab manual/excel)
- `_on_picking_list_upload` → `onPickingListUpload`
- `_apply_approved_allocation` → `onApplyApproved` (no modal, direct POST)

Missing (no handler in v864-3):
- `_on_sales_order_upload`, `_show_swap_report_dialog`, `_on_bl_carrier_register`, `_on_bl_carrier_analyze`, `_s1_open_audit_viewer`, `_show_snapshot_chart`
- `_open_ai_chat`, `_show_api_settings`, `_test_gemini_api_connection`, `_toggle_gemini` (entire Gemini submenu)
- `_batch_convert_pdf_excel`, `_analyze_pdf` (PDF tools collapsed into 1 generic modal)

## 8. Missing modals (handler exists, no dedicated UI)

1. `onSettings` / `tb-settings` — posts to NOT_READY backend, no SettingsDialog; toolbar ⚙️ 설정 is a dead button
2. `onIntegrityReport` / `onFixLotIntegrity` — raw JSON via renderInfoModal; no traffic-light visualization
3. `onReportTemplates` / `onReportHistory` — point at `/api/q/audit-log` (wrong endpoint), no template/history UI
4. `onDnCrossCheck` — GET only, no DNCheckDialog equivalent
5. `onProductMaster` — GET /api/info/system-info, no CRUD dialog
6. `onInboundTemplateManage` / `onPickingTemplateManage` — stub `showSettingsDialog` with 4 unwired fields
7. `onApprovalHistory` / `onReturnStatistics` — read-only renderInfoModal, no charts/tables
8. `onLotDetailPdf` — no detail preview dialog
9. `onExit` — no confirm dialog, straight pywebview.exit_app

## 9. All modals (29 functions + 5 helpers in sqm-inline.js)

Full list with line numbers in `v864-3_modals.md`. Summary counts:
- Upload modals (1 file slot each): **8** (PDF inbound, Picking List PDF, Manual Excel, Return Excel, Allocation Excel, Tonbag location, Barcode scan, Doc convert)
- Form modals: 6 (quick outbound, quick paste, outbound confirm, do update, inbound cancel, test DB reset)
- Tabular modals: 6 (approval queue, restore, lot allocation audit, move approval, product summary/lot lookup/movement)
- Settings-stub modals: 4 (email config, auto backup, inbound template, picking template) — all use `showSettingsDialog` helper
- Other: 5 (return dialog, apply approved allocation, + 3 helpers: `showDataModal`, `_showPdfUploadModal`, `_showExcelUploadModal`, `renderInfoModal`, `showSettingsDialog`)
