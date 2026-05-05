/* =======================================================================
   SQM Inventory v8.6.6 - sqm-core.js
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
      case 'C-2': e.preventDefault(); renderPage('available'); break;
      case 'C-3': e.preventDefault(); renderPage('allocation'); break;
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
  window._menuJustOpened = false;  // PyWebView/WebView2: cross-IIFE 공유 플래그

  function closeAllMenus() {
    // Fix: HTML uses .menu-btn[data-menu], not .menu-item — add both for safety
    document.querySelectorAll('.menu-btn.open').forEach(function(el){
      el.classList.remove('open');
    });
    document.querySelectorAll('.submenu-parent.open').forEach(function(el){
      el.classList.remove('open');
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
    menu.querySelectorAll('.submenu-parent.open').forEach(function(el){
      if (el !== parent) el.classList.remove('open');
    });
    menu.querySelectorAll('.submenu-dropdown').forEach(function(el){
      if (!parent.contains(el)) el.style.display = '';
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
      el.classList.remove('active-parent');
    });
    // 자식 라우트 선택 시 부모(Inventory) 버튼 강조
    var _childRoutes = {'available':'inventory','allocation':'inventory','picked':'inventory','return':'inventory'};
    var _parent = _childRoutes[route];
    if (_parent) {
      document.querySelectorAll('[data-route="' + _parent + '"]').forEach(function(el){
        el.classList.add('active-parent');
      });
    }
  }

  function renderPage(route) {
    _currentRoute = route;
    closeAllMenus();
    showPage(route);
    try { getStore().setItem('sqm_last_tab', route); } catch {}
    if (history.replaceState) history.replaceState(null,'','#' + route);
    switch (route) {
      case 'dashboard':  loadDashboard();     break;
      case 'inventory':  window.loadInventoryPage();  break;
      case 'available':  window.loadAvailablePage();  break;  // v9.5 신규
      case 'allocation': window.loadAllocationPage(); break;
      case 'picked':     window.loadPickedPage();     break;
      case 'inbound':    window.loadInboundPage();    break;
      case 'outbound':   window.loadOutboundPage();   break;
      case 'return':     window.loadReturnPage();     break;
      case 'move':       window.loadMovePage();       break;
      case 'log':        window.loadLogPage();        break;
      case 'scan':       window.loadScanPage();       break;
      case 'tonbag':     window.loadTonbagPage();     break;
      default:           loadStubPage(route);  break;
    }
  }

  function loadStubPage(route) {
    var c = document.getElementById('page-container');
    if (c) c.innerHTML = '<div class="empty" style="padding:60px;text-align:center;color:var(--text-muted)">Preparing: ' + escapeHtml(route) + '</div>';
  }

  window.renderPage = renderPage;

  window.closeAllMenus   = closeAllMenus;
  window.getStore        = getStore;
  window.escapeHtml        = escapeHtml;
  window.getCurrentRoute   = function() { return _currentRoute; };
  window.dbgLog            = dbgLog;
  window._dbgBuild              = _dbgBuild;
  window.applyTheme             = applyTheme;
  window.startKpiPolling        = startKpiPolling;
  window.loadKpi                = loadKpi;
  window.extractRows            = extractRows;
  window.fmtN                   = fmtN;
  window.toggleTheme            = toggleTheme;
  window.closeSiblingSubmenus   = closeSiblingSubmenus;
  window.sqmDownloadFileUrl     = sqmDownloadFileUrl;
  window.sqmShouldOpenXlsxAfterSave = sqmShouldOpenXlsxAfterSave;
  window.API                        = API;

  /* ===================================================
     6. DASHBOARD
     =================================================== */
  var _kpiTimer = null;

  function loadDashboard() {
    renderStatusCards({});   /* dash-matrix-area / dash-integrity-area 컨테이너 생성 */
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
      sv('kpi-inbound-val',        d.today_inbound_mt    !== undefined ? d.today_inbound_mt    : (d.inbound_today   || d.inbound   || '-'));
      sv('kpi-outbound-today-val', d.today_outbound_mt   !== undefined ? d.today_outbound_mt   : (d.outbound_today  || d.outbound  || '-'));
      sv('kpi-stock-lots-val',     d.current_stock_lots  !== undefined ? d.current_stock_lots  : (d.stock_lots      || d.lots      || '-'));
      sv('kpi-unassigned-val',     d.unassigned_locations !== undefined ? d.unassigned_locations : (d.unassigned_bags || d.unassigned|| '-'));
    }).catch(function(){});
  }

  function startKpiPolling() {
    if (_kpiTimer) clearInterval(_kpiTimer);
    _kpiTimer = setInterval(function(){
      if (_currentRoute === 'dashboard' && document.visibilityState !== 'hidden') loadKpi();
    }, 5000);
    // v9.5: 사이드바 배지 초기 로드 + 30초 갱신
    loadSidebarBadges();
    _sidebarBadgeTimer = setInterval(function(){
      if (document.visibilityState !== 'hidden') loadSidebarBadges();
    }, 30000);
  }

  /* v9.5: 사이드바 배지 (개수·MT) 주기적 갱신 */
  var _sidebarBadgeTimer = null;
  function loadSidebarBadges() {
    // submenu 배지(개수·MT)는 표시 안 함 — 사장님 지시 2026-05-05
    // 상단 Inventory 총계 배지만 유지
    apiGet('/api/dashboard/sidebar-counts').then(function(res){
      var d = (res && res.data) ? res.data : {};
      // 서브메뉴 배지 숨김 처리
      ['badge-available','badge-allocation','badge-picked','badge-return'].forEach(function(id){
        var el = document.getElementById(id);
        if (el) el.textContent = '';
      });
      // 상단 Inventory 버튼 총계는 유지
      var tot = document.getElementById('badge-inv-total');
      if (tot && d.total) tot.textContent = d.total.bags + '개 · ' + d.total.mt.toFixed(1) + 'MT';
    }).catch(function(){});
  }

  /* ── 공용 컨텍스트 드롭다운 엔진 (모든 탭 공유) ────────────────── */
  var _ctxMenuEl = null;
  function _closeCtxMenu() {
    if (_ctxMenuEl) { _ctxMenuEl.remove(); _ctxMenuEl = null; }
  }
  document.addEventListener('click', function(e) {
    if (_ctxMenuEl && !_ctxMenuEl.contains(e.target)) _closeCtxMenu();
  });
  window._openContextMenu = function(btn, items) {
    _closeCtxMenu();
    var rect = btn.getBoundingClientRect();
    var menu = document.createElement('div');
    menu.style.cssText = [
      'position:fixed','z-index:9999',
      'background:var(--panel)',
      'border:1px solid var(--panel-border)',
      'border-radius:8px',
      'box-shadow:0 4px 20px rgba(0,0,0,0.45)',
      'min-width:200px','padding:5px 0','font-size:13px'
    ].join(';');
    var spaceBelow = window.innerHeight - rect.bottom;
    if (spaceBelow < 250) {
      menu.style.bottom = (window.innerHeight - rect.top + 4) + 'px';
    } else {
      menu.style.top = (rect.bottom + 4) + 'px';
    }
    menu.style.left = Math.max(4, rect.left - 130) + 'px';
    items.forEach(function(item) {
      if (item === '-') {
        var sep = document.createElement('div');
        sep.style.cssText = 'border-top:1px solid var(--panel-border);margin:3px 0';
        menu.appendChild(sep); return;
      }
      var li = document.createElement('button');
      li.style.cssText = 'display:flex;align-items:center;gap:10px;width:100%;padding:7px 14px;'
        + 'background:none;border:none;cursor:pointer;color:'+(item.color||'var(--fg)')
        + ';text-align:left;font-size:13px;white-space:nowrap';
      li.innerHTML = '<span style="font-size:15px;width:20px;text-align:center">'
        + item.icon+'</span>'
        + '<span style="flex:1">' + item.label + '</span>'
        + (item.kbd ? '<span style="font-size:10px;color:var(--text-muted);margin-left:8px;'
          + 'background:rgba(128,128,128,0.15);padding:1px 5px;border-radius:3px">'
          + item.kbd + '</span>' : '');
      li.onmouseenter=function(){this.style.background='rgba(255,255,255,0.07)';};
      li.onmouseleave=function(){this.style.background='none';};
      li.onclick=function(e){e.stopPropagation();_closeCtxMenu();item.fn&&item.fn();};
      menu.appendChild(li);
    });
    _ctxMenuEl = menu;
    document.body.appendChild(menu);
  };
  window._closeCtxMenu = _closeCtxMenu;

  window.loadSidebarBadges = loadSidebarBadges;

  function loadDashboardTables() {
    apiGet('/api/dashboard/stats').then(function(res){
      var d = res.data || res || {};
      renderStockWeightSummary(d);                                   // v9.4: 상태별 무게 요약
      renderProductMatrix(d.product_matrix || []);
      renderIntegrity(d.integrity || {}, d.lot_weight_summary || {});
    }).catch(function(){
      renderStockWeightSummary({});
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

  /* 5단계 KPI 카드 제거 — 컨테이너만 초기화 */
  function renderStatusCards(summary) {
    var el = document.getElementById('dashboard-detail');
    if (!el) return;
    el.innerHTML = '<div id="dash-weight-summary"></div><div id="dash-matrix-area"></div><div id="dash-integrity-area"></div>';
  }

  /* v9.4: AVAILABLE / RESERVED / PICKED / TOTAL 무게 요약 바 */
  function renderStockWeightSummary(d) {
    var el = document.getElementById('dash-weight-summary');
    if (!el) return;

    // 우선순위: 직접 필드(v9.4) > status_summary 합산
    var ss = d.status_summary || {};
    var avail_mt   = typeof d.available_mt === 'number' ? d.available_mt
                   : ((ss.available || {}).weight_kg || 0) / 1000;
    var resv_mt    = typeof d.reserved_mt === 'number' ? d.reserved_mt
                   : ((ss.reserved || {}).weight_kg || 0) / 1000;
    var picked_mt  = typeof d.picked_mt === 'number' ? d.picked_mt
                   : ((ss.picked || {}).weight_kg || 0) / 1000;
    var total_mt   = avail_mt + resv_mt + picked_mt;

    function bar(label, color, icon, mt, pct) {
      var w = total_mt > 0 ? Math.max(2, Math.round(pct)) : 0;
      return '<div style="margin-bottom:6px">'
           + '<div style="display:flex;align-items:center;gap:8px;margin-bottom:2px">'
           + '<span style="font-size:13px">' + icon + '</span>'
           + '<span style="color:' + color + ';font-weight:700;font-size:13px;min-width:160px">' + label + '</span>'
           + '<span style="color:var(--text-primary,#e0e0e0);font-size:14px;font-weight:700">' + mt.toFixed(3) + ' MT</span>'
           + '<span style="color:var(--text-muted,#888);font-size:12px;margin-left:4px">(' + pct.toFixed(1) + '%)</span>'
           + '</div>'
           + '<div style="height:8px;background:var(--bg-card,#1a1a2e);border-radius:4px;overflow:hidden">'
           + '<div style="width:' + w + '%;height:100%;background:' + color + ';border-radius:4px;transition:width 0.4s"></div>'
           + '</div></div>';
    }

    var avail_pct  = total_mt > 0 ? (avail_mt  / total_mt * 100) : 0;
    var resv_pct   = total_mt > 0 ? (resv_mt   / total_mt * 100) : 0;
    var picked_pct = total_mt > 0 ? (picked_mt / total_mt * 100) : 0;

    var html = '<div style="background:var(--bg-card,#1e1e2e);border-radius:10px;padding:14px 18px;margin-bottom:16px">'
             + '<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:12px">'
             + '<h3 style="margin:0;font-size:15px;color:var(--text-primary,#e0e0e0)">&#x1F4CA; 재고 현황 (톤백 기준)</h3>'
             + '<span style="font-size:13px;color:var(--text-muted,#888)">TOTAL: <b style="color:#e0e0e0">' + total_mt.toFixed(3) + ' MT</b></span>'
             + '</div>';
    html += bar('Available (판매가능)', '#22c55e', '\u2705', avail_mt, avail_pct);
    html += bar('Reserved  (배분확정)', '#3b82f6', '\uD83D\uDCCB', resv_mt, resv_pct);
    html += bar('Picked    (피킹완료)', '#f59e0b', '\uD83D\uDCE6', picked_mt, picked_pct);
    html += '<div style="margin-top:10px;padding-top:8px;border-top:1px solid var(--border-color,#333);font-size:11px;color:var(--text-muted,#888)">'
          + 'TOTAL = Available + Reserved + Picked | 출고완료(Outbound)는 별도 집계</div>';
    html += '</div>';
    el.innerHTML = html;
  }

  /* -- 제품x상태 매트릭스 테이블 (제품별 단일 행 — 샘플 괄호 병기) -- */
  /* ── 제품×상태 테이블 — 제품당 2행 (일반 톤백 + 샘플) ── */
  function renderProductMatrix(rows) {
    var el = document.getElementById('dash-matrix-area');
    if (!el) return;
    if (!rows.length) {
      el.innerHTML = '<p style="color:var(--text-muted,#888);font-size:13px;padding:12px">제품별 데이터 없음</p>';
      return;
    }

    /* 제품별 그룹핑 */
    var productMap = {};
    rows.forEach(function(r) {
      var prod = r.product;
      if (!productMap[prod]) productMap[prod] = { normal: null, sample: null };
      if (r.is_sample) productMap[prod].sample = r;
      else             productMap[prod].normal = r;
    });

    /* 셀 헬퍼 */
    function cv(val, isWt) {
      var v = val || 0;
      return '<td style="text-align:right;padding:5px 8px">' + (isWt ? v.toFixed(3) : String(v)) + '</td>';
    }
    function cvLot(lotCnt, total) {
      var nl = lotCnt || 0; var nt = total || 0;
      return '<td style="text-align:right;padding:5px 8px">'
           + '<span style="color:#94a3b8;font-size:11px">' + nl + ' LOT</span>'
           + '<span style="font-weight:700;margin-left:4px">· ' + nt + '</span></td>';
    }

    var TH  = 'style="padding:6px 8px;text-align:right;background:var(--bg-header,#2a2a3e)"';
    var THL = 'style="text-align:left;padding:6px 10px;background:var(--bg-header,#2a2a3e)"';

    var html = '<div style="overflow-x:auto"><table class="sqm-table" style="width:100%;font-size:13px;border-collapse:collapse">';
    html += '<thead><tr>';
    html += '<th ' + THL + '>제품</th>';
    html += '<th ' + TH + ' style="color:#22c55e">Available</th>';
    html += '<th ' + TH + ' style="color:#3b82f6">Reserved</th>';
    html += '<th ' + TH + ' style="color:#f59e0b">Picked</th>';
    html += '<th ' + TH + ' style="color:#ef4444">Outbound</th>';
    html += '<th ' + TH + ' style="color:#8b5cf6">Return</th>';
    html += '<th ' + TH + '>톤백(개)</th>';
    html += '<th ' + TH + '>중량(MT)</th>';
    html += '</tr></thead><tbody>';

    var products = Object.keys(productMap).sort();
    products.forEach(function(prod, idx) {
      var g  = productMap[prod];
      var n  = g.normal || {};
      var s  = g.sample || {};
      var borderTop = idx > 0 ? 'border-top:2px solid var(--border-color,#3a3a5e);' : '';

      /* 1행: 일반 톤백 */
      html += '<tr style="' + borderTop + '">';
      html += '<td style="text-align:left;padding:6px 10px;font-weight:700">' + escapeHtml(prod) + '</td>';
      html += cv(n.available,  false);
      html += cv(n.reserved,   false);
      html += cv(n.picked,     false);
      html += cv(n.outbound,   false);
      html += cv(n['return'],  false);
      html += cvLot(n.lot_count, n.total);
      html += cv(n.weight_mt,  true);
      html += '</tr>';

      /* 2행: 샘플 (항상 표시 — 데이터 없으면 0) */
      html += '<tr style="background:rgba(234,179,8,0.07)">';
      html += '<td style="text-align:left;padding:4px 10px 4px 22px;color:#eab308;font-size:12px">🔬 샘플</td>';
      html += cv(s.available,  false);
      html += cv(s.reserved,   false);
      html += cv(s.picked,     false);
      html += cv(s.outbound,   false);
      html += cv(s['return'],  false);
      html += '<td style="text-align:right;padding:5px 8px">' + (s.total || 0) + '</td>';
      html += cv(s.weight_mt,  true);
      html += '</tr>';
    });

    html += '</tbody></table></div>';
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

})();
