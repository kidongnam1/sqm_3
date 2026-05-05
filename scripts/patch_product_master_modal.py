#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
showProductMasterModal 전면 교체:
 - 약칭(code), Full Name, 한글명, 톤백지원, 기본제품, 활성 컬럼/폼 추가
 - 기본 제품 삭제 차단 (API + JS 이중 보호)
 - 기본 제품 동기화(sync-defaults) 버튼 추가
 - 비활성화 버튼 추가
"""
import sys

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"Size: {len(content):,}", flush=True)

# ── 교체 대상: showProductMasterModal 함수 전체 ──────────────────────────────
START = "  function showProductMasterModal() {"
END   = "  window.showProductMasterModal = showProductMasterModal;"

s_idx = content.find(START)
e_idx = content.find(END, s_idx)
if s_idx < 0 or e_idx < 0:
    print("FAIL: showProductMasterModal 범위를 찾지 못함", flush=True)
    sys.exit(1)

# END 줄 포함해서 교체
end_line_end = content.find('\n', e_idx) + 1
OLD_BLOCK = content[s_idx:end_line_end]
print(f"OLD_BLOCK: {len(OLD_BLOCK)} chars", flush=True)

NEW_BLOCK = r"""  function showProductMasterModal() {
    var selectedId  = null;
    var cacheItems  = [];

    /* ── 폼 비우기 ── */
    function clearPmForm() {
      selectedId = null;
      ['pm-code','pm-name','pm-full','pm-korean','pm-sap','pm-spec','pm-unit','pm-remarks'].forEach(function(id){
        var el = document.getElementById(id); if (el) el.value = '';
      });
      var tb = document.getElementById('pm-tonbag'); if (tb) tb.checked = false;
      var ac = document.getElementById('pm-active'); if (ac) ac.checked = true;
      var saveBtn = document.getElementById('pm-save');
      if (saveBtn) saveBtn.textContent = '➕ 추가';
    }

    /* ── 핸들러 바인딩 ── */
    function bindPmHandlers() {
      /* 기본 제품 동기화 */
      var defBtn = document.getElementById('pm-sync-defaults');
      if (defBtn) defBtn.addEventListener('click', function(){
        apiPost('/api/product-master/sync-defaults', {}).then(function(res){
          showToast('success', res.message || '기본 제품 동기화 완료');
          loadPm();
        }).catch(function(e){ showToast('error', String(e.message||e)); });
      });
      /* 재고 동기화 */
      var invBtn = document.getElementById('pm-sync-inv');
      if (invBtn) invBtn.addEventListener('click', function(){
        apiPost('/api/product-master/sync-from-inventory', {}).then(function(res){
          showToast('success', res.message || '동기화 완료');
          loadPm();
        }).catch(function(e){ showToast('error', String(e.message||e)); });
      });
      /* 폼 비우기 */
      var newBtn = document.getElementById('pm-new');
      if (newBtn) newBtn.addEventListener('click', clearPmForm);
      /* 저장 (추가/수정) */
      var saveBtn = document.getElementById('pm-save');
      if (saveBtn) saveBtn.addEventListener('click', function(){
        var body = {
          code:           (document.getElementById('pm-code')||{}).value || '',
          product_name:   (document.getElementById('pm-name')||{}).value || '',
          full_name:      (document.getElementById('pm-full')||{}).value || '',
          korean_name:    (document.getElementById('pm-korean')||{}).value || '',
          sap_no:         (document.getElementById('pm-sap')||{}).value || '',
          spec:           (document.getElementById('pm-spec')||{}).value || '',
          unit:           (document.getElementById('pm-unit')||{}).value || '',
          remarks:        (document.getElementById('pm-remarks')||{}).value || '',
          tonbag_support: (document.getElementById('pm-tonbag')||{}).checked ? 1 : 0,
          is_active:      (document.getElementById('pm-active')||{}).checked ? 1 : 0,
          sort_order:     0
        };
        var displayName = body.code || body.product_name || body.full_name;
        if (!displayName) { showToast('warning','약칭(code) 또는 제품명을 입력하세요'); return; }
        var req = selectedId
          ? apiCall('PUT', '/api/product-master/' + selectedId, body)
          : apiPost('/api/product-master/create', body);
        req.then(function(res){
          if (res && res.ok === false) { showToast('error', res.error || '실패'); return; }
          showToast('success', res.message || '저장됨');
          clearPmForm();
          loadPm();
        }).catch(function(e){ showToast('error', String(e.message||e)); });
      });
      /* 수정 버튼 */
      document.querySelectorAll('.pm-edit').forEach(function(btn){
        btn.addEventListener('click', function(){
          var id = parseInt(btn.getAttribute('data-id'), 10);
          var r = cacheItems.filter(function(x){ return Number(x.id) === id; })[0];
          if (!r) return;
          selectedId = id;
          var set = function(eid, val){ var el=document.getElementById(eid); if(el) el.value=val||''; };
          set('pm-code',   r.code);
          set('pm-name',   r.product_name);
          set('pm-full',   r.full_name);
          set('pm-korean', r.korean_name);
          set('pm-sap',    r.sap_no);
          set('pm-spec',   r.spec);
          set('pm-unit',   r.unit);
          set('pm-remarks',r.remarks);
          var tb = document.getElementById('pm-tonbag'); if(tb) tb.checked = !!r.tonbag_support;
          var ac = document.getElementById('pm-active'); if(ac) ac.checked = (r.is_active !== 0);
          var saveBtn = document.getElementById('pm-save');
          if (saveBtn) saveBtn.textContent = '✏️ 수정 저장';
          document.getElementById('pm-code').focus();
        });
      });
      /* 삭제 버튼 */
      document.querySelectorAll('.pm-del').forEach(function(btn){
        btn.addEventListener('click', function(){
          var id  = parseInt(btn.getAttribute('data-id'), 10);
          var def = btn.getAttribute('data-default') === '1';
          if (def) { showToast('warning','기본 제품은 삭제할 수 없습니다. 비활성화를 사용하세요.'); return; }
          if (!confirm('이 제품을 삭제하겠습니까?')) return;
          apiCall('DELETE', '/api/product-master/' + id, null).then(function(res){
            if (res && res.ok === false) { showToast('error', res.error || '실패'); return; }
            showToast('success', '삭제됨');
            clearPmForm();
            loadPm();
          }).catch(function(e){ showToast('error', String(e.message||e)); });
        });
      });
      /* 비활성화 버튼 */
      document.querySelectorAll('.pm-deact').forEach(function(btn){
        btn.addEventListener('click', function(){
          var id = parseInt(btn.getAttribute('data-id'), 10);
          if (!confirm('이 제품을 비활성화하겠습니까?')) return;
          apiPost('/api/product-master/deactivate/' + id, {}).then(function(res){
            if (res && res.ok === false) { showToast('error', res.error || '실패'); return; }
            showToast('success', '비활성화 완료');
            loadPm();
          }).catch(function(e){ showToast('error', String(e.message||e)); });
        });
      });
    }

    /* ── 테이블 렌더 ── */
    function renderPm(data) {
      var items = (data && data.items) ? data.items : [];
      cacheItems = items.slice();
      var inpStyle = 'width:100%;padding:6px 8px;margin-top:4px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;font-size:12px;box-sizing:border-box';
      var rows = items.map(function(r){
        var isDef  = r.is_default ? 1 : 0;
        var defTag = isDef ? '<span style="font-size:10px;color:#f59e0b;font-weight:700">★기본</span>' : '';
        var actTag = r.is_active !== 0
          ? '<span style="font-size:10px;color:#22c55e">●활성</span>'
          : '<span style="font-size:10px;color:#888">○비활성</span>';
        var delBtn = isDef
          ? '<button type="button" class="btn btn-ghost pm-del" style="padding:3px 6px;font-size:11px;color:var(--text-muted);cursor:not-allowed" data-id="'+r.id+'" data-default="1" title="기본 제품 삭제 불가">🚫</button>'
          : '<button type="button" class="btn btn-ghost pm-del" style="padding:3px 6px;font-size:11px;color:#ef4444" data-id="'+r.id+'" data-default="0" title="삭제">🗑</button>';
        return '<tr style="' + (r.is_active===0?'opacity:0.45':'') + '">'
          + '<td style="text-align:center;font-weight:700;color:var(--accent)">' + escapeHtml(r.code||'') + '</td>'
          + '<td>' + escapeHtml(r.full_name||r.product_name||'') + '</td>'
          + '<td>' + escapeHtml(r.korean_name||'') + '</td>'
          + '<td class="mono-cell">' + escapeHtml(r.sap_no||'') + '</td>'
          + '<td style="text-align:center">' + (r.tonbag_support?'✅':'—') + '</td>'
          + '<td style="text-align:center">' + defTag + '</td>'
          + '<td style="text-align:center">' + actTag + '</td>'
          + '<td style="text-align:center;white-space:nowrap">'
          +   '<button type="button" class="btn btn-ghost pm-edit" style="padding:3px 6px;font-size:11px" data-id="'+r.id+'" title="수정">✏️</button> '
          +   delBtn + ' '
          +   '<button type="button" class="btn btn-ghost pm-deact" style="padding:3px 6px;font-size:11px;color:#888" data-id="'+r.id+'" title="비활성화">⬜</button>'
          + '</td></tr>';
      }).join('');

      var tbody = rows || '<tr><td colspan="8" style="text-align:center;color:var(--text-muted);padding:20px">등록 없음 — 기본 제품 동기화 또는 직접 추가</td></tr>';
      var html = [
        '<div style="max-width:900px">',
        '  <h2 style="margin:0 0 8px 0">📦 제품 마스터 관리</h2>',
        '  <p style="color:var(--text-muted);font-size:12px;margin-bottom:12px">표준 품목 코드·영문명·한글명·SAP·규격·톤백 지원 여부를 관리합니다. ★기본 제품은 삭제 불가.</p>',
        /* ── 버튼 바 ── */
        '  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">',
        '    <button type="button" class="btn btn-primary btn-sm" id="pm-sync-defaults">⭐ 기본 제품 동기화 (8종)</button>',
        '    <button type="button" class="btn btn-ghost btn-sm" id="pm-sync-inv">📥 재고 제품 가져오기</button>',
        '  </div>',
        /* ── 입력 폼 ── */
        '  <div style="background:var(--panel);border:1px solid var(--panel-border);border-radius:8px;padding:12px;margin-bottom:14px">',
        '    <div style="font-weight:700;font-size:13px;margin-bottom:10px;color:var(--accent)">✏️ 제품 추가 / 수정</div>',
        '    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">',
        '      <label style="font-size:12px">약칭(code) *<input id="pm-code" type="text" maxlength="16" placeholder="예: NSH" style="'+inpStyle+'"/></label>',
        '      <label style="font-size:12px">Full Name<input id="pm-full" type="text" placeholder="Nickel Sulfate Hexahydrate" style="'+inpStyle+'"/></label>',
        '      <label style="font-size:12px">한글명<input id="pm-korean" type="text" placeholder="황산니켈" style="'+inpStyle+'"/></label>',
        '      <label style="font-size:12px">제품명(product_name)<input id="pm-name" type="text" placeholder="product_name" style="'+inpStyle+'"/></label>',
        '      <label style="font-size:12px">SAP No<input id="pm-sap" type="text" style="'+inpStyle+'"/></label>',
        '      <label style="font-size:12px">규격<input id="pm-spec" type="text" style="'+inpStyle+'"/></label>',
        '      <label style="font-size:12px">단위<input id="pm-unit" type="text" style="'+inpStyle+'"/></label>',
        '      <label style="font-size:12px">비고<input id="pm-remarks" type="text" style="'+inpStyle+'"/></label>',
        '      <div style="display:flex;gap:16px;align-items:flex-end;padding-bottom:2px">',
        '        <label style="font-size:12px;display:flex;align-items:center;gap:4px;cursor:pointer">',
        '          <input id="pm-tonbag" type="checkbox"> 톤백지원',
        '        </label>',
        '        <label style="font-size:12px;display:flex;align-items:center;gap:4px;cursor:pointer">',
        '          <input id="pm-active" type="checkbox" checked> 활성',
        '        </label>',
        '      </div>',
        '    </div>',
        '    <div style="display:flex;gap:8px;margin-top:10px">',
        '      <button type="button" class="btn btn-primary" id="pm-save">➕ 추가</button>',
        '      <button type="button" class="btn btn-ghost" id="pm-new">🗑 폼 비우기</button>',
        '    </div>',
        '  </div>',
        /* ── 테이블 ── */
        '  <div style="overflow-x:auto;max-height:380px;border:1px solid var(--border);border-radius:8px">',
        '    <table class="data-table"><thead><tr>',
        '      <th style="text-align:center">약칭</th>',
        '      <th>Full Name</th>',
        '      <th>한글명</th>',
        '      <th>SAP</th>',
        '      <th style="text-align:center">톤백</th>',
        '      <th style="text-align:center">기본</th>',
        '      <th style="text-align:center">상태</th>',
        '      <th style="text-align:center">작업</th>',
        '    </tr></thead><tbody>',
        tbody,
        '    </tbody></table>',
        '  </div>',
        '  <div style="margin-top:14px;text-align:right">',
        '    <button type="button" class="btn btn-ghost" onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'">닫기</button>',
        '  </div>',
        '</div>'
      ].join('\n');
      document.getElementById('sqm-modal-content').innerHTML = html;
      bindPmHandlers();
    }

    function loadPm() {
      apiGet('/api/product-master/list').then(function(res){
        var d = res.data || res || {};
        renderPm(d);
      }).catch(function(e){
        document.getElementById('sqm-modal-content').innerHTML =
          '<h2>제품 마스터</h2><div class="empty">'+escapeHtml(e.message||String(e))+'</div>';
      });
    }

    showDataModal('', '<div style="padding:20px;text-align:center">⏳ Loading...</div>');
    loadPm();
  }
  window.showProductMasterModal = showProductMasterModal;
"""

content = content[:s_idx] + NEW_BLOCK + content[end_line_end:]
print("PATCH OK: showProductMasterModal replaced", flush=True)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print(f"Done. {len(content):,} bytes.", flush=True)
