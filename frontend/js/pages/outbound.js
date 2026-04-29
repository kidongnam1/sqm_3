/* ── Outbound Pages Module (출고예정 / 판매화물결정 / 출고완료) ── */
'use strict';

const OutboundPage = (() => {
  async function loadScheduled() {
    try {
      const res = await fetch('http://localhost:8765/api/outbound/scheduled');
      return res.ok ? await res.json() : [];
    } catch { return []; }
  }

  async function loadHistory(dateFrom, dateTo) {
    let url = 'http://localhost:8765/api/outbound/history';
    const params = new URLSearchParams();
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo)   params.set('date_to', dateTo);
    if ([...params].length) url += '?' + params.toString();
    try {
      const res = await fetch(url);
      return res.ok ? await res.json() : [];
    } catch { return []; }
  }

  function renderTable(tbodyId, rows, columns) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    tbody.innerHTML = rows.length ? rows.map(row =>
      '<tr>' + columns.map(col => {
        if (col === 'status') return `<td>${window.STATUS_BADGE?.[row[col]] || row[col]}</td>`;
        if (col === 'product') return `<td><span class="tag">${row[col]||'-'}</span></td>`;
        if (['net','balance','balance_kg'].includes(col))
          return `<td class="mono-cell" style="color:var(--accent)">${(row[col]||0).toLocaleString()}</td>`;
        return `<td class="mono-cell">${row[col]||'-'}</td>`;
      }).join('') + '</tr>'
    ).join('') : `<tr><td colspan="${columns.length}" style="text-align:center;padding:40px;color:var(--text-muted)">데이터 없음</td></tr>`;
  }

  async function confirmOutbound(lotNo) {
    if (!confirm(`${lotNo} 출고를 확정하시겠습니까?`)) return;
    try {
      const res = await fetch(`http://localhost:8765/api/outbound/${lotNo}/confirm`, { method: 'POST' });
      const data = await res.json();
      window.showToast?.(data.success ? 'success' : 'error', data.message || '처리 완료');
    } catch { window.showToast?.('error', '서버 연결 오류'); }
  }

  async function cancelOutbound(lotNo) {
    if (!confirm(`${lotNo} 출고를 취소하시겠습니까?`)) return;
    try {
      const res = await fetch(`http://localhost:8765/api/outbound/${lotNo}/cancel`, { method: 'POST' });
      const data = await res.json();
      window.showToast?.(data.success ? 'success' : 'error', data.message || '취소 완료');
    } catch { window.showToast?.('error', '서버 연결 오류'); }
  }

  return { loadScheduled, loadHistory, renderTable, confirmOutbound, cancelOutbound };
})();
