"""
patch_menu_connections.py — Menu connection fixes for sqm-inline.js

Priority 1: Fix wrong-connection ENDPOINTS (3 items)
Priority 2: Wire email/backup to real backend + honest LOT label
Priority 3 (easy): Wire Gemini API settings/test/toggle to real backend

Usage: python scripts/patch_menu_connections.py [--dry-run]
"""
import sys
import shutil
from pathlib import Path

DRY_RUN = '--dry-run' in sys.argv
ROOT   = Path(__file__).resolve().parent.parent
INLINE = ROOT / 'frontend' / 'js' / 'sqm-inline.js'

# JS close-modal snippet (reused in multiple modals)
_CLOSE = r"document.getElementById(\'sqm-modal\').style.display=\'none\'"
_CLOSE_BTN = r'<button onclick="' + _CLOSE + r'" class="btn btn-ghost">닫기</button>'


def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_atomic(path, content):
    if DRY_RUN:
        print(f'[DRY-RUN] would write {path} ({len(content)} chars)')
        return
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    tmp.replace(path)
    print(f'[OK] wrote {path}')


src = read(INLINE)
original_len = len(src)
patches = []

# Helper: build the close-button HTML that works inside a JS single-quoted string
# The JS string uses single quotes, so inner single quotes must be escaped as \'
CLOSE_M = "document.getElementById(\\'sqm-modal\\').style.display=\\'none\\'"
CLOSE_BTN_HTML = '<button onclick="' + CLOSE_M + '" class="btn btn-ghost">닫기</button>'

# ============================================================
# PRIORITY 1 — Fix wrong-connection ENDPOINTS (wip toast)
# ============================================================

p1_items = [
    (
        "'onProductMaster':   {m:'GET',  u:'/api/info/system-info',                    lbl:'제품 마스터'},",
        "'onProductMaster':   {m:'JS',   u:'wip',                                       lbl:'제품 마스터'},",
        'P1-A: onProductMaster -> wip',
    ),
    (
        "'onReportTemplates': {m:'GET',  u:'/api/q/audit-log',                          lbl:'보고서 양식 관리'},",
        "'onReportTemplates': {m:'JS',   u:'wip',                                       lbl:'보고서 양식 관리'},",
        'P1-B: onReportTemplates -> wip',
    ),
    (
        "'onReportHistory':   {m:'GET',  u:'/api/q/audit-log',                          lbl:'보고서 이력 조회'},",
        "'onReportHistory':   {m:'JS',   u:'wip',                                       lbl:'보고서 이력 조회'},",
        'P1-C: onReportHistory -> wip',
    ),
]

for old, new, label in p1_items:
    if old in src:
        src = src.replace(old, new, 1)
        patches.append(label)
    else:
        print(f'[WARN] {label}: pattern not found')

# ============================================================
# PRIORITY 2 — Honest labels + real backend connections
# ============================================================

# P2-A: LOT 복구 label -> 검사 (honest)
OLD = "'onFixLotIntegrity': {m:'GET',  u:'/api/action/integrity-check',              lbl:'LOT 상태 정합성 복구'},"
NEW = "'onFixLotIntegrity': {m:'GET',  u:'/api/action/integrity-check',              lbl:'LOT 정합성 검사'},"
if OLD in src:
    src = src.replace(OLD, NEW, 1)
    patches.append('P2-A: onFixLotIntegrity label -> 검사')
else:
    print('[WARN] P2-A: LOT integrity label pattern not found')

# P2-B: showEmailConfigModal — replace dummy showSettingsDialog with real load+save
OLD_EMAIL = (
    "  function showEmailConfigModal() {\n"
    "    showSettingsDialog('이메일 설정', '⚙️', [\n"
    "      { id:'host', label:'SMTP 서버', hint:'smtp.gmail.com', value:'smtp.gmail.com' },\n"
    "      { id:'port', label:'포트', type:'number', hint:'587', value:'587' },\n"
    "      { id:'user', label:'사용자', hint:'user@company.com' },\n"
    "      { id:'pass', label:'비밀번호', type:'password', hint:'앱 비밀번호' },\n"
    "      { id:'tls', label:'TLS 사용', type:'checkbox', checked:true, hint:'TLS 암호화' }\n"
    "    ]);\n"
    "  }\n"
    "  window.showEmailConfigModal = showEmailConfigModal;"
)

NEW_EMAIL = (
    "  function showEmailConfigModal() {\n"
    "    apiGet('/api/settings/email').then(function(res) {\n"
    "      var cfg = (res && res.data) || {};\n"
    "      var inp = 'padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;width:100%';\n"
    "      var html = '<div style=\"max-width:500px\">'\n"
    "        + '<h2 style=\"margin:0 0 16px 0\">⚙️ 이메일 설정</h2>'\n"
    "        + '<div style=\"display:grid;grid-template-columns:120px 1fr;gap:10px 12px;align-items:center;margin-bottom:16px\">'\n"
    "        + '<label style=\"font-weight:600\">SMTP 서버</label><input type=\"text\" id=\"em-host\" value=\"' + escapeHtml(cfg.smtp_host||'smtp.gmail.com') + '\" style=\"' + inp + '\">'\n"
    "        + '<label style=\"font-weight:600\">포트</label><input type=\"number\" id=\"em-port\" value=\"' + (cfg.smtp_port||587) + '\" style=\"' + inp + '\">'\n"
    "        + '<label style=\"font-weight:600\">사용자</label><input type=\"text\" id=\"em-user\" value=\"' + escapeHtml(cfg.smtp_user||'') + '\" placeholder=\"user@company.com\" style=\"' + inp + '\">'\n"
    "        + '<label style=\"font-weight:600\">비밀번호</label><input type=\"password\" id=\"em-pass\" value=\"' + escapeHtml(cfg.smtp_pass||'') + '\" placeholder=\"앱 비밀번호\" style=\"' + inp + '\">'\n"
    "        + '<label style=\"font-weight:600\">발신 주소</label><input type=\"text\" id=\"em-from\" value=\"' + escapeHtml(cfg.from_addr||'') + '\" placeholder=\"noreply@company.com\" style=\"' + inp + '\">'\n"
    "        + '<label style=\"font-weight:600\">수신자</label><input type=\"text\" id=\"em-recipients\" value=\"' + escapeHtml(cfg.recipients||'') + '\" placeholder=\"admin@company.com, ...\" style=\"' + inp + '\">'\n"
    "        + '<label style=\"font-weight:600\">TLS 사용</label><label style=\"display:flex;align-items:center;gap:6px\"><input type=\"checkbox\" id=\"em-tls\"' + (cfg.tls !== false ? ' checked' : '') + '> TLS 암호화</label>'\n"
    "        + '<label style=\"font-weight:600\">활성화</label><label style=\"display:flex;align-items:center;gap:6px\"><input type=\"checkbox\" id=\"em-enabled\"' + (cfg.enabled ? ' checked' : '') + '> 이메일 기능 사용</label>'\n"
    "        + '</div>'\n"
    "        + '<div style=\"display:flex;gap:8px;justify-content:flex-end\">'\n"
    "        + '<button onclick=\"" + CLOSE_M + "\" class=\"btn btn-ghost\">닫기</button>'\n"
    "        + '<button onclick=\"window._saveEmailConfig()\" class=\"btn btn-primary\">저장</button>'\n"
    "        + '</div></div>';\n"
    "      showDataModal('', html);\n"
    "    }).catch(function() {\n"
    "      showToast('error', '이메일 설정 불러오기 실패');\n"
    "    });\n"
    "  }\n"
    "  window._saveEmailConfig = function() {\n"
    "    var payload = {\n"
    "      smtp_host: (document.getElementById('em-host')||{}).value||'',\n"
    "      smtp_port: parseInt((document.getElementById('em-port')||{}).value||'587', 10),\n"
    "      smtp_user: (document.getElementById('em-user')||{}).value||'',\n"
    "      smtp_pass: (document.getElementById('em-pass')||{}).value||'',\n"
    "      from_addr: (document.getElementById('em-from')||{}).value||'',\n"
    "      recipients: (document.getElementById('em-recipients')||{}).value||'',\n"
    "      tls:      !!(document.getElementById('em-tls')||{}).checked,\n"
    "      enabled:  !!(document.getElementById('em-enabled')||{}).checked\n"
    "    };\n"
    "    apiPost('/api/settings/email', payload).then(function() {\n"
    "      showToast('success', '이메일 설정 저장 완료');\n"
    "      document.getElementById('sqm-modal').style.display = 'none';\n"
    "    }).catch(function(e) {\n"
    "      showToast('error', '저장 실패: ' + (e.message || String(e)));\n"
    "    });\n"
    "  };\n"
    "  window.showEmailConfigModal = showEmailConfigModal;"
)

if OLD_EMAIL in src:
    src = src.replace(OLD_EMAIL, NEW_EMAIL, 1)
    patches.append('P2-B: showEmailConfigModal -> real backend /api/settings/email')
else:
    print('[WARN] P2-B: showEmailConfigModal pattern not found')

# P2-C: showAutoBackupSettingsModal — replace dummy with real load+save
OLD_BACKUP = (
    "  function showAutoBackupSettingsModal() {\n"
    "    showSettingsDialog('자동 백업 설정', '⏰', [\n"
    "      { id:'enabled', label:'자동 백업', type:'checkbox', checked:false, hint:'활성화' },\n"
    "      { id:'interval', label:'주기', type:'select', options:['30분','1시간','3시간','6시간','12시간','24시간'] },\n"
    "      { id:'retention', label:'보존 개수', type:'number', hint:'최대 보존 백업 수', value:'10' },\n"
    "      { id:'path', label:'저장 경로', hint:'backup/', value:'backup/' }\n"
    "    ]);\n"
    "  }\n"
    "  window.showAutoBackupSettingsModal = showAutoBackupSettingsModal;"
)

NEW_BACKUP = (
    "  function showAutoBackupSettingsModal() {\n"
    "    var INTERVAL_VALUES = [30, 60, 180, 360, 720, 1440];\n"
    "    var INTERVAL_LABELS = ['30분', '1시간', '3시간', '6시간', '12시간', '24시간'];\n"
    "    var inp = 'padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px';\n"
    "    apiGet('/api/settings/backup').then(function(res) {\n"
    "      var cfg = (res && res.data) || {};\n"
    "      var selOpts = INTERVAL_VALUES.map(function(v, i) {\n"
    "        return '<option value=\"' + v + '\"' + (cfg.interval_min === v ? ' selected' : '') + '>' + INTERVAL_LABELS[i] + '</option>';\n"
    "      }).join('');\n"
    "      var lastBackup = cfg.last_backup ? '<div style=\"margin-bottom:10px;font-size:.82rem;color:var(--text-muted)\">최근 백업: ' + escapeHtml(cfg.last_backup) + '</div>' : '';\n"
    "      var html = '<div style=\"max-width:460px\">'\n"
    "        + '<h2 style=\"margin:0 0 16px 0\">⏰ 자동 백업 설정</h2>'\n"
    "        + '<div style=\"display:grid;grid-template-columns:100px 1fr;gap:10px 12px;align-items:center;margin-bottom:16px\">'\n"
    "        + '<label style=\"font-weight:600\">자동 백업</label><label style=\"display:flex;align-items:center;gap:6px\"><input type=\"checkbox\" id=\"bk-enabled\"' + (cfg.enabled ? ' checked' : '') + '> 활성화</label>'\n"
    "        + '<label style=\"font-weight:600\">주기</label><select id=\"bk-interval\" style=\"' + inp + '\">' + selOpts + '</select>'\n"
    "        + '<label style=\"font-weight:600\">보존 개수</label><input type=\"number\" id=\"bk-retention\" value=\"' + (cfg.retention||10) + '\" min=\"1\" max=\"100\" style=\"' + inp + '\">'\n"
    "        + '<label style=\"font-weight:600\">저장 경로</label><input type=\"text\" id=\"bk-path\" value=\"' + escapeHtml(cfg.path||'backup/') + '\" style=\"' + inp + '\">'\n"
    "        + '</div>'\n"
    "        + lastBackup\n"
    "        + '<div style=\"display:flex;gap:8px;justify-content:flex-end\">'\n"
    "        + '<button onclick=\"" + CLOSE_M + "\" class=\"btn btn-ghost\">닫기</button>'\n"
    "        + '<button onclick=\"window._saveBackupConfig()\" class=\"btn btn-primary\">저장</button>'\n"
    "        + '</div></div>';\n"
    "      showDataModal('', html);\n"
    "    }).catch(function() {\n"
    "      showToast('error', '백업 설정 불러오기 실패');\n"
    "    });\n"
    "  }\n"
    "  window._saveBackupConfig = function() {\n"
    "    var payload = {\n"
    "      enabled:      !!(document.getElementById('bk-enabled')||{}).checked,\n"
    "      interval_min: parseInt((document.getElementById('bk-interval')||{}).value||'60', 10),\n"
    "      retention:    parseInt((document.getElementById('bk-retention')||{}).value||'10', 10),\n"
    "      path:         (document.getElementById('bk-path')||{}).value||'backup/'\n"
    "    };\n"
    "    apiPost('/api/settings/backup', payload).then(function() {\n"
    "      showToast('success', '자동 백업 설정 저장 완료');\n"
    "      document.getElementById('sqm-modal').style.display = 'none';\n"
    "    }).catch(function(e) {\n"
    "      showToast('error', '저장 실패: ' + (e.message || String(e)));\n"
    "    });\n"
    "  };\n"
    "  window.showAutoBackupSettingsModal = showAutoBackupSettingsModal;"
)

if OLD_BACKUP in src:
    src = src.replace(OLD_BACKUP, NEW_BACKUP, 1)
    patches.append('P2-C: showAutoBackupSettingsModal -> real backend /api/settings/backup')
else:
    print('[WARN] P2-C: showAutoBackupSettingsModal pattern not found')

# ============================================================
# PRIORITY 3 — Gemini AI menu wires (backend already exists)
# ============================================================

# P3-A/B/C: ENDPOINTS wire Gemini items
gemini_items = [
    (
        "    'onGeminiToggle':      {m:'JS', u:'wip',                                       lbl:'🔀 Gemini AI 사용'},",
        "    'onGeminiToggle':      {m:'JS', u:'gemini-toggle',                             lbl:'🔀 Gemini AI 사용'},",
        'P3-A: onGeminiToggle -> gemini-toggle',
    ),
    (
        "    'onGeminiApiSettings': {m:'JS', u:'wip',                                       lbl:'🔐 Gemini API 설정'},",
        "    'onGeminiApiSettings': {m:'JS', u:'gemini-api-settings',                       lbl:'🔐 Gemini API 설정'},",
        'P3-B: onGeminiApiSettings -> gemini-api-settings',
    ),
    (
        "    'onGeminiApiTest':     {m:'JS', u:'wip',                                       lbl:'🧪 Gemini API 테스트'},",
        "    'onGeminiApiTest':     {m:'JS', u:'gemini-api-test',                           lbl:'🧪 Gemini API 테스트'},",
        'P3-C: onGeminiApiTest -> gemini-api-test',
    ),
]
for old, new, label in gemini_items:
    if old in src:
        src = src.replace(old, new, 1)
        patches.append(label)
    else:
        print(f'[WARN] {label}: pattern not found')

# P3-D: Add Gemini modal functions after showAutoBackupSettingsModal
ANCHOR = "  window.showAutoBackupSettingsModal = showAutoBackupSettingsModal;"

NEW_GEMINI = (
    "\n\n"
    "  /* ── Gemini AI 설정/테스트/토글 ─────────────────────────────── */\n"
    "  function showGeminiApiSettingsModal() {\n"
    "    apiGet('/api/ai/settings').then(function(res) {\n"
    "      var cfg = res || {};\n"
    "      var inp = 'padding:8px;background:var(--bg-hover);color:var(--text);border:1px solid var(--border);border-radius:6px;width:100%';\n"
    "      var statusHtml = cfg.has_key\n"
    "        ? '<span style=\"color:var(--success)\">✅ 키 등록됨</span> <span style=\"color:var(--text-muted);font-size:.8rem\">(' + escapeHtml(cfg.key_source||'') + ')</span>'\n"
    "        : '<span style=\"color:var(--warning)\">⚠️ 키 없음</span>';\n"
    "      var html = '<div style=\"max-width:480px\">'\n"
    "        + '<h2 style=\"margin:0 0 14px 0\">🔐 Gemini API 설정</h2>'\n"
    "        + '<div style=\"margin-bottom:12px\">' + statusHtml + '</div>'\n"
    "        + '<div style=\"display:grid;grid-template-columns:90px 1fr;gap:10px 12px;align-items:center;margin-bottom:14px\">'\n"
    "        + '<label style=\"font-weight:600\">API 키</label><input type=\"password\" id=\"gm-key\" placeholder=\"새 키 입력 (변경 시만)\" style=\"' + inp + '\">'\n"
    "        + '<label style=\"font-weight:600\">모델</label><input type=\"text\" id=\"gm-model\" value=\"' + escapeHtml(cfg.model||'gemini-1.5-flash') + '\" style=\"' + inp + '\">'\n"
    "        + '<label style=\"font-weight:600\">사용</label><label style=\"display:flex;align-items:center;gap:6px\"><input type=\"checkbox\" id=\"gm-enabled\"' + (cfg.enabled !== false ? ' checked' : '') + '> Gemini AI 활성화</label>'\n"
    "        + '</div>'\n"
    "        + '<div style=\"padding:9px;background:var(--bg-hover);border-radius:6px;margin-bottom:12px;font-size:.82rem;color:var(--text-muted)\">키를 비워두면 기존 키가 유지됩니다.</div>'\n"
    "        + '<div style=\"display:flex;gap:8px;justify-content:flex-end\">'\n"
    "        + '<button onclick=\"" + CLOSE_M + "\" class=\"btn btn-ghost\">닫기</button>'\n"
    "        + '<button onclick=\"window._saveGeminiSettings()\" class=\"btn btn-primary\">저장</button>'\n"
    "        + '</div></div>';\n"
    "      showDataModal('', html);\n"
    "    }).catch(function() {\n"
    "      showToast('error', 'Gemini 설정 불러오기 실패');\n"
    "    });\n"
    "  }\n"
    "  window._saveGeminiSettings = function() {\n"
    "    var key   = (document.getElementById('gm-key')||{}).value||'';\n"
    "    var model = (document.getElementById('gm-model')||{}).value||'gemini-1.5-flash';\n"
    "    var enabled = !!(document.getElementById('gm-enabled')||{}).checked;\n"
    "    var p1 = key.trim()\n"
    "      ? apiPost('/api/ai/settings', { api_key: key.trim(), model: model })\n"
    "      : Promise.resolve(null);\n"
    "    p1.then(function() {\n"
    "      return apiPost('/api/ai/toggle', { enabled: enabled });\n"
    "    }).then(function() {\n"
    "      showToast('success', 'Gemini 설정 저장 완료');\n"
    "      document.getElementById('sqm-modal').style.display = 'none';\n"
    "    }).catch(function(e) {\n"
    "      showToast('error', '저장 실패: ' + (e.message || String(e)));\n"
    "    });\n"
    "  };\n"
    "\n"
    "  function showGeminiApiTestModal() {\n"
    "    showDataModal('', '<div style=\"max-width:440px\"><h3 style=\"margin:0 0 12px\">🧪 Gemini API 연결 테스트</h3><div id=\"gm-test-body\" style=\"color:var(--text-muted)\">테스트 중…</div></div>');\n"
    "    apiGet('/api/ai/test').then(function(res) {\n"
    "      var body = document.getElementById('gm-test-body');\n"
    "      if (!body) return;\n"
    "      var ok = res && res.success;\n"
    "      body.innerHTML = ok\n"
    "        ? '<div style=\"color:var(--success);font-size:1.1rem\">✅ 연결 성공</div><div style=\"margin-top:8px;font-size:.85rem;color:var(--text-muted)\">' + escapeHtml((res.message||'') + (res.model ? ' / 모델: ' + res.model : '')) + '</div>'\n"
    "        : '<div style=\"color:var(--danger);font-size:1.1rem\">❌ 연결 실패</div><div style=\"margin-top:8px;font-size:.85rem;color:var(--text-muted)\">' + escapeHtml((res && res.message) || '알 수 없는 오류') + '</div>';\n"
    "    }).catch(function(e) {\n"
    "      var body = document.getElementById('gm-test-body');\n"
    "      if (body) body.innerHTML = '<div style=\"color:var(--danger)\">❌ 오류: ' + escapeHtml(e.message||String(e)) + '</div>';\n"
    "    });\n"
    "  }\n"
    "\n"
    "  window._geminiToggleAction = function() {\n"
    "    apiGet('/api/ai/settings').then(function(res) {\n"
    "      var next = !(res && res.enabled !== false);\n"
    "      return apiPost('/api/ai/toggle', { enabled: next }).then(function(r) {\n"
    "        showToast('success', (r && r.message) || ('Gemini AI ' + (next ? 'ON' : 'OFF')));\n"
    "      });\n"
    "    }).catch(function(e) {\n"
    "      showToast('error', 'Gemini 토글 실패: ' + (e.message || String(e)));\n"
    "    });\n"
    "  };"
)

if ANCHOR in src:
    src = src.replace(ANCHOR, ANCHOR + NEW_GEMINI, 1)
    patches.append('P3-D: added showGeminiApiSettingsModal / showGeminiApiTestModal / _geminiToggleAction')
else:
    print('[WARN] P3-D: anchor not found for Gemini functions')

# P3-E: Dispatcher cases for gemini handlers
OLD_DISP = (
    "      if (conf.u === 'auto-backup-settings') {\n"
    "        showAutoBackupSettingsModal();\n"
    "        return;\n"
    "      }"
)
NEW_DISP = (
    "      if (conf.u === 'auto-backup-settings') {\n"
    "        showAutoBackupSettingsModal();\n"
    "        return;\n"
    "      }\n"
    "      if (conf.u === 'gemini-api-settings') { showGeminiApiSettingsModal(); return; }\n"
    "      if (conf.u === 'gemini-api-test') { showGeminiApiTestModal(); return; }\n"
    "      if (conf.u === 'gemini-toggle') { window._geminiToggleAction(); return; }"
)
if OLD_DISP in src:
    src = src.replace(OLD_DISP, NEW_DISP, 1)
    patches.append('P3-E: added Gemini dispatcher cases')
else:
    print('[WARN] P3-E: dispatcher anchor not found')

# ============================================================
# Write result
# ============================================================
print(f'\nPatches applied ({len(patches)}):')
for p in patches:
    print(f'  [+] {p}')

print(f'\nSize: {original_len} -> {len(src)} chars (delta {len(src)-original_len:+d})')

if not DRY_RUN:
    bak = INLINE.with_suffix('.js.bak2')
    shutil.copy2(INLINE, bak)
    print(f'[BAK] {bak.name}')

write_atomic(INLINE, src)

if not DRY_RUN:
    print('\nNext: node --check frontend/js/sqm-inline.js')
