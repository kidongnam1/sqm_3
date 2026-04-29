// SQM v864.3 — Picked Page (Tier 2 Stage 3)
// v864.2 기준: 출고 예정 중 "Picked" 상태만 필터
import { apiGet } from '../api-client.js';
import { showToast } from '../toast.js';

export async function mount(container) {
  container.innerHTML = `
    <section class="page" data-page="picked">
      <h2>🚛 Picked — 출고 대기</h2>
      <div class="toolbar-mini">
        <button class="btn btn-secondary" data-action="refresh-picked">🔄 새로고침</button>
      </div>
      <div class="loading" id="picked-loading">로딩 중…</div>
      <table class="data-table" id="picked-table" style="display:none">
        <thead><tr><th>LOT</th><th>Product</th><th>수량</th><th>출고일</th><th>위치</th></tr></thead>
        <tbody id="picked-tbody"></tbody>
      </table>
      <div class="empty" id="picked-empty" style="display:none">표시할 데이터가 없습니다</div>
    </section>`;
  await load();
  container.querySelector('[data-action="refresh-picked"]')?.addEventListener('click', load);
}

async function load() {
  const loading = document.getElementById('picked-loading');
  const table = document.getElementById('picked-table');
  const empty = document.getElementById('picked-empty');
  const tbody = document.getElementById('picked-tbody');
  try {
    loading.style.display = 'block';
    table.style.display = 'none';
    empty.style.display = 'none';
    const res = await apiGet('/api/outbound/scheduled?status=picked');
    const rows = (res?.data ?? res?.rows ?? []) || [];
    if (rows.length === 0) {
      empty.style.display = 'block';
      return;
    }
    tbody.innerHTML = rows.map(r => `
      <tr><td>${r.lot ?? ''}</td><td>${r.product ?? ''}</td>
      <td>${r.qty ?? r.bags ?? ''}</td><td>${r.date ?? ''}</td><td>${r.location ?? ''}</td></tr>
    `).join('');
    table.style.display = '';
  } catch (e) {
    empty.textContent = `불러오기 실패: ${e.message}`;
    empty.style.display = 'block';
    showToast?.('error', 'Picked 데이터 로드 실패');
  } finally {
    loading.style.display = 'none';
  }
}

export function unmount() { /* no-op */ }
