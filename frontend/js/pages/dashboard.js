// SQM v864.3 — Dashboard (v864.2 Golden Reference 스타일로 전면 복구)
// 테이블 2개: [좌] 재고 및 확인 (판매가능/판매배정/판매화물/출고완료/반품대기/합계/샘플)
//             [우] LOT별 (기초재고/입고/출고/기말재고/검증)
import { apiGet } from '../api-client.js';

const SAMPLE = {
  products: [
    { name: 'LITHIUM CARBONATE', sellable: 200.0, reserved: 0, committed: 0,
      outbound_done: 0, return_wait: 0, total: 200.0, sample: 40 },
  ],
  lots: [
    { opening: 200.0, inbound: 0, outbound: 0, ending: 200.0, status: 'OK' },
  ],
};

export async function mount(container) {
  container.innerHTML = `
    <div class="dashboard-split">
      <div class="panel-half">
        <table class="data-table">
          <thead><tr>
            <th style="width:40px">순번</th>
            <th style="text-align:left;min-width:180px">Product</th>
            <th>판매가능</th><th>판매배정</th><th>판매화물</th>
            <th>출고완료</th><th>반품대기</th><th>합계</th><th>샘플</th>
          </tr></thead>
          <tbody id="dash-products"></tbody>
        </table>
      </div>
      <div class="panel-half">
        <table class="data-table">
          <thead><tr>
            <th style="width:40px">순번</th>
            <th>기초재고</th><th>입고</th><th>출고</th><th>기말재고</th><th>검증</th>
          </tr></thead>
          <tbody id="dash-lots"></tbody>
        </table>
      </div>
    </div>
  `;
  await loadAll();
}

async function loadAll() {
  let data = SAMPLE;
  try {
    const res = await apiGet('/api/dashboard/stats');
    if (res && (res.data || res.products)) data = res.data || res;
  } catch { /* 폴백 유지 */ }
  renderProducts(data.products || SAMPLE.products);
  renderLots(data.lots || SAMPLE.lots);
}

function num(v) {
  if (typeof v !== 'number') return v ?? '-';
  return v.toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function renderProducts(rows) {
  const tbody = document.getElementById('dash-products');
  if (!tbody) return;
  const total = rows.reduce((a, r) => ({
    sellable: a.sellable + (r.sellable || 0),
    reserved: a.reserved + (r.reserved || 0),
    committed: a.committed + (r.committed || 0),
    outbound_done: a.outbound_done + (r.outbound_done || 0),
    return_wait: a.return_wait + (r.return_wait || 0),
    total: a.total + (r.total || 0),
    sample: a.sample + (r.sample || 0),
  }), { sellable:0, reserved:0, committed:0, outbound_done:0, return_wait:0, total:0, sample:0 });
  tbody.innerHTML = rows.map((r, i) => `
    <tr>
      <td>${i+1}</td>
      <td style="text-align:left">${r.name}</td>
      <td>${num(r.sellable)}</td>
      <td>${num(r.reserved)}</td>
      <td>${num(r.committed)}</td>
      <td>${num(r.outbound_done)}</td>
      <td>${num(r.return_wait)}</td>
      <td><b>${num(r.total)}</b></td>
      <td>${r.sample ?? '-'}</td>
    </tr>
  `).join('') + `
    <tr class="total-row">
      <td></td><td style="text-align:left"><b>합계</b></td>
      <td>${num(total.sellable)}</td>
      <td>${num(total.reserved)}</td>
      <td>${num(total.committed)}</td>
      <td>${num(total.outbound_done)}</td>
      <td>${num(total.return_wait)}</td>
      <td>${num(total.total)}</td>
      <td>${total.sample}</td>
    </tr>
  `;
}

function renderLots(rows) {
  const tbody = document.getElementById('dash-lots');
  if (!tbody) return;
  tbody.innerHTML = rows.map((r, i) => `
    <tr>
      <td>${i+1}</td>
      <td>${num(r.opening)}</td>
      <td>${num(r.inbound)}</td>
      <td>${num(r.outbound)}</td>
      <td>${num(r.ending)}</td>
      <td><span class="badge-ok" style="color:#2e7d32;font-weight:700">${r.status || 'OK'}</span></td>
    </tr>
  `).join('');
}

export function unmount() {}
