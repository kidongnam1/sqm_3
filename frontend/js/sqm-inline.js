/* =======================================================================
   SQM Inventory v8.6.5 - sqm-inline.js
   Rebuilt: 2026-04-21  Ruby (Senior Software Architect)
   Updated: 2026-04-27  Draggable modals, parse log panel, step badge, ESC guard
   ======================================================================= */
(function () {
  'use strict';

  /* ===================================================
     CUSTOM TOOLTIP SYSTEM (SQM Dark Theme)
     title= 속성을 모두 data-sqm-tip= 으로 전환,
     OS 기본 툴팁 대신 커스텀 다크 스타일 툴팁 표시
     =================================================== */
  (function initSqmTooltip() {
    // ── 툴팁 DOM 요소 생성 ──
    var _tip = document.createElement('div');
    _tip.id = 'sqm-tooltip';
    _tip.style.cssText = [
      'position:fixed',
      'z-index:999999',
      'display:none',
      'max-width:320px',
      'padding:7px 12px',
      'background:linear-gradient(135deg,#0d1b2a 0%,#0a1628 100%)',
      'color:#c9e8f8',
      'border:1px solid #1e4a7a',
      'border-radius:7px',
      'font-size:12px',
      'font-family:"Malgun Gothic","\ub9d1\uc740 \uace0\ub515",Segoe UI,sans-serif',
      'line-height:1.5',
      'pointer-events:none',
      'box-shadow:0 4px 18px rgba(0,0,0,0.7),0 0 0 1px rgba(79,195,247,0.08)',
      'white-space:pre-wrap',
      'word-break:keep-all',
    ].join(';');
    document.body.appendChild(_tip);

    // ── title → data-sqm-tip 일괄 전환 ──
    function convertTitles(root) {
      (root || document).querySelectorAll('[title]').forEach(function(el) {
        var t = el.getAttribute('title');
        if (t) {
          el.setAttribute('data-sqm-tip', t);
          el.removeAttribute('title');
        }
      });
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function() { convertTitles(); });
    } else {
      convertTitles();
    }

    // ── MutationObserver: 동적 추가 요소 처리 ──
    var _observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(m) {
        m.addedNodes.forEach(function(node) {
          if (node.nodeType !== 1) return;
          if (node.hasAttribute && node.hasAttribute('title')) {
            node.setAttribute('data-sqm-tip', node.getAttribute('title'));
            node.removeAttribute('title');
          }
          convertTitles(node);
        });
        if (m.type === 'attributes' && m.attributeName === 'title' && m.target) {
          var t = m.target.getAttribute('title');
          if (t) {
            m.target.setAttribute('data-sqm-tip', t);
            m.target.removeAttribute('title');
          }
        }
      });
    });
    _observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['title']
    });

    // ── 위치 계산 ──
    function _pos(e) {
      var mx = e.clientX, my = e.clientY;
      var tw = _tip.offsetWidth  || 220;
      var th = _tip.offsetHeight || 36;
      var vw = window.innerWidth, vh = window.innerHeight;
      var gap = 14;
      var x = mx + gap;
      var y = my + gap;
      if (x + tw + 4 > vw) x = mx - tw - gap;
      if (y + th + 4 > vh) y = my - th - gap;
      if (x < 4) x = 4;
      if (y < 4) y = 4;
      _tip.style.left = x + 'px';
      _tip.style.top  = y + 'px';
    }

    var _active = null;
    var _showTimer = null;

    function _show(el, e) {
      var txt = el.getAttribute('data-sqm-tip');
      if (!txt) return;
      _active = el;
      clearTimeout(_showTimer);
      _showTimer = setTimeout(function() {
        _tip.textContent = txt;
        _tip.style.display = 'block';
        _pos(e);
      }, 180);
    }

    function _hide() {
      _active = null;
      clearTimeout(_showTimer);
      _tip.style.display = 'none';
    }

    document.addEventListener('mouseover', function(e) {
      var el = e.target && e.target.closest && e.target.closest('[data-sqm-tip]');
      if (el && el !== _active) _show(el, e);
      else if (!el) _hide();
    }, true);

    document.addEventListener('mouseout', function(e) {
      var rel = e.relatedTarget;
      if (!rel || !rel.closest || !rel.closest('[data-sqm-tip]')) _hide();
    }, true);

    document.addEventListener('mousemove', function(e) {
      if (_tip.style.display !== 'none') _pos(e);
    }, true);

    document.addEventListener('mousedown', _hide, true);
    document.addEventListener('click', _hide, true);
    document.addEventListener('keydown', _hide, true);

    console.log('[SQM Tooltip] custom dark tooltip ready');
  })();

  var API = 'http://127.0.0.1:8765';

  /* ===================================================
     0. ON-SCREEN DEBUG LOG PANEL
     F12 없이 화면 우측 하단에서 직접 확인
     F8 토글 / 기본: 숨김 (Ctrl+Shift+D → 알캡처 충돌로 F8 변경)
     =================================================== */
  var _dbgLogs = [];
  var _dbgMax  = 30;
  var _dbgEl   = null;

  function dbgLog(icon, label, detail, color) {
    var ts = new Date().toTimeString().slice(0,8);
    _dbgLogs.push({ts:ts, icon:icon, label:label, detail:detail, color:color||'#aaa'});
    if (_dbgLogs.length > _dbgMax) _dbgLogs.shift();
    _dbgRefresh();
  }

  function _dbgRefresh() {
    if (!_dbgEl || !_dbgEl.__body) return;
    _dbgEl.__body.innerHTML = _dbgLogs.slice().reverse().map(function(r){
      return '<div style="padding:2px 0;border-bottom:1px solid #222;color:'+r.color+'">'+
        '<span style="opacity:.6;font-size:10px">'+r.ts+'</span> '+
        r.icon+' <b>'+escapeHtml(r.label)+'</b>'+
        (r.detail ? '<div style="font-size:10px;color:#888;padding-left:8px">'+escapeHtml(String(r.detail).slice(0,120))+'</div>' : '')+
        '</div>';
    }).join('');
  }

  function _dbgBuild() {
    var wrap = document.createElement('div');
    wrap.id = 'sqm-debug-panel';
    wrap.style.cssText = [
      'position:fixed','bottom:8px','right:8px','width:340px','z-index:99999',
      'font-family:monospace','font-size:11px','border-radius:6px',
      'box-shadow:0 2px 12px rgba(0,0,0,.6)','display:none'
    ].join(';');

    var hdr = document.createElement('div');
    hdr.style.cssText = 'background:#1a1a2e;color:#00e5ff;padding:4px 8px;border-radius:6px 6px 0 0;display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none';
    hdr.innerHTML = '<span>🔍 SQM Debug Log</span><span style="font-size:10px;opacity:.6">(F8 토글)</span><button id="sqm-dbg-clear" style="margin-left:auto;background:#c00;color:#fff;border:none;border-radius:3px;padding:0 6px;cursor:pointer;font-size:10px">Clear</button>';

    var body = document.createElement('div');
    body.style.cssText = 'background:#0d0d1a;color:#ccc;padding:6px;max-height:260px;overflow-y:auto;border-radius:0 0 6px 6px';

    wrap.appendChild(hdr);
    wrap.appendChild(body);
    document.body.appendChild(wrap);

    wrap.__body = body;
    _dbgEl = wrap;

    hdr.querySelector('#sqm-dbg-clear').addEventListener('click', function(e){
      e.stopPropagation();
      _dbgLogs = [];
      _dbgRefresh();
    });

    // F8 토글 (Ctrl+Shift+D 는 알캡처 전역 단축키 충돌)
    document.addEventListener('keydown', function(e){
      if (e.key==='F8') {
        wrap.style.display = (wrap.style.display==='none') ? 'block' : 'none';
      }
    });

    dbgLog('🟢','Debug panel ready','F8 키로 토글 (Ctrl+Shift+D 알캡처 충돌 → F8 변경)','#4caf50');
  }

  /* ===================================================
     1. UTILITIES
     =================================================== */

  /** 범용 데이터 추출 — 모든 API 응답 패턴 대응
   *  {data: {items:[]}}  → items
   *  {data: {rows:[]}}   → rows
   *  {data: []}           → data
   *  []                   → 그대로
   *  그 외                → []
   */
  function extractRows(res) {
    if (Array.isArray(res)) return res;
    if (!res) return [];
    var d = res.data;
    if (Array.isArray(d)) return d;
    if (d && Array.isArray(d.items)) return d.items;
    if (d && Array.isArray(d.rows)) return d.rows;
    return [];
  }

  /* ===================================================
     1a. TABLE SORT — 컬럼 헤더 클릭으로 정렬 (v864.2 동일)
     사용법: <th> 에 자동 바인딩, 숫자/문자/날짜 자동 감지
     =================================================== */
  function enableTableSort(tableEl) {
    if (!tableEl || tableEl.dataset._sortBound) return;
    tableEl.dataset._sortBound = '1';
    var headers = tableEl.querySelectorAll('thead th');
    headers.forEach(function(th, colIdx) {
      th.style.cursor = 'pointer';
      th.style.userSelect = 'none';
      th.title = 'Click to sort';
      th.addEventListener('click', function() {
        var tbody = tableEl.querySelector('tbody');
        if (!tbody) return;
        var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
        var asc = th.dataset._sortDir !== 'asc';
        // 모든 th 리셋
        headers.forEach(function(h){ h.dataset._sortDir=''; h.textContent=h.textContent.replace(/ [▲▼]/g,''); });
        th.dataset._sortDir = asc ? 'asc' : 'desc';
        th.textContent = th.textContent + (asc ? ' ▲' : ' ▼');
        rows.sort(function(a, b) {
          var ca = (a.children[colIdx]||{}).textContent||'';
          var cb = (b.children[colIdx]||{}).textContent||'';
          // 숫자 감지
          var na = parseFloat(ca.replace(/,/g,'')), nb = parseFloat(cb.replace(/,/g,''));
          if (!isNaN(na) && !isNaN(nb)) return asc ? na-nb : nb-na;
          return asc ? ca.localeCompare(cb) : cb.localeCompare(ca);
        });
        rows.forEach(function(r){ tbody.appendChild(r); });
      });
    });
  }

  /* 페이지 렌더링 후 자동으로 테이블 정렬 바인딩 */
  var _sortObserver = new MutationObserver(function() {
    document.querySelectorAll('.data-table').forEach(enableTableSort);
  });
  _sortObserver.observe(document.documentElement, {childList:true, subtree:true});

  /* ===================================================
     1b. KEYBOARD SHORTCUTS (v864.2 동일)
     =================================================== */

  /* ── [UX] ESC = 현재 열린 창 닫기 (전역)
     우선순위: 컨텍스트 메뉴 → 모달 → 최상위 메뉴 드롭다운 → 입력 포커스
     input/textarea/select 안에서도 작동 (모달 닫기 우선).
     최상위 스코프에서 ESC 두 번(1.5초 이내) = 앱 종료 확인 다이얼로그. ── */
  var _escLastAt = 0;
  var EXIT_DOUBLE_ESC_WINDOW_MS = 1500;
  document.addEventListener('keydown', function(e){
    if (e.key !== 'Escape' && e.key !== 'Esc') return;

    /* 1순위: 컨텍스트 메뉴 (우클릭 팝업) */
    var ctx = document.querySelector('.ctx-menu');
    if (ctx) { ctx.remove(); e.preventDefault(); _escLastAt = 0; return; }

       /* 2순위: 모달 — ESC 두 번(1.5초 이내)으로만 닫기 (실수 방지) */
    var modal = document.getElementById('sqm-modal');
    if (modal && modal.style.display !== 'none' && modal.style.display !== '') {
      window._escModalCount = (window._escModalCount || 0) + 1;
      if (window._escModalCount === 1) {
        showToast('warning', '⚠️ ESC 한 번 더 누르면 창이 닫힙니다 (1.5초 이내)');
        clearTimeout(window._escModalTimer);
        window._escModalTimer = setTimeout(function(){ window._escModalCount = 0; }, 1500);
      } else {
        modal.style.display = 'none';
        window._escModalCount = 0;
        clearTimeout(window._escModalTimer);
      }
      e.preventDefault();
      _escLastAt = 0;
      return;
    }

    /* 3순위: 열린 상단 메뉴 드롭다운 (.menu-btn.open) */
    var openMenus = document.querySelectorAll('.menu-btn.open');
    if (openMenus.length) {
      openMenus.forEach(function(m){ m.classList.remove('open'); });
      if (document.activeElement && document.activeElement.blur) {
        try { document.activeElement.blur(); } catch(err) {}
      }
      e.preventDefault();
      _escLastAt = 0;
      return;
    }

    /* 4순위: 활성 input/textarea 포커스 해제 (편집 중단) */
    var ae = document.activeElement;
    if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable)) {
      try { ae.blur(); } catch(err) {}
      _escLastAt = 0;
      return;
    }

    /* 5순위: 아무것도 열려있지 않음 — 더블 ESC 감지 → 앱 종료 확인 */
    var now = Date.now();
    if ((now - _escLastAt) < EXIT_DOUBLE_ESC_WINDOW_MS) {
      _escLastAt = 0;
      e.preventDefault();
      if (confirm('앱을 종료하시겠습니까?')) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.exit_app) {
          window.pywebview.api.exit_app();
        } else {
          window.close();
        }
      }
    } else {
      _escLastAt = now;
      if (typeof showToast === 'function') {
        showToast('info', 'ESC 한 번 더 = 앱 종료', 1500);
      }
    }
  });

  /* ── [UX] 모달 Enter = primary 버튼 클릭 & Tab = 모달 내부 포커스 순환 ── */
  document.addEventListener('keydown', function(e){
    var modal = document.getElementById('sqm-modal');
    if (!modal || modal.style.display === 'none' || modal.style.display === '') return;

    /* Enter — primary 버튼 자동 클릭 (단, textarea 안에서는 줄바꿈 허용) */
    if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey) {
      if (e.target && e.target.tagName === 'TEXTAREA') return;         /* 줄바꿈 */
      if (e.target && e.target.tagName === 'BUTTON') return;           /* 브라우저 기본 */
      if (e.target && e.target.tagName === 'SELECT') return;           /* 선택 확정 */
      /* 우선 순위: .btn-primary > .btn[type=submit] > 모달 내 첫 번째 활성 버튼 */
      var primary =
        modal.querySelector('.btn-primary:not([disabled])') ||
        modal.querySelector('button[type="submit"]:not([disabled])');
      if (primary) {
        e.preventDefault();
        primary.click();
      }
      return;
    }

    /* [Sprint 1-2-D] Ctrl+Z / Ctrl+Y — 모달 안 편집 Undo/Redo
       OneStop Inbound 미리보기가 렌더된 상태에서만 작동 */
    if (e.ctrlKey && !e.altKey && typeof _onestopState !== 'undefined' && _onestopState.parsed) {
      /* input 안에서는 기본 undo 동작 허용 */
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
        /* Ctrl+Z 는 input 자체 undo 가 우선, Ctrl+Shift+Z 만 커스텀 redo */
        if (e.key === 'z' && e.shiftKey && typeof window.onestopRedo === 'function') {
          e.preventDefault();
          window.onestopRedo();
        }
        return;
      }
      if (e.key === 'z' && !e.shiftKey && typeof window.onestopUndo === 'function') {
        e.preventDefault();
        window.onestopUndo();
        return;
      }
      if ((e.key === 'y' || (e.key === 'z' && e.shiftKey)) && typeof window.onestopRedo === 'function') {
        e.preventDefault();
        window.onestopRedo();
        return;
      }
    }

    /* Tab — 모달 내부 포커스 트랩 (마지막 → 첫 번째, Shift+Tab 시 반대) */
    if (e.key === 'Tab') {
      var focusables = modal.querySelectorAll(
        'button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
        'select:not([disabled]), textarea:not([disabled]), a[href], ' +
        '[tabindex]:not([tabindex="-1"])'
      );
      if (focusables.length === 0) return;
      var first = focusables[0];
      var last  = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });

  document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
    var key = (e.ctrlKey?'C-':'') + (e.shiftKey?'S-':'') + (e.altKey?'A-':'') + e.key;
    switch(key) {
      case 'C-r': case 'F5': e.preventDefault(); renderPage(_currentRoute||'dashboard'); break;
      case 'C-1': e.preventDefault(); renderPage('inventory'); break;
      case 'C-2': e.preventDefault(); renderPage('allocation'); break;
      case 'C-3': e.preventDefault(); renderPage('picked'); break;
      case 'C-4': e.preventDefault(); renderPage('outbound'); break;
      case 'C-5': e.preventDefault(); renderPage('return'); break;
      case 'C-6': e.preventDefault(); renderPage('move'); break;
      case 'C-7': e.preventDefault(); renderPage('dashboard'); break;
      case 'C-8': e.preventDefault(); renderPage('log'); break;
      case 'C-9': e.preventDefault(); renderPage('scan'); break;
      case 'C-b': e.preventDefault(); dispatchAction('onOnBackup'); break;
      case 'C-e': e.preventDefault(); dispatchAction('onExport'); break;
      case 'C-i': e.preventDefault(); dispatchAction('onIntegrityCheck'); break;
    }
  });

  /* ===================================================
     1c. CONTEXT MENU — 테이블 행 우클릭 (v864.2 동일)
     =================================================== */
  var _ctxMenu = null;
  function showContextMenu(e, items) {
    e.preventDefault();
    hideContextMenu();
    var m = document.createElement('div');
    m.className = 'ctx-menu';
    m.style.cssText = 'position:fixed;z-index:9999;background:var(--panel-bg);border:1px solid var(--panel-border);border-radius:6px;padding:4px 0;min-width:160px;box-shadow:0 4px 16px rgba(0,0,0,.4);font-size:13px;';
    m.style.left = e.clientX+'px';
    m.style.top = e.clientY+'px';
    items.forEach(function(it){
      if (it === '---') { var hr=document.createElement('hr'); hr.style.cssText='margin:4px 8px;border:0;border-top:1px solid var(--panel-border)'; m.appendChild(hr); return; }
      var d = document.createElement('div');
      d.style.cssText = 'padding:6px 16px;cursor:pointer;color:var(--fg);white-space:nowrap;';
      d.textContent = it.label;
      d.addEventListener('mouseenter', function(){ d.style.background='var(--btn-hover)'; });
      d.addEventListener('mouseleave', function(){ d.style.background=''; });
      d.addEventListener('click', function(){ hideContextMenu(); if(it.action) it.action(); });
      m.appendChild(d);
    });
    document.body.appendChild(m);
    _ctxMenu = m;
    // 화면 밖으로 넘어가면 보정
    var r=m.getBoundingClientRect();
    if(r.right>window.innerWidth) m.style.left=(window.innerWidth-r.width-4)+'px';
    if(r.bottom>window.innerHeight) m.style.top=(window.innerHeight-r.height-4)+'px';
  }
  function hideContextMenu(){ if(_ctxMenu){ _ctxMenu.remove(); _ctxMenu=null; } }
  document.addEventListener('click', hideContextMenu);
  document.addEventListener('contextmenu', function(e){
    var tr = e.target.closest('.data-table tbody tr');
    if (!tr) return;
    var cells = tr.querySelectorAll('td');
    var lotCell = tr.querySelector('td:nth-child(1)') || {};
    var lot = (lotCell.textContent||'').trim();
    showContextMenu(e, [
      {label:'📋 LOT 상세 보기', action:function(){ if(window.showLotDetail) window.showLotDetail(lot); else showToast('info','LOT: '+lot); }},
      {label:'📤 Excel 내보내기', action:function(){ dispatchAction('onExport'); }},
      '---',
      {label:'📊 재고 현황', action:function(){ renderPage('inventory'); }},
      {label:'🔄 새로고침', action:function(){ renderPage(_currentRoute||'dashboard'); }},
    ]);
  });

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m];
    });
  }

  function ensureToastContainer() {
    var c = document.getElementById('toast-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'toast-container';
      document.body.appendChild(c);
    }
    return c;
  }

  var TOAST_ICONS = {success:'&#x2705;', info:'&#x2139;&#xFE0F;', warning:'&#x26A0;&#xFE0F;', error:'&#x274C;'};

  function showToast(type, message, duration) {
    if (!['success','info','warning','error'].includes(type)) type = 'info';
    duration = duration || 3000;
    var c = ensureToastContainer();
    var t = document.createElement('div');
    t.className = 'toast ' + type;
    t.innerHTML = '<span>' + (TOAST_ICONS[type]||'') + '</span><span>' + escapeHtml(message) + '</span>';
    c.appendChild(t);
    setTimeout(function () {
      t.style.opacity = '0';
      t.style.transition = 'opacity 300ms';
      setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 300);
    }, duration);
  }
  window.showToast = showToast;

  /* ===================================================
     2. API CLIENT
     =================================================== */
  var DEFAULT_TIMEOUT = 8000;

  function apiCall(method, path, body, opts) {
    opts = opts || {};
    var timeout = opts.timeout || DEFAULT_TIMEOUT;
    var retries = (opts.retries !== undefined) ? opts.retries : 2;
    var url = (path.indexOf('http') === 0) ? path : API + path;
    var fetchOpts = {
      method: method.toUpperCase(),
      headers: {'Content-Type':'application/json'}
    };
    if (body !== null && body !== undefined &&
        ['POST','PUT','DELETE'].includes(fetchOpts.method)) {
      fetchOpts.body = JSON.stringify(body);
    }
    // Debug log: request
    dbgLog('🔵', method.toUpperCase()+' '+path, null, '#64b5f6');
    function attempt(n) {
      var timer;
      var timeoutP = new Promise(function(_, rej) {
        timer = setTimeout(function(){ var e = new Error('timeout'); e.status=0; rej(e); }, timeout);
      });
      return Promise.race([fetch(url, fetchOpts), timeoutP])
        .then(function(res) {
          clearTimeout(timer);
          if (!res.ok) {
            return res.json().catch(function(){return null;}).then(function(detail){
              var e = new Error('HTTP ' + res.status);
              e.status = res.status; e.detail = detail;
              // Debug log: HTTP error
              var msg = (detail && (detail.detail||detail.message)) ? (detail.detail||detail.message) : '';
              dbgLog(res.status===501?'🟡':'🔴', 'HTTP '+res.status+' '+path, msg||'', res.status===501?'#ffa726':'#ef5350');
              throw e;
            });
          }
          // Debug log: success
          dbgLog('🟢', 'OK '+path, null, '#66bb6a');
          return res.json().catch(function(){return {};});
        })
        .catch(function(e) {
          clearTimeout(timer);
          if (e.status === 0) dbgLog('🔴','TIMEOUT '+path,'백엔드 응답 없음 (8초)','#ef5350');
          if (e.status === 501 || e.status === 404) throw e;
          if (n < retries) {
            return new Promise(function(r){ setTimeout(r, 500 * Math.pow(2,n)); })
              .then(function(){ return attempt(n+1); });
          }
          throw e;
        });
    }
    return attempt(0);
  }

  function apiGet(path, opts) { return apiCall('GET', path, null, opts); }
  function apiPost(path, body, opts) { return apiCall('POST', path, body, opts); }

  window.apiCall = apiCall;
  window.apiGet  = apiGet;
  window.apiPost = apiPost;

  /* ===================================================
     3. STATE / THEME
     =================================================== */
  function getStore() {
    try {
      localStorage.setItem('__probe__','1');
      localStorage.removeItem('__probe__');
      return localStorage;
    } catch {}
    try { return sessionStorage; } catch {}
    var m = {};
    return { getItem:function(k){return m[k]||null;},
             setItem:function(k,v){m[k]=String(v);},
             removeItem:function(k){delete m[k];} };
  }

  function applyTheme() {
    var store = getStore();
    var theme = store.getItem('sqm_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    var vm = store.getItem('sqm_view_mode') || 'mt';
    document.documentElement.setAttribute('data-view-mode', vm);
  }

  function toggleTheme() {
    var cur = document.documentElement.getAttribute('data-theme') || 'dark';
    var next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { getStore().setItem('sqm_theme', next); } catch {}
    showToast('info', (next === 'dark' ? '&#x1F319; Dark' : '&#x2600;&#xFE0F; Light') + ' theme');
  }

  /* ===================================================
     4. MENU CLOSE
     =================================================== */
  var _menuJustOpened = false;  // PyWebView/WebView2: stopPropagation 우회 방지 플래그

  function closeAllMenus() {
    // Fix: HTML uses .menu-btn[data-menu], not .menu-item — add both for safety
    document.querySelectorAll('.menu-btn.open').forEach(function(el){
      el.classList.remove('open');
    });
    document.querySelectorAll('.menu-dropdown.open,.menu-dropdown.active').forEach(function(el){
      el.classList.remove('open'); el.classList.remove('active');
    });
    document.querySelectorAll('.menu-item.active,.nav-item.open').forEach(function(el){
      el.classList.remove('active'); el.classList.remove('open');
    });
  }

  /* ===================================================
     5. ROUTER
     =================================================== */
  var _currentRoute = null;

  function showPage(route) {
    var dash = document.getElementById('dashboard-container');
    var page = document.getElementById('page-container');
    if (route === 'dashboard') {
      if (dash) { dash.style.display = 'block'; dash.style.removeProperty('display'); }
      if (page) page.style.display = 'none';
    } else {
      if (dash) dash.style.display = 'none';
      /* PyWebView/WebView2: style.display='' 이 inline none을 못 제거하는 경우 있음 → block 명시 */
      if (page) {
        page.style.removeProperty('display');
        page.style.display = 'block';
      }
    }
    /* 치수 측정 — height 0이면 flex 레이아웃 문제 */
    setTimeout(function(){
      var r1 = page ? page.getBoundingClientRect() : null;
      var r2 = page && page.parentElement ? page.parentElement.getBoundingClientRect() : null;
      dbgLog('📐','page-container rect',
        'W='+Math.round(r1?r1.width:0)+' H='+Math.round(r1?r1.height:0)+
        ' | wrapper H='+Math.round(r2?r2.height:0), '#ff9800');
    }, 300);
    dbgLog('🖥️','showPage', 'route='+route+
      ' dash='+(dash?dash.style.display:'?')+
      ' page='+(page?page.style.display:'?'), '#ab47bc');
    document.querySelectorAll('[data-route]').forEach(function(el){
      el.classList.toggle('active', el.dataset.route === route);
    });
  }

  function renderPage(route) {
    _currentRoute = route;
    closeAllMenus();
    showPage(route);
    try { getStore().setItem('sqm_last_tab', route); } catch {}
    if (history.replaceState) history.replaceState(null,'','#' + route);
    switch (route) {
      case 'dashboard':  loadDashboard();     break;
      case 'inventory':  loadInventoryPage();  break;
      case 'allocation': loadAllocationPage(); break;
      case 'picked':     loadPickedPage();     break;
      case 'inbound':    loadInboundPage();    break;
      case 'outbound':   loadOutboundPage();   break;
      case 'return':     loadReturnPage();     break;
      case 'move':       loadMovePage();       break;
      case 'log':        loadLogPage();        break;
      case 'scan':       loadScanPage();       break;
      case 'tonbag':     loadTonbagPage();     break;
      default:           loadStubPage(route);  break;
    }
  }

  function loadStubPage(route) {
    var c = document.getElementById('page-container');
    if (c) c.innerHTML = '<div class="empty" style="padding:60px;text-align:center;color:var(--text-muted)">Preparing: ' + escapeHtml(route) + '</div>';
  }

  window.renderPage = renderPage;

  /* ===================================================
     6. DASHBOARD
     =================================================== */
  var _kpiTimer = null;

  function loadDashboard() {
    loadKpi();
    loadDashboardTables();
  }

  function loadKpi() {
    apiGet('/api/dashboard/kpi').then(function(res) {
      var d = res.data || res || {};
      function sv(id, v) {
        var el = document.getElementById(id);
        if (el) el.textContent = (v === null || v === undefined) ? '-' : String(v);
      }
      sv('kpi-inbound-val',        d.inbound_today   !== undefined ? d.inbound_today   : (d.inbound   || '-'));
      sv('kpi-outbound-today-val', d.outbound_today  !== undefined ? d.outbound_today  : (d.outbound  || '-'));
      sv('kpi-stock-lots-val',     d.stock_lots       !== undefined ? d.stock_lots      : (d.lots      || '-'));
      sv('kpi-unassigned-val',     d.unassigned_bags  !== undefined ? d.unassigned_bags : (d.unassigned|| '-'));
    }).catch(function(){});
  }

  function startKpiPolling() {
    if (_kpiTimer) clearInterval(_kpiTimer);
    _kpiTimer = setInterval(function(){
      if (_currentRoute === 'dashboard' && document.visibilityState !== 'hidden') loadKpi();
    }, 5000);
  }

  function loadDashboardTables() {
    apiGet('/api/dashboard/stats').then(function(res){
      var d = res.data || res || {};
      renderStatusCards(d.status_summary || {});
      renderProductMatrix(d.product_matrix || []);
      renderIntegrity(d.integrity || {});
    }).catch(function(){
      renderStatusCards({});
      renderProductMatrix([]);
      renderIntegrity({});
    });
  }

  function fmtN(v) {
    if (typeof v !== 'number') return (v == null ? '-' : v);
    return v.toLocaleString('ko-KR',{minimumFractionDigits:1,maximumFractionDigits:1});
  }
  function fmtW(kg) {
    if (typeof kg !== 'number') return '-';
    return (kg / 1000).toLocaleString('ko-KR',{minimumFractionDigits:2,maximumFractionDigits:2}) + ' MT';
  }

  /* -- 5단계 재고 상태 카드 -- */
  var STATUS_CARD_META = [
    {key:'available', label:'Available (판매가능)', icon:'\u2705', color:'#22c55e'},
    {key:'reserved',  label:'Reserved (배정)',      icon:'\uD83D\uDCCB', color:'#3b82f6'},
    {key:'picked',    label:'Picked (피킹)',        icon:'\uD83D\uDCE6', color:'#f59e0b'},
    {key:'outbound',  label:'Outbound (출고)',      icon:'\uD83D\uDE9A', color:'#ef4444'},
    {key:'return',    label:'Return (반품)',         icon:'\uD83D\uDD04', color:'#8b5cf6'}
  ];

  function renderStatusCards(summary) {
    var el = document.getElementById('dashboard-detail');
    if (!el) return;
    var html = '<div style="margin-bottom:16px"><h3 style="margin:0 0 8px 0;font-size:15px;color:var(--text-primary,#e0e0e0)">';
    html += '5\uB2E8\uACC4 \uC7AC\uACE0 \uD604\uD669</h3>';
    html += '<div style="display:flex;gap:10px;flex-wrap:wrap">';
    STATUS_CARD_META.forEach(function(m){
      var s = summary[m.key] || {lots:0, tonbags:0, weight_kg:0};
      html += '<div style="flex:1;min-width:160px;background:var(--bg-card,#1e1e2e);border-left:4px solid '+m.color+';border-radius:8px;padding:12px 14px">';
      html += '<div style="font-size:13px;color:'+m.color+';font-weight:700;margin-bottom:6px">'+m.icon+' '+m.label+'</div>';
      html += '<div style="font-size:22px;font-weight:700;color:var(--text-primary,#e0e0e0)">'+s.tonbags+'<span style="font-size:12px;font-weight:400;color:var(--text-muted,#888)"> \uD1A4\uBC31</span></div>';
      html += '<div style="font-size:12px;color:var(--text-muted,#888);margin-top:2px">'+s.lots+' LOT \u00B7 '+fmtW(s.weight_kg)+'</div>';
      html += '</div>';
    });
    html += '</div></div>';
    html += '<div id="dash-matrix-area"></div>';
    html += '<div id="dash-integrity-area"></div>';
    el.innerHTML = html;
  }

  /* -- 제품x상태 매트릭스 테이블 -- */
  function renderProductMatrix(rows) {
    var el = document.getElementById('dash-matrix-area');
    if (!el) return;
    if (!rows.length) {
      el.innerHTML = '<p style="color:var(--text-muted,#888);font-size:13px">\uC81C\uD488\uBCC4 \uB370\uC774\uD130 \uC5C6\uC74C</p>';
      return;
    }
    var totals = {available:0, reserved:0, picked:0, outbound:0, return_cnt:0, total:0};
    rows.forEach(function(r){
      totals.available += (r.available||0);
      totals.reserved  += (r.reserved||0);
      totals.picked    += (r.picked||0);
      totals.outbound  += (r.outbound||0);
      totals.return_cnt+= (r['return']||0);
      totals.total     += (r.total||0);
    });
    var html = '<h3 style="margin:16px 0 8px 0;font-size:15px;color:var(--text-primary,#e0e0e0)">';
    html += '\uC81C\uD488\u00D7\uC0C1\uD0DC \uB9E4\uD2B8\uB9AD\uC2A4 (\uD1A4\uBC31 \uC218)</h3>';
    html += '<div style="overflow-x:auto"><table class="sqm-table" style="width:100%;font-size:13px;border-collapse:collapse">';
    html += '<thead><tr style="background:var(--bg-header,#2a2a3e)">';
    html += '<th style="text-align:left;padding:6px 10px">\uC81C\uD488</th>';
    html += '<th style="padding:6px 8px;color:#22c55e">Available</th>';
    html += '<th style="padding:6px 8px;color:#3b82f6">Reserved</th>';
    html += '<th style="padding:6px 8px;color:#f59e0b">Picked</th>';
    html += '<th style="padding:6px 8px;color:#ef4444">Outbound</th>';
    html += '<th style="padding:6px 8px;color:#8b5cf6">Return</th>';
    html += '<th style="padding:6px 8px;font-weight:700">Total</th>';
    html += '</tr></thead><tbody>';
    rows.forEach(function(r){
      html += '<tr>';
      html += '<td style="text-align:left;padding:5px 10px;font-weight:600">'+escapeHtml(r.product)+'</td>';
      html += '<td style="text-align:right;padding:5px 8px">'+(r.available||0)+'</td>';
      html += '<td style="text-align:right;padding:5px 8px">'+(r.reserved||0)+'</td>';
      html += '<td style="text-align:right;padding:5px 8px">'+(r.picked||0)+'</td>';
      html += '<td style="text-align:right;padding:5px 8px">'+(r.outbound||0)+'</td>';
      html += '<td style="text-align:right;padding:5px 8px">'+(r['return']||0)+'</td>';
      html += '<td style="text-align:right;padding:5px 8px;font-weight:700">'+(r.total||0)+'</td>';
      html += '</tr>';
    });
    html += '<tr style="border-top:2px solid var(--border-color,#444);font-weight:700">';
    html += '<td style="text-align:left;padding:5px 10px">Total</td>';
    html += '<td style="text-align:right;padding:5px 8px">'+totals.available+'</td>';
    html += '<td style="text-align:right;padding:5px 8px">'+totals.reserved+'</td>';
    html += '<td style="text-align:right;padding:5px 8px">'+totals.picked+'</td>';
    html += '<td style="text-align:right;padding:5px 8px">'+totals.outbound+'</td>';
    html += '<td style="text-align:right;padding:5px 8px">'+totals.return_cnt+'</td>';
    html += '<td style="text-align:right;padding:5px 8px">'+totals.total+'</td>';
    html += '</tr></tbody></table></div>';
    el.innerHTML = html;
  }

  /* -- 정합성 요약 -- */
  function renderIntegrity(data) {
    var el = document.getElementById('dash-integrity-area');
    if (!el) return;
    if (!data || data.total_inbound_kg === undefined) {
      el.innerHTML = '';
      return;
    }
    var ok = data.ok;
    var color = ok ? '#22c55e' : '#ef4444';
    var icon  = ok ? '\u2705' : '\u26A0\uFE0F';
    var label = ok ? '\uC815\uD569\uC131 OK' : '\uBD88\uC77C\uCE58 \uAC10\uC9C0';
    var html = '<div style="margin-top:16px;padding:12px 16px;background:var(--bg-card,#1e1e2e);border-left:4px solid '+color+';border-radius:8px">';
    html += '<h3 style="margin:0 0 8px 0;font-size:15px;color:'+color+'">'+icon+' \uC815\uD569\uC131 \uAC80\uC99D \u2014 '+label+'</h3>';
    html += '<div style="display:flex;gap:24px;flex-wrap:wrap;font-size:13px;color:var(--text-primary,#e0e0e0)">';
    html += '<div>\uCD1D\uC785\uACE0: <b>'+fmtW(data.total_inbound_kg)+'</b></div>';
    html += '<div>\uD604\uC7AC\uC7AC\uACE0: <b>'+fmtW(data.current_stock_kg)+'</b></div>';
    html += '<div>\uCD9C\uACE0\uB204\uACC4: <b>'+fmtW(data.outbound_total_kg)+'</b></div>';
    html += '<div>\uCC28\uC774: <b style="color:'+color+'">'+fmtN(data.diff_kg)+' kg</b></div>';
    html += '</div></div>';
    el.innerHTML = html;
  }

  /* ===================================================
     7a. PAGE: Inventory
     =================================================== */
  function loadInventoryPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = '<div style="padding:40px;text-align:center">Loading inventory...</div>';
    apiGet('/api/inventory').then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      if (!rows.length) {
        c.innerHTML = '<div class="empty" style="padding:60px;text-align:center">No inventory data</div>';
        return;
      }
      var html = '<section class="page" data-page="inventory">' +
        '<div style="display:flex;align-items:center;gap:12px;padding:4px 0 10px">' +
        '<h2 style="margin:0">📦 재고 목록 (Inventory)</h2>' +
        '<span style="font-size:12px;color:var(--text-muted)">'+rows.length+' LOTs</span>' +
        '<button class="btn btn-secondary" onclick="renderPage(\'inventory\')" style="margin-left:auto">🔁 새로고침</button>' +
        '</div>' +
        '<div style="overflow-x:auto"><table class="data-table"><thead><tr>' +
        '<th>#</th><th>LOT</th><th>SAP</th><th>BL</th><th>Product</th>' +
        '<th>Status</th><th>Balance(MT)</th><th>NET(MT)</th><th>Container</th>' +
        '<th>MXBG</th><th>Avail</th><th>Invoice</th>' +
        '<th>Ship</th><th>Arrival</th><th>Con Return</th><th>Free</th>' +
        '<th>WH</th><th>Customs</th><th>Inbound(MT)</th><th>Outbound(MT)</th><th>Location</th><th></th>' +
        '</tr></thead><tbody>';
      html += rows.map(function(r, i){
        return '<tr>' +
          '<td class="mono-cell" style="color:var(--text-muted)">'+(i+1)+'</td>' +
          '<td class="mono-cell" style="color:var(--accent);font-weight:600">'+escapeHtml(r.lot||'')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.sap||'')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.bl||'')+'</td>' +
          '<td><span class="tag">'+escapeHtml(r.product||'')+'</span></td>' +
          '<td>'+escapeHtml(r.status||'')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.balance!=null?fmtN(r.balance):'-')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.net!=null?fmtN(r.net):'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.container||'')+'</td>' +
          '<td class="mono-cell" style="text-align:center">'+(r.mxbg_pallet||'-')+'</td>' +
          '<td class="mono-cell" style="text-align:center">'+(r.avail_bags!=null?r.avail_bags:'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.invoice_no||'')+'</td>' +
          '<td class="mono-cell">'+escapeHtml((r.ship_date||'').slice(0,10))+'</td>' +
          '<td class="mono-cell">'+escapeHtml((r.arrival_date||'').slice(0,10))+'</td>' +
          '<td class="mono-cell">'+escapeHtml((r.con_return||'').slice(0,10))+'</td>' +
          '<td class="mono-cell" style="text-align:center">'+(r.free_time||'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.wh||'')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.customs||'')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.initial_weight!=null?fmtN(r.initial_weight):'-')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.outbound_weight!=null?fmtN(r.outbound_weight):'-')+'</td>' +
          '<td><span class="tag">'+escapeHtml(r.location||'-')+'</span></td>' +
          '<td><button class="btn btn-ghost btn-xs" onclick="window.showLotDetail(\''+escapeHtml(r.lot||'')+'\')">Detail</button></td>' +
          '</tr>';
      }).join('');
      html += '</tbody></table></div></section>';
      c.innerHTML = html;
    }).catch(function(e){
      if (_currentRoute !== route) return;
      c.innerHTML = '<div class="empty" style="padding:40px;text-align:center">Load failed: '+escapeHtml(e.message||String(e))+'</div>';
      showToast('error', 'Inventory load failed');
    });
  }

  /* ===================================================
     7b. PAGE: Allocation
     =================================================== */
  /* ===================================================
     7b. PAGE: Allocation — 2단 구조 (LOT 요약 + Detail)
     상단: LOT 단위 집계 (클릭 시 하단 확장)
     하단: 해당 LOT의 톤백 상세 목록
     =================================================== */
  /* ===================================================================
     [Sprint 1-1] Allocation 탭 — v864-2 AllocationDialog (1616줄) 포팅
     ──────────────────────────────────────────────────────────────────
     v864-2 source: gui_app_modular/dialogs/allocation_dialog.py
     v864-3 target: 이 함수 (탭 페이지) + 3개 기존 모달 재활용

     이 Phase(1-B+1-C)에서 구현:
       ✅ 9열 테이블 (ALLOC_PREVIEW_COLUMNS 매칭)
       ✅ 상단 액션 툴바 (4개 작동 + 3개 placeholder)
       ✅ 상태 필터 (전체/RESERVED/PICKED/SOLD)
       ✅ 다중 선택 체크박스 + 일괄 취소
       ✅ 합계 푸터 (qty_mt, 4 decimals)
       ✅ LOT 확장/축소 (기존 패턴 유지)

     다음 Phase(1-1-D~E)에서 추가:
       🟡 인라인 편집 (PATCH API 필요)
       🟡 PICKED/SOLD 상태 전환 (백엔드 엔드포인트 필요)
       🟡 LOT 예약 초기화 (백엔드 엔드포인트 필요)
       🟡 우클릭 컨텍스트 메뉴 (행 삭제/복사)
     =================================================================== */
  var _allocState = { currentFilter: 'all', rows: [], selectedLots: new Set() };
  /* [Sprint 1-1-D] 편집 가능 필드 (백엔드 _ALLOC_EDITABLE_FIELDS 와 일치 필요) */
  var ALLOC_EDITABLE_FIELDS = new Set(['customer', 'sale_ref', 'qty_mt', 'outbound_date']);

  function loadAllocationPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    _allocState.selectedLots.clear();
    c.innerHTML = [
      '<section class="page" data-page="allocation">',
      /* ── 헤더 ── */
      '<div class="alloc-header" style="display:flex;align-items:center;gap:12px;padding:8px 0 8px">',
      '  <h2 style="margin:0">📋 판매 배정 (Allocation)</h2>',
      '  <span id="alloc-summary-label" style="color:var(--text-muted);font-size:.9rem"></span>',
      '  <button class="btn btn-secondary" onclick="renderPage(\'allocation\')" style="margin-left:auto">🔁 새로고침</button>',
      '</div>',
      /* ── 액션 툴바 (v864-2 AllocationDialog primary_buttons 매핑) ── */
      '<div class="alloc-toolbar" style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:8px 10px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px">',
      '  <button class="btn btn-primary" onclick="window.allocUploadExcel()">📂 Excel 업로드</button>',
      '  <button class="btn" onclick="window.allocApplyApproved()">📌 승인분 반영</button>',
      '  <button class="btn" onclick="window.allocShowApprovalQueue()">✅ 승인 대기</button>',
      '  <span style="width:1px;height:22px;background:var(--panel-border);margin:0 4px"></span>',
      '  <button class="btn btn-danger" onclick="window.allocCancelSelected()">❌ 선택 배정 취소</button>',
      '  <span style="width:1px;height:22px;background:var(--panel-border);margin:0 4px"></span>',
      /* 백엔드 엔드포인트 미구현 — Sprint 1-1-E에서 연결 */
      '  <button class="btn" onclick="window.allocPickSelected()" title="RESERVED → PICKED">📦 출고 실행 (PICKED)</button>',
      '  <button class="btn" onclick="window.allocConfirmSelected()" title="PICKED → SOLD">🔒 출고 확정 (SOLD)</button>',
      '  <button class="btn" onclick="window.allocResetSelected()" title="LOT 배정 완전 삭제">🧹 LOT 초기화</button>',
      '</div>',
      /* ── 상태 필터 ── */
      '<div class="alloc-filter" style="display:flex;gap:4px;margin-bottom:8px">',
      '  <button class="alloc-filter-btn active" data-filter="all" onclick="window.allocFilterBy(\'all\')">전체</button>',
      '  <button class="alloc-filter-btn" data-filter="RESERVED" onclick="window.allocFilterBy(\'RESERVED\')">RESERVED</button>',
      '  <button class="alloc-filter-btn" data-filter="PICKED" onclick="window.allocFilterBy(\'PICKED\')">PICKED</button>',
      '  <button class="alloc-filter-btn" data-filter="SOLD" onclick="window.allocFilterBy(\'SOLD\')">SOLD</button>',
      '</div>',
      /* ── 로딩 / 빈 상태 ── */
      '<div id="alloc-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>',
      '<div class="empty" id="alloc-empty" style="display:none;padding:60px;text-align:center">📭 배정 데이터 없음</div>',
      /* ── 테이블 (v864-2 ALLOC_PREVIEW_COLUMNS: LOT/SAP/PRODUCT/QTY/CUSTOMER/SALE REF/OUTBOUND DATE/WH/STATUS) ── */
      '<div style="overflow-x:auto">',
      '  <table class="data-table" id="alloc-summary-table" style="display:none;width:100%">',
      '  <thead><tr>',
      '    <th style="width:32px"><input type="checkbox" id="alloc-select-all" onclick="window.allocToggleAll(this.checked)"></th>',
      '    <th style="width:40px">No.</th>',
      '    <th>LOT NO</th>',
      '    <th>SAP NO</th>',
      '    <th>PRODUCT</th>',
      '    <th style="text-align:right">QTY (MT)</th>',
      '    <th>CUSTOMER</th>',
      '    <th>SALE REF</th>',
      '    <th>OUTBOUND DATE</th>',
      '    <th>WH</th>',
      '    <th>STATUS</th>',
      '  </tr></thead>',
      '  <tbody id="alloc-summary-tbody"></tbody>',
      '  <tfoot id="alloc-summary-tfoot"></tfoot>',
      '  </table>',
      '</div>',
      /* ── 상세 패널 (기존 기능 유지) ── */
      '<div id="alloc-detail-panel" style="display:none;margin-top:16px;border-top:2px solid var(--panel-border);padding-top:16px">',
      '  <h3 id="alloc-detail-title" style="margin:0 0 12px 0">톤백 상세</h3>',
      '  <div id="alloc-detail-content"></div>',
      '</div>',
      '</section>'
    ].join('');

    apiGet('/api/q/allocation-summary').then(function(res){
      if (_currentRoute !== route) return;
      _allocState.rows = extractRows(res);
      document.getElementById('alloc-loading').style.display = 'none';
      if (!_allocState.rows.length) {
        document.getElementById('alloc-empty').style.display = 'block';
        var lbl = document.getElementById('alloc-summary-label');
        if (lbl) lbl.textContent = '(0건)';
        return;
      }
      _renderAllocTable();
    }).catch(function(e){
      if (_currentRoute !== route) return;
      document.getElementById('alloc-loading').style.display = 'none';
      document.getElementById('alloc-empty').textContent = 'Load failed: ' + (e.message||'');
      document.getElementById('alloc-empty').style.display = 'block';
    });
  }

  /* ── 테이블 렌더 (필터 적용) ────────────────────────────────────── */
  function _renderAllocTable() {
    var filter = _allocState.currentFilter;
    var rows = _allocState.rows.filter(function(r){
      if (filter === 'all') return true;
      return (r.status || 'RESERVED').toUpperCase() === filter;
    });
    var tbody = document.getElementById('alloc-summary-tbody');
    var tfoot = document.getElementById('alloc-summary-tfoot');
    var table = document.getElementById('alloc-summary-table');
    var empty = document.getElementById('alloc-empty');
    var lbl = document.getElementById('alloc-summary-label');

    if (!rows.length) {
      if (tbody) tbody.innerHTML = '';
      if (tfoot) tfoot.innerHTML = '';
      if (table) table.style.display = 'none';
      if (empty) { empty.textContent = '📭 (' + filter + ') 배정 데이터 없음'; empty.style.display = 'block'; }
      if (lbl) lbl.textContent = '(0/' + _allocState.rows.length + '건)';
      return;
    }
    if (empty) empty.style.display = 'none';
    if (table) table.style.display = '';
    if (lbl) lbl.textContent = '(' + rows.length + '/' + _allocState.rows.length + '건)';

    var totalMt = 0;
    /* [Sprint 1-1-D] 편집 가능 셀에 data-lot/data-field + ondblclick + oncontextmenu */
    tbody.innerHTML = rows.map(function(r, i){
      var lot = escapeHtml(r.lot_no || '');
      var qtyMt = (r.total_mt != null) ? Number(r.total_mt) : (r.qty_mt != null ? Number(r.qty_mt) : 0);
      if (!isNaN(qtyMt)) totalMt += qtyMt;
      var status = (r.status || 'RESERVED').toUpperCase();
      var statusColor = status === 'SOLD' ? '#66bb6a' : status === 'PICKED' ? '#42a5f5' : 'var(--warning)';
      var statusFg = status === 'RESERVED' ? '#000' : '#fff';
      var checked = _allocState.selectedLots.has(lot) ? 'checked' : '';

      /* 편집 가능 셀 attrs 헬퍼 */
      function editTd(field, display, extraClass, extraStyle) {
        var attrs = 'class="' + (extraClass || '') + ' alloc-editable" ' +
          'data-lot="' + lot + '" data-field="' + field + '"' +
          (extraStyle ? ' style="' + extraStyle + '"' : '') +
          ' ondblclick="window.allocEditCell(this)" title="더블클릭으로 편집";';
        return '<td ' + attrs + '>' + display + '</td>';
      }

      return '<tr class="alloc-summary-row" data-lot="' + lot + '" data-status="' + status + '" oncontextmenu="window.allocContextMenu(event, \'' + lot + '\'); return false;">' +
        '<td style="text-align:center"><input type="checkbox" ' + checked + ' onclick="event.stopPropagation();window.allocToggleRow(\'' + lot + '\',this.checked)"></td>' +
        '<td class="mono-cell" style="text-align:right">' + (i + 1) + '</td>' +
        '<td class="mono-cell" style="color:var(--accent);font-weight:600;cursor:pointer" onclick="window.toggleAllocDetail(\'' + lot + '\')">' +
          '<span class="alloc-expand-icon">▶</span> ' + lot + '</td>' +
        '<td class="mono-cell">' + escapeHtml(r.sap_no || '-') + '</td>' +
        '<td>' + escapeHtml(r.product || '-') + '</td>' +
        editTd('qty_mt', (qtyMt ? qtyMt.toFixed(4) : '-'), 'mono-cell', 'text-align:right') +
        editTd('customer', escapeHtml(r.customer || r.sold_to || '-'), '', '') +
        editTd('sale_ref', escapeHtml(r.sale_ref || '-'), 'mono-cell', '') +
        editTd('outbound_date', escapeHtml(r.outbound_date || r.ship_date || '-'), 'mono-cell', '') +
        '<td>' + escapeHtml(r.warehouse || r.wh || '-') + '</td>' +
        '<td><span class="tag" style="background:' + statusColor + ';color:' + statusFg + '">' + status + '</span></td>' +
        '</tr>';
    }).join('');

    /* Footer 합계 (v864-2 TreeviewTotalFooter 매칭) */
    tfoot.innerHTML =
      '<tr style="background:var(--panel);font-weight:700">' +
      '<td colspan="5" style="text-align:right">합계:</td>' +
      '<td class="mono-cell" style="text-align:right">' + totalMt.toFixed(4) + ' MT</td>' +
      '<td colspan="5"></td>' +
      '</tr>';
  }

  /* ── 버튼 핸들러 ─────────────────────────────────────────────────── */
  window.allocUploadExcel = function() {
    if (typeof showAllocationUploadModal === 'function') { showAllocationUploadModal(); }
    else { showToast('error', 'Upload modal 미초기화'); }
  };
  window.allocApplyApproved = function() {
    if (typeof showApplyApprovedAllocationModal === 'function') { showApplyApprovedAllocationModal(); }
    else { showToast('error', 'Apply modal 미초기화'); }
  };
  window.allocShowApprovalQueue = function() {
    if (typeof showApprovalQueueModal === 'function') { showApprovalQueueModal(); }
    else { showToast('error', 'Approval queue 미초기화'); }
  };
  window.allocWipToast = function(featureName) {
    showToast('info', featureName + ': 준비 중 (Sprint 1-1-E 예정 — 백엔드 엔드포인트 구현 후 연결)');
  };
  window.allocFilterBy = function(filter) {
    _allocState.currentFilter = filter;
    document.querySelectorAll('.alloc-filter-btn').forEach(function(b){
      b.classList.toggle('active', b.dataset.filter === filter);
    });
    _renderAllocTable();
  };
  window.allocToggleAll = function(checked) {
    var visibleFilter = _allocState.currentFilter;
    _allocState.rows.forEach(function(r){
      var status = (r.status || 'RESERVED').toUpperCase();
      if (visibleFilter !== 'all' && status !== visibleFilter) return;
      var lot = r.lot_no || '';
      if (checked) _allocState.selectedLots.add(lot);
      else _allocState.selectedLots.delete(lot);
    });
    _renderAllocTable();
  };
  window.allocToggleRow = function(lot, checked) {
    if (checked) _allocState.selectedLots.add(lot);
    else _allocState.selectedLots.delete(lot);
  };
  window.allocCancelSelected = function() {
    _allocBulkAction({
      url_suffix:   '/cancel',
      method:       'POST',
      label:        '배정 취소',
      icon:         '❌',
      confirmMsg:   '건 배정 취소?',
    });
  };

  /* ── [Sprint 1-1-E] 상태 전환 버튼 핸들러 ──────────────────────────── */
  window.allocPickSelected = function() {
    _allocBulkAction({
      url_suffix:   '/pick',
      method:       'POST',
      label:        '출고 실행 (PICKED)',
      icon:         '📦',
      confirmMsg:   '건을 PICKED 상태로 변경?\n(RESERVED → PICKED)',
    });
  };
  window.allocConfirmSelected = function() {
    _allocBulkAction({
      url_suffix:   '/confirm',
      method:       'POST',
      label:        '출고 확정 (SOLD)',
      icon:         '🔒',
      confirmMsg:   '건을 SOLD 상태로 확정?\n(PICKED → SOLD — 되돌릴 수 없음)',
    });
  };
  window.allocResetSelected = function() {
    _allocBulkAction({
      url_suffix:   '/reset',
      method:       'POST',
      label:        'LOT 배정 초기화',
      icon:         '🧹',
      confirmMsg:   '건 배정 완전 초기화?\nallocation_plan 에서 삭제 + inventory AVAILABLE 원복\n(SOLD 는 보호됨)',
    });
  };

  /* 공통 다중 선택 액션 헬퍼 */
  function _allocBulkAction(opts) {
    var selected = Array.from(_allocState.selectedLots);
    if (!selected.length) { showToast('warn', opts.label + ': 대상을 먼저 선택하세요'); return; }
    var preview = selected.slice(0, 5).join(', ') + (selected.length > 5 ? ' …외 ' + (selected.length - 5) + '건' : '');
    if (!confirm(opts.icon + ' ' + opts.label + '\n\n' + selected.length + opts.confirmMsg + '\n\n' + preview)) return;

    var okCount = 0, errors = [];
    var promises = selected.map(function(lot){
      return apiPost('/api/allocation/' + encodeURIComponent(lot) + opts.url_suffix, {})
        .then(function(){ okCount++; })
        .catch(function(e){ errors.push({ lot: lot, reason: (e && e.message) || String(e) }); });
    });
    Promise.all(promises).then(function(){
      var errCount = errors.length;
      if (errCount === 0) {
        showToast('success', opts.icon + ' ' + opts.label + ': ' + okCount + '건 성공');
      } else {
        var errSample = errors.slice(0, 3).map(function(e){ return e.lot + ' (' + e.reason + ')'; }).join(', ');
        showToast('warn', opts.label + ': 성공 ' + okCount + ' / 실패 ' + errCount + ' (' + errSample + ')');
      }
      _allocState.selectedLots.clear();
      loadAllocationPage();
    });
  }

  /* ── [Sprint 1-1-D] 인라인 편집 — 셀 더블클릭 → PATCH ─────────────── */
  window.allocEditCell = function(td) {
    if (!td || td.querySelector('input')) return;
    var lot = td.dataset.lot;
    var field = td.dataset.field;
    if (!lot || !field || !ALLOC_EDITABLE_FIELDS.has(field)) return;

    /* 현재 값 추출 (display 에서 HTML tag 제거) */
    var curDisplay = td.textContent.trim();
    var curVal = curDisplay === '-' ? '' : curDisplay;

    /* qty_mt 는 number input */
    var input = document.createElement('input');
    input.type = (field === 'qty_mt') ? 'number' : (field === 'outbound_date' ? 'date' : 'text');
    if (field === 'qty_mt') input.step = '0.0001';
    input.value = curVal;
    input.className = 'alloc-edit-input';
    input.style.cssText = 'width:100%;padding:2px 4px;background:var(--bg);color:var(--fg);border:1px solid var(--accent);border-radius:3px;font-size:11px;font-family:inherit';

    td.innerHTML = '';
    td.appendChild(input);
    input.focus();
    input.select && input.select();

    var committed = false;
    function cancel() {
      if (committed) return;
      committed = true;
      _renderAllocTable();  /* 원복 */
    }
    function commit() {
      if (committed) return;
      committed = true;
      var newVal = input.value;
      if (String(newVal).trim() === String(curVal).trim()) {
        _renderAllocTable();
        return;
      }
      /* PATCH /api/allocation/{lot} */
      td.innerHTML = '<span style="color:var(--text-muted);font-size:11px">⏳ 저장 중...</span>';
      var payload = {};
      payload[field] = newVal;
      fetch(API + '/api/allocation/' + encodeURIComponent(lot), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then(function(r){ return r.json().then(function(b){ return { ok: r.ok, body: b }; }); })
        .then(function(res){
          if (!res.ok || !res.body.success) {
            throw new Error((res.body && (res.body.detail || res.body.message)) || 'PATCH 실패');
          }
          /* 로컬 rows 업데이트 */
          var row = _allocState.rows.find(function(r){ return (r.lot_no || '') === lot; });
          if (row) {
            row[field] = (field === 'qty_mt') ? Number(newVal) : newVal;
            if (field === 'customer') row.sold_to = newVal;
          }
          showToast('success', '💾 ' + lot + '.' + field + ' 저장됨');
          _renderAllocTable();
        })
        .catch(function(e){
          showToast('error', '편집 실패: ' + (e.message || String(e)));
          _renderAllocTable();
        });
    }
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', function(e){
      if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
      else if (e.key === 'Escape') {
        e.preventDefault();
        input.removeEventListener('blur', commit);
        cancel();
      }
    });
  };

  /* ── [Sprint 1-1-D] 우클릭 컨텍스트 메뉴 — 행 삭제/복사 ─────────────── */
  window.allocContextMenu = function(e, lot) {
    e.preventDefault();
    /* 기존 컨텍스트 메뉴 제거 */
    var old = document.querySelector('.ctx-menu');
    if (old) old.remove();

    var row = _allocState.rows.find(function(r){ return (r.lot_no || '') === lot; });
    if (!row) return;

    var m = document.createElement('div');
    m.className = 'ctx-menu';
    m.style.cssText = 'position:fixed;z-index:9999;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;padding:4px 0;min-width:160px;box-shadow:0 4px 16px rgba(0,0,0,.4);font-size:13px;';
    m.style.left = e.clientX + 'px';
    m.style.top = e.clientY + 'px';

    function mi(label, onClick, danger) {
      var b = document.createElement('button');
      b.textContent = label;
      b.style.cssText = 'display:block;width:100%;text-align:left;padding:6px 14px;background:transparent;border:none;color:' + (danger ? 'var(--danger)' : 'var(--fg)') + ';cursor:pointer;font-size:13px';
      b.addEventListener('mouseover', function(){ b.style.background = 'var(--btn-hover)'; });
      b.addEventListener('mouseout', function(){ b.style.background = 'transparent'; });
      b.addEventListener('click', function(){ m.remove(); onClick(); });
      m.appendChild(b);
    }

    mi('📋 행 복사 (CSV)', function(){
      var cols = ['lot_no', 'sap_no', 'product', 'qty_mt', 'customer', 'sale_ref', 'outbound_date', 'warehouse', 'status'];
      var header = cols.join(',');
      var values = cols.map(function(c){ return String(row[c] != null ? row[c] : (c === 'customer' ? (row.sold_to || '') : '')); }).join(',');
      var text = header + '\n' + values;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function(){
          showToast('success', '📋 클립보드에 복사됨');
        }).catch(function(){
          prompt('수동 복사:', text);
        });
      } else {
        prompt('수동 복사:', text);
      }
    });

    mi('❌ 이 행 배정 취소', function(){
      if (!confirm('❌ ' + lot + '\n배정 취소하시겠습니까?')) return;
      apiPost('/api/allocation/' + encodeURIComponent(lot) + '/cancel', {})
        .then(function(){ showToast('success', lot + ' 취소됨'); loadAllocationPage(); })
        .catch(function(err){ showToast('error', '취소 실패: ' + (err.message || err)); });
    }, false);

    mi('🧹 이 행 초기화 (삭제)', function(){
      if (!confirm('🧹 ' + lot + '\nallocation 기록 삭제 + inventory AVAILABLE 원복\n(SOLD 는 보호됨)\n계속하시겠습니까?')) return;
      apiPost('/api/allocation/' + encodeURIComponent(lot) + '/reset', {})
        .then(function(res){ showToast('success', (res.data && res.data.message) || (lot + ' 초기화됨')); loadAllocationPage(); })
        .catch(function(err){ showToast('error', '초기화 실패: ' + (err.message || err)); });
    }, true);

    document.body.appendChild(m);
    /* 다음 클릭 또는 ESC 로 자동 닫기 */
    var closeHandler = function(ev){
      if (!m.contains(ev.target)) { m.remove(); document.removeEventListener('click', closeHandler); }
    };
    setTimeout(function(){ document.addEventListener('click', closeHandler); }, 10);
  };

  var _allocExpandedLot = null;
  window.toggleAllocDetail = function(lotNo) {
    var panel = document.getElementById('alloc-detail-panel');
    var content = document.getElementById('alloc-detail-content');
    var title = document.getElementById('alloc-detail-title');

    // 같은 LOT 클릭 시 닫기
    if (_allocExpandedLot === lotNo) {
      panel.style.display = 'none';
      _allocExpandedLot = null;
      document.querySelectorAll('.alloc-summary-row').forEach(function(r){ r.style.background=''; });
      document.querySelectorAll('.alloc-expand-icon').forEach(function(i){ i.textContent='▶'; });
      return;
    }

    _allocExpandedLot = lotNo;
    document.querySelectorAll('.alloc-summary-row').forEach(function(r){
      if (r.dataset.lot === lotNo) {
        r.style.background = 'var(--bg-active)';
        r.querySelector('.alloc-expand-icon').textContent = '▼';
      } else {
        r.style.background = '';
        r.querySelector('.alloc-expand-icon').textContent = '▶';
      }
    });

    panel.style.display = 'block';
    title.textContent = '📋 ' + lotNo + ' 톤백 상세';
    content.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">⏳ 로딩...</div>';

    apiGet('/api/q/allocation-detail/' + encodeURIComponent(lotNo)).then(function(res){
      var rows = extractRows(res);
      if (!rows.length) { content.innerHTML = '<div class="empty">상세 데이터 없음</div>'; return; }
      var tbl = '<table class="data-table"><thead><tr><th>#</th><th>톤백ID</th><th>중량(kg)</th><th>위치</th><th>상태</th><th>배정일</th></tr></thead><tbody>';
      tbl += rows.map(function(r, i){
        return '<tr><td>'+(i+1)+'</td><td class="mono-cell">'+escapeHtml(r.tonbag_id||r.sub_lt||'-')+'</td><td class="mono-cell" style="text-align:right">'+(r.weight!=null?Number(r.weight).toLocaleString():'-')+'</td><td>'+escapeHtml(r.location||'-')+'</td><td><span class="tag">'+escapeHtml(r.status||'-')+'</span></td><td>'+escapeHtml(r.plan_date||r.allocated_date||'-')+'</td></tr>';
      }).join('');
      tbl += '</tbody></table>';
      content.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:8px">' + rows.length + '개 톤백</p>' + tbl;
    }).catch(function(e){
      content.innerHTML = '<div class="empty">상세 로드 실패: '+escapeHtml(e.message||'')+'</div>';
    });
  };

  window.cancelAllocation = function(lot) {
    if (!confirm(lot + ': cancel allocation?')) return;
    apiPost('/api/allocation/' + encodeURIComponent(lot) + '/cancel', {})
      .then(function(){ showToast('success', lot + ' allocation cancelled'); loadAllocationPage(); })
      .catch(function(e){ showToast('error', 'Cancel failed: ' + (e.message||String(e))); });
  };

  /* ===================================================
     7c. PAGE: Picked
     =================================================== */
  /* ===================================================
     7c. PAGE: Picked — 2단 구조 (LOT 요약 + 톤백 상세)
     =================================================== */
  function loadPickedPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="picked">',
      '<div style="display:flex;align-items:center;gap:12px;padding:8px 0 12px">',
      '  <h2 style="margin:0">🚛 Picked - 피킹 완료 (화물 결정)</h2>',
      '  <button class="btn btn-secondary" onclick="renderPage(\'picked\')" style="margin-left:auto">🔁 새로고침</button>',
      '</div>',
      '<div id="picked-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '  <table class="data-table" id="picked-table" style="display:none">',
      '  <thead><tr><th></th><th>LOT No</th><th>피킹No</th><th>고객사</th><th>톤백수</th><th>중량(kg)</th><th>피킹일</th></tr></thead>',
      '  <tbody id="picked-tbody"></tbody>',
      '  </table>',
      '</div>',
      '<div class="empty" id="picked-empty" style="display:none;padding:60px;text-align:center">📭 피킹 데이터 없음</div>',
      '<div id="picked-detail-panel" style="display:none;margin-top:16px;border-top:2px solid var(--border);padding-top:16px">',
      '  <h3 id="picked-detail-title" style="margin:0 0 12px 0">톤백 상세</h3>',
      '  <div id="picked-detail-content"></div>',
      '</div>',
      '</section>'
    ].join('');

    apiGet('/api/q/picked-list').then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      document.getElementById('picked-loading').style.display = 'none';
      if (!rows.length) { document.getElementById('picked-empty').style.display='block'; return; }
      var tbody = document.getElementById('picked-tbody');
      if (tbody) tbody.innerHTML = rows.map(function(r){
        var lot = escapeHtml(r.lot_no||'');
        return '<tr class="picked-summary-row" data-lot="'+lot+'" style="cursor:pointer" onclick="window.togglePickedDetail(\''+lot+'\')">' +
          '<td style="width:24px;text-align:center"><span class="picked-expand-icon">▶</span></td>' +
          '<td class="mono-cell" style="color:var(--accent);font-weight:600">'+lot+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.picking_no||'')+'</td>' +
          '<td>'+escapeHtml(r.customer||r.picked_to||'')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.tonbag_count||0)+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.total_kg!=null?fmtN(r.total_kg):'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.picking_date||'')+'</td>' +
          '</tr>';
      }).join('');
      document.getElementById('picked-table').style.display = '';
    }).catch(function(e){
      if (_currentRoute !== route) return;
      document.getElementById('picked-loading').style.display = 'none';
      var el = document.getElementById('picked-empty');
      if (el) { el.textContent = 'Load failed: '+(e.message||String(e)); el.style.display='block'; }
    });
  }

  var _pickedExpandedLot = null;
  window.togglePickedDetail = function(lotNo) {
    var panel = document.getElementById('picked-detail-panel');
    var content = document.getElementById('picked-detail-content');
    var title = document.getElementById('picked-detail-title');

    if (_pickedExpandedLot === lotNo) {
      panel.style.display = 'none';
      _pickedExpandedLot = null;
      document.querySelectorAll('.picked-summary-row').forEach(function(r){ r.style.background=''; });
      document.querySelectorAll('.picked-expand-icon').forEach(function(i){ i.textContent='▶'; });
      return;
    }

    _pickedExpandedLot = lotNo;
    document.querySelectorAll('.picked-summary-row').forEach(function(r){
      if (r.dataset.lot === lotNo) {
        r.style.background = 'var(--bg-active)';
        r.querySelector('.picked-expand-icon').textContent = '▼';
      } else {
        r.style.background = '';
        r.querySelector('.picked-expand-icon').textContent = '▶';
      }
    });

    panel.style.display = 'block';
    title.textContent = '🚛 ' + lotNo + ' 톤백 상세';
    content.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">⏳ 로딩...</div>';

    apiGet('/api/tonbags?lot_no=' + encodeURIComponent(lotNo)).then(function(res){
      var rows = extractRows(res);
      if (!rows.length) { content.innerHTML = '<div class="empty">톤백 데이터 없음</div>'; return; }
      var tbl = '<table class="data-table"><thead><tr><th>#</th><th>톤백ID</th><th>중량(kg)</th><th>위치</th><th>상태</th><th>피킹일</th></tr></thead><tbody>';
      tbl += rows.map(function(r, i){
        return '<tr><td>'+(i+1)+'</td><td class="mono-cell">'+escapeHtml(r.sub_lt||r.tonbag_id||'-')+'</td><td class="mono-cell" style="text-align:right">'+(r.weight!=null?Number(r.weight).toLocaleString():'-')+'</td><td>'+escapeHtml(r.location||'-')+'</td><td><span class="tag">'+escapeHtml(r.status||'-')+'</span></td><td>'+escapeHtml(r.picked_date||r.updated_at||'-')+'</td></tr>';
      }).join('');
      tbl += '</tbody></table>';
      content.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:8px">' + rows.length + '개 톤백</p>' + tbl;
    }).catch(function(e){
      content.innerHTML = '<div class="empty">톤백 로드 실패: '+escapeHtml(e.message||'')+'</div>';
    });
  };

  /* ===================================================
     7c-2. PAGE: Inbound (입고 목록 — F009)
     /api/q/inbound-status → res.data.items
     columns: lot_no, lot_sqm, sap_no, bl_no, product,
              net_weight, current_weight, tonbag_count,
              status, inbound_date, arrival_date, warehouse, vessel
     =================================================== */
  /* _inboundAllRows: 전체 행 캐시 (필터용) */
  var _inboundAllRows = [];

  var STATUS_COLOR = {
    'INBOUND':'#1976d2','ALLOCATED':'#7b1fa2','PICKED':'#f57c00',
    'OUTBOUND':'#388e3c','RETURN':'#c62828','HOLD':'#616161'
  };

  function _renderInboundRows(rows) {
    var tbody = document.getElementById('inbound-tbody');
    var empty = document.getElementById('inbound-empty');
    var tbl   = document.getElementById('inbound-table');
    if (!tbody) return;
    if (!rows.length) {
      if (tbl)   tbl.style.display   = 'none';
      if (empty) { empty.textContent = '📭 해당 상태의 데이터 없음'; empty.style.display = 'block'; }
      return;
    }
    if (empty) empty.style.display = 'none';
    tbody.innerHTML = rows.map(function(r, i){
      var sc     = STATUS_COLOR[r.status] || '#888';
      var netMT  = r.net_weight     != null ? fmtN(r.net_weight     / 1000) : '-';
      var curMT  = r.current_weight != null ? fmtN(r.current_weight / 1000) : '-';
      return '<tr>' +
        '<td class="mono-cell" style="color:var(--text-muted)">'+(i+1)+'</td>' +
        '<td class="mono-cell" style="color:var(--accent);font-weight:600">'+escapeHtml(r.lot_no||'')+'</td>' +
        '<td class="mono-cell">'+escapeHtml(r.lot_sqm||'-')+'</td>' +
        '<td class="mono-cell">'+escapeHtml(r.sap_no||'-')+'</td>' +
        '<td class="mono-cell">'+escapeHtml(r.bl_no||'-')+'</td>' +
        '<td><span class="tag">'+escapeHtml(r.product||'-')+'</span></td>' +
        '<td class="mono-cell" style="text-align:right">'+netMT+'</td>' +
        '<td class="mono-cell" style="text-align:right">'+curMT+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+(r.tonbag_count||0)+'</td>' +
        '<td><span style="color:'+sc+';font-weight:600;font-size:11px">'+escapeHtml(r.status||'-')+'</span></td>' +
        '<td class="mono-cell">'+escapeHtml((r.inbound_date||'').slice(0,10)||'-')+'</td>' +
        '<td class="mono-cell">'+escapeHtml((r.arrival_date||'').slice(0,10)||'-')+'</td>' +
        '<td><span class="tag">'+escapeHtml(r.warehouse||'-')+'</span></td>' +
        '<td>'+escapeHtml(r.vessel||'-')+'</td>' +
        '</tr>';
    }).join('');
    if (tbl) tbl.style.display = '';
    dbgLog('📋','inbound-table shown', 'rows='+rows.length+' tbl='+(tbl?tbl.style.display:'?'), '#4caf50');
  }

  function _inboundFilter(status) {
    /* 필터 버튼 active 상태 갱신 */
    document.querySelectorAll('.inbound-filter-btn').forEach(function(b){
      b.style.fontWeight = (b.dataset.status === status) ? '700' : '400';
      b.style.opacity    = (b.dataset.status === status) ? '1'   : '0.55';
    });
    var filtered = status === 'ALL'
      ? _inboundAllRows
      : _inboundAllRows.filter(function(r){ return r.status === status; });
    var count = document.getElementById('inbound-count');
    if (count) count.textContent = filtered.length + ' / ' + _inboundAllRows.length + '건';
    _renderInboundRows(filtered);
  }
  window._inboundFilter = _inboundFilter;   /* HTML onclick에서 호출 */

  function loadInboundPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    _inboundAllRows = [];

    var FILTERS = ['ALL','INBOUND','ALLOCATED','PICKED','OUTBOUND','RETURN','HOLD'];
    var filterBtns = FILTERS.map(function(s){
      var col = STATUS_COLOR[s] || '#555';
      return '<button class="inbound-filter-btn" data-status="'+s+'" '+
        'onclick="_inboundFilter(\''+s+'\')" '+
        'style="border:1px solid '+col+';color:'+col+';background:transparent;'+
        'border-radius:4px;padding:3px 10px;cursor:pointer;font-size:12px;font-weight:400;opacity:0.55">'+s+'</button>';
    }).join('');

    c.innerHTML = [
      '<section class="page" data-page="inbound">',
      '<div style="display:flex;align-items:center;gap:12px;padding:8px 0 10px;flex-wrap:wrap">',
      '<h2 style="margin:0;white-space:nowrap">📥 입고 목록</h2>',
      '<div style="display:flex;gap:6px;flex-wrap:wrap">'+filterBtns+'</div>',
      '<span id="inbound-count" style="margin-left:auto;font-size:12px;color:var(--text-muted)">--</span>',
      '<button class="btn btn-secondary" onclick="renderPage(\'inbound\')" style="white-space:nowrap">🔁 새로고침</button>',
      '</div>',
      '<div id="inbound-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '<table class="data-table" id="inbound-table" style="display:none">',
      '<thead><tr>',
      '<th>#</th><th>LOT No</th><th>SQM LOT</th><th>SAP No</th><th>BL No</th>',
      '<th>제품</th><th>순중량(MT)</th><th>현재중량(MT)</th><th>톤백수</th>',
      '<th>상태</th><th>입고일자</th><th>도착일자</th><th>창고</th><th>선박</th>',
      '</tr></thead>',
      '<tbody id="inbound-tbody"></tbody>',
      '</table>',
      '</div>',
      '<div class="empty" id="inbound-empty" style="display:none;padding:60px;text-align:center;color:var(--text-muted)">📭 입고 데이터 없음</div>',
      '</section>'
    ].join('');

    apiGet('/api/q/inbound-status').then(function(res){
      if (_currentRoute !== route) return;
      _inboundAllRows = (res.data && res.data.items) || [];
      var total = _inboundAllRows.length;
      document.getElementById('inbound-loading').style.display = 'none';
      if (!total) {
        document.getElementById('inbound-empty').style.display = 'block';
        return;
      }
      _inboundFilter('ALL');   /* ALL 버튼 active + 전체 렌더 */
      dbgLog('📥','inbound-page','total='+total,'#4caf50');
    }).catch(function(e){
      if (_currentRoute !== route) return;
      document.getElementById('inbound-loading').style.display = 'none';
      var el = document.getElementById('inbound-empty');
      if (el) { el.textContent = '❌ 로드 실패: '+(e.message||String(e)); el.style.display = 'block'; }
      showToast('error', '입고 목록 로드 실패');
      dbgLog('❌','inbound-page',String(e),'#f44336');
    });
  }

  /* ===================================================
     7d. PAGE: Outbound (출고 현황 — F025/F037)
     /api/q/outbound-status → res.data.items
     columns: lot_no, movement_type, qty_kg, customer,
              from_location, to_location, movement_date,
              source_type, actor, remarks
     =================================================== */
  /* ===================================================
     7d. PAGE: Outbound/Sold — 2단 구조 (LOT 요약 + 톤백 상세)
     =================================================== */
  function loadOutboundPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="outbound">',
      '<div style="display:flex;align-items:center;gap:12px;padding:8px 0 12px">',
      '  <h2 style="margin:0">📤 출고 완료 (Sold / Outbound)</h2>',
      '  <button class="btn btn-secondary" onclick="renderPage(\'outbound\')" style="margin-left:auto">🔁 새로고침</button>',
      '</div>',
      '<div id="outbound-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '  <table class="data-table" id="outbound-table" style="display:none">',
      '  <thead><tr><th></th><th>#</th><th>LOT No</th><th>판매주문No</th><th>고객사</th><th>톤백수</th><th>중량(kg)</th><th>출고일</th></tr></thead>',
      '  <tbody id="outbound-tbody"></tbody>',
      '  </table>',
      '</div>',
      '<div class="empty" id="outbound-empty" style="display:none;padding:60px;text-align:center;color:var(--text-muted)">📭 출고 데이터 없음</div>',
      '<div id="outbound-detail-panel" style="display:none;margin-top:16px;border-top:2px solid var(--border);padding-top:16px">',
      '  <h3 id="outbound-detail-title" style="margin:0 0 12px 0">톤백 상세</h3>',
      '  <div id="outbound-detail-content"></div>',
      '</div>',
      '</section>'
    ].join('');

    apiGet('/api/q/sold-list').then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      document.getElementById('outbound-loading').style.display = 'none';
      if (!rows.length) {
        document.getElementById('outbound-empty').style.display = 'block';
        return;
      }
      var tbody = document.getElementById('outbound-tbody');
      if (tbody) tbody.innerHTML = rows.map(function(r, i){
        var lot = escapeHtml(r.lot_no||'');
        return '<tr class="outbound-summary-row" data-lot="'+lot+'" style="cursor:pointer" onclick="window.toggleOutboundDetail(\''+lot+'\')">' +
          '<td style="width:24px;text-align:center"><span class="outbound-expand-icon">▶</span></td>' +
          '<td class="mono-cell" style="color:var(--text-muted)">'+(i+1)+'</td>' +
          '<td class="mono-cell" style="color:var(--accent);font-weight:600">'+lot+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.sales_order_no||'-')+'</td>' +
          '<td>'+escapeHtml(r.customer||'-')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.tonbag_count||0)+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+(r.total_kg!=null?fmtN(r.total_kg):'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.sold_date||'-')+'</td>' +
          '</tr>';
      }).join('');
      document.getElementById('outbound-table').style.display = '';
      dbgLog('📤','outbound-page','rows='+rows.length,'#4caf50');
    }).catch(function(e){
      if (_currentRoute !== route) return;
      document.getElementById('outbound-loading').style.display = 'none';
      var el = document.getElementById('outbound-empty');
      if (el) { el.textContent = '❌ 로드 실패: '+(e.message||String(e)); el.style.display = 'block'; }
      showToast('error', '출고 현황 로드 실패');
    });
  }

  var _outboundExpandedLot = null;
  window.toggleOutboundDetail = function(lotNo) {
    var panel = document.getElementById('outbound-detail-panel');
    var content = document.getElementById('outbound-detail-content');
    var title = document.getElementById('outbound-detail-title');

    if (_outboundExpandedLot === lotNo) {
      panel.style.display = 'none';
      _outboundExpandedLot = null;
      document.querySelectorAll('.outbound-summary-row').forEach(function(r){ r.style.background=''; });
      document.querySelectorAll('.outbound-expand-icon').forEach(function(i){ i.textContent='▶'; });
      return;
    }

    _outboundExpandedLot = lotNo;
    document.querySelectorAll('.outbound-summary-row').forEach(function(r){
      if (r.dataset.lot === lotNo) {
        r.style.background = 'var(--bg-active)';
        r.querySelector('.outbound-expand-icon').textContent = '▼';
      } else {
        r.style.background = '';
        r.querySelector('.outbound-expand-icon').textContent = '▶';
      }
    });

    panel.style.display = 'block';
    title.textContent = '📤 ' + lotNo + ' 톤백 상세';
    content.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">⏳ 로딩...</div>';

    apiGet('/api/tonbags?lot_no=' + encodeURIComponent(lotNo)).then(function(res){
      var rows = extractRows(res);
      if (!rows.length) { content.innerHTML = '<div class="empty">톤백 데이터 없음</div>'; return; }
      var tbl = '<table class="data-table"><thead><tr><th>#</th><th>톤백ID</th><th>중량(kg)</th><th>위치</th><th>상태</th><th>출고일</th></tr></thead><tbody>';
      tbl += rows.map(function(r, i){
        return '<tr><td>'+(i+1)+'</td><td class="mono-cell">'+escapeHtml(r.sub_lt||r.tonbag_id||'-')+'</td><td class="mono-cell" style="text-align:right">'+(r.weight!=null?Number(r.weight).toLocaleString():'-')+'</td><td>'+escapeHtml(r.location||'-')+'</td><td><span class="tag">'+escapeHtml(r.status||'-')+'</span></td><td>'+escapeHtml(r.sold_date||r.updated_at||'-')+'</td></tr>';
      }).join('');
      tbl += '</tbody></table>';
      content.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:8px">' + rows.length + '개 톤백</p>' + tbl;
    }).catch(function(e){
      content.innerHTML = '<div class="empty">톤백 로드 실패: '+escapeHtml(e.message||'')+'</div>';
    });
  };

  /* ===================================================
     7e. PAGE: Return
     =================================================== */
  function loadReturnPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="return">',
      '<h2>Return - Re-inbound</h2>',
      '<div class="toolbar-mini"><button class="btn btn-secondary" onclick="renderPage(\'return\')">Refresh</button></div>',
      '<div id="return-loading" style="padding:40px;text-align:center">Loading...</div>',
      '<table class="data-table" id="return-table" style="display:none">',
      '<thead><tr><th>LOT</th><th>Product</th><th>Qty</th><th>Date</th><th>Reason</th></tr></thead>',
      '<tbody id="return-tbody"></tbody></table>',
      '<div class="empty" id="return-empty" style="display:none">No return data</div>',
      '</section>'
    ].join('');
    /* return-stats는 통계 구조(by_reason/monthly_trend)라 items 없음 → inventory?status=RETURN 직접 조회 */
    apiGet('/api/inventory?status=RETURN').then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      renderReturnRows(rows, route);
    }).catch(function(){
      if (_currentRoute !== route) return;
      document.getElementById('return-loading').style.display = 'none';
      document.getElementById('return-empty').style.display = 'block';
    });
  }

  function renderReturnRows(rows, route) {
    if (_currentRoute !== route) return;
    document.getElementById('return-loading').style.display = 'none';
    if (!rows.length) { document.getElementById('return-empty').style.display='block'; return; }
    var tbody = document.getElementById('return-tbody');
    if (tbody) tbody.innerHTML = rows.map(function(r){
      return '<tr><td>'+escapeHtml(r.lot||'')+'</td><td>'+escapeHtml(r.product||'')+'</td><td>'+(r.bags||r.qty||'')+'</td><td>'+escapeHtml(r.date||'')+'</td><td>'+escapeHtml(r.reason||'')+'</td></tr>';
    }).join('');
    document.getElementById('return-table').style.display = '';
  }

  /* ===================================================
     7f. PAGE: Move
     =================================================== */
  function loadMovePage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="move">',
      '<h2>Move - Inventory Relocation</h2>',
      '<div class="card" style="padding:20px;margin-bottom:16px">',
      '<h3 style="margin-bottom:12px">Execute Move</h3>',
      '<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">',
      '<input id="move-barcode" class="input" placeholder="Tonbag barcode" style="width:200px">',
      '<input id="move-dest" class="input" placeholder="Destination (e.g. A-3-2)" style="width:200px">',
      '<button class="btn btn-primary" onclick="window.executeMove()">Execute Move</button>',
      '</div></div>',
      '<div id="move-loading" style="padding:20px;text-align:center">Loading history...</div>',
      '<table class="data-table" id="move-table" style="display:none">',
      '<thead><tr><th>Date</th><th>LOT No</th><th>Type</th><th>Qty(MT)</th><th>From</th><th>To</th><th>By</th></tr></thead>',
      '<tbody id="move-tbody"></tbody></table>',
      '<div class="empty" id="move-empty" style="display:none">No movement history</div>',
      '</section>'
    ].join('');
    apiGet('/api/q/movement-history').then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      document.getElementById('move-loading').style.display = 'none';
      if (!rows.length) { document.getElementById('move-empty').style.display='block'; return; }
      var tbody = document.getElementById('move-tbody');
      if (tbody) tbody.innerHTML = rows.map(function(r){
        var qtyMT = r.qty_mt != null ? fmtN(r.qty_mt) : (r.qty_kg != null ? fmtN(r.qty_kg/1000) : '-');
        return '<tr>' +
          '<td class="mono-cell">'+escapeHtml(r.movement_date||r.moved_at||r.date||'')+'</td>' +
          '<td class="mono-cell" style="color:var(--accent)">'+escapeHtml(r.lot_no||r.sub_lt||r.barcode||'')+'</td>' +
          '<td>'+escapeHtml(r.movement_type||'')+'</td>' +
          '<td class="mono-cell" style="text-align:right">'+qtyMT+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.from_location||'-')+'</td>' +
          '<td class="mono-cell" style="color:var(--accent)">'+escapeHtml(r.to_location||'-')+'</td>' +
          '<td>'+escapeHtml(r.actor||r.moved_by||'system')+'</td></tr>';
      }).join('');
      document.getElementById('move-table').style.display = '';
    }).catch(function(){
      if (_currentRoute !== route) return;
      document.getElementById('move-loading').style.display = 'none';
      document.getElementById('move-empty').style.display = 'block';
    });
  }

  window.executeMove = function() {
    var barcode = (document.getElementById('move-barcode')||{}).value||'';
    var dest = (document.getElementById('move-dest')||{}).value||'';
    if (!barcode||!dest) { showToast('warning','Enter barcode and destination'); return; }
    apiPost('/api/action/inventory-move',{barcode:barcode,destination:dest})
      .then(function(){ showToast('success',barcode+' moved to '+dest); renderPage('move'); })
      .catch(function(e){
        if (e.status===501) showToast('info','Move (coming soon)');
        else showToast('error','Move failed: '+(e.message||String(e)));
      });
  };

  /* ===================================================
     7g. PAGE: Log
     =================================================== */
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
  }

  /* ===================================================
     7h. PAGE: Scan + PDF Upload
     =================================================== */
  function loadScanPage() {
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="scan">',
      '<h2>Scan - Barcode / PDF Inbound</h2>',
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">',

      '<!-- Barcode Panel -->',
      '<div class="card" style="padding:20px">',
      '<h3 style="margin-bottom:12px">Barcode Scan</h3>',
      '<input id="scan-input" class="input" placeholder="Scan or type barcode + Enter" style="width:100%;margin-bottom:12px">',
      '<div style="display:flex;gap:8px;margin-bottom:16px">',
      '<button class="btn btn-primary btn-sm" onclick="window.ScanActions.quickAction(\'inbound\')">Inbound</button>',
      '<button class="btn btn-warning btn-sm" onclick="window.ScanActions.quickAction(\'outbound\')">Outbound</button>',
      '<button class="btn btn-secondary btn-sm" onclick="window.ScanActions.quickAction(\'move\')">Move</button>',
      '</div>',
      '<table class="data-table"><thead><tr><th>Time</th><th>Barcode</th><th>Action</th><th>Result</th></tr></thead>',
      '<tbody id="scan-history-tbody"><tr><td colspan="4" style="text-align:center;padding:20px;color:var(--text-muted)">No scan history</td></tr></tbody></table>',
      '</div>',

      '<!-- PDF Panel -->',
      '<div class="card" style="padding:20px">',
      '<h3 style="margin-bottom:12px">PDF Inbound</h3>',
      '<div id="pdf-drop-zone" style="border:2px dashed var(--border);border-radius:8px;padding:40px;text-align:center;cursor:pointer;color:var(--text-muted)" onclick="document.getElementById(\'pdf-file-input\').click()" ondragover="event.preventDefault();this.style.borderColor=\'var(--accent)\'" ondragleave="this.style.borderColor=\'var(--border)\'" ondrop="window.PdfInbound.handleDrop(event)">',
      '<div style="font-size:2rem">&#x1F4C4;</div>',
      '<div style="margin-top:8px">Drag PDF here or click to select</div>',
      '<div style="font-size:0.8rem;margin-top:4px;color:var(--text-muted)">Picking List / BL / Inbound PDF</div>',
      '</div>',
      '<input type="file" id="pdf-file-input" accept=".pdf" style="display:none" onchange="window.PdfInbound.handleFile(this.files[0])">',
      '<div id="pdf-status" style="margin-top:12px;color:var(--text-muted);font-size:0.9rem"></div>',
      '<button class="btn btn-primary" id="pdf-upload-btn" style="display:none;margin-top:8px" onclick="window.PdfInbound.upload()">Upload &amp; Process</button>',
      '</div>',

      '</div></section>'
    ].join('');

    var inp = document.getElementById('scan-input');
    if (inp) {
      inp.addEventListener('keydown', function(e){
        if (e.key==='Enter') {
          e.preventDefault();
          window.ScanActions.processBarcode(inp.value.trim());
          inp.value='';
        }
      });
      inp.focus();
    }
  }

  var _scanHistory = [];
  window.ScanActions = {
    _lastBarcode: '',
    processBarcode: function(barcode, action) {
      if (!barcode) return;
      window.ScanActions._lastBarcode = barcode;
      if (!action) { showToast('info','Scanned: '+barcode+' - select action button'); return; }
      apiPost('/api/scan/process',{barcode:barcode,action:action})
        .then(function(res){
          var ok = res.success !== false;
          showToast(ok?'success':'error', res.message||(ok?'Done':'Failed'));
          window.ScanActions._addHist(barcode, action, ok);
        })
        .catch(function(e){
          if (e.status===501) showToast('info','Scan (coming soon)');
          else showToast('error','Scan error: '+(e.message||String(e)));
          window.ScanActions._addHist(barcode, action, false);
        });
    },
    quickAction: function(action) {
      var inp = document.getElementById('scan-input');
      var bc = (inp?inp.value.trim():'')||window.ScanActions._lastBarcode;
      if (!bc) { showToast('warning','Scan barcode first'); return; }
      window.ScanActions.processBarcode(bc, action);
      if (inp) inp.value='';
    },
    _addHist: function(barcode, action, ok) {
      var now = new Date();
      var t = [now.getHours(),now.getMinutes(),now.getSeconds()].map(function(n){return String(n).padStart(2,'0');}).join(':');
      _scanHistory.unshift({time:t,barcode:barcode,action:action,ok:ok});
      if (_scanHistory.length>100) _scanHistory.pop();
      var tbody = document.getElementById('scan-history-tbody');
      if (tbody) tbody.innerHTML = _scanHistory.slice(0,20).map(function(h){
        return '<tr><td class="mono-cell">'+h.time+'</td><td class="mono-cell">'+escapeHtml(h.barcode)+'</td><td>'+escapeHtml(h.action)+'</td><td>'+(h.ok?'<span style="color:var(--status-available)">OK</span>':'<span style="color:var(--status-return)">FAIL</span>')+'</td></tr>';
      }).join('');
    }
  };

  var _pdfFile=null, _pdfB64=null;
  window.PdfInbound = {
    handleDrop: function(e) {
      e.preventDefault();
      var dz = document.getElementById('pdf-drop-zone');
      if (dz) dz.style.borderColor='var(--border)';
      var f = e.dataTransfer.files[0];
      if (f) window.PdfInbound.handleFile(f);
    },
    handleFile: function(f) {
      if (!f||!f.name.toLowerCase().endsWith('.pdf')) { showToast('error','PDF files only'); return; }
      _pdfFile = f;
      var status=document.getElementById('pdf-status');
      var btn=document.getElementById('pdf-upload-btn');
      if (status) status.textContent='Selected: '+f.name+' ('+(f.size/1024).toFixed(1)+' KB)';
      var reader=new FileReader();
      reader.onload=function(ev){ _pdfB64=ev.target.result.split(',')[1]; if(btn) btn.style.display=''; };
      reader.readAsDataURL(f);
    },
    upload: function() {
      if (!_pdfB64) { showToast('warning','Select a PDF first'); return; }
      var status=document.getElementById('pdf-status');
      var btn=document.getElementById('pdf-upload-btn');
      if (status) status.textContent='Uploading...';
      if (btn) btn.disabled=true;
      apiPost('/api/inbound/pdf',{pdf_base64:_pdfB64,filename:(_pdfFile?_pdfFile.name:'upload.pdf')})
        .then(function(res){
          if (res.data && res.data.ai_provider_used === 'openai') {
            showToast('warning', '⚠️ Gemini 한도 초과 → OpenAI 전환됨');
          }
          showToast('success','PDF inbound done: '+(res.message||'OK'));
          if (status) status.textContent='Done: '+(res.message||'Success');
          if (btn) { btn.style.display='none'; btn.disabled=false; }
          _pdfB64=null; _pdfFile=null;
        })
        .catch(function(e){
          if (e.status===501) showToast('info','PDF inbound (coming soon)');
          else showToast('error','Upload failed: '+(e.message||String(e)));
          if (status) status.textContent='Failed: '+(e.message||String(e));
          if (btn) btn.disabled=false;
        });
    }
  };

  /* ===================================================
     7i. PAGE: Tonbag
     =================================================== */
  function loadTonbagPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="tonbag">',
      '<h2>Tonbag List</h2>',
      '<div class="toolbar-mini"><button class="btn btn-secondary" onclick="renderPage(\'tonbag\')">Refresh</button></div>',
      '<div id="tonbag-loading" style="padding:40px;text-align:center">Loading...</div>',
      '<table class="data-table" id="tonbag-table" style="display:none">',
      '<thead><tr><th>Tonbag ID</th><th>LOT</th><th>Product</th><th>Status</th><th>Weight(MT)</th><th>Location</th><th>Container</th><th></th></tr></thead>',
      '<tbody id="tonbag-tbody"></tbody></table>',
      '<div class="empty" id="tonbag-empty" style="display:none">No tonbag data</div>',
      '</section>'
    ].join('');
    apiGet('/api/tonbags').then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      document.getElementById('tonbag-loading').style.display='none';
      if (!rows.length) { document.getElementById('tonbag-empty').style.display='block'; return; }
      var tbody=document.getElementById('tonbag-tbody');
      if (tbody) tbody.innerHTML=rows.map(function(r){
        return '<tr>' +
          '<td class="mono-cell">'+escapeHtml(r.sub_lt||r.tonbag_id||'-')+'</td>' +
          '<td class="mono-cell" style="color:var(--accent)">'+escapeHtml(r.lot_no||'-')+'</td>' +
          '<td><span class="tag">'+escapeHtml(r.product||'-')+'</span></td>' +
          '<td>'+escapeHtml(r.status||'-')+'</td>' +
          '<td class="mono-cell">'+(r.weight!=null?Number(r.weight).toLocaleString():'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.location||'-')+'</td>' +
          '<td class="mono-cell">'+escapeHtml(r.container||'-')+'</td>' +
          '<td><button class="btn btn-ghost btn-xs">Detail</button></td></tr>';
      }).join('');
      document.getElementById('tonbag-table').style.display='';
    }).catch(function(){
      if (_currentRoute !== route) return;
      document.getElementById('tonbag-loading').style.display='none';
      document.getElementById('tonbag-empty').style.display='block';
    });
  }

  /* ===================================================
     8. MODAL — 드래그/리사이즈 지원 (2026-04-27)
     =================================================== */
  var _zFloatTop = 10100;
function _bringToFront(el) { el.style.zIndex = ++_zFloatTop; }

  function _makeDraggableResizable(el, dragBar) {
    var drag = {on:false, sx:0, sy:0, ox:0, oy:0};
    dragBar.style.cursor = 'move';
    el.addEventListener('mousedown', function(){ _bringToFront(el); });
    dragBar.addEventListener('mousedown', function(e){
      if (e.target.tagName === 'BUTTON') return;
      drag.on = true;
      drag.sx = e.clientX; drag.sy = e.clientY;
      var r = el.getBoundingClientRect();
      drag.ox = r.left; drag.oy = r.top;
      el.style.transform = 'none';
      el.style.left = drag.ox + 'px'; el.style.top = drag.oy + 'px';
      e.preventDefault();
    });
    document.addEventListener('mousemove', function(e){
      if (!drag.on) return;
      el.style.left = Math.max(0, drag.ox + (e.clientX - drag.sx)) + 'px';
      el.style.top  = Math.max(0, drag.oy + (e.clientY - drag.sy)) + 'px';
    });
    document.addEventListener('mouseup', function(){ drag.on = false; });
    ['n','s','e','w','ne','nw','se','sw'].forEach(function(d){
      var h = document.createElement('div');
      h.className = 'sqm-rh sqm-rh-' + d;
      el.appendChild(h);
      var res = {on:false, sx:0, sy:0, ow:0, oh:0, ox:0, oy:0};
      h.addEventListener('mousedown', function(e){
        res.on=true; res.sx=e.clientX; res.sy=e.clientY;
        var r=el.getBoundingClientRect();
        res.ow=r.width; res.oh=r.height; res.ox=r.left; res.oy=r.top;
        el.style.transform='none';
        el.style.left=res.ox+'px'; el.style.top=res.oy+'px';
        e.preventDefault(); e.stopPropagation();
      });
      document.addEventListener('mousemove', function(e){
        if (!res.on) return;
        var dx=e.clientX-res.sx, dy=e.clientY-res.sy;
        var nw=res.ow, nh=res.oh, nx=res.ox, ny=res.oy;
        if (d.indexOf('e')!==-1)  nw=Math.max(400,res.ow+dx);
        if (d.indexOf('s')!==-1)  nh=Math.max(200,res.oh+dy);
        if (d.indexOf('w')!==-1){ nw=Math.max(400,res.ow-dx); nx=res.ox+(res.ow-nw); }
        if (d.indexOf('n')!==-1){ nh=Math.max(200,res.oh-dy); ny=res.oy+(res.oh-nh); }
        el.style.width=nw+'px'; el.style.height=nh+'px';
        el.style.left=nx+'px';  el.style.top=ny+'px';
      });
      document.addEventListener('mouseup', function(){ res.on=false; });
    });
  }

  function ensureModal() {
    var m=document.getElementById('sqm-modal');
    if (m) return m;
    m=document.createElement('div');
    m.id='sqm-modal';
    m.style.cssText='display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;';
    m.innerHTML='<div id="sqm-modal-inner" style="background:var(--bg-card);border-radius:8px;width:min(1280px,92vw);max-width:92vw;min-height:200px;max-height:88vh;position:fixed;top:65px;left:50%;transform:translateX(-50%);overflow:visible;display:flex;flex-direction:column;">'
      +'<div id="sqm-modal-header" onmousedown="(function(){var mi=document.getElementById(\'sqm-modal-inner\');if(mi)mi.style.zIndex=++_zFloatTop;})()" style="flex-shrink:0;cursor:move;user-select:none;background:var(--bg-hover,rgba(0,0,0,.06));border-radius:8px 8px 0 0;border-bottom:1px solid var(--panel-border);padding:5px 48px 5px 12px;font-size:11px;color:var(--text-muted);display:flex;align-items:center;gap:6px;min-height:28px;position:relative;">'
      +'<span style="opacity:.4;font-size:10px"></span>'
      +'<button onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'" style="position:absolute;top:3px;right:10px;background:none;border:none;font-size:1.4rem;cursor:pointer;color:var(--text-muted);">&#x2715;</button>'
      +'</div>'
      +'<div id="sqm-modal-content" style="flex:1 1 auto;overflow:auto;padding:16px 20px;min-height:100px;"></div>'
      +'</div>';
    document.body.appendChild(m);
    _makeDraggableResizable(
      document.getElementById('sqm-modal-inner'),
      document.getElementById('sqm-modal-header')
    );
    return m;
  }

  function showDataModal(title, html) {
    ensureModal().style.display='block';
    document.getElementById('sqm-modal-content').innerHTML='<h2 style="margin-bottom:16px">'+escapeHtml(title)+'</h2>'+html;
  }

  /* ===================================================
     8b. Excel 업로드 모달 — Phase 4-B 공통 유틸
     (수동 입고 / 반품 입고 공용 — endpoint + title 만 다름)
     =================================================== */
  function _showExcelUploadModal(opts) {
    // opts: { title, subtitle, endpoint, onSuccess(data), columnsHint }
    var html = [
      '<div style="max-width:640px">',
      '  <h2 style="margin:0 0 12px 0">' + escapeHtml(opts.title) + '</h2>',
      '  <p style="color:var(--text-muted);margin:0 0 16px 0;font-size:.9rem">',
      '    ' + opts.subtitle,
      '  </p>',
      '  <div id="xls-drop-zone" style="border:2px dashed var(--border);border-radius:8px;padding:32px 16px;text-align:center;background:var(--bg-hover);cursor:pointer;margin-bottom:16px">',
      '    <div style="font-size:2.5rem;margin-bottom:8px">📁</div>',
      '    <div id="xls-file-name" style="color:var(--text-muted)">클릭 또는 파일을 여기에 드롭하세요</div>',
      '  </div>',
      '  <input type="file" id="xls-file-input" accept=".xlsx,.xls" style="display:none">',
      '  <div id="xls-progress" style="display:none;margin-bottom:16px">',
      '    <div style="background:var(--bg-hover);border-radius:4px;height:8px;overflow:hidden">',
      '      <div id="xls-progress-bar" style="background:var(--accent);height:100%;width:0%;transition:width .3s"></div>',
      '    </div>',
      '    <div id="xls-progress-text" style="font-size:.85rem;color:var(--text-muted);margin-top:4px">준비 중...</div>',
      '  </div>',
      '  <div id="xls-result" style="margin-bottom:16px"></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button id="xls-cancel-btn" class="btn btn-ghost">닫기</button>',
      '    <button id="xls-upload-btn" class="btn btn-primary" disabled>업로드</button>',
      '  </div>',
      '</div>'
    ].join('\n');

    showDataModal('', html);

    var fileInput = document.getElementById('xls-file-input');
    var dropZone  = document.getElementById('xls-drop-zone');
    var fileName  = document.getElementById('xls-file-name');
    var uploadBtn = document.getElementById('xls-upload-btn');
    var cancelBtn = document.getElementById('xls-cancel-btn');
    var progress  = document.getElementById('xls-progress');
    var progressBar = document.getElementById('xls-progress-bar');
    var progressText = document.getElementById('xls-progress-text');
    var resultBox = document.getElementById('xls-result');
    var selectedFile = null;

    function setFile(f) {
      if (!f) return;
      if (!/\.(xlsx|xls)$/i.test(f.name)) {
        showToast('error', 'Excel 파일(.xlsx/.xls)만 가능합니다: ' + f.name);
        return;
      }
      selectedFile = f;
      fileName.innerHTML = '✅ <strong>' + escapeHtml(f.name) + '</strong> (' + Math.round(f.size/1024) + ' KB)';
      uploadBtn.disabled = false;
    }

    dropZone.addEventListener('click', function(){ fileInput.click(); });
    fileInput.addEventListener('change', function(e){
      if (e.target.files && e.target.files[0]) setFile(e.target.files[0]);
    });
    dropZone.addEventListener('dragover', function(e){ e.preventDefault(); dropZone.style.background='var(--bg-active)'; });
    dropZone.addEventListener('dragleave', function(){ dropZone.style.background='var(--bg-hover)'; });
    dropZone.addEventListener('drop', function(e){
      e.preventDefault();
      dropZone.style.background='var(--bg-hover)';
      if (e.dataTransfer.files && e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
    });
    cancelBtn.addEventListener('click', function(){
      document.getElementById('sqm-modal').style.display = 'none';
    });

    uploadBtn.addEventListener('click', function(){
      if (!selectedFile) return;
      uploadBtn.disabled = true;
      cancelBtn.disabled = true;
      progress.style.display = 'block';
      progressBar.style.width = '10%';
      progressText.textContent = '업로드 중...';
      resultBox.innerHTML = '';

      var form = new FormData();
      form.append('file', selectedFile, selectedFile.name);

      var xhr = new XMLHttpRequest();
      xhr.open('POST', API + opts.endpoint);
      xhr.upload.onprogress = function(e){
        if (e.lengthComputable) {
          var pct = Math.round((e.loaded / e.total) * 70) + 10;
          progressBar.style.width = pct + '%';
          progressText.textContent = '업로드 중... ' + pct + '%';
        }
      };
      xhr.onload = function(){
        progressBar.style.width = '100%';
        cancelBtn.disabled = false;
        var body;
        try { body = JSON.parse(xhr.responseText); } catch(e){ body = null; }
        if (xhr.status >= 200 && xhr.status < 300 && body && body.ok) {
          progressText.textContent = body.message || '완료';
          var extraHtml = opts.onSuccess ? opts.onSuccess(body.data || {}) : '';
          resultBox.innerHTML =
            '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--success)">' +
            '<div style="font-weight:600;margin-bottom:4px">✅ ' + escapeHtml(body.message||'완료') + '</div>' +
            (extraHtml || '') +
            '</div>';
          showToast('success', body.message || '완료');
          dbgLog('🟢','XLS-UPLOAD OK', opts.endpoint + ' — ' + (body.message||''), '#66bb6a');
          if (_currentRoute === 'inventory' && typeof loadInventoryPage === 'function') loadInventoryPage();
          if (typeof loadKpi === 'function') loadKpi();
        } else {
          var errMsg = (body && (body.detail || body.error || body.message)) || ('HTTP ' + xhr.status);
          if (typeof errMsg === 'object') errMsg = JSON.stringify(errMsg);
          progressText.textContent = '실패';
          progressBar.style.background = 'var(--danger)';
          var errExtra = '';
          if (body && body.data && body.data.errors) {
            errExtra = '<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--warning)">⚠️ 실패 상세</summary><pre style="white-space:pre-wrap;font-size:.85rem;margin-top:8px">' +
              escapeHtml(JSON.stringify(body.data.errors, null, 2)) + '</pre></details>';
          }
          resultBox.innerHTML =
            '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--danger)">' +
            '<div style="font-weight:600">❌ 업로드 실패</div>' +
            '<div style="color:var(--text-muted);font-size:.85rem;margin-top:4px">' + escapeHtml(String(errMsg)) + '</div>' +
            errExtra +
            '</div>';
          showToast('error', '실패: ' + errMsg);
          dbgLog('🔴','XLS-UPLOAD FAIL', opts.endpoint + ' — ' + String(errMsg), '#ef5350');
          uploadBtn.disabled = false;
        }
      };
      xhr.onerror = function(){
        progressText.textContent = '네트워크 에러';
        progressBar.style.background = 'var(--danger)';
        resultBox.innerHTML = '<div style="padding:12px;color:var(--danger)">네트워크 에러 — API 서버를 확인하세요</div>';
        showToast('error', '네트워크 에러');
        uploadBtn.disabled = false;
        cancelBtn.disabled = false;
      };
      xhr.send(form);
    });
  }

  /* 수동 입고 (F002) */
  function showInboundManualUploadModal() {
    _showExcelUploadModal({
      title: '📊 수동 입고 — Excel 업로드',
      subtitle: '엑셀 파일(.xlsx/.xls)을 선택하세요. 컬럼: <code>lot_no, sap_no, bl_no, container_no, product, net_weight, stock_date</code> 등',
      endpoint: '/api/inbound/bulk-import-excel',
      onSuccess: function(d) {
        var errHtml = '';
        if (d.errors && d.errors.length) {
          errHtml = '<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--warning)">⚠️ ' + d.errors.length + '건 실패 상세</summary><table class="data-table" style="margin-top:8px;font-size:.85rem"><thead><tr><th>행</th><th>LOT</th><th>사유</th></tr></thead><tbody>' +
            d.errors.map(function(er){
              return '<tr><td>'+er.row+'</td><td>'+escapeHtml(er.lot_no||'-')+'</td><td>'+escapeHtml(er.reason||'')+'</td></tr>';
            }).join('') + '</tbody></table></details>';
        }
        return '<div style="color:var(--text-muted);font-size:.85rem">파일: ' + escapeHtml(d.filename||'-') +
               ' · 성공 ' + (d.success_count||0) + ' / 실패 ' + (d.fail_count||0) + ' / 총 ' + (d.total||0) +
               ' · 매핑: ' + ((d.matched_columns||[]).join(', ')) + '</div>' + errHtml;
      }
    });
  }
  window.showInboundManualUploadModal = showInboundManualUploadModal;

  /* 반품 입고 (F007) */
  function showReturnInboundUploadModal() {
    _showExcelUploadModal({
      title: '🔄 반품 입고 — Excel 업로드',
      subtitle: '반품 Excel 파일을 선택하세요. 기존 PICKING 데이터와 자동 매칭되어 재고로 복구됩니다.',
      endpoint: '/api/inbound/return-excel',
      onSuccess: function(d) {
        var detailHtml = '';
        if (d.details && d.details.length) {
          detailHtml = '<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--text-muted)">📋 처리 상세 (' + d.details.length + '건)</summary><pre style="white-space:pre-wrap;font-size:.8rem;margin-top:8px;max-height:240px;overflow:auto">' +
            escapeHtml(JSON.stringify(d.details.slice(0,50), null, 2)) + '</pre></details>';
        }
        return '<div style="color:var(--text-muted);font-size:.85rem">파일: ' + escapeHtml(d.filename||'-') +
               ' · <strong style="color:var(--accent)">' + (d.returned||0) + '건</strong> 반품 복구</div>' + detailHtml;
      }
    });
  }
  window.showReturnInboundUploadModal = showReturnInboundUploadModal;

  /* Allocation 입력 (F014) — 출고 예약 Excel 업로드 */
  function showAllocationUploadModal() {
    _showExcelUploadModal({
      title: '📍 Allocation 입력 — Excel 업로드',
      subtitle: 'Allocation Excel 파일을 선택하세요. 컬럼: <code>lot_no, sold_to, sale_ref, qty_mt, outbound_date, sublot_count</code>',
      endpoint: '/api/allocation/bulk-import-excel',
      onSuccess: function(d) {
        var warnHtml = '';
        if (d.errors && d.errors.length) {
          warnHtml = '<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--warning)">⚠️ 경고 ' + d.errors.length + '건</summary><pre style="white-space:pre-wrap;font-size:.8rem;margin-top:8px;max-height:200px;overflow:auto">' +
            escapeHtml(d.errors.join('\n')) + '</pre></details>';
        }
        var detailHtml = '';
        if (d.error_details && d.error_details.length) {
          detailHtml = '<details style="margin-top:4px"><summary style="cursor:pointer;color:var(--text-muted)">상세 (' + d.error_details.length + '건)</summary><pre style="white-space:pre-wrap;font-size:.8rem;margin-top:8px;max-height:200px;overflow:auto">' +
            escapeHtml(JSON.stringify(d.error_details, null, 2)) + '</pre></details>';
        }
        return '<div style="color:var(--text-muted);font-size:.85rem">파일: ' + escapeHtml(d.filename||'-') +
               ' · <strong style="color:var(--accent)">' + (d.reserved||0) + '건</strong> 예약 / 총 ' + (d.total_rows||0) + '행 · 매핑: ' + ((d.matched_columns||[]).join(', ')) +
               '</div>' + warnHtml + detailHtml;
      }
    });
  }
  window.showAllocationUploadModal = showAllocationUploadModal;

  /* ===================================================
     8c. 즉시 출고 (F015) — 폼 기반 네이티브 구현
     엔진 quick_outbound(lot_no, count, customer, reason, operator) 직접 호출
     =================================================== */
  /* =====================================================================
     [Sprint 1-3] OneStop Outbound Dialog — 4탭 state machine
     ─────────────────────────────────────────────────────────────────────
     v864-2 source: gui_app_modular/dialogs/onestop_outbound.py (2304 lines)
     State machine: DRAFT → WAIT_SCAN → (FINALIZED | REVIEW | ERROR)

     Phase A (this commit): 4탭 UI 뼈대 + Tab 1 입력 + 상태바 + 파싱 DRAFT 전환
     Phase B: Tab 2 톤백 선택 (nested per-LOT Treeview)
     Phase C: Tab 3 스캔 검증 (OUT 스캔 upload + 검증 엔진)
     Phase D: Tab 4 완료 + 감사 로그 sub-popup
     Phase E: proof docs 저장소 + 90일 자동 정리
     ===================================================================== */
  var _ooState = {
    state: 'DRAFT',         /* DRAFT | WAIT_SCAN | FINALIZED | REVIEW | ERROR */
    currentTab: 1,          /* 1 ~ 4 */
    proofDocs: [],          /* 근거문서 multi-file */
    customer: '',
    saleRef: '',
    lotNo: '',
    pasteText: '',
    manualActuals: {},      /* {lot_no: {expected_kg, actual_kg}} */
    parsedItems: [],        /* 파싱된 출고 아이템 */
    /* [Sprint 1-3-B] Tab 2 톤백 선택 */
    lotsWithTonbags: {},    /* { lot_no: [{sub_lt, weight, status, location, ...}, ...] } */
    selectedTonbags: null,  /* Set<"lot.sub_lt"> */
    expandedLots: null,     /* Set<lot_no> */
    /* [Sprint 1-3-C] Tab 3 OUT 스캔 검증 */
    scanFile: null,         /* 업로드한 파일 객체 */
    scanRows: [],           /* [{tonbag_uid, actual_kg}, ...] - 백엔드 파싱 결과 */
    manualScans: [],        /* 수동 입력 [{tonbag_uid, actual_kg}, ...] */
    validationResults: [],  /* [{tonbag_uid, lot_no, expected_kg, actual_kg, diff_pct, level: ok|warn|stop, message}] */
    completedItems: [],
  };

  function _ooReset() {
    _ooState.state = 'DRAFT';
    _ooState.currentTab = 1;
    _ooState.proofDocs = [];
    _ooState.customer = '';
    _ooState.saleRef = '';
    _ooState.lotNo = '';
    _ooState.pasteText = '';
    _ooState.manualActuals = {};
    _ooState.parsedItems = [];
    _ooState.lotsWithTonbags = {};
    _ooState.selectedTonbags = new Set();
    _ooState.expandedLots = new Set();
    _ooState.scanFile = null;
    _ooState.scanRows = [];
    _ooState.manualScans = [];
    _ooState.validationResults = [];
    _ooState.completedItems = [];
  }

  function showOneStopOutboundModal() {
    _ooReset();

    var html = [
      '<div class="oo-modal">',
      '  <h2>🚀 S1 원스톱 출고 <span style="font-size:12px;font-weight:400;color:var(--text-muted)">— v864.3 (Sprint 1-3)</span></h2>',
      /* 상태바 */
      '  <div class="oo-statusbar">',
      '    <span style="font-weight:700;color:var(--text-muted);font-size:12px">상태:</span>',
      '    <span id="oo-status-badge" class="oo-status-badge draft">● DRAFT</span>',
      '    <div class="oo-status-progress">',
      '      <span id="oo-dot-draft"  class="oo-status-dot active"></span><span>DRAFT</span>',
      '      <span>→</span>',
      '      <span id="oo-dot-scan"   class="oo-status-dot"></span><span>WAIT_SCAN</span>',
      '      <span>→</span>',
      '      <span id="oo-dot-final"  class="oo-status-dot"></span><span>FINALIZED</span>',
      '    </div>',
      '    <span id="oo-status-hint" style="font-size:11px;color:var(--text-muted)">Tab 1 에서 입력 후 ▶ 파싱</span>',
      '  </div>',
      /* 탭 헤더 */
      '  <div class="oo-tab-headers">',
      '    <button class="oo-tab-header active" data-tab="1" onclick="window.ooSwitchTab(1)">',
      '      <span class="oo-tab-header-num">①</span><span>입력 (붙여넣기)</span>',
      '    </button>',
      '    <button class="oo-tab-header" data-tab="2" onclick="window.ooSwitchTab(2)" disabled title="DRAFT 상태에서 활성화">',
      '      <span class="oo-tab-header-num">②</span><span>톤백 선택</span>',
      '    </button>',
      '    <button class="oo-tab-header" data-tab="3" onclick="window.ooSwitchTab(3)" disabled title="WAIT_SCAN 상태에서 활성화">',
      '      <span class="oo-tab-header-num">③</span><span>스캔 검증</span>',
      '    </button>',
      '    <button class="oo-tab-header" data-tab="4" onclick="window.ooSwitchTab(4)" disabled title="완료 시 활성화">',
      '      <span class="oo-tab-header-num">④</span><span>완료</span>',
      '    </button>',
      '  </div>',
      /* 탭 본문 */
      '  <div class="oo-tab-body">',
      /* --- Tab 1: 입력 --- */
      '    <div class="oo-tab-pane active" data-pane="1">',
      /* 근거문서 섹션 */
      '      <div class="oo-section">',
      '        <div class="oo-section-title">📎 근거문서 (Proof Documents)</div>',
      '        <input type="file" id="oo-proof-input" multiple style="display:none" onchange="window.ooAddProofFiles(this.files)">',
      '        <button class="btn" onclick="document.getElementById(\'oo-proof-input\').click()">+ 파일 첨부</button>',
      '        <div id="oo-proof-files" class="oo-files-list"></div>',
      '        <div style="font-size:11px;color:var(--text-muted);margin-top:6px">💡 출고 근거 서류(PDF/이미지/Excel). 완료 후 data/proof_docs/YYYY-MM-DD/ 에 저장 예정 (Phase E)</div>',
      '      </div>',
      /* 고객사/Sale Ref/LOT */
      '      <div class="oo-section">',
      '        <div class="oo-section-title">🏢 고객사 · Sale Ref · LOT</div>',
      '        <div class="oo-input-grid">',
      '          <label>고객사:</label><input type="text" id="oo-customer" placeholder="예: ACME Corp" onchange="_ooState.customer=this.value">',
      '          <label>Sale Ref:</label><input type="text" id="oo-sale-ref" placeholder="예: SO-2026-0420" onchange="_ooState.saleRef=this.value">',
      '          <label>LOT NO:</label><input type="text" id="oo-lot" placeholder="예: 1126013063" style="font-family:Consolas,monospace" onchange="_ooState.lotNo=this.value">',
      '          <label>출고일:</label><input type="date" id="oo-date">',
      '        </div>',
      '        <div style="font-size:11px;color:var(--text-muted);margin-top:4px">빠른 선택 단축키 (Sprint 2): 🔄 고객사 목록 새로고침</div>',
      '      </div>',
      /* 수동 실제수량 */
      '      <div class="oo-section">',
      '        <div class="oo-section-title">✏️ 수동 실제수량 입력 (선택)</div>',
      '        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px">',
      '          <label>LOT:</label><input type="text" id="oo-manual-lot" placeholder="LOT NO" style="padding:4px 8px;background:var(--bg-hover);border:1px solid var(--panel-border);border-radius:3px;font-family:Consolas,monospace">',
      '          <label>실제(kg):</label><input type="number" id="oo-manual-actual" step="0.01" placeholder="예: 5001.25" style="padding:4px 8px;background:var(--bg-hover);border:1px solid var(--panel-border);border-radius:3px;width:100px">',
      '          <button class="btn" onclick="window.ooAddManualActual()">적용</button>',
      '          <span id="oo-manual-list" style="color:var(--text-muted);font-size:11px"></span>',
      '        </div>',
      '        <div style="font-size:11px;color:var(--text-muted);margin-top:4px">💡 계측 오차 있는 LOT 은 수동 값으로 덮어씀. actual &gt; expected 는 ⛔ 하드스톱</div>',
      '      </div>',
      /* Paste 영역 */
      '      <div class="oo-section">',
      '        <div class="oo-section-title">📋 붙여넣기 입력</div>',
      '        <textarea id="oo-paste" class="oo-paste-textarea" placeholder="Excel/CSV 에서 복사한 LOT 정보를 여기에 붙여넣으세요\n예:&#10;LOT_NO\tSAP_NO\tQTY(kg)\tCUSTOMER\tSALE_REF\n1126013063\t2200034449\t5000\tACME\tSO-2026-0420"></textarea>',
      '        <div style="display:flex;gap:8px;margin-top:8px">',
      '          <button class="btn" onclick="window.ooInsertSample()">📝 샘플 삽입</button>',
      '          <button class="btn btn-primary" id="oo-parse-btn" onclick="window.ooParseDraft()">🔄 파싱 → DRAFT ▶</button>',
      '          <button class="btn" onclick="window.ooClearPaste()">🧹 지우기</button>',
      '          <span id="oo-parse-hint" style="margin-left:auto;color:var(--text-muted);font-size:11px;align-self:center">고객사 + LOT 또는 붙여넣기 내용 필요</span>',
      '        </div>',
      '      </div>',
      /* 파싱 결과 */
      '      <div id="oo-draft-result" style="margin-top:10px"></div>',
      '    </div>',
      /* --- Tab 2: 톤백 선택 (Sprint 1-3-B 실구현) --- */
      '    <div class="oo-tab-pane" data-pane="2">',
      /* 통계 */
      '      <div class="oo-section">',
      '        <div class="oo-section-title">📊 선택 요약</div>',
      '        <div id="oo-t2-stats" style="font-size:13px;color:var(--text-muted)">DRAFT 진입 전 — Tab 1 에서 ▶ 파싱을 먼저 실행하세요</div>',
      '      </div>',
      /* 액션 버튼 */
      '      <div class="oo-section">',
      '        <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">',
      '          <button class="btn" onclick="window.ooRandomSelect()" title="가용 톤백 중 무작위 선택">🎲 랜덤 선택</button>',
      '          <button class="btn" onclick="window.ooSelectAllLots()">✅ 전체 LOT 전체</button>',
      '          <button class="btn" onclick="window.ooDeselectAll()">☐ 전체 해제</button>',
      '          <button class="btn" onclick="window.ooExpandAll(true)">▼ 모두 펼침</button>',
      '          <button class="btn" onclick="window.ooExpandAll(false)">▶ 모두 접기</button>',
      '          <button class="btn btn-primary" id="oo-goto-scan-btn" onclick="window.ooMoveToScan()" disabled style="margin-left:auto" title="DRAFT → WAIT_SCAN">DRAFT → WAIT_SCAN ▶</button>',
      '        </div>',
      '      </div>',
      /* 톤백 리스트 */
      '      <div class="oo-section">',
      '        <div class="oo-section-title">📦 LOT별 가용 톤백</div>',
      '        <div id="oo-tonbags-body" style="max-height:360px;overflow-y:auto">',
      '          <div style="padding:30px;text-align:center;color:var(--text-muted);font-size:12px">⏳ DRAFT 진입 시 자동 로드됩니다</div>',
      '        </div>',
      '      </div>',
      '    </div>',
      /* --- Tab 3: 스캔 검증 (Sprint 1-3-C 실구현) --- */
      '    <div class="oo-tab-pane" data-pane="3">',
      /* 통계 */
      '      <div class="oo-section">',
      '        <div class="oo-section-title">📊 검증 요약</div>',
      '        <div id="oo-t3-stats" style="font-size:13px;color:var(--text-muted)">Tab 2 에서 톤백을 선택해야 검증 가능</div>',
      '      </div>',
      /* 파일 업로드 + 수동 입력 */
      '      <div class="oo-section">',
      '        <div class="oo-section-title">📊 OUT 스캔 파일 업로드</div>',
      '        <input type="file" id="oo-scan-input" accept=".csv,.xlsx,.xls" style="display:none" onchange="window.ooHandleScanFile(this.files[0])">',
      '        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">',
      '          <button class="btn btn-primary" onclick="document.getElementById(\'oo-scan-input\').click()">📂 파일 선택 (csv/xlsx)</button>',
      '          <span id="oo-scan-filename" style="font-family:Consolas,monospace;font-size:11px;color:var(--text-muted)">선택된 파일 없음</span>',
      '          <button class="btn" onclick="window.ooClearScan()" style="margin-left:auto">🧹 초기화</button>',
      '        </div>',
      '        <div style="margin-top:6px;font-size:11px;color:var(--text-muted)">💡 컬럼 자동 인식: <code>tonbag_uid</code>(또는 sub_lt/id) + <code>actual_kg</code>(또는 weight/net_kg)</div>',
      '      </div>',
      /* 수동 입력 */
      '      <div class="oo-section">',
      '        <div class="oo-section-title">✏️ 수동 입력 (선택)</div>',
      '        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px">',
      '          <label>톤백 ID:</label><input type="text" id="oo-scan-uid" placeholder="T-1234" style="padding:4px 8px;background:var(--bg-hover);border:1px solid var(--panel-border);border-radius:3px;font-family:Consolas,monospace">',
      '          <label>실제(kg):</label><input type="number" id="oo-scan-actual" step="0.01" placeholder="1001.25" style="padding:4px 8px;background:var(--bg-hover);border:1px solid var(--panel-border);border-radius:3px;width:110px">',
      '          <button class="btn" onclick="window.ooAddManualScan()">➕ 추가</button>',
      '        </div>',
      '      </div>',
      /* 검증 실행 */
      '      <div class="oo-section">',
      '        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">',
      '          <button class="btn btn-primary" onclick="window.ooRunValidation()">⚡ 전체 검증 실행</button>',
      '          <span id="oo-validation-hint" style="color:var(--text-muted);font-size:11px">스캔 데이터를 먼저 업로드/입력</span>',
      '          <button class="btn btn-primary" id="oo-goto-finalize-btn" onclick="window.ooMoveToFinalize()" disabled style="margin-left:auto" title="WAIT_SCAN → FINALIZED">WAIT_SCAN → FINALIZED ▶</button>',
      '        </div>',
      '      </div>',
      /* 검증 결과 */
      '      <div class="oo-section">',
      '        <div class="oo-section-title">📋 검증 결과</div>',
      '        <div id="oo-validation-results" style="max-height:280px;overflow-y:auto">',
      '          <div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px">⚡ "전체 검증 실행" 버튼을 눌러 결과를 확인하세요</div>',
      '        </div>',
      '      </div>',
      '    </div>',
      /* --- Tab 4: 완료 (Phase D placeholder) --- */
      '    <div class="oo-tab-pane" data-pane="4">',
      '      <div class="oo-tab-placeholder">',
      '        <div class="icon">✅</div>',
      '        <div style="font-weight:700;margin-top:12px">④ 완료</div>',
      '        <div style="margin-top:6px">Tab 3 검증 통과 후 활성화됩니다.</div>',
      '        <div class="phase">Sprint 1-3 Phase D 예정</div>',
      '        <div style="margin-top:16px;font-size:11px">예정 기능: 📦 확정건 출고 완료 ▶ · ✅ 승인 → FINALIZED · 완료 이력 Treeview · 📋 감사 로그 sub-popup (CSV export)</div>',
      '      </div>',
      '    </div>',
      '  </div>',  /* /oo-tab-body */
      /* 하단 버튼 */
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button class="btn btn-ghost" onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'">❌ 닫기</button>',
      '    <button class="btn" onclick="window.ooViewAuditLog()">📋 감사 로그 보기</button>',
      '    <button class="btn btn-wip" id="oo-final-btn" onclick="window.ooFinalize()" disabled title="Sprint 1-3 Phase D 예정">📦 확정건 출고 완료 ▶</button>',
      '  </div>',
      '</div>'
    ].join('\n');

    showDataModal('', html);

    /* 기본 출고일 = 오늘 */
    var dateInput = document.getElementById('oo-date');
    if (dateInput) {
      var d = new Date();
      dateInput.value = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    }
  }
  window.showOneStopOutboundModal = showOneStopOutboundModal;

  /* ─── Tab 전환 ─────────────────────────────────────────────────────── */
  window.ooSwitchTab = function(tab) {
    _ooState.currentTab = tab;
    document.querySelectorAll('.oo-tab-header').forEach(function(h){
      h.classList.toggle('active', parseInt(h.dataset.tab, 10) === tab);
    });
    document.querySelectorAll('.oo-tab-pane').forEach(function(p){
      p.classList.toggle('active', parseInt(p.dataset.pane, 10) === tab);
    });
  };

  /* ─── 상태 업데이트 ─────────────────────────────────────────────────── */
  function _ooSetState(newState) {
    _ooState.state = newState;
    var badge = document.getElementById('oo-status-badge');
    if (!badge) return;
    badge.className = 'oo-status-badge ' + newState.toLowerCase();
    var map = { DRAFT: '● DRAFT', WAIT_SCAN: '● WAIT_SCAN', FINALIZED: '● FINALIZED', REVIEW: '● REVIEW', ERROR: '● ERROR' };
    badge.textContent = map[newState] || ('● ' + newState);

    /* progress dots */
    var draft = document.getElementById('oo-dot-draft');
    var scan  = document.getElementById('oo-dot-scan');
    var final = document.getElementById('oo-dot-final');
    [draft, scan, final].forEach(function(d){ if (d) d.className = 'oo-status-dot'; });
    if (newState === 'DRAFT')         { if(draft) draft.className = 'oo-status-dot active'; }
    else if (newState === 'WAIT_SCAN'){ if(draft) draft.className = 'oo-status-dot done'; if(scan) scan.className = 'oo-status-dot active'; }
    else if (newState === 'FINALIZED'){ if(draft) draft.className = 'oo-status-dot done'; if(scan) scan.className = 'oo-status-dot done'; if(final) final.className = 'oo-status-dot active'; }

    /* 탭 활성화 */
    var tab2 = document.querySelector('.oo-tab-header[data-tab="2"]');
    var tab3 = document.querySelector('.oo-tab-header[data-tab="3"]');
    var tab4 = document.querySelector('.oo-tab-header[data-tab="4"]');
    if (tab2) tab2.disabled = !(newState === 'DRAFT' || newState === 'WAIT_SCAN' || newState === 'FINALIZED');
    if (tab3) tab3.disabled = !(newState === 'WAIT_SCAN' || newState === 'FINALIZED');
    if (tab4) tab4.disabled = !(newState === 'FINALIZED' || newState === 'REVIEW');

    var hint = document.getElementById('oo-status-hint');
    if (hint) {
      var hintMap = {
        DRAFT:     '📋 Tab 2 에서 톤백 선택 → DRAFT → WAIT_SCAN',
        WAIT_SCAN: '📊 Tab 3 에서 OUT 스캔 검증',
        FINALIZED: '✅ 완료 — Tab 4 에서 출고 확정',
        REVIEW:    '🔍 검토 필요 (불일치 발견)',
        ERROR:     '🚫 에러 — actual > expected',
      };
      hint.textContent = hintMap[newState] || '';
    }
  }

  /* ─── 근거문서 파일 관리 ────────────────────────────────────────────── */
  window.ooAddProofFiles = function(fileList) {
    if (!fileList) return;
    Array.from(fileList).forEach(function(f){ _ooState.proofDocs.push(f); });
    _ooRenderProofFiles();
  };
  window.ooRemoveProofFile = function(idx) {
    _ooState.proofDocs.splice(idx, 1);
    _ooRenderProofFiles();
  };
  function _ooRenderProofFiles() {
    var el = document.getElementById('oo-proof-files');
    if (!el) return;
    if (!_ooState.proofDocs.length) { el.innerHTML = '<span style="color:var(--text-muted);font-size:11px">첨부된 파일 없음</span>'; return; }
    el.innerHTML = _ooState.proofDocs.map(function(f, i){
      return '<span class="oo-file-chip">📄 ' + escapeHtml(f.name) + ' <span class="remove" onclick="window.ooRemoveProofFile(' + i + ')">✕</span></span>';
    }).join('');
  }

  /* ─── 수동 실제수량 ─────────────────────────────────────────────────── */
  window.ooAddManualActual = function() {
    var lot = (document.getElementById('oo-manual-lot') || {}).value || '';
    var act = (document.getElementById('oo-manual-actual') || {}).value || '';
    lot = String(lot).trim();
    if (!lot || !act) { showToast('warn', 'LOT NO 와 실제(kg) 값 필요'); return; }
    _ooState.manualActuals[lot] = { actual_kg: parseFloat(act) };
    document.getElementById('oo-manual-lot').value = '';
    document.getElementById('oo-manual-actual').value = '';
    var list = document.getElementById('oo-manual-list');
    if (list) {
      var items = Object.keys(_ooState.manualActuals).map(function(k){
        return k + '=' + _ooState.manualActuals[k].actual_kg + 'kg';
      });
      list.textContent = items.length ? '(' + items.length + '건: ' + items.slice(0, 3).join(', ') + (items.length > 3 ? '…' : '') + ')' : '';
    }
    showToast('success', '수동값 ' + lot + ' = ' + act + 'kg 저장됨');
  };

  /* ─── Paste / Sample / Clear ───────────────────────────────────────── */
  window.ooInsertSample = function() {
    var ta = document.getElementById('oo-paste');
    if (!ta) return;
    ta.value = 'LOT_NO\tSAP_NO\tQTY(kg)\tCUSTOMER\tSALE_REF\n' +
               '1126013063\t2200034449\t5001.25\tACME Corp\tSO-2026-0420\n' +
               '1126013064\t2200034449\t5000.50\tACME Corp\tSO-2026-0420\n' +
               '1126013065\t2200034449\t4998.75\tACME Corp\tSO-2026-0420';
    showToast('info', '샘플 3행 삽입됨 — 파싱해 보세요');
  };
  window.ooClearPaste = function() {
    var ta = document.getElementById('oo-paste');
    if (ta) ta.value = '';
    var rb = document.getElementById('oo-draft-result');
    if (rb) rb.innerHTML = '';
  };

  /* ─── 파싱 → DRAFT 전환 ────────────────────────────────────────────── */
  window.ooParseDraft = function() {
    var customer = (document.getElementById('oo-customer') || {}).value || '';
    var saleRef  = (document.getElementById('oo-sale-ref') || {}).value || '';
    var lotNo    = (document.getElementById('oo-lot') || {}).value || '';
    var paste    = (document.getElementById('oo-paste') || {}).value || '';
    customer = customer.trim(); saleRef = saleRef.trim(); lotNo = lotNo.trim(); paste = paste.trim();

    if (!customer && !paste) { showToast('error', '고객사 또는 붙여넣기 내용 필요'); return; }

    _ooState.customer = customer;
    _ooState.saleRef = saleRef;
    _ooState.lotNo = lotNo;
    _ooState.pasteText = paste;

    /* paste 파싱 — TSV/CSV 구분 + 헤더 자동 인식 */
    var items = [];
    if (paste) {
      var lines = paste.split(/\r?\n/).filter(function(l){ return l.trim(); });
      if (lines.length >= 2) {
        /* 헤더 감지 */
        var headers = lines[0].split(/\t|,/).map(function(s){ return s.trim().toLowerCase(); });
        var iLot  = headers.findIndex(function(h){ return /lot[_ ]?no|lot/.test(h); });
        var iSap  = headers.findIndex(function(h){ return /sap/.test(h); });
        var iQty  = headers.findIndex(function(h){ return /qty|weight|net/.test(h); });
        var iCust = headers.findIndex(function(h){ return /customer|고객/.test(h); });
        var iRef  = headers.findIndex(function(h){ return /sale[_ ]?ref|sale/.test(h); });
        /* 데이터 행 */
        for (var i = 1; i < lines.length; i++) {
          var cols = lines[i].split(/\t|,/).map(function(s){ return s.trim(); });
          if (!cols.length) continue;
          items.push({
            lot_no:     iLot  >= 0 ? cols[iLot]  : cols[0] || '',
            sap_no:     iSap  >= 0 ? cols[iSap]  : '',
            qty_kg:     iQty  >= 0 ? parseFloat(cols[iQty] || 0) : 0,
            customer:   iCust >= 0 ? cols[iCust] : customer,
            sale_ref:   iRef  >= 0 ? cols[iRef]  : saleRef,
          });
        }
      } else {
        /* 단일 행 텍스트 → LOT NO 만 추출 */
        items.push({ lot_no: paste, sap_no: '', qty_kg: 0, customer: customer, sale_ref: saleRef });
      }
    } else if (lotNo) {
      items.push({ lot_no: lotNo, sap_no: '', qty_kg: 0, customer: customer, sale_ref: saleRef });
    }

    if (!items.length) { showToast('error', '파싱 결과가 비어있습니다'); return; }

    _ooState.parsedItems = items;
    _ooSetState('DRAFT');

    var rb = document.getElementById('oo-draft-result');
    if (rb) {
      rb.innerHTML =
        '<div style="padding:10px;background:rgba(102,187,106,.1);border-left:3px solid var(--success);border-radius:4px">' +
        '<div style="font-weight:700;color:var(--success)">✅ DRAFT 생성 완료 — ' + items.length + '건</div>' +
        '<div style="font-size:11px;color:var(--text-muted);margin-top:4px">' +
        '고객사: ' + escapeHtml(customer || '(paste 기반)') + ' · Sale Ref: ' + escapeHtml(saleRef || '-') +
        ' · 근거문서: ' + _ooState.proofDocs.length + '건' +
        ' · 수동값: ' + Object.keys(_ooState.manualActuals).length + '건</div>' +
        '<details style="margin-top:6px"><summary style="cursor:pointer;font-size:12px">파싱된 LOT 목록</summary>' +
        '<table class="data-table" style="margin-top:6px;font-size:11px"><thead><tr><th>#</th><th>LOT</th><th>SAP</th><th>QTY(kg)</th><th>고객</th><th>Ref</th></tr></thead><tbody>' +
        items.map(function(it, i){
          return '<tr><td>' + (i+1) + '</td><td class="mono-cell">' + escapeHtml(it.lot_no||'-') + '</td><td class="mono-cell">' + escapeHtml(it.sap_no||'-') + '</td><td class="mono-cell" style="text-align:right">' + (it.qty_kg || 0) + '</td><td>' + escapeHtml(it.customer||'-') + '</td><td class="mono-cell">' + escapeHtml(it.sale_ref||'-') + '</td></tr>';
        }).join('') + '</tbody></table></details>' +
        '<div style="margin-top:8px;font-size:11px;color:var(--info, #42a5f5)">💡 다음 단계: 상단 <strong>② 톤백 선택</strong> 탭으로 이동 중...</div>' +
        '</div>';
    }
    showToast('success', 'DRAFT 생성: ' + items.length + '건 — 톤백 로드 중...');
    /* [Sprint 1-3-B] Tab 2 로 자동 이동 + 톤백 로드 */
    _ooLoadTonbagsForLots();
    setTimeout(function(){ window.ooSwitchTab(2); }, 600);
  };

  /* =====================================================================
     [Sprint 1-3-B] Tab 2 — 톤백 선택 로직
     ===================================================================== */
  function _ooLoadTonbagsForLots() {
    var lots = _ooState.parsedItems.map(function(it){ return it.lot_no; }).filter(Boolean);
    if (!lots.length) return;
    _ooState.lotsWithTonbags = {};
    _ooState.selectedTonbags.clear();
    _ooState.expandedLots.clear();

    var body = document.getElementById('oo-tonbags-body');
    if (body) body.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px">⏳ ' + lots.length + ' LOT 톤백 조회 중...</div>';

    /* 각 LOT에 대해 GET /api/tonbags?lot_no=<lot>&status=AVAILABLE */
    var promises = lots.map(function(lot){
      return apiGet('/api/tonbags?lot_no=' + encodeURIComponent(lot) + '&status=AVAILABLE')
        .then(function(res){ return { lot: lot, rows: extractRows(res) }; })
        .catch(function(){ return { lot: lot, rows: [] }; });
    });

    Promise.all(promises).then(function(results){
      results.forEach(function(r){
        _ooState.lotsWithTonbags[r.lot] = r.rows.filter(function(t){
          /* LOT NO 정확 매치 (LIKE 는 여러 LOT 잡을 수 있음) */
          return (t.lot_no || '') === r.lot;
        });
        /* 기본 확장 */
        _ooState.expandedLots.add(r.lot);
      });
      _ooRenderTonbags();
      _ooUpdateT2Stats();
    });
  }

  function _ooRenderTonbags() {
    var body = document.getElementById('oo-tonbags-body');
    if (!body) return;
    var lots = _ooState.parsedItems.map(function(it){ return it.lot_no; }).filter(Boolean);
    if (!lots.length) { body.innerHTML = '<div style="padding:30px;text-align:center;color:var(--text-muted)">LOT 없음</div>'; return; }

    var html = lots.map(function(lot){
      var tonbags = _ooState.lotsWithTonbags[lot] || [];
      var selectedInLot = tonbags.filter(function(t){
        return _ooState.selectedTonbags.has(lot + '.' + (t.sub_lt || t.tonbag_id));
      });
      var expanded = _ooState.expandedLots.has(lot);
      var totalKg = tonbags.reduce(function(s, t){ return s + (Number(t.weight) || 0); }, 0);
      var selKg   = selectedInLot.reduce(function(s, t){ return s + (Number(t.weight) || 0); }, 0);

      var header =
        '<div class="oo-lot-header" style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:var(--bg-hover);border:1px solid var(--panel-border);border-radius:4px;cursor:pointer;margin-top:4px;font-size:12px" onclick="window.ooToggleLotExpand(\'' + escapeHtml(lot) + '\')">' +
        '<span style="font-size:12px;color:var(--text-muted)">' + (expanded ? '▼' : '▶') + '</span>' +
        '<strong style="color:var(--accent);font-family:Consolas,monospace">' + escapeHtml(lot) + '</strong>' +
        '<span style="color:var(--text-muted)">· 가용 ' + tonbags.length + '개 · ' + totalKg.toFixed(2) + 'kg</span>' +
        (selectedInLot.length > 0 ? '<span style="color:var(--success);font-weight:700">· 선택 ' + selectedInLot.length + '개 (' + selKg.toFixed(2) + 'kg)</span>' : '') +
        '<span style="margin-left:auto;display:flex;gap:4px" onclick="event.stopPropagation()">' +
        '<button class="btn" style="padding:2px 8px;font-size:11px" onclick="window.ooSelectAllForLot(\'' + escapeHtml(lot) + '\')">✅ LOT 전체</button>' +
        '<button class="btn" style="padding:2px 8px;font-size:11px" onclick="window.ooDeselectForLot(\'' + escapeHtml(lot) + '\')">☐ 해제</button>' +
        '</span>' +
        '</div>';

      if (!expanded) return header;

      if (!tonbags.length) {
        return header + '<div style="padding:10px 20px;color:var(--text-muted);font-size:11px">📭 가용 톤백 없음</div>';
      }

      var rows = tonbags.map(function(t){
        var key = lot + '.' + (t.sub_lt || t.tonbag_id);
        var checked = _ooState.selectedTonbags.has(key) ? 'checked' : '';
        return '<tr style="font-size:11px">' +
          '<td style="width:28px;text-align:center"><input type="checkbox" ' + checked + ' onchange="window.ooToggleTonbag(\'' + escapeHtml(lot) + '\',\'' + escapeHtml(t.sub_lt || t.tonbag_id) + '\',this.checked)"></td>' +
          '<td class="mono-cell">' + escapeHtml(t.sub_lt || t.tonbag_id || '-') + '</td>' +
          '<td class="mono-cell" style="text-align:right">' + (Number(t.weight) || 0).toFixed(2) + '</td>' +
          '<td>' + escapeHtml(t.status || '-') + '</td>' +
          '<td>' + escapeHtml(t.location || '-') + '</td>' +
          '<td class="mono-cell">' + escapeHtml(t.container || '-') + '</td>' +
          '</tr>';
      }).join('');

      return header +
        '<table class="data-table" style="margin-top:2px;font-size:11px"><thead><tr><th></th><th>톤백 ID</th><th style="text-align:right">중량(kg)</th><th>상태</th><th>위치</th><th>컨테이너</th></tr></thead><tbody>' + rows + '</tbody></table>';
    }).join('');

    body.innerHTML = html;
  }

  function _ooUpdateT2Stats() {
    var el = document.getElementById('oo-t2-stats');
    var btn = document.getElementById('oo-goto-scan-btn');
    if (!el) return;
    var lots = _ooState.parsedItems.map(function(it){ return it.lot_no; }).filter(Boolean);
    var totalTonbags = 0, totalKg = 0, selectedCount = _ooState.selectedTonbags.size, selectedKg = 0;

    lots.forEach(function(lot){
      var arr = _ooState.lotsWithTonbags[lot] || [];
      arr.forEach(function(t){
        totalTonbags++;
        totalKg += Number(t.weight) || 0;
        var key = lot + '.' + (t.sub_lt || t.tonbag_id);
        if (_ooState.selectedTonbags.has(key)) selectedKg += Number(t.weight) || 0;
      });
    });

    el.innerHTML =
      '<div>📦 파싱 LOT <strong>' + lots.length + '개</strong> · 전체 가용 톤백 <strong>' + totalTonbags + '개</strong> (' + (totalKg / 1000).toFixed(3) + ' MT)</div>' +
      '<div style="margin-top:4px">✅ 선택됨: <strong style="color:' + (selectedCount > 0 ? 'var(--success)' : 'var(--text-muted)') + '">' + selectedCount + '개</strong> (' + (selectedKg / 1000).toFixed(3) + ' MT)</div>';

    if (btn) btn.disabled = selectedCount === 0;
  }

  /* 개별/일괄 토글 */
  window.ooToggleLotExpand = function(lot) {
    if (_ooState.expandedLots.has(lot)) _ooState.expandedLots.delete(lot);
    else _ooState.expandedLots.add(lot);
    _ooRenderTonbags();
  };
  window.ooToggleTonbag = function(lot, subLt, checked) {
    var key = lot + '.' + subLt;
    if (checked) _ooState.selectedTonbags.add(key);
    else _ooState.selectedTonbags.delete(key);
    _ooUpdateT2Stats();
    /* 헤더 요약 갱신을 위해 재렌더 (가벼운 구현 — 필요하면 부분 업데이트 최적화) */
    _ooRenderTonbags();
  };
  window.ooSelectAllForLot = function(lot) {
    var arr = _ooState.lotsWithTonbags[lot] || [];
    arr.forEach(function(t){ _ooState.selectedTonbags.add(lot + '.' + (t.sub_lt || t.tonbag_id)); });
    _ooRenderTonbags();
    _ooUpdateT2Stats();
  };
  window.ooDeselectForLot = function(lot) {
    var arr = _ooState.lotsWithTonbags[lot] || [];
    arr.forEach(function(t){ _ooState.selectedTonbags.delete(lot + '.' + (t.sub_lt || t.tonbag_id)); });
    _ooRenderTonbags();
    _ooUpdateT2Stats();
  };
  window.ooSelectAllLots = function() {
    Object.keys(_ooState.lotsWithTonbags).forEach(function(lot){
      (_ooState.lotsWithTonbags[lot] || []).forEach(function(t){
        _ooState.selectedTonbags.add(lot + '.' + (t.sub_lt || t.tonbag_id));
      });
    });
    _ooRenderTonbags();
    _ooUpdateT2Stats();
  };
  window.ooDeselectAll = function() {
    _ooState.selectedTonbags.clear();
    _ooRenderTonbags();
    _ooUpdateT2Stats();
  };
  window.ooExpandAll = function(expand) {
    _ooState.expandedLots.clear();
    if (expand) {
      Object.keys(_ooState.lotsWithTonbags).forEach(function(lot){ _ooState.expandedLots.add(lot); });
    }
    _ooRenderTonbags();
  };

  /* 🎲 랜덤 선택 — 각 LOT에서 parsedItems.qty_kg 에 가장 가까운 조합 선택
     단순 heuristic: qty_kg를 톤백 평균으로 나눈 개수만큼 선택 */
  window.ooRandomSelect = function() {
    _ooState.selectedTonbags.clear();
    _ooState.parsedItems.forEach(function(item){
      var arr = (_ooState.lotsWithTonbags[item.lot_no] || []).slice();
      if (!arr.length) return;
      var avgKg = arr.reduce(function(s, t){ return s + (Number(t.weight) || 0); }, 0) / arr.length;
      var needCount = item.qty_kg > 0 && avgKg > 0 ? Math.max(1, Math.round(item.qty_kg / avgKg)) : 1;
      needCount = Math.min(needCount, arr.length);
      /* Fisher-Yates shuffle */
      for (var i = arr.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
      }
      for (var k = 0; k < needCount; k++) {
        _ooState.selectedTonbags.add(item.lot_no + '.' + (arr[k].sub_lt || arr[k].tonbag_id));
      }
    });
    _ooRenderTonbags();
    _ooUpdateT2Stats();
    showToast('success', '🎲 랜덤 선택: ' + _ooState.selectedTonbags.size + '개');
  };

  /* DRAFT → WAIT_SCAN 전환 */
  window.ooMoveToScan = function() {
    if (_ooState.selectedTonbags.size === 0) {
      showToast('warn', '선택된 톤백이 없습니다');
      return;
    }
    if (!confirm('📦 WAIT_SCAN 진입\n\n선택된 톤백 ' + _ooState.selectedTonbags.size + '개로 스캔 검증 단계로 이동합니다.\n계속하시겠습니까?')) return;
    _ooSetState('WAIT_SCAN');
    _ooUpdateT3Stats();
    setTimeout(function(){ window.ooSwitchTab(3); }, 300);
    showToast('success', 'WAIT_SCAN 진입 — Tab 3 에서 OUT 스캔 검증');
  };

  /* =====================================================================
     [Sprint 1-3-C] Tab 3 — OUT 스캔 검증 + 하드스톱
     ─────────────────────────────────────────────────────────────────────
     검증 룰 (v864-2 매칭):
       |diff_pct| <= 0.5%     → ✅ OK
       0.5% < |diff_pct| ≤ 5% → ⚠️ Warning (REVIEW)
       |diff_pct| > 5%        → 🚫 STOP (ERROR — FINALIZED 차단)
       actual > expected      → 🚫 즉시 하드스톱
     ===================================================================== */
  function _ooUpdateT3Stats() {
    var el = document.getElementById('oo-t3-stats');
    if (!el) return;
    var selCount = _ooState.selectedTonbags.size;
    var selKg = 0;
    Object.keys(_ooState.lotsWithTonbags).forEach(function(lot){
      (_ooState.lotsWithTonbags[lot] || []).forEach(function(t){
        var key = lot + '.' + (t.sub_lt || t.tonbag_id);
        if (_ooState.selectedTonbags.has(key)) selKg += Number(t.weight) || 0;
      });
    });
    var scanned = _ooState.scanRows.length + _ooState.manualScans.length;
    var ok = _ooState.validationResults.filter(function(r){ return r.level === 'ok'; }).length;
    var warn = _ooState.validationResults.filter(function(r){ return r.level === 'warn'; }).length;
    var stop = _ooState.validationResults.filter(function(r){ return r.level === 'stop'; }).length;

    el.innerHTML =
      '<div>📦 검증 대상: <strong>' + selCount + '개 톤백</strong> (' + (selKg / 1000).toFixed(3) + ' MT)</div>' +
      '<div style="margin-top:4px">📊 스캔된 항목: <strong>' + scanned + '건</strong>' +
      (_ooState.validationResults.length ?
        ' · ✅ 통과 <strong style="color:var(--success)">' + ok + '</strong>' +
        ' · ⚠️ 경고 <strong style="color:var(--warning)">' + warn + '</strong>' +
        ' · 🚫 하드스톱 <strong style="color:var(--danger)">' + stop + '</strong>' : '') + '</div>';
  }

  /* CSV/xlsx 업로드 → 백엔드 파싱 */
  window.ooHandleScanFile = function(file) {
    if (!file) return;
    _ooState.scanFile = file;
    var fnEl = document.getElementById('oo-scan-filename');
    if (fnEl) fnEl.textContent = '⏳ 파싱 중: ' + file.name + ' (' + Math.round(file.size / 1024) + ' KB)';

    var form = new FormData();
    form.append('file', file, file.name);
    var xhr = new XMLHttpRequest();
    xhr.open('POST', API + '/api/outbound/onestop-scan-parse');
    xhr.onload = function(){
      var body; try { body = JSON.parse(xhr.responseText); } catch(e){ body = null; }
      if (xhr.status >= 200 && xhr.status < 300 && body && body.ok) {
        var d = body.data || {};
        _ooState.scanRows = d.rows || [];
        if (fnEl) fnEl.innerHTML = '✅ <strong>' + escapeHtml(d.filename) + '</strong> · ' + d.row_count + '행 (UID ' + d.uid_count + ' / actual ' + d.actual_count + ')';
        showToast('success', 'OUT 스캔 파싱: ' + d.row_count + '행');
        _ooUpdateT3Stats();
        var hint = document.getElementById('oo-validation-hint');
        if (hint) hint.textContent = '⚡ 전체 검증 실행 준비 완료';
      } else {
        var msg = (body && (body.detail || body.error || body.message)) || ('HTTP ' + xhr.status);
        if (typeof msg === 'object') msg = JSON.stringify(msg);
        if (fnEl) fnEl.innerHTML = '❌ 파싱 실패: ' + escapeHtml(String(msg));
        showToast('error', '파싱 실패: ' + msg);
        _ooState.scanFile = null;
        _ooState.scanRows = [];
      }
    };
    xhr.onerror = function(){
      if (fnEl) fnEl.textContent = '❌ 네트워크 에러';
      showToast('error', '네트워크 에러');
    };
    xhr.send(form);
  };

  window.ooClearScan = function() {
    _ooState.scanFile = null;
    _ooState.scanRows = [];
    _ooState.manualScans = [];
    _ooState.validationResults = [];
    var fnEl = document.getElementById('oo-scan-filename');
    if (fnEl) fnEl.textContent = '선택된 파일 없음';
    var input = document.getElementById('oo-scan-input');
    if (input) input.value = '';
    var resBody = document.getElementById('oo-validation-results');
    if (resBody) resBody.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px">⚡ "전체 검증 실행" 버튼을 눌러 결과를 확인하세요</div>';
    var goBtn = document.getElementById('oo-goto-finalize-btn');
    if (goBtn) goBtn.disabled = true;
    var hint = document.getElementById('oo-validation-hint');
    if (hint) hint.textContent = '스캔 데이터를 먼저 업로드/입력';
    _ooUpdateT3Stats();
  };

  window.ooAddManualScan = function() {
    var uid = (document.getElementById('oo-scan-uid') || {}).value || '';
    var act = (document.getElementById('oo-scan-actual') || {}).value || '';
    uid = String(uid).trim();
    if (!uid || !act) { showToast('warn', '톤백 ID와 실제(kg) 필요'); return; }
    var actNum = parseFloat(act);
    if (isNaN(actNum)) { showToast('error', 'actual_kg 가 숫자 아님'); return; }
    _ooState.manualScans.push({ tonbag_uid: uid, actual_kg: actNum });
    document.getElementById('oo-scan-uid').value = '';
    document.getElementById('oo-scan-actual').value = '';
    showToast('success', '수동 추가: ' + uid + ' = ' + actNum + 'kg (총 ' + _ooState.manualScans.length + '건)');
    _ooUpdateT3Stats();
  };

  /* ⚡ 전체 검증 실행 — 선택된 톤백 vs 스캔된 actual */
  window.ooRunValidation = function() {
    if (_ooState.selectedTonbags.size === 0) {
      showToast('error', 'Tab 2에서 톤백을 먼저 선택하세요');
      return;
    }
    var allScans = (_ooState.scanRows || []).concat(_ooState.manualScans || []);
    if (!allScans.length) {
      showToast('error', 'OUT 스캔 데이터를 먼저 업로드/입력하세요');
      return;
    }

    /* 선택된 톤백 → expected map */
    var expectedMap = {};  /* tonbag_uid → {lot_no, expected_kg, weight} */
    Object.keys(_ooState.lotsWithTonbags).forEach(function(lot){
      (_ooState.lotsWithTonbags[lot] || []).forEach(function(t){
        var uid = t.sub_lt || t.tonbag_id;
        var key = lot + '.' + uid;
        if (_ooState.selectedTonbags.has(key)) {
          expectedMap[uid] = {
            lot_no:      lot,
            expected_kg: Number(t.weight) || 0,
            tonbag_no:   t.tonbag_no || '',
            location:    t.location || '',
          };
        }
      });
    });

    /* actual map (덮어쓰기 — 마지막 값 우선) */
    var actualMap = {};
    allScans.forEach(function(s){
      if (s.tonbag_uid && s.actual_kg != null) actualMap[s.tonbag_uid] = Number(s.actual_kg);
    });

    /* 결과 조립 */
    var results = [];
    Object.keys(expectedMap).forEach(function(uid){
      var exp = expectedMap[uid];
      var actual = actualMap[uid];
      var level, message, diffPct = null;
      if (actual == null) {
        level = 'missing'; message = '🔍 스캔 데이터 없음';
      } else {
        diffPct = exp.expected_kg > 0 ? ((actual - exp.expected_kg) / exp.expected_kg) * 100 : 0;
        var absDiff = Math.abs(diffPct);
        if (actual > exp.expected_kg) {
          level = 'stop'; message = '🚫 actual > expected (하드스톱)';
        } else if (absDiff > 5) {
          level = 'stop'; message = '🚫 ' + absDiff.toFixed(2) + '% 편차 (>5% 하드스톱)';
        } else if (absDiff > 0.5) {
          level = 'warn'; message = '⚠️ ' + absDiff.toFixed(2) + '% 편차 (검토 필요)';
        } else {
          level = 'ok'; message = '✅ 통과 (' + absDiff.toFixed(2) + '% 편차)';
        }
      }
      results.push({
        tonbag_uid:  uid,
        lot_no:      exp.lot_no,
        expected_kg: exp.expected_kg,
        actual_kg:   actual,
        diff_pct:    diffPct,
        level:       level,
        message:     message,
      });
    });

    /* 스캔에 있는데 선택 안 된 항목도 표시 (extra) */
    Object.keys(actualMap).forEach(function(uid){
      if (!expectedMap[uid]) {
        results.push({
          tonbag_uid: uid,
          lot_no:     '(미선택)',
          expected_kg: 0,
          actual_kg:   actualMap[uid],
          diff_pct:    null,
          level:       'extra',
          message:     '⚠️ 선택되지 않은 톤백 (스캔만 존재)',
        });
      }
    });

    _ooState.validationResults = results;

    /* 상태 결정 */
    var hasStop = results.some(function(r){ return r.level === 'stop'; });
    var hasWarn = results.some(function(r){ return r.level === 'warn'; });
    if (hasStop) _ooSetState('ERROR');
    else if (hasWarn) _ooSetState('REVIEW');
    /* WAIT_SCAN 유지 (FINALIZED 는 명시적 클릭) */

    _ooRenderValidationResults();
    _ooUpdateT3Stats();

    var goBtn = document.getElementById('oo-goto-finalize-btn');
    if (goBtn) {
      goBtn.disabled = hasStop;
      if (hasStop) goBtn.title = '🚫 하드스톱 발견 — FINALIZED 진입 불가';
      else if (hasWarn) goBtn.title = '⚠️ 경고 있음 — 검토 후 FINALIZED 진입 가능';
      else goBtn.title = '✅ 모두 통과 — FINALIZED 진입 가능';
    }
    var hint = document.getElementById('oo-validation-hint');
    if (hint) {
      var summary = '✅ ' + results.filter(function(r){return r.level==='ok';}).length +
                    ' · ⚠️ ' + results.filter(function(r){return r.level==='warn';}).length +
                    ' · 🚫 ' + results.filter(function(r){return r.level==='stop';}).length;
      hint.textContent = '검증 완료: ' + summary;
    }
    if (hasStop) showToast('error', '🚫 하드스톱 발견 — 파일 확인 후 재검증');
    else if (hasWarn) showToast('warn', '⚠️ 일부 편차 — 검토 후 진행');
    else showToast('success', '✅ 모든 톤백 통과 — FINALIZED 진입 가능');
  };

  function _ooRenderValidationResults() {
    var body = document.getElementById('oo-validation-results');
    if (!body) return;
    var results = _ooState.validationResults;
    if (!results.length) { body.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">검증 결과 없음</div>'; return; }

    var levelStyle = {
      ok:      'background:rgba(102,187,106,.1)',
      warn:    'background:rgba(255,167,38,.15)',
      stop:    'background:rgba(244,67,54,.18)',
      missing: 'background:rgba(158,158,158,.1)',
      extra:   'background:rgba(66,165,245,.1)',
    };

    var rows = results.map(function(r, i){
      var style = levelStyle[r.level] || '';
      var diff = (r.diff_pct == null) ? '-' : (r.diff_pct >= 0 ? '+' : '') + r.diff_pct.toFixed(2) + '%';
      return '<tr style="' + style + '">' +
        '<td style="text-align:right">' + (i+1) + '</td>' +
        '<td class="mono-cell">' + escapeHtml(r.tonbag_uid) + '</td>' +
        '<td class="mono-cell" style="color:var(--accent)">' + escapeHtml(r.lot_no) + '</td>' +
        '<td class="mono-cell" style="text-align:right">' + (r.expected_kg ? r.expected_kg.toFixed(2) : '-') + '</td>' +
        '<td class="mono-cell" style="text-align:right">' + (r.actual_kg != null ? r.actual_kg.toFixed(2) : '-') + '</td>' +
        '<td class="mono-cell" style="text-align:right">' + diff + '</td>' +
        '<td>' + escapeHtml(r.message) + '</td>' +
        '</tr>';
    }).join('');

    body.innerHTML =
      '<table class="data-table" style="font-size:11px"><thead><tr>' +
      '<th>#</th><th>톤백 UID</th><th>LOT</th><th style="text-align:right">Expected (kg)</th><th style="text-align:right">Actual (kg)</th><th style="text-align:right">Diff %</th><th>상태</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table>';
  }

  /* WAIT_SCAN → FINALIZED 전환 */
  window.ooMoveToFinalize = function() {
    var hasStop = _ooState.validationResults.some(function(r){ return r.level === 'stop'; });
    if (hasStop) {
      showToast('error', '🚫 하드스톱 발견 — FINALIZED 진입 불가');
      return;
    }
    var hasWarn = _ooState.validationResults.some(function(r){ return r.level === 'warn'; });
    var msg = '✅ FINALIZED 진입\n\n검증 통과: ' + _ooState.selectedTonbags.size + '개 톤백\n' +
              (hasWarn ? '⚠️ 일부 경고 있음 — 검토하셨나요?\n' : '') +
              'Tab 4 에서 출고 확정합니다. 계속하시겠습니까?';
    if (!confirm(msg)) return;
    _ooSetState('FINALIZED');
    setTimeout(function(){ window.ooSwitchTab(4); }, 300);
    showToast('success', 'FINALIZED 진입 — Tab 4 에서 출고 확정 (Sprint 1-3-D 예정)');
  };

  /* ─── 플레이스홀더 ──────────────────────────────────────────────────── */
  window.ooFinalize = function() {
    showToast('info', '출고 확정: Sprint 1-3 Phase D (Tab 4 완료) 에서 구현 예정');
  };
  window.ooViewAuditLog = function() {
    showToast('info', '감사 로그 sub-popup: Sprint 1-3 Phase D 에서 구현 (오늘은 기존 📋 감사 로그 조회 메뉴 사용)');
  };

  /* 기존 showQuickOutboundModal (레거시 — 단순 즉시 출고) */
  function showQuickOutboundModal() {
    var html = [
      '<div style="max-width:560px">',
      '  <h2 style="margin:0 0 12px 0">🚀 즉시 출고 (원스톱)</h2>',
      '  <p style="color:var(--text-muted);margin:0 0 16px 0;font-size:.9rem">',
      '    Allocation 없이 소량 톤백을 바로 출고합니다. (AVAILABLE → PICKED)',
      '  </p>',
      '  <div style="display:grid;grid-template-columns:110px 1fr;gap:10px;align-items:center;margin-bottom:12px">',
      '    <label style="font-weight:600">LOT 번호</label>',
      '    <input type="text" id="qo-lot" placeholder="예: 1126013063" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;font-family:monospace">',
      '    <label style="font-weight:600">톤백 수</label>',
      '    <input type="number" id="qo-count" min="1" value="1" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;width:120px">',
      '    <label style="font-weight:600">고객명</label>',
      '    <input type="text" id="qo-customer" placeholder="예: ACME Corp" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '    <label style="font-weight:600">사유 <span style="color:var(--text-muted);font-weight:400;font-size:.8rem">(선택)</span></label>',
      '    <input type="text" id="qo-reason" placeholder="" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '    <label style="font-weight:600">작업자 <span style="color:var(--text-muted);font-weight:400;font-size:.8rem">(선택)</span></label>',
      '    <input type="text" id="qo-operator" placeholder="" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '  </div>',
      '  <div id="qo-info" style="padding:10px;background:var(--bg-hover);border-radius:6px;font-size:.85rem;color:var(--text-muted);margin-bottom:12px;min-height:38px">',
      '    LOT 번호를 입력하면 가용 톤백 정보가 표시됩니다',
      '  </div>',
      '  <div id="qo-result" style="margin-bottom:12px"></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button id="qo-cancel-btn" class="btn btn-ghost">닫기</button>',
      '    <button id="qo-submit-btn" class="btn btn-primary" disabled>출고 확정</button>',
      '  </div>',
      '</div>'
    ].join('\n');

    showDataModal('', html);

    var lotInput = document.getElementById('qo-lot');
    var countInput = document.getElementById('qo-customer');
    var cntInput = document.getElementById('qo-count');
    var customerInput = document.getElementById('qo-customer');
    var reasonInput = document.getElementById('qo-reason');
    var operatorInput = document.getElementById('qo-operator');
    var infoBox  = document.getElementById('qo-info');
    var resultBox = document.getElementById('qo-result');
    var submitBtn = document.getElementById('qo-submit-btn');
    var cancelBtn = document.getElementById('qo-cancel-btn');

    function validate() {
      var ok = !!(lotInput.value.trim() && customerInput.value.trim() && parseInt(cntInput.value, 10) > 0);
      submitBtn.disabled = !ok;
    }

    var _lotDebounce = null;
    function fetchLotInfo() {
      var lot = lotInput.value.trim();
      if (!lot) {
        infoBox.innerHTML = 'LOT 번호를 입력하면 가용 톤백 정보가 표시됩니다';
        infoBox.style.borderLeft = 'none';
        return;
      }
      infoBox.innerHTML = '⏳ 조회 중...';
      infoBox.style.borderLeft = 'none';
      apiGet('/api/outbound/quick/info?lot_no=' + encodeURIComponent(lot))
        .then(function(res) {
          if (!res || !res.ok) {
            infoBox.innerHTML = '❌ 조회 실패';
            return;
          }
          var d = res.data || {};
          var color = d.available_count > 0 ? 'var(--success)' : 'var(--warning)';
          infoBox.innerHTML =
            '<span style="color:' + color + ';font-weight:600">LOT ' + escapeHtml(lot) + '</span> · ' +
            '가용 톤백 <strong>' + d.available_count + '개</strong> (' + (d.total_weight_mt||0).toFixed(3) + ' MT) · ' +
            '최대 ' + d.max_count + '개';
          infoBox.style.borderLeft = '4px solid ' + color;
          infoBox.style.paddingLeft = '10px';
          // 톤백 수 max 조정
          cntInput.max = Math.min(d.available_count, d.max_count);
          if (parseInt(cntInput.value, 10) > cntInput.max) cntInput.value = cntInput.max;
        })
        .catch(function(e) {
          infoBox.innerHTML = '❌ 조회 실패: ' + escapeHtml(e.message || String(e));
        });
    }

    lotInput.addEventListener('input', function() {
      validate();
      if (_lotDebounce) clearTimeout(_lotDebounce);
      _lotDebounce = setTimeout(fetchLotInfo, 400);
    });
    cntInput.addEventListener('input', validate);
    customerInput.addEventListener('input', validate);

    cancelBtn.addEventListener('click', function() {
      document.getElementById('sqm-modal').style.display = 'none';
    });

    submitBtn.addEventListener('click', function() {
      var payload = {
        lot_no: lotInput.value.trim(),
        count: parseInt(cntInput.value, 10),
        customer: customerInput.value.trim(),
        reason: reasonInput.value.trim(),
        operator: operatorInput.value.trim(),
      };
      if (!confirm('LOT ' + payload.lot_no + ' 에서 ' + payload.count + '개 톤백을 ' + payload.customer + ' 로 출고하시겠습니까?')) return;

      submitBtn.disabled = true;
      cancelBtn.disabled = true;
      resultBox.innerHTML = '<div style="padding:8px;color:var(--text-muted)">⏳ 출고 처리 중...</div>';

      apiPost('/api/outbound/quick', payload)
        .then(function(res) {
          if (res && res.ok) {
            var d = res.data || {};
            resultBox.innerHTML =
              '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--success)">' +
              '<div style="font-weight:600;margin-bottom:4px">✅ ' + escapeHtml(res.message||'출고 완료') + '</div>' +
              '<div style="color:var(--text-muted);font-size:.85rem">LOT ' + escapeHtml(d.lot_no||'-') + ' · ' + (d.picked_count||0) + '개 톤백 · ' + (d.total_weight_mt||0).toFixed(3) + ' MT · ' + escapeHtml(d.customer||'-') + '</div>' +
              '</div>';
            showToast('success', res.message || '출고 완료');
            dbgLog('🟢','QUICK-OUTBOUND OK', res.message, '#66bb6a');
            // refresh
            if (_currentRoute === 'inventory' && typeof loadInventoryPage === 'function') loadInventoryPage();
            if (typeof loadKpi === 'function') loadKpi();
          } else {
            var errs = (res && res.data && res.data.errors) || [];
            var errMsg = (res && (res.message || res.error)) || '출고 실패';
            resultBox.innerHTML =
              '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--danger)">' +
              '<div style="font-weight:600">❌ ' + escapeHtml(errMsg) + '</div>' +
              (errs.length ? '<ul style="margin:8px 0 0 18px;color:var(--text-muted);font-size:.85rem">' + errs.map(function(e){return '<li>'+escapeHtml(e)+'</li>';}).join('') + '</ul>' : '') +
              '</div>';
            showToast('error', errMsg);
            dbgLog('🔴','QUICK-OUTBOUND FAIL', errMsg, '#ef5350');
            submitBtn.disabled = false;
            cancelBtn.disabled = false;
          }
        })
        .catch(function(e) {
          resultBox.innerHTML =
            '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--danger)">' +
            '<div style="font-weight:600">❌ 요청 실패</div>' +
            '<div style="color:var(--text-muted);font-size:.85rem;margin-top:4px">' + escapeHtml(e.message || String(e)) + '</div>' +
            '</div>';
          showToast('error', '출고 실패: ' + (e.message || String(e)));
          submitBtn.disabled = false;
          cancelBtn.disabled = false;
        });
    });
  }
  window.showQuickOutboundModal = showQuickOutboundModal;

  /* ===================================================
     8d. 톤백 위치 매핑 (F004) — Excel 업로드 공통 유틸 재사용
     =================================================== */
  function showTonbagLocationUploadModal() {
    _showExcelUploadModal({
      title: '📍 톤백 위치 매핑 — Excel 업로드',
      subtitle: 'Excel 컬럼: <code>lot_no, sub_lt, location, reason(선택), note(선택)</code>',
      endpoint: '/api/tonbag/location-upload',
      onSuccess: function(d) {
        var errHtml = '';
        if (d.errors && d.errors.length) {
          errHtml = '<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--warning)">⚠️ ' + d.errors.length + '건 실패 상세</summary><table class="data-table" style="margin-top:8px;font-size:.85rem"><thead><tr><th>행</th><th>LOT</th><th>sub_lt</th><th>사유</th></tr></thead><tbody>' +
            d.errors.map(function(er){
              return '<tr><td>'+er.row+'</td><td>'+escapeHtml(er.lot_no||'-')+'</td><td>'+(er.sub_lt||'-')+'</td><td>'+escapeHtml(er.reason||'')+'</td></tr>';
            }).join('') + '</tbody></table></details>';
        }
        return '<div style="color:var(--text-muted);font-size:.85rem">파일: ' + escapeHtml(d.filename||'-') +
               ' · 성공 <strong style="color:var(--accent)">' + (d.success_count||0) + '건</strong> / 실패 ' + (d.fail_count||0) +
               ' / 총 ' + (d.total||0) + '</div>' + errHtml;
      }
    });
  }
  window.showTonbagLocationUploadModal = showTonbagLocationUploadModal;

  /* ===================================================
     8e. D/O 후속 연결 (F003) — 단건 필드 업데이트 폼
     =================================================== */
  function showDoUpdateModal() {
    var ALLOWED_FIELDS = [
      ['free_time',         'Free Time'],
      ['con_return',        'Container Return 일자'],
      ['warehouse_name',    '창고명'],
      ['warehouse_code',    '창고 코드'],
      ['arrival_date',      '도착일'],
      ['stock_date',        '입고일'],
      ['place_of_delivery', 'Place of Delivery'],
      ['final_destination', 'Final Destination'],
    ];
    var fieldOpts = ALLOWED_FIELDS.map(function(f){
      return '<option value="' + f[0] + '">' + f[1] + ' (' + f[0] + ')</option>';
    }).join('');

    var html = [
      '<div style="max-width:520px">',
      '  <h2 style="margin:0 0 12px 0">📋 D/O 후속 연결</h2>',
      '  <p style="color:var(--text-muted);margin:0 0 16px 0;font-size:.9rem">',
      '    특정 LOT 의 D/O 필드 값을 수정합니다.',
      '  </p>',
      '  <div style="display:grid;grid-template-columns:110px 1fr;gap:10px;align-items:center;margin-bottom:14px">',
      '    <label style="font-weight:600">LOT 번호</label>',
      '    <input type="text" id="do-lot" placeholder="예: 1126013063" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;font-family:monospace">',
      '    <label style="font-weight:600">필드</label>',
      '    <select id="do-field" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">' + fieldOpts + '</select>',
      '    <label style="font-weight:600">값</label>',
      '    <input type="text" id="do-value" placeholder="" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '  </div>',
      '  <div id="do-result" style="margin-bottom:12px"></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button id="do-cancel-btn" class="btn btn-ghost">닫기</button>',
      '    <button id="do-submit-btn" class="btn btn-primary" disabled>업데이트</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);

    var lot = document.getElementById('do-lot');
    var fld = document.getElementById('do-field');
    var val = document.getElementById('do-value');
    var result = document.getElementById('do-result');
    var submit = document.getElementById('do-submit-btn');
    var cancel = document.getElementById('do-cancel-btn');

    function validate() { submit.disabled = !(lot.value.trim() && fld.value && val.value !== ''); }
    lot.addEventListener('input', validate); val.addEventListener('input', validate); fld.addEventListener('change', validate);

    cancel.addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; });
    submit.addEventListener('click', function(){
      var payload = { lot_no: lot.value.trim(), field: fld.value, value: val.value };
      submit.disabled = true; cancel.disabled = true;
      result.innerHTML = '<div style="padding:8px;color:var(--text-muted)">⏳ 업데이트 중...</div>';
      apiPost('/api/action3/do-update', payload)
        .then(function(res){
          if (res && res.ok !== false) {
            result.innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--success)"><div style="font-weight:600">✅ ' + escapeHtml((res.data && res.data.message) || '업데이트 완료') + '</div></div>';
            showToast('success', 'D/O 업데이트 완료');
            dbgLog('🟢','DO-UPDATE OK', payload.lot_no + ' · ' + payload.field, '#66bb6a');
            if (_currentRoute === 'inventory' && typeof loadInventoryPage === 'function') loadInventoryPage();
          } else {
            var msg = (res && (res.error || res.message)) || '실패';
            result.innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--danger)"><div style="font-weight:600">❌ ' + escapeHtml(msg) + '</div></div>';
            showToast('error', msg);
            submit.disabled = false; cancel.disabled = false;
          }
        })
        .catch(function(e){
          result.innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml(e.message||String(e)) + '</div>';
          showToast('error', '실패: ' + (e.message||String(e)));
          submit.disabled = false; cancel.disabled = false;
        });
    });
  }
  window.showDoUpdateModal = showDoUpdateModal;

  /* ===================================================
     8f. 예약 반영 (승인분) — F022 (단순 확정 모달)
     =================================================== */
  function showApplyApprovedAllocationModal() {
    var html = [
      '<div style="max-width:480px">',
      '  <h2 style="margin:0 0 12px 0">📌 예약 반영 — 승인분 실행</h2>',
      '  <p style="color:var(--text-muted);margin:0 0 16px 0;font-size:.9rem">',
      '    workflow_status = APPROVED 인 Allocation 계획을 톤백 RESERVED 로 실제 반영합니다.',
      '  </p>',
      '  <div id="aa-result" style="margin-bottom:12px;min-height:24px"></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button id="aa-cancel-btn" class="btn btn-ghost">닫기</button>',
      '    <button id="aa-submit-btn" class="btn btn-primary">지금 반영</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);

    var cancel = document.getElementById('aa-cancel-btn');
    var submit = document.getElementById('aa-submit-btn');
    var result = document.getElementById('aa-result');
    cancel.addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; });
    submit.addEventListener('click', function(){
      if (!confirm('승인 완료된 Allocation 을 모두 RESERVED 로 반영합니다. 계속할까요?')) return;
      submit.disabled = true; cancel.disabled = true;
      result.innerHTML = '<div style="padding:8px;color:var(--text-muted)">⏳ 처리 중...</div>';
      apiPost('/api/allocation/apply-approved', {})
        .then(function(res){
          if (res && res.ok) {
            var d = res.data || {};
            result.innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--success)"><div style="font-weight:600">✅ ' + escapeHtml(res.message||'완료') + '</div><div style="color:var(--text-muted);font-size:.85rem;margin-top:4px">반영 건수: <strong>' + (d.applied||0) + '</strong></div></div>';
            showToast('success', res.message || '반영 완료');
          } else {
            var errs = (res && res.data && res.data.errors) || [];
            var msg = (res && (res.message || res.error)) || '실패';
            result.innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--danger)"><div style="font-weight:600">❌ ' + escapeHtml(msg) + '</div>' + (errs.length ? '<ul style="margin:8px 0 0 18px;color:var(--text-muted);font-size:.85rem">' + errs.map(function(e){return '<li>'+escapeHtml(e)+'</li>';}).join('') + '</ul>' : '') + '</div>';
            showToast('error', msg);
            submit.disabled = false; cancel.disabled = false;
          }
        })
        .catch(function(e){
          result.innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml(e.message||String(e)) + '</div>';
          showToast('error', e.message || String(e));
          submit.disabled = false; cancel.disabled = false;
        });
    });
  }
  window.showApplyApprovedAllocationModal = showApplyApprovedAllocationModal;

  /* ===================================================
     8g. 공통 PDF 업로드 모달 (F001, F017 공용)
     =================================================== */
  function _showPdfUploadModal(opts) {
    // opts: {title, subtitle, endpoint, onSuccess(data) → HTML}
    var html = [
      '<div style="max-width:640px">',
      '  <h2 style="margin:0 0 12px 0">' + escapeHtml(opts.title) + '</h2>',
      '  <p style="color:var(--text-muted);margin:0 0 16px 0;font-size:.9rem">',
      '    ' + opts.subtitle,
      '  </p>',
      '  <div id="pdf-drop2-zone" style="border:2px dashed var(--border);border-radius:8px;padding:32px 16px;text-align:center;background:var(--bg-hover);cursor:pointer;margin-bottom:16px">',
      '    <div style="font-size:2.5rem;margin-bottom:8px">📄</div>',
      '    <div id="pdf-drop2-name" style="color:var(--text-muted)">클릭 또는 PDF 파일을 여기에 드롭하세요</div>',
      '  </div>',
      '  <input type="file" id="pdf-drop2-input" accept=".pdf" style="display:none">',
      '  <div id="pdf-drop2-progress" style="display:none;margin-bottom:16px">',
      '    <div style="background:var(--bg-hover);border-radius:4px;height:8px;overflow:hidden">',
      '      <div id="pdf-drop2-bar" style="background:var(--accent);height:100%;width:0%;transition:width .3s"></div>',
      '    </div>',
      '    <div id="pdf-drop2-text" style="font-size:.85rem;color:var(--text-muted);margin-top:4px">준비 중...</div>',
      '  </div>',
      '  <div id="pdf-drop2-result" style="margin-bottom:16px"></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button id="pdf-drop2-cancel" class="btn btn-ghost">닫기</button>',
      '    <button id="pdf-drop2-upload" class="btn btn-primary" disabled>업로드</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);

    var dz = document.getElementById('pdf-drop2-zone');
    var fi = document.getElementById('pdf-drop2-input');
    var nm = document.getElementById('pdf-drop2-name');
    var ub = document.getElementById('pdf-drop2-upload');
    var cb = document.getElementById('pdf-drop2-cancel');
    var pg = document.getElementById('pdf-drop2-progress');
    var bar = document.getElementById('pdf-drop2-bar');
    var tx = document.getElementById('pdf-drop2-text');
    var rb = document.getElementById('pdf-drop2-result');
    var f = null;

    function setFile(x) {
      if (!x) return;
      if (!/\.pdf$/i.test(x.name)) { showToast('error', 'PDF 파일만 가능: ' + x.name); return; }
      f = x;
      nm.innerHTML = '✅ <strong>' + escapeHtml(x.name) + '</strong> (' + Math.round(x.size/1024) + ' KB)';
      ub.disabled = false;
    }
    dz.addEventListener('click', function(){ fi.click(); });
    fi.addEventListener('change', function(e){ if (e.target.files && e.target.files[0]) setFile(e.target.files[0]); });
    dz.addEventListener('dragover', function(e){ e.preventDefault(); dz.style.background='var(--bg-active)'; });
    dz.addEventListener('dragleave', function(){ dz.style.background='var(--bg-hover)'; });
    dz.addEventListener('drop', function(e){ e.preventDefault(); dz.style.background='var(--bg-hover)'; if (e.dataTransfer.files && e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); });
    cb.addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; });

    ub.addEventListener('click', function(){
      if (!f) return;
      ub.disabled = true; cb.disabled = true;
      pg.style.display = 'block'; bar.style.width = '10%'; tx.textContent = '업로드 중...';
      rb.innerHTML = '';

      var form = new FormData();
      form.append('file', f, f.name);
      var xhr = new XMLHttpRequest();
      xhr.open('POST', API + opts.endpoint);
      xhr.upload.onprogress = function(e){
        if (e.lengthComputable) {
          var pct = Math.round((e.loaded/e.total)*70)+10;
          bar.style.width = pct+'%'; tx.textContent = '업로드 중... '+pct+'%';
        }
      };
      xhr.onload = function(){
        bar.style.width='100%'; cb.disabled = false;
        var body; try { body = JSON.parse(xhr.responseText); } catch(e){ body = null; }
        if (xhr.status >= 200 && xhr.status < 300 && body && body.ok) {
          tx.textContent = body.message || '완료';
          var extra = opts.onSuccess ? opts.onSuccess(body.data||{}) : '';
          rb.innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--success)"><div style="font-weight:600;margin-bottom:4px">✅ '+escapeHtml(body.message||'완료')+'</div>'+(extra||'')+'</div>';
          if (body.data && body.data.ai_provider_used === 'openai') {
            showToast('warning', '⚠️ Gemini 한도 초과 → OpenAI 전환됨');
          }
          showToast('success', body.message || '완료');
          dbgLog('🟢','PDF-UPLOAD OK', opts.endpoint, '#66bb6a');
          if (_currentRoute === 'inventory' && typeof loadInventoryPage === 'function') loadInventoryPage();
          if (typeof loadKpi === 'function') loadKpi();
        } else {
          var errMsg = (body && (body.detail || body.error || body.message)) || ('HTTP '+xhr.status);
          if (typeof errMsg === 'object') errMsg = JSON.stringify(errMsg);
          tx.textContent = '실패'; bar.style.background = 'var(--danger)';
          var errExtra = '';
          if (body && body.data && body.data.errors) {
            errExtra = '<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--warning)">⚠️ 상세</summary><pre style="white-space:pre-wrap;font-size:.8rem;margin-top:8px;max-height:240px;overflow:auto">'+escapeHtml(JSON.stringify(body.data.errors, null, 2))+'</pre></details>';
          }
          rb.innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--danger)"><div style="font-weight:600">❌ 실패</div><div style="color:var(--text-muted);font-size:.85rem;margin-top:4px">'+escapeHtml(String(errMsg))+'</div>'+errExtra+'</div>';
          showToast('error', '실패: '+errMsg);
          ub.disabled = false;
        }
      };
      xhr.onerror = function(){
        tx.textContent = '네트워크 에러'; bar.style.background = 'var(--danger)';
        rb.innerHTML = '<div style="padding:12px;color:var(--danger)">네트워크 에러</div>';
        showToast('error', '네트워크 에러');
        ub.disabled = false; cb.disabled = false;
      };
      xhr.send(form);
    });
  }

  /* F001 PDF 스캔 입고 (Packing List) — 레거시 단일 PDF 업로드 (Sprint 1-2 이후 showOneStopInboundModal로 대체) */
  function showPdfInboundUploadModal() {
    _showPdfUploadModal({
      title: '📄 PDF 스캔 입고 (Packing List)',
      subtitle: 'Packing List PDF 파일을 선택하세요. 자동 파싱 후 재고에 등록합니다.',
      endpoint: '/api/inbound/pdf-upload',
      onSuccess: function(d) {
        var errHtml = '';
        if (d.errors && d.errors.length) {
          errHtml = '<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--warning)">⚠️ 실패 ' + d.errors.length + '건</summary><pre style="white-space:pre-wrap;font-size:.8rem;margin-top:8px;max-height:200px;overflow:auto">' + escapeHtml(JSON.stringify(d.errors, null, 2)) + '</pre></details>';
        }
        return '<div style="color:var(--text-muted);font-size:.85rem">파일: ' + escapeHtml(d.filename||'-') +
               ' · Folio: ' + escapeHtml(d.folio||'-') +
               ' · 제품: ' + escapeHtml(d.product||'-') +
               ' · LOT 총 ' + (d.lots_total||0) + '개' +
               ' · <strong style="color:var(--accent)">저장 ' + (d.saved_count||0) + '건</strong>' +
               '</div>' + errHtml;
      }
    });
  }
  window.showPdfInboundUploadModal = showPdfInboundUploadModal;

  /* D/O PDF 업로드 */
  function showDoUploadModal() {
    _showPdfUploadModal({
      title: '📋 D/O PDF 업로드',
      subtitle: 'D/O PDF 파일을 선택하세요. 해당 LOT에 D/O 정보를 업데이트합니다.',
      endpoint: '/api/inbound/do',
      onSuccess: function(d) {
        return '<div style="color:var(--text-muted);font-size:.85rem">파일: '
          + escapeHtml(d.filename||'-') + ' · LOT: ' + escapeHtml(d.lot_no||'-')
          + ' · <strong style="color:var(--accent)">D/O 등록 완료</strong></div>';
      }
    });
  }
  window.showDoUploadModal = showDoUploadModal;

  /* Sales Order Excel 업로드 */
  function showSalesOrderUploadModal() {
    _showExcelUploadModal({
      title: '📊 Sales Order Excel 업로드',
      subtitle: 'Sales Order Excel 파일(.xlsx/.xls)을 선택하세요.',
      endpoint: '/api/action2/sales-order-upload',
      onSuccess: function(d) {
        return '<div style="color:var(--text-muted);font-size:.85rem">파일: '
          + escapeHtml(d.filename||'-') + ' · 처리 ' + (d.count||0) + '건</div>';
      }
    });
  }
  window.showSalesOrderUploadModal = showSalesOrderUploadModal;

  /* ═══ 선사 프로파일 관리 모달 ═══ */
  function showCarrierProfileModal() {
    function _renderCarrierList(profiles) {
      if (!profiles.length) return '<p style="color:var(--text-muted);text-align:center;padding:20px">등록된 선사 프로파일이 없습니다.</p>';
      return '<table class="data-table" style="width:100%;font-size:.88rem"><thead><tr>'
        + '<th>선사 ID</th><th>표시명</th><th>기본품목</th><th>기본중량(kg)</th><th>메모</th><th>액션</th>'
        + '</tr></thead><tbody>'
        + profiles.map(function(p) {
            return '<tr>'
              + '<td style="font-weight:600">' + escapeHtml(p.carrier_id) + '</td>'
              + '<td>' + escapeHtml(p.display_name) + '</td>'
              + '<td>' + escapeHtml(p.default_product || '-') + '</td>'
              + '<td style="text-align:right">' + (p.bag_weight_kg || 500) + '</td>'
              + '<td style="color:var(--text-muted);font-size:.8rem">' + escapeHtml(p.note || '') + '</td>'
              + '<td>'
              + '<button class="btn btn-sm" onclick="window._cpEdit(' + JSON.stringify(p.carrier_id) + ')">✏️</button>'
              + ' <button class="btn btn-sm" style="color:var(--danger)" onclick="window._cpDelete(' + JSON.stringify(p.carrier_id) + ')">🗑</button>'
              + '</td>'
              + '</tr>';
          }).join('')
        + '</tbody></table>';
    }

    function _cpLoad() {
      var listEl = document.getElementById('cp-list');
      if (listEl) listEl.innerHTML = '<p style="color:var(--text-muted);padding:12px">로딩 중...</p>';
      fetch(API + '/api/carriers')
        .then(function(r) { return r.json(); })
        .then(function(d) {
          if (listEl) listEl.innerHTML = _renderCarrierList(d.data || []);
        })
        .catch(function(e) {
          if (listEl) listEl.innerHTML = '<p style="color:var(--danger)">로드 실패: ' + escapeHtml(String(e)) + '</p>';
        });
    }

    var formHtml = [
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">',
      '  <div><label style="font-size:12px;color:var(--text-muted)">선사 ID (필수)</label><input id="cp-f-id" type="text" placeholder="예: Maersk" style="width:100%;margin-top:2px;padding:6px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:4px"></div>',
      '  <div><label style="font-size:12px;color:var(--text-muted)">표시명 (필수)</label><input id="cp-f-name" type="text" placeholder="예: 머스크" style="width:100%;margin-top:2px;padding:6px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:4px"></div>',
      '  <div><label style="font-size:12px;color:var(--text-muted)">기본 품목</label><input id="cp-f-product" type="text" placeholder="예: PP" style="width:100%;margin-top:2px;padding:6px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:4px"></div>',
      '  <div><label style="font-size:12px;color:var(--text-muted)">기본 중량(kg)</label><input id="cp-f-weight" type="number" value="500" min="1" style="width:100%;margin-top:2px;padding:6px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:4px"></div>',
      '  <div style="grid-column:1/-1"><label style="font-size:12px;color:var(--text-muted)">메모</label><input id="cp-f-note" type="text" placeholder="특이사항 (선택)" style="width:100%;margin-top:2px;padding:6px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:4px"></div>',
      '</div>',
      '<button class="btn btn-primary" onclick="window._cpSave()">💾 저장</button>',
    ].join('');

    var html = [
      '<div style="max-width:760px">',
      '<h2 style="margin:0 0 16px 0">🚢 선사 프로파일 관리</h2>',
      '<p style="color:var(--text-muted);font-size:.85rem;margin:0 0 16px 0">선사별 기본 품목·중량을 설정합니다. OneStop 입고 시 선사 선택만으로 파싱 기준값이 자동 적용됩니다.</p>',
      '<h3 style="margin:0 0 8px 0;font-size:.95rem">신규 등록 / 수정</h3>',
      formHtml,
      '<hr style="border:none;border-top:1px solid var(--border);margin:16px 0">',
      '<h3 style="margin:0 0 8px 0;font-size:.95rem">등록된 선사 프로파일</h3>',
      '<div id="cp-list">로딩 중...</div>',
      '</div>',
    ].join('');

    showDataModal('', html);
    _cpLoad();

    window._cpSave = function() {
      var id      = (document.getElementById('cp-f-id')      || {}).value || '';
      var name    = (document.getElementById('cp-f-name')    || {}).value || '';
      var product = (document.getElementById('cp-f-product') || {}).value || '';
      var weight  = parseFloat((document.getElementById('cp-f-weight') || {}).value || '500') || 500;
      var note    = (document.getElementById('cp-f-note')    || {}).value || '';
      if (!id.trim()) { showToast('error', '선사 ID를 입력하세요'); return; }
      if (!name.trim()) { showToast('error', '표시명을 입력하세요'); return; }
      var isEdit = window._cpEditId && window._cpEditId === id.trim();
      var method = isEdit ? 'PUT' : 'POST';
      var url    = isEdit ? (API + '/api/carriers/' + encodeURIComponent(id.trim())) : (API + '/api/carriers');
      fetch(url, { method: method, headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ carrier_id: id.trim(), display_name: name.trim(),
          default_product: product.trim(), bag_weight_kg: weight, note: note.trim() }) })
        .then(function(r) { return r.json(); })
        .then(function(d) {
          if (d.ok || d.success) {
            showToast('success', (isEdit ? '수정' : '등록') + ' 완료: ' + id.trim());
            window._cpEditId = null;
            ['cp-f-id','cp-f-name','cp-f-product','cp-f-note'].forEach(function(fid){
              var el = document.getElementById(fid); if (el) el.value = '';
            });
            var wEl = document.getElementById('cp-f-weight'); if (wEl) wEl.value = '500';
            _cpLoad();
          } else { showToast('error', d.detail || d.message || '저장 실패'); }
        })
        .catch(function(e) { showToast('error', '네트워크 오류: ' + String(e)); });
    };

    window._cpEdit = function(cid) {
      fetch(API + '/api/carriers/' + encodeURIComponent(cid))
        .then(function(r) { return r.json(); })
        .then(function(p) {
          window._cpEditId = cid;
          var set = function(id, v) { var el = document.getElementById(id); if (el) el.value = v; };
          set('cp-f-id',      p.carrier_id || '');
          set('cp-f-name',    p.display_name || '');
          set('cp-f-product', p.default_product || '');
          set('cp-f-weight',  p.bag_weight_kg || 500);
          set('cp-f-note',    p.note || '');
          showToast('info', cid + ' 수정 모드');
        })
        .catch(function(e) { showToast('error', '조회 실패: ' + String(e)); });
    };

    window._cpDelete = function(cid) {
      if (!confirm(cid + ' 프로파일을 삭제하시겠습니까?')) return;
      fetch(API + '/api/carriers/' + encodeURIComponent(cid), { method: 'DELETE' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
          if (d.ok || d.success) { showToast('success', cid + ' 삭제 완료'); _cpLoad(); }
          else { showToast('error', d.detail || '삭제 실패'); }
        })
        .catch(function(e) { showToast('error', '네트워크 오류: ' + String(e)); });
    };
  }
  window.showCarrierProfileModal = showCarrierProfileModal;

  /* =====================================================================
     [Sprint 1-2-A] OneStop Inbound — 4슬롯 wizard 모달
     ─────────────────────────────────────────────────────────────────────
     v864-2 source : gui_app_modular/dialogs/onestop_inbound.py (4302줄)
     v864-2 DOC_TYPES: [BL 필수, PACKING_LIST 필수, INVOICE 필수, DO 선택]

     이 Phase(A)에서 구현:
       ✅ 4단계 Wizard 스텝 표시
       ✅ 템플릿/선사 Combobox (placeholder — Sprint 2에서 CRUD 연결)
       ✅ 4 업로드 슬롯 (BL/PL/Invoice/DO) + 파일 선택 + 상태 표시
       ✅ 파싱 시작 / 다시 파싱 / 멀티 선택 / D/O 나중에 버튼
       ✅ 진행 상태 영역
       ✅ 필터 바 + 18열 미리보기 테이블 (뼈대)
       ✅ BL PDF 1장만 기존 /api/inbound/pdf-upload 로 파싱 (fallback)

     다음 Phase(B)에서 추가:
       🟡 백엔드 /api/inbound/onestop-upload (4종 multipart)
       🟡 4종 크로스체크 검증 (5 weight 소수 일치 등)
       🟡 18열 실데이터 미리보기
       🟡 인라인 편집 + Undo/Redo + 서브팝업 4개
     ===================================================================== */
  var _onestopState = {
    files: { BL: null, PACKING_LIST: null, INVOICE: null, DO: null },
    template: null,
    carrier: '',
    product: '',
    productCode: '',
    step: 1,
    /* [Sprint 1-2-C] 편집 상태 */
    previewRows: [],        /* 현재 미리보기 rows (편집 반영됨) */
    originalRows: [],       /* 원본 백업 — 편집 롤백용 */
    editedCells: {},        /* { "rowIdx.field": true } — 편집된 셀 표시용 */
    parsed: false,          /* 파싱 완료 여부 (true면 DB 업로드 가능) */
    /* [Sprint 1-2-D] Undo/Redo + D/O 수동 정보 */
    history: [],            /* [{rowIdx, field, oldVal, newVal}, ...] max 50 */
    historyIdx: -1,         /* 현재 위치 (stack pointer) */
    manualDo: null,         /* D/O 미첨부 시 수동 입력 정보 {free_time, warehouse, arrival_date} */
  };
  var ONESTOP_MAX_HISTORY = 50;
  /* [Sprint 1-2-C] 편집 가능 컬럼 (18열 중 — v864-2 EDITABLE_COLS 참고) */
  var ONESTOP_EDITABLE_FIELDS = new Set([
    'lot_no', 'sap_no', 'bl_no', 'product', 'container', 'code',
    'lot_sqm', 'mxbg', 'net_kg', 'gross_kg',
    'invoice_no', 'ship_date', 'arrival', 'con_return', 'free_time', 'wh'
  ]);
  /* 읽기 전용: no (순번), status (NEW 고정) */
  var ONESTOP_DOC_TYPES = [
    { key: 'BL',           icon: '🚢', seq: '①', name: 'Bill of Loading',  required: true  },
    { key: 'PACKING_LIST', icon: '📦', seq: '②', name: 'Packing List',     required: true  },
    { key: 'INVOICE',      icon: '📄', seq: '③', name: 'Invoice, FA',      required: true  },
    { key: 'DO',           icon: '📋', seq: '④', name: 'Delivery Order',   required: false },
  ];
  var ONESTOP_PREVIEW_COLS = [
    'NO','LOT NO','SAP NO','BL NO','PRODUCT','STATUS','CONTAINER','CODE',
    'LOT SQM','MXBG','NET(Kg)','GROSS(kg)','INVOICE NO','SHIP DATE','ARRIVAL',
    'CON RETURN','FREE TIME','WH'
  ];

  /* ─── 파싱 결과 플로팅 창 ─────────────────────── */
  var _parseResultPanel = null;
  function _ensureParseResultWindow() {
    if (_parseResultPanel && document.body.contains(_parseResultPanel)) {
      _parseResultPanel.style.display = 'flex';
      return _parseResultPanel;
    }
    var _fHtml = ['SAP','BL','CONTAINER','PRODUCT','STATUS'].map(function(f){
      return '<label style="font-size:11px;color:var(--text-muted)">' + f + ':</label>'
        + '<input type="text" id="onestop-filter-' + f.toLowerCase()
        + '" placeholder=" " oninput="window.onestopApplyFilter&&window.onestopApplyFilter()"'
        + ' style="padding:3px 6px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:4px;font-size:11px;width:90px">';
    }).join('');
    var _pH = ONESTOP_PREVIEW_COLS.map(function(cc){ return '<th>' + cc + '</th>'; }).join('');
    var p = document.createElement('div');
    p.id = 'sqm-parse-result';
    p.style.cssText = 'position:fixed;top:55px;left:50%;transform:translateX(-50%);'
      + 'width:min(1450px,96vw);height:84vh;background:var(--bg-card);'
      + 'border:2px solid var(--accent,#4fc3f7);border-radius:10px;'
      + 'box-shadow:0 8px 40px rgba(0,0,0,.6);z-index:10050;'
      + 'display:flex;flex-direction:column;overflow:visible;';
    var hdr = document.createElement('div');
    hdr.id = 'sqm-parse-result-hdr';
    hdr.style.cssText = 'flex-shrink:0;cursor:move;user-select:none;background:var(--bg-hover);'
      + 'border-radius:10px 10px 0 0;border-bottom:1px solid var(--panel-border);'
      + 'padding:6px 52px 6px 14px;display:flex;align-items:center;gap:8px;'
      + 'min-height:34px;position:relative;';
    hdr.innerHTML = '<span style="font-size:15px;font-weight:700;color:var(--accent)">📊 파싱 결과</span>'
      + '<span id="parse-result-title" style="font-size:11px;color:var(--text-muted)"></span>'
      + '<button onclick="document.getElementById(\'sqm-parse-result\').style.display=\'none\'" '
      + 'style="position:absolute;top:4px;right:10px;background:none;border:none;'
      + 'font-size:1.4rem;cursor:pointer;color:var(--text-muted);">×</button>';
    var bdy = document.createElement('div');
    bdy.style.cssText = 'flex:1 1 auto;display:flex;flex-direction:column;overflow:hidden;padding:10px 14px;gap:6px;';
    bdy.innerHTML =
      '<div class="onestop-edit-toolbar" style="display:flex;align-items:center;gap:6px;'
      + 'padding:6px 10px;background:var(--panel);border:1px solid var(--panel-border);'
      + 'border-radius:6px;flex-wrap:wrap;flex-shrink:0">'
      + '<span style="font-weight:700;color:var(--text-muted);font-size:12px">✏️ 편집:</span>'
      + '<button class="btn" id="onestop-undo-btn" onclick="window.onestopUndo()" disabled>↶ 되돌리기</button>'
      + '<button class="btn" id="onestop-redo-btn" onclick="window.onestopRedo()" disabled>↷ 다시 실행</button>'
      + '<button class="btn" id="onestop-reset-btn" onclick="window.onestopResetAll()" disabled>⟲ 원본 초기화</button>'
      + '<span style="width:1px;height:20px;background:var(--panel-border);margin:0 2px"></span>'
      + '<button class="btn btn-wip" onclick="window.onestopTemplateSave()">📋 템플릿 저장</button>'
      + '<button class="btn btn-wip" onclick="window.onestopTemplateLoad()">📋 템플릿 선택</button>'
      + '<span class="hint" style="margin-left:auto;color:var(--text-muted);font-size:11px">셀 더블클릭 → Enter 저장 · Esc 취소</span>'
      + '</div>'
      + '<div class="onestop-filter-bar" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;flex-shrink:0">'
      + '<span style="font-weight:700;font-size:12px">▼ 필터:</span>' + _fHtml
      + '<button class="btn" onclick="window.onestopResetFilter()" style="margin-left:auto">✖ 초기화</button>'
      + '</div>'
      + '<div style="flex:1 1 auto;overflow-x:auto;overflow-y:auto;">'
      + '<table class="onestop-preview-table" style="min-width:1200px">'
      + '<thead><tr>' + _pH + '</tr></thead>'
      + '<tbody id="onestop-preview-body">'
      + '<tr><td colspan="' + ONESTOP_PREVIEW_COLS.length + '" class="onestop-preview-empty">📭 파싱 대기 중...</td></tr>'
      + '</tbody></table></div>'
      + '<div style="display:flex;gap:8px;justify-content:flex-end;flex-shrink:0;padding-top:6px">'
      + '<button class="btn btn-ghost" onclick="document.getElementById(\'sqm-parse-result\').style.display=\'none\'">❌ 닫기</button>'
      + '<button class="btn btn-primary" id="onestop-save-btn" onclick="window.onestopSaveDb()" disabled>📤 DB 업로드</button>'
      + '</div>';
    p.appendChild(hdr); p.appendChild(bdy);
    document.body.appendChild(p);
    _makeDraggableResizable(p, hdr);
    _parseResultPanel = p;
    return p;
  }
  function _openParseResultWindow(carrier, lotCount) {
    var pw = _ensureParseResultWindow();
    pw.style.display = 'flex';
    var ttl = document.getElementById('parse-result-title');
    if (ttl) ttl.textContent = carrier
      ? ' — ' + carrier + (lotCount != null ? ' (' + lotCount + ' LOT)' : '') : '';
  }

  function showOneStopInboundModal() {
    /* 상태 초기화 */
    _onestopState.files = { BL: null, PACKING_LIST: null, INVOICE: null, DO: null };
    _onestopState.product = '';
    _onestopState.productCode = '';
    _onestopState.step = 1;

    var slotsHtml = ONESTOP_DOC_TYPES.map(function(dt){
      return (
        '<div class="upload-slot" id="onestop-slot-' + dt.key + '">' +
          '<div class="upload-slot-icon">' + dt.icon + '</div>' +
          '<div class="upload-slot-label">' + dt.seq + ' ' + escapeHtml(dt.name) +
            ' <span class="upload-slot-req ' + (dt.required ? 'required' : 'optional') + '">' +
            (dt.required ? '필수' : '선택') + '</span>' +
            '<small class="upload-slot-filename" id="onestop-filename-' + dt.key + '"></small>' +
          '</div>' +
          '<button class="upload-slot-pick-btn" onclick="window.onestopPickFile(\'' + dt.key + '\')">📂 파일 선택</button>' +
          '<input type="file" id="onestop-input-' + dt.key + '" accept=".pdf" style="display:none" onchange="window.onestopOnFileChange(\'' + dt.key + '\', this)">' +
          '<span class="upload-slot-status" id="onestop-status-' + dt.key + '">○</span>' +
        '</div>'
      );
    }).join('');

    var html = [
      '<div class="onestop-modal">',
      '  <h2 style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">📥 입고 — SQM v8.6.5 (OneStop)'
      +'<span id="onestop-step-badge" style="font-size:12px;font-weight:600;padding:2px 12px;border-radius:20px;background:var(--sidebar-active-bg,#3b82f6);color:var(--sidebar-active-fg,#fff);white-space:nowrap;">① 서류 선택</span></h2>',
      /* 템플릿 줄 */
      '  <div class="onestop-row">',
      '    <label>적용 템플릿:</label>',
      '    <select id="onestop-template" disabled><option value="">— 템플릿 없음 —</option></select>',
      '    <span class="chip">Sprint 2 예정</span>',
      '    <button class="btn" style="margin-left:auto" onclick="window.onestopSkipDo()">📋 D/O 나중에</button>',
      '  </div>',
      /* 선사 줄 */
      '  <div class="onestop-row">',
      '    <label>🚢 선사:</label>',
      '    <select id="onestop-carrier" onchange="window.onestopCarrierChange(this.value)" style="padding:6px;flex:1;max-width:280px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:6px;font-weight:600"><option value="">— 로딩 중... —</option></select>',
      '    <button class="btn" onclick="window.onestopReparseCarrier()" disabled>🚢 선사 재파싱</button>',
      '  </div>',
      /* 품목 줄 */
      '  <div class="onestop-row">',
      '    <label>📦 품목:</label>',
      '    <select id="onestop-product" onchange="window.onestopProductChange(this)" style="padding:6px;flex:1;max-width:420px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:6px;font-weight:600"><option value="">— 품목 로딩 중... —</option></select>',
      '    <span class="hint" style="font-size:11px;color:var(--text-muted)">선택값이 미리보기 PRODUCT 열과 DB 품목에 반영됩니다</span>',
      '  </div>',
      /* 힌트 줄 — 업로드 시점 한 줄 메모 (저장 안 됨, Gemini 파싱 보조) */
      '  <div class="onestop-row">',
      '    <label>💬 힌트:</label>',
      '    <input id="onestop-hint-input" type="text" placeholder="LOT/BL 특이사항 입력 (선택, DB 저장 안 됨)" style="flex:1;padding:6px 10px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:6px;font-size:13px">',
      '  </div>',
      /* manual date inputs row */
      '  <div class="onestop-row" id="onestop-dates-row">',
      '    <label style="white-space:nowrap">📅 날짜:</label>',
      '    <span style="display:flex;gap:6px;flex:1;align-items:center;flex-wrap:wrap">',
      '      <span style="font-size:11px;color:var(--text-muted)">ARRIVAL</span>',
      '      <input id="onestop-arrival-input" type="date" onchange="window.onestopCalcFreeTime()" style="padding:4px 8px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:6px;font-size:12px">',
      '      <span style="font-size:11px;color:var(--text-muted)">CON RETURN</span>',
      '      <input id="onestop-conreturn-input" type="date" onchange="window.onestopCalcFreeTime()" style="padding:4px 8px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:6px;font-size:12px">',
      '      <span style="font-size:11px;color:var(--text-muted)">FREE TIME</span>',
      '      <input id="onestop-freetime-display" type="text" readonly placeholder="자동" style="width:56px;padding:4px 6px;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:6px;font-size:12px;text-align:center">',
      '      <span style="font-size:11px;color:var(--text-muted)">일</span>',
      '    </span>',
      '  </div>',
            /* 템플릿 상태 행 */
      '  <div class="onestop-row" id="onestop-template-row" style="display:none">',
      '    <label>📋 템플릿:</label>',
      '    <span id="onestop-tpl-label" style="flex:1;padding:4px 10px;background:var(--bg-hover);border:1px solid var(--border);border-radius:6px;font-size:12px;color:var(--text-muted)">미선택</span>',
      '    <button class="btn btn-sm" onclick="window.onestopOpenTemplatePicker()">📋 선택/수정</button>',
      '  </div>',
      /* DB 파싱 템플릿 행 */
      '  <div class="onestop-row" id="onestop-db-tpl-row">',
      '    <label>🏋️ 파싱 템플릿:</label>',
      '    <span id="onestop-db-tpl-label" style="flex:1;padding:5px 10px;background:var(--bg-hover);border:1px solid var(--danger,#f44336);border-radius:6px;font-size:12px;color:var(--danger,#f44336);font-weight:600">❌ 미설정 (파싱 전 선택 필수)</span>',
      '    <button class="btn btn-sm" onclick="window.onestopOpenDbTemplatePicker()">📋 DB 템플릿 선택</button>',
      '  </div>',
      /* 4 업로드 슬롯 */
      '  <div class="upload-slots">' + slotsHtml + '</div>',
      /* 액션 버튼 */
      '  <div class="onestop-actions">',
      '    <button class="btn" onclick="window.onestopMultiPick()">📁 멀티 선택</button>',
      '    <button class="btn btn-primary" id="onestop-parse-btn" onclick="window.onestopParseStart()" disabled>▶ 파싱 시작</button>',
      '    <button class="btn" id="onestop-reparse-btn" onclick="window.onestopParseRedo()" disabled>↻ 다시 파싱</button>',
      '    <span class="hint" id="onestop-hint">💡 최소 Packing List를 선택하세요</span>',
      '  </div>',
      /* 진행 상태 */
      '  <div class="onestop-progress">',
      '    <div class="onestop-progress-title">📊 진행 상태</div>',
      '    <div id="onestop-progress-body" class="onestop-progress-empty">파싱을 시작하면 진행 상황이 여기에 표시됩니다.</div>',
      '  </div>',
      /* 결과는 별도 플로팅 창 (_ensureParseResultWindow) */
      '  <div id="onestop-result-hint" style="padding:10px 14px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-top:4px;color:var(--text-muted);font-size:12px;text-align:center">📊 파싱 시작 후 결과가 별도 창에 표시됩니다</div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px">',
      '    <button class="btn btn-ghost" onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'">❌ 닫기</button>',
      '  </div>',
      '</div>'
    ].join('\n');

    showDataModal('', html);
    _onestopLoadCarriers();
    _onestopLoadProducts();
  }
  window.showOneStopInboundModal = showOneStopInboundModal;

  /* ── 슬롯 핸들러 ─────────────────────────────────────────────────── */
  window.onestopPickFile = function(docKey) {
    var input = document.getElementById('onestop-input-' + docKey);
    if (input) input.click();
  };
  window.onestopOnFileChange = function(docKey, inputEl) {
    if (!inputEl.files || !inputEl.files[0]) return;
    var f = inputEl.files[0];
    if (!/\.pdf$/i.test(f.name)) { showToast('error', 'PDF 파일만 가능: ' + f.name); return; }
    _onestopState.files[docKey] = f;
    var slot = document.getElementById('onestop-slot-' + docKey);
    var nameEl = document.getElementById('onestop-filename-' + docKey);
    var statusEl = document.getElementById('onestop-status-' + docKey);
    if (slot) slot.classList.add('filled');
    if (nameEl) nameEl.textContent = f.name + ' (' + Math.round(f.size/1024) + ' KB)';
    if (statusEl) statusEl.textContent = '✓';
    _onestopUpdateEnableState();
  };
  function _onestopUpdateEnableState() {
    var s = _onestopState.files;
    /* 최소 Packing List 필수 */
    var canParse = !!s.PACKING_LIST;
    var parseBtn = document.getElementById('onestop-parse-btn');
    var hint = document.getElementById('onestop-hint');
    if (parseBtn) parseBtn.disabled = !canParse;
    if (hint) {
      if (!s.PACKING_LIST) hint.textContent = '💡 최소 Packing List(PL)를 선택하세요';
      else if (!s.BL || !s.INVOICE) hint.textContent = '⚠️ BL/Invoice 없음 — 크로스체크 제한 (파싱은 가능)';
      else if (!s.DO) hint.textContent = 'ℹ️ D/O 선택 — 나중에 첨부 가능';
      else hint.textContent = '✅ 4종 준비 완료 — 크로스체크 실행 가능';
    }
  }
  window.onestopMultiPick = function() {
    /* 기존 hidden input 재활용 or 신규 생성 */
    var inp = document.getElementById('onestop-multi-input');
    if (!inp) {
      inp = document.createElement('input');
      inp.type = 'file';
      inp.id   = 'onestop-multi-input';
      inp.accept = '.pdf';
      inp.multiple = true;
      inp.style.display = 'none';
      document.body.appendChild(inp);
      inp.addEventListener('change', function() {
        var files = Array.prototype.slice.call(inp.files);
        if (!files.length) return;

        /* 파일명 키워드 → 슬롯 자동 감지 */
        var RULES = [
          { key: 'BL',           kw: /\b(b[\/\-]?l|bill.?of.?lading|하선신고)\b/i },
          { key: 'PACKING_LIST', kw: /\b(p[\/\-]?l|packing.?list|팩킹)\b/i },
          { key: 'INVOICE',      kw: /\b(fa|inv|invoice|상업송장|commercial)\b/i },
          { key: 'DO',           kw: /\b(d[\/\-]?o|delivery.?order|화물인도|도착통지)\b/i },
        ];

        var assigned   = {};   /* key -> File */
        var unmatched  = [];   /* 자동 배정 실패 파일 목록 */

        files.forEach(function(f) {
          var name = f.name.replace(/\.pdf$/i, '');
          var matched = false;
          for (var i = 0; i < RULES.length; i++) {
            var r = RULES[i];
            if (r.kw.test(name) && !assigned[r.key]) {
              assigned[r.key] = f;
              matched = true;
              break;
            }
          }
          if (!matched) unmatched.push(f.name);
        });

        /* 슬롯에 배정 */
        /* 고정 순서: BL → PL → FA → DO */
        var SLOT_ORDER = ['BL', 'PACKING_LIST', 'INVOICE', 'DO'];

        /* 폴백: 감지 못한 파일 → 순서대로 빈 슬롯에 배정 */
        if (unmatched.length) {
          var unmatchedFiles = files.filter(function(f) {
            return unmatched.indexOf(f.name) !== -1;
          });
          SLOT_ORDER.forEach(function(key) {
            if (!assigned[key] && unmatchedFiles.length) {
              assigned[key] = unmatchedFiles.shift();
            }
          });
          unmatched = [];   /* 폴백으로 전부 소진 */
        }

        /* BL→PL→FA→DO 순으로 슬롯 반영 */
        var count = 0;
        SLOT_ORDER.forEach(function(key) {
          var f2 = assigned[key];
          if (!f2) return;
          _onestopState.files[key] = f2;
          var slot   = document.getElementById('onestop-slot-'     + key);
          var nameEl = document.getElementById('onestop-filename-' + key);
          var stEl   = document.getElementById('onestop-status-'   + key);
          if (slot)   slot.classList.add('filled');
          if (nameEl) nameEl.textContent = f2.name + ' (' + Math.round(f2.size/1024) + ' KB)';
          if (stEl)   stEl.textContent  = '✓';
          count++;
        });
        _onestopUpdateEnableState();
        inp.value = '';   /* 동일 파일 재선택 허용 */

        if (count > 0) {
          showToast('success', '📁 ' + count + '개 배정 완료 (BL→PL→FA→DO 순)');
        } else {
          showToast('warning', '⚠️ 파일을 선택하지 않았습니다.');
        }
      });
    }
    inp.click();
  };

  /* [Sprint 1-2-D] D/O 나중에 — 수동 정보 입력 프롬프트 체인 */
  window.onestopSkipDo = function() {
    var cur = _onestopState.manualDo || {};
    var ft = prompt('📋 D/O 수동 입력 (1/3) — Free Time (일수)\n\n예: 7\n(취소 → 전체 입력 취소)', cur.free_time || '');
    if (ft === null) return;
    ft = String(ft || '').trim();
    var wh = prompt('📋 D/O 수동 입력 (2/3) — 창고명\n\n예: 광양창고\n(빈값 허용)', cur.warehouse || '');
    if (wh === null) return;
    wh = String(wh || '').trim();
    var ar = prompt('📋 D/O 수동 입력 (3/3) — 도착일 (YYYY-MM-DD)\n\n예: 2026-04-20\n(빈값 허용)', cur.arrival_date || '');
    if (ar === null) return;
    ar = String(ar || '').trim();
    /* 도착일 형식 검증 (빈값 OK, 입력된 경우 YYYY-MM-DD) */
    if (ar && !/^\d{4}-\d{2}-\d{2}$/.test(ar)) {
      if (!confirm('도착일 형식이 YYYY-MM-DD가 아닙니다: "' + ar + '"\n그래도 저장하시겠습니까?')) return;
    }
    _onestopState.manualDo = { free_time: ft, warehouse: wh, arrival_date: ar };
    /* 파싱된 rows 가 있으면 DO 누락 필드에 수동 값 채우기 */
    if (_onestopState.parsed && _onestopState.previewRows.length) {
      _onestopState.previewRows.forEach(function(r, i){
        if (!r) return;
        if (ft && !r.free_time)  { r.free_time = ft;  _onestopState.editedCells[i + '.free_time'] = true; }
        if (wh && !r.wh)          { r.wh = wh;         _onestopState.editedCells[i + '.wh'] = true; }
        if (ar && !r.arrival)     { r.arrival = ar;    _onestopState.editedCells[i + '.arrival'] = true; }
      });
      _onestopRenderPreview(_onestopState.previewRows);
    }
    showToast('success',
      'D/O 수동 정보 저장됨 — Free Time=' + (ft || '-') +
      ' / 창고=' + (wh || '-') +
      ' / 도착=' + (ar || '-') +
      (_onestopState.parsed ? ' · 미리보기 반영됨' : ' (파싱 후 적용)')
    );
  };

  window.onestopReparseCarrier = function() {
    showToast('info', '선사 재파싱은 Sprint 2 (선사별 템플릿 재적용) 이후 연결됩니다');
  };

  /* [Sprint 1-2-D] Undo / Redo — 편집 이력 50-stack */
  window.onestopUndo = function() {
    if (_onestopState.historyIdx < 0) { showToast('info', '되돌릴 작업이 없습니다'); return; }
    var entry = _onestopState.history[_onestopState.historyIdx];
    if (!_onestopState.previewRows[entry.rowIdx]) _onestopState.previewRows[entry.rowIdx] = {};
    _onestopState.previewRows[entry.rowIdx][entry.field] = entry.oldVal;
    /* editedCells 재계산 */
    var origVal = (_onestopState.originalRows[entry.rowIdx] || {})[entry.field];
    var cellKey = entry.rowIdx + '.' + entry.field;
    if (String(entry.oldVal) !== String(origVal == null ? '' : origVal)) {
      _onestopState.editedCells[cellKey] = true;
    } else {
      delete _onestopState.editedCells[cellKey];
    }
    _onestopState.historyIdx--;
    _onestopRenderPreview(_onestopState.previewRows);
    _onestopUpdateHistoryButtons();
    showToast('info', '↶ 되돌림: ' + entry.field + ' · row ' + (entry.rowIdx + 1));
  };

  window.onestopRedo = function() {
    if (_onestopState.historyIdx >= _onestopState.history.length - 1) {
      showToast('info', '다시 실행할 작업이 없습니다');
      return;
    }
    _onestopState.historyIdx++;
    var entry = _onestopState.history[_onestopState.historyIdx];
    if (!_onestopState.previewRows[entry.rowIdx]) _onestopState.previewRows[entry.rowIdx] = {};
    _onestopState.previewRows[entry.rowIdx][entry.field] = entry.newVal;
    var origVal = (_onestopState.originalRows[entry.rowIdx] || {})[entry.field];
    var cellKey = entry.rowIdx + '.' + entry.field;
    if (String(entry.newVal) !== String(origVal == null ? '' : origVal)) {
      _onestopState.editedCells[cellKey] = true;
    } else {
      delete _onestopState.editedCells[cellKey];
    }
    _onestopRenderPreview(_onestopState.previewRows);
    _onestopUpdateHistoryButtons();
    showToast('info', '↷ 다시 실행: ' + entry.field + ' · row ' + (entry.rowIdx + 1));
  };

  window.onestopResetAll = function() {
    if (!_onestopState.history.length) { showToast('info', '편집 내역이 없습니다'); return; }
    if (!confirm('⟲ 원본 초기화\n\n모든 편집 내용을 파싱 직후 상태로 되돌립니다. 계속하시겠습니까?')) return;
    _onestopState.previewRows = JSON.parse(JSON.stringify(_onestopState.originalRows));
    _onestopState.editedCells = {};
    _onestopState.history = [];
    _onestopState.historyIdx = -1;
    _onestopRenderPreview(_onestopState.previewRows);
    _onestopUpdateHistoryButtons();
    showToast('success', '원본 상태로 초기화되었습니다');
  };

  /* [Sprint 1-2-D] Sprint 2 에서 구현될 기능 플레이스홀더 */
  window.onestopTemplateSave = function() {
    showToast('info', '📋 현재 파싱 설정 → 템플릿 저장: Sprint 2 (InboundTemplateDialog CRUD) 이후 활성화');
  };
  window.onestopTemplateLoad = function() {
    showToast('info', '📋 파싱 템플릿 선택: Sprint 2 (InboundTemplateDialog CRUD) 이후 활성화');
  };
  window.onestopParseErrorRecovery = function(docType, errorCode) {
    showToast('info', (docType || 'PDF') + ' 파싱 오류 복구 (9 ERROR_CODES): Sprint 2 (ParseErrorRecoveryDialog) 이후 활성화');
  };

  /* Undo/Redo 버튼 상태 갱신 */
  function _onestopUpdateHistoryButtons() {
    var undoBtn = document.getElementById('onestop-undo-btn');
    var redoBtn = document.getElementById('onestop-redo-btn');
    var resetBtn = document.getElementById('onestop-reset-btn');
    var canUndo = _onestopState.historyIdx >= 0;
    var canRedo = _onestopState.historyIdx < _onestopState.history.length - 1;
    var hasHistory = _onestopState.history.length > 0;
    if (undoBtn)  undoBtn.disabled  = !canUndo;
    if (redoBtn)  redoBtn.disabled  = !canRedo;
    if (resetBtn) resetBtn.disabled = !hasHistory;
    /* 카운터 표시 */
    if (undoBtn) undoBtn.title = '되돌리기 (Ctrl+Z) · 이력 ' + (_onestopState.historyIdx + 1) + '/' + _onestopState.history.length;
    if (redoBtn) redoBtn.title = '다시 실행 (Ctrl+Y) · ' + Math.max(0, _onestopState.history.length - _onestopState.historyIdx - 1) + '단계 남음';
  }
  window.onestopResetFilter = function() {
    ['sap','bl','container','product','status'].forEach(function(k){
      var el = document.getElementById('onestop-filter-' + k);
      if (el) el.value = '';
    });
  };


  /* ═══════════════════════════════════════════════════════════════════
     Carrier Template System  (v865 — 선사별 템플릿 관리)
     localStorage: sqm_tpl_{carrier}  → JSON array
     window._onestopActiveTemplate : 현재 적용 템플릿
     Template: { name, lot_sqm, mxbg, product_name, sap_no, notes }
  ═══════════════════════════════════════════════════════════════════ */
  window._onestopActiveTemplate = null;
  window._onestopBagWeight      = null;  // DB템플릿 bag_weight_kg — null=미선택
  window._onestopGeminiHint     = '';    // DB템플릿 gemini_hint_packing
  window._onestopDbTemplateId   = null;  // DB템플릿 ID (로깅용)
  window._onestopDbTemplateName = '';    // 화면 표시용 이름

  function _tplKey(carrier) {
    return 'sqm_tpl_' + (carrier || '').replace(/\s+/g, '_');
  }
  function _loadTplList(carrier) {
    try { return JSON.parse(localStorage.getItem(_tplKey(carrier)) || '[]'); }
    catch(e) { return []; }
  }
  function _saveTplList(carrier, list) {
    try { localStorage.setItem(_tplKey(carrier), JSON.stringify(list)); } catch(e) {}
  }
  function _applyTemplate(tpl, carrier) {
    window._onestopActiveTemplate = tpl;
    var lbl = document.getElementById('onestop-tpl-label');
    if (lbl) {
      lbl.textContent = tpl ? ('OK ' + tpl.name) : '미선택';
      lbl.style.color = tpl ? 'var(--success)' : 'var(--text-muted)';
      lbl.style.fontWeight = tpl ? '600' : 'normal';
    }
    if (tpl) showToast('success', '템플릿 적용: ' + tpl.name);
  }

  /* 선사 선택 시 자동 호출 */
  /* 선사 프로파일에서 동적 로딩 — 없으면 기본 11개 폴백 */
  var _CARRIER_FALLBACK = ['Maersk','ONE','Evergreen','HMM','MSC',
    'CMA CGM','Hapag-Lloyd','Yang Ming','ZIM','PIL','Wan Hai'];
  function _onestopLoadCarriers() {
    var sel = document.getElementById('onestop-carrier');
    if (!sel) return;
    fetch(API + '/api/carriers')
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(d) {
        var profiles = (d && d.data && d.data.length) ? d.data : null;
        var opts = '<option value="">— 선사 선택 (필수) —</option>';
        if (profiles) {
          opts += profiles.map(function(p) {
            return '<option value="' + escapeHtml(p.carrier_id) + '">' + escapeHtml(p.display_name || p.carrier_id) + '</option>';
          }).join('');
        } else {
          opts += _CARRIER_FALLBACK.map(function(n) {
            return '<option>' + escapeHtml(n) + '</option>';
          }).join('');
        }
        sel.innerHTML = opts;
      })
      .catch(function() {
        sel.innerHTML = '<option value="">— 선사 선택 (필수) —</option>'
          + _CARRIER_FALLBACK.map(function(n){
              return '<option>' + escapeHtml(n) + '</option>';
            }).join('');
      });
  }

  function _productLabel(p) {
    var code = p && p.code ? String(p.code) : '';
    var name = p && p.full_name ? String(p.full_name) : '';
    var ko = p && p.korean_name ? String(p.korean_name) : '';
    if (code && name && ko) return code + ' · ' + name + ' (' + ko + ')';
    if (code && name) return code + ' · ' + name;
    return name || code || '';
  }

  function _onestopLoadProducts() {
    var sel = document.getElementById('onestop-product');
    if (!sel) return;
    fetch(API + '/api/q/products')
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(d) {
        var items = (d && d.data && d.data.items) || [];
        var opts = '<option value="">— 품목 선택 (필수) —</option>';
        opts += items.map(function(p) {
          var value = p.full_name || p.code || '';
          return '<option value="' + escapeHtml(value) + '" data-code="' + escapeHtml(p.code || '') + '">'
            + escapeHtml(_productLabel(p)) + '</option>';
        }).join('');
        sel.innerHTML = opts || '<option value="">— 품목 없음 —</option>';
      })
      .catch(function() {
        sel.innerHTML = '<option value="">— 품목 목록 로드 실패 —</option>';
      });
  }

  window.onestopProductChange = function(sel) {
    var opt = sel && sel.options ? sel.options[sel.selectedIndex] : null;
    var product = sel ? String(sel.value || '').trim() : '';
    var code = opt ? String(opt.getAttribute('data-code') || '').trim() : '';
    _onestopState.product = product;
    _onestopState.productCode = code;
    if (_onestopState.parsed && _onestopState.previewRows.length && product) {
      _onestopState.previewRows.forEach(function(r, i) {
        if (!r) return;
        var oldProduct = r.product || '';
        if (oldProduct !== product) {
          r.product = product;
          _onestopState.editedCells[i + '.product'] = true;
        }
        if (code && r.code !== code) {
          r.code = code;
          _onestopState.editedCells[i + '.code'] = true;
        }
      });
      _onestopRenderPreview(_onestopState.previewRows);
      _onestopUpdateHistoryButtons();
      showToast('success', '품목이 미리보기 PRODUCT 열에 반영되었습니다');
    }
  };

  window.onestopCarrierChange = function(carrier) {
    window._onestopActiveTemplate = null;
    var lbl = document.getElementById('onestop-tpl-label');
    if (lbl) { lbl.textContent = '미선택'; lbl.style.color = 'var(--text-muted)'; lbl.style.fontWeight = 'normal'; }
    var tRow = document.getElementById('onestop-template-row');
    if (tRow) tRow.style.display = carrier ? '' : 'none';
    if (!carrier) return;
    var list = _loadTplList(carrier);
    if (list.length === 1) {
      _applyTemplate(list[0], carrier);
    } else if (list.length > 1) {
      showToast('info', carrier + ' 템플릿 ' + list.length + '개 — [선택/수정]에서 선택하세요');
    } else {
      showToast('info', carrier + ' 템플릿 없음 — [선택/수정]으로 새 템플릿을 만드세요');
    }
    /* Carrier Profile: bag_weight 자동 설정 */
    fetch(API + '/api/carriers/' + encodeURIComponent(carrier))
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(p) {
        if (!p || !p.carrier_id) return;
        if (window._onestopBagWeight === null && p.bag_weight_kg) {
          window._onestopBagWeight = p.bag_weight_kg;
          var lbl2 = document.getElementById('onestop-db-tpl-label');
          if (lbl2) {
            lbl2.textContent = '🚢 선사 프로파일 적용: ' + escapeHtml(p.display_name || carrier)
              + ' (' + p.bag_weight_kg + 'kg)';
            lbl2.style.color = 'var(--success,#4caf50)';
            lbl2.style.borderColor = 'var(--success,#4caf50)';
          }
        }
      })
      .catch(function() {});
  };

  /* 템플릿 선택/수정 모달 */
  window.onestopOpenTemplatePicker = function() {
    var cEl = document.getElementById('onestop-carrier');
    var carrier = cEl ? cEl.value : '';
    if (!carrier) { showToast('error', '선사를 먼저 선택하세요'); return; }
    var list = _loadTplList(carrier);
    var rows = list.map(function(t, i) {
      var ci = JSON.stringify(carrier);
      return '<tr style="border-bottom:1px solid var(--border)">'
        + '<td style="padding:6px 8px;font-weight:600">' + (t.name||'(이름없음)') + '</td>'
        + '<td style="padding:6px 8px;font-size:11px;color:var(--text-muted)">'
        + (t.product_name ? t.product_name + ' | ' : '')
        + (t.lot_sqm ? 'LOT:' + t.lot_sqm + 'm2 | ' : '')
        + (t.mxbg ? 'MXBG:' + t.mxbg + ' | ' : '')
        + (t.sap_no ? 'SAP:' + t.sap_no : '')
        + '</td>'
        + '<td style="padding:6px 4px;white-space:nowrap">'
        + '<button class="btn btn-sm btn-primary" style="margin-right:4px" onclick="window._onestopSelectTpl(' + i + ',' + ci + ')">적용</button>'
        + '<button class="btn btn-sm" style="margin-right:4px" onclick="window._onestopEditTpl(' + i + ',' + ci + ')">수정</button>'
        + '<button class="btn btn-sm btn-danger" onclick="window._onestopDeleteTpl(' + i + ',' + ci + ')">삭제</button>'
        + '</td>'
        + '</tr>';
    }).join('');
    var formHtml = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">'
      + '<div><label style="font-size:11px;color:var(--text-muted)">템플릿 이름 *</label><br><input id="tpl-f-name" class="form-control" placeholder="예: Maersk 기본"></div>'
      + '<div><label style="font-size:11px;color:var(--text-muted)">제품명</label><br><input id="tpl-f-product" class="form-control" placeholder="예: SQM White"></div>'
      + '<div><label style="font-size:11px;color:var(--text-muted)">LOT SQM (m2)</label><br><input id="tpl-f-lotsqm" class="form-control" placeholder="예: 1000"></div>'
      + '<div><label style="font-size:11px;color:var(--text-muted)">MXBG 수량</label><br><input id="tpl-f-mxbg" class="form-control" placeholder="예: 100"></div>'
      + '<div><label style="font-size:11px;color:var(--text-muted)">SAP 번호</label><br><input id="tpl-f-sap" class="form-control" placeholder="예: 1234567"></div>'
      + '<div><label style="font-size:11px;color:var(--text-muted)">메모</label><br><input id="tpl-f-notes" class="form-control" placeholder="선택사항"></div>'
      + '</div>';
    var ci2 = JSON.stringify(carrier);
    var html = '<div style="min-width:520px">'
      + '<div style="font-size:14px;font-weight:700;margin-bottom:12px">' + carrier + ' 템플릿 관리</div>'
      + (list.length ? '<table style="width:100%;border-collapse:collapse;margin-bottom:12px"><tbody>' + rows + '</tbody></table>' : '<p style="color:var(--text-muted);margin-bottom:12px">등록된 템플릿이 없습니다.</p>')
      + '<hr style="border-color:var(--border);margin-bottom:12px">'
      + '<div style="font-size:13px;font-weight:600;margin-bottom:8px">+ 새 템플릿 작성</div>'
      + formHtml
      + '<div style="text-align:right"><button class="btn btn-primary" onclick="window._onestopSaveNewTpl(' + ci2 + ')">저장 후 적용</button></div>'
      + '</div>';
    showDataModal(carrier + ' 템플릿', html);
  };

  window._onestopSelectTpl = function(idx, carrier) {
    var list = _loadTplList(carrier);
    if (list[idx]) { _applyTemplate(list[idx], carrier); document.getElementById('sqm-modal').style.display='none'; }
  };

  window._onestopDeleteTpl = function(idx, carrier) {
    if (!confirm('이 템플릿을 삭제하시겠습니까?')) return;
    var list = _loadTplList(carrier);
    list.splice(idx, 1);
    _saveTplList(carrier, list);
    window.onestopOpenTemplatePicker();
  };

  window._onestopEditTpl = function(idx, carrier) {
    var list = _loadTplList(carrier);
    var t = list[idx]; if (!t) return;
    window.onestopOpenTemplatePicker();
    setTimeout(function() {
      var nEl=document.getElementById('tpl-f-name'); if(nEl) nEl.value=t.name||'';
      var pEl=document.getElementById('tpl-f-product'); if(pEl) pEl.value=t.product_name||'';
      var lEl=document.getElementById('tpl-f-lotsqm'); if(lEl) lEl.value=t.lot_sqm||'';
      var mEl=document.getElementById('tpl-f-mxbg'); if(mEl) mEl.value=t.mxbg||'';
      var sEl=document.getElementById('tpl-f-sap'); if(sEl) sEl.value=t.sap_no||'';
      var noEl=document.getElementById('tpl-f-notes'); if(noEl) noEl.value=t.notes||'';
      var btns=document.querySelectorAll('#sqm-modal-inner button.btn-primary');
      btns.forEach(function(b){ if(b.textContent.indexOf('저장') > -1){
        b.textContent='수정 저장';
        b.onclick=function(){ window._onestopUpdateTpl(idx, carrier); };
      }});
    }, 60);
  };

  window._onestopUpdateTpl = function(idx, carrier) {
    var name=((document.getElementById('tpl-f-name')||{}).value||'').trim();
    if (!name) { showToast('error', '템플릿 이름을 입력하세요'); return; }
    var t = { name:name,
      product_name:(document.getElementById('tpl-f-product')||{}).value||'',
      lot_sqm:(document.getElementById('tpl-f-lotsqm')||{}).value||'',
      mxbg:(document.getElementById('tpl-f-mxbg')||{}).value||'',
      sap_no:(document.getElementById('tpl-f-sap')||{}).value||'',
      notes:(document.getElementById('tpl-f-notes')||{}).value||'' };
    var list=_loadTplList(carrier); list[idx]=t;
    _saveTplList(carrier, list); _applyTemplate(t, carrier); document.getElementById('sqm-modal').style.display='none';
  };

  window._onestopSaveNewTpl = function(carrier) {
    var name=((document.getElementById('tpl-f-name')||{}).value||'').trim();
    if (!name) { showToast('error', '템플릿 이름을 입력하세요'); return; }
    var t = { name:name,
      product_name:(document.getElementById('tpl-f-product')||{}).value||'',
      lot_sqm:(document.getElementById('tpl-f-lotsqm')||{}).value||'',
      mxbg:(document.getElementById('tpl-f-mxbg')||{}).value||'',
      sap_no:(document.getElementById('tpl-f-sap')||{}).value||'',
      notes:(document.getElementById('tpl-f-notes')||{}).value||'' };
    var list=_loadTplList(carrier);
    list.push(t); _saveTplList(carrier, list); _applyTemplate(t, carrier); document.getElementById('sqm-modal').style.display='none';
  };

  /* ── DB 파싱 템플릿 선택기 ── */
  window.onestopOpenDbTemplatePicker = function() {
    var mid = 'sqm-db-tpl-modal';
    var existing = document.getElementById(mid);
    if (existing) existing.remove();
    var m = document.createElement('div');
    m.id = mid;
    m.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:99990;display:flex;align-items:center;justify-content:center';
    var closeBtn = '<button class="btn" onclick="document.getElementById(\'' + mid + '\').remove()">✕ 닫기</button>';
    m.innerHTML = '<div style="background:var(--panel,#12233a);border:1px solid var(--panel-border,#1e4a7a);border-radius:10px;padding:22px 26px;min-width:460px;max-width:600px;max-height:80vh;overflow-y:auto;">'
      + '<div style="font-weight:700;font-size:15px;margin-bottom:14px">📋 DB 파싱 템플릿 선택</div>'
      + '<div id="db-tpl-list-body" style="min-height:60px">⏳ 로딩 중...</div>'
      + '<div style="margin-top:16px;display:flex;justify-content:flex-end">' + closeBtn + '</div></div>';
    document.body.appendChild(m);
    m.addEventListener('click', function(e){ if(e.target===m) m.remove(); });
    fetch(API + '/api/inbound/templates')
      .then(function(r){ return r.json(); })
      .then(function(data) {
        var lb = document.getElementById('db-tpl-list-body');
        if (!lb) return;
        if (!data.ok || !data.templates || data.templates.length === 0) {
          lb.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:20px">📭 등록된 템플릿 없음<br><small>메뉴 → 입고 → 인바운드 템플릿 관리에서 추가하세요</small></div>';
          return;
        }
        var html = '<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">' + data.templates.length + '개 — 클릭하여 적용</div>';
        html += '<div style="display:flex;flex-direction:column;gap:6px">';
        data.templates.forEach(function(t) {
          var bw = t.bag_weight_kg || 500;
          var hint = (t.gemini_hint_packing || '').substring(0, 40);
          var isActive = (window._onestopDbTemplateId === t.template_id);
          var bc = isActive ? 'var(--success,#4caf50)' : 'var(--border,#1e4a7a)';
          html += '<div class="db-tpl-item"'
            + ' data-tid="'   + escapeHtml(String(t.template_id))       + '"'
            + ' data-tname="' + escapeHtml(t.template_name || '')       + '"'
            + ' data-tbw="'   + bw                                      + '"'
            + ' data-thint="' + escapeHtml(t.gemini_hint_packing || '') + '"'
            + ' style="cursor:pointer;padding:10px 14px;background:var(--bg-hover);border:1px solid ' + bc + ';border-radius:7px;margin-bottom:2px;transition:border-color .15s"'
            + ' onmouseover="this.style.borderColor=\'var(--info,#42a5f5)\'"'
            + ' onmouseout="this.style.borderColor=\'' + bc + '\'">'   
            + '<div style="font-weight:700;font-size:13px">' + escapeHtml(t.template_name) + (isActive ? ' ✅' : '') + '</div>'
            + '<div style="font-size:11px;color:var(--text-muted);margin-top:3px">🏋️ ' + bw + 'kg'
            + (hint ? ' · 💬 ' + escapeHtml(hint) + (t.gemini_hint_packing && t.gemini_hint_packing.length > 40 ? '…' : '') : '')
            + (t.product_hint ? ' · 📦 ' + escapeHtml(t.product_hint) : '')
            + '</div></div>';
        });
        html += '</div>';
        lb.innerHTML = html;
        /* click handler: data-* 속성으로 안전 전달 */
        lb.addEventListener('click', function(e) {
          var item = e.target.closest('.db-tpl-item');
          if (!item) return;
          window._onestopSelectDbTpl(
            item.getAttribute('data-tid'),
            item.getAttribute('data-tname'),
            parseInt(item.getAttribute('data-tbw'), 10) || 500,
            item.getAttribute('data-thint') || ''
          );
        });
      })
      .catch(function(e) {
        var lb = document.getElementById('db-tpl-list-body');
        if (lb) lb.innerHTML = '<div style="color:var(--danger)">⚠️ 로드 실패: ' + escapeHtml(String(e)) + '</div>';
      });
  };

  window._onestopSelectDbTpl = function(id, name, bagWeight, geminiHint) {
    window._onestopBagWeight      = bagWeight;
    window._onestopGeminiHint     = geminiHint || '';
    window._onestopDbTemplateId   = id;
    window._onestopDbTemplateName = name;
    var lbl = document.getElementById('onestop-db-tpl-label');
    if (lbl) {
      lbl.style.color  = 'var(--success,#4caf50)';
      lbl.style.border = '1px solid var(--success,#4caf50)';
      lbl.textContent  = '✅ ' + name + ' · 🏋️ ' + bagWeight + 'kg'
        + (geminiHint ? ' · 💬 힌트있음' : '');
    }
    var m = document.getElementById('sqm-db-tpl-modal');
    if (m) m.remove();
    showToast('success', '🏋️ DB 템플릿 적용: ' + name + ' (' + bagWeight + 'kg)');
  };

  /* ── 파싱 실행 (Sprint 1-2-B: /api/inbound/onestop-upload 4종 multipart + 크로스체크) ── */
  window.onestopCalcFreeTime = function() {
    var arrEl = document.getElementById('onestop-arrival-input');
    var crEl  = document.getElementById('onestop-conreturn-input');
    var ftEl  = document.getElementById('onestop-freetime-display');
    if (!arrEl || !crEl || !ftEl) return;
    if (arrEl.value && crEl.value) {
      var ms   = new Date(crEl.value) - new Date(arrEl.value);
      var days = Math.max(0, Math.round(ms / 86400000));
      ftEl.value = days + ' 일';
    } else {
      ftEl.value = '';
    }
  };

  window.onestopParseStart = function() {
    var s = _onestopState.files;
    var _cEl = document.getElementById('onestop-carrier');
    var _pEl = document.getElementById('onestop-product');
    if (!_cEl || !_cEl.value) { showToast('error', '🚢 선사를 먼저 선택하세요 (필수)'); return; }
    if (!_pEl || !_pEl.value) { showToast('error', '📦 품목을 먼저 선택하세요 (필수)'); return; }
    if (window._onestopBagWeight === null) { showToast('error', '🏋️ DB 파싱 템플릿을 먼저 선택하세요 (톤백 단위 미설정 시 500kg로 오파싱 위험)'); return; }
    if (!s.PACKING_LIST) { showToast('error', 'Packing List(PL) 먼저 선택하세요'); return; }
    window.onestopProductChange(_pEl);

    _onestopSetStep(2);
    /* BL 슬롯 표시 (파싱 시작 시) */
    (function(){ var blRow=document.getElementById('onestop-bl'); if(blRow){ var p=blRow.closest('.onestop-slot'); if(p) p.style.display=''; } })();
    _showParseLogPanel();
    /* 결과차는 파싱 완료 후 표시 (몬조기 체제) */
    _addParseLog('🚀', '파싱 시작', 'var(--text-muted)');
    var pb = document.getElementById('onestop-progress-body');
    if (pb) {
      var filesSummary = [];
      if (s.BL)           filesSummary.push('🚢 BL');
      if (s.PACKING_LIST) filesSummary.push('📦 PL');
      if (s.INVOICE)      filesSummary.push('📄 INV');
      if (s.DO)           filesSummary.push('📋 DO');
      pb.innerHTML = '<div style="padding:4px;color:var(--fg)">⏳ 파싱 + 크로스체크 진행 중... <strong>' + filesSummary.join(' · ') + '</strong></div>';
    }

    var form = new FormData();
    /* FastAPI: pl 필수, bl/invoice/do_file 선택 */
    form.append('pl', s.PACKING_LIST, s.PACKING_LIST.name);
    if (s.BL)      form.append('bl',      s.BL,      s.BL.name);
    if (s.INVOICE) form.append('invoice', s.INVOICE, s.INVOICE.name);
    if (s.DO)      form.append('do_file', s.DO,      s.DO.name);
    // DB 템플릿 정보 주입 + 업로드 시점 힌트
    var _hintInputEl = document.getElementById('onestop-hint-input');
    if (_hintInputEl && _hintInputEl.value.trim()) window._onestopGeminiHint = _hintInputEl.value.trim();
    var _arrivalEl   = document.getElementById('onestop-arrival-input');
    var _conReturnEl = document.getElementById('onestop-conreturn-input');
    if (_arrivalEl   && _arrivalEl.value)   form.append('manual_arrival',    _arrivalEl.value);
    if (_conReturnEl && _conReturnEl.value) form.append('manual_con_return', _conReturnEl.value);
    if (window._onestopBagWeight !== null) form.append('bag_weight_kg', String(window._onestopBagWeight));
    if (window._onestopGeminiHint) form.append('gemini_hint', window._onestopGeminiHint);
    if (window._onestopDbTemplateId) form.append('template_id', String(window._onestopDbTemplateId));
    if (_onestopState.product) form.append('selected_product', _onestopState.product);
    if (_onestopState.productCode) form.append('selected_product_code', _onestopState.productCode);

    var xhr = new XMLHttpRequest();
    /* [Sprint 1-2-C] dry_run=true 로 DB 저장 없이 파싱만 실행 */
    xhr.open('POST', API + '/api/inbound/onestop-upload?dry_run=true');
    xhr.onload = function(){
      var body; try { body = JSON.parse(xhr.responseText); } catch(e){ body = null; }
      if (xhr.status >= 200 && xhr.status < 300 && body && body.ok) {
        var d = body.data || {};
        var xc = d.cross_check || {};
        var docs = d.parsed_docs || {};

        /* 진행 상태 패널 업데이트 */
        var xcColor = xc.has_critical ? 'var(--danger)' : (xc.warning > 0 ? 'var(--warning)' : 'var(--success)');
        var xcIcon = xc.has_critical ? '🚫' : (xc.warning > 0 ? '⚠️' : '✅');
        var docsBadges = [
          (docs.bl_loaded      ? '🚢 BL ✓'  : '🚢 BL ✗'),
          (docs.pl_loaded      ? '📦 PL ✓'  : '📦 PL ✗'),
          (docs.invoice_loaded ? '📄 INV ✓' : '📄 INV ✗'),
          (docs.do_loaded      ? '📋 DO ✓'  : '📋 DO ✗'),
        ].join('  ');

        var xcItemsHtml = '';
        if (xc.items && xc.items.length) {
          xcItemsHtml = '<details style="margin-top:8px"><summary style="cursor:pointer;font-size:12px;color:var(--text-muted)">⚠️ ' + xc.items.length + '건 상세</summary>' +
            '<ul style="font-size:11px;margin:6px 0 0 20px;padding:0">' +
            xc.items.map(function(it){
              var lc = it.level === 3 ? 'var(--danger)' : (it.level === 2 ? 'var(--warning)' : 'var(--text-muted)');
              return '<li style="color:' + lc + ';margin-bottom:2px">' + escapeHtml(it.icon) + ' <strong>[' + escapeHtml(it.field) + ']</strong> ' + escapeHtml(it.message) + '</li>';
            }).join('') +
            '</ul></details>';
        }

        if (pb) pb.innerHTML =
          '<div style="color:var(--success);font-weight:700">✅ ' + escapeHtml(body.message || '파싱 완료') + ' <span style="font-size:11px;color:var(--text-muted);font-weight:400">(미리보기 단계 — DB 저장 전)</span></div>' +
          '<div style="color:var(--text-muted);font-size:12px;margin-top:6px">📑 서류: ' + docsBadges + '</div>' +
          '<div style="color:' + xcColor + ';font-size:13px;font-weight:600;margin-top:6px">' + xcIcon + ' ' + escapeHtml(xc.summary || '') + '</div>' +
          xcItemsHtml +
          (xc.has_critical ? '<div style="color:var(--danger);font-size:11px;margin-top:6px;font-weight:600">🚫 심각 불일치 감지 — 파일 확인 후 다시 파싱 권장</div>' : '') +
          '<div style="color:var(--info, #42a5f5);font-size:11px;margin-top:8px">💡 셀 더블클릭으로 편집 가능 · 완료 후 하단 "📤 DB 업로드" 버튼 클릭</div>';

        /* 18열 미리보기 테이블 채우기 + 편집 상태 초기화 */
        var rows = d.preview_rows || [];
        _onestopState.previewRows = rows.slice();  /* 편집 대상 */
        _onestopState.originalRows = JSON.parse(JSON.stringify(rows));  /* deep copy */
        _onestopState.editedCells = {};
        _onestopState.parsed = rows.length > 0;
        /* [Sprint 1-2-D] 새 파싱 → Undo 히스토리 리셋 */
        _onestopState.history = [];
        _onestopState.historyIdx = -1;
        /* D/O 수동 정보가 있고 DO 파일이 없었다면 새 rows 에 적용 */
        if (_onestopState.manualDo && !_onestopState.files.DO) {
          var md = _onestopState.manualDo;
          _onestopState.previewRows.forEach(function(r, i){
            if (!r) return;
            if (md.free_time && !r.free_time)   { r.free_time = md.free_time; _onestopState.editedCells[i + '.free_time'] = true; }
            if (md.warehouse && !r.wh)           { r.wh = md.warehouse;        _onestopState.editedCells[i + '.wh'] = true; }
            if (md.arrival_date && !r.arrival)  { r.arrival = md.arrival_date; _onestopState.editedCells[i + '.arrival'] = true; }
          });
        }
        _onestopRenderPreview(_onestopState.previewRows);
        _onestopUpdateHistoryButtons();
        var _cEl2 = document.getElementById('onestop-carrier');
        _openParseResultWindow(_cEl2 ? _cEl2.value : '', rows.length);

        _onestopSetStep(3);
        _addParseLog('✅', '파싱 완료 — LOT ' + rows.length + '건', 'var(--success,#4caf50)');
        if (rows.length > 0) {
          var saveBtn = document.getElementById('onestop-save-btn');
          if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '📤 DB 업로드 (' + rows.length + '건)'; }
        }
        showToast('success', '파싱 완료: ' + rows.length + ' LOT — 편집 후 DB 업로드');
      } else {
        var errMsg = (body && (body.detail || body.error || body.message)) || ('HTTP ' + xhr.status);
        if (typeof errMsg === 'object') errMsg = JSON.stringify(errMsg);
        if (pb) pb.innerHTML = '<div style="color:var(--danger);font-weight:700">❌ 파싱 실패</div><div style="color:var(--text-muted);font-size:12px;margin-top:4px">' + escapeHtml(String(errMsg)) + '</div>';
        _addParseLog('❌', '파싱 실패: ' + String(errMsg), 'var(--danger)');
        showToast('error', '파싱 실패: ' + errMsg);
        _onestopSetStep(1);
      }
    };
    xhr.onerror = function(){
      if (pb) pb.innerHTML = '<div style="color:var(--danger)">❌ 네트워크 에러</div>';
      _addParseLog('❌', '네트워크 에러', 'var(--danger)');
      showToast('error', '네트워크 에러');
      _onestopSetStep(1);
    };
    xhr.send(form);

    var reparseBtn = document.getElementById('onestop-reparse-btn');
    if (reparseBtn) reparseBtn.disabled = false;
  };

  /* 18열 미리보기 렌더 — preview_rows (백엔드 응답) → Table body
     [Sprint 1-2-C] 각 셀에 data-row / data-field 부여, 더블클릭 편집 지원 */
  function _onestopRenderPreview(rows) {
    var tbody = document.getElementById('onestop-preview-body');
    if (!tbody) return;
    if (!rows || !rows.length) {
      tbody.innerHTML = '<tr><td colspan="' + ONESTOP_PREVIEW_COLS.length + '" class="onestop-preview-empty">📭 파싱 결과 0행</td></tr>';
      return;
    }
    /* xc_tag 에 따른 행 색상 */
    function tagColor(tag) {
      if (tag === 'xc_critical') return 'background:rgba(244,67,54,.15)';
      if (tag === 'xc_warning')  return 'background:rgba(255,167,38,.12)';
      if (tag === 'xc_info')     return 'background:rgba(66,165,245,.08)';
      return '';
    }
    /* field 키 → 컬럼 정의 (편집가능 여부 + 정렬 스타일) */
    var fields = [
      { key: 'no',          align: 'right',  accent: false },
      { key: 'lot_no',      align: 'left',   accent: true  },
      { key: 'sap_no',      align: 'left',   accent: false },
      { key: 'bl_no',       align: 'left',   accent: false },
      { key: 'product',     align: 'left',   accent: false, mono: false },
      { key: 'status',      align: 'left',   accent: false, tag: true },
      { key: 'container',   align: 'left',   accent: false },
      { key: 'code',        align: 'left',   accent: false },
      { key: 'lot_sqm',     align: 'left',   accent: false },
      { key: 'mxbg',        align: 'right',  accent: false },
      { key: 'net_kg',      align: 'right',  accent: false },
      { key: 'gross_kg',    align: 'right',  accent: false },
      { key: 'invoice_no',  align: 'left',   accent: false },
      { key: 'ship_date',   align: 'left',   accent: false },
      { key: 'arrival',     align: 'left',   accent: false },
      { key: 'con_return',  align: 'left',   accent: false },
      { key: 'free_time',   align: 'left',   accent: false },
      { key: 'wh',          align: 'left',   accent: false, mono: false },
    ];

    tbody.innerHTML = rows.map(function(r, rowIdx){
      var style = tagColor(r.xc_tag);
      var cellsHtml = fields.map(function(f){
        var val = r[f.key];
        var text = (val == null ? '' : String(val));
        var editable = ONESTOP_EDITABLE_FIELDS.has(f.key);
        var edited = _onestopState.editedCells[rowIdx + '.' + f.key];
        var cellClass = [
          (f.mono !== false ? 'mono-cell' : ''),
          (editable ? 'onestop-editable' : ''),
          (edited ? 'onestop-edited' : ''),
        ].filter(Boolean).join(' ');
        var cellStyle = [
          'text-align:' + f.align,
          (f.accent ? 'color:var(--accent);font-weight:600' : ''),
        ].filter(Boolean).join(';');
        var attrs = 'class="' + cellClass + '"' +
                    (cellStyle ? ' style="' + cellStyle + '"' : '') +
                    ' data-row="' + rowIdx + '" data-field="' + f.key + '"' +
                    (editable ? ' ondblclick="window.onestopEditCell(this)" title="더블클릭으로 편집"' : '');
        var rendered = f.tag ? '<span class="tag">' + escapeHtml(text) + '</span>' : escapeHtml(text);
        return '<td ' + attrs + '>' + rendered + '</td>';
      }).join('');
      return '<tr' + (style ? ' style="' + style + '"' : '') + '>' + cellsHtml + '</tr>';
    }).join('');
  }

  /* 셀 더블클릭 → input 으로 교체, blur/Enter 로 커밋, Escape 로 취소 */
  window.onestopEditCell = function(td) {
    if (!td || td.querySelector('input')) return;  /* 이미 편집 중 */
    var rowIdx = parseInt(td.dataset.row, 10);
    var field  = td.dataset.field;
    if (isNaN(rowIdx) || !field) return;
    var curVal = (_onestopState.previewRows[rowIdx] || {})[field];
    curVal = (curVal == null ? '' : String(curVal));

    var input = document.createElement('input');
    input.type = 'text';
    input.value = curVal;
    input.className = 'onestop-edit-input';
    input.style.cssText = 'width:100%;padding:2px 4px;background:var(--bg);color:var(--fg);border:1px solid var(--accent);border-radius:3px;font-size:11px;font-family:inherit';

    td.innerHTML = '';
    td.appendChild(input);
    input.focus();
    input.select();

    function commit() {
      var newVal = input.value;
      /* 값 변화 없으면 history 기록 생략 */
      if (String(newVal) === String(curVal)) {
        _onestopRenderPreview(_onestopState.previewRows);
        return;
      }
      /* [Sprint 1-2-D] Undo 스택에 push (현재 위치 이후 redo 엔트리 제거) */
      _onestopState.history = _onestopState.history.slice(0, _onestopState.historyIdx + 1);
      _onestopState.history.push({ rowIdx: rowIdx, field: field, oldVal: curVal, newVal: newVal });
      if (_onestopState.history.length > ONESTOP_MAX_HISTORY) {
        _onestopState.history.shift();
      }
      _onestopState.historyIdx = _onestopState.history.length - 1;

      /* 상태 업데이트 */
      if (!_onestopState.previewRows[rowIdx]) _onestopState.previewRows[rowIdx] = {};
      _onestopState.previewRows[rowIdx][field] = newVal;
      var origVal = (_onestopState.originalRows[rowIdx] || {})[field];
      var cellKey = rowIdx + '.' + field;
      if (String(newVal) !== String(origVal == null ? '' : origVal)) {
        _onestopState.editedCells[cellKey] = true;
      } else {
        delete _onestopState.editedCells[cellKey];
      }
      _onestopRenderPreview(_onestopState.previewRows);
      _onestopUpdateHistoryButtons();
    }
    function cancel() {
      _onestopRenderPreview(_onestopState.previewRows);
    }
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', function(e){
      if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
      else if (e.key === 'Escape') { e.preventDefault(); input.removeEventListener('blur', commit); cancel(); }
      /* Tab 은 기본 동작 허용 (포커스 이동) + blur 로 commit 됨 */
    });
  };
  window.onestopParseRedo = function() {
    _onestopState.step = 1;
    _onestopSetStep(1);
    window.onestopParseStart();
  };
  /* [Sprint 1-2-C] 편집된 미리보기 rows → /onestop-save POST → DB 저장 */
  window.onestopSaveDb = function() {
    if (!_onestopState.parsed || !_onestopState.previewRows.length) {
      showToast('warn', '파싱된 데이터가 없습니다. ▶ 파싱 시작을 먼저 실행하세요');
      return;
    }
    var editedCount = Object.keys(_onestopState.editedCells).length;
    var rowCount = _onestopState.previewRows.length;
    var confirmMsg = '💾 DB 저장 확인\n\n' +
      '총 ' + rowCount + ' LOT (편집된 셀 ' + editedCount + '개)\n' +
      '실제 재고 DB에 등록됩니다. 계속하시겠습니까?';
    if (!confirm(confirmMsg)) return;

    var saveBtn = document.getElementById('onestop-save-btn');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = '⏳ 저장 중...'; }

    apiPost('/api/inbound/onestop-save', { rows: _onestopState.previewRows })
      .then(function(res){
        var d = (res && res.data) || {};
        if (res && res.ok) {
          _onestopSetStep(4);
          _addParseLog('🗄️', 'DB 저장 완료: ' + (d.success_count || 0) + '건', 'var(--success,#4caf50)');
          if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = '✅ 저장 완료 (' + (d.success_count || 0) + '건)'; }
          var pb = document.getElementById('onestop-progress-body');
          var errHtml = '';
          if (d.errors && d.errors.length) {
            errHtml = '<details style="margin-top:6px"><summary style="cursor:pointer;font-size:12px;color:var(--warning)">⚠️ 실패 ' + d.errors.length + '건 상세</summary>' +
              '<ul style="font-size:11px;margin:4px 0 0 20px">' +
              d.errors.map(function(er){
                return '<li>row ' + er.row + ' — ' + escapeHtml(er.lot_no || '-') + ': ' + escapeHtml(er.reason || '') + '</li>';
              }).join('') + '</ul></details>';
          }
          if (pb) pb.innerHTML +=
            '<div style="margin-top:10px;padding:8px;background:rgba(102,187,106,.1);border-left:3px solid var(--success);border-radius:4px">' +
            '<div style="color:var(--success);font-weight:700">💾 DB 저장 완료 — 성공 ' + (d.success_count || 0) + '건 / 실패 ' + (d.fail_count || 0) + '건</div>' +
            errHtml + '</div>';
          showToast(d.fail_count ? 'warn' : 'success', 'DB 저장: 성공 ' + d.success_count + '건 / 실패 ' + d.fail_count + '건');
          if (_currentRoute === 'inventory' && typeof loadInventoryPage === 'function') loadInventoryPage();
          if (typeof loadKpi === 'function') loadKpi();
        } else {
          var msg = (res && (res.message || res.error)) || 'DB 저장 실패';
          showToast('error', msg);
          if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '📤 DB 업로드 재시도'; }
        }
      })
      .catch(function(e){
        showToast('error', 'DB 저장 오류: ' + (e.message || String(e)));
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '📤 DB 업로드 재시도'; }
      });
  };
  var _STEP_BADGE = ['','① 서류 선택','② 파싱 중…','③ 결과 확인','④ DB 저장 완료'];
  var _STEP_COLOR = ['','var(--sidebar-active-bg,#3b82f6)','#e67e22','var(--sidebar-active-bg,#3b82f6)','#27ae60'];
  function _onestopSetStep(step) {
    _onestopState.step = step;
    var badge = document.getElementById('onestop-step-badge');
    if (badge) {
      badge.textContent = _STEP_BADGE[step] || '';
      badge.style.background = _STEP_COLOR[step] || 'var(--sidebar-active-bg)';
      badge.style.color = 'var(--sidebar-active-fg,#fff)';
    }
  }

  /* ── 파싱 로그 플로팅 패널 ── */
  var _parseLogPanel = null;
  var _parseLogBody  = null;
  function _showParseLogPanel() {
    if (_parseLogPanel) {
      _parseLogPanel.style.display = 'flex';
      if (_parseLogBody) _parseLogBody.innerHTML = '';
      return;
    }
    var p = document.createElement('div');
    p.id = 'sqm-parse-log';
    p.style.cssText = 'position:fixed;top:130px;right:28px;width:340px;background:var(--bg-card);border:1px solid var(--panel-border);border-radius:10px;box-shadow:0 8px 32px rgba(0,0,0,.45);z-index:10051;font-size:12px;display:flex;flex-direction:column';
    p.innerHTML =
      '<div id="sqm-parse-log-hdr" style="cursor:move;user-select:none;padding:7px 12px;border-bottom:1px solid var(--panel-border);display:flex;align-items:center;gap:6px;border-radius:10px 10px 0 0;background:var(--panel);flex-shrink:0">'
      +'<span style="font-weight:700;flex:1;font-size:13px">⚙️ 파싱 진행 로그</span>'
      +'<button onclick="document.getElementById(\'sqm-parse-log\').style.display=\'none\'" style="background:none;border:none;cursor:pointer;color:var(--text-muted);font-size:1.2rem;line-height:1;padding:0 2px">✕</button>'
      +'</div>'
      +'<div id="sqm-parse-log-body" style="padding:8px 12px;max-height:340px;min-height:60px;overflow-y:auto;display:flex;flex-direction:column;gap:3px;"></div>'
      +'<div style="padding:5px 12px;border-top:1px solid var(--panel-border);font-size:10px;color:var(--text-muted);border-radius:0 0 10px 10px;background:var(--panel)">드래그로 이동 가능 · ✕ 닫기</div>';
    document.body.appendChild(p);
    _parseLogPanel = p;
    _parseLogBody  = p.querySelector('#sqm-parse-log-body');
    var hdr = p.querySelector('#sqm-parse-log-hdr');
    var drag = {on:false,sx:0,sy:0,ox:0,oy:0};
    hdr.addEventListener('mousedown', function(e){
      drag.on=true; drag.sx=e.clientX; drag.sy=e.clientY;
      var r=p.getBoundingClientRect(); drag.ox=r.left; drag.oy=r.top;
      p.style.right='auto'; e.preventDefault();
    });
    document.addEventListener('mousemove', function(e){
      if (!drag.on) return;
      p.style.left=(drag.ox+(e.clientX-drag.sx))+'px';
      p.style.top =(drag.oy+(e.clientY-drag.sy))+'px';
    });
    document.addEventListener('mouseup', function(){ drag.on=false; });
  }
  function _addParseLog(icon, msg, color) {
    if (!_parseLogBody) return;
    var t = new Date();
    var ts = t.getHours().toString().padStart(2,'0')+':'+t.getMinutes().toString().padStart(2,'0')+':'+t.getSeconds().toString().padStart(2,'0');
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:5px;align-items:flex-start;padding:3px 0;border-bottom:1px solid var(--panel-border,rgba(255,255,255,.07))';
    row.innerHTML =
      '<span style="color:var(--text-muted);flex-shrink:0;font-size:10px;padding-top:2px;width:50px">'+ts+'</span>'
      +'<span style="flex-shrink:0;font-size:13px">'+icon+'</span>'
      +'<span style="color:'+(color||'var(--fg)')+';flex:1;line-height:1.45">'+escapeHtml(msg)+'</span>';
    _parseLogBody.appendChild(row);
    _parseLogBody.scrollTop = _parseLogBody.scrollHeight;
  }

  /* F017 Picking List PDF 업로드 */
  function showPickingListPdfModal() {
    _showPdfUploadModal({
      title: '📋 Picking List PDF 업로드',
      subtitle: 'Picking List PDF 를 업로드하면 자동 파싱하여 picking_table 에 반영합니다.',
      endpoint: '/api/outbound/picking-list-pdf',
      onSuccess: function(d) {
        var warnHtml = '';
        if (d.warnings && d.warnings.length) {
          warnHtml = '<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--warning)">⚠️ 경고 ' + d.warnings.length + '건</summary><pre style="white-space:pre-wrap;font-size:.8rem;margin-top:8px">' + escapeHtml(d.warnings.join('\n')) + '</pre></details>';
        }
        return '<div style="color:var(--text-muted);font-size:.85rem">파일: ' + escapeHtml(d.filename||'-') +
               ' · 방법: ' + escapeHtml(d.parse_method||'-') +
               ' · LOT ' + (d.total_lots||0) + '개 · 일반 ' + (d.total_normal_mt||0) + ' MT · 샘플 ' + (d.total_sample_kg||0) + ' KG' +
               ' · <strong style="color:var(--accent)">반영 ' + (d.applied||0) + '건</strong>' +
               '</div>' + warnHtml;
      }
    });
  }
  window.showPickingListPdfModal = showPickingListPdfModal;

  /* ===================================================
     8h. F016 빠른 출고 (붙여넣기) — 여러 LOT 일괄
     =================================================== */
  function showQuickOutboundPasteModal() {
    var html = [
      '<div style="max-width:640px">',
      '  <h2 style="margin:0 0 12px 0">📤 빠른 출고 (붙여넣기)</h2>',
      '  <p style="color:var(--text-muted);margin:0 0 12px 0;font-size:.9rem">',
      '    아래에 LOT별 수량을 붙여넣으세요. 형식: <code>LOT_NO [TAB/공백/쉼표] 개수</code> (한 줄에 1 LOT)',
      '  </p>',
      '  <textarea id="qop-text" placeholder="1126013063\\t3&#10;1126013107,2&#10;1126013108 1" style="width:100%;height:140px;padding:10px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;font-family:monospace;font-size:.9rem;margin-bottom:10px"></textarea>',
      '  <div style="display:grid;grid-template-columns:110px 1fr;gap:10px;align-items:center;margin-bottom:10px">',
      '    <label style="font-weight:600">고객명</label>',
      '    <input type="text" id="qop-customer" placeholder="예: ACME Corp" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '    <label style="font-weight:600">사유 <span style="color:var(--text-muted);font-weight:400;font-size:.8rem">(선택)</span></label>',
      '    <input type="text" id="qop-reason" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '    <label style="font-weight:600">작업자 <span style="color:var(--text-muted);font-weight:400;font-size:.8rem">(선택)</span></label>',
      '    <input type="text" id="qop-operator" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '  </div>',
      '  <div id="qop-preview" style="padding:8px;background:var(--bg-hover);border-radius:6px;font-size:.85rem;color:var(--text-muted);margin-bottom:12px;min-height:32px">텍스트를 입력하면 파싱 결과가 여기에 표시됩니다</div>',
      '  <div id="qop-result" style="margin-bottom:12px"></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button id="qop-cancel" class="btn btn-ghost">닫기</button>',
      '    <button id="qop-submit" class="btn btn-primary" disabled>일괄 출고</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);

    var txt = document.getElementById('qop-text');
    var cust = document.getElementById('qop-customer');
    var reason = document.getElementById('qop-reason');
    var op = document.getElementById('qop-operator');
    var preview = document.getElementById('qop-preview');
    var result = document.getElementById('qop-result');
    var submit = document.getElementById('qop-submit');
    var cancel = document.getElementById('qop-cancel');

    function parseRows() {
      var rows = [];
      var lines = (txt.value || '').split(/\r?\n/);
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (!line) continue;
        var parts = line.split(/[\s,\t]+/).filter(Boolean);
        if (parts.length < 2) continue;
        var lot = parts[0];
        var n = parseInt(parts[1], 10);
        if (!lot || isNaN(n) || n <= 0) continue;
        rows.push({ lot_no: lot, count: n });
      }
      return rows;
    }

    function updatePreview() {
      var rows = parseRows();
      if (rows.length === 0) {
        preview.innerHTML = '텍스트를 입력하면 파싱 결과가 여기에 표시됩니다';
        submit.disabled = true;
        return;
      }
      var total = rows.reduce(function(s, r){ return s + r.count; }, 0);
      preview.innerHTML = '✅ <strong>' + rows.length + '개 LOT</strong> · 총 ' + total + ' 톤백 예정';
      submit.disabled = !cust.value.trim();
    }
    txt.addEventListener('input', updatePreview);
    cust.addEventListener('input', updatePreview);

    cancel.addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; });
    submit.addEventListener('click', function(){
      var rows = parseRows();
      if (!rows.length) return;
      var customer = cust.value.trim();
      var totalN = rows.reduce(function(s,r){return s+r.count;},0);
      if (!confirm('총 ' + rows.length + '개 LOT · ' + totalN + '개 톤백을 ' + customer + ' 로 출고합니다. 계속?')) return;

      submit.disabled = true; cancel.disabled = true;
      result.innerHTML = '<div style="padding:8px;color:var(--text-muted)">⏳ 일괄 출고 중...</div>';

      apiPost('/api/outbound/quick-paste', {
        rows: rows, customer: customer,
        reason: reason.value.trim(), operator: op.value.trim()
      }).then(function(res) {
        var d = res && res.data || {};
        var color = (d.fail_count||0) === 0 ? 'var(--success)' : 'var(--warning)';
        var resultsHtml = (d.results||[]).map(function(r){
          var icon = r.ok ? '✅' : '❌';
          var info = r.ok ? (r.picked_count + '개 · ' + (r.total_weight_kg||0).toFixed(1) + ' kg') : escapeHtml(r.reason||'');
          return '<tr><td>' + r.row + '</td><td>' + icon + '</td><td class="mono-cell">' + escapeHtml(r.lot_no) + '</td><td>' + info + '</td></tr>';
        }).join('');
        result.innerHTML =
          '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid '+color+'">' +
          '<div style="font-weight:600;margin-bottom:4px">' + ((d.fail_count||0)===0 ? '✅' : '⚠️') + ' ' + escapeHtml(res.message||'완료') + '</div>' +
          '<div style="color:var(--text-muted);font-size:.85rem">총 ' + (d.total||0) + '건 · 성공 ' + (d.success_count||0) + ' · 실패 ' + (d.fail_count||0) + ' · ' + (d.total_weight_mt||0).toFixed(3) + ' MT</div>' +
          '<table class="data-table" style="margin-top:8px;font-size:.85rem"><thead><tr><th>행</th><th></th><th>LOT</th><th>상세</th></tr></thead><tbody>' + resultsHtml + '</tbody></table>' +
          '</div>';
        showToast(res.ok ? 'success' : 'warning', res.message || '완료');
        dbgLog('🟢','QUICK-PASTE', res.message, '#66bb6a');
        if (_currentRoute === 'inventory' && typeof loadInventoryPage === 'function') loadInventoryPage();
        if (typeof loadKpi === 'function') loadKpi();
        cancel.disabled = false;
        submit.disabled = false;
      }).catch(function(e) {
        result.innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml(e.message||String(e)) + '</div>';
        showToast('error', '실패: ' + (e.message||String(e)));
        submit.disabled = false; cancel.disabled = false;
      });
    });
  }
  window.showQuickOutboundPasteModal = showQuickOutboundPasteModal;

  /* ===================================================
     8i. F028 출고 확정 — PICKED → OUTBOUND
     =================================================== */
  function showOutboundConfirmModal() {
    var html = [
      '<div style="max-width:640px">',
      '  <h2 style="margin:0 0 12px 0">✅ 출고 확정 — PICKED → OUTBOUND</h2>',
      '  <p style="color:var(--text-muted);margin:0 0 12px 0;font-size:.9rem">',
      '    PICKED 상태인 톤백을 실제 출고(OUTBOUND)로 확정합니다.',
      '  </p>',
      '  <div style="display:grid;grid-template-columns:110px 1fr;gap:10px;align-items:center;margin-bottom:10px">',
      '    <label style="font-weight:600">LOT 번호</label>',
      '    <input type="text" id="oc-lot" placeholder="비워두면 전체 — force_all 필수" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;font-family:monospace">',
      '  </div>',
      '  <label style="display:flex;align-items:center;gap:8px;padding:8px;background:var(--bg-hover);border-radius:6px;font-size:.85rem;margin-bottom:10px;color:var(--warning)">',
      '    <input type="checkbox" id="oc-force-all"> ⚠️ <strong>force_all</strong> — LOT 번호 없이 <u>전체 PICKED 일괄 확정</u> (위험)',
      '  </label>',
      '  <div id="oc-preview" style="padding:8px;background:var(--bg-hover);border-radius:6px;font-size:.85rem;color:var(--text-muted);margin-bottom:12px;min-height:40px">',
      '    LOT 번호 입력 또는 force_all 체크 시 PICKED 톤백 요약이 표시됩니다',
      '  </div>',
      '  <div id="oc-result" style="margin-bottom:12px"></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button id="oc-cancel" class="btn btn-ghost">닫기</button>',
      '    <button id="oc-submit" class="btn btn-primary" disabled>출고 확정</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);

    var lot = document.getElementById('oc-lot');
    var force = document.getElementById('oc-force-all');
    var preview = document.getElementById('oc-preview');
    var result = document.getElementById('oc-result');
    var submit = document.getElementById('oc-submit');
    var cancel = document.getElementById('oc-cancel');

    var _deb = null;
    function loadSummary() {
      var q = lot.value.trim();
      preview.innerHTML = '⏳ 조회 중...';
      var url = '/api/outbound/picked-summary' + (q ? ('?lot_no=' + encodeURIComponent(q)) : '');
      apiGet(url).then(function(res){
        if (!res || !res.ok) { preview.innerHTML = '❌ 조회 실패'; submit.disabled = true; return; }
        var d = res.data || {};
        if ((d.total_count||0) === 0) {
          preview.innerHTML = '<span style="color:var(--warning)">⚠️ PICKED 상태 톤백이 없습니다 — 확정할 대상 없음</span>';
          submit.disabled = true;
          return;
        }
        var items = (d.items||[]).slice(0, 5).map(function(it){
          return '<tr><td class="mono-cell" style="color:var(--accent)">'+escapeHtml(it.lot_no)+'</td><td>'+it.count+'</td><td>'+(it.total_weight_mt||0).toFixed(3)+'</td><td>'+escapeHtml(it.picked_to||'-')+'</td><td class="mono-cell">'+escapeHtml(it.sale_ref||'-')+'</td></tr>';
        }).join('');
        var more = (d.items||[]).length > 5 ? '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">...외 '+((d.items||[]).length-5)+'개 LOT</td></tr>' : '';
        preview.innerHTML =
          '<div style="font-weight:600;margin-bottom:6px;color:var(--accent)">대상: ' + (d.total_lots||0) + ' LOT · ' + (d.total_count||0) + '개 톤백 · ' + (d.total_weight_mt||0).toFixed(3) + ' MT</div>' +
          '<table class="data-table" style="font-size:.85rem"><thead><tr><th>LOT</th><th>개수</th><th>MT</th><th>고객</th><th>sale_ref</th></tr></thead><tbody>' + items + more + '</tbody></table>';
        // submit enable 조건: lot_no 있거나 force_all true
        submit.disabled = !(q || force.checked);
      }).catch(function(e){
        preview.innerHTML = '❌ 조회 실패: ' + escapeHtml(e.message||String(e));
        submit.disabled = true;
      });
    }
    function scheduleSummary() {
      if (_deb) clearTimeout(_deb);
      _deb = setTimeout(loadSummary, 300);
    }
    lot.addEventListener('input', scheduleSummary);
    force.addEventListener('change', loadSummary);
    // 초기 로드 — 전체 PICKED
    loadSummary();

    cancel.addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; });
    submit.addEventListener('click', function(){
      var payload = { lot_no: lot.value.trim(), force_all: force.checked };
      var msg = payload.lot_no ? ('LOT ' + payload.lot_no + ' 의 PICKED 톤백을 OUTBOUND 로 확정합니다.') :
                                  '⚠️ LOT 미지정 — 전체 PICKED 일괄 확정입니다! 매우 위험.';
      if (!confirm(msg + '\n계속하시겠습니까?')) return;

      submit.disabled = true; cancel.disabled = true;
      result.innerHTML = '<div style="padding:8px;color:var(--text-muted)">⏳ 확정 중...</div>';

      apiPost('/api/outbound/confirm', payload).then(function(res){
        if (res && res.ok) {
          var d = res.data || {};
          result.innerHTML =
            '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--success)">' +
            '<div style="font-weight:600">✅ ' + escapeHtml(res.message||'확정 완료') + '</div>' +
            '<div style="color:var(--text-muted);font-size:.85rem;margin-top:4px">LOT: ' + escapeHtml(d.lot_no||'-') + ' · 확정 <strong>' + (d.confirmed||0) + '</strong>개</div>' +
            '</div>';
          showToast('success', res.message || '확정 완료');
          dbgLog('🟢','CONFIRM-OUTBOUND OK', res.message, '#66bb6a');
          if (_currentRoute === 'inventory' && typeof loadInventoryPage === 'function') loadInventoryPage();
          if (typeof loadKpi === 'function') loadKpi();
          loadSummary();
          cancel.disabled = false;
        } else {
          var errs = (res && res.data && res.data.errors) || [];
          var msg2 = (res && (res.message || res.error)) || '실패';
          result.innerHTML =
            '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--danger)">' +
            '<div style="font-weight:600">❌ ' + escapeHtml(msg2) + '</div>' +
            (errs.length ? '<ul style="margin:8px 0 0 18px;color:var(--text-muted);font-size:.85rem">' + errs.map(function(e){return '<li>'+escapeHtml(e)+'</li>';}).join('') + '</ul>' : '') +
            '</div>';
          showToast('error', msg2);
          submit.disabled = false; cancel.disabled = false;
        }
      }).catch(function(e){
        result.innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml(e.message||String(e)) + '</div>';
        showToast('error', '실패: ' + (e.message||String(e)));
        submit.disabled = false; cancel.disabled = false;
      });
    });
  }
  window.showOutboundConfirmModal = showOutboundConfirmModal;

  /* ===================================================
     8i. 입고 취소 — LOT 선택 → POST /api/action2/inbound-cancel
     =================================================== */
  function showInboundCancelModal() {
    var html = [
      '<div style="max-width:480px">',
      '  <h2 style="margin:0 0 12px 0">↩️ 입고 취소</h2>',
      '  <p style="color:var(--text-muted);margin:0 0 16px 0;font-size:.9rem">',
      '    입고된 LOT를 취소(CANCELLED)합니다. 톤백 포함 원복됩니다.',
      '  </p>',
      '  <div style="display:grid;grid-template-columns:100px 1fr;gap:10px;align-items:center;margin-bottom:16px">',
      '    <label style="font-weight:600">LOT 번호</label>',
      '    <input type="text" id="ic-lot" placeholder="예: L240101-001" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;font-family:monospace">',
      '    <label style="font-weight:600">사유</label>',
      '    <input type="text" id="ic-reason" placeholder="취소 사유 (선택)" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '  </div>',
      '  <div id="ic-result" style="margin-bottom:12px;min-height:24px"></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button id="ic-cancel" class="btn btn-ghost">닫기</button>',
      '    <button id="ic-submit" class="btn btn-primary">입고 취소</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);
    var cancel = document.getElementById('ic-cancel');
    var submit = document.getElementById('ic-submit');
    var result = document.getElementById('ic-result');
    cancel.addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; });
    submit.addEventListener('click', function(){
      var lot = document.getElementById('ic-lot').value.trim();
      if (!lot) { showToast('warning', 'LOT 번호를 입력하세요'); return; }
      if (!confirm('LOT ' + lot + ' 입고를 취소합니다. 계속할까요?')) return;
      submit.disabled = true; cancel.disabled = true;
      result.innerHTML = '<div style="padding:8px;color:var(--text-muted)">⏳ 처리 중...</div>';
      apiPost('/api/action2/inbound-cancel', { lot_no: lot, reason: document.getElementById('ic-reason').value.trim() })
        .then(function(res){
          if (res && res.ok) {
            result.innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--success)"><div style="font-weight:600">✅ ' + escapeHtml(res.message||'입고 취소 완료') + '</div></div>';
            showToast('success', res.message || '입고 취소 완료');
            if (typeof loadKpi === 'function') loadKpi();
          } else {
            result.innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--danger)"><div style="font-weight:600">❌ ' + escapeHtml((res&&res.message)||'실패') + '</div></div>';
            showToast('error', (res&&res.message)||'실패');
            submit.disabled = false; cancel.disabled = false;
          }
        })
        .catch(function(e){
          result.innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml(e.message||String(e)) + '</div>';
          submit.disabled = false; cancel.disabled = false;
        });
    });
  }
  window.showInboundCancelModal = showInboundCancelModal;

  /* ===================================================
     8j. 승인 대기 (Allocation Approval Queue)
     =================================================== */
  function showApprovalQueueModal() {
    showDataModal('✅ 승인 대기','<div style="padding:20px;text-align:center">⏳ Loading...</div>');
    apiGet('/api/q/approval-history').then(function(res){
      var rows = extractRows(res);
      var pending = rows.filter(function(r){ return (r.approval_status||'').toUpperCase() === 'PENDING'; });
      var html;
      if (!pending.length && !rows.length) {
        html = '<div class="empty">승인 대기 건이 없습니다</div>';
      } else {
        var tgt = pending.length ? pending : rows;
        html = '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:12px">총 ' + tgt.length + '건' + (pending.length ? ' (PENDING)' : ' (전체 이력)') + '</p>';
        html += '<table class="data-table"><thead><tr><th>LOT</th><th>고객</th><th>수량</th><th>상태</th><th>요청일</th></tr></thead><tbody>';
        html += tgt.slice(0,50).map(function(r){
          return '<tr><td class="mono-cell">'+escapeHtml(r.lot_no||'-')+'</td><td>'+escapeHtml(r.sold_to||r.customer||'-')+'</td><td>'+(r.qty_mt!=null?Number(r.qty_mt).toFixed(3):'-')+'</td><td><span class="tag">'+escapeHtml(r.approval_status||r.status||'-')+'</span></td><td>'+escapeHtml(r.request_date||r.created_at||'-')+'</td></tr>';
        }).join('');
        html += '</tbody></table>';
      }
      document.getElementById('sqm-modal-content').innerHTML = '<h2 style="margin-bottom:16px">✅ 승인 대기 (Allocation)</h2>' + html;
    }).catch(function(e){
      document.getElementById('sqm-modal-content').innerHTML = '<h2>승인 대기</h2><div class="empty">조회 실패: ' + escapeHtml(e.message||String(e)) + '</div>';
    });
  }
  window.showApprovalQueueModal = showApprovalQueueModal;

  /* ===================================================
     8k. 백업 복원 — 목록 조회 → 선택 → 복원 실행
     =================================================== */
  function showRestoreModal() {
    showDataModal('🔄 백업 복원','<div style="padding:20px;text-align:center">⏳ 백업 목록 로딩...</div>');
    apiGet('/api/q/backup-list').then(function(res){
      var rows = extractRows(res);
      if (!rows.length) {
        document.getElementById('sqm-modal-content').innerHTML = '<h2>🔄 백업 복원</h2><div class="empty">사용 가능한 백업 파일이 없습니다</div>';
        return;
      }
      var html = '<h2 style="margin-bottom:12px">🔄 백업 복원</h2>';
      html += '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:12px">복원할 백업 파일을 선택하세요. <strong style="color:var(--warning)">⚠️ 현재 DB가 덮어씌워집니다!</strong></p>';
      html += '<div style="max-height:300px;overflow:auto"><table class="data-table"><thead><tr><th>선택</th><th>파일명</th><th>크기</th><th>생성일</th></tr></thead><tbody>';
      html += rows.map(function(r, i){
        return '<tr><td><input type="radio" name="restore-sel" value="'+i+'" data-file="'+escapeHtml(r.filename||r.name||'')+'"></td><td class="mono-cell">'+escapeHtml(r.filename||r.name||'-')+'</td><td>'+(r.size_mb!=null?r.size_mb.toFixed(2)+' MB':(r.size||'-'))+'</td><td>'+escapeHtml(r.modified||r.mtime||r.created||'-')+'</td></tr>';
      }).join('');
      html += '</tbody></table></div>';
      html += '<div id="restore-result" style="margin:12px 0;min-height:24px"></div>';
      html += '<div style="display:flex;gap:8px;justify-content:flex-end"><button id="restore-cancel" class="btn btn-ghost">닫기</button><button id="restore-submit" class="btn btn-primary">복원 실행</button></div>';
      document.getElementById('sqm-modal-content').innerHTML = html;

      document.getElementById('restore-cancel').addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; });
      document.getElementById('restore-submit').addEventListener('click', function(){
        var sel = document.querySelector('input[name="restore-sel"]:checked');
        if (!sel) { showToast('warning', '복원할 백업 파일을 선택하세요'); return; }
        var fname = sel.dataset.file;
        if (!confirm('⚠️ ' + fname + ' 으로 DB를 복원합니다.\n현재 데이터가 모두 덮어씌워집니다.\n\n정말 계속할까요?')) return;
        var btn = document.getElementById('restore-submit');
        btn.disabled = true;
        document.getElementById('restore-result').innerHTML = '<div style="padding:8px;color:var(--text-muted)">⏳ 복원 중...</div>';
        apiPost('/api/action/restore', { filename: fname })
          .then(function(res){
            if (res && res.ok) {
              document.getElementById('restore-result').innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--success)"><div style="font-weight:600">✅ ' + escapeHtml(res.message||'복원 완료') + '</div></div>';
              showToast('success', res.message || '복원 완료');
            } else {
              document.getElementById('restore-result').innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml((res&&res.message)||'복원 실패') + '</div>';
              btn.disabled = false;
            }
          })
          .catch(function(e){
            document.getElementById('restore-result').innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml(e.message||String(e)) + '</div>';
            btn.disabled = false;
          });
      });
    }).catch(function(e){
      document.getElementById('sqm-modal-content').innerHTML = '<h2>🔄 백업 복원</h2><div class="empty">백업 목록 조회 실패: ' + escapeHtml(e.message||String(e)) + '</div>';
    });
  }
  window.showRestoreModal = showRestoreModal;

  /* ===================================================
     8l. 창 크기 저장 / 초기화 — PyWebView API
     =================================================== */
  function saveWindowSize() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_window_size) {
      window.pywebview.api.save_window_size();
      showToast('success', '현재 창 크기가 저장되었습니다');
    } else {
      var w = window.innerWidth, h = window.innerHeight;
      try { getStore().setItem('sqm_window_size', w+'x'+h); } catch(e){}
      showToast('success', '창 크기 저장됨: ' + w + ' x ' + h);
    }
    dbgLog('💾','Window size saved', window.innerWidth + 'x' + window.innerHeight, '#4caf50');
  }
  function resetWindowSize() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.reset_window_size) {
      window.pywebview.api.reset_window_size();
    } else {
      try { window.resizeTo(1500, 900); } catch(e){}
      try { getStore().removeItem('sqm_window_size'); } catch(e){}
    }
    showToast('success', '기본 창 크기(1500x900)로 초기화되었습니다');
    dbgLog('↩️','Window size reset', '1500x900', '#4caf50');
  }

  /* ===================================================
     8m. 반품 다이얼로그 — 2탭: 소량(수동) + 다량(Excel)
     =================================================== */
  function showReturnDialog() {
    var html = [
      '<div style="max-width:600px">',
      '  <h2 style="margin:0 0 12px 0">🔄 반품 (재입고)</h2>',
      '  <div style="display:flex;gap:0;margin-bottom:16px">',
      '    <button id="ret-tab-manual" class="btn btn-ghost" style="flex:1;border-radius:6px 0 0 6px;border:1px solid var(--border);background:var(--accent);color:#fff">📝 소량 반품 (수동)</button>',
      '    <button id="ret-tab-excel" class="btn btn-ghost" style="flex:1;border-radius:0 6px 6px 0;border:1px solid var(--border)">📂 다량 반품 (Excel)</button>',
      '  </div>',
      '  <div id="ret-panel-manual">',
      '    <div style="display:grid;grid-template-columns:100px 1fr;gap:10px;align-items:center;margin-bottom:12px">',
      '      <label style="font-weight:600">LOT 번호</label>',
      '      <input type="text" id="ret-lot" placeholder="반품할 LOT" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;font-family:monospace">',
      '      <label style="font-weight:600">톤백 수</label>',
      '      <input type="number" id="ret-count" placeholder="반품 톤백 수" min="1" value="1" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '      <label style="font-weight:600">사유</label>',
      '      <select id="ret-reason" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '        <option value="품질 불량">품질 불량</option>',
      '        <option value="수량 초과">수량 초과</option>',
      '        <option value="오배송">오배송</option>',
      '        <option value="고객 변심">고객 변심</option>',
      '        <option value="기타">기타</option>',
      '      </select>',
      '      <label style="font-weight:600">메모</label>',
      '      <input type="text" id="ret-memo" placeholder="추가 메모 (선택)" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '    </div>',
      '  </div>',
      '  <div id="ret-panel-excel" style="display:none">',
      '    <p style="color:var(--text-muted);font-size:.9rem;margin-bottom:12px">다량 반품 Excel 파일을 업로드하세요.</p>',
      '    <button id="ret-excel-btn" class="btn btn-primary" style="width:100%">📂 반품 Excel 업로드 열기</button>',
      '  </div>',
      '  <div id="ret-result" style="margin:12px 0;min-height:24px"></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button id="ret-cancel" class="btn btn-ghost">닫기</button>',
      '    <button id="ret-submit" class="btn btn-primary">반품 처리</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);

    var tabManual = document.getElementById('ret-tab-manual');
    var tabExcel = document.getElementById('ret-tab-excel');
    var panelManual = document.getElementById('ret-panel-manual');
    var panelExcel = document.getElementById('ret-panel-excel');
    var submitBtn = document.getElementById('ret-submit');

    tabManual.addEventListener('click', function(){
      panelManual.style.display=''; panelExcel.style.display='none';
      tabManual.style.background='var(--accent)'; tabManual.style.color='#fff';
      tabExcel.style.background=''; tabExcel.style.color='';
      submitBtn.style.display='';
    });
    tabExcel.addEventListener('click', function(){
      panelManual.style.display='none'; panelExcel.style.display='';
      tabExcel.style.background='var(--accent)'; tabExcel.style.color='#fff';
      tabManual.style.background=''; tabManual.style.color='';
      submitBtn.style.display='none';
    });
    document.getElementById('ret-excel-btn').addEventListener('click', function(){
      document.getElementById('sqm-modal').style.display='none';
      showReturnInboundUploadModal();
    });
    document.getElementById('ret-cancel').addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; });
    submitBtn.addEventListener('click', function(){
      var lot = document.getElementById('ret-lot').value.trim();
      if (!lot) { showToast('warning', 'LOT 번호를 입력하세요'); return; }
      if (!confirm('LOT ' + lot + ' 반품 처리를 진행합니다.')) return;
      submitBtn.disabled = true;
      var result = document.getElementById('ret-result');
      result.innerHTML = '<div style="padding:8px;color:var(--text-muted)">⏳ 처리 중...</div>';
      apiPost('/api/action3/return-create', {
        lot_no: lot,
        tonbag_count: parseInt(document.getElementById('ret-count').value)||1,
        reason: document.getElementById('ret-reason').value,
        memo: document.getElementById('ret-memo').value.trim()
      }).then(function(res){
        if (res && res.ok) {
          result.innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--success)"><div style="font-weight:600">✅ ' + escapeHtml(res.message||'반품 완료') + '</div></div>';
          showToast('success', res.message || '반품 완료');
        } else {
          result.innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml((res&&res.message)||'실패') + '</div>';
          submitBtn.disabled = false;
        }
      }).catch(function(e){
        result.innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml(e.message||String(e)) + '</div>';
        submitBtn.disabled = false;
      });
    });
  }
  window.showReturnDialog = showReturnDialog;

  /* ===================================================
     8n. LOT Allocation·톤백 현황 조회
     =================================================== */
  function showLotAllocationAuditModal() {
    var html = [
      '<div style="max-width:700px">',
      '  <h2 style="margin:0 0 12px 0">📊 LOT Allocation·톤백 현황</h2>',
      '  <div style="display:flex;gap:8px;margin-bottom:16px;align-items:center">',
      '    <input type="text" id="laa-lot" placeholder="LOT 번호 (비우면 전체)" style="flex:1;padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;font-family:monospace">',
      '    <button id="laa-search" class="btn btn-primary">조회</button>',
      '  </div>',
      '  <div id="laa-result" style="min-height:60px"><div class="empty">LOT 번호를 입력하고 조회를 클릭하세요</div></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">',
      '    <button id="laa-close" class="btn btn-ghost">닫기</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);
    document.getElementById('laa-close').addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; });
    document.getElementById('laa-search').addEventListener('click', function(){
      var lot = document.getElementById('laa-lot').value.trim();
      var result = document.getElementById('laa-result');
      result.innerHTML = '<div style="padding:20px;text-align:center">⏳ 조회 중...</div>';
      var url = '/api/q/product-inventory' + (lot ? '?lot_no=' + encodeURIComponent(lot) : '');
      apiGet(url).then(function(res){
        var rows = extractRows(res);
        if (!rows.length) { result.innerHTML = '<div class="empty">데이터가 없습니다</div>'; return; }
        var tbl = '<table class="data-table"><thead><tr><th>LOT</th><th>제품</th><th>상태</th><th>톤백수</th><th>중량(MT)</th><th>위치</th></tr></thead><tbody>';
        tbl += rows.slice(0,100).map(function(r){
          return '<tr><td class="mono-cell" style="color:var(--accent)">'+escapeHtml(r.lot_no||'-')+'</td><td>'+escapeHtml(r.product||'-')+'</td><td><span class="tag">'+escapeHtml(r.status||'-')+'</span></td><td>'+(r.tonbag_count||r.total_tonbags||'-')+'</td><td>'+(r.net_weight!=null?Number(r.net_weight).toFixed(3):(r.total_weight||'-'))+'</td><td>'+escapeHtml(r.location||r.warehouse||'-')+'</td></tr>';
        }).join('');
        tbl += '</tbody></table>';
        result.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:8px">총 ' + rows.length + '건</p>' + tbl;
      }).catch(function(e){
        result.innerHTML = '<div class="empty">조회 실패: ' + escapeHtml(e.message||String(e)) + '</div>';
      });
    });
  }
  window.showLotAllocationAuditModal = showLotAllocationAuditModal;

  /* ===================================================
     8o. 테스트 DB 초기화 (개발자 전용)
     =================================================== */
  function showTestDbResetModal() {
    var html = [
      '<div style="max-width:480px">',
      '  <h2 style="margin:0 0 12px 0;color:var(--danger)">🗑️ 테스트 DB 초기화</h2>',
      '  <div style="padding:16px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--danger);margin-bottom:16px">',
      '    <div style="font-weight:600;color:var(--danger)">⚠️ 위험한 작업</div>',
      '    <div style="color:var(--text-muted);font-size:.9rem;margin-top:4px">모든 데이터가 삭제됩니다. 이 작업은 되돌릴 수 없습니다.</div>',
      '  </div>',
      '  <div style="margin-bottom:16px">',
      '    <label style="display:flex;align-items:center;gap:8px;color:var(--warning)">',
      '      <input type="checkbox" id="dbr-confirm"> 위 내용을 이해했으며 DB를 초기화합니다',
      '    </label>',
      '  </div>',
      '  <div id="dbr-result" style="margin-bottom:12px;min-height:24px"></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button id="dbr-cancel" class="btn btn-ghost">닫기</button>',
      '    <button id="dbr-submit" class="btn btn-primary" disabled style="background:var(--danger)">초기화 실행</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);
    var chk = document.getElementById('dbr-confirm');
    var submit = document.getElementById('dbr-submit');
    chk.addEventListener('change', function(){ submit.disabled = !chk.checked; });
    document.getElementById('dbr-cancel').addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; });
    submit.addEventListener('click', function(){
      if (!confirm('정말로 DB를 완전 초기화할까요?\n\n이 작업은 되돌릴 수 없습니다!')) return;
      submit.disabled = true;
      document.getElementById('dbr-result').innerHTML = '<div style="padding:8px;color:var(--text-muted)">⏳ 초기화 중...</div>';
      apiPost('/api/action3/db-reset', { confirm: true })
        .then(function(res){
          if (res && res.ok) {
            document.getElementById('dbr-result').innerHTML = '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;border-left:4px solid var(--success)"><div style="font-weight:600">✅ DB 초기화 완료</div></div>';
            showToast('success', 'DB 초기화 완료');
          } else {
            document.getElementById('dbr-result').innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml((res&&res.message)||'실패') + '</div>';
            submit.disabled = false;
          }
        })
        .catch(function(e){
          document.getElementById('dbr-result').innerHTML = '<div style="padding:12px;color:var(--danger)">❌ ' + escapeHtml(e.message||String(e)) + '</div>';
          submit.disabled = false;
        });
    });
  }
  window.showTestDbResetModal = showTestDbResetModal;

  /* ===================================================
     8p. 바코드 스캔 업로드 — CSV/Excel 파일 업로드
     =================================================== */
  function showBarcodeScanUploadModal() {
    _showExcelUploadModal({
      title: '📊 바코드 스캔 업로드',
      subtitle: '바코드 스캔 결과 파일(Excel/CSV)을 선택하세요. 스캔된 UID와 LOT를 매칭하여 출고 처리합니다.',
      endpoint: '/api/inbound/bulk-import-excel',
      onSuccess: function(d) {
        return '<div style="color:var(--text-muted);font-size:.85rem">처리 결과: 성공 ' + (d.success_count||0) + ' / 실패 ' + (d.fail_count||0) + '</div>';
      }
    });
  }
  window.showBarcodeScanUploadModal = showBarcodeScanUploadModal;

  /* ===================================================
     8q. 설정 다이얼로그 모음 — 이메일/자동백업/템플릿
     =================================================== */
  function showSettingsDialog(title, icon, fields) {
    var html = '<div style="max-width:480px"><h2 style="margin:0 0 16px 0">' + icon + ' ' + escapeHtml(title) + '</h2>';
    html += '<div style="display:grid;grid-template-columns:130px 1fr;gap:10px;align-items:center;margin-bottom:16px">';
    fields.forEach(function(f){
      html += '<label style="font-weight:600">' + escapeHtml(f.label) + '</label>';
      if (f.type === 'select') {
        html += '<select id="sdlg-'+f.id+'" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">';
        f.options.forEach(function(o){ html += '<option value="'+escapeHtml(o)+'">'+escapeHtml(o)+'</option>'; });
        html += '</select>';
      } else if (f.type === 'checkbox') {
        html += '<label style="display:flex;align-items:center;gap:6px"><input type="checkbox" id="sdlg-'+f.id+'"' + (f.checked ? ' checked' : '') + '> ' + escapeHtml(f.hint||'') + '</label>';
      } else {
        html += '<input type="'+(f.type||'text')+'" id="sdlg-'+f.id+'" placeholder="'+escapeHtml(f.hint||'')+'" value="'+escapeHtml(f.value||'')+'" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">';
      }
    });
    html += '</div>';
    html += '<div style="padding:12px;background:var(--bg-hover);border-radius:6px;margin-bottom:16px;font-size:.85rem;color:var(--text-muted)">💡 설정은 현재 세션에만 적용됩니다. PyWebView 재시작 시 기본값으로 복원됩니다.</div>';
    html += '<div style="display:flex;gap:8px;justify-content:flex-end"><button onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'" class="btn btn-ghost">닫기</button><button onclick="showToast(\'success\',\'설정 저장됨\');document.getElementById(\'sqm-modal\').style.display=\'none\'" class="btn btn-primary">저장</button></div>';
    html += '</div>';
    showDataModal('', html);
  }

  function showEmailConfigModal() {
    showSettingsDialog('이메일 설정', '⚙️', [
      { id:'host', label:'SMTP 서버', hint:'smtp.gmail.com', value:'smtp.gmail.com' },
      { id:'port', label:'포트', type:'number', hint:'587', value:'587' },
      { id:'user', label:'사용자', hint:'user@company.com' },
      { id:'pass', label:'비밀번호', type:'password', hint:'앱 비밀번호' },
      { id:'tls', label:'TLS 사용', type:'checkbox', checked:true, hint:'TLS 암호화' }
    ]);
  }
  window.showEmailConfigModal = showEmailConfigModal;

  function showAutoBackupSettingsModal() {
    showSettingsDialog('자동 백업 설정', '⏰', [
      { id:'enabled', label:'자동 백업', type:'checkbox', checked:false, hint:'활성화' },
      { id:'interval', label:'주기', type:'select', options:['30분','1시간','3시간','6시간','12시간','24시간'] },
      { id:'retention', label:'보존 개수', type:'number', hint:'최대 보존 백업 수', value:'10' },
      { id:'path', label:'저장 경로', hint:'backup/', value:'backup/' }
    ]);
  }
  window.showAutoBackupSettingsModal = showAutoBackupSettingsModal;

  /* 폰트 크기 전역 설정 */
  window.sqmSetFontScale = function(pct) {
    document.body.style.zoom = (pct / 100);
    window._sqmFontScale = pct;
    showToast('success', '폰트 크기: ' + pct + '%');
  };
  function showFontSizeModal() {
    var cur = window._sqmFontScale || 100;
    var html = '<div style="max-width:420px">'
      + '<h2 style="margin:0 0 14px 0">🔤 화면 폰트 크기</h2>'
      + '<p style="color:var(--text-muted);font-size:.9rem;margin-bottom:16px">'
      + '전체 UI 폰트를 일괄 확대합니다. 100% = 기본값.</p>'
      + '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px">';
    [100,110,120,130,140,150].forEach(function(p) {
      html += '<button class="btn' + (cur === p ? ' btn-primary' : '') + '"'
        + ' onclick="window.sqmSetFontScale(' + p + ');'
        + 'document.getElementById(\'sqm-modal\').style.display=\'none\'"'
        + ' style="min-width:66px;font-size:14px">' + p + '%</button>';
    });
    html += '</div>'
      + '<div style="display:flex;gap:8px;justify-content:flex-end">'
      + '<button class="btn btn-ghost" onclick="window.sqmSetFontScale(100);'
      + 'document.getElementById(\'sqm-modal\').style.display=\'none\'">초기화 (100%)</button>'
      + '<button class="btn btn-ghost" onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'">닫기</button>'
      + '</div></div>';
    showDataModal('', html);
  }
  window.showFontSizeModal = showFontSizeModal;

    /* ═══════════════════════════════════════════════════════════
     입고 파싱 템플릿 관리 (풀 CRUD)
     6컬럼: 순번 | 선사 | 템플릿이름 | 제품이름 | 톤백무게 | BL형식
     생성: 수동입력 / PDF파싱추출 / Excel업로드
     ═══════════════════════════════════════════════════════════ */
  var _tplMid = 'sqm-inbound-tpl-mgr';
  var _tplEditId = null;  // null=신규, string=수정 중인 template_id

    /* ══ 입고 파싱 템플릿 관리 (풀 CRUD) ══ */
  var _tplMid = 'sqm-inbound-tpl-mgr';
  var _tplEditId = null;

  function showInboundTemplateModal() {
    var ex = document.getElementById(_tplMid);
    if (ex) { ex.remove(); }
    var m = document.createElement('div');
    m.id = _tplMid;
    m.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.65);z-index:99980;display:flex;align-items:flex-start;justify-content:center;overflow-y:auto;padding:24px 0';
    m.innerHTML = _tplShell();
    document.body.appendChild(m);
    m.addEventListener('click', function(e){ if (e.target === m) m.remove(); });
    _tplLoadList();
  }
  window.showInboundTemplateModal = showInboundTemplateModal;

  function _tplClose() {
    var m = document.getElementById(_tplMid);
    if (m) m.remove();
  }

  function _tplShell() {
    return [
      '<div id="sqm-tpl-inner" style="background:var(--panel,#12233a);border:1px solid',
      ' var(--panel-border,#1e4a7a);border-radius:10px;padding:24px 28px;',
      'width:880px;max-width:96vw;color:var(--fg)">',
      /* 헤더 */
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">',
      '<span style="font-size:16px;font-weight:700">📋 입고 파싱 템플릿 관리</span>',
      '<button class="btn" onclick="window._tplClose()">✕ 닫기</button>',
      '</div>',
      /* 툴바 */
      '<div style="display:flex;gap:8px;margin-bottom:14px">',
      '<button class="btn btn-primary" onclick="window._tplShowForm(null)">➕ 수동 추가</button>',
      '<label class="btn" style="cursor:pointer;margin:0">',
      '📄 PDF에서 추출',
      '<input type="file" accept=".pdf" style="display:none" onchange="window._tplFromPdf(this)">',
      '</label>',
      '<label class="btn" style="cursor:pointer;margin:0">',
      '📊 Excel 일괄등록',
      '<input type="file" accept=".xlsx,.xls,.csv" style="display:none" onchange="window._tplFromExcel(this)">',
      '</label>',
      '<button class="btn" onclick="window._tplLoadList()" style="margin-left:auto">🔄 새로고침</button>',
      '</div>',
      '<div id="sqm-tpl-form-area" style="display:none"></div>',
      '<div id="sqm-tpl-table-area"><div style="color:var(--text-muted);padding:20px;text-align:center">',
      '⏳ 로딩 중...</div></div>',
      '</div>'
    ].join('');
  }

  window._tplClose = _tplClose;

  window._tplLoadList = function() { _tplLoadList(); };

  function _tplLoadList() {
    var area = document.getElementById('sqm-tpl-table-area');
    if (!area) return;
    area.innerHTML = '<div style="color:var(--text-muted);padding:16px;text-align:center">⏳ 로딩 중...</div>';
    fetch(API + '/api/inbound/templates')
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (!area) return;
        if (!d.ok) {
          area.innerHTML = '<div style="color:var(--danger)">❌ ' + escapeHtml(d.error || '로드 실패') + '</div>';
          return;
        }
        var rows = d.templates || [];
        if (rows.length === 0) {
          area.innerHTML = '<div style="color:var(--text-muted);padding:20px;text-align:center">📭 등록된 템플릿이 없습니다.<br><small>위 버튼으로 추가하세요</small></div>';
          return;
        }
        var TH = '<th style="padding:8px 6px;text-align:left;color:var(--text-muted);border-bottom:2px solid var(--border)">';
        var html = '<table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr>'
          + TH + '순번</th>'
          + TH + '선사</th>'
          + TH + '템플릿 이름</th>'
          + TH + '제품 이름</th>'
          + '<th style="padding:8px 6px;text-align:center;color:var(--text-muted);border-bottom:2px solid var(--border);width:80px">톬백무게</th>'
          + TH + 'BL 형식</th>'
          + '<th style="padding:8px 6px;text-align:center;color:var(--text-muted);border-bottom:2px solid var(--border);width:80px">작업</th>'
          + '</tr></thead><tbody>';
        var _tplRowsCache = {};
        rows.forEach(function(t, i) {
          _tplRowsCache[String(t.template_id)] = t;
          var bg = i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.03)';
          var bw = t.bag_weight_kg || 500;
          var tidSafe   = escapeHtml(String(t.template_id));
          var tnameSafe = escapeHtml(t.template_name || '');
          html += '<tr style="border-bottom:1px solid var(--border);background:' + bg + '">'
            + '<td style="padding:8px 6px;color:var(--text-muted)">' + (i+1) + '</td>'
            + '<td style="padding:8px 6px;font-weight:600">' + escapeHtml(t.carrier_id || '') + '</td>'
            + '<td style="padding:8px 6px">' + escapeHtml(t.template_name || '') + '</td>'
            + '<td style="padding:8px 6px;color:var(--text-muted)">' + escapeHtml(t.product_hint || '') + '</td>'
            + '<td style="padding:8px 6px;text-align:center"><span style="background:var(--info,#1565c0);color:#fff;border-radius:4px;padding:2px 7px;font-size:11px">' + bw + 'kg</span></td>'
            + '<td style="padding:8px 6px;font-family:monospace;font-size:12px">' + escapeHtml(t.bl_format || '') + '</td>'
            + '<td style="padding:8px 6px;text-align:center">'
            + '<button class="btn btn-sm tpl-edit-btn" data-tid="' + tidSafe + '" style="margin-right:4px">✏️</button>'
            + '<button class="btn btn-sm tpl-del-btn"  data-tid="' + tidSafe + '" data-tname="' + tnameSafe + '" style="background:rgba(244,67,54,0.12);color:var(--danger,#f44336)">🗑️</button>'
            + '</td></tr>';
        });
        html += '</tbody></table>';
        area.innerHTML = html;
        /* click handler: data-* attr -> safe call */
        area.addEventListener('click', function(e) {
          var editBtn = e.target.closest('.tpl-edit-btn');
          var delBtn  = e.target.closest('.tpl-del-btn');
          if (editBtn) {
            var tid = editBtn.getAttribute('data-tid');
            window._tplShowForm(_tplRowsCache[tid] || null);
          }
          if (delBtn) {
            var tid2  = delBtn.getAttribute('data-tid');
            var tname = delBtn.getAttribute('data-tname');
            window._tplDelete(tid2, tname);
          }
        });
      })
      .catch(function(e) {
        if (area) area.innerHTML = '<div style="color:var(--danger)">❌ ' + escapeHtml(String(e)) + '</div>';
      });
  }

  function _tplFld(id, label, val, type, hint) {
    return '<label style="display:flex;flex-direction:column;gap:4px">'
      + '<span style="font-size:12px;color:var(--text-muted)">' + escapeHtml(label) + '</span>'
      + '<input id="' + id + '" type="' + type + '" value="' + escapeHtml(String(val||'')) + '"'
      + ' placeholder="' + escapeHtml(hint) + '"'
      + ' style="padding:7px 10px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:6px"></label>';
  }

  window._tplShowForm = function(tObj) {
    _tplEditId = tObj && tObj.template_id ? tObj.template_id : null;
    var t = tObj || {};
    var bw = t.bag_weight_kg || 500;
    var area = document.getElementById('sqm-tpl-form-area');
    if (!area) return;
    var title = _tplEditId ? '✏️ 템플릿 수정' : '➕ 새 템플릿 추가';
    var wOpts = [500, 450, 600, 1000].map(function(w) {
      return '<option value="' + w + '"' + (bw === w ? ' selected' : '') + '>' + w + ' kg</option>';
    }).join('');
    area.innerHTML = '<div style="background:rgba(30,74,122,0.18);border:1px solid var(--border);border-radius:8px;padding:16px 18px;margin-bottom:14px">'
      + '<div style="font-weight:700;margin-bottom:12px">' + title + '</div>'
      + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px 16px">'
      + _tplFld('tpl-f-carrier', '선사', t.carrier_id||'', 'text', '예: Maersk, ONE, MSC')
      + _tplFld('tpl-f-name', '템플릿 이름 *', t.template_name||'', 'text', '예: Maersk SQM 500kg 표준')
      + _tplFld('tpl-f-product', '제품 이름', t.product_hint||'', 'text', '예: SQM Potassium Nitrate')
      + _tplFld('tpl-f-bl', 'BL 형식', t.bl_format||'', 'text', '예: MEDUXXXX')
      + '<label style="display:flex;flex-direction:column;gap:4px"><span style="font-size:12px;color:var(--text-muted)">톬백 무게 (kg)</span>'
      + '<select id="tpl-f-weight" style="padding:7px 10px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:6px">' + wOpts + '</select></label>'
      + _tplFld('tpl-f-hint', 'Gemini 파싱 힌트', t.gemini_hint_packing||'', 'text', '예: 3행부터 데이터, 열 순서 주의')
      + _tplFld('tpl-f-note', '메모', t.note||'', 'text', '자유 입력')
      + '</div>'
      + '<div style="display:flex;gap:8px;margin-top:14px">'
      + '<button class="btn btn-primary" onclick="window._tplSave()">💾 저장</button>'
      + '<button class="btn" onclick="window._tplCancelForm()">취소</button>'
      + '</div></div>';
    area.style.display = '';
    var el = document.getElementById('tpl-f-carrier');
    if (el) el.focus();
  };

  window._tplCancelForm = function() {
    _tplEditId = null;
    var area = document.getElementById('sqm-tpl-form-area');
    if (area) { area.innerHTML = ''; area.style.display = 'none'; }
  };

  window._tplSave = function() {
    var carrier = (document.getElementById('tpl-f-carrier') || {}).value || '';
    var name    = (document.getElementById('tpl-f-name')    || {}).value || '';
    var product = (document.getElementById('tpl-f-product') || {}).value || '';
    var bl      = (document.getElementById('tpl-f-bl')      || {}).value || '';
    var weight  = parseInt((document.getElementById('tpl-f-weight') || {}).value || '500', 10);
    var hint    = (document.getElementById('tpl-f-hint')    || {}).value || '';
    var note    = (document.getElementById('tpl-f-note')    || {}).value || '';
    if (!name.trim()) { showToast('error', '템플릿 이름은 필수입니다'); return; }
    var lotSqm  = (document.getElementById('tpl-f-lotsqm')  || {}).value || '';
    var mxbg    = parseInt((document.getElementById('tpl-f-mxbg') || {}).value || '0', 10) || 0;
    var sapNo   = (document.getElementById('tpl-f-sap')      || {}).value || '';
    var body = {
      carrier_id: carrier.trim(),
      template_name: name.trim(),
      product_hint: product.trim(),
      bag_weight_kg: weight,
      bl_format: bl.trim(),
      gemini_hint_packing: hint.trim(),
      note: note.trim(),
      lot_sqm: lotSqm.trim(),
      mxbg_pallet: mxbg,
      sap_no: sapNo.trim()
    };
    var url    = API + '/api/inbound/templates' + (_tplEditId ? '/' + encodeURIComponent(_tplEditId) : '');
    var method = _tplEditId ? 'PUT' : 'POST';
    fetch(url, { method: method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.ok) {
          showToast('success', _tplEditId ? '수정 완료' : '템플릿 추가 완료');
          window._tplCancelForm();
          _tplLoadList();
        } else {
          showToast('error', '저장 실패: ' + escapeHtml(String(d.detail || d.error || d.message || '')));
        }
      })
      .catch(function(e) { showToast('error', '오류: ' + String(e)); });
  };

  window._tplDelete = function(tid, name) {
    if (!confirm(name + ' 템플릿을 삭제하시겠습니까?')) return;
    fetch(API + '/api/inbound/templates/' + encodeURIComponent(tid), { method: 'DELETE' })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.ok) { showToast('success', '삭제 완료: ' + escapeHtml(name)); _tplLoadList(); }
        else      { showToast('error', '삭제 실패: ' + escapeHtml(String(d.detail || d.error || ''))); }
      })
      .catch(function(e) { showToast('error', '오류: ' + String(e)); });
  };

  window._tplFromPdf = function(input) {
    var file = input.files && input.files[0];
    if (!file) return;
    input.value = '';
    showToast('info', '📄 PDF 파싱 중... 잠시 기다려 주세요');
    var fd = new FormData();
    fd.append('file', file, file.name);
    fetch(API + '/api/inbound/templates/from-pdf', { method: 'POST', body: fd })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (!d.ok) { showToast('error', 'PDF 추출 실패: ' + escapeHtml(String(d.detail || d.error || ''))); return; }
        var ex = d.extracted || {};
        showToast('success', 'PDF 추출 완료 — 내용을 확인하고 저장하세요');
        window._tplShowForm({
          template_id:         null,
          carrier_id:          ex.carrier_id    || '',
          template_name:       ex.suggested_name || '',
          product_hint:        ex.product_hint  || '',
          bag_weight_kg:       ex.bag_weight_kg || 500,
          bl_format:           ex.bl_format     || '',
          gemini_hint_packing: '',
          note: 'PDF 추출: ' + (ex.source_file || file.name),
          lot_sqm: ex.lot_sqm || '',
          mxbg_pallet: ex.mxbg_pallet || 0,
          sap_no: ex.sap_no || '',
        });
      })
      .catch(function(e) { showToast('error', 'PDF 오류: ' + String(e)); });
  };

  window._tplFromExcel = function(input) {
    var file = input.files && input.files[0];
    if (!file) return;
    input.value = '';
    showToast('info', '📊 Excel 처리 중...');
    var fd = new FormData();
    fd.append('file', file, file.name);
    fetch(API + '/api/inbound/templates/from-excel', { method: 'POST', body: fd })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (!d.ok) { showToast('error', 'Excel 실패: ' + escapeHtml(String(d.detail || d.error || ''))); return; }
        showToast('success', d.message || 'Excel 등록 완료');
        _tplLoadList();
      })
      .catch(function(e) { showToast('error', 'Excel 오류: ' + String(e)); });
  };



  function showPickingTemplateModal() {
    showSettingsDialog('출고 피킹 템플릿 관리', '📦', [
      { id:'name', label:'템플릿 이름', hint:'기본 피킹 리스트' },
      { id:'format', label:'형식', type:'select', options:['Standard PDF','Custom Excel','Barcode List'] },
      { id:'cols', label:'출력 컬럼', hint:'lot_no,product,weight,...' },
      { id:'sort', label:'정렬 기준', type:'select', options:['LOT 번호','제품명','위치','날짜'] }
    ]);
  }
  window.showPickingTemplateModal = showPickingTemplateModal;

  /* ===================================================
     8r. 대량 이동 승인 — 승인 대기 중인 이동 건 목록
     =================================================== */
  function showMoveApprovalQueueModal() {
    showDataModal('✅ 대량 이동 승인','<div style="padding:20px;text-align:center">⏳ Loading...</div>');
    apiGet('/api/q/audit-log').then(function(res){
      var rows = extractRows(res);
      var moves = rows.filter(function(r){ return (r.event_type||'').indexOf('MOVE') >= 0; });
      var html;
      if (!moves.length) {
        html = '<div class="empty">승인 대기 중인 이동 건이 없습니다</div>';
      } else {
        html = '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:12px">' + moves.length + '건의 이동 기록</p>';
        html += '<table class="data-table"><thead><tr><th>일시</th><th>유형</th><th>상세</th></tr></thead><tbody>';
        html += moves.slice(0,30).map(function(r){
          return '<tr><td>'+escapeHtml(r.timestamp||r.created_at||'-')+'</td><td><span class="tag">'+escapeHtml(r.event_type||'-')+'</span></td><td style="max-width:300px;overflow:hidden;text-overflow:ellipsis">'+escapeHtml(r.event_data||r.detail||'-')+'</td></tr>';
        }).join('');
        html += '</tbody></table>';
      }
      document.getElementById('sqm-modal-content').innerHTML = '<h2 style="margin-bottom:16px">✅ 대량 이동 승인</h2>' + html;
    }).catch(function(e){
      document.getElementById('sqm-modal-content').innerHTML = '<h2>대량 이동 승인</h2><div class="empty">조회 실패</div>';
    });
  }
  window.showMoveApprovalQueueModal = showMoveApprovalQueueModal;

  /* ===================================================
     8s. 문서 변환 (OCR/PDF → Excel/Word)
     =================================================== */
  function showDocConvertModal() {
    var html = [
      '<div style="max-width:520px">',
      '  <h2 style="margin:0 0 12px 0">📷 문서 변환 (OCR/PDF)</h2>',
      '  <p style="color:var(--text-muted);margin:0 0 16px 0;font-size:.9rem">PDF/이미지를 Excel 또는 Word로 변환합니다.</p>',
      '  <div style="display:grid;grid-template-columns:100px 1fr;gap:10px;align-items:center;margin-bottom:16px">',
      '    <label style="font-weight:600">변환 형식</label>',
      '    <select id="dc-format" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '      <option value="excel">→ Excel (.xlsx)</option>',
      '      <option value="word">→ Word (.docx)</option>',
      '    </select>',
      '  </div>',
      '  <div id="dc-drop" style="border:2px dashed var(--border);border-radius:8px;padding:32px 16px;text-align:center;background:var(--bg-hover);cursor:pointer;margin-bottom:16px">',
      '    <div style="font-size:2.5rem;margin-bottom:8px">📄</div>',
      '    <div id="dc-name" style="color:var(--text-muted)">클릭 또는 PDF/이미지를 드롭하세요</div>',
      '  </div>',
      '  <input type="file" id="dc-file" accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp" style="display:none">',
      '  <div style="padding:12px;background:var(--bg-hover);border-radius:6px;margin-bottom:16px;font-size:.85rem;color:var(--warning)">',
      '    💡 이 기능은 서버에 OCR 엔진(Tesseract)이 필요합니다. 미설치 시 텍스트 PDF만 변환 가능합니다.',
      '  </div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'" class="btn btn-ghost">닫기</button>',
      '    <button id="dc-submit" class="btn btn-primary" disabled>변환</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);
    var drop = document.getElementById('dc-drop');
    var fi = document.getElementById('dc-file');
    var nm = document.getElementById('dc-name');
    var sub = document.getElementById('dc-submit');
    var selFile = null;
    function setF(f){
      if (!f) return; selFile = f;
      nm.innerHTML = '✅ <strong>'+escapeHtml(f.name)+'</strong> ('+Math.round(f.size/1024)+' KB)';
      sub.disabled = false;
    }
    drop.addEventListener('click', function(){ fi.click(); });
    fi.addEventListener('change', function(e){ if(e.target.files&&e.target.files[0]) setF(e.target.files[0]); });
    drop.addEventListener('dragover', function(e){ e.preventDefault(); });
    drop.addEventListener('drop', function(e){ e.preventDefault(); if(e.dataTransfer.files&&e.dataTransfer.files[0]) setF(e.dataTransfer.files[0]); });
    sub.addEventListener('click', function(){
      showToast('info', '문서 변환은 Phase 6에서 OCR 엔진 연동 후 지원됩니다');
    });
  }
  window.showDocConvertModal = showDocConvertModal;

  /* ===================================================
     8t. 품목별 재고 요약 — 제품 기준 집계
     =================================================== */
  function showProductSummaryModal() {
    showDataModal('📋 품목별 재고 요약','<div style="padding:20px;text-align:center">⏳ Loading...</div>');
    apiGet('/api/q/product-inventory').then(function(res){
      var rows = extractRows(res);
      // Group by product
      var byProd = {};
      rows.forEach(function(r){
        var p = r.product || '(미지정)';
        if (!byProd[p]) byProd[p] = { lots:0, weight:0, tonbags:0 };
        byProd[p].lots++;
        byProd[p].weight += Number(r.net_weight||0);
        byProd[p].tonbags += Number(r.tonbag_count||r.total_tonbags||0);
      });
      var prods = Object.keys(byProd).sort();
      if (!prods.length) {
        document.getElementById('sqm-modal-content').innerHTML = '<h2>📋 품목별 재고 요약</h2><div class="empty">데이터가 없습니다</div>';
        return;
      }
      var tbl = '<table class="data-table"><thead><tr><th>제품</th><th>LOT 수</th><th>톤백 수</th><th>총 중량(MT)</th></tr></thead><tbody>';
      prods.forEach(function(p){
        var d = byProd[p];
        tbl += '<tr><td style="font-weight:600">'+escapeHtml(p)+'</td><td>'+d.lots+'</td><td>'+d.tonbags+'</td><td class="mono-cell">'+d.weight.toFixed(3)+'</td></tr>';
      });
      tbl += '</tbody></table>';
      document.getElementById('sqm-modal-content').innerHTML = '<h2 style="margin-bottom:16px">📋 품목별 재고 요약</h2><p style="color:var(--text-muted);font-size:.85rem;margin-bottom:12px">' + prods.length + '개 제품, ' + rows.length + '개 LOT</p>' + tbl;
    }).catch(function(e){
      document.getElementById('sqm-modal-content').innerHTML = '<h2>품목별 재고 요약</h2><div class="empty">조회 실패</div>';
    });
  }
  window.showProductSummaryModal = showProductSummaryModal;

  /* ===================================================
     8u. 품목별 LOT 조회 — 제품 선택 → LOT 목록
     =================================================== */
  function showProductLotLookupModal() {
    var html = [
      '<div style="max-width:700px">',
      '  <h2 style="margin:0 0 12px 0">🔍 품목별 LOT 조회</h2>',
      '  <div style="display:flex;gap:8px;margin-bottom:16px;align-items:center">',
      '    <input type="text" id="pll-product" placeholder="제품명 (비우면 전체)" style="flex:1;padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '    <button id="pll-search" class="btn btn-primary">조회</button>',
      '  </div>',
      '  <div id="pll-result" style="min-height:60px"><div class="empty">제품명을 입력하고 조회를 클릭하세요</div></div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">',
      '    <button onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'" class="btn btn-ghost">닫기</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);
    document.getElementById('pll-search').addEventListener('click', function(){
      var prod = document.getElementById('pll-product').value.trim();
      var result = document.getElementById('pll-result');
      result.innerHTML = '<div style="padding:20px;text-align:center">⏳ 조회 중...</div>';
      apiGet('/api/q/product-inventory').then(function(res){
        var rows = extractRows(res);
        if (prod) rows = rows.filter(function(r){ return (r.product||'').toLowerCase().indexOf(prod.toLowerCase()) >= 0; });
        if (!rows.length) { result.innerHTML = '<div class="empty">해당 제품의 LOT가 없습니다</div>'; return; }
        var tbl = '<table class="data-table"><thead><tr><th>LOT</th><th>제품</th><th>상태</th><th>중량(MT)</th><th>톤백수</th><th>입고일</th></tr></thead><tbody>';
        tbl += rows.slice(0,100).map(function(r){
          return '<tr><td class="mono-cell" style="color:var(--accent);cursor:pointer" onclick="showLotDetail(\''+escapeHtml(r.lot_no||'')+'\')">'+escapeHtml(r.lot_no||'-')+'</td><td>'+escapeHtml(r.product||'-')+'</td><td><span class="tag">'+escapeHtml(r.status||'-')+'</span></td><td class="mono-cell">'+(r.net_weight!=null?Number(r.net_weight).toFixed(3):'-')+'</td><td>'+(r.tonbag_count||r.total_tonbags||'-')+'</td><td>'+escapeHtml(r.stock_date||r.inbound_date||'-')+'</td></tr>';
        }).join('');
        tbl += '</tbody></table>';
        result.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:8px">' + rows.length + '건</p>' + tbl;
      }).catch(function(e){
        result.innerHTML = '<div class="empty">조회 실패</div>';
      });
    });
  }
  window.showProductLotLookupModal = showProductLotLookupModal;

  /* ===================================================
     8v. 품목별 입출고 현황
     =================================================== */
  function showProductMovementModal() {
    showDataModal('📊 품목별 입출고 현황','<div style="padding:20px;text-align:center">⏳ Loading...</div>');
    apiGet('/api/q/movement-history').then(function(res){
      var rows = extractRows(res);
      // Group by product
      var byProd = {};
      rows.forEach(function(r){
        var p = r.product || '(미지정)';
        if (!byProd[p]) byProd[p] = { inbound:0, outbound:0, return_count:0, move:0 };
        var t = (r.movement_type||'').toUpperCase();
        if (t === 'INBOUND') byProd[p].inbound += Number(r.quantity||r.weight||1);
        else if (t === 'OUTBOUND') byProd[p].outbound += Number(r.quantity||r.weight||1);
        else if (t === 'RETURN') byProd[p].return_count += Number(r.quantity||r.weight||1);
        else byProd[p].move += Number(r.quantity||r.weight||1);
      });
      var prods = Object.keys(byProd).sort();
      if (!prods.length) {
        document.getElementById('sqm-modal-content').innerHTML = '<h2>품목별 입출고</h2><div class="empty">데이터가 없습니다</div>';
        return;
      }
      var tbl = '<table class="data-table"><thead><tr><th>제품</th><th>입고</th><th>출고</th><th>반품</th><th>기타</th></tr></thead><tbody>';
      prods.forEach(function(p){
        var d = byProd[p];
        tbl += '<tr><td style="font-weight:600">'+escapeHtml(p)+'</td><td style="color:var(--success)">'+d.inbound+'</td><td style="color:var(--warning)">'+d.outbound+'</td><td>'+d.return_count+'</td><td>'+d.move+'</td></tr>';
      });
      tbl += '</tbody></table>';
      document.getElementById('sqm-modal-content').innerHTML = '<h2 style="margin-bottom:16px">📊 품목별 입출고 현황</h2>' + tbl;
    }).catch(function(e){
      document.getElementById('sqm-modal-content').innerHTML = '<h2>품목별 입출고</h2><div class="empty">조회 실패</div>';
    });
  }
  window.showProductMovementModal = showProductMovementModal;

  function renderInfoModal(title, endpoint) {
    showDataModal(title,'<div style="padding:20px;text-align:center">Loading...</div>');
    apiGet(endpoint).then(function(res){
      var d=res.data||res||{};
      var html;
      if (endpoint === '/api/info/version') {
        var note = d.build_note ? String(d.build_note).split('\n').slice(0, 18).join('\n') : '';
        html = ''
          + '<div class="metrics-grid" style="grid-template-columns:repeat(2,minmax(180px,1fr));margin-bottom:14px">'
          + '<div class="metric-card"><div class="metric-label">프로그램</div><div class="metric-value" style="font-size:1.15rem">' + escapeHtml(d.app_name || 'SQM 재고관리 시스템') + '</div></div>'
          + '<div class="metric-card"><div class="metric-label">버전</div><div class="metric-value" style="font-size:1.4rem">v' + escapeHtml(d.version || '-') + '</div></div>'
          + '<div class="metric-card"><div class="metric-label">릴리즈 날짜</div><div class="metric-value" style="font-size:1rem">' + escapeHtml(d.release_date || '-') + '</div></div>'
          + '<div class="metric-card"><div class="metric-label">빌드 날짜</div><div class="metric-value" style="font-size:1rem">' + escapeHtml(d.build_date || '-') + '</div></div>'
          + '</div>';
        if (note) {
          html += '<h3 style="margin:10px 0 8px">변경 요약</h3><pre style="white-space:pre-wrap;max-height:260px;overflow:auto;background:var(--bg-muted,#f6f8fa);border:1px solid var(--panel-border);border-radius:8px;padding:12px;font-size:.86rem;line-height:1.5">' + escapeHtml(note) + '</pre>';
        }
      } else if (typeof d==='string') {
        html='<pre style="white-space:pre-wrap;font-size:.9rem">'+escapeHtml(d)+'</pre>';
      } else if (Array.isArray(d)) {
        html='<table class="data-table"><tbody>'+d.map(function(row){
          if (typeof row==='object'&&row!==null)
            return '<tr>'+Object.values(row).map(function(v){ return '<td>'+escapeHtml(String(v))+'</td>'; }).join('')+'</tr>';
          return '<tr><td>'+escapeHtml(String(row))+'</td></tr>';
        }).join('')+'</tbody></table>';
      } else {
        html='<table class="data-table"><tbody>'+Object.entries(d).map(function(kv){
          return '<tr><td style="font-weight:600;width:40%">'+escapeHtml(kv[0])+'</td><td>'+escapeHtml(String(kv[1]))+'</td></tr>';
        }).join('')+'</tbody></table>';
      }
      document.getElementById('sqm-modal-content').innerHTML='<h2 style="margin-bottom:16px">'+escapeHtml(title)+'</h2>'+html;
    }).catch(function(e){
      document.getElementById('sqm-modal-content').innerHTML='<h2>'+escapeHtml(title)+'</h2><div class="empty">Load failed: '+escapeHtml(e.message||String(e))+'</div>';
    });
  }

  window.showLotDetail = function(lotNo) {
    if (!lotNo) return;
    showDataModal('LOT Detail: '+lotNo,'<div style="padding:20px;text-align:center">Loading...</div>');
    apiGet('/api/action/lot-detail/'+encodeURIComponent(lotNo)).then(function(res){
      var d=res.data||res||{};
      var html='<table class="data-table"><tbody>'+Object.entries(d).map(function(kv){
        return '<tr><td style="font-weight:600;width:40%">'+escapeHtml(kv[0])+'</td><td>'+escapeHtml(String(kv[1]))+'</td></tr>';
      }).join('')+'</tbody></table>';
      document.getElementById('sqm-modal-content').innerHTML='<h2 style="margin-bottom:16px">LOT Detail: '+escapeHtml(lotNo)+'</h2>'+html;
    }).catch(function(e){
      document.getElementById('sqm-modal-content').innerHTML='<h2>LOT Detail: '+escapeHtml(lotNo)+'</h2><div class="empty">Load failed: '+escapeHtml(e.message||String(e))+'</div>';
    });
  };

  /* ===================================================
     9. ALERTS + STATUSBAR
     =================================================== */
  var FALLBACK_ALERTS = [
    {severity:'warning',icon:'&#x1F3F7;&#xFE0F;',text:'Tonbag integrity issues 40 — run integrity check',link:'#integrity'},
    {severity:'error',  icon:'&#x1F4CD;',         text:'400 unallocated tonbags (5 LOTs) — location assignment needed',link:'#allocation'}
  ];

  function loadAlerts() {
    var c=document.getElementById('alerts-container');
    if (!c) return;
    apiGet('/api/dashboard/alerts')
      .then(function(res){ renderAlerts(c, res.data||res.alerts||FALLBACK_ALERTS); })
      .catch(function(){ renderAlerts(c, FALLBACK_ALERTS); });
  }

  function renderAlerts(c, alerts) {
    c.innerHTML='<div class="alerts-header"><span class="alerts-title">&#x26A0;&#xFE0F; ALERTS</span><span class="alerts-counter">'+(alerts.length?'&#x1F534; '+alerts.length:'')+'</span></div>' +
      '<ul class="alerts-list">'+alerts.map(function(a){
        return '<li class="alert alert-'+escapeHtml(a.severity)+'"><span class="alert-icon">'+(a.icon||'')+'</span><span class="alert-text">'+escapeHtml(a.text)+'</span>'+(a.link?'<a class="alert-link" href="'+escapeHtml(a.link)+'">Go</a>':'')+'</li>';
      }).join('')+'</ul>';
  }

  function loadStatusbar() {
    var c=document.getElementById('statusbar-container');
    if (!c) return;
    if (!c.querySelector('.statusbar')) {
      c.innerHTML='<div class="statusbar"><span id="sb-modules">Modules: -/-</span><span class="sb-sep">|</span><span id="sb-unallocated">Unallocated -</span><span class="sb-sep">|</span><span id="sb-scan-fail">Scan fail -</span><span class="sb-sep">|</span><span id="sb-lot-age">LOT avg age -</span><span style="flex:1"></span><span id="sb-last-refresh">Last refresh: -</span><label style="margin-left:12px"><input type="checkbox" id="sb-auto-refresh" checked> Auto-refresh</label></div>';
    }
    refreshStatusbar();
  }

  function refreshStatusbar() {
    function st(id,txt){ var el=document.getElementById(id); if(el) el.textContent=txt; }
    apiGet('/api/dashboard/stats').then(function(res){
      var d=res.data||res||{};
      st('sb-unallocated','LOT '+( d.total_lots||0)+' / Tonbag '+(d.total_tbags||0));
      st('sb-scan-fail','Stock '+(d.total_weight_mt!=null?fmtN(d.total_weight_mt):'0')+' MT');
      st('sb-lot-age','Available '+(d.available_mt!=null?fmtN(d.available_mt):'0')+' MT');
    }).catch(function(){});
    apiGet('/api/health').then(function(res){
      var h=res.data||res||{};
      var ok = h.status==='ok';
      st('sb-modules','Engine: '+(ok?'OK':'ERR')+' ('+( h.lots||0)+' LOTs)');
    }).catch(function(){ st('sb-modules','Engine: offline'); });
    st('sb-last-refresh','Last refresh: '+new Date().toLocaleTimeString());
  }

  /* =====================================================
     10. ENDPOINTS  (key = HTML data-action name exactly)
     ===================================================== */
  var ENDPOINTS = {
    /* ── 파일 메뉴 ── */
    'onOpen':            {m:'GET',  u:'/api/q2/recent-files',                   lbl:'최근 파일'},
    'onSave':            {m:'GET',  u:'/api/action/export-lot-excel',            lbl:'내보내기'},
    'onExport':          {m:'GET',  u:'/api/action/export-lot-excel',            lbl:'Excel 내보내기'},
    /* v864.3 Phase 4-B: D/O 후속 연결 네이티브 폼 */
    'onDoUpdate':        {m:'JS', u:'do-update', lbl:'D/O 후속 연결'},
    'onReturnDialog':    {m:'JS',   u:'return-dialog',                             lbl:'반품 (재입고)'},
    /* v864.3 Phase 4-B: 반품 입고 — 네이티브 Excel 업로드 모달 */
    'onReturnInboundUpload': {m:'JS', u:'return-upload', lbl:'반품 입고 Excel'},
    'onReturnStatistics': {m:'GET', u:'/api/q2/return-stats',                   lbl:'반품 사유 통계'},
    'onRecentFiles':     {m:'GET',  u:'/api/q2/recent-files',                   lbl:'최근 파일'},
    'onExit':            {m:'JS',   u:'exit',                                    lbl:'종료'},

    /* ── 입고 메뉴 ── */
    /* v864.3 Phase 4-B: PDF 스캔 입고 네이티브 모달 (기존 scan 탭 대신) */
    'onOnPdfInbound':    {m:'JS', u:'pdf-inbound-upload', lbl:'PDF 스캔 입고'},
    /* v864.3 Phase 4-B: 수동 입고는 네이티브 모달로 처리 (tkinter filedialog 대체) */
    'onInboundManual':   {m:'JS', u:'inbound-upload', lbl:'수동 입고'},
    'onInboundList':     {m:'JS',   u:'inbound',                                  lbl:'입고 목록'},
    'onInboundCancel':   {m:'JS',   u:'inbound-cancel',                            lbl:'입고 취소'},
    'onCarrierProfile':  {m:'JS',   u:'carrier-profile',                          lbl:'선사 프로파일 관리'},

    /* ── 출고 메뉴 ── */
    /* v864.3 Phase 4-B: 즉시 출고 네이티브 폼 */
    'onOnQuickOutbound': {m:'JS', u:'quick-outbound', lbl:'즉시 출고'},
    /* v864.3 Phase 4-B: 빠른 출고 (붙여넣기) — 여러 LOT 일괄 */
    'onQuickOutboundPaste': {m:'JS', u:'quick-outbound-paste', lbl:'빠른 출고 (붙여넣기)'},
    /* v864.3 Phase 4-B: Picking List PDF 업로드 */
    'onPickingListUpload':  {m:'JS', u:'picking-list-pdf', lbl:'Picking List 업로드 (PDF)'},
    'onOutboundScheduled': {m:'JS', u:'outbound',                                 lbl:'출고 예정'},
    /* v864.3 Phase 4-B: 출고 확정 네이티브 폼 */
    'onOutboundConfirm': {m:'JS', u:'outbound-confirm', lbl:'출고 확정'},
    'onOutboundHistory': {m:'GET',  u:'/api/q/outbound-status',                  lbl:'출고 이력'},
    'onOutboundStatus':  {m:'JS',   u:'outbound',                                 lbl:'출고 현황'},
    'onApprovalHistory': {m:'GET',  u:'/api/q/approval-history',                 lbl:'승인 이력 조회'},

    /* ── 재고 메뉴 ── */
    'onInventoryList':   {m:'JS',   u:'inventory',                               lbl:'재고 조회'},
    /* v864.3 Phase 4-B: 톤백 위치 매핑 네이티브 Excel 업로드 */
    'onInventoryMove':   {m:'JS', u:'tonbag-location-upload', lbl:'위치 이동'},
    /* v864.3 Phase 4-B: Allocation 입력(출고 예약) 네이티브 Excel 업로드 */
    'onInventoryAllocation': {m:'JS', u:'allocation-upload', lbl:'Allocation 입력'},
    'onIntegrityCheck':  {m:'GET',  u:'/api/action/integrity-check',             lbl:'정합성 검사'},
    'onInventoryReport': {m:'GET',  u:'/api/q/inventory-report',                 lbl:'재고 현황 보고서'},
    'onInventoryTrend':  {m:'GET',  u:'/api/q/inventory-trend',                  lbl:'재고 추이 차트'},

    /* ── 보고서 메뉴 ── */
    'onReportDaily':     {m:'GET',  u:'/api/q2/report-daily',                    lbl:'일일 보고서'},
    'onReportMonthly':   {m:'GET',  u:'/api/q2/report-monthly',                  lbl:'월간 보고서'},
    'onReportCustom':    {m:'GET',  u:'/api/q/inventory-report',                   lbl:'맞춤 보고서'},
    'onInvoiceGenerate': {m:'GET',  u:'/api/action3/export-invoice-excel',         lbl:'거래명세서 생성'},
    'onDetailOfOutbound': {m:'GET', u:'/api/q2/detail-outbound',                 lbl:'Detail of Outbound'},
    'onSalesOrderDN':    {m:'GET',  u:'/api/q3/sales-order-dn',                  lbl:'Sales Order DN'},
    'onDnCrossCheck':    {m:'GET',  u:'/api/q3/dn-cross-check',                  lbl:'DN 교차검증'},
    'onLotDetailPdf':    {m:'GET',  u:'/api/action/lot-detail',                  lbl:'LOT 상세'},
    'onLotListExcel':    {m:'GET',  u:'/api/action/export-lot-excel',             lbl:'LOT 리스트 Excel'},
    'onTonbagListExcel': {m:'GET',  u:'/api/action2/export-tonbag-excel',          lbl:'톤백리스트 Excel'},
    'onReportExport':    {m:'GET',  u:'/api/action2/export-tonbag-excel',          lbl:'Excel 내보내기'},
    'onMovementHistory': {m:'GET',  u:'/api/q/movement-history',                  lbl:'입출고 내역'},
    'onAuditLog':        {m:'GET',  u:'/api/q/audit-log',                         lbl:'감사 로그'},

    /* ── 설정/도구 메뉴 ── */
    /* [Sprint 0] 'onSettings' removed — was wired to /api/menu/-on-settings (NotReadyError stub).
       Real settings dialog ships in Sprint 2 (SettingsDialogMixin port, ~5d). */
    'onProductMaster':   {m:'GET',  u:'/api/info/system-info',                    lbl:'제품 마스터'},
    'onProductInventoryReport': {m:'GET', u:'/api/q/product-inventory',           lbl:'제품별 재고 현황'},
    'onIntegrityRepair': {m:'GET',  u:'/api/action/integrity-check',                     lbl:'정합성 검사/복구'},
    'onOptimizeDb':      {m:'POST', u:'/api/action3/optimize-db',                 lbl:'DB 최적화'},
    'onCleanupLogs':     {m:'POST', u:'/api/action3/cleanup-logs',                lbl:'로그 정리'},
    'onDbInfo':          {m:'GET',  u:'/api/info/system-info',                    lbl:'DB 정보'},
    'onOnBackup':        {m:'POST', u:'/api/action/backup-create',                lbl:'백업 생성'},
    'onBackupList':      {m:'GET',  u:'/api/q/backup-list',                       lbl:'백업 목록'},
    'onRestore':         {m:'JS',   u:'restore',                                   lbl:'복원'},
    'onAiTools':         {m:'JS',   u:'wip',                                       lbl:'AI 도구'},
    'onSaveWindowSize':  {m:'JS',   u:'save-window-size',                          lbl:'창 크기 저장'},
    'onResetWindowSize': {m:'JS',   u:'reset-window-size',                         lbl:'창 크기 초기화'},

    /* ── 도움말 메뉴 ── */
    'onHelp':            {m:'GET',  u:'/api/info/usage',                          lbl:'사용자 매뉴얼'},
    'onShortcuts':       {m:'GET',  u:'/api/info/shortcuts',                      lbl:'단축키'},
    'onStatusGuide':     {m:'GET',  u:'/api/info/status-guide',                   lbl:'STATUS 안내'},
    'onBackupGuide':     {m:'GET',  u:'/api/info/backup-guide',                   lbl:'백업/복구 가이드'},
    'onAbout':           {m:'GET',  u:'/api/info/version',                        lbl:'버전 정보'},

    /* ── 탭 이동 ── */
    'onGoScanTab':       {m:'JS',   u:'scan',                                     lbl:'스캔 탭'},
    'onGoAllocationTab': {m:'JS',   u:'allocation',                               lbl:'배정 탭'},

    /* ── 툴바 ── */
    /* v864.3 Phase 4-B: 툴바 PDF 입고 — 네이티브 모달 */
    'tb-pdf-inbound':    {m:'JS', u:'pdf-inbound-upload', lbl:'PDF 입고'},
    /* 툴바 '즉시 출고' 도 네이티브 폼으로 */
    'tb-quick-outbound': {m:'JS', u:'quick-outbound', lbl:'즉시 출고'},
    'tb-return':         {m:'JS',   u:'return',                                   lbl:'반품'},
    'tb-inventory':      {m:'JS',   u:'inventory',                                lbl:'재고 조회'},
    'tb-integrity':      {m:'GET',  u:'/api/action/integrity-check',              lbl:'정합성'},
    'tb-backup':         {m:'POST', u:'/api/action/backup-create',                lbl:'백업'},
    'tb-settings':       {m:'JS',   u:'font-size-settings',                       lbl:'설정'},
    /* [Sprint 0] 'tb-settings' removed — same reason as onSettings (real dialog in Sprint 2). */

    /* ── v864.2 신규 액션 (메뉴 구조 동기화) ── */
    'onBarcodeScanUpload': {m:'JS', u:'barcode-scan-upload',                       lbl:'바코드 스캔 업로드'},
    'onApprovalQueue':   {m:'JS',   u:'approval-queue',                            lbl:'승인 대기'},
    'onApplyApproved':   {m:'POST', u:'/api/allocation/apply-approved',            lbl:'예약 반영 (승인분)'},
    'onPickingTemplateManage': {m:'JS', u:'picking-template',                      lbl:'피킹 템플릿 관리'},
    'onMoveApprovalQueue': {m:'JS', u:'move-approval-queue',                      lbl:'대량 이동 승인'},
    'onInboundTemplateManage': {m:'JS', u:'inbound-template',                     lbl:'입고 파싱 템플릿'},
    'onFontSizeSettings':    {m:'JS', u:'font-size-settings',                       lbl:'🔤 화면 폰트 크기'},
    'onEmailConfig':     {m:'JS',   u:'email-config',                              lbl:'이메일 설정'},
    'onIntegrityReport': {m:'GET',  u:'/api/action/integrity-check',              lbl:'정합성 검증 (시각화)'},
    'onFixLotIntegrity': {m:'GET',  u:'/api/action/integrity-check',              lbl:'LOT 상태 정합성 복구'},
    'onExportCustoms':   {m:'GET',  u:'/api/action/export-lot-excel',             lbl:'통관요청 양식'},
    'onExportRubyli':    {m:'GET',  u:'/api/action/export-lot-excel',             lbl:'루비리 양식'},
    'onExportTonbag':    {m:'GET',  u:'/api/action2/export-tonbag-excel',          lbl:'톤백 현황'},
    'onExportIntegrated': {m:'GET', u:'/api/action/export-lot-excel',             lbl:'통합 현황'},
    'onAutoBackupSettings': {m:'JS', u:'auto-backup-settings',                    lbl:'자동 백업 설정'},
    'onReportTemplates': {m:'GET',  u:'/api/q/audit-log',                          lbl:'보고서 양식 관리'},
    'onReportHistory':   {m:'GET',  u:'/api/q/audit-log',                          lbl:'보고서 이력 조회'},
    'onLotAllocationAudit': {m:'JS', u:'lot-allocation-audit',                    lbl:'LOT Allocation 톤백 현황'},
    'onDocConvert':      {m:'JS',   u:'doc-convert',                               lbl:'문서 변환 (OCR/PDF)'},
    'onTestDbReset':     {m:'JS',   u:'test-db-reset',                             lbl:'테스트 DB 초기화'},
    'onSystemInfo':      {m:'GET',  u:'/api/q3/settings-info',                    lbl:'시스템 정보'},
    'onProductSummary':  {m:'JS',   u:'product-summary',                           lbl:'품목별 재고 요약'},
    'onProductLotLookup': {m:'JS',  u:'product-lot-lookup',                        lbl:'품목별 LOT 조회'},
    'onProductMovement': {m:'JS',   u:'product-movement',                          lbl:'품목별 입출고 현황'},

    /* ── [Sprint 0-3b] v864-2 파일 메뉴 슬롯 복원 (placeholder — Sprint 2에서 실구현) ── */
    'onBlCarrierRegister': {m:'JS', u:'wip',                                       lbl:'🚢 선사 BL 등록 도구'},
    'onBlCarrierAnalyze':  {m:'JS', u:'wip',                                       lbl:'🔬 선사 패턴 분석'},
    'onGeminiToggle':      {m:'JS', u:'wip',                                       lbl:'🔀 Gemini AI 사용'},
    'onAiChat':            {m:'JS', u:'wip',                                       lbl:'💬 AI 채팅'},
    'onGeminiApiSettings': {m:'JS', u:'wip',                                       lbl:'🔐 Gemini API 설정'},
    'onGeminiApiTest':     {m:'JS', u:'wip',                                       lbl:'🧪 Gemini API 테스트'},

    /* ── [Sprint 0-3] v864-2 재고 메뉴 슬롯 (placeholder — Sprint 1/2에서 실구현) ── */
    'onExportLot':         {m:'JS', u:'wip',                                       lbl:'📊 LOT 리스트 Excel'},
    'onStockTrendChart':   {m:'JS', u:'wip',                                       lbl:'📊 재고 추이 차트'},

    /* ── [Sprint 0-3] 🔍 전역 검색 버튼 (placeholder — Sprint 2에서 실구현) ── */
    'onGlobalSearch':      {m:'JS', u:'wip',                                       lbl:'🔍 전역 검색'},

    /* View 메뉴 탭 이동 */
    'onGoInventoryTab':  {m:'JS',   u:'inventory',                                lbl:'Inventory 탭'},
    'onGoPickedTab':     {m:'JS',   u:'picked',                                   lbl:'Picked 탭'},
    'onGoOutboundTab':   {m:'JS',   u:'outbound',                                 lbl:'Outbound 탭'},
    'onGoReturnTab':     {m:'JS',   u:'return',                                   lbl:'Return 탭'},
    'onGoMoveTab':       {m:'JS',   u:'move',                                     lbl:'Move 탭'},
    'onGoDashboardTab':  {m:'JS',   u:'dashboard',                                lbl:'Dashboard 탭'},
    'onGoLogTab':        {m:'JS',   u:'log',                                      lbl:'Log 탭'},

    /* ── 업로드 / 보고서 ── */
    'onDoUpload':          {m:'JS',  u:'do-upload',                               lbl:'D/O PDF 업로드'},
    'onSalesOrderUpload':  {m:'JS',  u:'sales-order-upload',                      lbl:'Sales Order Excel 업로드'},
    'onSwapReport':        {m:'GET', u:'/api/action2/swap-report',                 lbl:'Swap 보고서'},
    'onStockAlerts':       {m:'GET', u:'/api/dashboard/alerts',                    lbl:'재고 알림'},

    /* ── 기타 ── */
    'refresh-all':       {m:'JS',   u:'refresh',                                  lbl:'새로고침'},
    'onToggleTheme':     {m:'JS',   u:'theme',                                    lbl:'테마 전환'},
  };

  function dispatchAction(action) {
    var conf = ENDPOINTS[action];
    if (!conf) {
      dbgLog('⚠️','[unregistered] '+action,'ENDPOINTS에 없는 액션','#ffa726');
      showToast('info', '[unregistered] action=' + action);
      return;
    }
    if (conf.m === 'JS') {
      if (conf.u === 'theme')   { toggleTheme(); return; }
      if (conf.u === 'refresh') { renderPage(_currentRoute || 'dashboard'); return; }
      if (conf.u === 'exit') {
        if (window.pywebview && window.pywebview.api) window.pywebview.api.exit_app();
        else window.close();
        return;
      }
      /* v864.3 Phase 4-B: 네이티브 모달 액션 */
      if (conf.u === 'inbound-upload') {
        showInboundManualUploadModal();
        return;
      }
      if (conf.u === 'return-upload') {
        showReturnInboundUploadModal();
        return;
      }
      if (conf.u === 'allocation-upload') {
        showAllocationUploadModal();
        return;
      }
      if (conf.u === 'quick-outbound') {
        /* [Sprint 1-3] OneStop 4탭 wizard 모달로 전환 */
        showOneStopOutboundModal();
        return;
      }
      if (conf.u === 'do-update') {
        showDoUpdateModal();
        return;
      }
      if (conf.u === 'tonbag-location-upload') {
        showTonbagLocationUploadModal();
        return;
      }
      if (conf.u === 'apply-approved-allocation') {
        showApplyApprovedAllocationModal();
        return;
      }
      if (conf.u === 'pdf-inbound-upload') {
        /* [Sprint 1-2] OneStop 4슬롯 wizard 모달 (v864-2 OneStopInboundDialog 매칭) */
        showOneStopInboundModal();
        return;
      }
      if (conf.u === 'picking-list-pdf') {
        showPickingListPdfModal();
        return;
      }
      if (conf.u === 'quick-outbound-paste') {
        showQuickOutboundPasteModal();
        return;
      }
      if (conf.u === 'outbound-confirm') {
        showOutboundConfirmModal();
        return;
      }
      if (conf.u === 'inbound-cancel') {
        showInboundCancelModal();
        return;
      }
      if (conf.u === 'approval-queue') {
        showApprovalQueueModal();
        return;
      }
      if (conf.u === 'restore') {
        showRestoreModal();
        return;
      }
      if (conf.u === 'save-window-size') {
        saveWindowSize();
        return;
      }
      if (conf.u === 'reset-window-size') {
        resetWindowSize();
        return;
      }
      if (conf.u === 'return-dialog') {
        showReturnDialog();
        return;
      }
      if (conf.u === 'lot-allocation-audit') {
        showLotAllocationAuditModal();
        return;
      }
      if (conf.u === 'test-db-reset') {
        showTestDbResetModal();
        return;
      }
      if (conf.u === 'barcode-scan-upload') {
        showBarcodeScanUploadModal();
        return;
      }
      if (conf.u === 'email-config') {
        showEmailConfigModal();
        return;
      }
      if (conf.u === 'auto-backup-settings') {
        showAutoBackupSettingsModal();
        return;
      }
      if (conf.u === 'inbound-template') {
        showInboundTemplateModal();
        return;
      }
      if (conf.u === 'font-size-settings') {
        showFontSizeModal();
        return;
      }
      if (conf.u === 'picking-template') {
        showPickingTemplateModal();
        return;
      }
      if (conf.u === 'move-approval-queue') {
        showMoveApprovalQueueModal();
        return;
      }
      if (conf.u === 'doc-convert') {
        showDocConvertModal();
        return;
      }
      if (conf.u === 'product-summary') {
        showProductSummaryModal();
        return;
      }
      if (conf.u === 'product-lot-lookup') {
        showProductLotLookupModal();
        return;
      }
      if (conf.u === 'product-movement') {
        showProductMovementModal();
        return;
      }
      if (conf.u === 'do-upload') {
        showDoUploadModal();
        return;
      }
      if (conf.u === 'sales-order-upload') {
        showSalesOrderUploadModal();
        return;
      }
      if (conf.u === 'carrier-profile') {
        showCarrierProfileModal();
        return;
      }
      if (conf.u === 'wip') {
        dbgLog('🟡','WIP: '+conf.lbl,'준비 중 (아직 미구현)','#ffa726');
        showToast('info', conf.lbl + ': 준비 중');
        return;
      }
      dbgLog('🔀','Route → '+conf.u, conf.lbl,'#ab47bc');
      renderPage(conf.u);
      return;
    }
    if (conf.m === 'GET') {
      renderInfoModal(conf.lbl, conf.u);
      return;
    }
    if (action === 'tb-backup' || action === 'onOnBackup') {
      var ok = window.confirm('💾 DB 백업을 생성합니다.\n\nOK를 누르면 백업 파일이 생성됩니다.');
      if (!ok) return;
    }
    apiCall(conf.m, conf.u, {})
      .then(function (res) {
        // v864.3 Debug: 응답 body 의 ok:false 체크 (가짜 성공 토스트 차단)
        if (res && res.ok === false) {
          var detailCode = res.detail && res.detail.code;
          if (detailCode === 'NOT_READY') {
            showToast('info', '⚠️ ' + conf.lbl + ' — 준비 중 (Phase 4-B)');
            dbgLog('🟡','NOT_READY', conf.lbl + ' (' + conf.u + ')','#ffa726');
          } else {
            showToast('warning', conf.lbl + ' — ' + (res.error || res.message || '실패'));
            dbgLog('🟡','ok:false', conf.lbl + ' — ' + (res.error || ''),'#ffa726');
          }
          return;
        }
        // 진짜 성공: data 가 의미있는지 간단 체크
        var d = res ? (res.data !== undefined ? res.data : res) : null;
        var hasData = d && (typeof d !== 'object' || Object.keys(d).length > 0 || (Array.isArray(d) && d.length > 0));
        if (!hasData && res && res.ok === true) {
          // 200 OK + ok:true 지만 data 없음 → 의심
          showToast('info', conf.lbl + ' 요청 전송됨 (UI 미구현)');
          dbgLog('🟠','EMPTY OK', conf.lbl + ' — 응답은 성공인데 data 없음','#ff9800');
          return;
        }
        showToast('success', conf.lbl + ' 완료');
      })
      .catch(function (e) {
        if (e.status === 501) showToast('info', conf.lbl + ' (coming soon)');
        else showToast('error', conf.lbl + ' 실패: ' + (e.message || String(e)));
      });
  }

  window.dispatchAction = dispatchAction;

  /* ===================================================
     11. BIND ALL + BOOT
     =================================================== */
  function bindAll() {
    // data-action elements
    document.querySelectorAll('[data-action]').forEach(function(el){
      if (el.dataset._sqmBound) return;
      el.dataset._sqmBound='1';
      el.addEventListener('click', function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        var action = el.dataset.action;
        if (action==='toggle-theme'||action==='theme-toggle') { toggleTheme(); return; }
        if (action==='refresh-all') { renderPage(_currentRoute||'dashboard'); return; }
        dispatchAction(action);
      });
    });

    // data-route elements
    document.querySelectorAll('[data-route]').forEach(function(el){
      if (el.dataset._sqmBound) return;
      el.dataset._sqmBound='1';
      el.addEventListener('click', function(ev){
        ev.preventDefault();
        renderPage(el.dataset.route);
      });
    });

    // top-level menu toggle
    document.querySelectorAll('.menu-btn[data-menu]').forEach(function(el){
      if (el.dataset._sqmBound) return;
      el.dataset._sqmBound='1';
      el.addEventListener('click', function(ev){
        var menuName = el.dataset.menu || '?';
        console.log('[SQM MENU CLICK]', menuName, '| target:', ev.target.tagName, '| hasAction:', !!ev.target.closest('[data-action]'));
        dbgLog('🖱️','MENU CLICK', menuName + ' | target=' + ev.target.tagName + ' | hasAction=' + (!!ev.target.closest('[data-action]')), '#00e5ff');
        if (ev.target.closest('