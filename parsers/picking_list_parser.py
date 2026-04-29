"""
SQM 재고관리 - Picking List 파서 (LBM 스타일)

문서 구조: PICKING LIST / Customer reference / Requisition / Sales order /
Plan Loading Date / Item(본품·샘플) + Batch line 반복 / Packing·Weight 요약.
라벨-라인 기반 파싱, 절대 실패하지 않음(errors[] 반환), 하드스톱 검증.
SQM picking_list_order / picking_list_detail 스키마와 매칭 가능한 dict 반환.

SQM 헤더 매칭 (기존 프로그램 DB 컬럼명 = 반환 dict 키):
  picking_list_order: sales_order, customer_ref, picking_date, status,
                      total_lots, total_weight, remarks, outbound_id
  picking_list_detail: picking_order_id, lot_no, sub_lt, weight,
                       picked_status, picked_at, remarks

특별 규칙: 리스트에 net 5001 kg으로 기재된 경우 문서에 적혀 있지 않아도
본품 500kg×10 + 샘플 1kg 포함으로 간주 (5001 = 500×10 + 1).
decode_net_weight_kg()로 (main_kg, sample_kg) 해석.

AGENTS.md 준수: snake_case, except Exception + logging, _validate_ 접두어.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# PDF 텍스트 추출 임계치 (이하면 OCR 분기 권장)
MIN_TEXT_LENGTH_FOR_PARSE = 100


# -----------------------------------------------------------------------------
# 1) 데이터 모델 (파싱 결과)
# -----------------------------------------------------------------------------

@dataclass
class BatchLine:
    """Batch 한 줄: Quantity / Batch number / Storage location"""
    batch_no: str
    qty: float
    unit: str
    storage_location: Optional[str] = None


@dataclass
class ItemBlock:
    """품목 블록: 자재코드 + 총량 + Batch 라인 목록"""
    material_code: str
    description: str
    total_qty: float
    total_unit: str
    customs_status: Optional[str] = None
    batches: List[BatchLine] = field(default_factory=list)


@dataclass
class PickingDoc:
    """Picking List 파싱 결과 (헤더 + 아이템 블록들)."""
    customer_ref: Optional[str] = None
    requisition_no: Optional[str] = None
    sales_order: Optional[str] = None
    creation_date: Optional[str] = None
    plan_loading_date: Optional[str] = None
    delivery_terms: Optional[str] = None
    container_plan: Optional[str] = None
    port_loading: Optional[str] = None
    port_discharge: Optional[str] = None
    outbound_id: Optional[str] = None
    items: List[ItemBlock] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    raw_lines: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """검증 통과 여부 (errors가 비어있고 필수 블록 존재)."""
        return len(self.errors) == 0


# -----------------------------------------------------------------------------
# 2) 정규화 유틸
# -----------------------------------------------------------------------------

def _to_float_num(s: str) -> float:
    """천 단위 콤마 제거 후 float."""
    if not s:
        return 0.0
    return float(s.replace(",", "").strip())


def _mt_to_kg(x: float) -> float:
    return x * 1000.0


# 리스트에 5001 kg으로 기재된 경우: 문서에는 적혀 있지 않지만 본품 500kg×10 + 샘플 1kg 포함으로 간주
NET_WEIGHT_IMPLICIT_SAMPLE_KG = 5001.0
MAIN_KG_WHEN_5001 = 5000.0
SAMPLE_KG_WHEN_5001 = 1.0


def decode_net_weight_kg(net_kg: Optional[float]) -> Tuple[float, float]:
    """
    LOT net이 5001 kg이면 본품 5000 kg(500kg×10) + 샘플 1 kg으로 해석.
    반환: (main_kg, sample_kg). 5001이 아니면 (net_kg, 0.0).
    """
    if net_kg is None:
        return 0.0, 0.0
    k = float(net_kg)
    if abs(k - NET_WEIGHT_IMPLICIT_SAMPLE_KG) < 0.01:
        return MAIN_KG_WHEN_5001, SAMPLE_KG_WHEN_5001
    return k, 0.0


def _parse_date_candidate(s: str) -> Optional[str]:
    """dd.mm.yyyy / dd-mm-yyyy / dd/mm/yyyy → YYYY-MM-DD 또는 원본 유지."""
    if not s or len(s) < 8:
        return None
    s = s.strip()
    for sep in (".", "-", "/"):
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                try:
                    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    if y > 1000 and 1 <= m <= 12 and 1 <= d <= 31:
                        return f"{y:04d}-{m:02d}-{d:02d}"
                except (ValueError, TypeError) as e:
                    logger.warning(f"[_parse_date_candidate] Suppressed: {e}")
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else None


# -----------------------------------------------------------------------------
# 3) 정규식 (라인 끝 고정·배치 문자열 보존)
# -----------------------------------------------------------------------------

# 자재코드 8자리 + 설명 + 끝쪽 (총량 + 단위 + 상태). desc는 비탐욕, 끝 3그룹 고정.
ITEM_LINE_RE = re.compile(
    r"^(?P<mat>\d{8})\s+(?P<desc>.+?)\s+"
    r"(?P<qty>[\d,]+\.?\d*)\s+"
    r"(?P<unit>MT|KG)\s+"
    r"(?P<status>\w+)\s*$",
    re.IGNORECASE,
)

# Quantity: 5.00 MT Batch number: 1125081447 Storage location: 1001 GY logistics
# batch_no는 문자열 보존(앞자리 0), sloc은 줄 끝까지
BATCH_LINE_RE = re.compile(
    r"^Quantity:\s*"
    r"(?P<qty>[\d,]+\.?\d*)\s*"
    r"(?P<unit>MT|KG)\s+"
    r"Batch number:\s*(?P<batch>\S+)\s+"
    r"Storage location:\s*(?P<sloc>.+)\s*$",
    re.IGNORECASE,
)

# 키워드 라인에서 숫자/값 추출
REQUISITION_RE = re.compile(r"Requisition\s+(?P<no>\d{4,6})", re.IGNORECASE)
# v8.5.6 [PATCH3-BUG4]: Outbound ID 자동 파싱 추가
OUTBOUND_ID_RE = re.compile(r"Outbound\s+ID\s+(?P<no>\d{5,12})", re.IGNORECASE)
SALES_ORDER_RE = re.compile(r"Sales order\s+(?P<no>\d{3,10})", re.IGNORECASE)
CUSTOMER_REF_RE = re.compile(r"Customer reference\s+(?P<ref>\S.+)", re.IGNORECASE)
PLAN_LOADING_RE = re.compile(r"Plan Loading Date\s+(?P<date>[\d./\-]+)", re.IGNORECASE)
PORT_LOADING_RE = re.compile(r"Port of loading\s+(?P<port>\S.+)", re.IGNORECASE)
PORT_DISCHARGE_RE = re.compile(r"Port of discharge\s+(?P<port>\S.+)", re.IGNORECASE)
CONTAINER_RE = re.compile(r"(\d+\s*x\s*40\s*['']?\s*Containers?)", re.IGNORECASE)


# -----------------------------------------------------------------------------
# 4) 파서 (상태머신, 첫 페이지만 헤더 확정)
# -----------------------------------------------------------------------------

def parse_picking_text(all_text: str) -> PickingDoc:
    """
    Picking List 전체 텍스트를 파싱. 예외로 죽지 않으며, 실패 시 errors에 기록.
    """
    doc = PickingDoc()
    lines = [ln.strip() for ln in all_text.splitlines() if ln.strip()]
    doc.raw_lines = lines[:]  # 디버그 증거

    cur_item: Optional[ItemBlock] = None
    header_done = False

    for ln in lines:
        # ----- 헤더 (첫 번째 유효 매칭만) -----
        if not header_done:
            m = CUSTOMER_REF_RE.search(ln)
            if m and doc.customer_ref is None:
                doc.customer_ref = m.group("ref").strip()

            m = REQUISITION_RE.search(ln)
            if m and doc.requisition_no is None:
                doc.requisition_no = m.group("no")

            m = OUTBOUND_ID_RE.search(ln)
            if m and doc.outbound_id is None:
                try:
                    doc.outbound_id = m.group("no")   # str로 보관 (int 변환은 저장 시)
                except (ValueError, AttributeError) as _e:
                    logger.debug(f"[SUPPRESSED] exception in picking_list_parser.py: {_e}")  # noqa

            m = SALES_ORDER_RE.search(ln)
            if m and doc.sales_order is None:
                doc.sales_order = m.group("no")

            m = PLAN_LOADING_RE.search(ln)
            if m and doc.plan_loading_date is None:
                doc.plan_loading_date = _parse_date_candidate(m.group("date").strip()) or m.group("date").strip()

            m = PORT_LOADING_RE.search(ln)
            if m and doc.port_loading is None:
                doc.port_loading = m.group("port").strip()

            m = PORT_DISCHARGE_RE.search(ln)
            if m and doc.port_discharge is None:
                doc.port_discharge = m.group("port").strip()

            m = CONTAINER_RE.search(ln)
            if m and doc.container_plan is None:
                doc.container_plan = m.group(1).strip()

            # Creation date: dd.mm.yyyy 형태 단독 라인
            if re.match(r"^\d{2}[./\-]\d{2}[./\-]\d{4}$", ln) and doc.creation_date is None:
                doc.creation_date = _parse_date_candidate(ln) or ln

        # ----- Item 시작 (8자리 자재코드 + qty + MT/KG) -----
        m = ITEM_LINE_RE.match(ln)
        if m:
            header_done = True
            cur_item = ItemBlock(
                material_code=m.group("mat"),
                description=m.group("desc").strip(),
                total_qty=_to_float_num(m.group("qty")),
                total_unit=m.group("unit").upper(),
                customs_status=m.group("status"),
                batches=[],
            )
            doc.items.append(cur_item)
            continue

        # ----- Batch 라인 (직전 Item에 소속) -----
        mb = BATCH_LINE_RE.match(ln)
        if mb and cur_item is not None:
            header_done = True
            sloc = mb.group("sloc").strip()
            # "1001 GY logistics" → 1001만 쓰거나 전부 보존 (정책에 따라)
            if sloc and sloc.split()[0].isdigit():
                sloc = sloc.split()[0]
            cur_item.batches.append(BatchLine(
                batch_no=mb.group("batch").strip(),
                qty=_to_float_num(mb.group("qty")),
                unit=mb.group("unit").upper(),
                storage_location=sloc or None,
            ))
            continue

        # 라벨만 있는 줄(Quantity: 등) 다음에 오는 숫자 라인은 배치 보조로 쓸 수 있으나, 여기서는 한 줄 배치만 처리
        if ln == "PICKING LIST":
            continue

    # 최소 검증: 아이템이 하나도 없으면 에러
    if not doc.items:
        doc.errors.append("아이템 블록을 1개도 찾지 못했습니다(문서 포맷/OCR 확인 필요).")

    return doc


# -----------------------------------------------------------------------------
# 5) 하드스톱 검증 (정책 위반 시 errors에 추가)
# -----------------------------------------------------------------------------

def _validate_picking_doc(doc: PickingDoc) -> None:
    """
    본품/샘플 존재, 총량=배치합, 본품 배치=샘플 배치, Big bag 수량 등 7개 정책.
    doc.errors에만 추가하며 예외는 발생시키지 않음.
    """
    if not doc.items:
        return

    main = next(
        (it for it in doc.items if it.total_unit == "MT" and it.material_code == "30000008"),
        None,
    )
    samp = next(
        (it for it in doc.items if it.total_unit == "KG" and "SAMPLE" in (it.description or "").upper()),
        None,
    )

    if not main:
        doc.errors.append("본품(자재 30000008, MT)을 찾지 못했습니다.")
    else:
        main_sum = sum(b.qty for b in main.batches)
        if abs(main_sum - main.total_qty) > 1e-3:
            doc.errors.append(
                f"본품 배치 합({main_sum} MT) != 본품 총량({main.total_qty} MT)"
            )

    if not samp:
        doc.errors.append("샘플 아이템 블록을 찾지 못했습니다(정책상 필수).")
    else:
        samp_sum = sum(b.qty for b in samp.batches)
        if abs(samp_sum - samp.total_qty) > 1e-3:
            doc.errors.append(
                f"샘플 배치 합({samp_sum} KG) != 샘플 총량({samp.total_qty} KG)"
            )
        if main and samp:
            main_batches = {b.batch_no for b in main.batches}
            samp_batches = {b.batch_no for b in samp.batches}
            if main_batches != samp_batches:
                doc.errors.append("본품 배치와 샘플 배치가 1:1로 일치하지 않습니다.")


# -----------------------------------------------------------------------------
# 6) SQM picking_list_order / picking_list_detail 매칭
# -----------------------------------------------------------------------------

def to_sqm_picking_order_row(
    doc: PickingDoc,
    outbound_id: Optional[int] = None,
    status: str = "DRAFT",
    remarks: str = "",
) -> Dict[str, Any]:
    """
    PickingDoc → picking_list_order 한 행에 대응하는 dict.
    DB 컬럼명(snake_case)과 호환: id 제외, created_at/updated_at는 DB 기본값 사용.
    """
    main = next(
        (it for it in doc.items if it.total_unit == "MT" and it.material_code == "30000008"),
        None,
    )
    total_lots = len(main.batches) if main else 0
    total_weight_kg = _mt_to_kg(main.total_qty) if main else 0.0

    picking_date = doc.plan_loading_date or doc.creation_date or ""

    row = {
        "outbound_id": outbound_id,
        "outbound_id": (str(doc.outbound_id) if doc.outbound_id else ""),
        "sales_order": (doc.sales_order or "").strip(),
        "customer_ref": (doc.customer_ref or "").strip(),
        "picking_date": picking_date,
        "status": status,
        "total_lots": total_lots,
        "total_weight": total_weight_kg,
        "remarks": remarks.strip(),
    }
    return row


def to_sqm_picking_detail_rows(
    doc: PickingDoc,
    picking_order_id: int,
    bag_weight_kg: int = None,  # v8.6.1: None → DEFAULT_TONBAG_WEIGHT fallback
    include_decode_fields: bool = True,
) -> List[Dict[str, Any]]:
    """
    PickingDoc의 본품 배치 → picking_list_detail 행 목록.
    lot_no = batch_no(문자열), weight = 배치당 중량(kg), picked_status = PENDING.
    weight가 5001 kg이면 정책상 500kg×10 + 1kg 샘플 포함으로 해석하며,
    include_decode_fields=True일 때 main_weight_kg, sample_weight_kg, tonbag_count를 함께 넣음.
    """
    main = next(
        (it for it in doc.items if it.total_unit == "MT" and it.material_code == "30000008"),
        None,
    )
    if not main:
        return []

    rows = []
    for b in main.batches:
        qty_kg = _mt_to_kg(b.qty)
        main_kg, sample_kg = decode_net_weight_kg(qty_kg)
        tonbag_count = int(round(main_kg / (bag_weight_kg or DEFAULT_TONBAG_WEIGHT)))  # v8.6.1: None→DEFAULT

        row = {
            "picking_order_id": picking_order_id,
            "lot_no": b.batch_no,
            "sub_lt": None,
            "weight": round(qty_kg, 2),
            "picked_status": "PENDING",
            "picked_at": None,
            "remarks": (b.storage_location or "").strip(),
        }
        if include_decode_fields:
            row["main_weight_kg"] = round(main_kg, 2)
            row["sample_weight_kg"] = round(sample_kg, 2)
            row["tonbag_count"] = tonbag_count
        rows.append(row)
    return rows


# -----------------------------------------------------------------------------
# 7) 피킹 플랜 (컨테이너당 배치 분배, 선택)
# -----------------------------------------------------------------------------

def build_pick_plan(
    doc: PickingDoc,
    bag_weight_kg: int = 500,
    containers: Optional[int] = None,
) -> Dict[str, Any]:
    """
    본품 배치 → 톤백 수·샘플 kg 계산 후 컨테이너 수만큼 round-robin 분배.
    net 5001 kg이면 5000 kg(톤백 10개) + 샘플 1 kg으로 해석.
    """
    plan: Dict[str, Any] = {
        "header": {
            "customer_ref": doc.customer_ref,
            "sales_order": doc.sales_order,
            "requisition_no": doc.requisition_no,
            "plan_loading_date": doc.plan_loading_date,
            "container_plan": doc.container_plan,
        },
        "containers": [],
        "errors": list(doc.errors),
    }

    main = next(
        (it for it in doc.items if it.total_unit == "MT" and it.material_code == "30000008"),
        None,
    )
    if not main:
        plan["errors"].append("본품(30000008, MT)을 찾지 못했습니다.")
        return plan

    if containers is None and doc.container_plan:
        m = re.search(r"(\d+)\s*x\s*40", doc.container_plan, re.IGNORECASE)
        containers = int(m.group(1)) if m else 15
    if containers is None or containers < 1:
        containers = 15

    plan["containers"] = [
        {"container_index": i + 1, "batches": []}
        for i in range(containers)
    ]
    for idx, b in enumerate(main.batches):
        c = plan["containers"][idx % containers]
        qty_kg = _mt_to_kg(b.qty)
        main_kg, sample_kg = decode_net_weight_kg(qty_kg)
        tonbag_count = int(round(main_kg / (bag_weight_kg or DEFAULT_TONBAG_WEIGHT)))  # v8.6.1: None→DEFAULT
        c["batches"].append({
            "batch_no": b.batch_no,
            "main_qty_mt": b.qty,
            "main_qty_kg": main_kg,
            "total_net_kg": qty_kg,
            "tonbag_weight_kg": bag_weight_kg,
            "tonbag_count": tonbag_count,
            "sample_kg": sample_kg,
            "storage_location": b.storage_location,
        })
    return plan


# -----------------------------------------------------------------------------
# 8) PDF 진입점 (텍스트 추출 → 파싱, OCR 분기 준비)
# -----------------------------------------------------------------------------

def _extract_text_from_pdf(pdf_path: str) -> Tuple[str, List[str]]:
    """PDF에서 텍스트 추출. (텍스트, 에러 메시지 목록)."""
    errs: List[str] = []
    try:
        from core.pdf_engine import open_pdf
    except ImportError:
        errs.append("PyMuPDF(fitz)가 필요합니다: pip install pymupdf")
        return "", errs

    path = Path(pdf_path)
    if not path.exists():
        errs.append(f"파일이 없습니다: {pdf_path}")
        return "", errs

    doc = None
    try:
        doc = open_pdf(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text, errs
    except Exception as e:
        logger.debug("Picking List PDF 텍스트 추출 실패: %s", e)
        errs.append(f"PDF 텍스트 추출 실패: {e}")
        return "", errs
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception as _ce:
                logging.getLogger(__name__).debug(f"[PL파서] 문서 닫기 실패: {_ce}")


def parse_picking_list_pdf(pdf_path: str) -> PickingDoc:
    """
    Picking List PDF 파일을 파싱.
    텍스트가 충분하면 Text 파서, 부족하면 errors에 OCR 권장 메시지 추가.
    """
    text, extract_errors = _extract_text_from_pdf(pdf_path)
    doc = PickingDoc()
    doc.errors[:] = extract_errors

    if not text and extract_errors:
        return doc
    if not text:
        doc.errors.append("PDF에서 추출된 텍스트가 없습니다.")
        return doc

    if len(text.strip()) < MIN_TEXT_LENGTH_FOR_PARSE:
        doc.errors.append(
            "텍스트가 부족합니다. 이미지 PDF일 수 있으니 OCR 파서를 사용하세요."
        )

    parsed = parse_picking_text(text)
    doc.customer_ref = parsed.customer_ref
    doc.requisition_no = parsed.requisition_no
    doc.sales_order = parsed.sales_order
    doc.creation_date = parsed.creation_date
    doc.plan_loading_date = parsed.plan_loading_date
    doc.delivery_terms = parsed.delivery_terms
    doc.container_plan = parsed.container_plan
    doc.port_loading = parsed.port_loading
    doc.port_discharge = parsed.port_discharge
    doc.items = parsed.items
    doc.raw_lines = parsed.raw_lines
    doc.errors.extend(parsed.errors)

    _validate_picking_doc(doc)
    return doc
