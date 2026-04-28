// SQM v864.3 — Toast 통합 모듈 (Tier 2 Stage 4)
// 4타입 통일: success / info / warning / error
const ICONS = { success: '✅', info: 'ℹ️', warning: '⚠️', error: '❌' };
const DEFAULT_DURATION = 3000;

function ensureContainer() {
  let c = document.getElementById('toast-container');
  if (!c) {
    c = document.createElement('div');
    c.id = 'toast-container';
    document.body.appendChild(c);
  }
  return c;
}

export function showToast(type, message, duration = DEFAULT_DURATION) {
  if (!['success', 'info', 'warning', 'error'].includes(type)) type = 'info';
  const container = ensureContainer();
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${ICONS[type]}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 300ms';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, m =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])
  );
}

if (typeof window !== 'undefined') window.showToast = showToast;
