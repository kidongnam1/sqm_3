/* =======================================================================
   SQM Inventory v8.6.6 - sqm-inline.js
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

  /**
   * Excel/FileResponse 다운로드.
   * 1) PyWebView: Python 네이티브 저장 대화상자 (Blob 클릭은 WebView2에서 무동작인 경우 다수)
   * 2) 그 외: fetch → Blob → <a download>
   */
  /** 엑셀 네이티브 저장 후 기본 앱(Excel)으로 열기 — ⚙️ 설정에서 끌 수 있음 */
  function sqmShouldOpenXlsxAfterSave() {
    try {
      var v = getStore().getItem('sqm_open_xlsx_after_save');
      if (v === null || v === '') return true;
      return v === '1' || v === 'true';
    } catch (e) {
      return true;
    }
  }
  window.sqmSetOpenXlsxAfterSave = function (on) {
    try {
      getStore().setItem('sqm_open_xlsx_after_save', on ? '1' : '0');
    } catch (e) {}
  };

  function sqmSuggestedXlsxName(url) {
    try {
      if (url.indexOf('export-lot-excel') >= 0) return 'SQM-LOT-List.xlsx';
      if (url.indexOf('export-tonbag-excel') >= 0) return 'SQM-Tonbag-List.xlsx';
      if (url.indexOf('sales-order-dn-template') >= 0) return 'Sales_order_DN.xlsx';
      var mo = url.match(/[?&]option=(\d+)/);
      if (mo) {
        var opt = mo[1];
        var map = { '1': 'SQM-Customs.xlsx', '3': 'SQM-Inventory.xlsx', '4': 'SQM-SubLOT.xlsx', '6': 'SQM-FullInventory.xlsx' };
        if (map[opt]) return map[opt];
      }
    } catch (e) {}
    return 'SQM-export.xlsx';
  }

  function sqmDownloadFileUrl(url, successToastLabel) {
    if (typeof window.pywebview !== 'undefined' && window.pywebview && window.pywebview.api &&
        typeof window.pywebview.api.save_download_url === 'function') {
      var sug = sqmSuggestedXlsxName(url);
      var openAfter = sqmShouldOpenXlsxAfterSave();
      window.pywebview.api.save_download_url(url, sug, openAfter).then(function (res) {
        if (res && res.ok) {
          if (typeof showToast === 'function') {
            var msg = (successToastLabel || '내보내기') + ' 저장 완료 — ' + (res.path || '');
            if (res.opened) {
              msg += ' · 파일을 열었습니다.';
            } else if (openAfter && res.open_error) {
              msg += ' · (파일 자동 열기 실패: ' + String(res.open_error).slice(0, 80) + ')';
            }
            showToast('success', msg);
          }
        } else if (res && res.cancelled) {
          if (typeof showToast === 'function') showToast('info', '저장을 취소했습니다.');
        } else {
          if (typeof showToast === 'function') {
            showToast('error', '저장 실패: ' + ((res && res.error) ? res.error : 'unknown'));
          }
        }
      }).catch(function (e) {
        if (typeof showToast === 'function') {
          showToast('error', '저장 실패: ' + (e && e.message ? e.message : String(e)));
        }
      });
      return;
    }

    fetch(url, { method: 'GET' })
      .then(function (resp) {
        if (!resp.ok) {
          return resp.text().then(function (t) {
            throw new Error('HTTP ' + resp.status + (t ? ': ' + String(t).slice(0, 120) : ''));
          });
        }
        var cd = resp.headers.get('Content-Disposition') || '';
        var fname = 'SQM-export.xlsx';
        var mStar = cd.match(/filename\*=UTF-8''([^;\s]+)/i);
        if (mStar && mStar[1]) {
          try {
            fname = decodeURIComponent(mStar[1].replace(/["']/g, '').trim());
          } catch (e) {
            fname = mStar[1];
          }
        } else {
          var m = cd.match(/filename="([^"]+)"/i);
          if (m && m[1]) {
            fname = m[1];
          } else {
            m = cd.match(/filename=([^;\s]+)/i);
            if (m && m[1]) fname = m[1].replace(/["']/g, '').trim();
          }
        }
        return resp.blob().then(function (blob) {
          return { blob: blob, fname: fname };
        });
      })
      .then(function (o) {
        var a = document.createElement('a');
        a.href = URL.createObjectURL(o.blob);
        a.download = o.fname;
        a.rel = 'noopener';
        document.body.appendChild(a);
        a.click();
        setTimeout(function () {
          try {
            URL.revokeObjectURL(a.href);
          } catch (e) {}
          if (a.parentNode) a.parentNode.removeChild(a);
        }, 2500);
        if (successToastLabel && typeof showToast === 'function') {
          showToast('success', successToastLabel + ' — 저장 위치를 선택하세요.');
        }
      })
      .catch(function (e) {
        if (typeof showToast === 'function') {
          showToast('error', '다운로드 실패: ' + (e && e.message ? e.message : String(e)));
        }
      });
  }

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
    if (e.ctrlKey && !e.altKey && window._sqmOS && window._sqmOS.parsed) {
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
    if (document.body) document.body.setAttribute('data-theme', theme);
    var vm = store.getItem('sqm_view_mode') || 'mt';
    document.documentElement.setAttribute('data-view-mode', vm);
  }

  function toggleTheme() {
    var cur = document.documentElement.getAttribute('data-theme') || 'dark';
    var next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    if (document.body) document.body.setAttribute('data-theme', next);
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
    document.querySelectorAll('.submenu-parent.open,.submenu-parent.hover-active').forEach(function(el){
      el.classList.remove('open');
      el.classList.remove('hover-active');
    });
    document.querySelectorAll('.submenu-dropdown').forEach(function(el){
      el.style.display = '';
    });
    document.querySelectorAll('.menu-dropdown.open,.menu-dropdown.active').forEach(function(el){
      el.classList.remove('open'); el.classList.remove('active');
    });
    document.querySelectorAll('.menu-item.active,.nav-item.open').forEach(function(el){
      el.classList.remove('active'); el.classList.remove('open');
    });
  }

  function closeSiblingSubmenus(parent) {
    var menu = parent && parent.closest ? parent.closest('.menu-dropdown') : null;
    if (!menu) return;
    menu.querySelectorAll('.submenu-parent.open,.submenu-parent.hover-active').forEach(function(el){
      if (el !== parent) {
        el.classList.remove('open');
        el.classList.remove('hover-active');
      }
    });
    menu.querySelectorAll('.submenu-dropdown').forEach(function(el){
      if (!parent.contains(el)) el.style.display = '';
    });
  }

  function activateSubmenuParent(parent, lockOpen) {
    if (!parent) return;
    var menu = parent.closest ? parent.closest('.menu-dropdown') : null;
    var active = document.activeElement;
    if (menu && active && menu.contains(active) && !parent.contains(active) && active.blur) {
      active.blur();
    }
    closeSiblingSubmenus(parent);
    parent.classList.add('hover-active');
    if (lockOpen) parent.classList.add('open');
    var dropdown = parent.querySelector('.submenu-dropdown');
    if (dropdown) dropdown.style.display = 'block';
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


  /* ── view-unit 라디오 버튼: 톤백/LOT/MT 표시 단위 전환 ──────────────────
     - 돈백(tonbag): 각 상태 카드의 주숫자를 "톤백 수"로 표시
     - LOT:         주숫자를 "LOT 수"로 표시
     - MT:          주숫자를 "중량(MT)"으로 표시 (기본값)
     위 세 모드는 대시보드 status 카드에만 적용됨.
  ─────────────────────────────────────────────────────────────── */
  var _viewUnit = 'mt';  // 기본값: MT

  (function _initViewUnit(){
    var radios = document.querySelectorAll('input[name="view-unit"]');
    if (!radios.length) return;
    radios.forEach(function(r){
      r.addEventListener('change', function(){
        _viewUnit = r.value;
        _applyViewUnit();
      });
    });
  })();

  function _applyViewUnit() {
    var el = document.getElementById('dashboard-detail');
    if (!el) return;
    // 현재 렌더링된 카드들을 다시 렌더하기 위해 stats 재요청
    apiGet('/api/dashboard/stats').then(function(res){
      var d = res.data || res || {};
      var summary = d.status_summary || {};
      var html = '<div style="margin-bottom:16px"><h3 style="margin:0 0 8px 0;font-size:15px;color:var(--text-primary,#e0e0e0)">재고 현황</h3>';
      html += '<div style="display:flex;gap:10px;flex-wrap:wrap">';
      STATUS_CARD_META.forEach(function(m){
        var s = summary[m.key] || {lots:0,tonbags:0,weight_kg:0,normal_bags:0,sample_bags:0,normal_kg:0,sample_kg:0};
        var normalBags = (s.normal_bags != null ? s.normal_bags : s.tonbags);
        var sampleBags = (s.sample_bags || 0);
        var normalKg   = (s.normal_kg   != null ? s.normal_kg   : s.weight_kg);
        var sampleKg   = (s.sample_kg   || 0);

        var bigNum, bigLabel;
        if (_viewUnit === 'tonbag') {
          bigNum = normalBags; bigLabel = '톤백';
        } else if (_viewUnit === 'lot') {
          bigNum = s.lots; bigLabel = 'LOT';
        } else {
          bigNum = fmtW(s.weight_kg); bigLabel = '';
        }

        html += '<div style="flex:1;min-width:160px;background:var(--bg-card,#1e1e2e);border-left:4px solid '+m.color+';border-radius:8px;padding:12px 14px">';
        html += '<div style="font-size:13px;color:'+m.color+';font-weight:700;margin-bottom:6px">'+m.icon+' '+m.label+'</div>';
        if (_viewUnit === 'mt') {
          html += '<div style="font-size:22px;font-weight:700;color:var(--text-primary,#e0e0e0)">'+bigNum+'</div>';
        } else {
          html += '<div style="font-size:22px;font-weight:700;color:var(--text-primary,#e0e0e0)">'+bigNum+'<span style="font-size:12px;font-weight:400;color:var(--text-muted,#888)"> '+bigLabel+'</span></div>';
        }
        if (sampleBags > 0) {
          html += '<div style="font-size:13px;font-weight:600;color:#f59e0b;margin-top:1px">'+sampleBags+'<span style="font-size:11px;font-weight:400;color:var(--text-muted,#888)"> 샘플</span></div>';
        }
        html += '<div style="font-size:12px;color:var(--text-muted,#888);margin-top:2px">'+s.lots+' LOT · '+fmtW(normalKg)+'</div>';
        if (sampleBags > 0) {
          html += '<div style="font-size:11px;color:#f59e0b;margin-top:1px">샘플: '+fmtW(sampleKg)+'</div>';
        }
        html += '</div>';
      });
      html += '</div></div>';
      html += '<div id="dash-matrix-area"></div>';
      html += '<div id="dash-integrity-area"></div>';
      el.innerHTML = html;
      renderProductMatrix(d.product_matrix || []);
      renderIntegrity(d.integrity || {}, d.lot_weight_summary || {});
    }).catch(function(){});
  }

  function loadDashboardTables() {
    apiGet('/api/dashboard/stats').then(function(res){
      var d = res.data || res || {};
      renderStatusCards(d.status_summary || {});
      renderProductMatrix(d.product_matrix || []);
      renderIntegrity(d.integrity || {}, d.lot_weight_summary || {});
    }).catch(function(){
      renderStatusCards({});
      renderProductMatrix([]);
      renderIntegrity({}, {});
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
    html += '\uC7AC\uACE0 \uD604\uD669</h3>';
    html += '<div style="display:flex;gap:10px;flex-wrap:wrap">';
    STATUS_CARD_META.forEach(function(m){
      var s = summary[m.key] || {lots:0, tonbags:0, weight_kg:0};
      html += '<div style="flex:1;min-width:160px;background:var(--bg-card,#1e1e2e);border-left:4px solid '+m.color+';border-radius:8px;padding:12px 14px">';
      html += '<div style="font-size:13px;color:'+m.color+';font-weight:700;margin-bottom:6px">'+m.icon+' '+m.label+'</div>';
      var normalBags  = (s.normal_bags  != null ? s.normal_bags  : s.tonbags);
      var sampleBags  = (s.sample_bags  != null ? s.sample_bags  : 0);
      var normalKg    = (s.normal_kg    != null ? s.normal_kg    : s.weight_kg);
      var sampleKg    = (s.sample_kg    != null ? s.sample_kg    : 0);
      html += '<div style="font-size:22px;font-weight:700;color:var(--text-primary,#e0e0e0)">'+normalBags+'<span style="font-size:12px;font-weight:400;color:var(--text-muted,#888)"> \uD1A4\uBC31</span></div>';
      if (sampleBags > 0) {
        html += '<div style="font-size:13px;font-weight:600;color:#f59e0b;margin-top:1px">'+sampleBags+'<span style="font-size:11px;font-weight:400;color:var(--text-muted,#888)"> \uC0D8\uD50C</span></div>';
      }
      html += '<div style="font-size:12px;color:var(--text-muted,#888);margin-top:2px">'+s.lots+' LOT \u00B7 '+fmtW(normalKg)+'</div>';
      if (sampleBags > 0) {
        html += '<div style="font-size:11px;color:#f59e0b;margin-top:1px">\uC0D8\uD50C: '+fmtW(sampleKg)+'</div>';
      }
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
  function renderIntegrity(data, lotW) {
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
    html += '<div>\uCD1D\uC785\uACE0(initial): <b>'+fmtW(data.total_inbound_kg)+'</b></div>';
    html += '<div>\uD604\uC7AC\uC7AC\uACE0(\uD1A4\uBC31\uD569): <b>'+fmtW(data.current_stock_kg)+'</b></div>';
    html += '<div>\uCD9C\uACE0\uB204\uACC4(\uD1A4\uBC31\uD569): <b>'+fmtW(data.outbound_total_kg)+'</b></div>';
    html += '<div>\uCC28\uC774: <b style="color:'+color+'">'+fmtN(data.diff_kg)+' kg</b></div>';
    html += '</div>';
    if (lotW && lotW.sum_net_weight_kg !== undefined) {
      html += '<div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--border-color,#333);font-size:12px;color:var(--text-muted,#888);line-height:1.5">';
      html += '<b style="color:var(--text-primary,#e0e0e0)">LOT \uC900\uC911\uB7C9 \uD569 vs \uD604\uC7AC\uC911\uB7C9 \uD569</b> (Excel LOT \uBAA9\uB85D\uACFC \uB3D9\uC77C \uAE30\uC900)<br>';
      html += '\uC21C\uC911\uB7C9 \uD569: <b style="color:#e0e0e0">'+fmtW(lotW.sum_net_weight_kg)+'</b>';
      html += ' \u00B7 \uD604\uC7AC\uC911\uB7C9 \uD569: <b style="color:#e0e0e0">'+fmtW(lotW.sum_current_weight_kg)+'</b>';
      html += ' \u00B7 \uCC28\uC774(\uC0D8\uD50C\uB4F1 \uCD94\uC815): <b style="color:#f59e0b">'+fmtN(lotW.gap_net_minus_current_kg)+' kg</b>';
      if (lotW.sample_tonbags_in_stock_kg != null && lotW.sample_tonbags_in_stock_kg > 0) {
        html += ' \u00B7 \uC0D8\uD50C \uD1A4\uBC31(\uC7AC\uACE0 \uB0B4): <b>'+fmtN(lotW.sample_tonbags_in_stock_kg)+' kg</b>';
      }
      html += '</div>';
    }
    html += '</div>';
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
      _invAllRows = rows;
      if (!rows.length) {
        c.innerHTML = '<div class="empty" style="padding:60px;text-align:center">No inventory data</div>';
        return;
      }
      var sumBal = 0;
      var sumNet = 0;
      var sumIni = 0;
      var sumOb = 0;
      rows.forEach(function(r){
        if (r.balance != null && !isNaN(Number(r.balance))) sumBal += Number(r.balance);
        if (r.net != null && !isNaN(Number(r.net))) sumNet += Number(r.net);
        if (r.initial_weight != null && !isNaN(Number(r.initial_weight))) sumIni += Number(r.initial_weight);
        if (r.outbound_weight != null && !isNaN(Number(r.outbound_weight))) sumOb += Number(r.outbound_weight);
      });
      var html = '<section class="page" data-page="inventory">' +
        '<div style="display:flex;align-items:center;gap:12px;padding:4px 0 10px">' +
        '<h2 style="margin:0">📦 재고 목록 (Inventory)</h2>' +
        '<span style="font-size:12px;color:var(--text-muted)" id="inv-count-label">'+rows.length+' LOTs</span>' +
        '<button class="btn btn-secondary" onclick="renderPage(\'inventory\')" style="margin-left:auto">🔁 새로고침</button>' +
        '</div>' +
        /* ── 필터 / 검색 바 ── */
        '<div id="inv-filter-bar" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:8px 10px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px">' +
        '<label style="font-size:12px;white-space:nowrap;font-weight:600;color:var(--text-muted)">상태</label>' +
        '<select id="inv-status-filter" style="font-size:12px;padding:3px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)" onchange="window.invOnStatusChange()">' +
        '<option value="">전체</option>' +
        '<option value="AVAILABLE">AVAILABLE</option>' +
        '<option value="RESERVED">RESERVED</option>' +
        '<option value="PICKED">PICKED</option>' +
        '<option value="RETURN">RETURN</option>' +
        '</select>' +
        '<span style="width:1px;height:20px;background:var(--panel-border);margin:0 2px"></span>' +
        '<label style="font-size:12px;white-space:nowrap;font-weight:600;color:var(--text-muted)">SAP</label>' +
        '<select id="inv-sap-filter" style="font-size:12px;padding:3px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg);min-width:110px" onchange="window.invApplyFilter()"><option value="">전체</option></select>' +
        '<label style="font-size:12px;white-space:nowrap;font-weight:600;color:var(--text-muted)">BL</label>' +
        '<select id="inv-bl-filter" style="font-size:12px;padding:3px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg);min-width:110px" onchange="window.invApplyFilter()"><option value="">전체</option></select>' +
        '<label style="font-size:12px;white-space:nowrap;font-weight:600;color:var(--text-muted)">LOT</label>' +
        '<select id="inv-lot-filter" style="font-size:12px;padding:3px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg);min-width:130px" onchange="window.invApplyFilter()"><option value="">전체</option></select>' +
        '<label style="font-size:12px;white-space:nowrap;font-weight:600;color:var(--text-muted)">컨테이너</label>' +
        '<select id="inv-cont-filter" style="font-size:12px;padding:3px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg);min-width:130px" onchange="window.invApplyFilter()"><option value="">전체</option></select>' +
        '<button class="btn btn-ghost" style="font-size:12px;margin-left:auto" onclick="window.invClearFilter()">✕ 초기화</button>' +
        '</div>' +
        '<p style="font-size:12px;color:var(--text-muted);margin:0 0 8px 0">' +
        '목록 합계 · NET(MT): <b style="color:var(--accent)">'+fmtN(sumNet)+'</b> · Balance(MT): <b>'+fmtN(sumBal)+'</b> · 차이(순−현, 샘플 등): <b style="color:#f59e0b">'+fmtN(sumNet - sumBal)+'</b>' +
        '</p>' +
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
          '<td style="white-space:nowrap">' +
          '<button class="btn btn-ghost btn-xs" onclick="window.showLotDetail(\''+escapeHtml(r.lot||'')+'\')" title="LOT 상세">📋</button> ' +
          '<button class="btn btn-ghost btn-xs" onclick="window.invCopyLot(\''+escapeHtml(r.lot||'')+'\')" title="LOT 번호 복사">📄</button> ' +
          '<button class="btn btn-ghost btn-xs" onclick="window.invCopyRow(this)" title="행 전체 복사">📑</button> ' +
          '<button class="btn btn-ghost btn-xs" onclick="window.invQuickOutbound(\''+escapeHtml(r.lot||'')+'\')" title="즉시 출고 진입" style="color:#42a5f5">🚀</button> ' +
          '<button class="btn btn-ghost btn-xs" onclick="window.invQuickReturn(\''+escapeHtml(r.lot||'')+'\')" title="반품 진입" style="color:#ef5350">🔄</button> ' +
          '<button class="btn btn-ghost btn-xs" onclick="window.invShowLotHistory(\''+escapeHtml(r.lot||'')+'\')" title="LOT 이력" style="color:#66bb6a">📊</button>' +
          '</td>' +
          '</tr>';
      }).join('');
      html += '</tbody><tfoot><tr style="background:var(--panel);font-weight:700">';
      html += '<td colspan="6" style="text-align:right;padding:8px 10px">합계 ('+rows.length+' LOT)</td>';
      html += '<td class="mono-cell" style="text-align:right">'+fmtN(sumBal)+'</td>';
      html += '<td class="mono-cell" style="text-align:right">'+fmtN(sumNet)+'</td>';
      html += '<td colspan="10"></td>';
      html += '<td class="mono-cell" style="text-align:right">'+fmtN(sumIni)+'</td>';
      html += '<td class="mono-cell" style="text-align:right">'+fmtN(sumOb)+'</td>';
      html += '<td colspan="2"></td>';
      html += '</tr></tfoot></table></div></section>';
      c.innerHTML = html;
      // 드롭다운 초기 구성 (전체 행 기준)
      if (window.invPopulateDropdowns) window.invPopulateDropdowns(_invAllRows);
    }).catch(function(e){
      if (_currentRoute !== route) return;
      c.innerHTML = '<div class="empty" style="padding:40px;text-align:center">Load failed: '+escapeHtml(e.message||String(e))+'</div>';
      showToast('error', 'Inventory load failed');
    });
  }

  /* ── Inventory 탭 필터/검색 핸들러 ─────────────────────────────── */
  var _invAllRows = [];  // 전체 행 캐시 (필터용)

  /* SAP/BL/LOT/컨테이너 드롭다운을 statusFilteredRows 기준으로 재구성 */
  window.invPopulateDropdowns = function(filteredRows) {
    var fields = [
      { id: 'inv-sap-filter',  key: 'sap' },
      { id: 'inv-bl-filter',   key: 'bl' },
      { id: 'inv-lot-filter',  key: 'lot' },
      { id: 'inv-cont-filter', key: 'container' }
    ];
    fields.forEach(function(f) {
      var sel = document.getElementById(f.id);
      if (!sel) return;
      var prevVal = sel.value;
      var vals = [];
      filteredRows.forEach(function(r) {
        var v = (r[f.key] || '').trim();
        if (v && vals.indexOf(v) === -1) vals.push(v);
      });
      vals.sort();
      sel.innerHTML = '<option value="">전체 (' + vals.length + ')</option>' +
        vals.map(function(v) {
          return '<option value="' + escapeHtml(v) + '"' + (v === prevVal ? ' selected' : '') + '>' + escapeHtml(v) + '</option>';
        }).join('');
    });
  };

  /* 상태 변경 시: 드롭다운 재구성 후 필터 적용 */
  window.invOnStatusChange = function() {
    var statusVal = ((document.getElementById('inv-status-filter') || {}).value || '').toUpperCase();
    var statusFiltered = _invAllRows.filter(function(r) {
      return !statusVal || (r.status || '').toUpperCase() === statusVal;
    });
    window.invPopulateDropdowns(statusFiltered);
    window.invApplyFilter();
  };

  /* 4개 드롭다운 + 상태 필터 조합 적용 */
  window.invApplyFilter = function() {
    var statusVal = ((document.getElementById('inv-status-filter') || {}).value || '').toUpperCase();
    var sapVal    = (document.getElementById('inv-sap-filter')    || {}).value || '';
    var blVal     = (document.getElementById('inv-bl-filter')     || {}).value || '';
    var lotVal    = (document.getElementById('inv-lot-filter')    || {}).value || '';
    var contVal   = (document.getElementById('inv-cont-filter')   || {}).value || '';
    var tbody = document.querySelector('[data-page="inventory"] tbody');
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var visible = 0;
    rows.forEach(function(tr) {
      var cells = tr.querySelectorAll('td');
      if (!cells.length) return;
      var lot    = (cells[1] ? cells[1].textContent.trim() : '');
      var sap    = (cells[2] ? cells[2].textContent.trim() : '');
      var bl     = (cells[3] ? cells[3].textContent.trim() : '');
      var status = (cells[5] ? cells[5].textContent.trim() : '').toUpperCase();
      var cont   = (cells[8] ? cells[8].textContent.trim() : '');
      var ok = (!statusVal || status === statusVal) &&
               (!sapVal    || sap    === sapVal)    &&
               (!blVal     || bl     === blVal)     &&
               (!lotVal    || lot    === lotVal)    &&
               (!contVal   || cont   === contVal);
      tr.style.display = ok ? '' : 'none';
      if (ok) visible++;
    });
    var countEl = document.getElementById('inv-count-label');
    if (countEl) countEl.textContent = visible + ' / ' + rows.length + ' LOTs';
  };

  window.invClearFilter = function() {
    ['inv-status-filter','inv-sap-filter','inv-bl-filter','inv-lot-filter','inv-cont-filter'].forEach(function(id) {
      var el = document.getElementById(id); if (el) el.value = '';
    });
    window.invPopulateDropdowns(_invAllRows);
    window.invApplyFilter();
  };

  window.invCopyLot = function(lot) {
    if (!lot) return;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(lot).then(function(){
        showToast('success', '📋 LOT 번호 복사됨: ' + lot);
      }).catch(function(){ prompt('수동 복사:', lot); });
    } else {
      prompt('수동 복사:', lot);
    }
  };

  window.invCopyRow = function(btn) {
    var tr = btn ? btn.closest('tr') : null;
    if (!tr) return;
    var cells = Array.from(tr.querySelectorAll('td'));
    var text = cells.slice(0, cells.length - 1).map(function(td){ return td.textContent.trim(); }).join('\t');
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function(){
        showToast('success', '📑 행 복사됨');
      }).catch(function(){ prompt('수동 복사:', text); });
    } else {
      prompt('수동 복사:', text);
    }
  };

  window.invQuickOutbound = function(lot) {
    if (!lot) return;
    renderPage('outbound');
    showToast('info', '🚀 출고 탭으로 이동: ' + lot);
  };

  window.invQuickReturn = function(lot) {
    if (!lot) return;
    renderPage('return');
    showToast('info', '🔄 반품 탭으로 이동: ' + lot);
  };

  window.invShowLotHistory = function(lot) {
    if (!lot) return;
    apiGet('/api/action/lot-detail?lot_no=' + encodeURIComponent(lot)).then(function(res){
      var d = res && res.data ? res.data : res;
      var history = (d.history || d.audit_log || []);
      var lines = history.map(function(h){
        return '[' + (h.created_at||h.action_time||'').slice(0,16) + '] ' + (h.action||'') + ' — ' + (h.note||h.detail||'');
      });
      var msg = lines.length ? lines.join('\n') : '이력 없음';
      alert('📊 LOT 이력: ' + lot + '\n\n' + msg);
    }).catch(function(e){
      showToast('error', 'LOT 이력 조회 실패: ' + (e.message||e));
    });
  };


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
      '  <span style="width:1px;height:22px;background:var(--panel-border);margin:0 4px"></span>',
      '  <button class="btn btn-danger" onclick="window.allocResetAll()" title="모든 배정 취소 + AVAILABLE 원복">⚠️ 전체 초기화</button>',
      '  <button class="btn" onclick="window.allocCancelBySaleRef()" title="SALE REF 입력 후 해당 배정 전체 취소">🔖 SALE REF 취소</button>',
      '  <button class="btn" onclick="window.allocOpenLotOverview()" title="LOT별 배정 현황 팝업">📦 LOT 현황</button>',
      '  <button class="btn btn-secondary" onclick="window.allocExportExcel()" title="현재 배정 데이터 Excel 다운로드">📊 Excel 내보내기</button>',
      '</div>',
      /* ── 단계 되돌리기 버튼 행 ── */
      '<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px">',
      '  <span style="font-size:12px;font-weight:600;white-space:nowrap">&#x21A9; 단계 되돌리기:</span>',
      '  <button class="btn" onclick="window.allocRevertStep(\'RESERVED\')" style="font-size:12px">RESERVED &rarr; AVAILABLE</button>',
      '  <button class="btn" onclick="window.allocRevertStep(\'PICKED\')" style="font-size:12px">PICKED &rarr; RESERVED</button>',
      '  <button class="btn" onclick="window.allocRevertStep(\'OUTBOUND\')" style="font-size:12px">OUTBOUND &rarr; PICKED</button>',
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

  /* ── 전체 초기화 ── */
  window.allocResetAll = function() {
    if (!confirm('⚠️ 전체 초기화\n\n모든 RESERVED/PICKED/OUTBOUND 배정을 취소하고 AVAILABLE로 원복합니다.\n(SOLD는 보호됩니다)\n\n계속하시겠습니까?')) return;
    apiPost('/api/allocation/reset-all', {})
      .then(function(res){
        showToast('success', '⚠️ ' + (res.message || '전체 초기화 완료'));
        loadAllocationPage();
      })
      .catch(function(e){ showToast('error', '전체 초기화 실패: ' + (e.message||e)); });
  };

  /* ── SALE REF 일괄 취소 ── */
  window.allocCancelBySaleRef = function() {
    var saleRef = prompt('SALE REF 번호를 입력하세요 (예: SC-2026-001)');
    if (!saleRef || !saleRef.trim()) return;
    saleRef = saleRef.trim();
    if (!confirm('🔖 SALE REF 취소\n\n"' + saleRef + '" 에 해당하는 모든 배정을 취소하고 AVAILABLE로 원복합니다.\n계속하시겠습니까?')) return;
    apiPost('/api/allocation/cancel-by-sale-ref', { sale_ref: saleRef })
      .then(function(res){
        if (res.ok === false) { showToast('warn', res.message || '취소 대상 없음'); }
        else { showToast('success', '🔖 ' + (res.message || 'SALE REF 취소 완료')); loadAllocationPage(); }
      })
      .catch(function(e){ showToast('error', 'SALE REF 취소 실패: ' + (e.message||e)); });
  };

  /* ── LOT 현황 팝업 ── */
  window.allocOpenLotOverview = function() {
    showToast('info', '📦 LOT 현황 로딩...');
    apiGet('/api/allocation/lot-overview').then(function(res){
      var rows = (res.data || []);
      if (!rows.length) { showToast('warn', 'LOT 현황 데이터 없음'); return; }
      var lines = rows.map(function(r, i){
        return (i+1) + '. ' + r.lot_no +
          ' | 순중량: ' + (r.net_mt||0).toFixed(3) + 'MT' +
          ' | 현재: ' + (r.balance_mt||0).toFixed(3) + 'MT' +
          ' | 배정: ' + (r.alloc_mt||0).toFixed(3) + 'MT' +
          ' | 잔여: ' + (r.remain_mt||0).toFixed(3) + 'MT' +
          (r.sample_bags ? ' | 샘플:' + r.sample_bags + '개' : '');
      });
      alert('📦 LOT 배정 현황 (' + rows.length + '건)\n\n' + lines.join('\n'));
    }).catch(function(e){ showToast('error', 'LOT 현황 실패: ' + (e.message||e)); });
  };

  /* ── Excel 내보내기 ── */
  window.allocExportExcel = function() {
    var url = (typeof API !== 'undefined' ? API : 'http://localhost:8765') + '/api/allocation/export-excel';
    var a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast('success', '📊 Excel 다운로드 시작됨');
  };

  /* ── 단계 되돌리기 ── */
  window.allocRevertStep = function(fromStatus) {
    var labels = { RESERVED: 'RESERVED → AVAILABLE', PICKED: 'PICKED → RESERVED', OUTBOUND: 'OUTBOUND → PICKED' };
    var label = labels[fromStatus] || fromStatus;
    if (!confirm('↩️ 단계 되돌리기\n\n' + label + '\n\n' + fromStatus + ' 상태의 모든 배정을 한 단계 되돌립니다.\n계속하시겠습니까?')) return;
    apiPost('/api/allocation/revert-step', { from_status: fromStatus })
      .then(function(res){
        if (res.ok === false) { showToast('warn', res.message || '되돌릴 대상 없음'); }
        else { showToast('success', '↩️ ' + (res.message || label + ' 완료')); loadAllocationPage(); }
      })
      .catch(function(e){ showToast('error', '되돌리기 실패: ' + (e.message||e)); });
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
      var totalCount = 0, totalKg = 0;
      if (tbody) tbody.innerHTML = rows.map(function(r, idx){
        var lot = escapeHtml(r.lot_no||'');
        totalCount += (r.tonbag_count||0);
        totalKg += (r.total_kg||0);
        return '<tr class="picked-summary-row" data-lot="'+lot+'">' +
          '<td style="text-align:center;width:32px"><input type="checkbox" class="picked-row-chk" onclick="event.stopPropagation()" data-lot="'+lot+'"></td>' +
          '<td style="text-align:center;color:var(--text-muted);font-size:11px">'+(idx+1)+'</td>' +
          '<td class="mono-cell" style="text-align:center;color:var(--accent);font-weight:600;cursor:pointer" onclick="window.togglePickedDetail(\''+lot+'\')">' +
            lot+' <span class="picked-expand-icon" style="font-size:10px">▶</span></td>' +
          '<td class="mono-cell" style="text-align:center">'+escapeHtml(r.picking_no||'-')+'</td>' +
          '<td style="text-align:center">'+escapeHtml(r.customer||r.picked_to||'-')+'</td>' +
          '<td class="mono-cell" style="text-align:center">'+(r.tonbag_count||0)+'</td>' +
          '<td class="mono-cell" style="text-align:center">'+(r.total_kg!=null?fmtN(r.total_kg):'-')+'</td>' +
          '<td class="mono-cell" style="text-align:center">'+escapeHtml((r.picking_date||'').slice(0,10))+'</td>' +
          '</tr>';
      }).join('');
      var sumBar = document.getElementById('picked-summary-bar');
      if (sumBar) {
        document.getElementById('picked-sum-count').textContent = totalCount;
        document.getElementById('picked-sum-kg').textContent = fmtN(totalKg);
        sumBar.style.display = '';
      }
      document.getElementById('picked-table').style.display = '';    }).catch(function(e){
      if (_currentRoute !== route) return;
      document.getElementById('picked-loading').style.display = 'none';
      var el = document.getElementById('picked-empty');
      if (el) { el.textContent = 'Load failed: '+(e.message||String(e)); el.style.display='block'; }
    });
  }

  /* ── Picked 탭 추가 핸들러 ── */
  window.pickedToggleAll = function(checked) {
    document.querySelectorAll('.picked-row-chk').forEach(function(c){ c.checked = checked; });
  };
  window.pickedSelectAll = function() {
    var allChk = document.getElementById('picked-chk-all');
    var newState = allChk ? !allChk.checked : true;
    if (allChk) allChk.checked = newState;
    window.pickedToggleAll(newState);
  };
  window.pickedCancelSale = function() {
    var lots = Array.from(document.querySelectorAll('.picked-row-chk:checked')).map(function(c){ return c.dataset.lot; });
    if (!lots.length) { showToast('warning','되돌릴 LOT을 선택하세요'); return; }
    if (!confirm(lots.length + '개 LOT을 PICKED → RESERVED (판매 배정)로 되돌리겠습니까?')) return;
    apiPost('/api/allocation/revert-step', {step:'picked_to_reserved', lot_nos: lots})
      .then(function(res){ showToast('success', (res.reverted||lots.length) + ' LOT 되돌리기 완료'); renderPage('picked'); })
      .catch(function(e){ showToast('error', '실패: '+(e.message||String(e))); });
  };
  window.pickedExportExcel = function() {
    var a = document.createElement('a');
    a.href = '/api/allocation/export-excel?status=PICKED';
    a.download = 'picked_list.xlsx'; a.click();
  };
  var _pickedShowAllDetail = false;
  window.pickedToggleAllDetail = function() {
    _pickedShowAllDetail = !_pickedShowAllDetail;
    if (!_pickedShowAllDetail) {
      var panel = document.getElementById('picked-detail-panel');
      if (panel) panel.style.display = 'none';
      _pickedExpandedLot = null;
      document.querySelectorAll('.picked-expand-icon').forEach(function(i){ i.textContent='▶'; });
    }
  };

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
  var _obAllRows = [];  // 출고 전체 데이터 캐시

  function loadOutboundPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="outbound">',
      /* ── 제목 + 카운트 ── */
      '<div style="display:flex;align-items:center;gap:8px;padding:6px 0 8px;border-bottom:1px solid var(--panel-border);margin-bottom:8px">',
      '<h2 style="margin:0;font-size:16px">📤 출고완료(OUTBOUND) LOT 리스트</h2>',
      '<span id="ob-count-label" style="font-size:12px;color:var(--text-muted);margin-left:8px">0 LOT / 0건</span>',
      '<div style="margin-left:auto;font-size:12px">',
      '<button class="btn btn-ghost btn-sm" onclick="window.obToggleAllSale()">📋 전체 판매 보기</button>',
      '</div></div>',
      /* ── 날짜 필터 바 ── */
      '<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:6px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:8px;font-size:12px">',
      '<label style="font-weight:600;color:var(--text-muted)">시작일</label>',
      '<input id="ob-date-from" type="date" style="font-size:12px;padding:2px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)">',
      '<span style="color:var(--text-muted)">~</span>',
      '<label style="font-weight:600;color:var(--text-muted)">종료일</label>',
      '<input id="ob-date-to" type="date" style="font-size:12px;padding:2px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)">',
      '<button class="btn btn-primary btn-sm" onclick="window.obApplyFilter()">🔍 조회</button>',
      '<button class="btn btn-ghost btn-sm" onclick="window.obClearFilter()">✕ 초기화</button>',
      '</div>',
      /* ── 액션 툴바 ── */
      '<div style="display:flex;gap:6px;align-items:center;padding:4px 0 8px;flex-wrap:wrap">',
      '<button class="btn btn-secondary btn-sm" onclick="renderPage(\'outbound\')">🔁 새로고침</button>',
      '<button class="btn btn-warning btn-sm" onclick="window.obCancelOutbound()" title="선택 LOT → PICKED (판매화물 결정 단계로)">↩ 출고 취소 (→ 판매화물 결정)</button>',
      '<button class="btn btn-ghost btn-sm" onclick="window.obReturnConfirm()" title="선택 LOT → AVAILABLE (반품 처리)">🔄 반품 확정 (→ AVAILABLE)</button>',
      /* ── 합계바 ── */
      '<div style="margin-left:auto;font-size:12px;color:var(--text-muted);padding:2px 8px;background:var(--panel);border:1px solid var(--panel-border);border-radius:4px">',
      'Σ 건수: <b id="ob-sum-count">0</b> &nbsp;|&nbsp; 중량(kg): <b id="ob-sum-kg">0</b>',
      '</div></div>',
      '<div id="outbound-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '<table class="data-table" id="outbound-table" style="display:none">',
      '<thead><tr>',
      '<th style="width:32px;text-align:center"><input type="checkbox" id="ob-chk-all" onclick="window.obToggleAll(this.checked)"></th>',
      '<th style="text-align:center">No.</th>',
      '<th style="text-align:center">LOT NO</th>',
      '<th style="text-align:center">판매주문No</th>',
      '<th style="text-align:center">고객사</th>',
      '<th style="text-align:center">톤백수</th>',
      '<th style="text-align:center">중량(kg)</th>',
      '<th style="text-align:center">판매일</th>',
      '</tr></thead>',
      '<tbody id="outbound-tbody"></tbody>',
      '</table>',
      '</div>',
      '<div class="empty" id="outbound-empty" style="display:none;padding:60px;text-align:center;color:var(--text-muted)">📭 출고 데이터 없음</div>',
      '<div id="outbound-detail-panel" style="display:none;margin-top:16px;border-top:2px solid var(--border);padding-top:16px">',
      '<h3 id="outbound-detail-title" style="margin:0 0 12px 0">톤백 상세</h3>',
      '<div id="outbound-detail-content"></div>',
      '</div>',
      '</section>'
    ].join('');

    apiGet('/api/q/sold-list').then(function(res){
      if (_currentRoute !== route) return;
      _obAllRows = extractRows(res);
      document.getElementById('outbound-loading').style.display = 'none';
      window.obRenderRows(_obAllRows);
      dbgLog('📤','outbound-page','rows='+_obAllRows.length,'#4caf50');
    }).catch(function(e){
      if (_currentRoute !== route) return;
      document.getElementById('outbound-loading').style.display = 'none';
      var el = document.getElementById('outbound-empty');
      if (el) { el.textContent = '❌ 로드 실패: '+(e.message||String(e)); el.style.display = 'block'; }
      showToast('error', '출고 현황 로드 실패');
    });
  }

  window.obRenderRows = function(rows) {
    var totalCount = 0, totalKg = 0;
    var tbody = document.getElementById('outbound-tbody');
    var empty  = document.getElementById('outbound-empty');
    var table  = document.getElementById('outbound-table');
    if (!tbody) return;
    if (!rows.length) {
      table.style.display = 'none';
      empty.style.display = 'block';
      document.getElementById('ob-count-label').textContent = '0 LOT / 0건';
      document.getElementById('ob-sum-count').textContent = '0';
      document.getElementById('ob-sum-kg').textContent = '0';
      return;
    }
    empty.style.display = 'none';
    tbody.innerHTML = rows.map(function(r, i){
      var lot = escapeHtml(r.lot_no||'');
      totalCount += (r.tonbag_count||0);
      totalKg += (r.total_kg||0);
      return '<tr class="outbound-summary-row" data-lot="'+lot+'">' +
        '<td style="text-align:center;width:32px"><input type="checkbox" class="ob-row-chk" onclick="event.stopPropagation()" data-lot="'+lot+'"></td>' +
        '<td style="text-align:center;color:var(--text-muted);font-size:11px">'+(i+1)+'</td>' +
        '<td class="mono-cell" style="text-align:center;color:var(--accent);font-weight:600;cursor:pointer" onclick="window.toggleOutboundDetail(\''+lot+'\')">'+lot+' <span class="outbound-expand-icon" style="font-size:10px">▶</span></td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml(r.sales_order_no||'-')+'</td>' +
        '<td style="text-align:center">'+escapeHtml(r.customer||'-')+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+(r.tonbag_count||0)+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+(r.total_kg!=null?fmtN(r.total_kg):'-')+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml((r.sold_date||'-').slice(0,10))+'</td>' +
        '</tr>';
    }).join('');
    table.style.display = '';
    document.getElementById('ob-count-label').textContent = rows.length + ' LOT / ' + totalCount + '건';
    document.getElementById('ob-sum-count').textContent = totalCount;
    document.getElementById('ob-sum-kg').textContent = fmtN(totalKg);
  };

  window.obApplyFilter = function() {
    var from = (document.getElementById('ob-date-from')||{}).value || '';
    var to   = (document.getElementById('ob-date-to')  ||{}).value || '';
    var filtered = _obAllRows.filter(function(r) {
      var d = (r.sold_date||'').slice(0,10);
      if (from && d < from) return false;
      if (to   && d > to)   return false;
      return true;
    });
    window.obRenderRows(filtered);
  };

  window.obClearFilter = function() {
    var f = document.getElementById('ob-date-from'); if (f) f.value = '';
    var t = document.getElementById('ob-date-to');   if (t) t.value = '';
    window.obRenderRows(_obAllRows);
  };

  window.obToggleAll = function(checked) {
    document.querySelectorAll('.ob-row-chk').forEach(function(c){ c.checked = checked; });
  };

  window.obCancelOutbound = function() {
    var lots = Array.from(document.querySelectorAll('.ob-row-chk:checked')).map(function(c){ return c.dataset.lot; });
    if (!lots.length) { showToast('warning','취소할 LOT을 선택하세요'); return; }
    if (!confirm(lots.length + '개 LOT 출고 취소(→ PICKED)하겠습니까?')) return;
    apiPost('/api/allocation/revert-step', {step:'outbound_to_picked', lot_nos: lots})
      .then(function(r){ showToast('success',(r.reverted||lots.length)+' LOT 취소 완료'); renderPage('outbound'); })
      .catch(function(e){ showToast('error','실패: '+(e.message||String(e))); });
  };

  window.obReturnConfirm = function() {
    var lots = Array.from(document.querySelectorAll('.ob-row-chk:checked')).map(function(c){ return c.dataset.lot; });
    if (!lots.length) { showToast('warning','반품 처리할 LOT을 선택하세요'); return; }
    if (!confirm(lots.length + '개 LOT을 반품(→ AVAILABLE) 처리하겠습니까?')) return;
    apiPost('/api/allocation/revert-step', {step:'outbound_to_available', lot_nos: lots})
      .then(function(r){ showToast('success',(r.reverted||lots.length)+' LOT 반품 완료'); renderPage('outbound'); })
      .catch(function(e){ showToast('error','실패: '+(e.message||String(e))); });
  };

  window.obToggleAllSale = function() {
    var rows = document.querySelectorAll('.outbound-summary-row');
    rows.forEach(function(tr){ var lot = tr.dataset.lot; if (lot) window.toggleOutboundDetail(lot); });
  };

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
  var _retActiveTab = 'reinbound';  // 현재 활성 Return 서브탭

  function loadReturnPage() {
    var route = _currentRoute;
    var c = document.getElementById('page-container');
    if (!c) return;
    c.innerHTML = [
      '<section class="page" data-page="return">',
      /* ── 제목 + 서브탭 ── */
      '<div style="display:flex;align-items:center;gap:0;padding:6px 0 0;border-bottom:2px solid var(--panel-border);margin-bottom:12px">',
      '<h2 style="margin:0 16px 0 0;font-size:16px">🔄 Return Management</h2>',
      '<button class="btn btn-ghost btn-sm" id="ret-tab-reinbound" onclick="window.retSwitchTab(\'reinbound\')" style="border-radius:4px 4px 0 0;border-bottom:2px solid var(--accent);color:var(--accent)">📥 Return Inbound (Excel)</button>',
      '<button class="btn btn-ghost btn-sm" id="ret-tab-list" onclick="window.retSwitchTab(\'list\')" style="border-radius:4px 4px 0 0">📋 Return (Re-inbound)</button>',
      '<button class="btn btn-ghost btn-sm" id="ret-tab-stats" onclick="window.retSwitchTab(\'stats\')" style="border-radius:4px 4px 0 0">📊 Return Statistics</button>',
      '<button class="btn btn-secondary btn-sm" onclick="renderPage(\'return\')" style="margin-left:auto">🔁 Refresh</button>',
      '</div>',
      /* ── 통계 카드 ── */
      '<div style="display:flex;gap:12px;margin-bottom:12px">',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Total Returns</div><div id="ret-stat-total" style="font-size:24px;font-weight:700;margin-top:4px">—</div></div>',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Pending Review</div><div id="ret-stat-pending" style="font-size:24px;font-weight:700;margin-top:4px">—</div></div>',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Completed</div><div id="ret-stat-complete" style="font-size:24px;font-weight:700;margin-top:4px">—</div></div>',
      '</div>',
      /* ── Return Inbound (Excel) 패널 ── */
      '<div id="ret-panel-reinbound">',
      '<div style="padding:16px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;margin-bottom:12px">',
      '<p style="font-size:13px;color:var(--text-muted);margin:0 0 8px 0">반품 데이터를 Excel 파일로 업로드하거나 DB에서 반품 상태 항목을 조회합니다.</p>',
      '<div style="display:flex;gap:8px;flex-wrap:wrap">',
      '<button class="btn btn-primary btn-sm" onclick="window.retUploadExcel()">📂 Excel 업로드</button>',
      '<button class="btn btn-ghost btn-sm" onclick="window.retExportExcel()">📊 Excel 내보내기</button>',
      '</div></div>',
      '</div>',
      /* ── Re-inbound 목록 패널 ── */
      '<div id="ret-panel-list">',
      '<div id="return-loading" style="padding:40px;text-align:center;color:var(--text-muted)">⏳ 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '<table class="data-table" id="return-table" style="display:none">',
      '<thead><tr>',
      '<th style="text-align:center">순번</th>',
      '<th style="text-align:center">LOT NO</th>',
      '<th style="text-align:center">Product</th>',
      '<th style="text-align:center">Return Date</th>',
      '<th style="text-align:center">Qty (kg)</th>',
      '<th style="text-align:center">Reason</th>',
      '<th style="text-align:center">Status</th>',
      '</tr></thead>',
      '<tbody id="return-tbody"></tbody>',
      '</table>',
      '</div>',
      '<div class="empty" id="return-empty" style="display:none;padding:60px;text-align:center">📭 반품 데이터 없음</div>',
      '</div>',
      /* ── Statistics 패널 ── */
      '<div id="ret-panel-stats" style="display:none">',
      '<div id="ret-stats-content" style="padding:20px;color:var(--text-muted)">통계 데이터 로딩 중...</div>',
      '</div>',
      '</section>'
    ].join('');

    _retActiveTab = 'reinbound';
    window.retSwitchTab('reinbound');

    apiGet('/api/inventory?status=RETURN').then(function(res){
      if (_currentRoute !== route) return;
      var rows = extractRows(res);
      renderReturnRows(rows, route);
      /* 통계 카드 업데이트 */
      document.getElementById('ret-stat-total').textContent   = rows.length;
      document.getElementById('ret-stat-pending').textContent = rows.filter(function(r){ return !r.return_reviewed; }).length;
      document.getElementById('ret-stat-complete').textContent= rows.filter(function(r){ return r.return_reviewed; }).length;
    }).catch(function(){
      if (_currentRoute !== route) return;
      document.getElementById('return-loading').style.display = 'none';
      document.getElementById('return-empty').style.display = 'block';
    });
  }

  window.retSwitchTab = function(tab) {
    _retActiveTab = tab;
    var panels = ['reinbound','list','stats'];
    panels.forEach(function(p) {
      var panel = document.getElementById('ret-panel-' + p);
      var btn   = document.getElementById('ret-tab-' + p);
      if (!panel || !btn) return;
      if (p === tab) {
        panel.style.display = '';
        btn.style.borderBottom = '2px solid var(--accent)';
        btn.style.color = 'var(--accent)';
      } else {
        panel.style.display = 'none';
        btn.style.borderBottom = '';
        btn.style.color = '';
      }
    });
  };

  window.retUploadExcel = function() {
    showToast('info', 'Excel 업로드 기능은 준비 중입니다');
  };
  window.retExportExcel = function() {
    var a = document.createElement('a');
    a.href = '/api/allocation/export-excel?status=RETURN';
    a.download = 'return_list.xlsx'; a.click();
  };

  function renderReturnRows(rows, route) {
    if (_currentRoute !== route) return;
    document.getElementById('return-loading').style.display = 'none';
    if (!rows.length) { document.getElementById('return-empty').style.display='block'; return; }
    var tbody = document.getElementById('return-tbody');
    if (tbody) tbody.innerHTML = rows.map(function(r, i){
      var statusColor = '#f59e0b';
      return '<tr>' +
        '<td style="text-align:center;color:var(--text-muted);font-size:11px">'+(i+1)+'</td>' +
        '<td class="mono-cell" style="text-align:center;color:var(--accent);font-weight:600">'+escapeHtml(r.lot||r.lot_no||'')+'</td>' +
        '<td style="text-align:center">'+escapeHtml(r.product||'-')+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml((r.return_date||r.updated_at||r.date||'').slice(0,10))+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+(r.balance!=null?fmtN(Number(r.balance)*1000):(r.qty||r.bags||'-'))+'</td>' +
        '<td style="text-align:center">'+escapeHtml(r.return_reason||r.reason||'-')+'</td>' +
        '<td style="text-align:center"><span class="tag" style="color:'+statusColor+'">'+escapeHtml(r.status||'RETURN')+'</span></td>' +
        '</tr>';
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
      /* ── 제목 ── */
      '<div style="display:flex;align-items:center;gap:8px;padding:6px 0 8px;border-bottom:1px solid var(--panel-border);margin-bottom:10px">',
      '<h2 style="margin:0;font-size:16px">🔀 Move Management</h2>',
      '<button class="btn btn-secondary btn-sm" onclick="renderPage(\'move\')" style="margin-left:auto">🔁 Refresh</button>',
      '</div>',
      /* ── Scan to Move ── */
      '<div class="card" style="padding:14px;margin-bottom:12px">',
      '<div style="font-weight:700;font-size:13px;margin-bottom:10px">⚡ Scan to Move</div>',
      '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:8px">',
      '<div style="display:flex;align-items:center;gap:6px">',
      '<label style="font-size:12px;white-space:nowrap;min-width:90px">Tonbag UID:</label>',
      '<input id="move-barcode" class="input" placeholder="바코드 스캔 또는 입력" style="width:200px;font-size:12px;padding:3px 8px">',
      '<button class="btn btn-ghost btn-sm" onclick="window.moveLookup()">🔍 Lookup</button>',
      '<span id="move-current-loc" style="font-size:11px;color:var(--text-muted)">Current: —</span>',
      '</div>',
      '</div>',
      '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:8px">',
      '<div style="display:flex;align-items:center;gap:6px">',
      '<label style="font-size:12px;white-space:nowrap;min-width:90px">To Location:</label>',
      '<input id="move-dest" class="input" placeholder="예: A-3-2" style="width:200px;font-size:12px;padding:3px 8px">',
      '</div>',
      '<button class="btn btn-primary btn-sm" onclick="window.executeMove()">✅ Move</button>',
      '<button class="btn btn-ghost btn-sm" onclick="window.moveClear()">🗑 Clear</button>',
      '<label style="font-size:12px;display:flex;align-items:center;gap:4px">',
      '<input type="checkbox" id="move-continuous"> 연속 스캔',
      '</label>',
      '</div>',
      '<div style="font-size:11px;color:var(--text-muted)">톤백 바코드를 스캔하거나 UID를 입력하세요.</div>',
      '</div>',
      /* ── 보조 툴바 ── */
      '<div style="display:flex;gap:6px;align-items:center;padding:4px 0 8px;flex-wrap:wrap">',
      '<button class="btn btn-ghost btn-sm" onclick="showToast(\'info\',\'Excel 업로드 준비 중\')">📂 Location Upload (Excel)</button>',
      '<button class="btn btn-ghost btn-sm" onclick="window.loadMoveApprovals()">✅ Move Approval</button>',
      '</div>',
      /* ── 통계 카드 ── */
      '<div style="display:flex;gap:12px;margin-bottom:12px">',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Pending</div><div id="move-stat-pending" style="font-size:22px;font-weight:700;margin-top:4px">—</div></div>',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Approved</div><div id="move-stat-approved" style="font-size:22px;font-weight:700;margin-top:4px">—</div></div>',
      '<div class="card" style="flex:1;padding:12px;text-align:center"><div style="font-size:11px;color:var(--text-muted)">Completed</div><div id="move-stat-complete" style="font-size:22px;font-weight:700;margin-top:4px">—</div></div>',
      '</div>',
      /* ── 필터 ── */
      '<div style="display:flex;gap:8px;align-items:center;font-size:12px;margin-bottom:6px">',
      '<label>Status:</label>',
      '<select id="move-status-filter" style="font-size:12px;padding:2px 6px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg)" onchange="window.moveApplyFilter()">',
      '<option value="">ALL</option>',
      '<option value="MOVE">MOVE</option>',
      '<option value="APPROVED">APPROVED</option>',
      '<option value="COMPLETED">COMPLETED</option>',
      '</select>',
      '<label>LOT:</label>',
      '<input id="move-lot-filter" type="text" style="font-size:12px;padding:2px 8px;border-radius:4px;border:1px solid var(--panel-border);background:var(--bg);color:var(--fg);width:140px" oninput="window.moveApplyFilter()">',
      '<button class="btn btn-ghost btn-xs" onclick="window.moveFilterClear()">🔍</button>',
      '</div>',
      /* ── Move History 테이블 ── */
      '<div style="font-weight:700;font-size:13px;margin-bottom:6px">📋 Move History</div>',
      '<div id="move-loading" style="padding:20px;text-align:center;color:var(--text-muted)">⏳ 로딩 중...</div>',
      '<div style="overflow-x:auto">',
      '<table class="data-table" id="move-table" style="display:none">',
      '<thead><tr>',
      '<th style="text-align:center">순번</th>',
      '<th style="text-align:center">Time</th>',
      '<th style="text-align:center">LOT NO</th>',
      '<th style="text-align:center">Tonbag No</th>',
      '<th style="text-align:center">From</th>',
      '<th style="text-align:center">To</th>',
      '<th style="text-align:center">Status</th>',
      '<th style="text-align:center">Operator</th>',
      '</tr></thead>',
      '<tbody id="move-tbody"></tbody>',
      '</table>',
      '</div>',
      '<div class="empty" id="move-empty" style="display:none;padding:40px;text-align:center">📭 이동 이력 없음</div>',
      '</section>'
    ].join('');

    var _moveAllRows = [];

    apiGet('/api/q/movement-history').then(function(res){
      if (_currentRoute !== route) return;
      _moveAllRows = extractRows(res);
      document.getElementById('move-loading').style.display = 'none';
      /* 통계 카드 */
      var pending   = _moveAllRows.filter(function(r){ return (r.status||'').toUpperCase()==='MOVE'; }).length;
      var approved  = _moveAllRows.filter(function(r){ return (r.status||'').toUpperCase()==='APPROVED'; }).length;
      var completed = _moveAllRows.filter(function(r){ return (r.status||'').toUpperCase()==='COMPLETED'; }).length;
      document.getElementById('move-stat-pending').textContent  = pending;
      document.getElementById('move-stat-approved').textContent = approved;
      document.getElementById('move-stat-complete').textContent = completed;
      window._moveAllRows = _moveAllRows;
      window.moveRenderHistory(_moveAllRows);
    }).catch(function(){
      if (_currentRoute !== route) return;
      document.getElementById('move-loading').style.display = 'none';
      document.getElementById('move-empty').style.display = 'block';
    });
  }

  window.moveRenderHistory = function(rows) {
    var tbody = document.getElementById('move-tbody');
    var table = document.getElementById('move-table');
    var empty = document.getElementById('move-empty');
    if (!tbody) return;
    if (!rows.length) {
      if (table) table.style.display = 'none';
      if (empty) empty.style.display = 'block';
      return;
    }
    if (empty) empty.style.display = 'none';
    tbody.innerHTML = rows.map(function(r, i){
      var qtyMT = r.qty_mt != null ? fmtN(r.qty_mt) : (r.qty_kg != null ? fmtN(r.qty_kg/1000) : '-');
      return '<tr>' +
        '<td style="text-align:center;color:var(--text-muted);font-size:11px">'+(i+1)+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml(r.movement_date||r.moved_at||r.date||'')+'</td>' +
        '<td class="mono-cell" style="text-align:center;color:var(--accent)">'+escapeHtml(r.lot_no||r.sub_lt||r.barcode||'')+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml(r.tonbag_id||r.sub_lt||'-')+'</td>' +
        '<td class="mono-cell" style="text-align:center">'+escapeHtml(r.from_location||'-')+'</td>' +
        '<td class="mono-cell" style="text-align:center;color:var(--accent)">'+escapeHtml(r.to_location||'-')+'</td>' +
        '<td style="text-align:center"><span class="tag">'+escapeHtml(r.status||r.movement_type||'-')+'</span></td>' +
        '<td style="text-align:center">'+escapeHtml(r.actor||r.moved_by||'system')+'</td></tr>';
    }).join('');
    if (table) table.style.display = '';
  };

  window.moveApplyFilter = function() {
    var statusVal = ((document.getElementById('move-status-filter')||{}).value||'').toUpperCase();
    var lotVal    = ((document.getElementById('move-lot-filter')||{}).value||'').toLowerCase();
    var rows = (window._moveAllRows||[]).filter(function(r){
      var status = (r.status||r.movement_type||'').toUpperCase();
      var lot    = (r.lot_no||r.sub_lt||'').toLowerCase();
      return (!statusVal || status === statusVal) && (!lotVal || lot.includes(lotVal));
    });
    window.moveRenderHistory(rows);
  };

  window.moveFilterClear = function() {
    var s = document.getElementById('move-status-filter'); if (s) s.value = '';
    var l = document.getElementById('move-lot-filter');    if (l) l.value = '';
    window.moveRenderHistory(window._moveAllRows||[]);
  };

  window.moveLookup = function() {
    var uid = ((document.getElementById('move-barcode')||{}).value||'').trim();
    if (!uid) { showToast('warning','UID를 입력하세요'); return; }
    apiGet('/api/tonbags?sub_lt='+encodeURIComponent(uid)).then(function(res){
      var rows = extractRows(res);
      if (!rows.length) { showToast('warning','해당 톤백을 찾을 수 없습니다'); return; }
      var loc = rows[0].location||'-';
      var el = document.getElementById('move-current-loc');
      if (el) el.textContent = 'Current: ' + loc;
      showToast('info', uid + ' → 현재위치: ' + loc);
    }).catch(function(e){ showToast('error','조회 실패: '+(e.message||'')); });
  };

  window.moveClear = function() {
    var b = document.getElementById('move-barcode'); if (b) b.value = '';
    var d = document.getElementById('move-dest');    if (d) d.value = '';
    var el = document.getElementById('move-current-loc'); if (el) el.textContent = 'Current: —';
  };

  window.loadMoveApprovals = function() {
    showToast('info', 'Move Approval 기능 준비 중');
  };

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
  /* ── 이동 유형 뱃지 ── */
  var _LOG_TYPE_COLOR = {
    'INBOUND':'#4caf50','OUTBOUND':'#f44336','MOVE':'#2196f3',
    'RETURN':'#ff9800','HOLD':'#9c27b0','ADJUST':'#00bcd4',
    'ALLOCATED':'#ff9800','PICKED':'#8bc34a','SOLD':'#e91e63',
    'SWAP':'#ff5722','FIX':'#795548'
  };
  function _logTypeBadge(t) {
    var col = _LOG_TYPE_COLOR[String(t).toUpperCase()] || '#607d8b';
    return '<span style="background:'+col+';color:#fff;border-radius:3px;padding:1px 7px;font-size:11px;white-space:nowrap">'+escapeHtml(String(t||''))+'</span>';
  }
  function _logLoadMovement(limit) {
    var tbody  = document.getElementById('log-mv-tbody');
    var cntEl  = document.getElementById('log-mv-count');
    var statsEl= document.getElementById('log-mv-stats');
    if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-muted)">⏳ 로딩 중...</td></tr>';
    apiGet('/api/q/movement-history?limit='+(limit||300)).then(function(res){
      var rows  = extractRows(res);
      var stats = (res && res.data && res.data.stats) || [];
      if (cntEl) cntEl.textContent = rows.length+'건';
      if (statsEl) {
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
      tbody.innerHTML = rows.map(function(r,i){
        var td = function(v){ return '<td style="text-align:center;white-space:nowrap">'+escapeHtml(String(v||''))+'</td>'; };
        return '<tr>'+td(i+1)+
          '<td style="text-align:center">'+_logTypeBadge(r.movement_type||r.type||'')+'</td>'+
          td(r.lot_no||'')+
          '<td style="text-align:right;white-space:nowrap">'+(r.qty_kg?Number(r.qty_kg).toLocaleString()+' KG':'')+'</td>'+
          td(r.customer||'')+td(r.actor||r.operator||'system')+
          td((r.movement_date||r.created_at||'').replace('T',' ').substring(0,16))+
          td(r.remarks||r.source_type||'')+'</tr>';
      }).join('');
    }).catch(function(e){
      if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:red;padding:20px">❌ 로드 실패: '+escapeHtml(String(e))+'</td></tr>';
    });
  }
  function _logLoadAudit(limit) {
    var tbody = document.getElementById('log-au-tbody');
    var cntEl = document.getElementById('log-au-count');
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-muted)">⏳ 로딩 중...</td></tr>';
    apiGet('/api/q/audit-log?limit='+(limit||200)).then(function(res){
      var rows = extractRows(res);
      if (cntEl) cntEl.textContent = rows.length+'건';
      if (!tbody) return;
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-muted)">📭 감사 로그 없음 (OneStop 출고 시 기록됨)</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function(r,i){
        var td = function(v){ return '<td style="text-align:center;white-space:nowrap">'+escapeHtml(String(v||''))+'</td>'; };
        return '<tr>'+td(i+1)+
          '<td style="text-align:center">'+_logTypeBadge(r.event_type||'')+'</td>'+
          td(r.lot_no||r.tonbag_id||'')+td(r.created_by||'')+
          '<td style="text-align:left;max-width:300px">'+escapeHtml(String(r.event_data||r.user_note||''))+'</td>'+
          td((r.created_at||'').replace('T',' ').substring(0,16))+'</tr>';
      }).join('');
    }).catch(function(e){
      if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:red;padding:20px">❌ 로드 실패: '+escapeHtml(String(e))+'</td></tr>';
    });
  }
  window._logActiveTab = 'movement';
  window.logSwitchTab = function(tab) {
    window._logActiveTab = tab;
    var aS='padding:6px 16px;border:none;cursor:pointer;font-size:13px;border-bottom:2px solid var(--accent);color:var(--accent);background:transparent;font-weight:600';
    var iS='padding:6px 16px;border:none;cursor:pointer;font-size:13px;border-bottom:2px solid transparent;color:var(--text-muted);background:transparent;font-weight:400';
    var mb=document.getElementById('log-tab-movement'), ab=document.getElementById('log-tab-audit');
    var mp=document.getElementById('log-panel-movement'), ap=document.getElementById('log-panel-audit');
    if (mb) mb.style.cssText = tab==='movement'?aS:iS;
    if (ab) ab.style.cssText = tab==='audit'?aS:iS;
    if (mp) mp.style.display = tab==='movement'?'':'none';
    if (ap) ap.style.display = tab==='audit'?'':'none';
  };
  window.logRefresh = function() {
    var limit = parseInt(((document.getElementById('log-limit-sel')||{}).value)||300, 10);
    if (window._logActiveTab==='movement') _logLoadMovement(limit);
    else _logLoadAudit(limit);
  };
  function loadLogPage() {
    var container = document.getElementById('page-container');
    if (!container) return;
    var aS='padding:6px 16px;border:none;cursor:pointer;font-size:13px;border-bottom:2px solid var(--accent);color:var(--accent);background:transparent;font-weight:600';
    var iS='padding:6px 16px;border:none;cursor:pointer;font-size:13px;border-bottom:2px solid transparent;color:var(--text-muted);background:transparent;font-weight:400';
    var th='style="text-align:center;white-space:nowrap"';
    container.innerHTML = [
      '<section class="page" data-page="log">',
      '<div style="display:flex;align-items:center;gap:12px;padding:8px 0 6px;flex-wrap:wrap">',
        '<h2 style="margin:0">📋 로그</h2>',
        '<div style="display:flex;border-bottom:1px solid var(--panel-border)">',
          '<button id="log-tab-movement" style="'+aS+'" onclick="logSwitchTab(\'movement\')">📊 활동 이력</button>',
          '<button id="log-tab-audit"    style="'+iS+'" onclick="logSwitchTab(\'audit\')">🔒 감사 로그</button>',
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
      '<div id="log-mv-stats" style="display:flex;flex-wrap:wrap;gap:6px;margin:6px 0;min-height:22px"></div>',
      /* 활동 이력 패널 */
      '<div id="log-panel-movement">',
        '<div style="display:flex;align-items:center;margin-bottom:6px">',
          '<span style="font-size:12px;color:var(--text-muted)">stock_movement 기반 — 입고·출고·이동 전체 이력</span>',
          '<span id="log-mv-count" style="font-size:12px;color:var(--accent);margin-left:auto"></span>',
        '</div>',
        '<div style="overflow-x:auto"><table class="data-table" style="width:100%">',
          '<thead><tr>',
            '<th '+th+'>#</th><th '+th+'>유형</th><th '+th+'>LOT NO</th>',
            '<th '+th+'>중량(KG)</th><th '+th+'>고객사</th>',
            '<th '+th+'>작업자</th><th '+th+'>일시</th><th '+th+'>비고</th>',
          '</tr></thead>',
          '<tbody id="log-mv-tbody"></tbody>',
        '</table></div>',
      '</div>',
      /* 감사 로그 패널 */
      '<div id="log-panel-audit" style="display:none">',
        '<div style="display:flex;align-items:center;margin-bottom:6px">',
          '<span style="font-size:12px;color:var(--text-muted)">audit_log 기반 — OneStop 출고 감사 기록</span>',
          '<span id="log-au-count" style="font-size:12px;color:var(--accent);margin-left:auto"></span>',
        '</div>',
        '<div style="overflow-x:auto"><table class="data-table" style="width:100%">',
          '<thead><tr>',
            '<th '+th+'>#</th><th '+th+'>이벤트</th><th '+th+'>LOT/톤백</th>',
            '<th '+th+'>작업자</th><th '+th+'>내용</th><th '+th+'>일시</th>',
          '</tr></thead>',
          '<tbody id="log-au-tbody"></tbody>',
        '</table></div>',
      '</div>',
      '</section>'
    ].join('');
    window._logActiveTab = 'movement';
    _logLoadMovement(300);
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
  window._sqmZ = window._sqmZ || 10100;
  var _zFloatTop = window._sqmZ;  // IIFE 내부에서도 사용 가능하도록 유지
  function _bringToFront(el) { el.style.zIndex = ++(window._sqmZ); _zFloatTop = window._sqmZ; }
  // 전역 노출 (인라인 이벤트에서 접근 가능)
  window._bringToFront = _bringToFront;

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
      +'<div id="sqm-modal-header" onmousedown="(function(){var mi=document.getElementById(\'sqm-modal-inner\');if(mi)mi.style.zIndex=++(window._sqmZ);})()" style="flex-shrink:0;cursor:move;user-select:none;background:var(--bg-hover,rgba(0,0,0,.06));border-radius:8px 8px 0 0;border-bottom:1px solid var(--panel-border);padding:5px 48px 5px 12px;font-size:11px;color:var(--text-muted);display:flex;align-items:center;gap:6px;min-height:28px;position:relative;">'
      +'<span style="opacity:.4;letter-spacing:3px;">&#x28FF;&#x28FF;</span>&nbsp;드래그: 이동 &nbsp;|&nbsp; 모서리: 크기 조절'
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
     대량 이동 승인 모달 (F004-B) — PENDING 배치 목록 조회 + 승인/반려
     =================================================== */
  function showBatchMoveApprovalModal() {
    var REASONS = {
      RELOCATE: '일반 재배치', RACK_REPAIR: '랙 수리',
      INVENTORY_AUDIT: '재고 실사', PICKING_OPT: '피킹 최적화',
      RETURN_PUTAWAY: '반품 적치', CORRECTION: '위치 보정', OTHER: '기타'
    };

    function renderBatches(rows) {
      if (!rows || !rows.length) {
        return '<p style="color:var(--text-muted);text-align:center;padding:24px">대기 중인 이동 요청이 없습니다.</p>';
      }
      var html = '<table class="data-table" style="width:100%;font-size:.85rem"><thead><tr>'
        + '<th>배치 ID</th><th>건수</th><th>사유</th><th>요청자</th><th>요청시각</th><th>비고</th><th>처리</th>'
        + '</tr></thead><tbody>';
      rows.forEach(function(b) {
        var reasonLabel = REASONS[b.reason_code] || b.reason_code || '-';
        html += '<tr>'
          + '<td style="font-family:monospace;font-size:.8rem">' + escapeHtml(b.batch_id || '-') + '</td>'
          + '<td style="text-align:center">' + (b.total_count || 0) + '</td>'
          + '<td>' + escapeHtml(reasonLabel) + '</td>'
          + '<td>' + escapeHtml(b.submitted_by || '-') + '</td>'
          + '<td style="font-size:.78rem">' + escapeHtml((b.submitted_at || '').replace('T',' ').substring(0,16)) + '</td>'
          + '<td style="font-size:.78rem;max-width:120px;overflow:hidden;text-overflow:ellipsis">' + escapeHtml(b.note || '') + '</td>'
          + '<td style="white-space:nowrap">'
          + '<button class="btn btn-sm" style="background:var(--accent);color:#fff;margin-right:4px" '
          + 'onclick="window._batchMoveAction(\'approve\',\'' + escapeHtml(b.batch_id) + '\')">'
          + '✅ 승인</button>'
          + '<button class="btn btn-sm" style="background:var(--danger,#c62828);color:#fff" '
          + 'onclick="window._batchMoveAction(\'reject\',\'' + escapeHtml(b.batch_id) + '\')">'
          + '❌ 반려</button>'
          + '</td></tr>';
      });
      html += '</tbody></table>';
      return html;
    }

    function openModal() {
      var html = [
        '<div style="width:860px;max-width:94vw">',
        '  <h2 style="margin:0 0 12px 0">📦 대량 이동 승인</h2>',
        '  <p style="color:var(--text-muted);font-size:.88rem;margin:0 0 14px 0">',
        '    PENDING 상태의 대량 이동 요청을 확인하고 승인 또는 반려합니다.<br>',
        '    승인 시 All-or-Nothing 방식으로 즉시 DB에 반영됩니다.',
        '  </p>',
        '  <div id="bma-body" style="min-height:80px;display:flex;align-items:center;justify-content:center">',
        '    <span style="color:var(--text-muted)">불러오는 중…</span>',
        '  </div>',
        '  <div style="display:flex;justify-content:flex-end;margin-top:14px;gap:8px">',
        '    <button class="btn btn-ghost" onclick="window._bmaRefresh()">🔄 새로고침</button>',
        '    <button class="btn btn-ghost" id="bma-close-btn">닫기</button>',
        '  </div>',
        '</div>'
      ].join('\n');

      var modal = showDataModal(html);
      document.getElementById('bma-close-btn').onclick = function() { modal.close(); };

      window._bmaRefresh = function() {
        var el = document.getElementById('bma-body');
        if (!el) return;
        el.innerHTML = '<span style="color:var(--text-muted)">불러오는 중…</span>';
        fetch(API + '/api/tonbag/batch-move/pending')
          .then(function(r) { return r.json(); })
          .then(function(res) {
            if (el) el.innerHTML = renderBatches(res.data || []);
          })
          .catch(function(e) {
            if (el) el.innerHTML = '<p style="color:var(--danger,#c62828)">로드 실패: ' + escapeHtml(String(e)) + '</p>';
          });
      };

      window._batchMoveAction = function(action, batchId) {
        var label = action === 'approve' ? '승인' : '반려';
        var reason = '';
        if (action === 'reject') {
          reason = prompt('반려 사유를 입력하세요 (선택):', '') || '';
        }
        if (action === 'approve' && !confirm('배치 ' + batchId + ' 를 승인하시겠습니까?\n승인 즉시 DB에 반영됩니다.')) return;
        var url = API + '/api/tonbag/batch-move/' + action + '/' + encodeURIComponent(batchId);
        fetch(url, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({approver: 'supervisor', reason: reason})
        })
          .then(function(r) { return r.json(); })
          .then(function(res) {
            if (res.ok === false || res.detail) {
              alert(label + ' 실패: ' + (res.detail || res.message || JSON.stringify(res)));
            } else {
              alert(label + ' 완료\n' + (res.message || ''));
              window._bmaRefresh();
            }
          })
          .catch(function(e) { alert(label + ' 오류: ' + String(e)); });
      };

      window._bmaRefresh();
    }

    openModal();
  }
  window.showBatchMoveApprovalModal = showBatchMoveApprovalModal;


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

  /* Sales Order DN 템플릿 생성 */
  /* ═══════════════════════════════════════════════════════════════
     Sales Order DN 모달 — v864-2 _on_sales_order_dn_report() 매핑
     - Sales Order No 목록 + 상세 테이블 + Excel 다운로드
  ═══════════════════════════════════════════════════════════════ */
  function _soDnClose() {
    var ov = document.getElementById('so-dn-overlay');
    if (ov) ov.remove();
  }
  function showSalesOrderDnTemplateModal() {
    var overlay = document.createElement('div');
    overlay.id  = 'so-dn-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9200;display:flex;align-items:center;justify-content:center';

    var btnS = 'padding:5px 14px;border:none;border-radius:4px;cursor:pointer;font-size:12px';

    overlay.innerHTML = [
      '<div style="background:var(--card-bg);border:1px solid var(--panel-border);border-radius:10px;',
        'padding:22px 26px;width:1060px;max-width:96vw;max-height:90vh;display:flex;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,.45)">',
      /* 헤더 */
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">',
        '<h3 style="margin:0;font-size:16px">📋 Sales Order DN</h3>',
        '<button onclick="_soDnClose()" ',
          'style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--text-muted);line-height:1">✕</button>',
      '</div>',
      /* 2단 레이아웃 */
      '<div style="display:flex;gap:16px;flex:1;overflow:hidden;min-height:0">',
        /* 좌측: Sales Order No 목록 */
        '<div style="width:280px;flex-shrink:0;display:flex;flex-direction:column">',
          '<div style="font-size:12px;font-weight:600;color:var(--text-muted);margin-bottom:8px">Sales Order No 목록</div>',
          '<input id="so-dn-search" type="text" placeholder="🔍 SO No 검색..." ',
            'style="padding:5px 8px;margin-bottom:6px;background:var(--bg);color:var(--fg);',
            'border:1px solid var(--panel-border);border-radius:4px;font-size:12px;width:100%;box-sizing:border-box">',
          '<div id="so-dn-list" style="flex:1;overflow-y:auto;border:1px solid var(--panel-border);border-radius:6px;',
            'background:var(--sidebar-bg)">',
            '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px">⏳ 불러오는 중...</div>',
          '</div>',
          /* 직접 입력 */
          '<div style="margin-top:10px">',
            '<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">직접 입력</div>',
            '<div style="display:flex;gap:6px">',
              '<input id="so-dn-manual" type="text" placeholder="SO No 직접 입력" ',
                'style="flex:1;padding:5px 7px;background:var(--bg);color:var(--fg);',
                'border:1px solid var(--panel-border);border-radius:4px;font-size:12px">',
              '<button onclick="soDnManualLoad()" style="'+btnS+';background:var(--accent);color:#fff">조회</button>',
            '</div>',
          '</div>',
        '</div>',
        /* 우측: 상세 테이블 */
        '<div style="flex:1;display:flex;flex-direction:column;min-width:0">',
          '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">',
            '<div>',
              '<span id="so-dn-title" style="font-size:14px;font-weight:600">← Sales Order No를 선택하세요</span>',
              '<span id="so-dn-count" style="font-size:12px;color:var(--text-muted);margin-left:10px"></span>',
            '</div>',
            '<button id="so-dn-dl-btn" onclick="soDnDownload()" ',
              'style="'+btnS+';background:var(--success,#4caf50);color:#fff;display:none">📥 Excel 다운로드</button>',
          '</div>',
          '<div style="flex:1;overflow:auto;border:1px solid var(--panel-border);border-radius:6px">',
            '<table class="data-table" style="width:100%;min-width:600px">',
              '<thead><tr>',
                '<th style="text-align:center">#</th>',
                '<th style="text-align:center">LOT NO</th>',
                '<th style="text-align:center">제품</th>',
                '<th style="text-align:center">고객사</th>',
                '<th style="text-align:center">SAP No</th>',
                '<th style="text-align:center">BL No</th>',
                '<th style="text-align:center">출고일</th>',
                '<th style="text-align:center">Net (KG)</th>',
                '<th style="text-align:center">Gross (KG)</th>',
                '<th style="text-align:center">Plt</th>',
                '<th style="text-align:center">샘플</th>',
              '</tr></thead>',
              '<tbody id="so-dn-tbody">',
                '<tr><td colspan="11" style="text-align:center;padding:40px;color:var(--text-muted)">좌측에서 Sales Order No를 선택하세요.</td></tr>',
              '</tbody>',
            '</table>',
          '</div>',
          /* 합계 행 */
          '<div id="so-dn-summary" style="display:none;background:var(--sidebar-bg);border:1px solid var(--panel-border);',
            'border-radius:6px;padding:8px 14px;margin-top:8px;font-size:12px;display:flex;gap:20px">',
          '</div>',
        '</div>',
      '</div>',
      '</div>'
    ].join('');

    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e){ if(e.target===overlay) overlay.remove(); });

    /* 현재 선택된 SO No 저장 */
    window._soDnSelected = '';

    /* SO 목록 로드 */
    fetch(API + '/api/q3/sales-order-nos?limit=200')
      .then(function(r){ return r.json(); })
      .then(function(res){
        var items = (res && res.data && res.data.items) || [];
        var listEl = document.getElementById('so-dn-list');
        if (!listEl) return;
        if (!items.length) {
          listEl.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:12px">출고 완료된 Sales Order No 없음<br><span style="font-size:11px">직접 입력 후 조회하세요</span></div>';
          return;
        }
        window._soDnItems = items;
        soDnRenderList(items);
        /* 검색 필터 */
        var searchEl = document.getElementById('so-dn-search');
        if (searchEl) {
          searchEl.addEventListener('input', function(){
            var q = (this.value || '').toLowerCase();
            soDnRenderList(items.filter(function(it){
              return (it.sales_order_no || '').toLowerCase().indexOf(q) >= 0 ||
                     (it.customer || '').toLowerCase().indexOf(q) >= 0;
            }));
          });
        }
      })
      .catch(function(e){
        var listEl = document.getElementById('so-dn-list');
        if (listEl) listEl.innerHTML = '<div style="padding:16px;color:red;font-size:12px">조회 실패: ' + escapeHtml(String(e)) + '</div>';
      });
  }

  function soDnRenderList(items) {
    var listEl = document.getElementById('so-dn-list');
    if (!listEl) return;
    if (!items.length) {
      listEl.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:12px">검색 결과 없음</div>';
      return;
    }
    listEl.innerHTML = items.map(function(it){
      var so = it.sales_order_no || '';
      var mt = it.total_mt ? parseFloat(it.total_mt).toFixed(3) + ' MT' : '';
      var cnt = it.row_count ? it.row_count + '행' : '';
      var cust = it.customer || '';
      var isActive = so === window._soDnSelected;
      return '<div onclick="soDnSelectSo(this.dataset.so)" data-so="' + escapeHtml(so) + '" ' +
        'style="padding:9px 12px;cursor:pointer;border-bottom:1px solid var(--panel-border);' +
        (isActive ? 'background:var(--sidebar-active-bg);color:var(--sidebar-active-fg)' : 'background:transparent') +
        ';transition:background .15s">' +
        '<div style="font-size:12px;font-weight:600">' + escapeHtml(so) + '</div>' +
        '<div style="font-size:11px;opacity:.75;margin-top:2px">' + escapeHtml(cust) +
          (mt ? ' · ' + mt : '') + (cnt ? ' · ' + cnt : '') + '</div>' +
        '</div>';
    }).join('');
  }

  window.soDnSelectSo = function(so) {
    window._soDnSelected = so;
    /* 목록 다시 렌더링 (active 표시 갱신) */
    if (window._soDnItems) soDnRenderList(window._soDnItems);
    soDnLoadDetail(so);
  };

  window.soDnManualLoad = function() {
    var v = ((document.getElementById('so-dn-manual') || {}).value || '').trim();
    if (!v) { showToast('warn', 'Sales Order No를 입력하세요'); return; }
    window._soDnSelected = v;
    soDnLoadDetail(v);
  };

  function soDnLoadDetail(so) {
    var tbody  = document.getElementById('so-dn-tbody');
    var title  = document.getElementById('so-dn-title');
    var cnt    = document.getElementById('so-dn-count');
    var dlBtn  = document.getElementById('so-dn-dl-btn');
    var sumEl  = document.getElementById('so-dn-summary');
    if (title) title.textContent = so;
    if (cnt)   cnt.textContent = '조회 중...';
    if (dlBtn) dlBtn.style.display = 'none';
    if (tbody) tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:20px;color:var(--text-muted)">⏳ 로딩 중...</td></tr>';

    fetch(API + '/api/q3/sales-order-dn-template?sales_order_no=' + encodeURIComponent(so), {method:'HEAD'})
      .catch(function(){});  /* 미리 캐싱 워밍업 */

    /* 상세 데이터는 sales-order-dn API에서 SO No 필터 */
    fetch(API + '/api/q3/sales-order-dn')
      .then(function(r){ return r.json(); })
      .then(function(res){
        var allItems = (res && res.data && res.data.items) || [];
        /* lot_no 기준으로 해당 SO와 연관된 행 필터링 시도 */
        var items = allItems.filter(function(r){
          return (r.sale_ref || r.sales_order_no || '').indexOf(so) >= 0 || so === '' ||
                 (r.sub_lt || '').indexOf(so) >= 0;
        });
        /* 필터 결과가 없으면 전체 표시 (SO No가 allocation_plan에 다른 키로 있을 수 있음) */
        if (!items.length) items = allItems;

        if (!tbody) return;
        if (!items.length) {
          tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:30px;color:var(--text-muted)">📭 데이터 없음 — Excel 다운로드로 직접 확인하세요</td></tr>';
          if (cnt) cnt.textContent = '0건';
          if (dlBtn) { dlBtn.style.display = 'inline-block'; }
          return;
        }

        var totalNet = 0, totalGross = 0, totalPlt = 0;
        tbody.innerHTML = items.map(function(r, i){
          var net   = parseFloat(r.net_kg || r.qty_mt*1000 || 0);
          var gross = parseFloat(r.gross_kg || r.do_gross_kg || 0);
          var plt   = parseInt(r.ct_plt || r.total_packages || 0, 10);
          totalNet   += net;
          totalGross += gross;
          totalPlt   += plt;
          var td = function(v){ return '<td style="text-align:center;white-space:nowrap">' + escapeHtml(String(v||'')) + '</td>'; };
          return '<tr>' +
            td(i+1) +
            td(r.lot_no || r.sub_lt || '') +
            td(r.product || r.sku || '') +
            td(r.customer || '') +
            td(r.sap_no || '') +
            td(r.bl_no || '') +
            td(r.delivery_date || r.outbound_date || '') +
            '<td style="text-align:right;white-space:nowrap">' + (net ? net.toLocaleString() : '') + '</td>' +
            '<td style="text-align:right;white-space:nowrap">' + (gross ? gross.toLocaleString(undefined,{maximumFractionDigits:1}) : '') + '</td>' +
            td(plt || '') +
            td(r.is_sample ? '✓' : '') +
            '</tr>';
        }).join('');

        if (cnt) cnt.textContent = items.length + '건';
        if (dlBtn) dlBtn.style.display = 'inline-block';
        if (sumEl) {
          sumEl.style.display = 'flex';
          sumEl.innerHTML = [
            '<span>총 건수: <strong>' + items.length + '</strong></span>',
            '<span>Net 합계: <strong>' + totalNet.toLocaleString() + ' KG</strong> (' + (totalNet/1000).toFixed(3) + ' MT)</span>',
            totalGross ? '<span>Gross 합계: <strong>' + totalGross.toLocaleString(undefined,{maximumFractionDigits:1}) + ' KG</strong></span>' : '',
            totalPlt   ? '<span>총 Pallet: <strong>' + totalPlt + '</strong></span>' : '',
          ].filter(Boolean).join('');
        }
      })
      .catch(function(e){
        if (tbody) tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:red;padding:20px">❌ 조회 실패: ' + escapeHtml(String(e)) + '</td></tr>';
        if (dlBtn) dlBtn.style.display = 'inline-block';
      });
  }

  window.soDnDownload = function() {
    var so = window._soDnSelected || '';
    if (!so) { showToast('warn', 'Sales Order No를 선택하세요'); return; }
    sqmDownloadFileUrl(
      API + '/api/q3/sales-order-dn-template?sales_order_no=' + encodeURIComponent(so),
      'Sales_order_DN_' + so + '.xlsx'
    );
  };

  window.showSalesOrderDnTemplateModal = showSalesOrderDnTemplateModal;

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

  /* OneStop Inbound module -> sqm-onestop-inbound.js */
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
    apiGet('/api/settings/email').then(function(res) {
      var cfg = (res && res.data) || {};
      var inp = 'padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;width:100%';
      var html = '<div style="max-width:500px">'
        + '<h2 style="margin:0 0 16px 0">⚙️ 이메일 설정</h2>'
        + '<div style="display:grid;grid-template-columns:120px 1fr;gap:10px 12px;align-items:center;margin-bottom:16px">'
        + '<label style="font-weight:600">SMTP 서버</label><input type="text" id="em-host" value="' + escapeHtml(cfg.smtp_host||'smtp.gmail.com') + '" style="' + inp + '">'
        + '<label style="font-weight:600">포트</label><input type="number" id="em-port" value="' + (cfg.smtp_port||587) + '" style="' + inp + '">'
        + '<label style="font-weight:600">사용자</label><input type="text" id="em-user" value="' + escapeHtml(cfg.smtp_user||'') + '" placeholder="user@company.com" style="' + inp + '">'
        + '<label style="font-weight:600">비밀번호</label><input type="password" id="em-pass" value="' + escapeHtml(cfg.smtp_pass||'') + '" placeholder="앱 비밀번호" style="' + inp + '">'
        + '<label style="font-weight:600">발신 주소</label><input type="text" id="em-from" value="' + escapeHtml(cfg.from_addr||'') + '" placeholder="noreply@company.com" style="' + inp + '">'
        + '<label style="font-weight:600">수신자</label><input type="text" id="em-recipients" value="' + escapeHtml(cfg.recipients||'') + '" placeholder="admin@company.com, ..." style="' + inp + '">'
        + '<label style="font-weight:600">TLS 사용</label><label style="display:flex;align-items:center;gap:6px"><input type="checkbox" id="em-tls"' + (cfg.tls !== false ? ' checked' : '') + '> TLS 암호화</label>'
        + '<label style="font-weight:600">활성화</label><label style="display:flex;align-items:center;gap:6px"><input type="checkbox" id="em-enabled"' + (cfg.enabled ? ' checked' : '') + '> 이메일 기능 사용</label>'
        + '</div>'
        + '<div style="display:flex;gap:8px;justify-content:flex-end">'
        + '<button onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'" class="btn btn-ghost">닫기</button>'
        + '<button onclick="window._saveEmailConfig()" class="btn btn-primary">저장</button>'
        + '</div></div>';
      showDataModal('', html);
    }).catch(function() {
      showToast('error', '이메일 설정 불러오기 실패');
    });
  }
  window._saveEmailConfig = function() {
    var payload = {
      smtp_host: (document.getElementById('em-host')||{}).value||'',
      smtp_port: parseInt((document.getElementById('em-port')||{}).value||'587', 10),
      smtp_user: (document.getElementById('em-user')||{}).value||'',
      smtp_pass: (document.getElementById('em-pass')||{}).value||'',
      from_addr: (document.getElementById('em-from')||{}).value||'',
      recipients: (document.getElementById('em-recipients')||{}).value||'',
      tls:      !!(document.getElementById('em-tls')||{}).checked,
      enabled:  !!(document.getElementById('em-enabled')||{}).checked
    };
    apiPost('/api/settings/email', payload).then(function() {
      showToast('success', '이메일 설정 저장 완료');
      document.getElementById('sqm-modal').style.display = 'none';
    }).catch(function(e) {
      showToast('error', '저장 실패: ' + (e.message || String(e)));
    });
  };
  window.showEmailConfigModal = showEmailConfigModal;

  function showAutoBackupSettingsModal() {
    var INTERVAL_VALUES = [30, 60, 180, 360, 720, 1440];
    var INTERVAL_LABELS = ['30분', '1시간', '3시간', '6시간', '12시간', '24시간'];
    var inp = 'padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px';
    apiGet('/api/settings/backup').then(function(res) {
      var cfg = (res && res.data) || {};
      var selOpts = INTERVAL_VALUES.map(function(v, i) {
        return '<option value="' + v + '"' + (cfg.interval_min === v ? ' selected' : '') + '>' + INTERVAL_LABELS[i] + '</option>';
      }).join('');
      var lastBackup = cfg.last_backup ? '<div style="margin-bottom:10px;font-size:.82rem;color:var(--text-muted)">최근 백업: ' + escapeHtml(cfg.last_backup) + '</div>' : '';
      var html = '<div style="max-width:460px">'
        + '<h2 style="margin:0 0 16px 0">⏰ 자동 백업 설정</h2>'
        + '<div style="display:grid;grid-template-columns:100px 1fr;gap:10px 12px;align-items:center;margin-bottom:16px">'
        + '<label style="font-weight:600">자동 백업</label><label style="display:flex;align-items:center;gap:6px"><input type="checkbox" id="bk-enabled"' + (cfg.enabled ? ' checked' : '') + '> 활성화</label>'
        + '<label style="font-weight:600">주기</label><select id="bk-interval" style="' + inp + '">' + selOpts + '</select>'
        + '<label style="font-weight:600">보존 개수</label><input type="number" id="bk-retention" value="' + (cfg.retention||10) + '" min="1" max="100" style="' + inp + '">'
        + '<label style="font-weight:600">저장 경로</label><input type="text" id="bk-path" value="' + escapeHtml(cfg.path||'backup/') + '" style="' + inp + '">'
        + '</div>'
        + lastBackup
        + '<div style="display:flex;gap:8px;justify-content:flex-end">'
        + '<button onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'" class="btn btn-ghost">닫기</button>'
        + '<button onclick="window._saveBackupConfig()" class="btn btn-primary">저장</button>'
        + '</div></div>';
      showDataModal('', html);
    }).catch(function() {
      showToast('error', '백업 설정 불러오기 실패');
    });
  }
  window._saveBackupConfig = function() {
    var payload = {
      enabled:      !!(document.getElementById('bk-enabled')||{}).checked,
      interval_min: parseInt((document.getElementById('bk-interval')||{}).value||'60', 10),
      retention:    parseInt((document.getElementById('bk-retention')||{}).value||'10', 10),
      path:         (document.getElementById('bk-path')||{}).value||'backup/'
    };
    apiPost('/api/settings/backup', payload).then(function() {
      showToast('success', '자동 백업 설정 저장 완료');
      document.getElementById('sqm-modal').style.display = 'none';
    }).catch(function(e) {
      showToast('error', '저장 실패: ' + (e.message || String(e)));
    });
  };
  window.showAutoBackupSettingsModal = showAutoBackupSettingsModal;

  /* ── Gemini AI 설정/테스트/토글 ─────────────────────────────── */
  function showGeminiApiSettingsModal() {
    apiGet('/api/ai/settings').then(function(res) {
      var cfg = res || {};
      var inp = 'padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;width:100%';
      var statusHtml = cfg.has_key
        ? '<span style="color:var(--success)">✅ 키 등록됨</span> <span style="color:var(--text-muted);font-size:.8rem">(' + escapeHtml(cfg.key_source||'') + ')</span>'
        : '<span style="color:var(--warning)">⚠️ 키 없음</span>';
      var html = '<div style="max-width:480px">'
        + '<h2 style="margin:0 0 14px 0">🔐 Gemini API 설정</h2>'
        + '<div style="margin-bottom:12px">' + statusHtml + '</div>'
        + '<div style="display:grid;grid-template-columns:90px 1fr;gap:10px 12px;align-items:center;margin-bottom:14px">'
        + '<label style="font-weight:600">API 키</label><input type="password" id="gm-key" placeholder="새 키 입력 (변경 시만)" style="' + inp + '">'
        + '<label style="font-weight:600">모델</label><input type="text" id="gm-model" value="' + escapeHtml(cfg.model||'gemini-1.5-flash') + '" style="' + inp + '">'
        + '<label style="font-weight:600">사용</label><label style="display:flex;align-items:center;gap:6px"><input type="checkbox" id="gm-enabled"' + (cfg.enabled !== false ? ' checked' : '') + '> Gemini AI 활성화</label>'
        + '</div>'
        + '<div style="padding:9px;background:var(--bg-hover);border-radius:6px;margin-bottom:12px;font-size:.82rem;color:var(--text-muted)">키를 비워두면 기존 키가 유지됩니다.</div>'
        + '<div style="display:flex;gap:8px;justify-content:flex-end">'
        + '<button onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'" class="btn btn-ghost">닫기</button>'
        + '<button onclick="window._saveGeminiSettings()" class="btn btn-primary">저장</button>'
        + '</div></div>';
      showDataModal('', html);
    }).catch(function() {
      showToast('error', 'Gemini 설정 불러오기 실패');
    });
  }
  window._saveGeminiSettings = function() {
    var key   = (document.getElementById('gm-key')||{}).value||'';
    var model = (document.getElementById('gm-model')||{}).value||'gemini-1.5-flash';
    var enabled = !!(document.getElementById('gm-enabled')||{}).checked;
    var p1 = key.trim()
      ? apiPost('/api/ai/settings', { api_key: key.trim(), model: model })
      : Promise.resolve(null);
    p1.then(function() {
      return apiPost('/api/ai/toggle', { enabled: enabled });
    }).then(function() {
      showToast('success', 'Gemini 설정 저장 완료');
      document.getElementById('sqm-modal').style.display = 'none';
    }).catch(function(e) {
      showToast('error', '저장 실패: ' + (e.message || String(e)));
    });
  };

  function showGeminiApiTestModal() {
    showDataModal('', '<div style="max-width:440px"><h3 style="margin:0 0 12px">🧪 Gemini API 연결 테스트</h3><div id="gm-test-body" style="color:var(--text-muted)">테스트 중…</div></div>');
    apiGet('/api/ai/test').then(function(res) {
      var body = document.getElementById('gm-test-body');
      if (!body) return;
      var ok = res && res.success;
      body.innerHTML = ok
        ? '<div style="color:var(--success);font-size:1.1rem">✅ 연결 성공</div><div style="margin-top:8px;font-size:.85rem;color:var(--text-muted)">' + escapeHtml((res.message||'') + (res.model ? ' / 모델: ' + res.model : '')) + '</div>'
        : '<div style="color:var(--danger);font-size:1.1rem">❌ 연결 실패</div><div style="margin-top:8px;font-size:.85rem;color:var(--text-muted)">' + escapeHtml((res && res.message) || '알 수 없는 오류') + '</div>';
    }).catch(function(e) {
      var body = document.getElementById('gm-test-body');
      if (body) body.innerHTML = '<div style="color:var(--danger)">❌ 오류: ' + escapeHtml(e.message||String(e)) + '</div>';
    });
  }

  window._geminiToggleAction = function() {
    apiGet('/api/ai/settings').then(function(res) {
      var next = !(res && res.enabled !== false);
      return apiPost('/api/ai/toggle', { enabled: next }).then(function(r) {
        showToast('success', (r && r.message) || ('Gemini AI ' + (next ? 'ON' : 'OFF')));
      });
    }).catch(function(e) {
      showToast('error', 'Gemini 토글 실패: ' + (e.message || String(e)));
    });
  };

  /* 폰트 크기 전역 설정 */
  function normalizeFontScale(pct) {
    pct = parseInt(pct, 10);
    if (isNaN(pct)) pct = 100;
    pct = Math.max(100, Math.min(160, pct));
    return Math.round(pct / 10) * 10;
  }

  function applyFontScale(pct, notify) {
    pct = normalizeFontScale(pct);
    document.body.style.zoom = String(pct / 100);
    document.documentElement.setAttribute('data-font-scale', String(pct));
    window._sqmFontScale = pct;
    try { getStore().setItem('sqm_font_scale', String(pct)); } catch {}
    if (notify) showToast('success', '폰트 크기: ' + pct + '%');
  }

  window.sqmSetFontScale = function(pct) {
    applyFontScale(pct, true);
  };

  function applyStoredFontScale() {
    var stored = null;
    try { stored = getStore().getItem('sqm_font_scale'); } catch {}
    applyFontScale(stored || 100, false);
  }

  function showFontSizeModal() {
    var cur = window._sqmFontScale || 100;
    var html = '<div style="max-width:420px">'
      + '<h2 style="margin:0 0 14px 0">⚙️ 표시 · 엑셀</h2>'
      + '<p style="color:var(--text-muted);font-size:.9rem;margin-bottom:16px">'
      + '화면 확대와 엑셀 내보내기 동작을 설정합니다.</p>'
      + '<h3 style="margin:0 0 10px 0;font-size:1rem">🔤 화면 폰트 크기</h3>'
      + '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:12px">'
      + '전체 UI 폰트를 일괄 확대합니다. 100% = 기본값.</p>'
      + '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px">';
    [100,110,120,130,140,150,160].forEach(function(p) {
      html += '<button class="btn' + (cur === p ? ' btn-primary' : '') + '"'
        + ' onclick="window.sqmSetFontScale(' + p + ');'
        + 'document.getElementById(\'sqm-modal\').style.display=\'none\'"'
        + ' style="min-width:66px;font-size:14px">' + p + '%</button>';
    });
    html += '</div>'
      + '<div style="margin-top:8px;padding-top:16px;border-top:1px solid var(--panel-border,#1e4a7a)">'
      + '<h3 style="margin:0 0 8px 0;font-size:1rem">📊 엑셀 내보내기</h3>'
      + '<label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer">'
      + '<input type="checkbox" id="sqm-open-xlsx-after-save" style="margin-top:3px" '
      + (sqmShouldOpenXlsxAfterSave() ? 'checked ' : '')
      + 'onchange="window.sqmSetOpenXlsxAfterSave(this.checked)">'
      + '<span style="line-height:1.45">저장한 엑셀 파일을 <b>기본 프로그램(Excel)</b>으로 바로 열기'
      + '<br><span style="color:var(--text-muted);font-size:.85rem">'
      + 'PyWebView(본 프로그램)에서 “다른 이름으로 저장”으로 내보낼 때 적용됩니다.</span></span>'
      + '</label></div>'
      + '<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">'
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
      '<div style="max-width:560px">',
      '  <h2 style="margin:0 0 12px 0">📷 문서 변환 (OCR/PDF)</h2>',
      '  <p style="color:var(--text-muted);margin:0 0 12px 0;font-size:.88rem">v864 도구 메뉴와 동일하게 세부 단계를 구분합니다. 서버 OCR·배치 변환은 데스크톱 빌드(Phase 6)에서 연동합니다.</p>',
      '  <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px">',
      '    <button type="button" class="btn btn-ghost" id="dc-xlsx">📊 PDF → Excel</button>',
      '    <button type="button" class="btn btn-ghost" id="dc-docx">📝 PDF → Word</button>',
      '    <button type="button" class="btn btn-ghost" id="dc-batch">📁 일괄 변환</button>',
      '    <button type="button" class="btn btn-ghost" id="dc-analyze">🔍 문서 분석</button>',
      '    <button type="button" class="btn btn-ghost" id="dc-ocr">📷 OCR (스캔 PDF)</button>',
      '  </div>',
      '  <div style="display:grid;grid-template-columns:100px 1fr;gap:10px;align-items:center;margin-bottom:16px">',
      '    <label style="font-weight:600">변환 형식</label>',
      '    <select id="dc-format" style="padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px">',
      '      <option value="excel">→ Excel (.xlsx)</option>',
      '      <option value="word">→ Word (.docx)</option>',
      '    </select>',
      '  </div>',
      '  <div id="dc-drop" style="border:2px dashed var(--border);border-radius:8px;padding:28px 16px;text-align:center;background:var(--bg-hover);cursor:pointer;margin-bottom:12px">',
      '    <div style="font-size:2.2rem;margin-bottom:8px">📄</div>',
      '    <div id="dc-name" style="color:var(--text-muted);font-size:.9rem">클릭 또는 PDF/이미지를 드롭하세요</div>',
      '  </div>',
      '  <input type="file" id="dc-file" accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp" style="display:none">',
      '  <div style="padding:12px;background:var(--bg-hover);border-radius:6px;margin-bottom:14px;font-size:.82rem;color:var(--warning)">',
      '    💡 Tesseract 등 OCR 미설치 시 스캔 PDF는 텍스트 추출이 제한됩니다. 입고용 PDF는 메뉴 <strong>PDF 스캔 입고</strong>를 사용하세요.',
      '  </div>',
      '  <div style="display:flex;gap:8px;justify-content:flex-end">',
      '    <button onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'" class="btn btn-ghost">닫기</button>',
      '    <button id="dc-submit" class="btn btn-primary" disabled>선택 파일 변환</button>',
      '  </div>',
      '</div>'
    ].join('\n');
    showDataModal('', html);
    function stub(msg) { showToast('info', msg); }
    document.getElementById('dc-xlsx').addEventListener('click', function(){ document.getElementById('dc-format').value='excel'; stub('Excel 변환 파이프라인은 Phase 6(OCR 서버) 연동 후 사용 가능합니다.'); });
    document.getElementById('dc-docx').addEventListener('click', function(){ document.getElementById('dc-format').value='word'; stub('Word 변환 파이프라인은 Phase 6 연동 후 사용 가능합니다.'); });
    document.getElementById('dc-batch').addEventListener('click', function(){ stub('일괄 변환은 서버 배치 작업으로 Phase 6에서 제공 예정입니다.'); });
    document.getElementById('dc-analyze').addEventListener('click', function(){ stub('문서 분석(메타/표 추출)은 동일 단계에서 Gemini·로컬 OCR과 함께 연계합니다.'); });
    document.getElementById('dc-ocr').addEventListener('click', function(){ stub('스캔 PDF OCR은 Tesseract 설치 및 Phase 6 파이프라인이 필요합니다.'); });
    var drop = document.getElementById('dc-drop');
    var fi = document.getElementById('dc-file');
    var nm = document.getElementById('dc-name');
    var sub = document.getElementById('dc-submit');
    function setF(f){
      if (!f) return;
      nm.innerHTML = '✅ <strong>'+escapeHtml(f.name)+'</strong> ('+Math.round(f.size/1024)+' KB)';
      sub.disabled = false;
    }
    drop.addEventListener('click', function(){ fi.click(); });
    fi.addEventListener('change', function(e){ if(e.target.files&&e.target.files[0]) setF(e.target.files[0]); });
    drop.addEventListener('dragover', function(e){ e.preventDefault(); });
    drop.addEventListener('drop', function(e){ e.preventDefault(); if(e.dataTransfer.files&&e.dataTransfer.files[0]) setF(e.dataTransfer.files[0]); });
    sub.addEventListener('click', function(){
      showToast('info', '선택 파일 변환은 Phase 6에서 OCR 엔진 연동 후 지원됩니다');
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

  /* ===================================================
     8w. 제품 마스터 — product_master 테이블 CRUD + inventory 동기화
     =================================================== */
  /* ═══════════════════════════════════════════════════════════════
     LOT 정합성 복구 모달 — v864-2 _on_fix_lot_status_integrity 매핑
     POST /api/action/fix-integrity → eng.fix_lot_status_integrity()
  ═══════════════════════════════════════════════════════════════ */
  /* ═══════════════════════════════════════════════════════════════
     재고 추이 차트 모달 — chart.md ①② 구현
     GET  /api/q/inventory-trend    → 스냅샷 목록 + chart data
     POST /api/q/create-snapshot    → 오늘 스냅샷 생성
  ═══════════════════════════════════════════════════════════════ */
  function showInventoryTrendModal() {
    var overlay = document.createElement('div');
    overlay.id  = 'inv-trend-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9300;display:flex;align-items:center;justify-content:center';
    overlay.innerHTML = [
      '<div style="background:var(--card-bg);border:1px solid var(--panel-border);border-radius:10px;',
        'padding:22px 26px;width:860px;max-width:95vw;max-height:90vh;display:flex;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,.45)">',
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">',
        '<div>',
          '<h3 style="margin:0;font-size:16px">📊 재고 추이 차트</h3>',
          '<div style="font-size:11px;color:var(--text-muted);margin-top:2px">매일 시작 시 자동 저장 — inventory_snapshot 기반</div>',
        '</div>',
        '<div style="display:flex;gap:8px;align-items:center">',
          '<button onclick="invTrendCreateSnapshot()" style="padding:5px 12px;background:var(--success,#4caf50);color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px">📸 오늘 스냅샷 생성</button>',
          '<button onclick="document.getElementById(\'inv-trend-overlay\').remove()" style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--text-muted);line-height:1">✕</button>',
        '</div>',
      '</div>',
      '<div id="inv-trend-body" style="flex:1;overflow-y:auto">',
        '<div style="text-align:center;padding:40px;color:var(--text-muted)">⏳ 로딩 중...</div>',
      '</div>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e){ if(e.target===overlay) overlay.remove(); });
    invTrendLoad();
  }

  window.invTrendLoad = function() {
    var body = document.getElementById('inv-trend-body');
    if (!body) return;
    body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">⏳ 데이터 로딩 중...</div>';
    fetch(API + '/api/q/inventory-trend')
      .then(function(r){ return r.json(); })
      .then(function(res){
        var items = (res && res.data && res.data.items) || [];
        var chart = (res && res.data && res.data.chart) || {};
        if (!items.length) {
          body.innerHTML = [
            '<div style="text-align:center;padding:50px 20px">',
              '<div style="font-size:48px;margin-bottom:16px">📸</div>',
              '<h4 style="margin:0 0 10px;font-size:16px">스냅샷 데이터가 없습니다</h4>',
              '<p style="color:var(--text-muted);font-size:13px;margin:0 0 20px">',
                '앱이 시작될 때 자동으로 오늘 스냅샷이 저장됩니다.<br>',
                '지금 바로 생성하려면 아래 버튼을 누르세요.',
              '</p>',
              '<button onclick="invTrendCreateSnapshot()" style="padding:8px 20px;background:var(--accent);color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px">',
                '📸 오늘 스냅샷 생성',
              '</button>',
            '</div>'
          ].join('');
          return;
        }
        /* 최대값 계산 (막대 너비 비율용) */
        var maxMt = 0;
        items.forEach(function(r){ if ((r.total_weight_mt||0) > maxMt) maxMt = r.total_weight_mt||0; });
        /* 표 + 간단 막대 차트 */
        var rows = items.map(function(r, i){
          var tot = r.total_weight_mt || 0;
          var avl = r.available_weight_mt || 0;
          var pck = r.picked_weight_mt || 0;
          var barW = maxMt > 0 ? Math.round((tot / maxMt) * 200) : 0;
          var avlW = maxMt > 0 ? Math.round((avl / maxMt) * 200) : 0;
          var pckW = maxMt > 0 ? Math.round((pck / maxMt) * 200) : 0;
          var isToday = r.snapshot_date === new Date().toISOString().slice(0,10);
          return '<tr style="' + (isToday ? 'background:rgba(33,150,243,.08)' : '') + '">' +
            '<td style="text-align:center;white-space:nowrap;font-weight:'+(isToday?'600':'400')+'">' +
              escapeHtml(r.snapshot_date||'') + (isToday ? ' <span style="font-size:10px;color:var(--accent)">(오늘)</span>' : '') +
            '</td>' +
            '<td style="text-align:right">' + (r.total_lots||0) + '</td>' +
            '<td style="text-align:right">' + (r.total_tonbags||0) + '</td>' +
            /* 총재고 */
            '<td style="text-align:right;white-space:nowrap">' + tot.toFixed(2) + ' MT</td>' +
            /* 막대 시각화 */
            '<td style="padding:4px 8px">' +
              '<div style="display:flex;flex-direction:column;gap:2px;min-width:220px">' +
                '<div title="총재고" style="height:6px;background:#2196f3;width:'+barW+'px;border-radius:3px"></div>' +
                '<div title="판매가능" style="height:6px;background:#4caf50;width:'+avlW+'px;border-radius:3px"></div>' +
                '<div title="피킹/출고대기" style="height:6px;background:#ff9800;width:'+pckW+'px;border-radius:3px"></div>' +
              '</div>' +
            '</td>' +
            '<td style="text-align:right;white-space:nowrap;color:#4caf50">' + avl.toFixed(2) + ' MT</td>' +
            '<td style="text-align:right;white-space:nowrap;color:#ff9800">' + pck.toFixed(2) + ' MT</td>' +
            '</tr>';
        }).join('');

        body.innerHTML = [
          /* 범례 */
          '<div style="display:flex;gap:16px;margin-bottom:10px;font-size:12px;flex-wrap:wrap">',
            '<span><span style="display:inline-block;width:14px;height:8px;background:#2196f3;border-radius:2px;margin-right:4px"></span>총재고</span>',
            '<span><span style="display:inline-block;width:14px;height:8px;background:#4caf50;border-radius:2px;margin-right:4px"></span>판매가능</span>',
            '<span><span style="display:inline-block;width:14px;height:8px;background:#ff9800;border-radius:2px;margin-right:4px"></span>피킹/출고대기</span>',
            '<span style="margin-left:auto;color:var(--text-muted)">총 '+items.length+'일 데이터</span>',
          '</div>',
          '<div style="overflow-x:auto">',
          '<table class="data-table" style="width:100%">',
            '<thead><tr>',
              '<th style="text-align:center">날짜</th>',
              '<th style="text-align:center">LOT 수</th>',
              '<th style="text-align:center">톤백 수</th>',
              '<th style="text-align:center">총재고</th>',
              '<th style="text-align:center;min-width:230px">추이 막대</th>',
              '<th style="text-align:center">판매가능</th>',
              '<th style="text-align:center">피킹/출고대기</th>',
            '</tr></thead>',
            '<tbody>' + rows + '</tbody>',
          '</table></div>'
        ].join('');
      })
      .catch(function(e){
        if (body) body.innerHTML = '<div style="text-align:center;color:red;padding:40px">❌ 로드 실패: '+escapeHtml(String(e))+'</div>';
      });
  };

  window.invTrendCreateSnapshot = function() {
    showToast('info', '⏳ 오늘 스냅샷 생성 중...');
    fetch(API + '/api/q/create-snapshot?force=false', {method:'POST'})
      .then(function(r){ return r.json(); })
      .then(function(res){
        if (res && res.ok === false) {
          showToast('warn', res.error || '스냅샷 생성 실패');
          return;
        }
        var d = (res && res.data) || {};
        if (d.created === false) {
          showToast('info', '이미 오늘 스냅샷이 있습니다. (force=true로 덮어쓰기 가능)');
        } else {
          showToast('success', '스냅샷 생성 완료 — ' + (d.date||'') + ' / ' + (d.total_lots||0) + ' LOT / ' + ((d.total_weight_kg||0)/1000).toFixed(2) + ' MT');
        }
        invTrendLoad();  /* 목록 새로고침 */
      })
      .catch(function(e){
        showToast('error', '스냅샷 생성 오류: ' + escapeHtml(String(e)));
      });
  };

  /* ═══════════════════════════════════════════════════════════════
     Swap 리포트 모달 — v864-2 _show_swap_report_dialog() 매핑
     GET /api/action2/swap-report?start_date=&end_date=&customer=&lot_no=&operator=
     GET /api/action2/swap-report/export?fmt=xlsx
  ═══════════════════════════════════════════════════════════════ */
  function showSwapReportModal() {
    /* 오늘 날짜 기본값 */
    var today = new Date();
    function fmt(d) {
      return d.getFullYear() + '-' +
        String(d.getMonth()+1).padStart(2,'0') + '-' +
        String(d.getDate()).padStart(2,'0');
    }
    var d30 = new Date(today); d30.setDate(d30.getDate() - 30);
    var defStart = fmt(d30);
    var defEnd   = fmt(today);

    var overlay = document.createElement('div');
    overlay.id  = 'swap-report-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9100;display:flex;align-items:center;justify-content:center';

    var inp = 'width:120px;padding:4px 6px;background:var(--bg);color:var(--fg);border:1px solid var(--panel-border);border-radius:4px;font-size:12px;font-family:inherit';
    var inpW = 'width:150px;padding:4px 6px;background:var(--bg);color:var(--fg);border:1px solid var(--panel-border);border-radius:4px;font-size:12px;font-family:inherit';
    var btnS = 'padding:5px 14px;border:none;border-radius:4px;cursor:pointer;font-size:12px';

    overlay.innerHTML = [
      '<div style="background:var(--card-bg);border:1px solid var(--panel-border);border-radius:10px;',
        'padding:22px 26px;width:900px;max-width:95vw;max-height:88vh;display:flex;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,.45)">',
      /* 헤더 */
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">',
        '<h3 style="margin:0;font-size:16px">🔁 Swap 리포트</h3>',
        '<button onclick="document.getElementById(\'swap-report-overlay\').remove()" ',
          'style="background:none;border:none;font-size:20px;cursor:pointer;color:var(--text-muted);line-height:1">✕</button>',
      '</div>',
      /* 조회 조건 */
      '<div style="background:var(--sidebar-bg);border:1px solid var(--panel-border);border-radius:6px;padding:12px 16px;margin-bottom:12px">',
        '<div style="font-size:12px;color:var(--text-muted);font-weight:600;margin-bottom:10px">조회 조건</div>',
        '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">',
          '<label style="font-size:12px">시작일<br><input id="sr-start" type="date" value="'+defStart+'" style="'+inp+'"></label>',
          '<label style="font-size:12px">종료일<br><input id="sr-end"   type="date" value="'+defEnd+'"   style="'+inp+'"></label>',
          '<label style="font-size:12px">고객사<br><input id="sr-cust"  type="text" placeholder="전체"   style="'+inpW+'"></label>',
          '<label style="font-size:12px">LOT NO<br><input id="sr-lot"   type="text" placeholder="전체"   style="'+inpW+'"></label>',
          '<label style="font-size:12px">작업자<br><input id="sr-op"    type="text" placeholder="전체"   style="'+inpW+'"></label>',
          '<div style="margin-top:14px">',
            '<button onclick="swapReportSearch()" style="'+btnS+';background:var(--accent);color:#fff">🔍 조회</button>',
          '</div>',
        '</div>',
      '</div>',
      /* 카운트 + 내보내기 */
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">',
        '<span id="sr-count" style="font-size:12px;color:var(--text-muted)">— 건</span>',
        '<button onclick="swapReportExport()" style="'+btnS+';background:var(--success,#4caf50);color:#fff">📥 Excel 내보내기</button>',
      '</div>',
      /* 테이블 */
      '<div style="overflow:auto;flex:1;border:1px solid var(--panel-border);border-radius:6px">',
        '<table class="data-table" id="sr-table" style="width:100%;min-width:720px">',
          '<thead><tr>',
            '<th style="text-align:center;white-space:nowrap">#</th>',
            '<th style="text-align:center;white-space:nowrap">SWAP_AT</th>',
            '<th style="text-align:center;white-space:nowrap">LOT NO</th>',
            '<th style="text-align:center;white-space:nowrap">CUSTOMER</th>',
            '<th style="text-align:center;white-space:nowrap">OPERATOR</th>',
            '<th style="text-align:center;white-space:nowrap">EXPECTED UID</th>',
            '<th style="text-align:center;white-space:nowrap">SCANNED UID</th>',
            '<th style="text-align:center;white-space:nowrap">REASON</th>',
          '</tr></thead>',
          '<tbody id="sr-tbody"><tr><td colspan="8" style="text-align:center;padding:30px;color:var(--text-muted)">조회 조건을 입력하고 [🔍 조회]를 누르세요.</td></tr></tbody>',
        '</table>',
      '</div>',
      '</div>'
    ].join('');

    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e){ if(e.target===overlay) overlay.remove(); });
  }

  window.swapReportSearch = function() {
    var start  = (document.getElementById('sr-start') || {}).value || '';
    var end    = (document.getElementById('sr-end')   || {}).value || '';
    var cust   = (document.getElementById('sr-cust')  || {}).value || '';
    var lot    = (document.getElementById('sr-lot')   || {}).value || '';
    var op     = (document.getElementById('sr-op')    || {}).value || '';

    if (!start || !end) { showToast('warn','시작일과 종료일을 입력하세요'); return; }

    var tbody = document.getElementById('sr-tbody');
    var cnt   = document.getElementById('sr-count');
    if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-muted)">⏳ 조회 중...</td></tr>';
    if (cnt)   cnt.textContent = '조회 중...';

    var url = API + '/api/action2/swap-report?start_date=' + encodeURIComponent(start) +
              '&end_date=' + encodeURIComponent(end) +
              '&customer=' + encodeURIComponent(cust) +
              '&lot_no='   + encodeURIComponent(lot)  +
              '&operator=' + encodeURIComponent(op);

    fetch(url)
      .then(function(r){ return r.json(); })
      .then(function(res){
        var rows = (res.data && res.data.rows) || [];
        if (cnt) cnt.textContent = rows.length + '건';
        if (!tbody) return;
        if (!rows.length) {
          tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:30px;color:var(--text-muted)">📭 조회 결과 없음</td></tr>';
          return;
        }
        tbody.innerHTML = rows.map(function(r, i){
          var td = function(v){ return '<td style="text-align:center;white-space:nowrap">' + escapeHtml(String(v||'')) + '</td>'; };
          return '<tr>' +
            td(i+1) + td(r.created_at) + td(r.lot_no) + td(r.customer) + td(r.operator) +
            '<td style="text-align:center;font-family:monospace;font-size:11px">' + escapeHtml(String(r.expected_uid||'')) + '</td>' +
            '<td style="text-align:center;font-family:monospace;font-size:11px">' + escapeHtml(String(r.scanned_uid||'')) + '</td>' +
            td(r.reason) + '</tr>';
        }).join('');
      })
      .catch(function(e){
        if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:red;padding:20px">❌ 조회 실패: ' + escapeHtml(String(e)) + '</td></tr>';
        showToast('error','Swap 리포트 조회 실패');
      });
  };

  window.swapReportExport = function() {
    var start  = (document.getElementById('sr-start') || {}).value || '';
    var end    = (document.getElementById('sr-end')   || {}).value || '';
    var cust   = (document.getElementById('sr-cust')  || {}).value || '';
    var lot    = (document.getElementById('sr-lot')   || {}).value || '';
    var op     = (document.getElementById('sr-op')    || {}).value || '';
    if (!start || !end) { showToast('warn','시작일과 종료일을 입력하세요'); return; }
    var url = API + '/api/action2/swap-report/export?fmt=xlsx&start_date=' + encodeURIComponent(start) +
              '&end_date=' + encodeURIComponent(end) +
              '&customer=' + encodeURIComponent(cust) +
              '&lot_no='   + encodeURIComponent(lot)  +
              '&operator=' + encodeURIComponent(op);
    sqmDownloadFileUrl(url, 'Swap_리포트_' + start + '_' + end + '.xlsx');
  };

  function _fixLotIntegrityClose() {
    var ov = document.getElementById('fix-lot-integrity-overlay');
    if (ov) ov.remove();
    renderPage(_currentRoute || 'dashboard');
  }
  function showFixLotIntegrityModal() {
    var ok = window.confirm(
      'LOT 상태를 톤백 기준으로 일괄 보정합니다.\n\n' +
      '• LOT=SOLD/OUTBOUND 이지만 AVAILABLE 톤백 잔존 → AVAILABLE/PARTIAL\n' +
      '• LOT=AVAILABLE 이지만 전체 SOLD → OUTBOUND\n\n' +
      '계속하시겠습니까?'
    );
    if (!ok) return;
    showToast('info', '⏳ LOT 정합성 복구 실행 중...');
    apiCall('POST', '/api/action/fix-integrity', {})
      .then(function(res) {
        if (!res || res.ok === false) {
          showToast('error', 'LOT 정합성 복구 실패: ' + ((res && res.error) || '알 수 없는 오류'));
          return;
        }
        var d = (res.data) || {};
        var fixed  = d.fixed_count  !== undefined ? d.fixed_count  : (d.repaired || '?');
        var total  = d.total_checked !== undefined ? d.total_checked : '';
        var msg = 'LOT 정합성 복구 완료 — 수정: ' + fixed + '건';
        if (total) msg += ' / 검사: ' + total + '건';
        showToast('success', msg);
        /* 결과 모달 */
        var details = '';
        if (d.details && d.details.length) {
          details = '<ul style="text-align:left;max-height:200px;overflow:auto;padding-left:20px">' +
            d.details.map(function(x){
              return '<li style="font-size:12px;margin:2px 0">' +
                escapeHtml(x.lot_no || x) + ' : ' +
                escapeHtml(x.old_status || '') + ' → ' +
                escapeHtml(x.new_status || '') + '</li>';
            }).join('') + '</ul>';
        }
        var overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9000;display:flex;align-items:center;justify-content:center';
        overlay.innerHTML = [
          '<div style="background:var(--card-bg);border:1px solid var(--panel-border);border-radius:8px;padding:24px 28px;min-width:340px;max-width:480px;box-shadow:0 8px 32px rgba(0,0,0,.4)">',
          '<h3 style="margin:0 0 12px;font-size:16px">🛠 LOT 정합성 복구 결과</h3>',
          '<p style="margin:0 0 10px;font-size:14px">수정된 LOT: <strong>' + fixed + '건</strong>' + (total ? ' / 전체 검사: ' + total + '건' : '') + '</p>',
          details || '<p style="color:var(--text-muted);font-size:13px">수정 대상 없음 (모두 정상)</p>',
          '<div style="text-align:right;margin-top:16px">',
          '<button onclick="_fixLotIntegrityClose()" style="padding:6px 18px;background:var(--accent);color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:13px">확인 &amp; 새로고침</button>',
          '</div></div>'
        ].join('');
        document.body.appendChild(overlay);
        overlay.addEventListener('click', function(e){ if(e.target===overlay) overlay.remove(); });
      })
      .catch(function(e) {
        showToast('error', 'LOT 정합성 복구 오류: ' + (e.message || String(e)));
      });
  }

  function showProductMasterModal() {
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

  function showReturnStatisticsModal() {
    showDataModal('📊 반품 사유 통계', '<div style="padding:20px;text-align:center">⏳ Loading...</div>');
    apiGet('/api/q2/return-stats').then(function(res){
      var d = res.data || res || {};
      var byReason = d.by_reason || [];
      var monthly = d.monthly_trend || [];
      var total = d.total || {};
      var tbl1 = '<table class="data-table"><thead><tr><th>사유</th><th>건수</th><th>중량(MT)</th></tr></thead><tbody>';
      if (!byReason.length) tbl1 += '<tr><td colspan="3" class="empty">사유별 데이터 없음</td></tr>';
      byReason.forEach(function(r){
        tbl1 += '<tr><td>'+escapeHtml(String(r.reason||'-'))+'</td><td>'+(r.cnt!=null?r.cnt:0)+'</td><td class="mono-cell">'+(r.total_mt!=null?r.total_mt:'-')+'</td></tr>';
      });
      tbl1 += '</tbody></table>';
      var tbl2 = '<table class="data-table"><thead><tr><th>월</th><th>건수</th><th>중량(MT)</th></tr></thead><tbody>';
      if (!monthly.length) tbl2 += '<tr><td colspan="3" class="empty">월별 데이터 없음</td></tr>';
      monthly.forEach(function(r){
        tbl2 += '<tr><td>'+escapeHtml(String(r.month||'-'))+'</td><td>'+(r.cnt!=null?r.cnt:0)+'</td><td class="mono-cell">'+(r.total_mt!=null?r.total_mt:'-')+'</td></tr>';
      });
      tbl2 += '</tbody></table>';
      var sum = '<p style="color:var(--text-muted);font-size:.9rem;margin-bottom:10px">전체 <strong>'+(total.cnt!=null?total.cnt:0)+'</strong>건 · '
        + '<strong>'+(total.total_mt!=null?total.total_mt:'0')+'</strong> MT (return_history)</p>';
      document.getElementById('sqm-modal-content').innerHTML = [
        '<h2 style="margin-bottom:8px">📊 반품 사유 통계</h2>',
        sum,
        '<h3 style="margin:14px 0 8px;font-size:1rem">사유별</h3>', tbl1,
        '<h3 style="margin:14px 0 8px;font-size:1rem">월별 추이 (최근 12개월)</h3>', tbl2
      ].join('');
    }).catch(function(e){
      document.getElementById('sqm-modal-content').innerHTML = '<h2>반품 통계</h2><div class="empty">'+escapeHtml(e.message||String(e))+'</div>';
    });
  }
  window.showReturnStatisticsModal = showReturnStatisticsModal;

  function showAdvancedToolsHubModal() {
    var h = [
      '<div style="max-width:440px">',
      '  <h2 style="margin:0 0 12px 0">🔧 고급 도구</h2>',
      '  <p style="color:var(--text-muted);font-size:.86rem;margin-bottom:14px">v864 「고급」에 해당하는 진단·유지보수로 이동합니다.</p>',
      '  <div style="display:flex;flex-direction:column;gap:8px">',
      '    <button type="button" class="btn btn-primary" id="adv-int">🩺 정합성 검증 (시각화)</button>',
      '    <button type="button" class="btn btn-ghost" id="adv-opt">🔧 DB 최적화</button>',
      '    <button type="button" class="btn btn-ghost" id="adv-log">📋 로그 정리</button>',
      '    <button type="button" class="btn btn-ghost" id="adv-testdb">🗑️ 테스트 DB 초기화</button>',
      '  </div>',
      '  <div style="margin-top:14px;text-align:right"><button type="button" class="btn btn-ghost" onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'">닫기</button></div>',
      '</div>'
    ].join('\n');
    showDataModal('', h);
    document.getElementById('adv-int').addEventListener('click', function(){
      document.getElementById('sqm-modal').style.display='none';
      renderInfoModal('정합성 검증 (시각화)', '/api/action/integrity-report');
    });
    document.getElementById('adv-opt').addEventListener('click', function(){
      document.getElementById('sqm-modal').style.display='none';
      dispatchAction('onOptimizeDb');
    });
    document.getElementById('adv-log').addEventListener('click', function(){
      document.getElementById('sqm-modal').style.display='none';
      dispatchAction('onCleanupLogs');
    });
    document.getElementById('adv-testdb').addEventListener('click', function(){
      document.getElementById('sqm-modal').style.display='none';
      dispatchAction('onTestDbReset');
    });
  }
  window.showAdvancedToolsHubModal = showAdvancedToolsHubModal;

  function showAiToolsHubModal() {
    var h = [
      '<div style="max-width:420px;padding:4px 0">',
      '  <h2 style="margin:0 0 12px 0">🤖 AI / 선사 도구</h2>',
      '  <p style="color:var(--text-muted);font-size:.86rem;margin-bottom:16px">자주 쓰는 항목을 모았습니다.</p>',
      '  <div style="display:flex;flex-direction:column;gap:10px">',
      '    <button type="button" class="btn btn-primary" id="aihub-carrier">🚢 선사 프로파일 (BL 등록)</button>',
      '    <button type="button" class="btn btn-primary" id="aihub-gemini-set">🔐 Gemini API 설정</button>',
      '    <button type="button" class="btn btn-ghost" id="aihub-gemini-test">🧪 Gemini 연결 테스트</button>',
      '  </div>',
      '  <div style="margin-top:16px;text-align:right"><button type="button" class="btn btn-ghost" onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'">닫기</button></div>',
      '</div>'
    ].join('\n');
    showDataModal('', h);
    document.getElementById('aihub-carrier').addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; showCarrierProfileModal(); });
    document.getElementById('aihub-gemini-set').addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; showGeminiApiSettingsModal(); });
    document.getElementById('aihub-gemini-test').addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; showGeminiApiTestModal(); });
  }
  window.showAiToolsHubModal = showAiToolsHubModal;

  function showReportTemplatesHubModal() {
    function renderFiles(items) {
      var box = document.getElementById('rt-file-list');
      if (!box) return;
      if (!items || !items.length) {
        box.innerHTML = '<div class="empty" style="padding:12px">업로드된 양식 파일이 없습니다 (.xlsx · .pdf 등)</div>';
        return;
      }
      var tbl = '<table class="data-table"><thead><tr><th>파일명</th><th>크기</th><th>수정일</th><th></th></tr></thead><tbody>';
      items.forEach(function(it){
        var nm = it.name || '';
        tbl += '<tr><td style="font-weight:600;word-break:break-all">'+escapeHtml(nm)+'</td><td class="mono-cell">'+(it.size_bytes!=null?Math.round(it.size_bytes/1024)+' KB':'-')+'</td><td style="font-size:.82rem">'+escapeHtml(it.modified_at||'-')+'</td>'
          + '<td><button type="button" class="btn btn-ghost rt-del" style="padding:4px 8px;font-size:.8rem;color:var(--danger,#c62828)" data-enc="'+encodeURIComponent(nm)+'">삭제</button></td></tr>';
      });
      tbl += '</tbody></table>';
      box.innerHTML = tbl;
      box.querySelectorAll('.rt-del').forEach(function(btn){
        btn.addEventListener('click', function(){
          var enc = btn.getAttribute('data-enc');
          var name = enc ? decodeURIComponent(enc) : '';
          if (!name || !window.confirm('파일을 삭제할까요?')) return;
          fetch(API + '/api/report-templates/file?name=' + encodeURIComponent(name), { method: 'DELETE' })
            .then(function(r){ return r.json(); })
            .then(function(res){
              if (res && res.ok === false) { showToast('error', res.error || '삭제 실패'); return; }
              showToast('success', '삭제됨');
              refreshList();
            }).catch(function(e){ showToast('error', String(e.message||e)); });
        });
      });
    }

    function refreshList() {
      apiGet('/api/report-templates/list').then(function(res){
        var d = res.data || res || {};
        renderFiles(d.items || []);
      }).catch(function(){
        var box = document.getElementById('rt-file-list');
        if (box) box.innerHTML = '<div class="empty">목록 조회 실패</div>';
      });
    }

    var h = [
      '<div style="max-width:520px;padding:4px 0">',
      '  <h2 style="margin:0 0 10px 0">📂 보고서 양식 · 데이터</h2>',
      '  <p style="color:var(--text-muted);font-size:.86rem;margin-bottom:12px">',
      '    <code>data/report_templates/</code> 에 보관되는 업로드 양식입니다. 일·월·재고 집계는 아래 버튼으로 확인합니다.',
      '  </p>',
      '  <div style="margin-bottom:14px;padding:12px;background:var(--bg-hover);border-radius:8px;border:1px solid var(--border)">',
      '    <div style="font-weight:600;margin-bottom:8px">양식 파일 업로드</div>',
      '    <input type="file" id="rt-file" accept=".xlsx,.xls,.pdf,.docx,.csv,.html" style="margin-bottom:8px"/>',
      '    <button type="button" class="btn btn-primary" id="rt-upload">업로드</button>',
      '  </div>',
      '  <h3 style="font-size:1rem;margin:0 0 8px">저장된 양식</h3>',
      '  <div id="rt-file-list" style="max-height:220px;overflow:auto;border:1px solid var(--border);border-radius:8px;margin-bottom:14px"><div class="empty" style="padding:12px">Loading...</div></div>',
      '  <div style="display:flex;flex-direction:column;gap:8px">',
      '    <button type="button" class="btn btn-primary" id="rt-daily">📊 일일 현황 데이터</button>',
      '    <button type="button" class="btn btn-primary" id="rt-monthly">📅 월간 실적 데이터</button>',
      '    <button type="button" class="btn btn-ghost" id="rt-inv">📦 재고 현황 보고서(집계)</button>',
      '  </div>',
      '  <div style="margin-top:16px;text-align:right"><button type="button" class="btn btn-ghost" onclick="document.getElementById(\'sqm-modal\').style.display=\'none\'">닫기</button></div>',
      '</div>'
    ].join('\n');
    showDataModal('', h);
    document.getElementById('rt-daily').addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; renderInfoModal('일일 보고서', '/api/q2/report-daily'); });
    document.getElementById('rt-monthly').addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; renderInfoModal('월간 보고서', '/api/q2/report-monthly'); });
    document.getElementById('rt-inv').addEventListener('click', function(){ document.getElementById('sqm-modal').style.display='none'; renderInfoModal('재고 현황 보고서', '/api/q/inventory-report'); });
    document.getElementById('rt-upload').addEventListener('click', function(){
      var fi = document.getElementById('rt-file');
      if (!fi || !fi.files || !fi.files[0]) { showToast('warning', '파일을 선택하세요'); return; }
      var fd = new FormData();
      fd.append('file', fi.files[0]);
      fetch(API + '/api/report-templates/upload', { method: 'POST', body: fd })
        .then(function(r){ return r.json(); })
        .then(function(res){
          if (res && res.ok === false) { showToast('error', res.error || '업로드 실패'); return; }
          showToast('success', res.message || '업로드 완료');
          fi.value = '';
          refreshList();
        }).catch(function(e){ showToast('error', String(e.message||e)); });
    });
    refreshList();
  }
  window.showReportTemplatesHubModal = showReportTemplatesHubModal;

  function showReportHistoryAuditModal() {
    showDataModal('📋 보고서·작업 이력', '<div style="padding:20px;text-align:center">⏳ Loading...</div>');
    apiGet('/api/q/audit-log?limit=150').then(function(res){
      var rows = extractRows(res);
      if (!rows.length) {
        document.getElementById('sqm-modal-content').innerHTML = '<h2>📋 보고서·작업 이력</h2><div class="empty">감사 로그가 없습니다</div>';
        return;
      }
      var prefer = rows.filter(function(r){
        var t = ((r.event_type || '') + ' ' + (String(r.event_data || ''))).toUpperCase();
        return t.indexOf('PDF') >= 0 || t.indexOf('REPORT') >= 0 || t.indexOf('OUTBOUND') >= 0 || t.indexOf('INBOUND') >= 0;
      });
      var show = prefer.length ? prefer.slice(0, 80) : rows.slice(0, 80);
      var tbl = '<table class="data-table"><thead><tr><th>시간</th><th>유형</th><th>요약</th></tr></thead><tbody>';
      show.forEach(function(r){
        var ts = escapeHtml(r.created_at || r.ts || '-');
        var et = escapeHtml(r.event_type || '-');
        var ed = r.event_data != null ? String(r.event_data) : '';
        if (ed.length > 120) ed = ed.slice(0, 117) + '…';
        tbl += '<tr><td style="white-space:nowrap;font-size:.82rem">' + ts + '</td><td><span class="tag">' + et + '</span></td><td style="font-size:.82rem;max-width:280px;word-break:break-all">' + escapeHtml(ed) + '</td></tr>';
      });
      tbl += '</tbody></table>';
      document.getElementById('sqm-modal-content').innerHTML = [
        '<h2 style="margin-bottom:8px">📋 보고서·작업 이력</h2>',
        '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:10px">audit_log 기준 최근 ' + show.length + '건 (PDF·보고서·입출고 관련 우선 표시)</p>',
        tbl
      ].join('');
    }).catch(function(e){
      document.getElementById('sqm-modal-content').innerHTML = '<h2>이력</h2><div class="empty">조회 실패</div>';
    });
  }
  window.showReportHistoryAuditModal = showReportHistoryAuditModal;

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
    'onReturnStatistics': {m:'JS', u:'return-statistics-modal',                  lbl:'반품 사유 통계'},
    'onRecentFiles':     {m:'GET',  u:'/api/q2/recent-files',                   lbl:'최근 파일'},
    'onExit':            {m:'JS',   u:'exit',                                    lbl:'종료'},

    /* ── 입고 메뉴 ── */
    /* v864.3 Phase 4-B: PDF 스캔 입고 네이티브 모달 (기존 scan 탭 대신) */
    'onOnPdfInbound':    {m:'JS', u:'pdf-inbound-upload', lbl:'PDF 스캔 입고'},
    /* v864.3 Phase 4-B: 수동 입고는 네이티브 모달로 처리 (tkinter filedialog 대체) */
    'onInboundManual':   {m:'JS', u:'inbound-upload', lbl:'수동 입고'},
    /* v864.2 menu_registry: _bulk_import_inventory_simple — 동일 모달 */
    'onBulkImportInventorySimple': {m:'JS', u:'inbound-upload', lbl:'엑셀 파일 수동 입고'},
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
    /* v865: 대량 이동 승인 워크플로 */
    'onBatchMoveApproval': {m:'JS', u:'batch-move-approval', lbl:'대량 이동 승인'},
    /* v864.3 Phase 4-B: Allocation 입력(출고 예약) 네이티브 Excel 업로드 */
    'onInventoryAllocation': {m:'JS', u:'allocation-upload', lbl:'Allocation 입력'},
    'onIntegrityCheck':  {m:'GET',  u:'/api/action/integrity-check',             lbl:'정합성 검사'},
    'onInventoryReport': {m:'GET',  u:'/api/q/inventory-report',                 lbl:'재고 현황 보고서'},
    'onInventoryTrend':  {m:'JS',   u:'inventory-trend-modal',                   lbl:'재고 추이 차트'},

    /* ── 보고서 메뉴 ── */
    'onReportDaily':     {m:'GET',  u:'/api/q2/report-daily',                    lbl:'일일 보고서'},
    'onReportMonthly':   {m:'GET',  u:'/api/q2/report-monthly',                  lbl:'월간 보고서'},
    'onReportCustom':    {m:'GET',  u:'/api/q/inventory-report',                   lbl:'맞춤 보고서'},
    'onInvoiceGenerate': {m:'GET',  u:'/api/action3/export-invoice-excel',         lbl:'거래명세서 생성'},
    'onDetailOfOutbound': {m:'GET', u:'/api/q2/detail-outbound',                 lbl:'Detail of Outbound'},
    'onSalesOrderDN':    {m:'JS',   u:'sales-order-dn-template',                 lbl:'Sales Order DN'},
    'onDnCrossCheck':    {m:'GET',  u:'/api/q3/dn-cross-check',                  lbl:'DN 교차검증'},
    'onLotDetailPdf':    {m:'GET',  u:'/api/action/lot-detail',                  lbl:'LOT 상세'},
    /* 재고 메뉴: FileResponse — GET+json 모달이 아니라 다운로드 (onExportLot 과 동일 계열) */
    'onLotListExcel':    {m:'JS',   u:'export-lot-excel-dl',                       lbl:'LOT 리스트 Excel'},
    'onTonbagListExcel': {m:'JS',   u:'export-tonbag-simple-dl',                  lbl:'톤백리스트 Excel'},
    'onReportExport':    {m:'GET',  u:'/api/action2/export-tonbag-excel',          lbl:'Excel 내보내기'},
    'onMovementHistory': {m:'GET',  u:'/api/q/movement-history',                  lbl:'입출고 내역'},
    'onAuditLog':        {m:'GET',  u:'/api/q/audit-log',                         lbl:'감사 로그'},

    /* ── 설정/도구 메뉴 ── */
    /* [Sprint 0] 'onSettings' removed — was wired to /api/menu/-on-settings (NotReadyError stub).
       Real settings dialog ships in Sprint 2 (SettingsDialogMixin port, ~5d). */
    'onProductMaster':   {m:'JS',   u:'product-master',                            lbl:'제품 마스터'},
    'onIntegrityRepair': {m:'JS',   u:'fix-lot-integrity',                              lbl:'LOT 정합성 복구'},
    'onOptimizeDb':      {m:'POST', u:'/api/action3/optimize-db',                 lbl:'DB 최적화'},
    'onCleanupLogs':     {m:'POST', u:'/api/action3/cleanup-logs',                lbl:'로그 정리'},
    'onDbInfo':          {m:'GET',  u:'/api/info/system-info',                    lbl:'DB 정보'},
    'onOnBackup':        {m:'POST', u:'/api/action/backup-create',                lbl:'백업 생성'},
    'onBackupList':      {m:'GET',  u:'/api/q/backup-list',                       lbl:'백업 목록'},
    'onRestore':         {m:'JS',   u:'restore',                                   lbl:'복원'},
    'onAiTools':         {m:'JS',   u:'ai-tools-hub',                              lbl:'AI 도구'},
    'onAdvancedTools':   {m:'JS',   u:'advanced-tools-hub',                      lbl:'고급 도구'},
    'onSaveWindowSize':  {m:'JS',   u:'save-window-size',                          lbl:'창 크기 저장'},
    'onResetWindowSize': {m:'JS',   u:'reset-window-size',                         lbl:'창 크기 초기화'},

    /* ── 도움말 메뉴 ── */
    'onHelp':            {m:'GET',  u:'/api/info/usage',                          lbl:'사용자 매뉴얼'},
    'onShortcuts':       {m:'GET',  u:'/api/info/shortcuts',                      lbl:'단축키'},
    'onStatusGuide':     {m:'GET',  u:'/api/info/status-guide',                   lbl:'STATUS 안내'},
    'onBackupGuide':     {m:'GET',  u:'/api/info/backup-guide',                   lbl:'백업/복구 가이드'},
    'onAbout':           {m:'GET',  u:'/api/info/version',                        lbl:'버전 정보'},

    /* ── 탭 이동 ── */

    /* ── 툴바 ── */
    /* v864.3 Phase 4-B: 툴바 PDF 입고 — 네이티브 모달 */
    'tb-pdf-inbound':    {m:'JS', u:'pdf-inbound-upload', lbl:'PDF 입고'},
    /* 툴바 '즉시 출고' 도 네이티브 폼으로 */
    'tb-quick-outbound': {m:'JS', u:'quick-outbound', lbl:'즉시 출고'},
    'tb-return':         {m:'JS',   u:'return',                                   lbl:'반품'},
    'tb-inventory':      {m:'JS',   u:'inventory',                                lbl:'재고 조회'},
    'tb-integrity':      {m:'GET',  u:'/api/action/integrity-check',              lbl:'정합성'},
    'tb-backup':         {m:'POST', u:'/api/action/backup-create',                lbl:'백업'},
    'tb-settings':       {m:'JS',   u:'font-size-settings',                       lbl:'표시·엑셀 설정'},
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
    'onFixLotIntegrity': {m:'JS',   u:'fix-lot-integrity',                        lbl:'LOT 정합성 복구'},
    'onExportCustoms':   {m:'JS',   u:'export-dl-e1',                             lbl:'통관요청 양식'},
    'onExportRubyli':    {m:'JS',   u:'export-dl-e3',                             lbl:'루비리 양식'},
    'onExportTonbag':    {m:'JS',   u:'export-dl-e4',                             lbl:'톤백 현황'},
    'onExportIntegrated': {m:'JS',  u:'export-dl-e6',                             lbl:'통합 현황'},
    'onAutoBackupSettings': {m:'JS', u:'auto-backup-settings',                    lbl:'자동 백업 설정'},
    'onReportTemplates': {m:'JS',   u:'report-templates-hub',                      lbl:'보고서 양식 관리'},
    'onReportHistory':   {m:'JS',   u:'report-history-audit',                      lbl:'보고서 이력 조회'},
    'onLotAllocationAudit': {m:'JS', u:'lot-allocation-audit',                    lbl:'LOT Allocation 톤백 현황'},
    'onDocConvert':      {m:'JS',   u:'doc-convert',                               lbl:'문서 변환 (OCR/PDF)'},
    'onTestDbReset':     {m:'JS',   u:'test-db-reset',                             lbl:'테스트 DB 초기화'},
    'onSystemInfo':      {m:'GET',  u:'/api/q3/settings-info',                    lbl:'시스템 정보'},
    'onProductSummary':  {m:'JS',   u:'product-summary',                           lbl:'품목별 재고 요약'},
    'onProductLotLookup': {m:'JS',  u:'product-lot-lookup',                        lbl:'품목별 LOT 조회'},
    'onProductMovement': {m:'JS',   u:'product-movement',                          lbl:'품목별 입출고 현황'},

    /* ── 선사 BL / Gemini: 선사는 carriers 화면으로 통합 (v864 도구 메뉴와 기능 동등) ── */
    'onBlCarrierRegister': {m:'JS', u:'carrier-profile',                           lbl:'🚢 선사 BL 등록 도구'},
    'onBlCarrierAnalyze':  {m:'JS', u:'carrier-profile',                           lbl:'🔬 선사 패턴 분석'},
    'onGeminiToggle':      {m:'JS', u:'gemini-toggle',                             lbl:'🔀 Gemini AI 사용'},
    /* 채팅 UI 미포함 시 API 설정으로 안내 (키 등록 후 사용) */
    'onAiChat':            {m:'JS', u:'gemini-api-settings',                       lbl:'💬 AI 채팅'},
    'onGeminiApiSettings': {m:'JS', u:'gemini-api-settings',                       lbl:'🔐 Gemini API 설정'},
    'onGeminiApiTest':     {m:'JS', u:'gemini-api-test',                           lbl:'🧪 Gemini API 테스트'},

    /* ── 재고 메뉴: LOT Excel은 FileResponse → 새 창 다운로드 / 추이는 JSON 모달 ── */
    'onExportLot':         {m:'JS', u:'export-lot-excel-dl',                       lbl:'📊 LOT 리스트 Excel'},
    'onStockTrendChart':   {m:'JS',  u:'inventory-trend-modal',                    lbl:'📊 재고 추이 차트'},

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
    'onSwapReport':        {m:'JS',  u:'swap-report-modal',                        lbl:'Swap 리포트'},
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
      if (conf.u === 'batch-move-approval') {
        showBatchMoveApprovalModal();
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
      if (conf.u === 'gemini-api-settings') { showGeminiApiSettingsModal(); return; }
      if (conf.u === 'gemini-api-test') { showGeminiApiTestModal(); return; }
      if (conf.u === 'gemini-toggle') { window._geminiToggleAction(); return; }
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
      if (conf.u === 'return-statistics-modal') {
        showReturnStatisticsModal();
        return;
      }
      if (conf.u === 'advanced-tools-hub') {
        showAdvancedToolsHubModal();
        return;
      }
      if (conf.u === 'export-dl-e1') {
        sqmDownloadFileUrl(API + '/api/action/export-engine-excel?option=1', conf.lbl);
        return;
      }
      if (conf.u === 'export-dl-e3') {
        sqmDownloadFileUrl(API + '/api/action/export-engine-excel?option=3', conf.lbl);
        return;
      }
      if (conf.u === 'export-dl-e4') {
        var incSample = window.confirm('톤백리스트(Sub LOT): 샘플 톤백을 포함할까요?\n\n[확인] 포함 · [취소] 제외');
        sqmDownloadFileUrl(
          API + '/api/action/export-engine-excel?option=4&include_sample=' + (incSample ? 'true' : 'false'),
          conf.lbl
        );
        return;
      }
      if (conf.u === 'export-dl-e6') {
        sqmDownloadFileUrl(API + '/api/action/export-engine-excel?option=6', conf.lbl);
        return;
      }
      if (conf.u === 'export-tonbag-simple-dl') {
        showToast('info', '⏳ 톤백리스트 Excel 생성 중...');
        apiCall('GET', '/api/action2/open-tonbag-excel')
          .then(function(res) {
            if (res && res.data && res.data.opened) {
              showToast('success', '✅ 톤백리스트 열림 (' + res.data.rows + '행)\n📁 ' + res.data.filename);
            } else {
              showToast('error', '❌ 파일 열기 실패');
            }
          })
          .catch(function(e) { showToast('error', '❌ 오류: ' + e); });
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
      if (conf.u === 'sales-order-dn-template') {
        showSalesOrderDnTemplateModal();
        return;
      }
      if (conf.u === 'carrier-profile') {
        showCarrierProfileModal();
        return;
      }
      if (conf.u === 'export-lot-excel-dl') {
        showToast('info', '⏳ LOT 리스트 Excel 생성 중...');
        apiCall('GET', '/api/action/open-lot-excel')
          .then(function(res) {
            if (res && res.data && res.data.opened) {
              showToast('success', '✅ LOT 리스트 열림 (' + res.data.rows + ' LOT)\n📁 ' + res.data.filename);
            } else {
              showToast('error', '❌ 파일 열기 실패');
            }
          })
          .catch(function(e) { showToast('error', '❌ 오류: ' + e); });
        return;
      }
      if (conf.u === 'fix-lot-integrity') {
        showFixLotIntegrityModal();
        return;
      }
      if (conf.u === 'swap-report-modal') {
        showSwapReportModal();
        return;
      }
      if (conf.u === 'inventory-trend-modal') {
        showInventoryTrendModal();
        return;
      }
      if (conf.u === 'product-master') {
        showProductMasterModal();
        return;
      }
      if (conf.u === 'ai-tools-hub') {
        showAiToolsHubModal();
        return;
      }
      if (conf.u === 'report-templates-hub') {
        showReportTemplatesHubModal();
        return;
      }
      if (conf.u === 'report-history-audit') {
        showReportHistoryAuditModal();
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
        closeAllMenus();
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
        if (ev.target.closest('[data-action]')) {
          dbgLog('⚡','MENU → action', ev.target.dataset.action, '#ffeb3b');
          return;
        }
        if (ev.target.closest('.submenu-parent')) {
          ev.preventDefault();
          ev.stopPropagation();
          return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        var open = el.classList.contains('open');
        closeAllMenus();
        if (!open) {
          el.classList.add('open');
          _menuJustOpened = true;
          setTimeout(function(){ _menuJustOpened = false; }, 200);
          console.log('[SQM MENU OPEN]', menuName, '| .open class added:', el.classList.contains('open'));
          dbgLog('📂','MENU OPEN', menuName + ' | .open 추가됨', '#4caf50');
        } else {
          console.log('[SQM MENU CLOSE]', menuName);
          dbgLog('📁','MENU CLOSE', menuName, '#ff9800');
        }
      });
    });

    // click-lock nested submenu. Hover still works through CSS, but click keeps it open
    // while the pointer moves across the submenu gap.
    document.querySelectorAll('.submenu-parent > .submenu-parent-btn').forEach(function(btn){
      if (btn.dataset._sqmSubmenuBound) return;
      btn.dataset._sqmSubmenuBound = '1';
      btn.addEventListener('click', function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        var parent = btn.closest('.submenu-parent');
        var dropdown = parent ? parent.querySelector('.submenu-dropdown') : null;
        if (!parent || !dropdown) return;
        var open = parent.classList.contains('open');
        if (open) {
          parent.classList.remove('open');
          parent.classList.remove('hover-active');
          dropdown.style.display = '';
        } else {
          activateSubmenuParent(parent, true);
        }
      });
    });

    // Keep submenu highlight tied to the item under the pointer/focus, not the
    // previously clicked submenu button.
    document.querySelectorAll('.submenu-parent').forEach(function(parent){
      if (parent.dataset._sqmSubmenuHoverBound) return;
      parent.dataset._sqmSubmenuHoverBound = '1';
      parent.addEventListener('mouseenter', function(){
        activateSubmenuParent(parent, false);
      });
      parent.addEventListener('focusin', function(){
        activateSubmenuParent(parent, false);
      });
    });

    // close on outside click
    document.addEventListener('click', function(ev){
      if (_menuJustOpened) {
        console.log('[SQM] document click 차단됨 (_menuJustOpened=true)');
        return;
      }
      if (!ev.target.closest('.menu-btn,.menu-dropdown')) {
        console.log('[SQM] outside click → closeAllMenus');
        closeAllMenus();
      }
    });

    // theme buttons
    document.querySelectorAll('[data-action="theme-dark"]').forEach(function(el){
      el.addEventListener('click',function(){
        document.documentElement.setAttribute('data-theme','dark');
        if (document.body) document.body.setAttribute('data-theme','dark');
        try{getStore().setItem('sqm_theme','dark');}catch{}
      });
    });
    document.querySelectorAll('[data-action="theme-light"]').forEach(function(el){
      el.addEventListener('click',function(){
        document.documentElement.setAttribute('data-theme','light');
        if (document.body) document.body.setAttribute('data-theme','light');
        try{getStore().setItem('sqm_theme','light');}catch{}
      });
    });

    // F5 shortcut — F8: debug panel toggle (handled in _dbgBuild)
    document.addEventListener('keydown', function(ev){
      if (ev.key === 'Escape') {
        closeAllMenus();
        return;
      }
      if (ev.key==='F5'&&!ev.ctrlKey&&!ev.metaKey){
        ev.preventDefault();
        renderPage(_currentRoute||'dashboard');
      }
    });

    console.info('[SQM v864.3] bindAll complete');
  }

  function boot() {
    _dbgBuild();
    applyTheme();
    applyStoredFontScale();
    bindAll();
    loadAlerts();
    loadStatusbar();
    startKpiPolling();
    dbgLog('🚀','SQM v864.3 부팅 완료', 'F8 = 디버그 패널 토글','#4caf50');

    var hash = location.hash.slice(1);
    var lastTab = null;
    try { lastTab = getStore().getItem('sqm_last_tab'); } catch {}
    var initial = hash || lastTab || 'dashboard';
    renderPage(initial);

    window.addEventListener('hashchange', function(){
      var id = location.hash.slice(1);
      if (id && id !== _currentRoute) renderPage(id);
    });

    setInterval(function(){
      var auto = document.getElementById('sb-auto-refresh');
      if (auto && auto.checked && document.visibilityState !== 'hidden') {
        loadAlerts();
        refreshStatusbar();
        if (_currentRoute==='dashboard') loadKpi();
      }
    }, 30000);

    window.SQM = window.SQM || {};
    window.SQM.version = '864.3-phase5';
    window.SQM.renderPage = renderPage;
    window.SQM.dispatchAction = dispatchAction;
    window.SQM.currentRoute = function(){ return _currentRoute; };
    console.info('[SQM v864.3] boot complete. initial route:', initial);
  }

  /* sqm-onestop-inbound.js 의존성 전역 노출 */
  window.escapeHtml = escapeHtml;
  window.showDataModal = showDataModal;
  window._makeDraggableResizable = _makeDraggableResizable;
  window.loadInventoryPage = loadInventoryPage;
  window.loadKpi = loadKpi;
  window.API = API;
  Object.defineProperty(window, '_currentRoute', {
    get: function() { return window.SQM && window.SQM.currentRoute ? window.SQM.currentRoute() : ''; },
    configurable: true
  });

  if (document.readyState==='loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

})();
