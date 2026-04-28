"""
SQM 재고관리 시스템 - B/L (Bill of Lading) 파서 Mixin
======================================================
v3.6.0: document_parser_v2.py에서 분리
v5.8.6.B: Ship Date 하이브리드 추출 (Gemini 우선 + 정규식 폴백)

작성자: Ruby (남기동)
버전: v5.8.6.B
"""

import logging
import re
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

from ..document_models import BLData

logger = logging.getLogger(__name__)


def _dbg_log(*args, **kwargs) -> None:
    # v8.6.4: 프로덕션 debug 파일 쓰기 제거 → logger.debug
    # 호출부 호환: msg 1개 또는 구조화 인자 모두 허용
    if len(args) == 1 and not kwargs:
        logger.debug(f"[DBG] {args[0]}")
        return
    logger.debug("[DBG] args=%s kwargs=%s", args, kwargs)


class BLMixin:
    """B/L (Bill of Lading) 파서 Mixin — 좌표 기반 3단계 단독 파서"""

    BL_LABEL_PATTERNS = [
        r"SEA\s+WAYBILL\s*No\.?",
        r"WAYBILL\s*No\.?",
        r"B\s*/\s*L\s*No\.?",
        r"BILL\s+OF\s+LADING\s*No\.?",
        r"\bBL\s*No\.?",
    ]
    # v8.0.0 [BL-FORMAT]: 선사별 BL 번호 형식 직접 지정
    # 형식: (영문접두사, 숫자길이) — 빈 접두사면 순수 숫자
    BL_FORMAT_MAP = {
        'MSC':      [('MSCU', 7), ('MEDU', 7)],   # v8.2.4: MSCU1234567 / MEDUFP963988 — CARRIER_RE 우선, 숫자7은 폴백
        'MAERSK':   [('MAEU', 9)],                  # v8.4.4: MAEU263764814 (알파벳4+숫자9) — 순수숫자 형식 제거
        'COSCO':    [('COSU', 7)],                 # COSU1234567
        'EVERGREEN':[('EVER', 7)],                 # EVER1234567
        'CMA CGM':  [('CMA', 7)],                  # CMA1234567
        'HMM':      [('HMMU', 7)],                 # HMMU1234567
        'ONE':      [('ONEU', 7)],                 # ONEU1234567
        'HAPAG':    [('HLCU', 7)],                 # HLCU1234567
        'YANG MING':[('YMLU', 7)],                 # YMLU1234567
        'PIL':      [('PILU', 7)],
        'SITC':     [('SITC', 7)],
    }

    BL_TOKEN_RE = re.compile(r"^[A-Z0-9]{6,25}$")
    CARRIER_RE = re.compile(
        r"(?:MEDU[A-Z0-9]{6,10}|MSCU[A-Z0-9]{6,10}|COSU[A-Z0-9]{6,10}|EVER[A-Z0-9]{6,10}|"
        r"YMLU[A-Z0-9]{6,10}|HMMU[A-Z0-9]{6,10}|ONEU[A-Z0-9]{6,10}|HLCU[A-Z0-9]{6,10}|"
        r"CMA[A-Z0-9]{6,10}|PILU[A-Z0-9]{6,10}|SITC[A-Z0-9]{6,10}|"
        r"MAEU\d{9}|"           # v8.4.4: MAERSK BL No — MAEU + 숫자9자리
        r"\d{9,15})"            # 순수 숫자 폴백 (기타 선사 대비 유지)
    )
    BLACKLIST = {
        "NOT", "COPY", "PAGES", "NEGOTIABLE", "ORIGINAL", "BILL", "LADING", "NO",
        "BOOKING", "SHIPPER", "CONSIGNEE",
        # v8.4.4: MSC Sea Waybill "NO. OF RIDER PAGES: N Two" 오파싱 방지
        "NOOFRIDER2PAGESTWO", "NOOFRIDER1PAGESONE", "NOOFRIDER3PAGESTHREE",
        "NOOFRIDER4PAGESFOUR", "NOOFRIDER5PAGESFIVE",
        "RIDER2PAGESTWO", "RIDER1PAGESONE",
    }
    SHIP_DATE_PATTERNS = [
        re.compile(r"\b\d{1,2}[-/.](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/.]\d{4}\b", re.IGNORECASE),
        re.compile(r"\b\d{4}[-/.]\d{2}[-/.]\d{2}\b"),
        re.compile(r"\b\d{1,2}[-/.]\d{2}[-/.]\d{4}\b"),
        re.compile(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b", re.IGNORECASE),
    ]
    SHIPPED_PATTERN = re.compile(r"\bSHIPPED\b.*\bBOARD\b(?:.*\bDATE\b)?", re.IGNORECASE)
    URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
    # 좌표는 페이지 절대픽셀이 아닌 퍼센트(%) 기준.
    CARRIER_COORD_TABLE = {
        "MAERSK": {
            # v8.4.5: 실제 MAERSK BL PDF(263764814) 좌표 직접 측정 결과
            # BL No: x=86.2%, y=6.6% → 라벨(B/L No.) 제외 x=85~95%
            "bl_no": (85.0, 95.0, 6.0, 7.5),
            # SALLY MAERSK: x=6.1~10%, y=33.8% → 정상
            "vessel": (5.0, 25.0, 33.3, 34.6),
            # 604W: x=27%, y=33.9% → 정상
            "voyage_no": (26.0, 40.0, 33.3, 34.6),
            # Puerto Angamos,Chile: y=36.8% — 라벨행(36.0%) 제외 y=36.5~37.8
            "port_of_loading": (5.0, 26.0, 36.5, 37.8),
            # GWANGYANG,SOUTH KOREA: y=36.7% → y=36.5~37.8, x=26~46%
            "port_of_discharge": (26.0, 46.0, 36.5, 37.8),
            # Shipped on Board Date: y=80.1% — 구좌표 75~78.5% 는 빈값!
            "ship_date": (5.0, 22.0, 79.5, 81.5),
        },
        "MSC": {
            # v8.4.5: 실제 MSC Sea Waybill PDF(963970, 963988) 좌표 직접 측정 결과
            # MEDUFP963970 위치: x=77.1%, y=2.6% → x=65~90%, y=2.0~3.5%
            "bl_no": (65.0, 90.0, 2.0, 3.5),
            # HMM BLESSING 위치: x=4.2~7.3%, y=29.9% → x=3~25%, y=29.5~31.0%
            # (VESSEL AND VOYAGE NO 라벨은 y=28.x%로 제외됨)
            "vessel": (3.0, 25.0, 29.5, 31.0),
            # 0037W 위치: x=14.3%, y=29.9% → x=14~22%, y=29.5~31.0%
            "voyage_no": (14.0, 22.0, 29.5, 31.0),
            # Puerto Angamos,Chile: x=36~45%, y=29.6% → x=30~58%, y=29.0~31.0%
            "port_of_loading": (30.0, 58.0, 29.0, 31.0),
            # Gwangyang,Korea: x=36%, y=32.8% → x=30~58%, y=32.0~34.0%
            "port_of_discharge": (30.0, 58.0, 32.0, 34.0),
            # 선적일: 하단 박스 넓게 유지
            "ship_date": (12.0, 58.0, 80.0, 95.0),
        },
        "HAPAG": {
            # HAPAG-Lloyd Sea Waybill PDF 실측 (HLCUSCL260148627)
            # SWB-No. 라벨(61.1%, 9.7%) 아래 값: HLCUSCL260148627 at [62.3%, 11.1%]
            "bl_no": (60.0, 97.0, 10.5, 12.0),
            # Vessel(s) 라벨(6.6%, 35.5%) 아래: BUENAVENTURA EXPRESS at [7.0~29%, 36.8%]
            "vessel": (6.0, 40.0, 36.5, 38.0),
            # Voyage-No. 라벨(39.6%, 35.5%) 아래: 2602W at [42.3%, 36.8%]
            "voyage_no": (40.0, 55.0, 36.5, 38.0),
            # Port of Loading 라벨(6.6%, 40.0%) 아래: PUERTO ANGAMOS, CHILE at [7~26%, 41.3%]
            "port_of_loading": (6.0, 45.0, 41.0, 42.5),
            # Port of Discharge 라벨(6.6%, 43.0%) 아래: BUSAN, SOUTH KOREA at [7~22%, 44.3%]
            "port_of_discharge": (6.0, 42.0, 44.0, 45.5),
            # Place and date of issue 오른쪽: 26.FEB.2026 at [70.6%, 88.7%]
            "ship_date": (68.0, 90.0, 88.0, 89.5),
        },
        "ONE": {
            # ONE Sea Waybill PDF 실측 (SCLG01825300, SCLG01857800)
            # SEA WAYBILL NO. 라벨(78.8%, 7.3%) 오른쪽: ONEYSCLG01825300 at [80.4%, 8.0%]
            "bl_no": (78.0, 97.0, 7.5, 9.0),
            # OCEAN VESSEL 행(y=34.4%) 바로 아래: RIO DE JANEIRO EXPRESS at [5~16%, 35.2%]
            "vessel": (4.0, 21.0, 35.0, 36.3),
            # 2601W at [21.2%, 35.2%]
            "voyage_no": (19.0, 27.0, 35.0, 36.3),
            # PORT OF LOADING 행 아래: PUERTO ANGAMOS, CHILE at [31.2~52%, 35.5%]
            "port_of_loading": (30.0, 56.0, 35.0, 36.8),
            # PORT OF DISCHARGE 행 아래: KWANGYANG at [5.0%, 38.3%]
            "port_of_discharge": (4.0, 21.0, 38.0, 39.5),
            # DATE LADEN ON BOARD(74.2%) 바로 아래: 19 FEB 2026 at [82.3~89%, 74.9%]
            "ship_date": (80.0, 96.0, 74.5, 76.5),
        },
    }

    def _extract_by_bl_format(self, text: str, bl_format: str) -> str:
        """v8.0.0: bl_format 직접 지정으로 BL 번호 추출.
        형식: '숫자9' → 순수 숫자 9자리
              'MSCU7' → MSCU + 숫자 7자리
        """
        import re as _re
        # v8.2.4: MSC MEDU/MSCU/HLCU 계열 — 알파숫자 혼합 (MEDUFP963988 등)
        # 기존 {7} 숫자 고정 → {3,6} 알파숫자 허용으로 확장
        if bl_format and any(p in bl_format.upper() for p in ('MEDU','MSCU','HLCU','COSU')):
            msc_pat = _re.compile(r'\b((?:MEDU|MSCU|HLCU|COSU)[A-Z0-9]{6,10})\b')
            hits = msc_pat.findall(text)
            if hits:
                return hits[0]
        if not bl_format:
            return ''
        import re as _re
        fmt = bl_format.strip()
        try:
            if fmt.startswith('숫자') or fmt.lower().startswith('num'):
                # 순수 숫자 N자리
                n = int(''.join(filter(str.isdigit, fmt)))
                pattern = _re.compile(rf'\b(\d{{{n}}})\b')
            else:
                # 영문접두사 + 숫자N자리
                prefix = ''.join(filter(str.isalpha, fmt)).upper()
                n = int(''.join(filter(str.isdigit, fmt)))
                pattern = _re.compile(rf'\b({_re.escape(prefix)}\d{{{n}}})\b')
            matches = pattern.findall(text)
            if matches:
                return matches[0]
        except Exception as _e:
            logger.debug(f"[BL] bl_format 파싱 실패: {_e}")
        return ''

    def parse_bl(self, pdf_path: str, **kwargs) -> "Optional[BLData]":
        """v9.2: BL PDF 파싱 — 좌표 테이블 2단계 + 최종 정규식 폴백 1회."""
        logger.info(f"[BL] 파싱 시작: {pdf_path}")
        words     = self._extract_words(pdf_path, max_pages=3)
        full_text = self._extract_text(pdf_path)
        if not words and not full_text:
            raise RuntimeError("[BL] PDF 텍스트 추출 실패")

        explicit_carrier = str(kwargs.get("carrier_id", "") or "").upper().strip()
        _bl_format = str(kwargs.get("bl_format", "") or "").strip()
        carrier_id = self._detect_carrier_from_words(words, full_text=full_text, explicit=explicit_carrier)
        # region agent log
        _dbg_log(
            "H8",
            "bl_mixin.py:parse_bl:carrier_resolution",
            "carrier resolution for BL parsing",
            {
                "explicit_carrier": explicit_carrier,
                "detected_carrier": carrier_id,
                "bl_format": _bl_format,
                "has_words": bool(words),
            },
        )
        # endregion
        coord_data = self._parse_by_coord_table(words, carrier_id) if carrier_id else {}

        bl_no = self._clean_bl_no(coord_data.get("bl_no", ""))
        method = f"coord_table({carrier_id})" if bl_no else ""

        # 레거시 bl_format 지정이 있으면 1회 시도
        if not bl_no and _bl_format:
            bl_no = self._extract_by_bl_format(full_text, _bl_format)
            method = f"bl_format({_bl_format})" if bl_no else ""

        # 최종 폴백: 정규식 스캔 1회
        if not bl_no:
            m = self.CARRIER_RE.search(full_text)
            if m:
                bl_no = self._clean_bl_no(m.group(0))
                method = "carrier_re_scan"

        if not bl_no:
            partial = BLData()
            partial.source_file = pdf_path
            partial.parsed_at = datetime.now()
            partial.raw_text = full_text[:20000] if full_text else ""
            if carrier_id:
                partial.carrier_id = carrier_id
            try:
                from .ai_fallback import parse_bl_ai
                ai_result = parse_bl_ai(
                    self,
                    pdf_path,
                    partial=partial,
                    carrier_id=carrier_id or explicit_carrier,
                    provider=getattr(self, "provider", "gemini"),
                )
                if ai_result and getattr(ai_result, "success", False):
                    logger.info("[BL] 좌표/정규식 실패 → AI fallback 성공: %s", ai_result.bl_no)
                    return ai_result
            except Exception as ai_err:
                logger.warning("[BL] AI fallback 실패: %s", ai_err)
            raise RuntimeError(f"[BL] BL 번호 파싱 실패 (선사={carrier_id or '미지정'})")

        result = BLData()
        result.source_file = pdf_path
        result.parsed_at   = datetime.now()
        result.bl_no = bl_no
        result.booking_no = bl_no

        # v8.5.7 [PATCH3-BUG3]: total_containers / gross_weight 보강
        import re as _bl_re
        _ct_m = _bl_re.search(r'(\d+)\s+(?:cntrs|containers?|CNTRS)', full_text, _bl_re.IGNORECASE)
        if _ct_m:
            try:
                result.total_containers = int(_ct_m.group(1))
            except (ValueError, TypeError) as _e:
                logger.debug(f"[SUPPRESSED] exception in bl_mixin.py: {_e}")  # noqa
        _gw_m = _bl_re.search(
            r'Total\s*Gross\s*Weight\s*[:\s]*([\d,.]+)',
            full_text, _bl_re.IGNORECASE
        )
        if not _gw_m:
            _gw_m = _bl_re.search(r'([\d,]+\.\d+)\s*Kgs?\.?', full_text, _bl_re.IGNORECASE)
        if _gw_m:
            try:
                _gw_str = _gw_m.group(1).replace(',', '')
                result.gross_weight_kg = float(_gw_str)
            except (ValueError, TypeError) as _e:
                logger.debug(f"[SUPPRESSED] exception in bl_mixin.py: {_e}")  # noqa
        result.raw_text    = full_text[:20000] if full_text else ""

        # 좌표 테이블에서 추가 필드 채우기
        try:
            extra = dict(coord_data or {})
            if not extra:
                extra = self._extract_bl_extra_fields(words)
            result.vessel            = extra.get("vessel", "")
            result.voyage            = extra.get("voyage_no", "")
            result.port_of_loading   = extra.get("port_of_loading", "")
            result.port_of_discharge = extra.get("port_of_discharge", "")
            if extra.get("vessel"):
                logger.info(
                    f"[BL] 추가필드: vessel={extra['vessel']} "
                    f"POD={extra.get('port_of_discharge', '')}"
                )
        except Exception as _e:
            logger.debug(f"[BL] 추가필드 추출 실패(무시): {_e}")

        # Ship Date: 좌표 테이블 우선 → 기존 폴백
        try:
            ship_date = extra.get("ship_date", "") if isinstance(extra, dict) else ""
            source = f"coord_table({carrier_id})" if ship_date else ""
            page_no = None
            if not ship_date:
                ship_date, source, page_no = self._extract_ship_date_v2(words)
            if not ship_date:
                from utils.date_utils import extract_ship_date
                ship_date, source, _estimated = extract_ship_date({}, full_text or "")
                page_no = None
            result.shipped_on_board_date = ship_date
            result.ship_date = ship_date
            if ship_date:
                logger.info(f"[BL] Ship Date: {ship_date} (method={source})")
        except Exception as e:
            logger.debug(f"[BL] Ship Date 추출 실패(무시): {e}")

        logger.info(f"[BL] 파싱 성공: {bl_no} (method={method})")
        # region agent log
        _dbg_log(
            "H9",
            "bl_mixin.py:parse_bl:success",
            "BL parse finished",
            {
                "carrier_id": carrier_id,
                "method": method,
                "bl_no": bl_no,
            },
        )
        # endregion
        result.success = bool(result.bl_no)
        # v8.4.5: carrier_id/carrier_name BLData에 저장 → 선사 뱃지 표시용
        if carrier_id:
            result.carrier_id = carrier_id
            _carrier_name_map = {
                "MSC":      "Mediterranean Shipping Company",
                "MAERSK":   "Maersk",
                "HMM":      "Hyundai Merchant Marine",
                "CMA_CGM":  "CMA CGM",
                "ONE":      "Ocean Network Express",
                "HAPAG":    "Hapag-Lloyd",
                "EVERGREEN":"Evergreen",
                "COSCO":    "COSCO",
                "YANG MING":"Yang Ming",
            }
            result.carrier_name = _carrier_name_map.get(carrier_id, carrier_id)
        return result

    def _detect_carrier_from_words(self, words: List[Dict], full_text: str = "", explicit: str = "") -> str:
        if explicit:
            if explicit in ("MAEU", "MERSK"):
                chosen = "MAERSK"
            else:
                chosen = explicit
            logger.info(f"[BL] carrier: explicit={explicit!r} -> {chosen}")
            return chosen
        page0_words = [w for w in words if int(w.get("page", 0)) == 0]
        page0_text = " ".join(str(w.get("text", "")) for w in page0_words).upper()
        if not page0_text:
            page0_text = (full_text or "").upper()
        score = {"MAERSK": 0, "MSC": 0, "ONE": 0, "HAPAG": 0}
        # MAERSK
        if any(k in page0_text for k in ("MAERSK", "SCAC")):
            score["MAERSK"] += 2
        if "NON-NEGOTIABLE WAYBILL" in page0_text:
            score["MAERSK"] += 3
        if re.search(r"\bMAEU\b", page0_text):
            score["MAERSK"] += 2
        # MSC
        if "MEDITERRANEAN" in page0_text:
            score["MSC"] += 2
        if "MSC.COM" in page0_text or "WWW.MSC.COM" in page0_text:
            score["MSC"] += 4
        if re.search(r"\bMSC\b", page0_text):
            score["MSC"] += 2
        if re.search(r"\b(?:MSCU|MEDU)\b", page0_text):
            score["MSC"] += 2
        if re.search(r"\b(?:MEDU|MSCU)[A-Z0-9]{4,}\b", page0_text):
            score["MSC"] += 3
        # ONE (Ocean Network Express)
        if "ONE-LINE.COM" in page0_text or "WWW.ONE-LINE.COM" in page0_text:
            score["ONE"] += 4
        if "OCEAN NETWORK EXPRESS" in page0_text:
            score["ONE"] += 4
        if re.search(r"\bONEY[A-Z]{3,4}\d{6,9}\b", page0_text):
            score["ONE"] += 3
        if re.search(r"\bONEU[A-Z0-9]{6,10}\b", page0_text):
            score["ONE"] += 2
        if "SEA WAYBILL" in page0_text and score["ONE"] > 0:
            score["ONE"] += 1
        elif "SEA WAYBILL" in page0_text:
            score["MSC"] += 2
        # HAPAG-Lloyd
        if "HAPAG-LLOYD" in page0_text or "HAPAG LLOYD" in page0_text:
            score["HAPAG"] += 5
        if "HLAG.COM" in page0_text or "WWW.HLAG.COM" in page0_text:
            score["HAPAG"] += 4
        if re.search(r"\bHLCU[A-Z0-9]{6,}\b", page0_text):
            score["HAPAG"] += 4
        if re.search(r"\bHAPAG\b", page0_text):
            score["HAPAG"] += 2
        best = max(score, key=lambda k: score[k])
        if score[best] == 0:
            chosen = ""
        elif list(score.values()).count(score[best]) > 1:
            # 동점 처리
            if score["HAPAG"] == score[best]:
                chosen = "HAPAG"
            elif score["ONE"] == score[best]:
                chosen = "ONE"
            elif "NON-NEGOTIABLE WAYBILL" in page0_text or re.search(r"\bMAEU\b", page0_text):
                chosen = "MAERSK"
            else:
                chosen = "MSC"
        else:
            chosen = best
        logger.info(f"[BL] carrier score: {score} -> {chosen or '(none)'}")
        return chosen

    def _clean_bl_no(self, value: str) -> str:
        token = self._norm(value)
        token = re.sub(r"^SCAC", "", token)
        token = re.sub(r"^(?:BLNO|BILLNO|WAYBILLNO)", "", token)
        if token and self._looks_like_bl(token):
            return token
        return ""

    def _parse_by_coord_table(self, words: List[Dict], carrier_id: str) -> dict:
        if not words:
            return {}
        table = self.CARRIER_COORD_TABLE.get((carrier_id or "").upper(), {})
        if not table:
            return {}
        parsed = {}
        for field, box in table.items():
            if not isinstance(box, tuple) or len(box) != 4:
                continue
            raw = self._by_coord(words, box[0], box[1], box[2], box[3], page=0)
            if not raw:
                continue
            if field == "bl_no":
                clean = self._clean_bl_no(raw)
                if clean:
                    parsed[field] = clean
            elif field == "ship_date":
                parsed_date = self._parse_date_from_text(raw)
                if parsed_date:
                    parsed[field] = parsed_date
            else:
                cleaned = re.sub(
                    r"^(?:Vessel|Voyage(?:\s*No\.?)?|Port\s+of\s+Loading|Port\s+of\s+Discharge)\s*",
                    "",
                    raw,
                    flags=re.IGNORECASE,
                ).strip()
                if cleaned:
                    parsed[field] = cleaned
        return parsed

    def _extract_words(self, pdf_path: str, max_pages: int = 3) -> List[Dict]:
        """PyMuPDF 단어 좌표 추출."""
        from core.pdf_engine import open_pdf
        out: List[Dict] = []
        doc = open_pdf(pdf_path)
        try:
            for page_idx in range(min(max_pages, len(doc))):
                page = doc[page_idx]
                width = float(page.rect.width or 1.0)
                height = float(page.rect.height or 1.0)
                for w in page.get_text("words") or []:
                    x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], str(w[4] or "")
                    t = text.strip()
                    if not t:
                        continue
                    out.append({
                        "text": t, "x0": float(x0), "x1": float(x1),
                        "top": float(y0), "bottom": float(y1),
                        "page": page_idx, "width": width, "height": height,
                    })
        finally:
            doc.close()
        return out

    def _norm(self, token: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", str(token or "").upper())

    def _looks_like_bl(self, token: str) -> bool:
        t = self._norm(token)
        if not t or t in self.BLACKLIST:
            return False
        if not self.BL_TOKEN_RE.match(t):
            return False
        if not re.search(r"\d", t):
            return False
        return True

    def _group_lines(self, words: List[Dict], y_tol: float = 4.0) -> Dict[tuple, List[Dict]]:
        lines: Dict[tuple, List[Dict]] = {}
        for w in words:
            yc = (w["top"] + w["bottom"]) / 2.0
            bucket = int(round(yc / max(0.1, y_tol)))
            key = (w["page"], bucket)
            lines.setdefault(key, []).append(w)
        for key in lines:
            lines[key].sort(key=lambda x: x["x0"])
        return lines

    def _by_coord(self, words, x1: float, x2: float,
                  y1: float, y2: float, page: int = 0) -> str:
        """좌표 범위로 텍스트 추출 (공용 헬퍼 v9.1)."""
        if not words:
            return ''
        # 첫 번째 단어에서 페이지 크기 가져오기
        ref = next((w for w in words if w.get('page', 0) == page), None)
        if not ref:
            ref = words[0]
        pw = float(ref.get('width',  595.0) or 595.0)
        ph = float(ref.get('height', 842.0) or 842.0)
        hits = sorted(
            [w for w in words
             if w.get('page', 0) == page
             and x1 <= w['x0']/pw*100 <= x2
             and y1 <= w['top']/ph*100 <= y2],
            key=lambda w: (w['top'], w['x0'])
        )
        return ' '.join(w['text'] for w in hits).strip()


    def _extract_bl_extra_fields(self, words) -> dict:
        """v9.1: BL PDF에서 vessel/voyage/POL/POD 좌표 기반 추출.

        MAERSK NON-NEGOTIABLE WAYBILL 고정 레이아웃:
          y≈33.8%  x=5~25%:   SALLY MAERSK  (vessel)
          y≈33.8%  x=26~38%:  604W           (voyage_no)
          y≈36.8%  x=5~26%:   Puerto Angamos, Chile  (port_of_loading)
          y≈36.7%  x=26~46%:  GWANGYANG,SOUTH KOREA  (port_of_discharge)
        """
        if not words:
            return {}

        page_h = float(words[0].get("height", 842.0)) if words else 842.0
        page_w = float(words[0].get("width",  595.0)) if words else 595.0

        def by_xy(x1, x2, y1, y2):
            hits = sorted(
                [w for w in words
                 if x1 <= w["x0"] / page_w * 100 <= x2
                 and y1 <= w["top"] / page_h * 100 <= y2
                 and w.get("page", 0) == 0],
                key=lambda x: x["x0"]
            )
            return " ".join(w["text"] for w in hits).strip()

        # 라벨 행(y≈33.0%)과 값 행(y≈33.8%)을 분리
        vessel  = by_xy(5,  25, 33.3, 34.5)   # 라벨 제외 값만
        voyage  = by_xy(26, 38, 33.3, 34.5)
        pol     = by_xy(5,  26, 36.4, 37.5)
        pod_raw = by_xy(26, 46, 36.3, 37.5)

        # "Vessel" / "Voyage No." 라벨 토큰 제거
        vessel  = re.sub(r"^Vessel\s*", "", vessel, flags=re.IGNORECASE).strip()
        voyage  = re.sub(r"^(Voyage|No\.)\s*", "", voyage, flags=re.IGNORECASE).strip()
        pol     = re.sub(r"^Port\s+of\s+Loading\s*", "", pol, flags=re.IGNORECASE).strip()
        pod     = re.sub(r"^Port\s+of\s+Discharge\s*", "", pod_raw, flags=re.IGNORECASE).strip()

        return {
            "vessel":             vessel,
            "voyage_no":          voyage,
            "port_of_loading":    pol,
            "port_of_discharge":  pod,
        }






    def _parse_date_from_text(self, text: str):
        from utils.date_utils import normalize_date
        if not text:
            return None
        parsed = normalize_date(text)
        if parsed:
            return parsed
        for pat in self.SHIP_DATE_PATTERNS:
            m = pat.search(text)
            if m:
                parsed = normalize_date(m.group(0))
                if parsed:
                    return parsed
        return None

    def _page_words(self, words: List[Dict], page_idx: int) -> List[Dict]:
        return [w for w in words if int(w.get("page", -1)) == int(page_idx)]

    def _ordered_pages(self, words: List[Dict]) -> List[int]:
        pages = sorted({int(w.get("page", -1)) for w in words if int(w.get("page", -1)) >= 0})
        preferred = [1, 2, 0]
        out = [p for p in preferred if p in pages]
        for p in pages:
            if p not in out:
                out.append(p)
        return out

    def _sanitize_line(self, text: str) -> str:
        s = self.URL_PATTERN.sub("", text or "")
        s = re.sub(r"\[https?://[^\]]*\]", "", s, flags=re.IGNORECASE)
        return s

    def _extract_ship_date_keyword_anchor(self, words: List[Dict]):
        lines = self._group_lines(words, y_tol=4.0)
        pages = self._ordered_pages(words)
        for page in pages:
            page_words = self._page_words(words, page)
            if not page_words:
                continue
            by_line = {k: v for k, v in lines.items() if k[0] == page}
            for (_p, _b), line in by_line.items():
                line_text = " ".join(w["text"] for w in line)
                up = line_text.upper()
                if "SHIPPED" not in up or "BOARD" not in up:
                    continue
                if "PLACE" in up and "ISSUE" in up:
                    continue
                shipped_x = min((w["x0"] for w in line if str(w["text"]).upper().startswith("SHIPPED")), default=line[0]["x0"])
                candidates = []
                for w in page_words:
                    dy = float(w["top"]) - float(line[0]["top"])
                    if not (3 <= dy <= 60):
                        continue
                    if not (shipped_x - 80 <= float(w["x0"]) <= shipped_x + 220):
                        continue
                    d = self._parse_date_from_text(str(w["text"]))
                    if d:
                        candidates.append((abs(float(w["x0"]) - shipped_x), abs(dy), d))
                if candidates:
                    candidates.sort(key=lambda x: (x[0], x[1]))
                    return candidates[0][2], "keyword_anchor", page + 1
        return None, "", None

    def _extract_ship_date_bottom_zone(self, words: List[Dict]):
        pages = self._ordered_pages(words)
        for page in pages:
            page_words = self._page_words(words, page)
            cands = []
            for w in page_words:
                h = float(w.get("height") or 1.0)
                ww = float(w.get("width") or 1.0)
                y_ratio = float(w["top"]) / h
                x_ratio = float(w["x0"]) / ww
                if y_ratio < 0.75:
                    continue
                if not (0.03 <= x_ratio <= 0.55):
                    continue
                d = self._parse_date_from_text(str(w["text"]))
                if d:
                    cands.append((y_ratio, x_ratio, d))
            if cands:
                cands.sort(key=lambda x: (x[0], x[1]))
                return cands[0][2], "bottom_zone_scan", page + 1
        return None, "", None

    def _extract_ship_date_text_proximity(self, words: List[Dict]):
        lines = self._group_lines(words, y_tol=4.0)
        pages = self._ordered_pages(words)
        for page in pages:
            page_lines = [(k, lines[k]) for k in sorted(lines.keys(), key=lambda x: x[1]) if k[0] == page]
            if not page_lines:
                continue
            line_texts = [self._sanitize_line(" ".join(w["text"] for w in ln)) for _k, ln in page_lines]
            if not any(self.SHIPPED_PATTERN.search(t.upper()) for t in line_texts):
                continue
            for i, t in enumerate(line_texts):
                if not self.SHIPPED_PATTERN.search(t.upper()):
                    continue
                direct = self._parse_date_from_text(t)
                if direct:
                    return direct, "full_text_proximity", page + 1
                for j in range(i + 1, min(i + 7, len(line_texts))):
                    near = self._parse_date_from_text(line_texts[j])
                    if near:
                        return near, "full_text_proximity", page + 1
        return None, "", None

    def _extract_ship_date_v2(self, words: List[Dict]):
        d, m, p = self._extract_ship_date_keyword_anchor(words)
        if d:
            return d, m, p
        d, m, p = self._extract_ship_date_bottom_zone(words)
        if d:
            return d, m, p
        d, m, p = self._extract_ship_date_text_proximity(words)
        if d:
            return d, m, p
        return None, "none", None
