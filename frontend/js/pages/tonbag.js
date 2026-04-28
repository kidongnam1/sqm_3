/* ── Tonbag & Move Page Module ── */
'use strict';

const TonbagPage = (() => {
  let data = [];
  let filters = { lot: '', sap: '', bl: '', container: '', product: '', status: '' };

  async function load() {
    try {
      const params = new URLSearchParams();
      if (filters.lot) params.set('lot_no', filters.lot);
      if (filters.status) params.set('status', filters.status);
      const res = await fetch(`http://localhost:8765/api/tonbags?${params}`);
      data = res.ok ? await res.json() : [];
    } catch { data = []; }
    render();
  }

  function render() {
    const tbody = document.getElementById('tonbag-tbody');
    if (!tbody) return;
    const filtered = data.filter(r => {
      return (!filters.product || r.product === filters.product) &&
             (!filters.container || r.container?.includes(filters.container));
    });
    tbody.innerHTML = filtered.length ? filtered.map(r => `
      <tr>
        <td class="mono-cell">${r.sub_lt || r.tonbag_id || '-'}</td>
        <td class="mono-cell" style="color:var(--accent)">${r.lot_no || '-'}</td>
        <td><span class="tag">${r.product || '-'}</span></td>
        <td>${window.STATUS_BADGE?.[r.status] || r.status || '-'}</td>
        <td class="mono-cell">${(r.weight || 0).toLocaleString()}</td>
        <td class="mono-cell">${r.location || '-'}</td>
        <td class="mono-cell">${r.container || '-'}</td>
        <td><button class="btn btn-ghost btn-xs">상세</button></td>
      </tr>
    `).join('') : `<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--text-muted)">데이터 없음</td></tr>`;
  }

  function setFilter(key, value) { filters[key] = value; render(); }

  return { load, render, setFilter };
})();

const MovePage = (() => {
  let moveHistory = [];

  async function executeMove(barcode, destination) {
    if (!barcode || !destination) {
      window.showToast?.('warning', '바코드와 목적지를 입력하세요'); return;
    }
    try {
      const res = await fetch('http://localhost:8765/api/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ barcode, destination }),
      });
      const data = await res.json();
      window.showToast?.(data.success ? 'success' : 'error', data.message || '이동 처리');
      if (data.success) await loadHistory();
    } catch { window.showToast?.('error', '서버 연결 오류'); }
  }

  async function loadHistory() {
    try {
      const res = await fetch('http://localhost:8765/api/move/history');
      moveHistory = res.ok ? await res.json() : [];
      renderHistory();
    } catch {}
  }

  function renderHistory() {
    const tbody = document.getElementById('move-history-tbody');
    if (!tbody) return;
    tbody.innerHTML = moveHistory.slice(0, 50).map(h => `
      <tr>
        <td class="mono-cell">${h.moved_at || '-'}</td>
        <td class="mono-cell">${h.sub_lt || '-'}</td>
        <td class="mono-cell">${h.from_location || '-'}</td>
        <td class="mono-cell" style="color:var(--accent)">${h.to_location || '-'}</td>
        <td>${h.moved_by || 'system'}</td>
      </tr>
    `).join('') || `<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-muted)">이동 이력 없음</td></tr>`;
  }

  return { executeMove, loadHistory, renderHistory };
})();
