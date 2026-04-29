from __future__ import annotations
# -*- coding: utf-8 -*-
"""
SQM 재고관리 시스템 - Packing List 파서 Mixin
==============================================

v3.6.0: document_parser_v2.py에서 분리

모듈 개요:
    Packing List(포장명세서) PDF를 파싱합니다.
    
추출 항목:
    - Folio: 3770868
    - Product: LITHIUM CARBONATE
    - Packing: MX 500 Kg
    - Code: MIC9000.00/500 KG
    - Vessel: CHARLOTTE MAERSK 535W
    - LOT 상세: 컨테이너, LOT NO, 중량 등

작성자: Ruby (남기동)
버전: v3.6.0
"""

import logging
import os
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Gemini API
try:
    HAS_NEW_GENAI = True
except ImportError:
    HAS_NEW_GENAI = False


class PackingMixin:
    """
    Packing List 파서 Mixin
    
    포장명세서 PDF에서 LOT 목록, 중량, 컨테이너 정보를 추출합니다.
    Gemini API 사용 가능 시 우선 사용합니다.
    
    Example:
        >>> class MyParser(PackingMixin, DocumentParserBase):
        ...     pass
        >>> parser = MyParser(gemini_api_key='your_key')
        >>> packing = parser.parse_packing_list('packing.pdf')
    """
    

    def _validate_pl_rows(self, result) -> list:
        """
        Ruby v2: PL 25케이스(T026~T050) 대응 후처리 검증
        반환: 경고 메시지 리스트 (비어있으면 정상)
        """
        warnings = []
        rows = getattr(result, 'rows', []) or getattr(result, 'lots', [])
        if not rows:
            warnings.append("[T026/T027] PL LOT 행이 0개 — 파싱 실패 의심")
            return warnings

        # ── T028/T029: 합계행·누적행이 상세행으로 섞임 감지 ─────────────
        # lot_no가 공백이거나 'TOTAL'/'ACCUMULATED' 패턴이면 합계행으로 판단
        SUMMARY_PAT = re.compile(r"^(total|accumulated|합계|소계|sum)", re.I)
        clean_rows = []
        for r in rows:
            lot_no = str(getattr(r, 'lot_no', '') or getattr(r, 'lot_sqm', '') or '').strip()
            if SUMMARY_PAT.match(lot_no) or not lot_no:
                warnings.append(f"[T028/T029] 합계/누적 행으로 의심되는 행 감지: lot_no='{lot_no}'")
            else:
                clean_rows.append(r)

        # ── T030: MXBG 열 매핑 오류 — 음수 또는 0인 tonbag 감지 ─────────
        for r in clean_rows:
            tb = getattr(r, 'mxbg_pallet', None) or getattr(r, 'tonbag_count', None)
            if tb is not None:
                try:
                    tb_f = float(tb)
                    if tb_f <= 0:
                        warnings.append(
                            f"[T030/T040/T041] LOT {getattr(r,'lot_no','')} tonbag={tb} — "
                            f"0이하 또는 오인식 의심"
                        )
                    elif tb_f in (1.0, 2.0) and len(clean_rows) > 1:
                        # 10→1, 20→2 오인식 의심 (전체 LOT가 2개 이하가 아닌 경우)
                        warnings.append(
                            f"[T040/T041] LOT {getattr(r,'lot_no','')} tonbag={tb} — "
                            f"10→1 또는 20→2 오인식 의심"
                        )
                except (ValueError, TypeError):
                    logger.debug("[SUPPRESSED] exception in packing_mixin.py")  # noqa

        # ── T038/T039: 중량 오인식 감지 (500→5000, 1000→100) ────────────
        for r in clean_rows:
            nw = getattr(r, 'net_weight', None) or getattr(r, 'net_weight_kg', None)
            if nw is not None:
                try:
                    nw_f = float(str(nw).replace(',', ''))
                    # v8.0.6: LOT 전체 무게 기준 수정
                    # net_weight = LOT 전체(톤백합+샘플) — 500kg×10개=5001kg 정상
                    # 실제 오인식은 50,000kg 초과인 경우 (톤백 1000kg×20개 최대=20,001kg)
                    if nw_f > 50000:
                        warnings.append(
                            f"[T038] LOT {getattr(r,'lot_no','')} net_weight={nw} — "
                            f"LOT 전체 무게 50,000kg 초과, 오인식 의심"
                        )
                    # v8.0.6: LOT 전체 무게 기준 — 톤백 없이 샘플만(1kg)이면 정상
                    # 실제 오인식은 2kg 미만인 경우만 (샘플 1kg 제외)
                    elif 0 < nw_f < 2:
                        warnings.append(
                            f"[T039] LOT {getattr(r,'lot_no','')} net_weight={nw} — "
                            f"1000→100 오인식 의심 (100kg 미만)"
                        )
                except (ValueError, TypeError):
                    logger.debug("[SUPPRESSED] exception in packing_mixin.py")  # noqa

        # ── T034/T035: 컨테이너 공백 행 감지 ────────────────────────────
        has_container = False
        for r in clean_rows:
            cont = str(getattr(r, 'container', '') or getattr(r, 'container_no', '') or '').strip()
            if cont:
                has_container = True
                break
        if not has_container:
            warnings.append("[T034] 모든 LOT 행의 컨테이너 값이 비어있음")

        # ── T049: 하단 요약 합계 vs rows 합계 불일치 ─────────────────────
        declared_net = getattr(result, 'total_net_weight_kg', None)
        if declared_net and clean_rows:
            computed_net = sum(
                float(str(getattr(r,'net_weight',0) or getattr(r,'net_weight_kg',0) or 0)
                      .replace(',',''))
                for r in clean_rows
            )
            if declared_net and abs(float(declared_net) - computed_net) > 5:
                warnings.append(
                    f"[T049] PL 요약 합계와 행 합계 불일치: "
                    f"요약={declared_net:,.1f}kg  행합={computed_net:,.1f}kg"
                )

        # ── T036: LOT 번호 자릿수 이상 감지 ─────────────────────────────
        for r in clean_rows:
            lot_no = str(getattr(r, 'lot_no', '') or '').strip()
            digits = re.sub(r'\D', '', lot_no)
            if digits and (len(digits) < 8 or len(digits) > 12):
                warnings.append(
                    f"[T036] LOT 번호 자릿수 이상: '{lot_no}' (숫자부 {len(digits)}자리)"
                )

        return warnings


    def _validate_required_packing_fields(self, result: object) -> None:
        """P3 (GPT PATCH15 채택): Packing List 핵심 필드 검증.
        LOT 번호 없음 / net_weight 0 이하 / 총중량 0 이하 시 RuntimeError.
        parse_packing_list 완료 직후 호출.
        """
        lots = list(getattr(result, 'lots', []) or [])
        if not lots:
            raise RuntimeError('[PACKING_LIST][P3] LOT 정보가 없습니다 — DB 저장 차단')

        invalid = []
        for lot in lots:
            lot_no     = str(getattr(lot, 'lot_no', '') or '').strip()
            net_weight = float(getattr(lot, 'net_weight_kg', 0) or 0)
            if not lot_no or net_weight <= 0:
                invalid.append({'lot_no': lot_no, 'net_weight_kg': net_weight})

        if invalid:
            sample = invalid[:3]
            raise RuntimeError(
                f'[PACKING_LIST][P3] 핵심 필드 누락/오류 {len(invalid)}건 '
                f'(lot_no 없음 또는 net_weight=0): {sample}'
            )

        # 총중량 재계산 (0이면 자동 보완)
        total_net = float(getattr(result, 'total_net_weight_kg', 0) or 0)
        if total_net <= 0:
            total_net = sum(
                float(getattr(lot, 'net_weight_kg', 0) or 0) for lot in lots
            )
            setattr(result, 'total_net_weight_kg', total_net)
        if total_net <= 0:
            raise RuntimeError('[PACKING_LIST][P3] total_net_weight_kg 계산 실패')

        logger.debug(f'[P3] PL 핵심 필드 검증 통과: {len(lots)}개 LOT, {total_net:,.1f}kg')


    def _parse_packing_list_coord(self, pdf_path: str,
                                   bag_weight_kg: int = None) -> "Optional[object]":  # v8.6.1: None → DEFAULT_TONBAG_WEIGHT
        """v9.1: SQM Packing List PyMuPDF 좌표 기반 파싱.

        Gemini API 불필요. SQM SALAR SpA 단일 발행 양식 고정.

        구조:
          헤더: 고정 좌표 (Folio, Product, Vessel, Packing, Customer, Code, Destination)
          데이터: LOT 10자리 숫자 탐지 → 같은 줄 컨테이너/중량 추출
        """
        from core.pdf_engine import open_pdf
        try:
            doc = open_pdf(pdf_path)
            all_words = []
            page_heights = []
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                W = page.rect.width
                H = page.rect.height
                page_heights.append(H)
                for w in page.get_text("words") or []:
                    all_words.append({
                        "text": str(w[4]).strip(),
                        "x0": float(w[0]), "x1": float(w[2]),
                        "top": float(w[1]), "bottom": float(w[3]),
                        "page": page_idx, "W": W, "H": H,
                    })
            doc.close()
        except (Exception, NameError) as e:
            logger.debug(f"[PL-COORD] PDF 읽기 실패: {e}")
            return None  # v8.5.6: 예외 시 None 반환 → Gemini 폴백

        # 1페이지 단어만 헤더 추출용
        p0 = [w for w in all_words if w["page"] == 0]
        W0 = p0[0]["W"] if p0 else 612.0
        H0 = p0[0]["H"] if p0 else 792.0

        def by_xy(words, x1, x2, y1, y2):
            hits = sorted(
                [w for w in words
                 if x1 <= w["x0"]/w["W"]*100 <= x2
                 and y1 <= w["top"]/w["H"]*100 <= y2],
                key=lambda x: x["x0"]
            )
            return " ".join(w["text"] for w in hits).strip()

        def parse_euro(s):
            s = re.sub(r"[^\d,.]", "", str(s or ""))
            if not s:
                return 0.0
            if "," in s and "." in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                s = s.replace(",", ".")
            try:
                return float(s)
            except (ValueError, TypeError):
                return 0.0

        # ── 헤더 추출 (1페이지 고정 좌표) ──────────────────────
        folio       = by_xy(p0, 82, 97, 5.5, 7.5)
        product     = by_xy(p0, 14, 35, 11.0, 12.5)
        vessel      = by_xy(p0, 62, 90, 11.0, 12.5)
        packing     = by_xy(p0, 14, 45, 13.2, 14.7)
        customer    = by_xy(p0, 62, 90, 13.2, 14.7)
        code        = by_xy(p0, 14, 35, 15.5, 17.0)
        destination = by_xy(p0, 62, 90, 15.5, 17.0)

        # ── LOT 행 스캔 (전 페이지) ────────────────────────────
        LOT_RE = re.compile(r"^\d{8,11}$")  # v8.6.4: 8~11자리 허용 (OCR 오독 대응)
        CT_RE  = re.compile(r"^[A-Z]{4}\d{3,}")
        lots   = []
        seen   = set()

        for w in sorted(all_words, key=lambda x: (x["page"], x["top"], x["x0"])):
            if not LOT_RE.match(w["text"]):
                continue
            lot_no = w["text"]
            if lot_no in seen:
                continue
            seen.add(lot_no)

            page_w = w["W"]
            page_h = w["H"]
            # 같은 줄 단어 (±3px)
            row = sorted(
                [ww for ww in all_words
                 if ww["page"] == w["page"]
                 and abs(ww["top"] - w["top"]) < 3],
                key=lambda x: x["x0"]
            )
            # 컨테이너: x=8~18%
            _ct_raw = next(
                (ww["text"] for ww in row
                 if 7 <= ww["x0"]/page_w*100 <= 19
                 and CT_RE.match(ww["text"])), ""
            )
            # Normalize check digit hyphen: TCLU640435-3 → TCLU6404353
            import re as _re_ct
            container = _re_ct.sub(r'^([A-Z]{4}\d+)-(\d)$', r'\1\2', _ct_raw)
            # LOT SQM: x=27~35% (6~7자리 — 실측 1015616 등)
            lot_sqm = next(
                (ww["text"] for ww in row
                 if 25 <= ww["x0"]/page_w*100 <= 36
                 and re.match(r"^\d{6,7}$", ww["text"])), ""
            )
            # MXBG 톤백 수: x=34~41%
            mxbg_tok = [ww["text"] for ww in row
                        if 33 <= ww["x0"]/page_w*100 <= 42
                        and re.match(r"^\d{1,3}$", ww["text"])]
            mxbg = int(mxbg_tok[0]) if mxbg_tok else 0

            # Net Weight: x=47~56%
            nw_tok = [ww["text"] for ww in row
                      if 46 <= ww["x0"]/page_w*100 <= 57]
            nw_raw = nw_tok[0] if nw_tok else ""
            net_weight_kg = parse_euro(nw_raw) * 1000 \
                            if parse_euro(nw_raw) < 1000 \
                            else parse_euro(nw_raw)

            # Gross Weight: x=55~64%
            gw_tok = [ww["text"] for ww in row
                      if 54 <= ww["x0"]/page_w*100 <= 65]
            gw_raw = gw_tok[0] if gw_tok else ""
            gross_weight_kg = parse_euro(gw_raw) * 1000 \
                              if parse_euro(gw_raw) < 1000 \
                              else parse_euro(gw_raw)

            # DEL N°: x=63~71%
            del_no = next(
                (ww["text"] for ww in row
                 if 62 <= ww["x0"]/page_w*100 <= 72
                 and re.match(r"^\d{7}$", ww["text"])), ""
            )
            # AL N°: x=71~80%
            al_no = next(
                (ww["text"] for ww in row
                 if 70 <= ww["x0"]/page_w*100 <= 81
                 and re.match(r"^\d{7}$", ww["text"])), ""
            )

            lots.append({
                "list_no":        len(lots) + 1,
                "container_no":   container,
                "lot_no":         lot_no,
                "lot_sqm":        lot_sqm,
                "mxbg":           mxbg,
                "net_weight_kg":  net_weight_kg,
                "gross_weight_kg": gross_weight_kg,
                "del_no":         del_no,
                "al_no":          al_no,
            })

        if not lots:
            return None  # Gemini 폴백 사용

        # ── PackingListData 조립 ───────────────────────────────
        from ..document_models import PackingListData, PackingListRow, LOTInfo
        from datetime import datetime

        result = PackingListData()
        result.source_file          = pdf_path
        result.parsed_at            = datetime.now()
        result.folio                = folio
        result.product              = product
        result.vessel               = vessel
        result.packing              = packing
        result.customer             = customer
        result.code                 = code
        result.destination          = destination
        result.bag_weight_kg        = bag_weight_kg
        # v8.5.6 [PATCH4]: SAP No 파일명 추출 안전화 (NameError 방지)
        try:
            _sap_m = re.search(r"(\d{8,11})", os.path.basename(pdf_path) or "") if pdf_path else None  # v8.6.4
            result.sap_no = _sap_m.group(1) if _sap_m else ""
        except Exception as exc:
            logger.debug("SAP No 파일명 추출 실패: %s", exc)
            result.sap_no = ""

        for lot in lots:
            row = PackingListRow(
                list_no       = lot["list_no"],
                container     = lot["container_no"],
                lot_no        = lot["lot_no"],
                lot_sqm       = lot["lot_sqm"],
                mxbg_pallet   = lot["mxbg"],
                plastic_jars  = 1,
                net_weight    = lot["net_weight_kg"],
                gross_weight  = lot["gross_weight_kg"],
                del_no        = lot["del_no"],
                al_no         = lot["al_no"],
            )
            result.rows.append(row)
            result.lots.append(LOTInfo(
                list_no         = lot["list_no"],
                container_no    = lot["container_no"],
                lot_no          = lot["lot_no"],
                lot_sqm         = lot["lot_sqm"],
                mxbg_pallet     = lot["mxbg"],
                plastic_jars    = 1,
                net_weight_kg   = lot["net_weight_kg"],
                gross_weight_kg = lot["gross_weight_kg"],
                del_no          = lot["del_no"],
                al_no           = lot["al_no"],
            ))

        result.total_lots          = len(result.lots)
        result.total_maxibag       = sum((r.mxbg_pallet or 0) for r in result.rows)
        result.total_plastic_jars  = result.total_lots
        result.containers          = sorted({r.container for r in result.rows if r.container})
        result.total_net_weight_kg = sum((r.net_weight or 0) for r in result.rows)
        result.total_gross_weight_kg = sum((r.gross_weight or 0) for r in result.rows)
        result.success             = len(result.lots) > 0
        result.error_message       = ""
        result.raw_response        = ""

        logger.info(
            f"[PL-COORD] 좌표 파싱 완료: {result.total_lots}개 LOT / "
            f"{result.total_net_weight_kg:,.0f}kg"
        )
        return result

    def parse_packing_list(self, pdf_path: str,
                           bag_weight_kg: int = None,  # v8.6.1: None → DEFAULT_TONBAG_WEIGHT
                           gemini_hint: str = '') -> Optional[object]:  # Ruby v2 / v7.3.0
        """
        Packing List PDF 파싱.

        Args:
            pdf_path:       Packing List PDF 파일 경로
            bag_weight_kg:  톤백 단가 (500 or 1000) — v7.2.0: 입고 템플릿에서 주입
            gemini_hint:    선사별 추가 힌트 — v7.3.0: Gemini 프롬프트에 주입

        Returns:
            PackingListData: 파싱 결과, 실패 시 None

        Note:
            v5.5.1부터 **모든 파싱은 API(Gemini) 강제** 정책입니다.
            - 키가 없으면 하드-스톱(예외)
            - 실패 시 정규식 폴백을 하지 않습니다.
        """
        from ..document_models import PackingListData, PackingListRow, LOTInfo  # type: ignore[misc]  # 패키지 경로 정상

        # ── v9.1: 좌표 기반 0단계 (SQM SALAR SpA 단일 양식) ─────────────
        # Gemini 없이 직접 추출. 실패 시 Gemini 폴백.
        try:
            _coord = self._parse_packing_list_coord(pdf_path, bag_weight_kg)
            if _coord and getattr(_coord, 'success', False):
                logger.info("[PACKING_LIST] 좌표 파싱 성공 — Gemini 건너뜀")
                return _coord
            logger.debug("[PACKING_LIST] 좌표 파싱 실패 → Gemini 폴백")
        except Exception as _ce:
            logger.debug(f"[PACKING_LIST] 좌표 파싱 예외(Gemini 폴백): {_ce}")

        # API-Only Gate (provider-agnostic)
        self._require_gemini_api_key()  # type: ignore[attr-defined]  # Mixin: 부모 클래스 메서드

        provider = getattr(self, 'provider', 'gemini') or 'gemini'  # type: ignore[attr-defined]
        logger.info(f"[PACKING_LIST] {provider.upper()} API로 파싱")
        gemini_result = self._parse_packing_with_ai(  # type: ignore[attr-defined]
            pdf_path,
            bag_weight_kg=bag_weight_kg,
            gemini_hint=gemini_hint,
            provider=provider,
        )

        if not gemini_result or not getattr(gemini_result, 'success', False) or len(getattr(gemini_result, 'lots', []) or []) == 0:
            msg = getattr(gemini_result, 'error_message', '') if gemini_result else ''
            # ── parse_packing_list_ai (ai_fallback.py) 2차 시도 ───────
            try:
                from .ai_fallback import parse_packing_list_ai
                logger.info("[PACKING_LIST] _parse_packing_with_ai 실패 → "
                            "parse_packing_list_ai(ai_fallback) 2차 시도")
                _partial = locals().get('_coord')  # 좌표 파싱 부분 결과
                _ai2 = parse_packing_list_ai(
                    self, pdf_path,
                    partial=_partial,
                    bag_weight_kg=bag_weight_kg,
                    provider=provider,
                )
                if _ai2 and getattr(_ai2, 'success', False) and \
                        len(getattr(_ai2, 'lots', []) or []) > 0:
                    logger.info("[PACKING_LIST] parse_packing_list_ai 2차 성공: "
                                "%d LOT", len(_ai2.lots))
                    return _ai2
                logger.warning("[PACKING_LIST] parse_packing_list_ai 2차도 실패")
            except Exception as _ai2_err:
                logger.debug("[PACKING_LIST] parse_packing_list_ai 2차 오류: %s", _ai2_err)
            raise RuntimeError(f"[PACKING_LIST] {provider.upper()} 파싱 실패. {msg}".strip())

        result = PackingListData()
        result.source_file = pdf_path
        result.parsed_at = datetime.now()
        result.folio = gemini_result.folio
        result.product = gemini_result.product
        result.packing = gemini_result.packing
        result.code = gemini_result.code
        result.vessel = gemini_result.vessel
        result.customer = gemini_result.customer
        result.destination = gemini_result.destination
        result.total_net_weight_kg = gemini_result.total_net_weight_kg
        result.total_gross_weight_kg = gemini_result.total_gross_weight_kg

        for lot in gemini_result.lots:
            row = PackingListRow(
                list_no=lot.list_no,
                container=lot.container_no,
                lot_no=lot.lot_no,
                lot_sqm=lot.lot_sqm,
                mxbg_pallet=lot.mxbg,
                plastic_jars=1,
                net_weight=lot.net_weight_kg,
                gross_weight=lot.gross_weight_kg,
                del_no=getattr(lot, 'del_no', '') or '',
                al_no=getattr(lot, 'al_no', '') or '',
            )
            result.rows.append(row)
            # LOTInfo로 정규화 (하위 로직에서 필드/정합성 검증이 흔들리지 않게)
            result.lots.append(LOTInfo(
                list_no=lot.list_no,
                container_no=lot.container_no,
                lot_no=lot.lot_no,
                lot_sqm=lot.lot_sqm,
                mxbg_pallet=lot.mxbg,
                plastic_jars=1,
                net_weight_kg=lot.net_weight_kg,
                gross_weight_kg=lot.gross_weight_kg,
                del_no=getattr(lot, 'del_no', '') or '',
                al_no=getattr(lot, 'al_no', '') or '',
            ))

        # 요약 값 보강
        result.total_lots = len(result.rows) or len(result.lots)
        result.total_maxibag = sum((r.mxbg_pallet or 0) for r in result.rows)
        result.total_plastic_jars = result.total_lots  # 정책: LOT당 1개
        result.containers = sorted({r.container for r in result.rows if r.container})
        result.bag_weight_kg = bag_weight_kg          # v7.2.0: 템플릿 단가 저장
        # v9.0 [Phase2]: PackingListResult → PackingListData 통합 필드 복사
        result.success = len(result.lots) > 0
        result.error_message = getattr(gemini_result, 'error_message', '') or ''
        result.raw_response = getattr(gemini_result, 'raw_response', '') or ''
        result.duplicate_skipped_lot_nos = list(
            getattr(gemini_result, 'duplicate_skipped_lot_nos', []) or []
        )
        # 총중량 요약(없으면 rows 합으로 보강)
        if not result.total_net_weight_kg:
            result.total_net_weight_kg = sum((r.net_weight or 0.0) for r in result.rows)
        if not result.total_gross_weight_kg:
            result.total_gross_weight_kg = sum((r.gross_weight or 0.0) for r in result.rows)

        # Ruby v2: PL 25케이스 후처리 검증
        _pl_warnings = self._validate_pl_rows(result)
        for _w in _pl_warnings:
            logger.warning(f"[PL_VALIDATE] {_w}")
        result.pl_warnings = _pl_warnings

        logger.info(f"[PACKING_LIST] {provider} 성공(API-Only): {result.total_lots}개 LOT")

        # P3: 핵심 필드 검증 (저장 전 차단)
        self._validate_required_packing_fields(result)
        return result

    def _parse_packing_with_ai(self, pdf_path: str, *, bag_weight_kg=None, gemini_hint: str = '', provider: str = 'gemini'):
        """선택된 AI provider로 Packing List 파싱. 실패 시 다음 provider로 폴백."""
        api_key = self._get_ai_key(provider)  # type: ignore[attr-defined]
        model = self._get_ai_model(provider)  # type: ignore[attr-defined]

        result = None

        if provider == 'gemini':
            try:
                from features.ai.gemini_parser import GeminiDocumentParser
                gp = GeminiDocumentParser(api_key)
                result = self._gemini_with_retry(  # type: ignore[attr-defined]
                    gp.parse_packing_list, pdf_path,
                    retries=3, wait_seconds=1.0,
                    bag_weight_kg=bag_weight_kg, gemini_hint=gemini_hint,
                )
            except Exception as e:
                logger.warning(f"[PACKING_LIST] Gemini 실패: {e}")

        elif provider == 'openai':
            try:
                from features.ai.openai_parser import try_parse_packing_list
                result = try_parse_packing_list(pdf_path, api_key=api_key, model=model or None)
            except Exception as e:
                logger.warning(f"[PACKING_LIST] OpenAI 실패: {e}")

        elif provider == 'anthropic':
            try:
                from features.ai.anthropic_parser import try_parse_packing_list
                result = try_parse_packing_list(pdf_path, api_key=api_key, model=model or None)
            except Exception as e:
                logger.warning(f"[PACKING_LIST] Anthropic 실패: {e}")

        # 실패 시 다른 provider로 폴백 (선택된 provider가 아닌 경우만)
        if not result or not getattr(result, 'success', False) or not getattr(result, 'lots', []):
            fallback_order = [p for p in ('gemini', 'openai', 'anthropic') if p != provider]
            for fb_provider in fallback_order:
                fb_key = self._get_ai_key(fb_provider)  # type: ignore[attr-defined]
                if not fb_key:
                    continue
                logger.info(f"[PACKING_LIST] {provider} 실패 → {fb_provider} 폴백 시도")
                try:
                    if fb_provider == 'gemini':
                        from features.ai.gemini_parser import GeminiDocumentParser
                        gp = GeminiDocumentParser(fb_key)
                        result = gp.parse_packing_list(pdf_path, bag_weight_kg=bag_weight_kg, gemini_hint=gemini_hint)
                    elif fb_provider == 'openai':
                        from features.ai.openai_parser import try_parse_packing_list as oai_parse
                        result = oai_parse(pdf_path, api_key=fb_key)
                    elif fb_provider == 'anthropic':
                        from features.ai.anthropic_parser import try_parse_packing_list as ant_parse
                        result = ant_parse(pdf_path, api_key=fb_key)
                    if result and getattr(result, 'success', False) and getattr(result, 'lots', []):
                        logger.info(f"[PACKING_LIST] {fb_provider} 폴백 성공")
                        break
                except Exception as fb_err:
                    logger.warning(f"[PACKING_LIST] {fb_provider} 폴백 실패: {fb_err}")

        return result