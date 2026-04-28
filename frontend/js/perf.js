// SQM v864.3 — Performance Hygiene (Tier 3 S2)
// 이벤트 리스너 WeakMap 관리 + 페이지 언마운트 시 자동 cleanup
// 메모리 누수 방지

const _listenerRegistry = new WeakMap();

export function on(element, event, handler, options) {
  if (!element) return;
  element.addEventListener(event, handler, options);
  const list = _listenerRegistry.get(element) || [];
  list.push({ event, handler, options });
  _listenerRegistry.set(element, list);
}

export function offAll(element) {
  const list = _listenerRegistry.get(element);
  if (!list) return;
  list.forEach(({ event, handler, options }) => {
    element.removeEventListener(event, handler, options);
  });
  _listenerRegistry.delete(element);
}

// 타이머 레지스트리 — 페이지 교체 시 자동 cleanup
const _timers = new Set();

export function setInt(fn, ms) {
  const id = setInterval(fn, ms);
  _timers.add(id);
  return id;
}

export function clearAllTimers() {
  _timers.forEach(id => clearInterval(id));
  _timers.clear();
}

// 간단한 성능 측정
export function measure(label, fn) {
  const t0 = performance.now();
  try { return fn(); }
  finally {
    const t = performance.now() - t0;
    if (t > 100) console.warn(`[perf] ${label}: ${t.toFixed(1)}ms`);
  }
}

export async function measureAsync(label, fn) {
  const t0 = performance.now();
  try { return await fn(); }
  finally {
    const t = performance.now() - t0;
    if (t > 200) console.warn(`[perf] ${label} (async): ${t.toFixed(1)}ms`);
  }
}
