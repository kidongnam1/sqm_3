/* ── Allocation Page Module ── */
'use strict';

const AllocationPage = (() => {
  let data = [];
  let selected = new Set();

  async function load() {
    try {
      const res = await fetch('http://localhost:8765/api/allocation');
      if (res.ok) { const j = await res.json(); data = j.data || []; }
    } catch { data = []; }
    render();
  }

  function render() {
    const tbody = document.getElementById('allocation-tbody');
    if (!tbody) return;
    tbody.innerHTML = data.length ? data.map(row => `
      <tr>
        <td><input type="checkbox" onchange="AllocationPage.toggle('${row.lot}', this.checked)"></td>
        <td class="mono-cell" style="color:var(--accent)">${row.lot}</td>
        <td><span class="tag">${row.product}</span></td>
        <td>${row.customer || '-'}</td>
        <td class="mono-cell">${row.sale_ref || '-'}</td>
        <td class="mono-cell" style="color:var(--accent)">${(row.balance||0).toLocaleString()}</td>
        <td class="mono-cell">${row.bags || '-'}</td>
        <td class="mono-cell">${row.ship_date || '-'}</td>
        <td>${window.STATUS_BADGE?.['RESERVED'] || 'RESERVED'}</td>
        <td><button class="btn btn-ghost btn-xs" onclick="AllocationPage.cancel('${row.lot}')">취소</button></td>
      </tr>
    `).join('') : `<tr><td colspan="10" style="text-align:center;padding:40px;color:var(--text-muted)">배정 데이터 없음</td></tr>`;
  }

  function toggle(lot, checked) {
    checked ? selected.add(lot) : selected.delete(lot);
  }

  async function cancel(lot) {
    if (!confirm(`${lot} 배정을 취소하시겠습니까?`)) return;
    try {
      const res = await fetch(`http://localhost:8765/api/allocation/${lot}/cancel`, { method: 'POST' });
      if (res.ok) { window.showToast?.('success', `${lot} 배정 취소 완료`); await load(); }
      else window.showToast?.('error', '배정 취소 실패');
    } catch { window.showToast?.('error', '서버 연결 오류'); }
  }

  async function cancelBulk() {
    if (!selected.size) { window.showToast?.('warning', '선택된 항목 없음'); return; }
    for (const lot of selected) await cancel(lot);
    selected.clear();
  }

  return { load, render, toggle, cancel, cancelBulk };
})();
