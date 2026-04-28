"""
bl_carrier_registry.py — SQM v6.4.0
=====================================
BL 선사별 파싱 템플릿 레지스트리

설계 원칙:
  공통 파싱 엔진(GeminiParser)은 유지하되,
  선사별로 탐지 규칙 / BL No 추출 패턴 / Gemini 프롬프트 힌트를 분리.
  새 선사 추가 = CARRIER_TEMPLATES에 항목 1개 추가만으로 완료.

탐지 우선순위:
  1) 정규식(detect_pattern) 매칭 — 신뢰도 높음 (2점)
  2) 키워드(detect_keywords) 매칭 — 보조 (각 1점)
  점수가 가장 높은 선사 템플릿 선택
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
try:
    from engine_modules.constants import CARRIER_OPTIONS as _CARRIER_OPTIONS
except ImportError:
    _CARRIER_OPTIONS = []
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# 1. 선사 템플릿 데이터 클래스
# ─────────────────────────────────────────────────────────────────
@dataclass
class CarrierTemplate:
    """선사별 BL 파싱 규칙 정의"""
    carrier_id: str           # 내부 식별자 (예: "MSC", "MAERSK")
    carrier_name: str         # 표시용 이름

    # ── 탐지 규칙 ─────────────────────────────────────────────────
    detect_keywords: list     # 1페이지 텍스트에 있으면 이 선사로 인식 (각 1점)
    detect_pattern: str       # 정규식 매칭 시 2점 보너스

    # ── BL No 추출 규칙 ───────────────────────────────────────────
    bl_extract_pattern: str   # 정규식 — group(1)이 BL No
    bl_page_scope: str        # "page0" | "page0_to_2" | "all"
    bl_format_hint: str       # Gemini 프롬프트용 예시 (예: "MEDUFP963996")

    # ── 컨테이너 추출 ─────────────────────────────────────────────
    container_pattern: str = r"\b([A-Z]{4}\d{7})\b"
    container_blacklist: list = field(default_factory=list)

    # ── SAP No 위치 힌트 ─────────────────────────────────────────
    sap_page_hint: str = "all"

    # ── Gemini 프롬프트 커스터마이징 ────────────────────────────
    bl_no_prompt_hint: str = ""

    # ── 특수 처리 플래그 ─────────────────────────────────────────
    # Maersk처럼 BL No == Booking No인 경우 크로스체크에서 정상 처리
    bl_equals_booking_no: bool = False


# ─────────────────────────────────────────────────────────────────
# 2. 선사 템플릿 레지스트리
#    새 선사 추가 = 아래 딕셔너리에 항목 1개 추가
# ─────────────────────────────────────────────────────────────────
CARRIER_TEMPLATES: dict[str, CarrierTemplate] = {

    # ── MSC (Mediterranean Shipping Company) ──────────────────────
    # BL 형식: 1페이지 상단 첫 줄
    #   "MEDITERRANEAN SHIPPING COMPANY S.A.  SEA WAYBILL No.  MEDUFP963996"
    # 주의: Rider Page에 컨테이너 번호(MSNU..., TCLU...) 있음 → 오탐 차단 필요
    "MSC": CarrierTemplate(
        carrier_id="MSC",
        carrier_name="Mediterranean Shipping Company",
        detect_keywords=["MEDITERRANEAN SHIPPING COMPANY", "SEA WAYBILL No.", "MSC CHILE"],
        detect_pattern=r"MEDITERRANEAN SHIPPING COMPANY",
        bl_extract_pattern=(
            r"MEDITERRANEAN SHIPPING COMPANY.*?SEA WAYBILL No\.\s+(\w{6,20})"
        ),
        bl_page_scope="page0",          # Rider page(2~3페이지) 절대 사용 금지
        bl_format_hint="MEDUFP963996",
        sap_page_hint="page1_to_2",     # SAP는 Rider page에 있음
        bl_no_prompt_hint=(
            "【MSC Sea Waybill 전용 규칙】\n"
            "BL No 위치: 1페이지 상단 맨 첫 번째 줄 끝에 있습니다.\n"
            "형식 예시: MEDUFP963996 (MEDU로 시작하는 알파벳+숫자 혼합)\n"
            "⚠️ 주의: Rider Page(2~3페이지)에 컨테이너 번호(MSNU7490553, TCLU4987755 등)가 있는데 "
            "이것은 BL No가 아닙니다. 절대 혼동하지 마세요.\n"
            "⚠️ 주의: 문서에 'SEA WAYBILL No.'가 여러 번 등장하는데 반드시 1페이지 것만 사용하세요."
        ),
    ),

    # ── MAERSK ────────────────────────────────────────────────────
    # BL 형식: 1페이지 "B/L No. 263764814"
    #          2~3페이지 "B/L: 263764814 Page : 2"
    # 특이사항: BL No == Booking No (같은 숫자) → 크로스체크 경고 방지 필요
    "MAERSK": CarrierTemplate(
        carrier_id="MAERSK",
        carrier_name="Maersk",
        detect_keywords=["MAERSK", "SCAC MAEU", "NON-NEGOTIABLE WAYBILL"],
        detect_pattern=r"(?:MAERSK|SCAC\s+MAEU)",
        bl_extract_pattern=r"B/L\s*(?:No\.?|:)\s*(\d{6,12})",
        bl_page_scope="page0_to_2",
        bl_format_hint="263764814",
        sap_page_hint="all",
        bl_no_prompt_hint=(
            "【Maersk Sea Waybill 전용 규칙】\n"
            "BL No 위치: 1페이지 우상단 'B/L No.' 라벨 바로 오른쪽\n"
            "형식 예시: 263764814 (순수 숫자 9자리)\n"
            "2~3페이지에도 'B/L: 263764814 Page : 2' 형식으로 반복됩니다.\n"
            "⚠️ 주의: Booking No.도 같은 숫자(263764814)일 수 있는데 "
            "이것은 Maersk의 정상 현상입니다. 반드시 'B/L No.' 라벨이 붙은 것을 BL No로 사용하세요."
        ),
        bl_equals_booking_no=True,      # ★ Maersk 전용: BL No == Booking No 정상 플래그
    ),

    # ── HMM (Hyundai Merchant Marine) ─────────────────────────────
    # 실제 HMM BL 샘플 없음 → 보수적 패턴 적용, 실제 수신 후 정밀화 필요
    # 현재 상태: 탐지만 가능, BL No는 Gemini fallback 사용
    "HMM": CarrierTemplate(
        carrier_id="HMM",
        carrier_name="Hyundai Merchant Marine",
        detect_keywords=["HYUNDAI MERCHANT MARINE", "HMM", "HMM CO., LTD"],
        detect_pattern=r"HYUNDAI MERCHANT MARINE",
        bl_extract_pattern=r"B(?:/L|ILL OF LADING)\s*(?:No\.?|NUMBER|:)\s*([A-Z0-9]{6,20})",
        bl_page_scope="page0",
        bl_format_hint="HBKM1234567",  # 예시 — 실제 형식 확인 후 업데이트 필요
        sap_page_hint="all",
        bl_no_prompt_hint=(
            "【HMM (Hyundai Merchant Marine) Bill of Lading 전용 규칙】\n"
            "BL No 위치: 1페이지 상단 'B/L No.' 또는 'Bill of Lading No.' 라벨 근처\n"
            "⚠️ 주의: 실제 HMM BL 샘플 기반이 아니므로 추출 후 반드시 확인하세요."
        ),
    ),

    # ── CMA CGM ───────────────────────────────────────────────────
    # 실제 CMA CGM BL 샘플 없음 → 보수적 패턴, Gemini fallback
    "CMA_CGM": CarrierTemplate(
        carrier_id="CMA_CGM",
        carrier_name="CMA CGM",
        detect_keywords=["CMA CGM", "COMPAGNIE GENERALE MARITIME"],
        detect_pattern=r"CMA\s*CGM",
        bl_extract_pattern=r"B(?:/L|ILL OF LADING)\s*(?:No\.?|:)\s*([A-Z0-9]{6,20})",
        bl_page_scope="page0",
        bl_format_hint="CMAU1234567",  # 예시 — 실제 형식 확인 후 업데이트 필요
        sap_page_hint="all",
        bl_no_prompt_hint=(
            "【CMA CGM Bill of Lading 전용 규칙】\n"
            "BL No 위치: 1페이지 상단 'B/L No.' 라벨 근처\n"
            "⚠️ 주의: 실제 CMA CGM BL 샘플 기반이 아니므로 추출 후 반드시 확인하세요."
        ),
    ),

    # ── ONE (Ocean Network Express) ───────────────────────────────
    # v9.2: 실제 ONE BL 샘플(ONEYSCLG01825300 BL.pdf) 기반으로 갱신
    # BL 형식: "SEA WAYBILL NO." 라벨 우측 — ONEY + 영숫자 10~14자리
    #   예: ONEYSCLG01825300
    "ONE": CarrierTemplate(
        carrier_id="ONE",
        carrier_name="Ocean Network Express",
        detect_keywords=["OCEAN NETWORK EXPRESS", "ONE-LINE.COM", "WWW.ONE-LINE.COM"],
        detect_pattern=r"OCEAN NETWORK EXPRESS",
        bl_extract_pattern=r"\b(ONEY[A-Z0-9]{10,14})\b",
        bl_page_scope="page0",
        bl_format_hint="ONEYSCLG01825300",
        sap_page_hint="all",
        bl_no_prompt_hint=(
            "【ONE (Ocean Network Express) Sea Waybill 전용 규칙】\n"
            "BL No 위치: 1페이지 상단 'SEA WAYBILL NO.' 라벨 오른쪽\n"
            "형식 예시: ONEYSCLG01825300 (ONEY로 시작하는 영숫자 14~16자리)\n"
            "⚠️ 주의: 글자가 한 칸씩 분리되어 인쇄될 수 있음 → 공백 제거 후 ONEY 접두사로 매칭\n"
            "⚠️ 주의: 컨테이너 번호(ONEU로 시작)와 혼동하지 마세요."
        ),
    ),
}


# ─────────────────────────────────────────────────────────────────
# 3. 선사 자동 탐지
# ─────────────────────────────────────────────────────────────────
def detect_carrier(page0_text: str) -> Optional[CarrierTemplate]:
    """
    1페이지 텍스트를 분석해 가장 적합한 선사 템플릿 반환.
    매칭 없으면 None 반환 → 범용 파싱 사용.
    """
    scores: dict[str, int] = {}
    text_upper = page0_text.upper()

    for cid, tmpl in CARRIER_TEMPLATES.items():
        score = 0
        for kw in tmpl.detect_keywords:
            if kw.upper() in text_upper:
                score += 1
        if tmpl.detect_pattern and re.search(
            tmpl.detect_pattern, page0_text, re.IGNORECASE
        ):
            score += 2
        scores[cid] = score
        logger.debug(f"[CarrierDetect] {cid}: score={score}")

    if not scores or max(scores.values()) == 0:
        logger.warning("[CarrierDetect] 매칭 선사 없음 → 범용 파싱 사용")
        return None

    best_id = max(scores, key=lambda k: scores[k])
    tmpl = CARRIER_TEMPLATES[best_id]
    logger.info(
        f"[CarrierDetect] 선사 감지: {tmpl.carrier_name} "
        f"(score={scores[best_id]}, "
        f"bl_extract_scope={tmpl.bl_page_scope})"
    )
    return tmpl


# ─────────────────────────────────────────────────────────────────
# 4. BL No 정규식 추출 (Gemini 없이 0.01초)
# ─────────────────────────────────────────────────────────────────
def extract_bl_no_by_template(
    pages_text: list[str],
    tmpl: CarrierTemplate,
) -> str:
    """
    선사 템플릿의 bl_extract_pattern으로 BL No 추출.
    성공 시 즉시 반환, 실패 시 빈 문자열 → Gemini fallback.
    """
    if tmpl.bl_page_scope == "page0":
        search_pages = pages_text[:1]
    elif tmpl.bl_page_scope == "page0_to_2":
        search_pages = pages_text[:3]
    else:
        search_pages = pages_text

    for page_i, text in enumerate(search_pages):
        m = re.search(tmpl.bl_extract_pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            bl_no = m.group(1).strip()
            logger.info(
                f"[BLExtract] {tmpl.carrier_id} BL No 정규식 추출 성공: "
                f"{bl_no!r} (page {page_i})"
            )
            return bl_no

    logger.warning(
        f"[BLExtract] {tmpl.carrier_id} BL No 정규식 미탐 — Gemini fallback 사용"
    )
    return ""


# ─────────────────────────────────────────────────────────────────
# 5. Gemini 프롬프트 생성 (선사별 힌트 포함)
# ─────────────────────────────────────────────────────────────────
def build_bl_prompt(tmpl: Optional[CarrierTemplate] = None) -> str:
    """
    선사 템플릿에 맞는 Gemini 프롬프트 반환.
    tmpl=None이면 범용 프롬프트.
    """
    bl_example = tmpl.bl_format_hint if tmpl else "258468669"
    carrier_section = (
        f"\n\n{tmpl.bl_no_prompt_hint}\n" if tmpl and tmpl.bl_no_prompt_hint else ""
    )

    return f"""이 B/L(선하증권/NON-NEGOTIABLE WAYBILL) 문서를 분석하여 아래 JSON 형식으로 추출해주세요.
{carrier_section}
**중요 추출 규칙:**
1. B/L No는 문서 상단 "B/L No." 필드 (예: {bl_example})
2. 컨테이너 번호는 XXXX0000000 형식 (4글자+7숫자)
   - 문서에서 ML-CL 앞에 있는 번호 (예: FFAU5355006, MRKU3714936)
   - 하이픈 없이 추출
3. SAP NO는 2페이지나 3페이지에 22로 시작하는 10자리로 있을 수 있음
4. 컨테이너별 Seal No도 추출 (ML-CL0501798 형식)

```json
{{
    "bl_no": "B/L 번호 (예: {bl_example})",
    "booking_no": "Booking 번호",
    "sap_no": "22로 시작하는 10자리 (있으면)",
    "vessel": "선박명 (예: CHARLOTTE MAERSK)",
    "voyage": "항차 번호 (예: 535W)",
    "port_of_loading": "선적항 (예: Puerto Angamos, Chile)",
    "port_of_discharge": "양하항 (예: GWANGYANG, SOUTH KOREA)",
    "shipper": "송하인 (예: SQM SALAR SpA)",
    "consignee": "수하인 (예: SOQUIMICH LLC)",
    "containers": [
        {{"container_no": "FFAU5355006", "seal_no": "ML-CL0501798", "weight_kg": 20525}},
        {{"container_no": "MRKU3714936", "seal_no": "ML-CL0501791", "weight_kg": 20525}}
    ],
    "total_containers": 5,
    "total_weight_kg": 102625,
    "shipped_on_board_date": "★필수★ 선적일 YYYY-MM-DD 또는 NOT_FOUND"
}}
```

★★★ shipped_on_board_date (선적일) 추출 규칙 ★★★
- 찾는 위치: "SHIPPED ON BOARD", "ON BOARD DATE", "LADEN ON BOARD", "DATE OF SHIPMENT" 라벨 근처
- 보통 문서 하단 또는 서명 근처에 있습니다
- 형식: 반드시 YYYY-MM-DD로 변환 (예: 2025-09-15)
- "15 SEP 2025" 형식이면 → "2025-09-15"로 변환
- "15/09/2025" 형식이면 → "2025-09-15"로 변환
- 찾지 못하면 "NOT_FOUND"라고 적어주세요. 빈 문자열("") 금지!

모든 컨테이너를 빠짐없이 추출해주세요. JSON만 응답해주세요."""


# ─────────────────────────────────────────────────────────────────
# 6. 선사 템플릿 정보 조회 (디버그/UI 표시용)
# ─────────────────────────────────────────────────────────────────
def get_carrier_summary() -> str:
    """등록된 선사 목록 요약 (로그/UI 표시용)"""
    lines = ["[CarrierRegistry] 등록 선사 목록:"]
    for cid, tmpl in CARRIER_TEMPLATES.items():
        status = "✅ 검증됨" if cid in ("MSC", "MAERSK") else "⚠️ 샘플 미검증"
        lines.append(
            f"  {cid:12s} {tmpl.carrier_name:35s} | "
            f"scope={tmpl.bl_page_scope:12s} | {status}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# 7. v8.7.0: carrier_profiles YAML 플러그인 통합 (옵셔널)
#    - YAML 파일이 0개이거나 pyyaml 미설치여도 앱은 정상 동작.
#    - 병합 전략: 기존 Python 엔트리 우선, YAML은 빈 필드만 보강 or 신규 추가.
#    - 어떤 오류도 raise 하지 않는다 (logger.warning/debug 로 suppress).
# ─────────────────────────────────────────────────────────────────
try:
    from features.ai.carrier_profiles.carrier_profile_loader import merge_with_registry as _merge_yaml_profiles
    CARRIER_TEMPLATES = _merge_yaml_profiles(CARRIER_TEMPLATES)
    logger.info(
        f"[CarrierRegistry] YAML 플러그인 병합 완료: {len(CARRIER_TEMPLATES)}개 선사"
    )
except ImportError:
    logger.debug("[CarrierRegistry] YAML 플러그인 스킵 (pyyaml 또는 loader 없음)")
except Exception as _e:
    logger.warning(f"[CarrierRegistry] YAML 병합 실패(기존 유지): {_e}")
