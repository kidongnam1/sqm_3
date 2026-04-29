"""
SQM 피킹리스트 PDF 파서 — 최종 로직 (라벨-라인 기반, 하드스톱 검증)
================================================================
파일: parsers/document_parser_modular/picking_mixin.py

문서 구조(고정 패턴):
  - Header: PICKING LIST, Customer reference(LBM-LC20250901), Requisition(3073),
    Sales order(80007418), Creation Date, Delivery terms, Ports, Containers(15 x40')
  - 본품: Quantity: 5.00 MT → Batch number: ... → Storage location: ...
  - 샘플: Quantity: 1.00 KG → Batch number: ... (동일 LOT)
  - 요약: Net 300,000.00 KG / Gross 307,800.00 KG, Big bag 500kg net 600ea

파이프라인: PDF/Text 추출 → 블록(줄) 목록 → Quantity/Batch/Storage 파싱 → 메타 파싱
            → 정규화(MT→kg, 콤마 제거) → 하드스톱 검증 → success/errors
"""
from engine_modules.constants import STATUS_PICKED
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

UNIT_WEIGHT_KG = 500  # Big bag 500kg net (문서 기준)

# 파서가 기대하는 라벨 패턴
RE_QUANTITY = re.compile(
    r'^Quantity:\s*([\d,.]+)\s*(MT|KG)\s*$',
    re.IGNORECASE
)
RE_BATCH_NUMBER = re.compile(r'Batch number:\s*(.+)', re.IGNORECASE)
RE_STORAGE_LOCATION = re.compile(r'Storage location:\s*(.+)', re.IGNORECASE)
RE_LARGE_KG = re.compile(r'([\d,]+\.?\d*)\s*KG\b', re.IGNORECASE)


def _normalize_num(s: str) -> float:
    """천단위 구분자 제거 후 float. 유럽식(점=천단위, 콤마=소수) 자동 감지.
    
    예시:
        '300.000,00' → 300000.0  (유럽식)
        '1.234,56'   → 1234.56   (유럽식)
        '5,000.00'   → 5000.0    (미국/한국식)
        '5.00'       → 5.0       (소수점)
        ''           → 0.0
    """
    if not s or not isinstance(s, str):
        return 0.0
    s = s.strip()
    try:
        # ★ S4-4: 유럽식 감지 — 콤마가 마지막 구분자이고 점이 그 앞에 있으면 유럽식
        # 패턴: 숫자.숫자.숫자,숫자  또는  숫자.숫자,숫자
        if re.search(r'\d\.\d{3}[,]', s):
            # 유럽식: 점=천단위 제거, 콤마→점
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s and '.' in s:
            # 미국식: 콤마=천단위 제거 (점이 소수점)
            last_comma = s.rfind(',')
            last_dot = s.rfind('.')
            if last_dot > last_comma:
                # 미국식: 5,000.00
                s = s.replace(',', '')
            else:
                # 유럽식: 5.000,00
                s = s.replace('.', '').replace(',', '.')
        elif ',' in s and '.' not in s:
            # 콤마만 있음: 천단위 또는 소수점 판단
            parts = s.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # 소수점 가능성: 1234,56 → 1234.56
                s = s.replace(',', '.')
            else:
                # 천단위: 1,234,567 → 1234567
                s = s.replace(',', '')
        else:
            # 콤마 없음: 점만 또는 순수 숫자
            pass
        # 공백/기타 제거
        s = re.sub(r'[\s]', '', s)
        return float(s)
    except (ValueError, TypeError):
        return 0.0


@dataclass
class PickingListMeta:
    picking_no:        str = ''
    sales_order:       str = ''
    outbound_id:       str = ''
    creation_date:     str = ''
    delivery_terms:    str = ''
    containers:        str = '1'
    cutoff_date:       str = ''
    plan_loading_date: str = ''
    contact_person:    str = ''
    contact_email:     str = ''
    port_loading:      str = ''
    port_discharge:    str = ''
    total_nw_kg:       str = ''
    total_gw_kg:       str = ''
    # v8.6.1: big bag 실측 무게 (PDF에서 자동 감지)
    bag_weight_kg:     int = 0     # 0 = 미감지(fallback 500 사용), 450/500/1000 등


@dataclass
class PickingLotItem:
    lot_no:    str
    weight_kg: float
    unit:      str   # 'MT' | 'KG'
    storage:   str = ''


@dataclass
class PickingListResult:
    meta:    PickingListMeta           = field(default_factory=PickingListMeta)
    tonbag:  List[PickingLotItem]      = field(default_factory=list)
    sample:  List[PickingLotItem]      = field(default_factory=list)
    summary: Dict                      = field(default_factory=dict)
    errors:  List[str]                 = field(default_factory=list)
    warnings: List[str]                = field(default_factory=list)
    success: bool                      = False


class PickingListParserMixin:
    """
    피킹리스트 파서 — 절대 예외로 죽지 않음. 실패 시 result.errors + success=False.

    진입점:
      - parse_picking_list(pdf_path)  : PDF 파일
      - parse_from_text(all_text)    : 이미 추출된 텍스트(OCR 등)
    """

    def _strict_mode(self, key: str, default: bool = False) -> bool:
        """
        항목별 strict 여부를 ENV로 제어.
        예: SQM_PICKING_STRICT_TONBAG_5MT=true
        """
        raw = str(os.environ.get(f'SQM_PICKING_STRICT_{key.upper()}', '')).strip().lower()
        if raw in ('1', 'true', 'yes', 'on', 'y'):
            return True
        if raw in ('0', 'false', 'no', 'off', 'n'):
            return False
        return default

    @staticmethod
    def _append_issue(result: PickingListResult, message: str, strict: bool) -> None:
        if strict:
            result.errors.append(message)
            return
        result.warnings.append(message)

    def parse_picking_list(self, pdf_path: str) -> PickingListResult:
        """PDF에서 텍스트 추출 후 파싱. 추출 실패 시 errors에 메시지."""
        result = PickingListResult()
        try:
            blocks = self._extract_pdf_blocks(pdf_path)
            if not blocks:
                result.errors.append('PDF 텍스트 추출 실패')
                return result
            return self._parse_blocks(blocks)
        except (OSError, ValueError, TypeError) as e:
            result.errors.append(f'파싱 예외: {e}')
            logger.debug(f'Suppressed: {e}')
            return result

    def parse_from_text(self, all_text: str) -> PickingListResult:
        """이미 추출된 전체 텍스트로 파싱(OCR/외부 추출 결과용)."""
        if not all_text or not all_text.strip():
            r = PickingListResult()
            r.errors.append('입력 텍스트가 비어 있습니다')
            return r
        blocks = [ln.strip() for ln in all_text.splitlines() if ln.strip()]
        return self._parse_blocks(blocks)

    def _parse_blocks(self, blocks: List[str]) -> PickingListResult:
        """공통: 블록(줄) 목록 → 파싱 → 정규화 → 하드스톱 검증 → Result."""
        result = PickingListResult()
        try:
            all_items = self._parse_quantity_blocks(blocks)
            result.tonbag = self._dedup(all_items, 'MT')
            result.sample = self._dedup(all_items, 'KG')
            result.meta = self._parse_meta(blocks)
            self._validate_hard_stops(result)
            total_mt = sum(r.weight_kg for r in result.tonbag) / 1000.0
            total_spkg = sum(r.weight_kg for r in result.sample)
            tb_set = {r.lot_no for r in result.tonbag}
            result.summary = {
                'total_lots':    len(tb_set),
                'total_mt':     total_mt,
                'total_sample_kg': total_spkg,
                'lot_integrity': tb_set == {s.lot_no for s in result.sample},
                'tonbag_count':  len(result.tonbag),
                'sample_count':  len(result.sample),
                'warning_count': len(result.warnings),
            }
            result.success = len(result.errors) == 0
            if result.success:
                logger.info(
                    f'[PickingParser] 파싱 완료: {len(tb_set)} LOT / '
                    f'{total_mt:.1f} MT / 샘플 {total_spkg:.0f} kg'
                )
        except (ValueError, TypeError) as e:
            result.errors.append(f'파싱 중 오류: {e}')
            logger.debug(f'Suppressed: {e}')
        return result

    def _validate_hard_stops(self, result: PickingListResult) -> None:
        """하드스톱 검증. 위반 시 result.errors에 추가."""
        tb = result.tonbag
        sp = result.sample
        tb_set = {r.lot_no for r in tb}
        sp_set = {s.lot_no for s in sp}

        if not tb:
            result.errors.append('본품(톤백) 배치가 없습니다. 문서 형식 또는 OCR을 확인하세요.')
        if not sp:
            result.errors.append('샘플 배치가 없습니다. 문서 형식 또는 OCR을 확인하세요.')

        if tb_set - sp_set:
            self._append_issue(
                result,
                f'샘플 없는 톤백 LOT {len(tb_set - sp_set)}개: {sorted(tb_set - sp_set)[:5]}...',
                strict=self._strict_mode('lot_integrity', default=False),
            )
        if sp_set - tb_set:
            self._append_issue(
                result,
                f'톤백 없는 샘플 LOT {len(sp_set - tb_set)}개: {sorted(sp_set - tb_set)[:5]}...',
                strict=self._strict_mode('lot_integrity', default=False),
            )

        sum_tonbag_kg = sum(r.weight_kg for r in tb)
        sum_sample_kg = sum(s.weight_kg for s in sp)
        if tb and abs(sum_tonbag_kg - len(tb) * 5000.0) > 1.0:
            expected_per_lot = sum_tonbag_kg / len(tb) if len(tb) else 0
            if expected_per_lot and abs(expected_per_lot - 5000.0) > 100.0:
                self._append_issue(
                    result,
                    f'본품 배치당 중량 이상: 합계 {sum_tonbag_kg:.0f} kg, {len(tb)} LOT (기대: 5 MT/LOT)',
                    strict=self._strict_mode('tonbag_5mt', default=False),
                )
        if sp and abs(sum_sample_kg - len(sp) * 1.0) > 0.01:
            self._append_issue(
                result,
                f'샘플 배치 합계 불일치: {sum_sample_kg:.2f} kg (기대: {len(sp)} kg, 1 kg/LOT)',
                strict=self._strict_mode('sample_1kg', default=False),
            )

        total_nw = result.meta.total_nw_kg
        if total_nw:
            nw_val = _normalize_num(RE_LARGE_KG.search(total_nw).group(1) if RE_LARGE_KG.search(total_nw) else total_nw)
            if nw_val > 100000 and abs(sum_tonbag_kg - nw_val) > 0.01 * nw_val:
                self._append_issue(
                    result,
                    f'본품 총량 불일치: 배치 합 {sum_tonbag_kg:.0f} kg vs 문서 NW {total_nw.strip()}',
                    strict=self._strict_mode('nw_total', default=False),
                )
        expected_bags = round(sum_tonbag_kg / UNIT_WEIGHT_KG)
        if tb and expected_bags > 0 and abs(expected_bags - len(tb) * 10) > len(tb):
            self._append_issue(
                result,
                f'Big bag 수 불일치: 예상 {expected_bags}ea (500kg net 기준) vs LOT당 10백 기대',
                strict=self._strict_mode('bigbag_count', default=False),
            )

    def _extract_pdf_blocks(self, pdf_path: str) -> List[str]:
        """PDF 텍스트 추출. (…)Tj 우선, 실패 시 PyMuPDF 줄 단위 폴백."""
        try:
            with open(pdf_path, 'rb') as f:
                raw = f.read().decode('latin-1', errors='replace')
            blocks = re.findall(r'\(([^)]+)\)Tj', raw)
            if blocks:
                return blocks
            try:
                from core.pdf_engine import open_pdf
                doc = open_pdf(pdf_path)
                lines = []
                for page in doc:
                    lines.extend(page.get_text().splitlines())
                doc.close()
                blocks = [ln.strip() for ln in lines if ln.strip()]
                if blocks:
                    logger.debug(f'[PickingParser] PyMuPDF 폴백으로 {len(blocks)} 블록 추출')
                    return blocks
            except Exception as e:
                logger.debug(f'Suppressed: {e}')
            return []
        except OSError as e:
            logger.error(f'PDF 읽기 실패: {e}')
            return []

    def _parse_quantity_blocks(self, blocks: List[str]) -> List[PickingLotItem]:
        """라벨-라인 순차: Quantity: X MT/KG → Batch number: → Storage location:."""
        items: List[PickingLotItem] = []
        i = 0
        while i < len(blocks):
            line = blocks[i].strip()
            qty_m = RE_QUANTITY.match(line)
            if not qty_m:
                i += 1
                continue
            qty_val = _normalize_num(qty_m.group(1))
            unit = qty_m.group(2).upper()
            weight_kg = qty_val * 1000.0 if unit == 'MT' else qty_val
            lot_no = ''
            storage = ''
            if i + 1 < len(blocks):
                bn = RE_BATCH_NUMBER.match(blocks[i + 1].strip())
                if bn:
                    lot_no = bn.group(1).strip()
                    i += 1
            if i + 1 < len(blocks):
                sl = RE_STORAGE_LOCATION.match(blocks[i + 1].strip())
                if sl:
                    storage = sl.group(1).strip()
                    i += 1
            if lot_no:
                items.append(PickingLotItem(lot_no=lot_no, weight_kg=weight_kg, unit=unit, storage=storage))
            i += 1
        return items

    def _dedup(self, items: List[PickingLotItem], unit: str) -> List[PickingLotItem]:
        """동일 lot_no + unit 첫 번째만 유지."""
        seen: Dict[str, PickingLotItem] = {}
        for it in items:
            if it.unit == unit and it.lot_no not in seen:
                seen[it.lot_no] = it
        return list(seen.values())

    def _parse_meta(self, blocks: List[str]) -> PickingListMeta:
        """v9.1: PICKING LIST 헤더 라벨 기반 파싱 (고정 인덱스 제거).

        SAP Picking List 구조:
          라벨: Outbound ID / Sales order / Customer reference 등
          값:   라벨 오른쪽 또는 다음 줄
        """
        meta = PickingListMeta()

        import re as _re

        # 라벨→값 매핑 (라벨명: 다음 토큰 또는 같은 줄 오른쪽)
        LABEL_MAP = {
            'Outbound ID':        'outbound_id',
            'Sales order':        'sales_order',
            'Customer reference': 'picking_no',   # picking_no로 저장
            'Creation Date':      'creation_date',
            'Plan Loading Date':  'plan_loading_date',
            'Cut-Off Date':       'cutoff_date',
            'Delivery terms':     'delivery_terms',
            'Containers':         'containers',
            'Contact person':     'contact_person',
            'E-mail':             'contact_email',
            'Port of loading':    'port_loading',
            'Port of discharge':  'port_discharge',
        }

        full_text = '\n'.join(blocks)
        lines = [b.strip() for b in blocks if b.strip()]

        for label, attr in LABEL_MAP.items():
            # 패턴: "라벨명 값" 또는 "라벨명\n값"
            pat = _re.compile(
                _re.escape(label) + r'[\s:]*([^\n]+)',
                _re.IGNORECASE
            )
            m = pat.search(full_text)
            if m:
                val = m.group(1).strip()
                # 날짜 정규화: DD.MM.YYYY → YYYY-MM-DD
                dm = _re.match(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', val)
                if dm:
                    val = f"{dm.group(3)}-{dm.group(2).zfill(2)}-{dm.group(1).zfill(2)}"
                setattr(meta, attr, val)

        # NW/GW: 200,000 kg 이상 KG 라인
        for b in blocks:
            m = RE_LARGE_KG.search(b)
            if m:
                val = _normalize_num(m.group(1))
                if val > 200000:
                    line = b.strip()
                    if not meta.total_nw_kg:
                        meta.total_nw_kg = line
                    elif not meta.total_gw_kg:
                        meta.total_gw_kg = line

        # v8.6.1 [Q2-BAG-WEIGHT]: big bag 실측 무게 자동 감지
        # "big bags 450 kgs" / "big bag 500 kgs" / "Big bag 1000 kgs" 패턴 인식
        # → UNIT_WEIGHT_KG(500) 하드코딩 대신 PDF 실측값 우선 사용
        _bag_wt_re = _re.compile(
            r'big\s+bag[s]?\s+([\d,]+)\s*kg', _re.IGNORECASE
        )
        for b in blocks:
            bm = _bag_wt_re.search(b)
            if bm:
                try:
                    wt = int(float(bm.group(1).replace(',', '')))
                    if 100 <= wt <= 2000:   # 합리적 범위: 100~2000kg
                        meta.bag_weight_kg = wt
                        break
                except (ValueError, TypeError) as _e:
                    logger.debug(f"[SUPPRESSED] exception in picking_mixin.py: {_e}")  # noqa

        return meta

    def build_pick_plan(
        self,
        result: PickingListResult,
        bag_weight_kg: int = UNIT_WEIGHT_KG,
        container_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        피킹 결과 → 컨테이너별 배치/톤백/샘플 배분(결정론적 round-robin).
        result.summary, result.meta.containers 사용. 검증 실패 시 plan['errors']에만 추가.
        """
        plan: Dict[str, Any] = {
            'header': {
                'picking_no': result.meta.picking_no,
                'sales_order': result.meta.sales_order,
                'total_mt': result.summary.get('total_mt', 0),
                'total_sample_kg': result.summary.get('total_sample_kg', 0),
                # v8.6.1: big bag 무게 전달 (PDF 감지값 우선)
                'bag_weight_kg': result.meta.bag_weight_kg or bag_weight_kg,
            },
            'containers': [],
            'errors': list(result.errors),
        }
        if not result.tonbag:
            plan['errors'].append('본품 톤백 없음 — 플랜 생성 불가')
            return plan
        n_containers = container_count
        if n_containers is None and result.meta.containers:
            num_match = re.search(r'(\d+)', result.meta.containers)
            n_containers = int(num_match.group(1)) if num_match else 15
        if n_containers is None or n_containers < 1:
            n_containers = 15
        plan['header']['container_count'] = n_containers
        plan['containers'] = [{'container_index': i + 1, 'batches': []} for i in range(n_containers)]
        for idx, item in enumerate(result.tonbag):
            c = plan['containers'][idx % n_containers]
            qty_kg = item.weight_kg
            tonbag_count = max(1, round(qty_kg / bag_weight_kg))
            c['batches'].append({
                'batch_no': item.lot_no,
                'main_qty_kg': qty_kg,
                'tonbag_weight_kg': bag_weight_kg,
                'tonbag_count': tonbag_count,
                'sample_kg': 1.0,
                'storage_location': item.storage,
            })
        return plan

    def expand_tonbags(
        self,
        result: PickingListResult,
        unit_weight: int = UNIT_WEIGHT_KG,
    ) -> List[Dict]:
        """LOT 단위 톤백/샘플을 개별 행으로 분해(기존 출고 실행 호환)."""
        rows: List[Dict] = []
        for item in result.tonbag:
            count = max(1, round(item.weight_kg / unit_weight))
            for sub in range(1, count + 1):
                rows.append({
                    'type': 'TONBAG',
                    'lot_no': item.lot_no,
                    'sub_lt': sub,
                    'weight_kg': unit_weight,
                    'storage': item.storage,
                    'status': STATUS_PICKED,
                })
        sp_lots = {s.lot_no for s in result.sample}
        for item in result.tonbag:
            if item.lot_no in sp_lots:
                rows.append({
                    'type': 'SAMPLE',
                    'lot_no': item.lot_no,
                    'sub_lt': 0,
                    'weight_kg': 1,
                    'storage': item.storage,
                    'status': STATUS_PICKED,
                })
        return rows

    # =========================================================
    # [COORD-PARSER v2.0 2026-04-29] pdfplumber 좌표 기반 파서
    # =========================================================

    _COORD_SHIFT_H = 4.0
    _COORD_SHIFT_V = 2.5
    _COORD_ROW_PX  = 5

    def parse_picking_list_coord(self, pdf_path, fallback=True):
        # 1차 좌표 파싱, 실패시 regex 폴백
        result = PickingListResult()
        all_words = []
        try:
            all_words = self._coord_extract_words(pdf_path)
        except Exception as exc:
            logger.warning("[PL-COORD] pdfplumber 실패: %s", exc)

        if all_words:
            try:
                self._coord_fill_result(all_words, result)
            except Exception as exc:
                logger.warning("[PL-COORD] 좌표 파싱 오류: %s", exc)
                result.errors.append("[PL-COORD-ERR] " + str(exc))

        if fallback and not result.tonbag:
            logger.info("[PL-COORD] 좌표 결과 0개 -> regex 폴백")
            try:
                fb = self.parse_picking_list(pdf_path)
                if fb.tonbag:
                    return fb
            except Exception as exc:
                logger.debug("[PL-COORD] 폴백 실패: %s", exc)

        try:
            self._validate_hard_stops(result)
            tb_set = {r.lot_no for r in result.tonbag}
            total_mt = sum(r.weight_kg for r in result.tonbag) / 1000.0
            total_spkg = sum(r.weight_kg for r in result.sample)
            result.summary = {
                "total_lots":      len(tb_set),
                "total_mt":        total_mt,
                "total_sample_kg": total_spkg,
                "lot_integrity":   tb_set == {s.lot_no for s in result.sample},
                "tonbag_count":    len(result.tonbag),
                "sample_count":    len(result.sample),
                "warning_count":   len(result.warnings),
            }
            result.success = len(result.errors) == 0
        except Exception as exc:
            result.errors.append("[PL-COORD-VALIDATE] " + str(exc))

        return result

    def _coord_extract_words(self, pdf_path):
        # pdfplumber 전 페이지 단어 추출
        import pdfplumber
        words = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                W = float(page.width)
                H = float(page.height)
                for w in (page.extract_words() or []):
                    words.append({
                        "text":   w["text"],
                        "x0":     float(w["x0"]),
                        "top":    float(w["top"]),
                        "x1":     float(w["x1"]),
                        "bottom": float(w["bottom"]),
                        "page":   page_idx,
                        "W":      W,
                        "H":      H,
                    })
        return words

    def _coord_fill_result(self, all_words, result):
        p0 = [w for w in all_words if w["page"] == 0]
        if p0:
            W = p0[0]["W"]
            H = p0[0]["H"]
            result.meta = self._coord_parse_header(p0, W, H)
        lines = self._coord_build_lines(all_words)
        self._coord_parse_batch_lines(lines, result)

    def _coord_parse_header(self, words, W, H):
        # 픽셀 단위 정밀 헤더 추출 (v2.1 2026-04-29)
        # 전략: 라벨 키워드 단어의 exact top(px) 를 앵커로,
        #        같은 행(±ROW_PX px) + 지정 x% 범위에서 값 추출
        # SHIFT_H 만 라벨 x 범위에 적용 (y 는 픽셀 단위로 타이트하게)
        import re as _r
        meta = PickingListMeta()
        sh = self._COORD_SHIFT_H  # x % 허용 (라벨 탐색용)
        row_tol = self._COORD_ROW_PX  # 동일 행 인정 픽셀 (기본 5px)

        def find_label_top(keyword, lx1_pct, lx2_pct):
            # 라벨 키워드 단어 중 x% 범위에 맞는 것의 top(px) 반환
            kw = keyword.lower()
            for w in sorted(words, key=lambda ww: ww["top"]):
                if kw not in w["text"].lower():
                    continue
                xp = w["x0"] / W * 100
                if (lx1_pct - sh) <= xp <= (lx2_pct + sh):
                    return w["top"]  # px
            return None

        def row_val(keyword, lx1_pct, lx2_pct, vx1_pct, vx2_pct):
            # 라벨 행의 top(px) 기준으로 같은 행 값 추출
            sh_v = self._COORD_SHIFT_H
            top_px = find_label_top(keyword, lx1_pct, lx2_pct)
            if top_px is None:
                return ""
            hits = sorted(
                [w for w in words
                 if abs(w["top"] - top_px) <= row_tol
                 and (vx1_pct - sh_v) <= w["x0"] / W * 100 <= (vx2_pct + sh_v)],
                key=lambda ww: ww["x0"],
            )
            return " ".join(ww["text"] for ww in hits).strip()

        def norm_date(s):
            m = _r.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
            if m:
                return "%s-%s-%s" % (m.group(3), m.group(2).zfill(2), m.group(1).zfill(2))
            return s

        # 좌측 열: 라벨 x=0~15%, 값 x=17~33%
        # row_val(keyword, lbl_x1, lbl_x2, val_x1, val_x2)
        meta.outbound_id       = row_val("Outbound",    0, 15, 17, 32)
        meta.sales_order       = row_val("Sales",       0, 12, 17, 32)
        meta.picking_no        = row_val("Customer",    0, 15, 17, 43)   # Customer reference
        meta.creation_date     = norm_date(row_val("Creation",   0, 15, 17, 32))
        meta.plan_loading_date = norm_date(row_val("Plan",       0, 12, 17, 32))
        # Containers: 라벨 "Containers" x=0~15%, 값 "15 x40'" x=17~26%
        meta.containers        = row_val("Containers",  0, 15, 17, 20)   # "15 x40'" 범위 (vx2+SHIFT=24% < Containers 24.9%)
        # 우측 열: 라벨 x=44~58%, 값 x=60~82%
        # "loading" 앞에 Port of 가 붙는 위치 x≈51.7% → lbl_x1=44
        meta.port_loading      = row_val("loading",    44, 58, 60, 82)
        meta.port_discharge    = row_val("discharge",  44, 58, 60, 82)

        logger.debug(
            "[PL-COORD] 헤더: ob=%s so=%s ref=%s ld=%s",
            meta.outbound_id, meta.sales_order,
            meta.picking_no, meta.plan_loading_date,
        )
        return meta

    def _coord_build_lines(self, all_words):
        # 단어를 (page, top_bucket) 그룹으로 묶어 행 텍스트 리스트 반환
        from collections import defaultdict
        buckets = defaultdict(list)
        for w in all_words:
            key = (w["page"], round(w["top"] / self._COORD_ROW_PX))
            buckets[key].append(w)
        lines = []
        for key in sorted(buckets.keys()):
            row_words = sorted(buckets[key], key=lambda ww: ww["x0"])
            line = " ".join(ww["text"] for ww in row_words).strip()
            if line:
                lines.append(line)
        return lines

    def _coord_parse_batch_lines(self, lines, result):
        # Batch 행 추출: MT -> tonbag, KG -> sample
        import re as _r
        QTY_RE   = _r.compile(r"Quantity[:\s]+([\d,.]+)\s*(MT|KG)", _r.I)
        BATCH_RE = _r.compile(r"Batch\s*number[:\s]+([A-Za-z0-9\-]+)", _r.I)
        SLOC_RE  = _r.compile(r"Storage\s+location[:\s]+(.+?)(?:\s{2,}|$)", _r.I)
        seen_main = {}
        seen_samp = {}
        for line in lines:
            mq = QTY_RE.search(line)
            mb = BATCH_RE.search(line)
            if not (mq and mb):
                continue
            qty   = _normalize_num(mq.group(1))
            unit  = mq.group(2).upper()
            batch = mb.group(1).strip()
            ms = SLOC_RE.search(line)
            storage = ms.group(1).strip() if ms else ""
            weight_kg = qty * 1000.0 if unit == "MT" else qty
            item = PickingLotItem(lot_no=batch, weight_kg=weight_kg, unit=unit, storage=storage)
            if unit == "MT":
                if batch not in seen_main:
                    seen_main[batch] = item
            else:
                if batch not in seen_samp:
                    seen_samp[batch] = item
        result.tonbag = list(seen_main.values())
        result.sample = list(seen_samp.values())
        logger.debug(
            "[PL-COORD] 배치 추출: tonbag %d개 / sample %d개",
            len(result.tonbag), len(result.sample),
        )
