# -*- coding: utf-8 -*-
"""중복 삽입된 allocation 핸들러 블록을 제거한다."""
import pathlib, sys

JS = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "js" / "sqm-inline.js"
src = JS.read_text(encoding="utf-8")

# 두 번째로 삽입된 중복 블록 (빈 줄 2개로 시작하는 두 번째 세트)
DUPE_START = "\n\n  /* ── 전체 초기화 ── */\n  window.allocResetAll = function()"
DUPE_END   = "  window.allocResetSelected = function() {"

idx_start = src.find(DUPE_START)
if idx_start == -1:
    print("[INFO] 중복 블록 없음 (이미 제거됨)")
    sys.exit(0)

# 두 번째 allocResetAll 위치 찾기 (첫 번째 이후)
idx_first = src.find("  /* ── 전체 초기화 ── */\n  window.allocResetAll")
idx_second = src.find("  /* ── 전체 초기화 ── */\n  window.allocResetAll", idx_first + 10)
if idx_second == -1:
    print("[INFO] 중복 없음")
    sys.exit(0)

# 두 번째 블록 끝 찾기 (allocResetSelected 바로 앞)
idx_end = src.find(DUPE_END, idx_second)
if idx_end == -1:
    print("[ERROR] 중복 블록 끝 못 찾음")
    sys.exit(1)

# 두 번째 블록 제거 (선행 줄바꿈 포함)
removed_block = src[idx_second:idx_end]
print(f"[INFO] 제거할 블록: 약 {len(removed_block)} chars ({removed_block[:80].strip()!r}...)")

# 두 번째 인스턴스 직전 여분 개행 포함 제거
# idx_second 앞 개행 2개 제거
remove_from = max(0, idx_second - 2)
src_new = src[:remove_from] + "  " + src[idx_end:]

JS.write_text(src_new, encoding="utf-8", newline="\n")
print(f"[OK] 중복 핸들러 제거 완료. {len(src)} → {len(src_new)} chars")
