// SQM v864.3 — State Persistence (Tier 2 Stage 4)
// localStorage → sessionStorage → 메모리 3단 폴백
const STORAGE_KEY = 'sqm_v864_3_state';
const memoryFallback = {};

function getStore() {
  try {
    if (typeof localStorage !== 'undefined') {
      // probe
      localStorage.setItem('__sqm_probe__', '1');
      localStorage.removeItem('__sqm_probe__');
      return localStorage;
    }
  } catch {}
  try {
    if (typeof sessionStorage !== 'undefined') return sessionStorage;
  } catch {}
  // In-memory fallback
  return {
    getItem: (k) => (k in memoryFallback ? memoryFallback[k] : null),
    setItem: (k, v) => { memoryFallback[k] = String(v); },
    removeItem: (k) => { delete memoryFallback[k]; },
  };
}

export function saveState(patch) {
  const store = getStore();
  let current = {};
  try { current = JSON.parse(store.getItem(STORAGE_KEY) || '{}'); } catch {}
  const next = { ...current, ...patch };
  try { store.setItem(STORAGE_KEY, JSON.stringify(next)); } catch (e) {
    console.warn('saveState failed', e);
  }
  return next;
}

export function loadState() {
  const store = getStore();
  try { return JSON.parse(store.getItem(STORAGE_KEY) || '{}'); }
  catch { return {}; }
}

export function applyState() {
  const s = loadState();
  if (s.theme) document.documentElement.setAttribute('data-theme', s.theme);
  if (s.viewMode) document.documentElement.setAttribute('data-view-mode', s.viewMode);
  if (s.lastTab && location.hash !== '#' + s.lastTab) {
    location.hash = s.lastTab;
  }
}

export function captureState() {
  return {
    theme: document.documentElement.getAttribute('data-theme') || 'dark',
    viewMode: document.documentElement.getAttribute('data-view-mode') || 'mt',
    lastTab: location.hash.slice(1) || 'dashboard',
    ts: Date.now(),
  };
}

export function initStatePersistence() {
  applyState();
  window.addEventListener('beforeunload', () => saveState(captureState()));
  // 1분마다 자동 저장 (비상 대비)
  setInterval(() => saveState(captureState()), 60000);
}
