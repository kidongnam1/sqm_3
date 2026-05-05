/* =======================================================================
   sqm-onestop-inbound.js  (v20260429)
   OneStop Inbound — 4-slot wizard modal + parse engine
   Extracted from sqm-inline.js lines 3811–5008 by extract_onestop.py
   Dependencies (provided by sqm-inline.js):
     showToast, escapeHtml, apiPost, apiGet,
     _makeDraggableResizable, _bringToFront, showDataModal,
     loadInventoryPage, loadKpi, _currentRoute, API
   ======================================================================= */
(function () {
  'use strict';
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

  /* ── 제품 마스터 캐시 (product 셀 드롭다운용) ── */
  window._pmCache = [];
  window.loadPmCache = function() {
    return fetch(API + '/api/product-master/list')
      .then(function(r){ return r.json(); })
      .then(function(res){
        var items = (res.data && res.data.items) || [];
        window._pmCache = items.filter(function(i){ return i.is_active !== 0; });
      })
      .catch(function(e){ console.warn('PM cache load failed:', e); });
  };
  /* 최초 1회 로드 */
  window.loadPmCache();

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
      + '<table class="data-table onestop-preview-table" style="min-width:1200px">'
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
      /* 템플릿 줄 — Sprint 2 예정 행 제거, D/O 나중에 버튼은 액션 바로 이동 */
      /* 선사 줄 */
      '  <div class="onestop-row">',
      '    <label>🚢 선사:</label>',
      '    <select id="onestop-carrier" onchange="window.onestopCarrierChange(this.value)" style="padding:6px;flex:1;max-width:280px;background:var(--bg-hover);color:var(--fg);border:1px solid var(--border);border-radius:6px;font-weight:600"><option value="">— 로딩 중... —</option></select>',
      '    <button class="btn" onclick="window.onestopReparseCarrier()" disabled>🚢 선사 재파싱</button>',
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
      /* 템플릿 상태 행 — _onestopActiveTemplate 미사용으로 숨김 */
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
      '    <button class="btn" onclick="window.onestopSkipDo()">📋 D/O 나중에</button>',
      '    <button class="btn btn-primary" id="onestop-parse-btn" onclick="window.onestopParseStart()" disabled>▶ 파싱 시작</button>',
      '    <button class="btn" id="onestop-reparse-btn" onclick="window.onestopParseRedo()" disabled>↻ 다시 파싱</button>',
      '    <label id="onestop-gemini-label" style="display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--text-muted);cursor:pointer;margin-left:4px" title="좌표 파싱과 Gemini AI 파싱을 동시에 실행하여 결과를 비교합니다">'
        + '<input type="checkbox" id="onestop-gemini-check" style="cursor:pointer"> 🤖 Gemini 비교</label>',
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
      + (list.length ? '<table class="data-table" style="width:100%;border-collapse:collapse;margin-bottom:12px"><tbody>' + rows + '</tbody></table>' : '<p style="color:var(--text-muted);margin-bottom:12px">등록된 템플릿이 없습니다.</p>')
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
    if (!_cEl || !_cEl.value) { showToast('error', '🚢 선사를 먼저 선택하세요 (필수)'); return; }
    if (window._onestopBagWeight === null) { showToast('error', '🏋️ DB 파싱 템플릿을 먼저 선택하세요 (톤백 단위 미설정 시 500kg로 오파싱 위험)'); return; }
    if (!s.PACKING_LIST) { showToast('error', 'Packing List(PL) 먼저 선택하세요'); return; }

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
    var _geminiCheck = document.getElementById('onestop-gemini-check');
    form.append('use_gemini', (_geminiCheck && _geminiCheck.checked) ? 'true' : 'false');

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

        var wRoll = d.weight_rollups || {};
        var plDet = d.pl_detail || {};
        var wLine = '';
        if (wRoll.preview_rows_net_sum_kg != null) {
          wLine = '<div style="font-size:12px;margin-top:8px;padding:8px 10px;background:var(--panel);border:1px solid var(--panel-border);border-radius:6px;color:var(--text-primary)">' +
            '<b>순중량(kg) 합계</b> · PL 행 합: <b>' + Number(wRoll.preview_rows_net_sum_kg).toLocaleString('ko-KR') + ' kg</b>';
          if (plDet.total_net_kg != null && plDet.total_net_kg !== '') {
            wLine += ' · PL 헤더 총순중량: <b>' + Number(plDet.total_net_kg).toLocaleString('ko-KR') + ' kg</b>';
          }
          if (wRoll.header_minus_rows_kg != null) {
            wLine += ' · 헤더−행차이: <b style="color:#f59e0b">' + Number(wRoll.header_minus_rows_kg).toLocaleString('ko-KR') + ' kg</b>';
          }
          wLine += '<br><span style="font-size:11px;color:var(--text-muted)">엑셀 LOT 목록 «순중량» 합은 보통 PL 행 합과 같습니다. «현재중량» 합은 샘플(톤백 1kg) 제외로 더 작게 보일 수 있습니다.</span></div>';
        }
        if (pb) pb.innerHTML =
          '<div style="color:var(--success);font-weight:700">✅ ' + escapeHtml(body.message || '파싱 완료') + ' <span style="font-size:11px;color:var(--text-muted);font-weight:400">(미리보기 단계 — DB 저장 전)</span></div>' +
          '<div style="color:var(--text-muted);font-size:12px;margin-top:6px">📑 서류: ' + docsBadges + '</div>' +
          wLine +
          '<div style="color:' + xcColor + ';font-size:13px;font-weight:600;margin-top:6px">' + xcIcon + ' ' + escapeHtml(xc.summary || '') + '</div>' +
          xcItemsHtml +
          (xc.has_critical ? '<div style="color:var(--danger);font-size:11px;margin-top:6px;font-weight:600">🚫 심각 불일치 감지 — 파일 확인 후 다시 파싱 권장</div>' : '') +
          '<div style="color:var(--info, #42a5f5);font-size:11px;margin-top:8px">💡 셀 더블클릭으로 편집 가능 · 완료 후 하단 "📤 DB 업로드" 버튼 클릭</div>';

        /* 18열 미리보기 테이블 채우기 + 편집 상태 초기화 */
        var rows = d.preview_rows || [];
        /* compare_mode: show side-by-side, let user pick */
        var _showCompareAfterPreview = false;
        if (d.compare_mode && d.coord_rows && d.gemini_rows) {
          _onestopState.previewRows = d.coord_rows.slice();
          _onestopState.originalRows = JSON.parse(JSON.stringify(d.coord_rows));
          _onestopState.editedCells = {};
          _onestopState.parsed = d.coord_rows.length > 0;
          _showCompareAfterPreview = true;
        } else {
          _onestopState.previewRows = rows.slice();  /* 편집 대상 */
          _onestopState.originalRows = JSON.parse(JSON.stringify(rows));  /* deep copy */
          _onestopState.editedCells = {};
          _onestopState.parsed = rows.length > 0;
        }
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
        /* v8.6.5 fix: open window FIRST so onestop-preview-body exists in DOM */
        var _cEl2 = document.getElementById('onestop-carrier');
        _openParseResultWindow(_cEl2 ? _cEl2.value : '', rows.length);
        _onestopRenderPreview(_onestopState.previewRows);
        if (_showCompareAfterPreview) {
          _showGeminiComparePanel(d.coord_rows, d.gemini_rows);
        }
        _onestopUpdateHistoryButtons();

        _onestopSetStep(3);
        _addParseLog('\u2705', '\ud30c\uc2f1 \uc644\ub8cc — LOT ' + rows.length + '\uac74', 'var(--success,#4caf50)');

        /* ── DO arrival_date 자동채움 + 충돌 처리 (v865) ─────────────────────────────
         * 규칙: 비어있으면 조용히 채움 / 값이 있고 다르면 사용자 선택 토스트 표시
         * ──────────────────────────────────────────────────────────────────────── */
        if (docs.do_loaded && rows.length > 0) {
          var _parsedArr = ((rows[0] || {}).arrival || '').slice(0, 10);
          if (_parsedArr) {
            var _arrFld = document.getElementById('onestop-arrival-input');
            if (_arrFld) {
              var _manArr = (_arrFld.value || '').trim();
              if (!_manArr) {
                /* Case A: 빈 칸 → 조용히 자동 채움 */
                _arrFld.value = _parsedArr;
                window.onestopCalcFreeTime();
                _addParseLog('\ud83d\udcc5', 'ARRIVAL 자동채움: ' + _parsedArr, 'var(--info,#42a5f5)');
              } else if (_manArr !== _parsedArr) {
                /* Case C: 충돌 → 사용자 선택 토스트 (15초 자동소멸) */
                (function(_manual, _parsed, _el) {
                  var _t = document.createElement('div');
                  _t.id = '_arrival-conflict-toast';
                  _t.style.cssText = [
                    'position:fixed;bottom:80px;right:20px;z-index:99999',
                    'background:#2a1a0a;border:1px solid #e8a07e;border-radius:8px',
                    'padding:14px 18px;max-width:320px;box-shadow:0 4px 20px #0009',
                    'font-size:12px;color:#ddd;line-height:1.5'
                  ].join(';');
                  _t.innerHTML =
                    '<div style="font-weight:700;color:#e8c87e;margin-bottom:8px;font-size:13px">&#9888;&#65039; ARRIVAL 날짜 충돌</div>' +
                    '<table class="data-table" style="width:100%;border-collapse:collapse;font-size:11px">' +
                    '<tr><td style="color:#aaa;padding:2px 6px 2px 0">수동 입력</td>' +
                    '<td style="color:#e87e7e;font-weight:700">' + _manual + '</td></tr>' +
                    '<tr><td style="color:#aaa;padding:2px 6px 2px 0">DO 파싱결과</td>' +
                    '<td style="color:#7ec87e;font-weight:700">' + _parsed + '</td></tr>' +
                    '</table>' +
                    '<div style="display:flex;gap:8px;margin-top:10px">' +
                    '<button id="_arr-apply" style="flex:1;padding:6px 4px;background:#1a3a1a;color:#7ec87e;' +
                    'border:1px solid #7ec87e;border-radius:4px;cursor:pointer;font-size:11px;font-weight:600">&#9989; 파싱값 적용</button>' +
                    '<button id="_arr-keep" style="flex:1;padding:6px 4px;background:#1a1a2e;color:#aaa;' +
                    'border:1px solid #555;border-radius:4px;cursor:pointer;font-size:11px">&#128274; 수동값 유지</button>' +
                    '</div>' +
                    '<div style="color:#555;font-size:10px;margin-top:6px;text-align:right">15초 후 자동 닫힘</div>';
                  document.body.appendChild(_t);
                  function _closeT() { if (document.body.contains(_t)) document.body.removeChild(_t); }
                  document.getElementById('_arr-apply').onclick = function() {
                    _el.value = _parsed;
                    window.onestopCalcFreeTime();
                    _addParseLog('\ud83d\udcc5', 'ARRIVAL \u2192 DO \ud30c\uc2f1\uac12 \uc801\uc6a9: ' + _parsed, 'var(--success,#4caf50)');
                    _closeT();
                  };
                  document.getElementById('_arr-keep').onclick = function() {
                    _addParseLog('\ud83d\udcc5', 'ARRIVAL \u2192 \uc218\ub3d9\uac12 \uc720\uc9c0: ' + _manual, 'var(--warning,#ff9800)');
                    _closeT();
                  };
                  setTimeout(_closeT, 15000);
                })(_manArr, _parsedArr, _arrFld);
              }
              /* Case B: 값 동일 → 아무것도 안 함 */
            }
          }
        }
        /* ── end arrival 충돌 처리 ─────────────────────────────────────── */

        if (rows.length > 0) {
          var saveBtn = document.getElementById('onestop-save-btn');
          if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '📤 DB 업로드 (' + rows.length + '건)'; }
        }
        showToast('success', '파싱 완료: ' + rows.length + ' LOT (미리보기)');
        /* 파싱만 한 경우(dry_run): 재고/대시보드는 DB 업로드 전까지 변하지 않음 */
        if (d.dry_run !== false) {
          showToast('warn',
            '⚠️ 아직 데이터베이스에 저장되지 않았습니다. 재고·대시보드에 반영하려면 미리보기 창 하단 「📤 DB 업로드」를 눌러 주세요.');
        }
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

    /* ── product 필드: 제품 마스터 드롭다운 ── */
    if (field === 'product') {
      var pm = window._pmCache || [];
      var sel = document.createElement('select');
      sel.className = 'onestop-edit-input';
      sel.style.cssText = 'width:100%;padding:2px 4px;background:var(--bg);color:var(--fg);border:1px solid var(--accent);border-radius:3px;font-size:11px;font-family:inherit';
      /* 첫 옵션: 현재 값 또는 빈값 */
      var opts = '<option value="">(제품 선택)</option>';
      pm.forEach(function(p) {
        var code   = p.code || '';
        var fn     = p.full_name || p.product_name || '';
        var kr     = p.korean_name || '';
        var label  = code ? (code + ' — ' + fn + (kr ? ' / ' + kr : '')) : fn;
        var val    = code || fn;
        var sel_   = (val === curVal || fn === curVal || p.product_name === curVal) ? ' selected' : '';
        opts += '<option value="' + val.replace(/"/g,'&quot;') + '"' + sel_ + '>' + label + '</option>';
      });
      /* 직접 입력 옵션 */
      opts += '<option value="__custom__">✏️ 직접 입력...</option>';
      sel.innerHTML = opts;
      td.innerHTML = '';
      td.appendChild(sel);
      sel.focus();

      function commitSel() {
        var newVal = sel.value;
        if (newVal === '__custom__') {
          /* 직접 입력 모드로 전환 */
          td.innerHTML = '';
          var ci = document.createElement('input');
          ci.type = 'text'; ci.value = curVal;
          ci.className = 'onestop-edit-input';
          ci.style.cssText = 'width:100%;padding:2px 4px;background:var(--bg);color:var(--fg);border:1px solid var(--accent);border-radius:3px;font-size:11px;font-family:inherit';
          td.appendChild(ci); ci.focus(); ci.select();
          ci.addEventListener('blur', function(){ applyCommit(ci.value); });
          ci.addEventListener('keydown', function(e){
            if (e.key==='Enter'){ e.preventDefault(); ci.blur(); }
            else if (e.key==='Escape'){ e.preventDefault(); ci.removeEventListener('blur',function(){}); _onestopRenderPreview(_onestopState.previewRows); }
          });
          return;
        }
        applyCommit(newVal);
      }
      function applyCommit(newVal) {
        if (String(newVal) === String(curVal) || !newVal) {
          _onestopRenderPreview(_onestopState.previewRows); return;
        }
        _onestopState.history = _onestopState.history.slice(0, _onestopState.historyIdx + 1);
        _onestopState.history.push({ rowIdx: rowIdx, field: field, oldVal: curVal, newVal: newVal });
        if (_onestopState.history.length > ONESTOP_MAX_HISTORY) _onestopState.history.shift();
        _onestopState.historyIdx = _onestopState.history.length - 1;
        if (!_onestopState.previewRows[rowIdx]) _onestopState.previewRows[rowIdx] = {};
        _onestopState.previewRows[rowIdx][field] = newVal;
        var origVal = (_onestopState.originalRows[rowIdx] || {})[field];
        var cellKey = rowIdx + '.' + field;
        if (String(newVal) !== String(origVal == null ? '' : origVal)) { _onestopState.editedCells[cellKey] = true; }
        else { delete _onestopState.editedCells[cellKey]; }
        _onestopRenderPreview(_onestopState.previewRows);
        _onestopUpdateHistoryButtons();
      }
      sel.addEventListener('change', commitSel);
      sel.addEventListener('blur',   commitSel);
      sel.addEventListener('keydown', function(e){
        if (e.key === 'Enter')  { e.preventDefault(); commitSel(); }
        else if (e.key === 'Escape') { e.preventDefault(); sel.removeEventListener('blur', commitSel); _onestopRenderPreview(_onestopState.previewRows); }
      });
      return;  /* product 처리 끝 — 아래 일반 input 로직 실행 안 함 */
    }

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
    var seenLots = {};
    var dupLots = [];
    _onestopState.previewRows.forEach(function(r, idx) {
      var lot = String((r && r.lot_no) || '').trim();
      if (!lot) return;
      var key = lot.toUpperCase();
      if (seenLots[key]) dupLots.push({lot_no: lot, first: seenLots[key], row: idx + 1});
      else seenLots[key] = idx + 1;
    });
    if (dupLots.length) {
      showToast('error', '중복 LOT가 있어 DB 업로드를 중단했습니다: ' + dupLots[0].lot_no);
      alert('중복 LOT 차단\n\n같은 입고 파일 안에 동일 LOT가 있습니다.\n첫 번째 중복: ' + dupLots[0].lot_no + ' (행 ' + dupLots[0].first + ', ' + dupLots[0].row + ')\n\n중복을 제거한 뒤 다시 저장하세요.');
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
        var d = e && e.detail && e.detail.detail ? e.detail.detail : null;
        var msg = (d && (d.message || d.code)) || (e.message || String(e));
        if (d && d.errors && d.errors.length) {
          msg += ' — ' + (d.errors[0].lot_no || '') + ' ' + (d.errors[0].reason || '');
        }
        showToast('error', 'DB 저장 오류: ' + msg);
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


  /* ── Gemini 비교 패널 ─────────────────────────────────────── */
  var COMPARE_COLS   = ['lot_no', 'container', 'lot_sqm', 'mxbg', 'net_kg', 'gross_kg', 'arrival', 'con_return', 'free_time', 'wh'];
  var COMPARE_LABELS = ['LOT No', '컨테이너', 'LOT m²', '맥시백', '순중량', '총중량', '입항일', '컨반납일', 'FreeTime', '창고'];

  function _showGeminiComparePanel(coordRows, geminiRows) {
    var existing = document.getElementById('sqm-gemini-compare');
    if (existing) existing.remove();

    var p = document.createElement('div');
    p.id = 'sqm-gemini-compare';
    p.style.cssText = 'position:fixed;top:32px;left:50%;transform:translateX(-50%);width:min(98vw,1400px);max-height:90vh;'
      + 'background:var(--bg-card);border:1px solid var(--panel-border);border-radius:10px;'
      + 'box-shadow:0 8px 40px rgba(0,0,0,.55);z-index:10100;display:flex;flex-direction:column';

    /* header */
    p.innerHTML = '<div id="sgc-hdr" style="cursor:move;user-select:none;padding:9px 14px;border-bottom:1px solid var(--panel-border);'
      + 'display:flex;align-items:center;gap:8px;border-radius:10px 10px 0 0;background:var(--panel)">'
      + '<span style="font-weight:700;font-size:13px;flex:1">🔍 파싱 결과 비교 — 좌: 좌표 등록 / 우: Gemini AI</span>'
      + '<button onclick="document.getElementById(\'sqm-gemini-compare\').remove()" '
      + 'style="background:none;border:none;cursor:pointer;color:var(--text-muted);font-size:1.3rem;line-height:1">✕</button></div>'
      + '<div style="overflow:auto;flex:1;padding:0">' + _buildCompareTable(coordRows, geminiRows) + '</div>'
      + '<div style="padding:10px 14px;border-top:1px solid var(--panel-border);display:flex;gap:10px;justify-content:flex-end;background:var(--panel);border-radius:0 0 10px 10px">'
      + '<span style="flex:1;font-size:12px;color:var(--text-muted)">🟡 노란색 = 두 결과가 다른 셀  · 선택한 결과가 DB 업로드 대상이 됩니다</span>'
      + '<button class="btn" onclick="_selectCompareResult(\'coord\')" style="border:2px solid var(--info,#42a5f5)">📍 좌표 등록 선택</button>'
      + '<button class="btn btn-primary" onclick="_selectCompareResult(\'gemini\')">🤖 Gemini 선택</button>'
      + '</div>';

    document.body.appendChild(p);

    /* draggable header */
    var drag = {on:false,sx:0,sy:0,ox:0,oy:0};
    p.querySelector('#sgc-hdr').addEventListener('mousedown', function(e){
      drag.on=true; drag.sx=e.clientX; drag.sy=e.clientY;
      var r=p.getBoundingClientRect(); drag.ox=r.left; drag.oy=r.top;
      p.style.transform='none'; p.style.left=r.left+'px'; e.preventDefault();
    });
    document.addEventListener('mousemove', function(e){
      if (!drag.on) return;
      p.style.left=(drag.ox+(e.clientX-drag.sx))+'px';
      p.style.top =(drag.oy+(e.clientY-drag.sy))+'px';
    });
    document.addEventListener('mouseup', function(){ drag.on=false; });

    /* store rows for selection */
    p._coordRows  = coordRows;
    p._geminiRows = geminiRows;
  }

  function _buildCompareTable(coordRows, geminiRows) {
    var maxLen = Math.max(coordRows.length, geminiRows.length);
    var thStyle = 'padding:5px 7px;border:1px solid var(--panel-border);background:var(--panel);font-size:11px;white-space:nowrap';
    var tdStyle = 'padding:4px 6px;border:1px solid var(--panel-border);font-size:11px;white-space:nowrap';
    var diffStyle = tdStyle + ';background:#fff3cd;color:#7a5c00';

    var html = '<table class="data-table" style="border-collapse:collapse;width:100%;min-width:900px">';
    /* header row */
    html += '<thead><tr>';
    html += '<th style="' + thStyle + '">#</th>';
    COMPARE_COLS.forEach(function(c, i) {
      html += '<th style="' + thStyle + ';color:var(--info,#42a5f5)">' + COMPARE_LABELS[i] + '<br><small style="color:var(--text-muted)">좌표</small></th>';
      html += '<th style="' + thStyle + ';color:#27ae60">' + COMPARE_LABELS[i] + '<br><small style="color:var(--text-muted)">Gemini</small></th>';
    });
    html += '</tr></thead><tbody>';

    for (var i = 0; i < maxLen; i++) {
      var cr = coordRows[i]  || {};
      var gr = geminiRows[i] || {};
      html += '<tr>';
      html += '<td style="' + tdStyle + ';text-align:center;color:var(--text-muted)">' + (i+1) + '</td>';
      COMPARE_COLS.forEach(function(col) {
        var cv = String(cr[col] == null ? '' : cr[col]);
        var gv = String(gr[col] == null ? '' : gr[col]);
        var diff = cv !== gv;
        html += '<td style="' + (diff ? diffStyle : tdStyle) + '">' + escapeHtml(cv) + '</td>';
        html += '<td style="' + (diff ? diffStyle : tdStyle) + '">' + escapeHtml(gv) + '</td>';
      });
      html += '</tr>';
    }
    html += '</tbody></table>';
    return html;
  }

  function _selectCompareResult(which) {
    var p = document.getElementById('sqm-gemini-compare');
    if (!p) return;
    var chosen = which === 'gemini' ? p._geminiRows : p._coordRows;
    _onestopState.previewRows  = chosen.slice();
    _onestopState.originalRows = JSON.parse(JSON.stringify(chosen));
    _onestopState.editedCells  = {};
    _onestopState.parsed = chosen.length > 0;
    _onestopRenderPreview();
    p.remove();
    showToast('success', (which === 'gemini' ? '🤖 Gemini' : '📍 좌표 등록') + ' 결과 선택됨 (' + chosen.length + '행)');
  }

  /* expose state for sqm-inline.js keyboard handler */
  window._sqmOS = _onestopState;

})();
