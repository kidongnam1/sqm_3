// SQM v864.3 — Main Entry Point (Tier 2 Stage 5 통합)
console.info('[SQM v864.3] main.js 로드 시작');

// 모듈 import — 단계별로 try/catch
let mods = {};
async function loadModules() {
  const items = [
    ['toast',   () => import('./toast.js')],
    ['apicli',  () => import('./api-client.js')],
    ['router',  () => import('./router.js')],
    ['menubar', () => import('./handlers/menubar.js')],
    ['toolbar', () => import('./handlers/toolbar.js')],
    ['topbar',  () => import('./handlers/topbar.js')],
    ['short',   () => import('./shortcuts.js')],
    ['state',   () => import('./state.js')],
    ['alerts',  () => import('./components/alerts.js')],
    ['status',  () => import('./components/statusbar.js')],
    ['refresh', () => import('./components/auto_refresh.js')],
  ];
  for (const [name, fn] of items) {
    try {
      mods[name] = await fn();
      console.info(`[SQM] OK 모듈: ${name}`);
    } catch (e) {
      console.error(`[SQM] FAIL 모듈: ${name}`, e);
    }
  }
}

// fail-safe 메뉴 핸들러 — 모듈 로드 전에도 메뉴 클릭이 죽지 않게
function installFailSafe() {
  document.querySelectorAll('[data-action]').forEach(el => {
    el.addEventListener('click', (ev) => {
      const action = el.dataset.action;
      // 진짜 핸들러가 바인딩됐으면 그쪽이 처리, 아니면 토스트라도
      if (!el.dataset._bound) {
        ev.preventDefault();
        const msg = `[준비 중]${el.textContent.trim()} (action=${action})`;
        if (window.showToast) window.showToast('info', msg);
        else console.info(msg);
      }
    });
  });
  // 사이드바 라우트도 fail-safe
  document.querySelectorAll('[data-route]').forEach(el => {
    el.addEventListener('click', (ev) => {
      if (!el.dataset._bound) {
        ev.preventDefault();
        document.querySelectorAll('[data-route]').forEach(e => e.classList.remove('active'));
        el.classList.add('active');
        const target = document.getElementById('page-container');
        if (target) target.innerHTML = '<div class="empty">' + el.textContent.trim() + ' 페이지 (모듈 로딩 대기...)</div>';
      }
    });
  });
  console.info('[SQM] fail-safe 핸들러 설치 완료');
}

async function boot() {
  console.info('[SQM v864.3] boot 시작');
  installFailSafe();
  await loadModules();
  try { mods.state?.initStatePersistence?.(); } catch (e) { console.error('state init', e); }
  const alertsEl = document.getElementById('alerts-container');
  if (alertsEl && mods.alerts?.mountAlerts) {
    try { await mods.alerts.mountAlerts(alertsEl); } catch (e) { console.error('alerts', e); }
  }
  const statusbarEl = document.getElementById('statusbar-container');
  if (statusbarEl && mods.status?.mountStatusbar) {
    try { await mods.status.mountStatusbar(statusbarEl); } catch (e) { console.error('statusbar', e); }
  }
  try { mods.menubar?.bindMenubar?.(document); } catch (e) { console.error('menubar bind', e); }
  try { mods.toolbar?.bindToolbar?.(document); } catch (e) { console.error('toolbar bind', e); }
  try { mods.topbar?.bindTopbar?.(document); } catch (e) { console.error('topbar bind', e); }
  try { mods.short?.initShortcuts?.(); } catch (e) { console.error('shortcuts', e); }
  try { mods.router?.initRouter?.(); } catch (e) { console.error('router', e); }
  try { mods.refresh?.startAutoRefresh?.(); } catch (e) { console.error('autorefresh', e); }
  console.info('[SQM v864.3] boot 완료');
  console.info('  로드된 모듈:', Object.keys(mods).filter(k => mods[k]).join(', '));
  console.info('  실패한 모듈:', Object.keys(mods).filter(k => !mods[k]).join(', ') || '없음');
  // 콘솔에서 즉시 확인 가능하도록 전역 노출
  window.SQM = window.SQM || {};
  window.SQM.modules = mods;
  window.SQM.bootComplete = true;
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
