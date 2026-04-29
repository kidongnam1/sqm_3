"""
extract_onestop.py — OneStop Inbound module extractor
Splits lines 3811-5008 from sqm-inline.js into sqm-onestop-inbound.js

Usage:
    python scripts/extract_onestop.py [--dry-run]

Safe to re-run: creates .bak backup before modifying any file.
"""
import sys
import shutil
import re
from pathlib import Path

DRY_RUN = '--dry-run' in sys.argv

ROOT    = Path(__file__).resolve().parent.parent
INLINE  = ROOT / 'frontend' / 'js' / 'sqm-inline.js'
ONESTOP = ROOT / 'frontend' / 'js' / 'sqm-onestop-inbound.js'
INDEX   = ROOT / 'frontend' / 'index.html'
VERSION = '20260429'

# OneStop Inbound section boundaries (1-based line numbers, inclusive)
START = 3811   # /* ===  [Sprint 1-2-A] OneStop Inbound  */
END   = 5008   # blank line after _addParseLog closing brace

def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_atomic(path, content):
    """Write UTF-8 LF; verify no byte corruption."""
    if DRY_RUN:
        print(f'[DRY-RUN] would write {path} ({len(content)} chars)')
        return
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    tmp.replace(path)
    print(f'[OK] wrote {path}')

def backup(path):
    bak = path.with_suffix(path.suffix + '.bak')
    if not DRY_RUN:
        shutil.copy2(path, bak)
    print(f'[BAK] {bak.name}')

# ── 1. Read source ──────────────────────────────────────────────────────────
src = read(INLINE)
lines = src.splitlines(keepends=True)
total = len(lines)
print(f'[INFO] sqm-inline.js: {total} lines')

assert START <= END <= total, f'Boundary out of range: {START}-{END} vs {total}'

# Extract section (0-based indexing)
extracted_lines = lines[START - 1 : END]   # lines 3811..5008
extracted = ''.join(extracted_lines).rstrip('\n') + '\n'

# ── 2. Build sqm-onestop-inbound.js ─────────────────────────────────────────
# The extracted code uses variables defined in sqm-inline.js's outer IIFE
# (showToast, escapeHtml, apiPost, apiGet, _makeDraggableResizable, _bringToFront,
#  showDataModal, loadInventoryPage, loadKpi, _currentRoute, API).
# We wrap in a deferred init so sqm-inline.js loads first.

ONESTOP_HEADER = f"""\
/* =======================================================================
   sqm-onestop-inbound.js  (v{VERSION})
   OneStop Inbound — 4-slot wizard modal + parse engine
   Extracted from sqm-inline.js lines {START}–{END} by extract_onestop.py
   Dependencies (provided by sqm-inline.js):
     showToast, escapeHtml, apiPost, apiGet,
     _makeDraggableResizable, _bringToFront, showDataModal,
     loadInventoryPage, loadKpi, _currentRoute, API
   ======================================================================= */
(function () {{
  'use strict';
"""

ONESTOP_FOOTER = """
  /* expose state for sqm-inline.js keyboard handler */
  window._sqmOS = _onestopState;

})();
"""

# Strip the raw section's leading/trailing blank lines; keep inner indentation
onestop_body = extracted

onestop_content = ONESTOP_HEADER + onestop_body + ONESTOP_FOOTER

# ── 3. Patch sqm-inline.js ──────────────────────────────────────────────────
# 3a. Replace the extracted section with a single comment placeholder
placeholder = (
    '  /* OneStop Inbound module -> sqm-onestop-inbound.js */\n'
)

before = ''.join(lines[:START - 1])
after  = ''.join(lines[END:])
patched_inline = before + placeholder + after

# 3b. Fix line 369 reference: _onestopState.parsed -> window._sqmOS && window._sqmOS.parsed
OLD_REF = "typeof _onestopState !== 'undefined' && _onestopState.parsed"
NEW_REF = "window._sqmOS && window._sqmOS.parsed"
if OLD_REF in patched_inline:
    patched_inline = patched_inline.replace(OLD_REF, NEW_REF, 1)
    print('[PATCH] line 369: _onestopState reference updated')
else:
    print('[WARN] line 369 reference not found — check manually')

# ── 4. Patch index.html ─────────────────────────────────────────────────────
html_src = read(INDEX)
INLINE_TAG = f'sqm-inline.js?v='
ONESTOP_TAG = f'<script src="js/sqm-onestop-inbound.js?v={VERSION}"></script>'

if 'sqm-onestop-inbound.js' in html_src:
    print('[SKIP] index.html already has sqm-onestop-inbound.js tag')
else:
    # Insert after the sqm-inline.js script tag line
    m = re.search(r'(<script[^>]*sqm-inline\.js[^>]*></script>)', html_src)
    if m:
        insert_after = m.group(0)
        html_patched = html_src.replace(
            insert_after,
            insert_after + '\n    ' + ONESTOP_TAG,
            1
        )
        print('[PATCH] index.html: added sqm-onestop-inbound.js script tag')
    else:
        html_patched = None
        print('[WARN] Could not find sqm-inline.js tag in index.html — add manually:')
        print(f'       {ONESTOP_TAG}')

# ── 5. Write all files ──────────────────────────────────────────────────────
print()
backup(INLINE)
backup(INDEX)

write_atomic(ONESTOP, onestop_content)
write_atomic(INLINE, patched_inline)
if 'html_patched' in dir() and html_patched:
    write_atomic(INDEX, html_patched)

# ── 6. Quick size sanity check ──────────────────────────────────────────────
if not DRY_RUN:
    inline_lines = len(open(INLINE, encoding='utf-8').readlines())
    onestop_lines = len(open(ONESTOP, encoding='utf-8').readlines())
    print(f'\n[RESULT]')
    print(f'  sqm-inline.js         : {total} -> {inline_lines} lines '
          f'(removed {total - inline_lines})')
    print(f'  sqm-onestop-inbound.js: {onestop_lines} lines (new)')
    print()
    print('Next: node --check frontend/js/sqm-inline.js')
    print('      node --check frontend/js/sqm-onestop-inbound.js')
