// SQM v8.6.6
// 30초 주기, 탭 hidden 시 일시정지, 실패 3연속 시 60초 백오프
import { startStatusAutoRefresh } from './statusbar.js';
import { startAlertsAutoRefresh } from './alerts.js';
import { showToast } from '../toast.js';

const BASE_INTERVAL = 30000;
const BACKOFF_INTERVAL = 60000;
const MAX_CONSECUTIVE_FAILS = 3;

let statusTimer = null;
let alertsTimer = null;
let failCount = 0;
let currentInterval = BASE_INTERVAL;

export function startAutoRefresh() {
  const alertsEl = document.getElementById('alerts-container');
  statusTimer = startStatusAutoRefresh(currentInterval);
  if (alertsEl) alertsTimer = startAlertsAutoRefresh(alertsEl, currentInterval);

  // 실패 감지 및 백오프
  window.addEventListener('sqm:api-fail', onFail);
  window.addEventListener('sqm:api-success', onSuccess);

  // 탭 활성화 변화 감지
  document.addEventListener('visibilitychange', () => {
    // Visible 전환 시 즉시 한 번 재호출
    if (document.visibilityState === 'visible') {
      window.dispatchEvent(new Event('sqm:force-refresh'));
    }
  });
}

function onFail() {
  failCount++;
  if (failCount >= MAX_CONSECUTIVE_FAILS && currentInterval !== BACKOFF_INTERVAL) {
    currentInterval = BACKOFF_INTERVAL;
    restart();
    showToast('warning', '자동 갱신 일시 지연 (60초로 전환)');
  }
}

function onSuccess() {
  if (failCount > 0) failCount = 0;
  if (currentInterval !== BASE_INTERVAL) {
    currentInterval = BASE_INTERVAL;
    restart();
  }
}

function restart() {
  if (statusTimer) clearInterval(statusTimer);
  if (alertsTimer) clearInterval(alertsTimer);
  const alertsEl = document.getElementById('alerts-container');
  statusTimer = startStatusAutoRefresh(currentInterval);
  if (alertsEl) alertsTimer = startAlertsAutoRefresh(alertsEl, currentInterval);
}

export function stopAutoRefresh() {
  if (statusTimer) clearInterval(statusTimer);
  if (alertsTimer) clearInterval(alertsTimer);
  statusTimer = alertsTimer = null;
}
