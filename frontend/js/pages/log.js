// SQM v864.3 — Log Page (Tier 2 Stage 3)
import { apiGet } from '../api-client.js';
import { showToast } from '../toast.js';

export async function mount(container) {
  container.innerHTML = `
    <section class="page" data-page="log">
      <h2>📝 Log — 활동 로그</h2>
      <div class="toolbar-mini">
        <button class="btn btn-secondary" data-action="refresh-log">🔄 새로고침</button>
        <select id="log-limit" class="select">
          <option value="100">최근 100</option>
          <option value="500">최근 500</option>
          <option value="1000">최근 1000</option>
        </select>
      </div>
      <div class="loading" id="log-loading">로딩 중…</div>
      <table class="data-table" id="log-table" style="display:none">
        <thead><tr><th>시각</th><th>유형</th><th>LOT</th><th>메모</th></tr></thead>
        <tbody id="log-tbody"></tbody>
      </table>
      <div class="empty" id="log-empty" style="display:none">로그 없음</div>
    </section>`;
  await load();
  container.querySelector('[data-action="refresh-log"]')?.addEventListener('click', load);
  container.querySelector('#log-limit')?.addEventListener('change', load);
}

async function load() {
  const limit = document.getElementById('log-limit')?.value || 100;
  const loading = document.getElementById('log-loading');
  const table = document.getElementById('log-table');
  const empty = document.getElementById('log-empty');
  const tbody = document.getElementById('log-tbody');
  try {
    loading.style.display = 'block';
    const res = await apiGet(`/api/log/activity?limit=${limit}`);
    const rows = Array.isArray(res) ? res : (res?.data ?? []);
    if (rows.length === 0) {
      table.style.display = 'none';
      empty.style.display = 'block';
      return;
    }
    tbody.innerHTML = rows.map(r => `
      <tr><td>${r.time ?? ''}</td><td>${r.type ?? ''}</td>
      <td>${r.lot ?? ''}</td><td>${r.note ?? ''}</td></tr>
    `).join('');
    table.style.display = '';
    empty.style.display = 'none';
  } catch (e) {
    empty.textContent = `로그 로드 실패: ${e.message}`;
    empty.style.display = 'block';
    showToast?.('error', 'Log 로드 실패');
  } finally {
    loading.style.display = 'none';
  }
}

export function unmount() { /* no-op */ }
