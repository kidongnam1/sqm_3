# v864-3 Modals — Full Inventory

All modals live in `frontend/js/sqm-inline.js` (the active bundle loaded by `index.html`). No modals live in `pages/*.js` or any other file. Helpers: `showDataModal` (line 1428), `_showExcelUploadModal` (line 1437), `_showPdfUploadModal` (line 1949), `showSettingsDialog` (line 2681), `renderInfoModal` (line 2929).

Legend: **UL** = upload slots (distinct `<input type="file">` elements in the modal's HTML template).

## Upload modals (file slots per modal)

| Line | Function | Handler / Action | Title | Helper | UL | Endpoint |
|---|---|---|---|---|---|---|
| 2053 | `showPdfInboundUploadModal` | `onOnPdfInbound`, `tb-pdf-inbound` | 📄 PDF 스캔 입고 (Packing List) | `_showPdfUploadModal` | **1** | POST /api/inbound/pdf-upload |
| 2075 | `showPickingListPdfModal` | `onPickingListUpload` | 📋 Picking List PDF 업로드 | `_showPdfUploadModal` | **1** | POST /api/outbound/picking-list-pdf |
| 1575 | `showInboundManualUploadModal` | `onInboundManual` | 📊 수동 입고 — Excel 업로드 | `_showExcelUploadModal` | **1** | POST /api/inbound/bulk-import-excel |
| 1597 | `showReturnInboundUploadModal` | `onReturnInboundUpload` | 🔄 반품 입고 — Excel 업로드 | `_showExcelUploadModal` | **1** | POST /api/inbound/return-excel |
| 1616 | `showAllocationUploadModal` | `onInventoryAllocation` | 📍 Allocation 입력 — Excel 업로드 | `_showExcelUploadModal` | **1** | POST /api/allocation/bulk-import-excel |
| 1796 | `showTonbagLocationUploadModal` | `onInventoryMove` | 📍 톤백 위치 매핑 — Excel 업로드 | `_showExcelUploadModal` | **1** | POST /api/inventory/tonbag-location |
| 2666 | `showBarcodeScanUploadModal` | `onBarcodeScanUpload` | 📊 바코드 스캔 업로드 | `_showExcelUploadModal` | **1** | POST /api/inbound/bulk-import-excel |
| 2773 | `showDocConvertModal` | `onDocConvert` | 📷 문서 변환 (OCR/PDF) | (inline, own file input `dc-file`) | **1** | (Phase 6 stub — toast only) |

**Total file upload slots across every v864-3 modal: 8 slots × 1 = 8 file slots.**
v864-2 equivalent counts for the same 8 workflows: 4 (OneStopInbound) + 1 (PickingList) + 1 + 1 + 1 + 1 + 1 + N/A = 10 slots just on the BL+PL+Invoice+DO row alone.

## Form modals (no file uploads)

| Line | Function | Handler | Title | Form fields |
|---|---|---|---|---|
| 1644 | `showQuickOutboundModal` | `onOnQuickOutbound`, `tb-quick-outbound` | 🚀 즉시 출고 (원스톱) | qo-lot, qo-count, qo-customer, qo-reason, qo-operator |
| 2098 | `showQuickOutboundPasteModal` | `onQuickOutboundPaste` | 📤 빠른 출고 (붙여넣기) | qop-text (textarea), qop-customer, qop-reason, qop-operator |
| 2209 | `showOutboundConfirmModal` | `onOutboundConfirm` | ✅ 출고 확정 — PICKED → OUTBOUND | oc-lot, oc-force-all |
| 1820 | `showDoUpdateModal` | `onDoUpdate` | 📋 D/O 후속 연결 | (date range + LOT filter) |
| 2325 | `showInboundCancelModal` | `onInboundCancel` | 입고 취소 | LOT no + reason |
| 2616 | `showTestDbResetModal` | `onTestDbReset` | 🗑️ 테스트 DB 초기화 | dbr-confirm checkbox |

## Tabular / query modals

| Line | Function | Handler | Title | Data source |
|---|---|---|---|---|
| 1899 | `showApplyApprovedAllocationModal` | `onApplyApproved` | 📌 예약 반영 (승인분) | POST /api/allocation/apply-approved |
| 2379 | `showApprovalQueueModal` | `onApprovalQueue` | ✅ 승인 대기 | GET /api/q/approval-queue |
| 2406 | `showRestoreModal` | `onRestore` | 🔄 복원 | GET /api/q/backup-list |
| 2483 | `showReturnDialog` | `onReturnDialog` | 🔄 반품 (재입고) | tab1: POST /api/action3/return-create, tab2: delegates to showReturnInboundUploadModal |
| 2576 | `showLotAllocationAuditModal` | `onLotAllocationAudit` | 📊 LOT Allocation·톤백 현황 | GET /api/q/product-inventory |
| 2747 | `showMoveApprovalQueueModal` | `onMoveApprovalQueue` | ✅ 대량 이동 승인 | GET /api/q/audit-log (filtered) |
| 2823 | `showProductSummaryModal` | `onProductSummary` | 📋 품목별 재고 요약 | GET /api/q/product-inventory (grouped) |
| 2857 | `showProductLotLookupModal` | `onProductLotLookup` | 🔍 품목별 LOT 조회 | GET /api/q/product-inventory (filtered) |
| 2896 | `showProductMovementModal` | `onProductMovement` | 📊 품목별 입출고 현황 | GET /api/q/movement-history |

## Settings-stub modals

All 4 invoke `showSettingsDialog(title, icon, fields)` (helper at line 2681) with hardcoded field lists. **None persist — they are placeholder forms without a save endpoint.**

| Line | Function | Handler | Title |
|---|---|---|---|
| 2703 | `showEmailConfigModal` | `onEmailConfig` | ⚙️ 이메일 설정 (host/port/user/pass/tls) |
| 2714 | `showAutoBackupSettingsModal` | `onAutoBackupSettings` | ⏰ 자동 백업 설정 (enabled/interval/retention/path) |
| 2724 | `showInboundTemplateModal` | `onInboundTemplateManage` | 📝 입고 파싱 템플릿 관리 (name/format/cols/skip) |
| 2734 | `showPickingTemplateModal` | `onPickingTemplateManage` | 📦 출고 피킹 템플릿 관리 (name/format/cols/sort) |

## Helpers (not user-facing modals, but referenced by all above)

| Line | Function | Purpose |
|---|---|---|
| 1428 | `showDataModal(title, html)` | Generic overlay (#sqm-modal container) used by most `show*Modal` |
| 1437 | `_showExcelUploadModal(opts)` | Shared 1-slot .xlsx/.xls upload modal with progress bar (id `xls-file-input` at 1449) |
| 1949 | `_showPdfUploadModal(opts)` | Shared 1-slot .pdf upload modal with drag-drop + progress bar (id `pdf-drop2-input` at 1961) |
| 2681 | `showSettingsDialog(title, icon, fields)` | Renders any grid of text/number/password/select/checkbox fields — used only by the 4 stub modals |
| 2929 | `renderInfoModal(title, endpoint)` | GET endpoint, pretty-print JSON. Used by 28+ GET actions that have no dedicated dialog |

## Cross-reference: every `<input type="file">` in sqm-inline.js

| Line | Element id | accept | Purpose |
|---|---|---|---|
| 1270 | `pdf-file-input` | `.pdf` | **Scan TAB's right-side PDF panel** (separate from modal) — invokes `window.PdfInbound.handleFile` |
| 1449 | `xls-file-input` | `.xlsx,.xls` | `_showExcelUploadModal` (shared across 6 modals) |
| 1961 | `pdf-drop2-input` | `.pdf` | `_showPdfUploadModal` (shared across 2 modals) |
| 2789 | `dc-file` | `.pdf,.png,.jpg,.jpeg,.tiff,.bmp` | `showDocConvertModal` only |

**Exactly 4 distinct file-input elements exist in the entire v864-3 UI, each with accept=".pdf" or similar, each in its own modal/panel. No modal contains more than one `<input type="file">`.**

## Confirmed answer to the user's question

> "v864-2 has 4, v864-3 has 1."

- **v864-2 PDF inbound dialog** (`_on_pdf_inbound` → `OneStopInboundDialog` in `onestop_inbound.py`, 4302 lines): **4 upload slots** (BL / Packing List / Invoice / D/O).
- **v864-3 PDF inbound modal** (`onOnPdfInbound` → `showPdfInboundUploadModal` at `sqm-inline.js:2053` → `_showPdfUploadModal` at `sqm-inline.js:1949`, 103 lines): **1 upload slot** (`<input type="file" id="pdf-drop2-input" accept=".pdf">` at line 1961).

Gap: 3 missing slots (no BL, no Invoice, no D/O) plus the supporting UI (per-slot select buttons, 적용 템플릿 combobox, 🚢 선사 combobox, 18-col preview, undo/redo, parse-error recovery) — all absent.
