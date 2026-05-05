#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Log 페이지 전면 개선
- 탭 1: 활동 이력 (stock_movement) → /api/q/movement-history
- 탭 2: 감사 로그 (audit_log)      → /api/q/audit-log
- 필터: 건수 선택 + Refresh + 타입별 색상 뱃지
"""
import sys

SRC = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'

with open(SRC, 'r', encoding='utf-8') as f:
    c = f.read()
print(f"Size: {len(c):,}", flush=True)

OLD = """\
  function loadLogPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="log">',
      '<h2>Log - Activity Log</h2>',
      '<div class="toolbar-mini">',
      '<button class="btn btn-secondary" onclick="renderPage(\'log\')">Refresh</button>',
      '<select id="log-limit" class="select" style="margin-left:8px" onchange="renderPage(\'log\')">',
      '<option value="100">Last 100</option>',
      '<option value="500">Last 500</option>',
      '<option value="1000">Last 1000</option>',
      '</select></div>',
      '<div id="log-loading" style="padding:40px;text-align:center">Loading...</div>',
      '<table class="data-table" id="log-table" style="display:none">',
      '<thead><tr><th>Time</th><th>Type</th><th>LOT</th><th>Detail</th></tr></thead>',
      '<tbody id="log-tbody"></tbody></table>',
      '<div class="empty" id="log-empty" style="display:none">No logs</div>',
      '</section>'
    ].join('');
    var limit = 100;
    try { var el=document.getElementById('log-limit'); if(el) limit=parseInt(el.value)||100; } catch {}
    apiGet('/api/q/audit-log?limit='+limit).then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      document.getElementById('log-loading').style.display = 'none';
      if (!rows.length) { document.getElementById('log-empty').style.display='block'; return; }
      var tbody = document.getElementById('log-tbody');
      if (tbody) tbody.innerHTML = rows.map(function(r){
        return '<tr>' +
          '<td class="mono-cell">'+escapeHtml(r.created_at||r.time||r.timestamp||'')+'</td>' +
          '<td>'+escapeHtml(r.event_type||r.type||r.action||'')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.lot_no||r.lot||r.tonbag_id||'')+'</td>' +
          '<td>'+escapeHtml(r.event_data||r.user_note||r.note||r.memo||r.detail||'')+'</td></tr>';
      }).join('');
      document.getElementById('log-table').style.display = '';
    }).catch(function(e){
      if (_currentRoute !== route) return;
      document.getElementById('log-loading').style.display = 'none';
      var el=document.getElementById('log-empty');
      if (el) { el.textContent='Load failed: '+(e.message||String(e)); el.style.display='block'; }
    });
  }"""

NEW = """\
  /* 이동 타입별 뱃지 색상 */
  var _LOG_TYPE_COLOR = {
    'INBOUND':   '#4caf50', 'OUTBOUND': '#f44336', 'MOVE': '#2196f3',
    'RETURN':    '#ff9800', 'HOLD':     '#9c27b0', 'ADJUST': '#00bcd4',
    'ALLOCATED': '#ff9800', 'PICKED':   '#8bc34a', 'SOLD': '#e91e63',
    'SWAP': '#ff5722', 'FIX': '#795548',
  };
  function _logTypeBadge(t) {
    var col = _LOG_TYPE_COLOR[String(t).toUpperCase()] || '#607d8b';
    return '<span style="background:'+col+';color:#fff;border-radius:3px;padding:1px 7px;font-size:11px;white-space:nowrap">'+escapeHtml(String(t||''))+'</span>';
  }

  /* ── 활동 이력 탭 (stock_movement) ── */
  function _logLoadMovement(limit) {
    var tbody  = document.getElementById('log-mv-tbody');
    var cntEl  = document.getElementById('log-mv-count');
    var statsEl= document.getElementById('log-mv-stats');
    if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-muted)">⏳ 로딩 중...</td></tr>';
    apiGet('/api/q/movement-history?limit=' + (limit||300)).then(function(res) {
      var rows  = extractRows(res);
      var stats = (res && res.data && res.data.stats) || [];
      if (cntEl) cntEl.textContent = rows.length + '건';
      if (statsEl && stats.length) {
        statsEl.innerHTML = stats.map(function(s){
          return '<span style="margin-right:10px;font-size:12px">'+_logTypeBadge(s.movement_type)+
            ' <strong>'+s.cnt+'건</strong> / '+(s.total_mt||0)+' MT</span>';
        }).join('');
      }
      if (!tbody) return;
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--text-muted)">📭 활동 이력 없음</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function(r, i){
        var td = function(v){ return '<td style="text-align:center;white-space:nowrap">' + escapeHtml(String(v||'')) + '</td>'; };
        return '<tr>' +
          td(i+1) +
          '<td style="text-align:center">' + _logTypeBadge(r.movement_type||r.type||'') + '</td>' +
          td(r.lot_no||'') +
          '<td style="text-align:right;white-space:nowrap">' + (r.qty_kg ? Number(r.qty_kg).toLocaleString() + ' KG' : '') + '</td>' +
          td(r.customer||'') +
          td(r.actor||r.operator||'system') +
          td((r.movement_date||r.created_at||'').replace('T',' ').substring(0,16)) +
          td(r.remarks||r.source_type||'') +
          '</tr>';
      }).join('');
    }).catch(function(e){
      if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:red;padding:20px">❌ 로드 실패: '+escapeHtml(String(e))+'</td></tr>';
    });
  }

  /* ── 감사 로그 탭 (audit_log) ── */
  function _logLoadAudit(limit) {
    var tbody = document.getElementById('log-au-tbody');
    var cntEl = document.getElementById('log-au-count');
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-muted)">⏳ 로딩 중...</td></tr>';
    apiGet('/api/q/audit-log?limit=' + (limit||200)).then(function(res) {
      var rows = extractRows(res);
      if (cntEl) cntEl.textContent = rows.length + '건';
      if (!tbody) return;
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-muted)">📭 감사 로그 없음 (OneStop 출고 시 기록됨)</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function(r, i){
        var td = function(v){ return '<td style="text-align:center;white-space:nowrap">'+escapeHtml(String(v||''))+'</td>'; };
        return '<tr>' +
          td(i+1) +
          '<td style="text-align:center">' + _logTypeBadge(r.event_type||'') + '</td>' +
          td(r.lot_no||r.tonbag_id||'') +
          td(r.created_by||'') +
          '<td style="text-align:left;max-width:300px;overflow:hidden;text-overflow:ellipsis">' + escapeHtml(String(r.event_data||r.user_note||'')) + '</td>' +
          td((r.created_at||'').replace('T',' ').substring(0,16)) +
          '</tr>';
      }).join('');
    }).catch(function(e){
      if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:red;padding:20px">❌ 로드 실패: '+escapeHtml(String(e))+'</td></tr>';
    });
  }

  window._logActiveTab = 'movement';
  window.logSwitchTab = function(tab) {
    window._logActiveTab = tab;
    var mvPanel = document.getElementById('log-panel-movement');
    var auPanel = document.getElementById('log-panel-audit');
    var mvBtn   = document.getElementById('log-tab-movement');
    var auBtn   = document.getElementById('log-tab-audit');
    var activeStyle  = 'padding:6px 16px;border:none;cursor:pointer;font-size:13px;border-bottom:2px solid var(--accent);color:var(--accent);background:transparent;font-weight:600';
    var inactiveStyle= 'padding:6px 16px;border:none;cursor:pointer;font-size:13px;border-bottom:2px solid transparent;color:var(--text-muted);background:transparent;font-weight:400';
    if (mvBtn) mvBtn.style.cssText = tab==='movement' ? activeStyle : inactiveStyle;
    if (auBtn) auBtn.style.cssText = tab==='audit'    ? activeStyle : inactiveStyle;
    if (mvPanel) mvPanel.style.display = tab==='movement' ? '' : 'none';
    if (auPanel) auPanel.style.display = tab==='audit'    ? '' : 'none';
  };

  window.logRefresh = function() {
    var limit = parseInt((document.getElementById('log-limit-sel')||{}).value||300, 10);
    if (window._logActiveTab === 'movement') _logLoadMovement(limit);
    else _logLoadAudit(limit);
  };

  function loadLogPage() {
    var route = _currentRoute;
    var container = document.getElementById('page-container');
    if (!container) return;

    var thStyle = 'style="text-align:center;white-space:nowrap"';
    var activeStyle  = 'padding:6px 16px;border:none;cursor:pointer;font-size:13px;border-bottom:2px solid var(--accent);color:var(--accent);background:transparent;font-weight:600';
    var inactiveStyle= 'padding:6px 16px;border:none;cursor:pointer;font-size:13px;border-bottom:2px solid transparent;color:var(--text-muted);background:transparent;font-weight:400';

    container.innerHTML = [
      '<section class="page" data-page="log">',
      /* 헤더 */
      '<div style="display:flex;align-items:center;gap:12px;padding:8px 0 6px;flex-wrap:wrap">',
        '<h2 style="margin:0;white-space:nowrap">📋 로그</h2>',
        '<div style="display:flex;border-bottom:1px solid var(--panel-border)">',
          '<button id="log-tab-movement" style="'+activeStyle+'" onclick="logSwitchTab(\'movement\')">📊 활동 이력</button>',
          '<button id="log-tab-audit"    style="'+inactiveStyle+'" onclick="logSwitchTab(\'audit\')">🔒 감사 로그</button>',
        '</div>',
        '<div style="margin-left:auto;display:flex;align-items:center;gap:8px">',
          '<select id="log-limit-sel" style="padding:4px 8px;background:var(--bg);color:var(--fg);border:1px solid var(--panel-border);border-radius:4px;font-size:12px">',
            '<option value="100">최근 100건</option>',
            '<option value="300" selected>최근 300건</option>',
            '<option value="500">최근 500건</option>',
            '<option value="1000">최근 1000건</option>',
          '</select>',
          '<button class="btn btn-secondary" onclick="logRefresh()" style="white-space:nowrap">🔁 새로고침</button>',
        '</div>',
      '</div>',
      /* 통계 바 (movement) */
      '<div id="log-mv-stats" style="display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 6px;min-height:24px"></div>',
      /* ── 활동 이력 패널 ── */
      '<div id="log-panel-movement">',
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">',
          '<span style="font-size:12px;color:var(--text-muted)">입출고·이동 전체 이력 (stock_movement 기반)</span>',
          '<span id="log-mv-count" style="font-size:12px;color:var(--accent);margin-left:auto"></span>',
        '</div>',
        '<div style="overflow-x:auto">',
        '<table class="data-table" style="width:100%">',
          '<thead><tr>',
            '<th '+thStyle+'>#</th>',
            '<th '+thStyle+'>유형</th>',
            '<th '+thStyle+'>LOT NO</th>',
            '<th '+thStyle+'>중량 (KG)</th>',
            '<th '+thStyle+'>고객사</th>',
            '<th '+thStyle+'>작업자</th>',
            '<th '+thStyle+'>일시</th>',
            '<th '+thStyle+'>비고</th>',
          '</tr></thead>',
          '<tbody id="log-mv-tbody"></tbody>',
        '</table></div>',
      '</div>',
      /* ── 감사 로그 패널 ── */
      '<div id="log-panel-audit" style="display:none">',
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">',
          '<span style="font-size:12px;color:var(--text-muted)">OneStop 출고 감사 로그 (audit_log 기반)</span>',
          '<span id="log-au-count" style="font-size:12px;color:var(--accent);margin-left:auto"></span>',
        '</div>',
        '<div style="overflow-x:auto">',
        '<table class="data-table" style="width:100%">',
          '<thead><tr>',
            '<th '+thStyle+'>#</th>',
            '<th '+thStyle+'>이벤트</th>',
            '<th '+thStyle+'>LOT/톤백</th>',
            '<th '+thStyle+'>작업자</th>',
            '<th '+thStyle+'>내용</th>',
            '<th '+thStyle+'>일시</th>',
          '</tr></thead>',
          '<tbody id="log-au-tbody"></tbody>',
        '</table></div>',
      '</div>',
      '</section>'
    ].join('');

    window._logActiveTab = 'movement';
    _logLoadMovement(300);
  }"""

if OLD in c:
    c = c.replace(OLD, NEW, 1)
    print("PATCH OK: loadLogPage 전면 개선", flush=True)
else:
    print("PATCH FAIL: 기존 함수 패턴 못 찾음", flush=True)
    idx = c.find("function loadLogPage()")
    print(f"  함수 위치: {idx}")
    sys.exit(1)

with open(SRC, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)
print(f"Done. {len(c):,} bytes.", flush=True)
