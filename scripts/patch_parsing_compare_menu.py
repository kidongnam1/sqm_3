# -*- coding: utf-8 -*-
"""sqm-inline.js 에 onParsingCompareSummary ENDPOINT + dispatch 추가 (원자적 쓰기)"""
import sys, re

SRC  = r'd:\program\SQM_inventory\SQM_v866_CLEAN\frontend\js\sqm-inline.js'
DEST = SRC

with open(SRC, 'r', encoding='utf-8') as f:
    c = f.read()

# ── 1. ENDPOINTS 테이블에 추가 ──────────────────────────────────────────
OLD_EP = "    'onOnPdfInbound':    {m:'JS', u:'pdf-inbound-upload', lbl:'PDF 스캔 입고'},"
NEW_EP = ("    'onOnPdfInbound':    {m:'JS', u:'pdf-inbound-upload', lbl:'PDF 스캔 입고'},\n"
          "    'onParsingCompareSummary': {m:'JS', u:'parsing-compare-summary', lbl:'파싱 결과 요약표'},")

if OLD_EP not in c:
    print("ERROR: ENDPOINT 삽입 위치를 찾지 못했습니다.", file=sys.stderr)
    sys.exit(1)

c = c.replace(OLD_EP, NEW_EP, 1)

# ── 2. dispatch 블록에 추가 ─────────────────────────────────────────────
OLD_DIS = "      if (conf.u === 'pdf-inbound-upload') {\n        /* [Sprint 1-2] OneStop 4슬롯 wizard 모달 (v864-2 OneStopInboundDialog 매칭) */\n        showOneStopInboundModal();\n        return;\n      }"
NEW_DIS = (OLD_DIS + "\n"
           "      if (conf.u === 'parsing-compare-summary') {\n"
           "        if (typeof window.showParsingCompareSummaryModal === 'function') {\n"
           "          window.showParsingCompareSummaryModal();\n"
           "        } else {\n"
           "          showToast('warn', 'sqm-onestop-inbound.js 로드 전입니다. 잠시 후 다시 시도하세요.');\n"
           "        }\n"
           "        return;\n"
           "      }")

if OLD_DIS not in c:
    print("ERROR: dispatch 삽입 위치를 찾지 못했습니다.", file=sys.stderr)
    sys.exit(1)

c = c.replace(OLD_DIS, NEW_DIS, 1)

# ── 3. null바이트 / bash 오염 제거 ──────────────────────────────────────
raw = c.encode('utf-8')
raw = raw.replace(bytes([0x00]), b'')
raw = raw.replace(bytes([0x5c, 0x21]), bytes([0x21]))

# ── 4. 원자적 쓰기 ──────────────────────────────────────────────────────
with open(DEST, 'w', encoding='utf-8', newline='\n') as f:
    f.write(raw.decode('utf-8'))

print("OK: onParsingCompareSummary ENDPOINT + dispatch 추가 완료")

# ── 5. 확인 ─────────────────────────────────────────────────────────────
with open(DEST, 'r', encoding='utf-8') as f:
    chk = f.read()

assert 'onParsingCompareSummary' in chk, "ENDPOINT 확인 실패"
assert 'parsing-compare-summary' in chk, "dispatch 확인 실패"
print("검증 완료 — ENDPOINT 2건 존재 확인:")
for i, line in enumerate(chk.splitlines(), 1):
    if 'onParsingCompareSummary' in line or 'parsing-compare-summary' in line:
        print(f"  line {i}: {line.strip()[:80]}")
