// SQM v8.6.6
// 자동 생성 — feature_matrix.json 의 category=toolbar_button 2건 + 스크린샷 기반 7개
import { apiCall } from '../api-client.js';
import { showToast } from '../toast.js';

export const TOOLBAR_MAP_AUTO = {
  "onRefreshAllData": { id: "F084", method: "POST", endpoint: "/api/toolbar/-refresh-all-data", label: "🔄 새로고침" },
  "onToggleTheme": { id: "F085", method: "POST", endpoint: "/api/toolbar/-toggle-theme", label: "🎨 테마 토글" },
};

// Golden Reference 기반 툴바 7개 (feature_matrix 에 없어도 UI 반응 보장)
export const TOOLBAR_MAP = {
  "tb-pdf-inbound":   { method: "POST", endpoint: "/api/menu/-on-pdf-inbound", label: "📄 PDF 입고" },
  "tb-quick-outbound":{ method: "POST", endpoint: "/api/menu/-on-quick-outbound", label: "🚀 즉시 출고" },
  "tb-return":        { method: "POST", endpoint: "/api/menu/-on-return", label: "🔄 반품" },
  "tb-inventory":     { method: "GET",  endpoint: "/api/inventory", label: "📋 재고 조회" },
  "tb-integrity":     { method: "GET",  endpoint: "/api/integrity/quick", label: "✅ 정합성" },
  "tb-backup":        { method: "POST", endpoint: "/api/menu/-on-backup", label: "💾 백업" },
  "tb-settings":      { method: "POST", endpoint: "/api/menu/-on-settings", label: "⚙️ 설정" },
  ...TOOLBAR_MAP_AUTO,
};

export function bindToolbar(root = document) {
  Object.entries(TOOLBAR_MAP).forEach(([action, conf]) => {
    const el = root.querySelector(`[data-action="${action}"]`);
    if (!el || el.dataset._bound) return;
    el.addEventListener('click', async (ev) => {
      ev.preventDefault();
      try {
        const res = await apiCall(conf.method, conf.endpoint, {});
        showToast('success', conf.label + ' 완료');
      } catch (e) {
        showToast(e.status === 501 ? 'info' : 'error',
                  conf.label + (e.status === 501 ? ' (준비 중)' : ' 실패: ' + e.message));
      }
    });
    el.dataset._bound = '1';
  });
}
