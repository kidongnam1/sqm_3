"""
menu_patch_1_structure.py
SQM Inventory v8.6.6 — 메뉴 재구조화 Phase A1

변경 내용:
  ① Allocation → 최상위 독립 메뉴 승격 (입고↔출고 사이 삽입)
  ② 출고 메뉴에서 Allocation 서브메뉴 블록 제거
  ③ BL 선사 도구 → 파일 메뉴에서 입고 메뉴로 이동
  ④ Gemini AI → 파일 메뉴에서 설정/도구 메뉴로 이동
  ⑤ 톤백 위치 매핑 + 대량 이동 승인 → 입고에서 재고 메뉴로 이동 (창고 관리 서브메뉴)

실행 방법:
  python scripts/menu_patch_1_structure.py
"""

import os
import shutil

# ─────────────────────────────────────────────
# 경로 설정 (이 스크립트 위치 기준으로 계산)
# ─────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SRC         = os.path.join(PROJECT_DIR, "frontend", "index.html")
BAK         = os.path.join(PROJECT_DIR, "frontend", "index.html.bak_menu1")

print(f"[INFO] 원본 파일: {SRC}")
print(f"[INFO] 백업 파일: {BAK}")

# ─────────────────────────────────────────────
# 파일 읽기
# ─────────────────────────────────────────────
with open(SRC, "r", encoding="utf-8") as f:
    html = f.read()

print(f"[INFO] 원본 파일 읽기 완료 ({len(html):,} bytes)")

# ─────────────────────────────────────────────
# ① Allocation → 최상위 독립 메뉴 승격
#    삽입 위치: "  <!-- ══ ③ 출고 ══ -->" 바로 앞
# ─────────────────────────────────────────────
print("\n[STEP 1] Allocation 최상위 메뉴 삽입...")

STEP1_ANCHOR = "  <!-- ══ ③ 출고 ══ -->"
assert STEP1_ANCHOR in html, \
    f"STEP1 실패: 앵커 문자열을 찾을 수 없습니다.\n찾는 문자열: {STEP1_ANCHOR!r}"

STEP1_NEW_MENU = """\
  <!-- ══ ③ Allocation ══ -->
  <div class="menu-btn" data-menu="Allocation" tabindex="0" role="menuitem">📋 <span>Allocation</span> <span class="caret">▼</span>
    <div class="menu-dropdown">
      <button data-action="onInventoryAllocation" title="고객사별 제품 배정(Allocation)을 입력합니다">📋 Allocation 입력</button>
      <button data-action="onApprovalQueue" title="출고 승인 대기 중인 요청 목록을 확인합니다">✅ 승인 대기</button>
      <button data-action="onApplyApproved" title="승인 완료된 예약 건을 실제 재고에 반영합니다">📌 예약 반영 (승인분)</button>
      <button data-action="onApprovalHistory" title="과거 승인/반려 이력을 조회합니다">📜 승인 이력 조회</button>
      <button data-action="onLotAllocationAudit" title="LOT별 Allocation 및 톤백 현황을 감사합니다">📊 LOT Allocation 현황</button>
    </div>
  </div>

  <!-- ══ ④ 출고 ══ -->"""

html = html.replace(STEP1_ANCHOR, STEP1_NEW_MENU, 1)
assert "data-menu=\"Allocation\"" in html, "STEP1 검증 실패: Allocation 메뉴가 삽입되지 않았습니다."
print("[OK] Allocation 최상위 메뉴 삽입 완료")

# ─────────────────────────────────────────────
# ② 출고 메뉴에서 Allocation 서브메뉴 블록 제거
#    제거 대상: "<!-- Allocation이 PICKING LIST 위로 -->" 주석부터
#              onApprovalHistory 버튼 포함 </div></div> 까지
# ─────────────────────────────────────────────
print("\n[STEP 2] 출고 메뉴에서 Allocation 서브메뉴 제거...")

STEP2_OLD = """\
      <!-- Allocation이 PICKING LIST 위로 -->
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">📋 Allocation</button>
        <div class="submenu-dropdown">
          <button data-action="onInventoryAllocation" title="고객사별 제품 배정(Allocation)을 입력합니다">📋 Allocation 입력</button>
          <button data-action="onApprovalQueue" title="출고 승인 대기 중인 요청 목록을 확인합니다">✅ 승인 대기</button>
          <button data-action="onApplyApproved" title="승인 완료된 예약 건을 실제 재고에 반영합니다">📌 예약 반영 (승인분)</button>
          <button data-action="onApprovalHistory" title="과거 승인/반려 이력을 조회합니다">📜 승인 이력 조회</button>
        </div>
      </div>
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">📋 PICKING LIST</button>"""

STEP2_NEW = """\
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">📋 PICKING LIST</button>"""

assert STEP2_OLD in html, \
    "STEP2 실패: 출고 메뉴 내 Allocation 서브메뉴 블록을 찾을 수 없습니다."

html = html.replace(STEP2_OLD, STEP2_NEW, 1)
print("[OK] 출고 메뉴 Allocation 서브메뉴 제거 완료")

# ─────────────────────────────────────────────
# ③ BL 선사 도구 → 파일 메뉴에서 입고 메뉴로 이동
#    3-1. 파일 메뉴에서 BL 선사 도구 submenu-parent 블록 제거
#    3-2. 입고 메뉴의 onInboundTemplateManage 버튼 바로 다음에 삽입
# ─────────────────────────────────────────────
print("\n[STEP 3] BL 선사 도구 → 파일에서 입고로 이동...")

# 3-1. 파일 메뉴에서 제거
# 앞의 </div> + 다음 submenu-parent까지 포함해서 정확히 매칭
STEP3_REMOVE = """\
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">🚢 BL 선사 도구</button>
        <div class="submenu-dropdown">
          <button data-action="onBlCarrierRegister" title="선사별 BL 양식을 등록합니다. 파싱 정확도 향상에 사용">🚢 선사 BL 등록 도구</button>
          <button data-action="onBlCarrierAnalyze" title="BL 파일을 분석하여 선사별 패턴을 자동 학습합니다">🔬 선사 패턴 분석</button>
        </div>
      </div>
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">✨ Gemini AI</button>"""

STEP3_REMOVE_REPLACEMENT = """\
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">✨ Gemini AI</button>"""

assert STEP3_REMOVE in html, \
    "STEP3 실패: 파일 메뉴 내 BL 선사 도구 블록을 찾을 수 없습니다."

html = html.replace(STEP3_REMOVE, STEP3_REMOVE_REPLACEMENT, 1)
print("[OK] 파일 메뉴에서 BL 선사 도구 제거 완료")

# 3-2. 입고 메뉴의 onInboundTemplateManage 버튼 다음에 삽입
STEP3_INSERT_ANCHOR = """\
      <button data-action="onInboundTemplateManage" title="선사별 PDF 파싱 템플릿을 생성·수정·삭제합니다">📝 인바운드 템플릿 관리</button>
      <!-- D/O만 남김: Invoice FA, B/L 삭제 -->"""

STEP3_INSERT_REPLACEMENT = """\
      <button data-action="onInboundTemplateManage" title="선사별 PDF 파싱 템플릿을 생성·수정·삭제합니다">📝 인바운드 템플릿 관리</button>
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">🚢 BL 선사 도구</button>
        <div class="submenu-dropdown">
          <button data-action="onBlCarrierRegister" title="선사별 BL 양식을 등록합니다. 파싱 정확도 향상에 사용">🚢 선사 BL 등록 도구</button>
          <button data-action="onBlCarrierAnalyze" title="BL 파일을 분석하여 선사별 패턴을 자동 학습합니다">🔬 선사 패턴 분석</button>
        </div>
      </div>
      <!-- D/O만 남김: Invoice FA, B/L 삭제 -->"""

assert STEP3_INSERT_ANCHOR in html, \
    "STEP3 실패: 입고 메뉴 내 onInboundTemplateManage 앵커를 찾을 수 없습니다."

html = html.replace(STEP3_INSERT_ANCHOR, STEP3_INSERT_REPLACEMENT, 1)
print("[OK] 입고 메뉴에 BL 선사 도구 삽입 완료")

# ─────────────────────────────────────────────
# ④ Gemini AI → 파일 메뉴에서 설정/도구로 이동
#    4-1. 파일 메뉴에서 Gemini AI submenu-parent 블록 제거
#    4-2. 설정/도구 메뉴의 onAiTools 버튼 바로 앞에 삽입
# ─────────────────────────────────────────────
print("\n[STEP 4] Gemini AI → 파일에서 설정/도구로 이동...")

# 4-1. 파일 메뉴에서 제거
STEP4_REMOVE = """\
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">✨ Gemini AI</button>
        <div class="submenu-dropdown">
          <button data-action="onAiChat" title="Gemini AI와 재고/물류 관련 질문을 나눕니다">💬 AI 채팅</button>
          <button data-action="onGeminiApiSettings" title="Gemini API 키를 등록·변경합니다">🔐 API 키 설정</button>
          <button data-action="onGeminiApiTest" title="현재 API 키로 Gemini 연결 상태를 테스트합니다">🧪 API 연결 테스트</button>
        </div>
      </div>
      <hr class="menu-sep">
      <button data-action="onDocConvert" title="PDF 또는 이미지 파일을 다른 형식으로 변환합니다">📷 PDF/이미지 변환</button>"""

STEP4_REMOVE_REPLACEMENT = """\
      <hr class="menu-sep">
      <button data-action="onDocConvert" title="PDF 또는 이미지 파일을 다른 형식으로 변환합니다">📷 PDF/이미지 변환</button>"""

assert STEP4_REMOVE in html, \
    "STEP4 실패: 파일 메뉴 내 Gemini AI 블록을 찾을 수 없습니다."

html = html.replace(STEP4_REMOVE, STEP4_REMOVE_REPLACEMENT, 1)
print("[OK] 파일 메뉴에서 Gemini AI 제거 완료")

# 4-2. 설정/도구 메뉴의 onAiTools 버튼 앞에 삽입
STEP4_INSERT_ANCHOR = """\
      <button data-action="onAiTools" title="선사 프로파일·Gemini API 등 AI 관련 도구">🤖 AI 도구 모음</button>"""

STEP4_INSERT_REPLACEMENT = """\
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">✨ Gemini AI</button>
        <div class="submenu-dropdown">
          <button data-action="onAiChat" title="Gemini AI와 재고/물류 관련 질문을 나눕니다">💬 AI 채팅</button>
          <button data-action="onGeminiApiSettings" title="Gemini API 키를 등록·변경합니다">🔐 API 키 설정</button>
          <button data-action="onGeminiApiTest" title="현재 API 키로 Gemini 연결 상태를 테스트합니다">🧪 API 연결 테스트</button>
        </div>
      </div>
      <button data-action="onAiTools" title="선사 프로파일·Gemini API 등 AI 관련 도구">🤖 AI 도구 모음</button>"""

assert STEP4_INSERT_ANCHOR in html, \
    "STEP4 실패: 설정/도구 메뉴 내 onAiTools 버튼 앵커를 찾을 수 없습니다."

html = html.replace(STEP4_INSERT_ANCHOR, STEP4_INSERT_REPLACEMENT, 1)
print("[OK] 설정/도구 메뉴에 Gemini AI 삽입 완료")

# ─────────────────────────────────────────────
# ⑤ 톤백 위치 매핑 + 대량 이동 승인 → 입고에서 재고로 이동
#    5-1. 입고 메뉴 맨 아래 두 버튼 + 위의 <hr> 제거
#    5-2. 재고 메뉴의 onStockTrendChart 앞에 창고 관리 서브메뉴 + hr 삽입
# ─────────────────────────────────────────────
print("\n[STEP 5] 톤백 위치 매핑·대량 이동 승인 → 입고에서 재고로 이동...")

# 5-1. 입고 메뉴에서 제거
STEP5_REMOVE = """\
      <hr class="menu-sep">
      <!-- 톤백·대량이동: 서브메뉴 없이 입고 직속 -->
      <button data-action="onInventoryMove" title="창고 내 톤백의 위치(구역/행/열)를 지도 형태로 매핑합니다">📍 톤백 위치 매핑</button>
      <button data-action="onMoveApprovalQueue" title="대량 이동 요청 목록을 확인하고 일괄 승인 처리합니다">✅ 대량 이동 승인</button>
    </div>
  </div>

  <!-- ══ ③ Allocation ══ -->"""

STEP5_REMOVE_REPLACEMENT = """\
    </div>
  </div>

  <!-- ══ ③ Allocation ══ -->"""

assert STEP5_REMOVE in html, \
    "STEP5 실패: 입고 메뉴 하단 톤백 버튼 블록을 찾을 수 없습니다."

html = html.replace(STEP5_REMOVE, STEP5_REMOVE_REPLACEMENT, 1)
print("[OK] 입고 메뉴에서 톤백 위치 매핑·대량 이동 승인 제거 완료")

# 5-2. 재고 메뉴의 onStockTrendChart 버튼 앞에 삽입
STEP5_INSERT_ANCHOR = """\
      <hr class="menu-sep">
      <button data-action="onStockTrendChart" title="기간별 재고 증감 추이를 차트로 시각화합니다">📊 재고 추이 차트</button>"""

STEP5_INSERT_REPLACEMENT = """\
      <hr class="menu-sep">
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">🏭 창고 관리</button>
        <div class="submenu-dropdown">
          <button data-action="onInventoryMove" title="창고 내 톤백의 위치(구역/행/열)를 지도 형태로 매핑합니다">📍 톤백 위치 매핑</button>
          <button data-action="onMoveApprovalQueue" title="대량 이동 요청 목록을 확인하고 일괄 승인 처리합니다">✅ 대량 이동 승인</button>
        </div>
      </div>
      <hr class="menu-sep">
      <button data-action="onStockTrendChart" title="기간별 재고 증감 추이를 차트로 시각화합니다">📊 재고 추이 차트</button>"""

assert STEP5_INSERT_ANCHOR in html, \
    "STEP5 실패: 재고 메뉴 내 onStockTrendChart 앵커를 찾을 수 없습니다."

html = html.replace(STEP5_INSERT_ANCHOR, STEP5_INSERT_REPLACEMENT, 1)
print("[OK] 재고 메뉴에 창고 관리 서브메뉴 삽입 완료")

# ─────────────────────────────────────────────
# 백업 저장
# ─────────────────────────────────────────────
print(f"\n[BACKUP] 원본 백업 저장: {BAK}")
shutil.copy2(SRC, BAK)
print("[OK] 백업 완료")

# ─────────────────────────────────────────────
# 최종 파일 저장 (UTF-8, LF)
# ─────────────────────────────────────────────
with open(SRC, "w", encoding="utf-8", newline="\n") as f:
    f.write(html)

print(f"\n[DONE] 패치 완료: {SRC} ({len(html):,} bytes)")
print("변경 내용 요약:")
print("  ① Allocation → 최상위 독립 메뉴 (입고↔출고 사이, 번호 재정렬 ③)")
print("  ② 출고 메뉴 Allocation 서브메뉴 제거")
print("  ③ BL 선사 도구 → 파일 메뉴 제거 / 입고 메뉴 추가")
print("  ④ Gemini AI → 파일 메뉴 제거 / 설정/도구 메뉴 추가")
print("  ⑤ 톤백 위치 매핑·대량 이동 승인 → 입고 제거 / 재고>창고 관리 추가")
