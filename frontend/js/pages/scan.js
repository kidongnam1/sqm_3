/* ── Scan Page Module ── */
'use strict';

const ScanPage = (() => {
  let history = [];
  let lastBarcode = '';

  function init() {
    const inp = document.getElementById('scan-input');
    if (!inp) return;
    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); processBarcode(inp.value.trim()); inp.value = ''; }
    });
    inp.focus();
  }

  async function processBarcode(barcode, action) {
    if (!barcode) return;
    lastBarcode = barcode;
    if (!action) { window.showToast?.('info', `스캔: ${barcode} — 처리 유형을 선택하세요`); return; }
    try {
      const res = await fetch('http://localhost:8765/api/scan/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ barcode, action }),
      });
      const data = await res.json();
      const ok = data.success;
      window.showToast?.(ok ? 'success' : 'error', data.message || (ok ? '처리 완료' : '처리 실패'));
      addHistory(barcode, action, ok);
    } catch {
      window.showToast?.('error', '서버 연결 오류');
      addHistory(barcode, action, false);
    }
  }

  function addHistory(barcode, action, success) {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
    history.unshift({ time, barcode, action, success });
    if (history.length > 100) history.pop();
    renderHistory();
  }

  function renderHistory() {
    const tbody = document.getElementById('scan-history-tbody');
    if (!tbody) return;
    tbody.innerHTML = history.slice(0, 20).map(h => `
      <tr>
        <td class="mono-cell">${h.time}</td>
        <td class="mono-cell">${h.barcode}</td>
        <td>${h.action}</td>
        <td>${h.success
          ? '<span class="badge badge-available">성공</span>'
          : '<span class="badge badge-return">실패</span>'}</td>
      </tr>
    `).join('') || '<tr><td colspan="4" style="text-align:center;padding:20px;color:var(--text-muted)">스캔 이력 없음</td></tr>';
  }

  function quickAction(action) {
    const inp = document.getElementById('scan-input');
    const barcode = inp?.value.trim() || lastBarcode;
    if (!barcode) { window.showToast?.('warning', '바코드를 먼저 스캔하세요'); return; }
    processBarcode(barcode, action);
    if (inp) inp.value = '';
  }

  return { init, processBarcode, quickAction, renderHistory };
})();
