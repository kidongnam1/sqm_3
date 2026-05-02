"""
menu_patch_2_cleanup.py — SQM v866 메뉴 재구조화 Phase A2 (정리)
실행 전제: menu_patch_1_structure.py 가 이미 적용된 index.html 상태

변경 내용:
  ⑥ 출고 > Sales Order → 보고서 메뉴로 이동 (onSalesOrderDN 제외)
  ⑦ onSalesOrderDN 중복 — 출고에서 ⑥ 처리됨, 추가 작업 없음
  ⑧ 입고 > 🔍 정합성 submenu-parent 블록 제거 + onFixLotIntegrity 설정/도구 추가
  ⑨ 입고 직속 onInboundTemplateManage 단독 버튼 제거
  ⑩ 설정/도구 > 📦 제품 관리 submenu-parent 블록 전체 제거

실행 방법: python scripts/menu_patch_2_cleanup.py
"""

import os
import shutil

# ─────────────────────────────────────────────
# 경로 설정
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(BASE_DIR, "frontend", "index.html")
BAK  = os.path.join(BASE_DIR, "frontend", "index.html.bak_menu2")

print("=" * 60)
print("menu_patch_2_cleanup.py 시작")
print(f"  대상: {SRC}")
print(f"  백업: {BAK}")
print("=" * 60)

# ─────────────────────────────────────────────
# 파일 읽기 (null 바이트 제거)
# ─────────────────────────────────────────────
with open(SRC, "rb") as f:
    raw = f.read()

null_count = raw.count(b"\x00")
if null_count:
    print(f"[경고] null 바이트 {null_count:,}개 발견 → 자동 제거")
    raw = raw.replace(b"\x00", b"")

content = raw.decode("utf-8", errors="replace")
print(f"[OK] 파일 읽기 완료 — {len(content):,} 문자")

# 백업 저장
shutil.copy2(SRC, BAK)
print(f"[OK] 백업 저장: {BAK}")

# ─────────────────────────────────────────────
# 헬퍼: str.replace 1회 치환 + 존재 확인
# ─────────────────────────────────────────────
def apply_patch(label, old, new, text, count=1):
    if old not in text:
        print(f"[SKIP] {label} — 대상 문자열 없음 (이미 적용됐거나 구조 변경됨)")
        return text
    result = text.replace(old, new, count)
    applied = text.count(old) - result.count(old)
    print(f"[OK]   {label} — {applied}곳 치환 완료")
    return result

# ─────────────────────────────────────────────
# ⑥ 출고 메뉴 Sales Order submenu-parent 블록 제거
#    → 보고서 메뉴 첫 번째 submenu-parent(송장/DN) 바로 앞에 삽입
#       (onSalesOrderDN은 보고서>송장/DN에 이미 있으므로 미포함)
# ─────────────────────────────────────────────
print()
print("─ ⑥ Sales Order: 출고→보고서 이동 ─")

# 제거 대상: 출고 메뉴 내 Sales Order 블록
OLD_SO_OUTBOUND = """\
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">📊 Sales Order</button>
        <div class="submenu-dropdown">
          <button data-action="onSalesOrderUpload" title="Sales Order Excel 파일을 업로드합니다">📊 Sales Order 업로드</button>
          <button data-action="onSalesOrderDN" title="Sales Order 기반 DN(Delivery Note)을 생성합니다">📋 Sales Order DN</button>
        </div>
      </div>"""

content = apply_patch("⑥-a 출고>Sales Order 블록 제거", OLD_SO_OUTBOUND, "", content)

# 삽입 대상: 보고서 메뉴 첫 submenu-parent(송장/DN) 바로 앞
# anchor: 보고서 메뉴 드롭다운 첫 번째 submenu-parent 시작
ANCHOR_REPORT_FIRST = """\
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">📄 송장/DN</button>"""

NEW_SO_REPORT = """\
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">📊 Sales Order</button>
        <div class="submenu-dropdown">
          <button data-action="onSalesOrderUpload" title="Sales Order Excel 파일을 업로드합니다">📊 Sales Order 업로드</button>
        </div>
      </div>
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">📄 송장/DN</button>"""

content = apply_patch("⑥-b 보고서 앞에 Sales Order 삽입", ANCHOR_REPORT_FIRST, NEW_SO_REPORT, content)

# ─────────────────────────────────────────────
# ⑦ onSalesOrderDN 중복 처리
#    출고 메뉴의 Sales Order DN은 ⑥에서 전체 블록 제거 시 함께 처리됨.
#    보고서>송장/DN의 onSalesOrderDN은 유지.
#    → 추가 작업 없음.
# ─────────────────────────────────────────────
print()
print("─ ⑦ onSalesOrderDN 중복 확인 ─")
dn_count = content.count('data-action="onSalesOrderDN"')
print(f"[INFO] onSalesOrderDN 잔존 개수: {dn_count} (보고서>송장/DN 1개만 있어야 정상)")
if dn_count == 1:
    print("[OK]   중복 없음 — 추가 작업 불필요")
elif dn_count == 0:
    print("[경고] onSalesOrderDN 버튼이 전혀 없음 — 보고서>송장/DN 확인 필요")
else:
    print(f"[경고] onSalesOrderDN이 {dn_count}곳 — 수동 확인 필요")

# ─────────────────────────────────────────────
# ⑧ 입고 > 🔍 정합성 submenu-parent 블록 전체 제거
#    + 설정/도구 > 🩺 정합성 안에 onFixLotIntegrity 추가 (없는 경우에만)
# ─────────────────────────────────────────────
print()
print("─ ⑧ 입고>정합성 블록 제거 + 설정/도구>정합성에 onFixLotIntegrity 추가 ─")

OLD_INBOUND_INTEGRITY = """\
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">🔍 정합성</button>
        <div class="submenu-dropdown">
          <button data-action="onIntegrityCheck" title="DB 데이터의 정합성을 시각적으로 확인합니다. 이상 데이터 감지">🔍 정합성 검증 (시각화)</button>
          <button data-action="onFixLotIntegrity" title="LOT 상태값 불일치를 자동으로 감지하고 복구합니다">🛠️ LOT 상태 정합성 복구</button>
        </div>
      </div>"""

content = apply_patch("⑧-a 입고>🔍정합성 블록 제거", OLD_INBOUND_INTEGRITY, "", content)

# 설정/도구 > 🩺 정합성 안에 onFixLotIntegrity 없으면 추가
if 'data-action="onFixLotIntegrity"' in content:
    print("[SKIP] ⑧-b onFixLotIntegrity 이미 설정/도구에 존재 — 추가 불필요")
else:
    # onIntegrityCheck 다음 줄에 추가 (설정/도구 내 🩺 정합성 dropdown 안)
    OLD_TOOLS_INTEGRITY_BTN = """\
          <button data-action="onIntegrityCheck" title="DB 데이터의 정합성을 시각적으로 확인합니다. 이상 데이터 감지">🩺 데이터 정합성 검사</button>
        </div>"""
    NEW_TOOLS_INTEGRITY_BTN = """\
          <button data-action="onIntegrityCheck" title="DB 데이터의 정합성을 시각적으로 확인합니다. 이상 데이터 감지">🩺 데이터 정합성 검사</button>
          <button data-action="onFixLotIntegrity" title="LOT 상태값 불일치를 자동으로 감지하고 복구합니다">🛠️ LOT 상태 정합성 복구</button>
        </div>"""
    content = apply_patch("⑧-b 설정/도구>🩺정합성에 onFixLotIntegrity 추가",
                          OLD_TOOLS_INTEGRITY_BTN, NEW_TOOLS_INTEGRITY_BTN, content)

# ─────────────────────────────────────────────
# ⑨ 입고 직속 단독 버튼 onInboundTemplateManage 제거
#    입고>조회/관리 안의 동일 버튼은 유지
# ─────────────────────────────────────────────
print()
print("─ ⑨ 입고 직속 onInboundTemplateManage 단독 버튼 제거 ─")

# 직속 버튼: 서브메뉴 없이 단독으로 존재하는 버튼
# 앞뒤 context를 이용해 정확히 특정
OLD_INBOUND_TMPL_DIRECT = """\
      <button data-action="onInboundTemplateManage" title="선사별 PDF 파싱 템플릿을 생성·수정·삭제합니다">📝 인바운드 템플릿 관리</button>
      <!-- D/O만 남김: Invoice FA, B/L 삭제 -->"""

NEW_INBOUND_TMPL_DIRECT = """\
      <!-- D/O만 남김: Invoice FA, B/L 삭제 -->"""

content = apply_patch("⑨ 입고 직속 onInboundTemplateManage 제거",
                      OLD_INBOUND_TMPL_DIRECT, NEW_INBOUND_TMPL_DIRECT, content)

# 혹시 주석 없이 바로 다음 줄이 다를 경우 대비 — 단순 버튼만으로 재시도
if 'data-action="onInboundTemplateManage"' in content:
    # 조회/관리 안의 버튼은 유지해야 하므로, 개수 확인 후 직속(서브메뉴 밖) 것만 제거
    remaining = content.count('data-action="onInboundTemplateManage"')
    print(f"[INFO] onInboundTemplateManage 잔존 개수: {remaining}")
    if remaining == 1:
        print("[OK]   조회/관리 안 버튼 1개만 남음 — 정상")
    elif remaining > 1:
        print("[경고] 아직 중복 존재 — 주석 형태가 다를 수 있음, 수동 확인 필요")
else:
    print("[경고] onInboundTemplateManage 버튼이 전혀 없음 — 조회/관리 안 버튼 확인 필요")

# ─────────────────────────────────────────────
# ⑩ 설정/도구 > 📦 제품 관리 submenu-parent 블록 전체 제거
#    (onLotAllocationAudit는 Phase A1에서 Allocation 메뉴로 이동됨)
# ─────────────────────────────────────────────
print()
print("─ ⑩ 설정/도구>📦제품 관리 블록 제거 ─")

OLD_PRODUCT_MGMT = """\
      <div class="submenu-parent" tabindex="0">
        <button class="submenu-parent-btn" type="button">📦 제품 관리</button>
        <div class="submenu-dropdown">
          <button data-action="onLotAllocationAudit" title="LOT별 Allocation 및 톤백 현황을 감사합니다">📊 LOT Allocation 톤백 현황</button>
        </div>
      </div>"""

content = apply_patch("⑩ 설정/도구>📦제품 관리 블록 제거", OLD_PRODUCT_MGMT, "", content)

# ─────────────────────────────────────────────
# 최종 저장
# ─────────────────────────────────────────────
print()
print("─ 최종 저장 ─")
with open(SRC, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
print(f"[OK] 저장 완료: {SRC}")
print(f"     최종 파일 크기: {len(content.encode('utf-8')):,} bytes")

# ─────────────────────────────────────────────
# 검증 요약
# ─────────────────────────────────────────────
print()
print("=" * 60)
print("검증 요약")
print("=" * 60)

checks = [
    ("보고서>Sales Order 삽입",       'data-action="onSalesOrderUpload"',         1),
    ("onSalesOrderDN 유일",            'data-action="onSalesOrderDN"',              1),
    ("입고>정합성 블록 제거",           '🔍 정합성 검증 (시각화)',                    0),
    ("설정/도구>정합성 onFixLot 존재", 'data-action="onFixLotIntegrity"',           1),
    ("입고 직속 템플릿 단독 버튼 제거", '인바운드 템플릿 관리</button>\n      <!-- D/O', 0),
    ("조회/관리 템플릿 버튼 유지",     'data-action="onInboundTemplateManage"',     1),
    ("설정/도구>제품관리 블록 제거",   'onLotAllocationAudit',                      0),
]

all_ok = True
for label, needle, expected in checks:
    actual = content.count(needle)
    ok = (actual == expected)
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {label}: 기대 {expected}개, 실제 {actual}개")
    if not ok:
        all_ok = False

print()
if all_ok:
    print("[PASS] 모든 검증 통과 — Phase A2 완료")
else:
    print("[WARN] 일부 항목 불일치 — 위 FAIL 항목 수동 확인 필요")
print("=" * 60)
