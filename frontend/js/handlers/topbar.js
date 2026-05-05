// SQM v8.6.6
// 새로고침, Dark/Light, 돈백/LOT/MT 라디오
import { showToast } from '../toast.js';
import { refresh as refreshStatus } from '../components/statusbar.js';
import { mountAlerts } from '../components/alerts.js';

export const VIEW_MODES = ['tonbag', 'lot', 'mt'];
let currentViewMode = (() => {
  try { return localStorage.getItem('sqm_view_mode') || 'mt'; } catch { return 'mt'; }
})();

export function getViewMode() { return currentViewMode; }

export function setViewMode(mode) {
  if (!VIEW_MODES.includes(mode)) return;
  currentViewMode = mode;
  try { localStorage.setItem('sqm_view_mode', mode); } catch {}
  document.documentElement.setAttribute('data-view-mode', mode);
  document.dispatchEvent(new CustomEvent('sqm:viewmode-change', { detail: mode }));
}

export function bindTopbar(root = document) {
  // 새로고침
  const refreshBtn = root.querySelector('[data-action="refresh-all"]');
  if (refreshBtn && !refreshBtn.dataset._bound) {
    refreshBtn.addEventListener('click', () => {
      refreshStatus();
      const alertsEl = document.getElementById('alerts-container');
      if (alertsEl) mountAlerts(alertsEl);
      showToast('success', '데이터 새로고침 완료');
    });
    refreshBtn.dataset._bound = '1';
  }

  // Dark/Light — 기존 theme-toggle 은 app.js 에서 처리됨. 여기는 Dark 전용·Light 전용 버튼.
  root.querySelectorAll('[data-action="theme-dark"]').forEach(el => {
    if (el.dataset._bound) return;
    el.addEventListener('click', () => {
      document.documentElement.setAttribute('data-theme', 'dark');
      try { localStorage.setItem('sqm_theme', 'dark'); } catch {}
    });
    el.dataset._bound = '1';
  });
  root.querySelectorAll('[data-action="theme-light"]').forEach(el => {
    if (el.dataset._bound) return;
    el.addEventListener('click', () => {
      document.documentElement.setAttribute('data-theme', 'light');
      try { localStorage.setItem('sqm_theme', 'light'); } catch {}
    });
    el.dataset._bound = '1';
  });

  // 돈백/LOT/MT 라디오
  root.querySelectorAll('[data-view-mode]').forEach(el => {
    if (el.dataset._bound) return;
    el.addEventListener('click', () => setViewMode(el.dataset.viewMode));
    if (el.dataset.viewMode === currentViewMode) el.classList.add('active');
    el.dataset._bound = '1';
  });

  // 초기화 적용
  setViewMode(currentViewMode);
}
