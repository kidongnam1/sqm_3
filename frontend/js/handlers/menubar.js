// SQM v864.3 — Menubar Handlers (Tier 2 Stage 4)
// 자동 생성 — feature_matrix.json 의 category=menubar 62건
import { apiCall } from '../api-client.js';
import { showToast } from '../toast.js';

export const MENUBAR_MAP = {
  "onOnPdfInbound": { id: "F001", method: "POST", endpoint: "/api/menu/-on-pdf-inbound", label: "📄  PDF 스캔 입고" },
  "onBulkImportInventorySimple": { id: "F002", method: "POST", endpoint: "/api/menu/-bulk-import-inventory-simple", label: "📊  엑셀 파일 수동 입고" },
  "onOnDoUpdate": { id: "F003", method: "POST", endpoint: "/api/menu/-on-do-update", label: "📋  D/O 후속 연결" },
  "onOnTonbagLocationUpload": { id: "F004", method: "POST", endpoint: "/api/menu/-on-tonbag-location-upload", label: "📍  톤백 위치 매핑" },
  "onOnMoveApprovalQueue": { id: "F005", method: "POST", endpoint: "/api/menu/-on-move-approval-queue", label: "✅  대량 이동 승인" },
  "onShowReturnDialog": { id: "F006", method: "POST", endpoint: "/api/menu/-show-return-dialog", label: "🔄  반품 (재입고)" },
  "onOnReturnInboundUpload": { id: "F007", method: "POST", endpoint: "/api/menu/-on-return-inbound-upload", label: "📂  반품 입고 (Excel)" },
  "onShowReturnStatistics": { id: "F008", method: "POST", endpoint: "/api/menu/-show-return-statistics", label: "📊  반품 사유 통계" },
  "onBulkImportInventory": { id: "F009", method: "POST", endpoint: "/api/menu/-bulk-import-inventory", label: "📋  입고 현황 조회" },
  "onOnInboundTemplateManage": { id: "F010", method: "POST", endpoint: "/api/menu/-on-inbound-template-manage", label: "📝  입고 파싱 템플릿 관리" },
  "onInboundTemplateManage": { id: "F010", method: "POST", endpoint: "/api/menu/-on-inbound-template-manage", label: "📝  입고 파싱 템플릿 관리" },
  "onShowProductMaster": { id: "F011", method: "POST", endpoint: "/api/menu/-show-product-master", label: "📦  제품 마스터 관리" },
  "onShowEmailConfig": { id: "F012", method: "POST", endpoint: "/api/menu/-show-email-config", label: "⚙️  이메일 설정" },
  "onOnIntegrityReportV760": { id: "F013", method: "POST", endpoint: "/api/menu/-on-integrity-report-v760", label: "🔍  정합성 검증 (시각화)" },
  "onOnFixLotStatusIntegrity": { id: "F014", method: "POST", endpoint: "/api/menu/-on-fix-lot-status-integrity", label: "🛠️  LOT 상태 정합성 복구" },
  "onOnS1OnestopOutbound": { id: "F015", method: "POST", endpoint: "/api/menu/-on-s1-onestop-outbound", label: "🚀  즉시 출고 (원스톱)" },
  "onOnQuickOutboundPaste": { id: "F016", method: "POST", endpoint: "/api/menu/-on-quick-outbound-paste", label: "📤  빠른 출고 (붙여넣기)" },
  "onOnPickingListUpload": { id: "F017", method: "POST", endpoint: "/api/menu/-on-picking-list-upload", label: "📋  Picking List 업로드 (PDF)" },
  "onOnBarcodeScanUpload": { id: "F018", method: "POST", endpoint: "/api/menu/-on-barcode-scan-upload", label: "📊  바코드 스캔 업로드" },
  "onOnGoScanTab": { id: "F019", method: "POST", endpoint: "/api/menu/-on-go-scan-tab", label: "📷  스캔 탭으로 이동" },
  "onOnAllocationInputUnified": { id: "F020", method: "POST", endpoint: "/api/menu/-on-allocation-input-unified", label: "📋  Allocation 입력" },
  "onShowAllocationApprovalQueue": { id: "F021", method: "POST", endpoint: "/api/menu/-show-allocation-approval-queue", label: "✅  승인 대기" },
  "onApplyApprovedAllocation": { id: "F022", method: "POST", endpoint: "/api/menu/-apply-approved-allocation", label: "📌  예약 반영 (승인분)" },
  "onShowAllocationApprovalHistory": { id: "F023", method: "POST", endpoint: "/api/menu/-show-allocation-approval-history", label: "📜  승인 이력 조회" },
  "onOnGoAllocationTab": { id: "F024", method: "POST", endpoint: "/api/menu/-on-go-allocation-tab", label: "📋  판매 배정 탭으로 이동" },
  "onShowOutboundHistory": { id: "F025", method: "POST", endpoint: "/api/menu/-show-outbound-history", label: "📋  출고 현황 조회" },
  "onOnSalesOrderUpload": { id: "F026", method: "POST", endpoint: "/api/menu/-on-sales-order-upload", label: "📊  Sales Order 업로드" },
  "onShowSwapReportDialog": { id: "F027", method: "POST", endpoint: "/api/menu/-show-swap-report-dialog", label: "🔁  Swap 리포트" },
  "onOnPickingTemplateManage": { id: "F028", method: "POST", endpoint: "/api/menu/-on-picking-template-manage", label: "📦  출고 피킹 템플릿 관리" },
  "onOnBackupClick": { id: "F029", method: "POST", endpoint: "/api/menu/-on-backup-click", label: "💾 백업 생성" },
  "onOnRestoreClick": { id: "F030", method: "POST", endpoint: "/api/menu/-on-restore-click", label: "🔄 복원" },
  "onShowBackupList": { id: "F031", method: "POST", endpoint: "/api/menu/-show-backup-list", label: "📋 백업 목록" },
  "onOnBlCarrierRegister": { id: "F032", method: "POST", endpoint: "/api/menu/-on-bl-carrier-register", label: "🚢 선사 BL 등록 도구" },
  "onOnBlCarrierAnalyze": { id: "F033", method: "POST", endpoint: "/api/menu/-on-bl-carrier-analyze", label: "🔬 선사 패턴 분석" },
  "onS1OpenAuditViewer": { id: "F034", method: "POST", endpoint: "/api/menu/-s1-open-audit-viewer", label: "📋 감사 로그 조회 / Export" },
  "onOnExportClick": { id: "F035", method: "POST", endpoint: "/api/menu/-on-export-click", label: "📊 LOT 리스트 Excel" },
  "onOnExportClick": { id: "F036", method: "POST", endpoint: "/api/menu/-on-export-click", label: "🎒 톤백리스트 Excel" },
  "onShowOutboundHistory": { id: "F037", method: "POST", endpoint: "/api/menu/-show-outbound-history", label: "📋 출고 현황 조회" },
  "onShowSnapshotChart": { id: "F038", method: "POST", endpoint: "/api/menu/-show-snapshot-chart", label: "📊 재고 추이 차트" },
  "onGenerateOutboundInvoice": { id: "F039", method: "POST", endpoint: "/api/menu/-generate-outbound-invoice", label: "📄 거래명세서 생성" },
  "onOnDetailOfOutboundReport": { id: "F040", method: "POST", endpoint: "/api/menu/-on-detail-of-outbound-report", label: "📦 Detail of Outbound" },
  "onOnSalesOrderDnReport": { id: "F041", method: "POST", endpoint: "/api/menu/-on-sales-order-dn-report", label: "📋 Sales Order DN" },
  "onOnDnCrossCheck": { id: "F042", method: "POST", endpoint: "/api/menu/-on-dn-cross-check", label: "🔍 DN 교차검증" },
  "onGenerateCustomerReport": { id: "F043", method: "POST", endpoint: "/api/menu/-generate-customer-report", label: "📝 고객 보고서 생성" },
  "onManageReportTemplates": { id: "F044", method: "POST", endpoint: "/api/menu/-manage-report-templates", label: "📂 보고서 양식 관리" },
  "onShowReportHistory": { id: "F045", method: "POST", endpoint: "/api/menu/-show-report-history", label: "📋 보고서 이력 조회" },
  "onGenerateInventoryPdfReport": { id: "F046", method: "POST", endpoint: "/api/menu/-generate-inventory-pdf-report", label: "📦 재고 현황 보고서" },
  "onGenerateTransactionPdf": { id: "F047", method: "POST", endpoint: "/api/menu/-generate-transaction-pdf", label: "📈 입출고 내역" },
  "onGenerateMonthlyPdfV398": { id: "F048", method: "POST", endpoint: "/api/menu/-generate-monthly-pdf-v398", label: "📅 월간 실적 PDF" },
  "onGenerateDailyPdfV398": { id: "F049", method: "POST", endpoint: "/api/menu/-generate-daily-pdf-v398", label: "📊 일일 현황 PDF" },
  "onGenerateLotDetailPdf": { id: "F050", method: "POST", endpoint: "/api/menu/-generate-lot-detail-pdf", label: "🔖 LOT 상세" },
  "onRefreshAllData": { id: "F051", method: "POST", endpoint: "/api/menu/-refresh-all-data", label: "🔄 새로고침 (F5)" },
  "onOnSaveWindowSize": { id: "F052", method: "POST", endpoint: "/api/menu/-on-save-window-size", label: "💾 현재 창 크기 저장" },
  "onOnResetWindowSize": { id: "F053", method: "POST", endpoint: "/api/menu/-on-reset-window-size", label: "↩️ 기본 창 크기 초기화" },
  "onShowProductMaster": { id: "F054", method: "POST", endpoint: "/api/menu/-show-product-master", label: "📦 제품 마스터 관리" },
  "onShowProductInventoryReport": { id: "F055", method: "POST", endpoint: "/api/menu/-show-product-inventory-report", label: "📊 제품별 재고 현황" },
  "onOnDoUpdate": { id: "F056", method: "POST", endpoint: "/api/menu/-on-do-update", label: "📋 D/O 후속 연결" },
  "onShowHelp": { id: "F057", method: "POST", endpoint: "/api/menu/-show-help", label: "📖 사용법" },
  "onShowShortcuts": { id: "F058", method: "POST", endpoint: "/api/menu/-show-shortcuts", label: "⌨️ 단축키 안내" },
  "onShowStatusGuide": { id: "F059", method: "POST", endpoint: "/api/menu/-show-status-guide", label: "📊 STATUS 상태값 안내" },
  "onShowBackupGuide": { id: "F060", method: "POST", endpoint: "/api/menu/-show-backup-guide", label: "💾 DB 백업/복구 가이드" },
  "onShowSystemInfo": { id: "F061", method: "POST", endpoint: "/api/menu/-show-system-info", label: "ℹ️ 시스템 정보" },
  "onShowAbout": { id: "F062", method: "POST", endpoint: "/api/menu/-show-about", label: "📝 버전 정보" },
};

export function bindMenubar(root = document) {
  root.querySelectorAll('[data-action]').forEach(el => {
    if (el.dataset._bound) return;
    const action = el.dataset.action;
    const conf = MENUBAR_MAP[action];
    if (!conf) return;
    el.addEventListener('click', (ev) => {
      ev.preventDefault();
      dispatch(action, conf);
    });
    el.dataset._bound = '1';
  });
}

async function dispatch(action, conf) {
  try {
    const res = await apiCall(conf.method, conf.endpoint, {});
    showToast('success', conf.label + ' 완료');
    return res;
  } catch (e) {
    if (e.status === 501) {
      showToast('info', conf.label + ' (준비 중)');
    } else {
      showToast('error', conf.label + ' 실패: ' + (e.message || 'unknown'));
    }
  }
}
