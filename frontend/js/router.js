// SQM v8.6.6
// 9개 사이드바 탭 전환 로직. 이전 페이지 unmount → 다음 mount

const PAGE_LOADERS = {
  dashboard:  () => import('./pages/dashboard.js'),
  inventory:  () => import('./pages/inventory.js'),
  allocation: () => import('./pages/allocation.js'),
  outbound:   () => import('./pages/outbound.js'),
  picked:     () => import('./pages/picked.js'),
  return:     () => import('./pages/return.js'),
  move:       () => import('./pages/move.js').catch(() => stubModule('move')),
  log:        () => import('./pages/log.js'),
  scan:       () => import('./pages/scan.js'),
  tonbag:     () => import('./pages/tonbag.js'),
};

function stubModule(name) {
  return {
    mount(container) {
      container.innerHTML = `
        <section class="page" data-page="${name}">
          <h2>${name}</h2>
          <div class="empty">준비 중 (Tier 3 이관 예정)</div>
        </section>`;
    },
    unmount() {},
  };
}

let currentPage = null;

export async function navigateTo(pageId, container) {
  const target = container || document.getElementById('page-container');
  if (!target) {
    console.error('[router] page-container not found');
    return;
  }
  try {
    if (currentPage?.unmount) currentPage.unmount();
    const loader = PAGE_LOADERS[pageId] || (() => Promise.resolve(stubModule(pageId)));
    const mod = await loader();
    await (mod.mount || (() => {}))(target);
    currentPage = mod;

    // 사이드바 active 표시
    document.querySelectorAll('[data-route]').forEach(el => {
      el.classList.toggle('active', el.dataset.route === pageId);
    });
    // URL hash 동기화
    if (location.hash.slice(1) !== pageId) location.hash = pageId;
    // localStorage 에 마지막 탭 저장
    try { localStorage.setItem('sqm_last_tab', pageId); } catch {}
  } catch (e) {
    console.error('[router] navigate failed', e);
    target.innerHTML = `<div class="empty">페이지 로드 실패: ${e.message}</div>`;
  }
}

export function initRouter() {
  document.querySelectorAll('[data-route]').forEach(el => {
    el.addEventListener('click', (ev) => {
      ev.preventDefault();
      navigateTo(el.dataset.route);
    });
  });
  window.addEventListener('hashchange', () => {
    const id = location.hash.slice(1);
    if (id && PAGE_LOADERS[id]) navigateTo(id);
  });
  // 초기 진입
  const initial = location.hash.slice(1)
    || localStorage.getItem('sqm_last_tab')
    || 'dashboard';
  navigateTo(initial);
}
