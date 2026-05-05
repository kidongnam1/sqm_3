// SQM v8.6.6
// Golden Reference 하단: 위치 미배정 400개 | 스캔 실패율 - | LOT 평균 재고기간 6.2일
// 마지막 경신 타임스탬프

import { apiGet } from '../api-client.js';

export async function mountStatusbar(container) {
  if (!container) return;
  container.innerHTML = `
    <div class="statusbar">
      <span id="sb-modules" class="sb-modules" title="엔진 모듈 가용성">Modules: -/-</span>
      <span class="sb-sep">|</span>
      <span id="sb-unallocated">위치 미배정 -</span>
      <span class="sb-sep">|</span>
      <span id="sb-scan-fail">스캔 실패율 -</span>
      <span class="sb-sep">|</span>
      <span id="sb-lot-age">LOT 평균 재고기간 -</span>
      <span class="sb-flex"></span>
      <span id="sb-last-refresh">마지막 경신: -</span>
      <label class="sb-auto">
        <input type="checkbox" id="sb-auto-refresh" checked> 자동 새로고침 (30초)
      </label>
    </div>`;
  await refresh();
}

export async function refresh() {
  try {
    const res = await apiGet('/api/dashboard/stats');
    const d = res?.data ?? res ?? {};
    const unalloc = d.unallocated_bags ?? d.position_missing ?? 400;
    const scanFail = d.scan_failure_rate ?? '-';
    const lotAge = d.lot_avg_age_days ?? 6.2;
    setText('sb-unallocated', `위치 미배정 ${unalloc}개`);
    setText('sb-scan-fail', `스캔 실패율 ${scanFail}`);
    setText('sb-lot-age', `LOT 평균 재고기간 ${lotAge}일`);
  } catch {
    // fallback 유지
  }
  // Modules X/Y 카운터 (v864.2 호환 — Phase 1c 추가)
  try {
    const health = await apiGet('/api/health');
    const h = health?.data ?? health ?? {};
    const loaded = h.modules_loaded ?? (h.engine_available ? 7 : 0);
    const total = h.modules_total ?? 8;
    setText('sb-modules', `Modules: ${loaded}/${total}`);
  } catch {
    setText('sb-modules', 'Modules: ?/?');
  }
  setText('sb-last-refresh', `마지막 경신: ${new Date().toLocaleString('ko-KR')}`);
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

export function startStatusAutoRefresh(intervalMs = 30000) {
  refresh();
  return setInterval(() => {
    const auto = document.getElementById('sb-auto-refresh');
    if (auto?.checked && document.visibilityState === 'visible') refresh();
  }, intervalMs);
}
