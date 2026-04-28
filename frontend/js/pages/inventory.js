/* ── Inventory Page Module ── */
'use strict';

const InventoryPage = (() => {
  let allData = [];
  let filtered = [];
  let currentStatus = 'ALL';
  let currentProduct = '';
  let searchQuery = '';
  let sortCol = 'lot';
  let sortAsc = true;
  let page = 1;
  const PAGE_SIZE = 50;

  async function load() {
    try {
      const res = await fetch('http://localhost:8765/api/inventory');
      allData = res.ok ? await res.json() : SAMPLE_INVENTORY;
    } catch { allData = window.SAMPLE_INVENTORY || []; }
    applyFilters();
  }

  function applyFilters() {
    filtered = allData.filter(row => {
      if (currentStatus !== 'ALL' && row.status !== currentStatus) return false;
      if (currentProduct && row.product !== currentProduct) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!row.lot.toLowerCase().includes(q) &&
            !row.sap.toLowerCase().includes(q) &&
            !row.bl.toLowerCase().includes(q)) return false;
      }
      return true;
    });
    filtered.sort((a, b) => {
      let va = a[sortCol], vb = b[sortCol];
      if (typeof va === 'number') return sortAsc ? va - vb : vb - va;
      return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
    });
    page = 1;
    render();
  }

  function render() {
    const tbody = document.getElementById('inventory-tbody');
    if (!tbody) return;
    const start = (page - 1) * PAGE_SIZE;
    const slice = filtered.slice(start, start + PAGE_SIZE);
    tbody.innerHTML = slice.map(row => `
      <tr onclick="InventoryPage.showDetail('${row.lot}')">
        <td onclick="event.stopPropagation()"><input type="checkbox"></td>
        <td class="mono-cell" style="color:var(--accent);font-weight:500;">${row.lot}</td>
        <td class="mono-cell">${row.sap}</td>
        <td class="mono-cell">${row.bl}</td>
        <td class="mono-cell">${row.container}</td>
        <td><span class="tag">${row.product}</span></td>
        <td>${window.STATUS_BADGE?.[row.status] || row.status}</td>
        <td class="mono-cell">${row.net.toLocaleString()}</td>
        <td class="mono-cell" style="color:${row.balance > 0 ? 'var(--status-available)' : 'var(--text-muted)'};">
          ${row.balance.toLocaleString()}
        </td>
        <td class="mono-cell">${row.bags}</td>
        <td class="mono-cell">${row.date}</td>
        <td><span class="tag">${row.location}</span></td>
        <td onclick="event.stopPropagation()">
          <button class="btn btn-ghost btn-xs" onclick="InventoryPage.showDetail('${row.lot}')">상세</button>
        </td>
      </tr>
    `).join('');

    const footer = document.querySelector('#page-inventory .card-footer span');
    if (footer) footer.textContent = `${filtered.length}건 중 ${start+1}-${Math.min(start+PAGE_SIZE, filtered.length)} 표시`;
  }

  function showDetail(lotNo) {
    window.showToast?.('info', `LOT 상세: ${lotNo}`);
    // TODO: T6에서 LOT 상세 모달 구현
  }

  function setStatus(status) {
    currentStatus = status;
    applyFilters();
  }
  function setProduct(product) {
    currentProduct = product;
    applyFilters();
  }
  function setSearch(q) {
    searchQuery = q;
    applyFilters();
  }

  return { load, setStatus, setProduct, setSearch, showDetail, render };
})();
