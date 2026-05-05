// SQM v8.6.6
// Golden Reference: 돈백 무결성 이슈, 위치 미배정 등 경고 2건 표시

import { apiGet } from '../api-client.js';

const FALLBACK_ALERTS = [
  {
    severity: 'warning',
    icon: '🏷️',
    text: '톤백 무결성 이슈 40건 — inventory.current_weight ≠ inventory_tonbag 합산 불일치 LOT 감지. [재고관리 → 정합성 검사]에서 LOT별 수동 확인 및 보정 필요',
    link: '#integrity',
  },
  {
    severity: 'error',
    icon: '📍',
    text: '위치 미배정 톤백 400개 (5 LOT) — 입고 후 창고 행·열·단 위치가 미지정 상태. 재고 실사 및 위치 추적 불가 — [재고관리 → 위치배정] 즉시 처리 필요',
    link: '#allocation',
  },
];

export async function mountAlerts(container) {
  if (!container) return;
  try {
    const res = await apiGet('/api/dashboard/alerts');
    render(container, res?.data ?? res?.alerts ?? FALLBACK_ALERTS);
  } catch (e) {
    // API 없으면 폴백 데이터로 UI 는 유지 (NO-STOP)
    render(container, FALLBACK_ALERTS);
  }
}

function render(container, alerts) {
  const count = alerts.length;
  container.innerHTML = `
    <div class="alerts-header">
      <span class="alerts-title">⚠️ ALERTS 알림 및 경고</span>
      <span class="alerts-counter">${count > 0 ? `🔴 ${count}` : ''}</span>
    </div>
    <ul class="alerts-list">
      ${alerts.map(a => `
        <li class="alert alert-${a.severity}">
          <span class="alert-icon">${a.icon}</span>
          <span class="alert-text">${escapeHtml(a.text)}</span>
          ${a.link ? `<a class="alert-link" href="${a.link}">바로가기</a>` : ''}
        </li>
      `).join('')}
    </ul>`;
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, m =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])
  );
}

export function startAlertsAutoRefresh(container, intervalMs = 30000) {
  mountAlerts(container);
  return setInterval(() => {
    if (document.visibilityState === 'visible') mountAlerts(container);
  }, intervalMs);
}
