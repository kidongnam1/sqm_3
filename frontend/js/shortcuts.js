// SQM v8.6.6
// feature_matrix.json 의 category=keyboard 13건 + Golden Reference 기본 단축키
import { navigateTo } from './router.js';
import { showToast } from './toast.js';

export const SHORTCUTS = {
  'F1':        { action: 'help',        label: '도움말' },
  'F2':        { action: 'refresh',     label: '새로고침' },
  'F5':        { action: 'refresh',     label: '새로고침' },
  'Ctrl+F':    { action: 'find',        label: '찾기' },
  'Ctrl+N':    { action: 'new',         label: '신규' },
  'Ctrl+S':    { action: 'save',        label: '저장' },
  'Ctrl+P':    { action: 'print',       label: '인쇄' },
  'Ctrl+B':    { action: 'backup',      label: '백업' },
  'Ctrl+I':    { action: 'inventory',   label: '재고 조회' },
  'Ctrl+O':    { action: 'outbound',    label: '출고' },
  'Ctrl+R':    { action: 'return',      label: '반품' },
  'Ctrl+L':    { action: 'log',         label: '로그' },
  'Escape':    { action: 'close',       label: '닫기' },
};

function normalizeEvent(ev) {
  const keys = [];
  if (ev.ctrlKey) keys.push('Ctrl');
  if (ev.altKey) keys.push('Alt');
  if (ev.shiftKey) keys.push('Shift');
  const k = ev.key;
  if (!['Control', 'Alt', 'Shift', 'Meta'].includes(k)) {
    keys.push(k.length === 1 ? k.toUpperCase() : k);
  }
  return keys.join('+');
}

export function initShortcuts() {
  document.addEventListener('keydown', (ev) => {
    // 입력 필드 안에서는 스킵
    const tag = (ev.target?.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || ev.target?.isContentEditable) {
      if (!(ev.key === 'Escape' || ev.key.startsWith('F'))) return;
    }
    const combo = normalizeEvent(ev);
    const conf = SHORTCUTS[combo];
    if (!conf) return;
    ev.preventDefault();
    try {
      handleAction(conf.action);
      showToast('info', `⌨️ ${combo} — ${conf.label}`);
    } catch (e) {
      showToast('error', `단축키 실행 실패: ${e.message}`);
    }
  });
}

function handleAction(action) {
  switch (action) {
    case 'refresh':
      document.querySelector('[data-action="refresh-all"]')?.click();
      break;
    case 'inventory':  navigateTo('inventory'); break;
    case 'outbound':   navigateTo('outbound'); break;
    case 'return':     navigateTo('return'); break;
    case 'log':        navigateTo('log'); break;
    case 'help':
      window.dispatchEvent(new Event('sqm:help-open'));
      break;
    case 'close':
      document.querySelector('.modal.open')?.classList.remove('open');
      break;
    case 'find':
      document.querySelector('input[type="search"]')?.focus();
      break;
    case 'new':
    case 'save':
    case 'print':
    case 'backup':
      document.querySelector(`[data-action="tb-${action}"]`)?.click();
      break;
  }
}
