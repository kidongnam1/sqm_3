# -*- coding: utf-8 -*-
"""
SQM v865 - Inbound API
POST /api/inbound/pdf  : base64 PDF decode -> pdf_parser -> DB save
Phase 4-D + Gemini Vision Fallback (Phase 5)

Parsing strategy (2-tier):
  Tier-1 (Primary)  : SQMPdfParser coordinate/text-based parsing
  Tier-2 (Fallback) : Gemini Vision API (PDF -> PNG -> structured JSON)
  Condition: auto Tier-2 when Tier-1 fails OR total_lots == 0
"""
import base64
import json
import logging
import re
import tempfile
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Body, Form
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inbound", tags=["inbound"])

# Tier-2 Fallback: Gemini Vision API PDF 파싱
# 조건: Tier-1 실패 OR total_lots == 0
# ════════════════════════════════════════════════════════════

_GEMINI_PARSE_PROMPT = """
이 이미지는 리튬카보네이트 Packing List PDF 입니다.
아래 JSON 형식으로 정보를 추출하세요. JSON만 반환, 설명 없이.

{
  "folio": "7자리 숫자 Folio 번호 (없으면 null)",
  "product": "제품명 전체 (예: LITHIUM CARBONATE - BATTERY GRADE)",
  "product_code": "제품코드 (예: MIC9000, CRY9000, 없으면 null)",
  "vessel": "선박명 (없으면 null)",
  "lots": [
    {
      "lot_no": "LOT 번호 (보통 10자리 숫자)",
      "container_no": "컨테이너 번호 (없으면 null)",
      "mxbg_pallet": "톤백(MxBag) 개수 정수 (없으면 null)",
      "lot_sqm": "LOT SQM 면적 숫자 (없으면 null)",
      "net_weight": "순중량 kg 숫자 (없으면 null)",
      "gross_weight": "총중량 kg 숫자 (없으면 null)"
    }
  ]
}

주의:
- LOT 번호는 정확히 추출 (보통 112로 시작하는 10자리)
- 중량 단위가 MT이면 1000을 곱해 kg으로 변환
- 숫자 필드는 쉼표(,) 제거 후 숫자만
- lots 배열이 비어있으면 안 됨
- mxbg_pallet: 표 끝 열의 정수 (보통 10~20)
- lot_sqm: LOT N° 옆 숫자 (보통 6자리)
""".strip()


def _gemini_parse_pdf(pdf_path: str, filename: str = "") -> Optional[Any]:
    """
    Gemini Vision API로 PDF 첫 페이지를 이미지로 변환 후 구조화된 파싱.

    Returns:
        PackingListData 객체 (성공) 또는 None (실패/API 없음)
    """
    try:
        # ① PyMuPDF로 첫 페이지 → PNG 이미지
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("[Gemini fallback] PyMuPDF(fitz) 미설치 — 이미지 변환 불가")
            return None

        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            logger.warning("[Gemini fallback] PDF 페이지 없음")
            return None

        page = doc[0]
        mat = fitz.Matrix(2.0, 2.0)   # 2× 확대 → 글자 인식률 향상
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        doc.close()
        logger.info(f"[Gemini fallback] PDF→PNG 변환 OK ({len(img_bytes)//1024} KB), file={filename}")

        # ② Gemini 클라이언트 준비
        try:
            from features.ai.gemini_utils import get_gemini_client, get_model_name, call_gemini_safe
        except ImportError:
            logger.warning("[Gemini fallback] gemini_utils import 실패")
            return None

        client = get_gemini_client()
        if client is None:
            logger.warning("[Gemini fallback] Gemini 클라이언트 없음 (API 키 미설정?)")
            return None

        model_name = get_model_name()

        # ③ Gemini API 호출 (이미지 + 텍스트 프롬프트)
        try:
            from google.genai import types as genai_types
            contents = [
                genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                genai_types.Part.from_text(_GEMINI_PARSE_PROMPT),
            ]
        except ImportError:
            # 구버전 google-generativeai 호환
            contents = [
                {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                _GEMINI_PARSE_PROMPT,
            ]

        logger.info(f"[Gemini fallback] API 호출 시작 (model={model_name})")
        response = call_gemini_safe(client, model_name, contents, timeout=45)

        if response is None:
            logger.warning("[Gemini fallback] API 응답 없음")
            return None

        raw_text = getattr(response, "text", "") or ""
        logger.info(f"[Gemini fallback] 응답 수신: {len(raw_text)} chars")
        logger.debug(f"[Gemini fallback] 응답 미리보기: {raw_text[:300]}")

        # ④ JSON 파싱
        # 마크다운 코드블록 제거
        json_text = re.sub(r"```(?:json)?\s*", "", raw_text).strip().rstrip("`").strip()
        # JSON 객체 부분만 추출
        m = re.search(r'\{.*\}', json_text, re.DOTALL)
        if not m:
            logger.warning(f"[Gemini fallback] JSON 추출 실패: {raw_text[:200]}")
            return None

        data = json.loads(m.group(0))

        # ⑤ PackingListData 조립
        from parsers.pdf_parser import PackingListData
        from datetime import datetime

        result = PackingListData()
        result.source_file = pdf_path
        result.parsed_at = datetime.now()
        result.folio = str(data.get("folio") or "")
        result.product = str(data.get("product") or "")
        result.product_code = str(data.get("product_code") or "")
        result.vessel = str(data.get("vessel") or "")

        raw_lots = data.get("lots") or []
        lots_out = []
        for lot in raw_lots:
            lot_no = str(lot.get("lot_no") or "").strip()
            if not lot_no:
                continue
            # ★ 키명 통일: tonbag_count(구버전 호환) → mxbg_pallet (add_inventory 파라미터명)
            mxbg = _safe_int(lot.get("mxbg_pallet") or lot.get("tonbag_count"))
            lots_out.append({
                "lot_no":       lot_no,
                "container_no": str(lot.get("container_no") or ""),
                "mxbg_pallet":  mxbg,          # add_inventory 파라미터와 동일 키명
                "lot_sqm":      str(lot.get("lot_sqm") or ""),
                "net_weight":   _safe_float(lot.get("net_weight")),
                "gross_weight": _safe_float(lot.get("gross_weight")),
            })

        result.lots = lots_out
        result.total_lots = len(lots_out)

        if result.total_lots > 0:
            result.total_net_weight = sum(
                l.get("net_weight") or 0 for l in lots_out
            )

        logger.info(
            f"[Gemini fallback] 파싱 성공 — folio={result.folio}, "
            f"product={result.product}, lots={result.total_lots}개"
        )
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"[Gemini fallback] JSON 파싱 오류: {e}")
        return None
    except Exception as e:
        logger.error(f"[Gemini fallback] 예외: {e}", exc_info=True)
        return None


def _safe_int(v) -> Optional[int]:
    try:
        return int(str(v).replace(",", "").strip()) if v is not None else None
    except (ValueError, TypeError):
        return None


def _safe_float(v) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").strip()) if v is not None else None
    except (ValueError, TypeError):
        return None


_INBOUND_COLUMN_MAP = {
    # 표준 키 → 허용 Excel 컬럼명 (소문자 비교)
    "lot_no":         ["lot_no", "lot", "lot no", "lot번호", "로트", "로트번호"],
    "sap_no":         ["sap_no", "sap", "sap no", "sap번호"],
    "bl_no":          ["bl_no", "bl", "bl no", "b/l", "선하증권"],
    "container_no":   ["container_no", "container", "컨테이너", "컨테이너번호"],
    "product":        ["product", "product_name", "품목", "제품", "상품"],
    "product_code":   ["product_code", "제품코드", "품목코드"],
    "mxbg_pallet":    ["mxbg_pallet", "pallet", "팔레트", "mx_bag_pallet"],
    "net_weight":     ["net_weight", "net", "net(mt)", "net_kg", "순중량", "중량"],
    "gross_weight":   ["gross_weight", "gross", "gross(mt)", "gross_kg", "총중량"],
    "warehouse":      ["warehouse", "창고", "warehouse_name"],
    "arrival_date":   ["arrival_date", "arrival", "도착일"],
    "stock_date":     ["stock_date", "inbound_date", "입고일", "재고일"],
    "lot_sqm":        ["lot_sqm"],
    "salar_invoice_no": ["salar_invoice_no", "invoice", "인보이스"],
    "ship_date":      ["ship_date", "출항일", "선적일"],
    "con_return":     ["con_return", "반납일"],
    "free_time":      ["free_time", "프리타임"],
}


def _match_columns(df_columns) -> dict:
    """Excel 컬럼명을 표준 키로 매핑. {표준키: 원본컬럼} 반환."""
    result = {}
    lowered = {str(c).strip().lower(): c for c in df_columns}
    for std_key, aliases in _INBOUND_COLUMN_MAP.items():
        for alias in aliases:
            a = alias.strip().lower()
            if a in lowered:
                result[std_key] = lowered[a]
                break
    return result


def _clean_value(v: Any) -> Any:
    """pandas NaN / 빈 문자열 정리."""
    try:
        import math
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    return v


@router.post("/bulk-import-excel", summary="📊 수동 입고 — Excel 업로드 (F002)")
async def bulk_import_excel(file: UploadFile = File(...)):
    """
    PyWebView 네이티브 수동 입고.
    - multipart/form-data 로 Excel 파일 업로드
    - pandas 로 header=1 (수동 입고 템플릿) 우선, 실패 시 header=0 fallback
    - 각 행을 engine.add_inventory_from_dict(row_dict) 호출
    - 결과: {success_count, fail_count, total, errors: [...]}
    """
    # 1. 입력 검증
    if not file.filename:
        raise HTTPException(400, "파일명이 없습니다.")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".xlsx", ".xls"):
        raise HTTPException(400, f"Excel 파일만 지원 (.xlsx/.xls). 받은 파일: {file.filename}")

    # 2. pandas 확인
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(500, "pandas 미설치 — pip install pandas openpyxl")

    # 3. 엔진 확인
    try:
        from backend.api import engine, ENGINE_AVAILABLE
    except Exception as e:
        raise HTTPException(500, f"엔진 로드 실패: {e}")
    if not ENGINE_AVAILABLE or engine is None:
        raise HTTPException(500, "엔진이 사용 불가 상태입니다.")

    # 4. 파일을 임시 저장
    tmp_path = None
    try:
        content = await file.read()
        if not content:
            raise HTTPException(400, "빈 파일")

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        logger.info(f"[bulk-import] 수신: {file.filename} ({len(content)} bytes) -> {tmp_path}")

        # 5. Excel 읽기 — 수동 입고 템플릿(header=1) 우선, 실패 시 header=0
        df = None
        header_used = None
        for header_row in (1, 0, 2):
            try:
                candidate = pd.read_excel(tmp_path, header=header_row)
                if candidate.empty:
                    continue
                # 컬럼 매핑이 최소 2개 이상 되면 성공으로 간주
                matched = _match_columns(candidate.columns)
                if len(matched) >= 2:
                    df = candidate
                    header_used = header_row
                    break
            except Exception as e:
                logger.debug(f"[bulk-import] header={header_row} 실패: {e}")
                continue
        if df is None or df.empty:
            raise HTTPException(400, "Excel 헤더를 인식할 수 없습니다. (header=0/1/2 시도 실패) 템플릿을 확인해주세요.")

        col_map = _match_columns(df.columns)
        logger.info(f"[bulk-import] header={header_used}, {len(df)}행, 매핑: {list(col_map.keys())}")
        if "lot_no" not in col_map:
            raise HTTPException(400, f"필수 컬럼 'lot_no' 없음. 감지된 컬럼: {list(df.columns)}")

        # 6. 행별 엔진 호출
        success_count = 0
        fail_count = 0
        errors = []
        for idx, row in df.iterrows():
            data = {}
            for std_key, orig_col in col_map.items():
                data[std_key] = _clean_value(row[orig_col])
            # lot_no 필수
            if not data.get("lot_no"):
                fail_count += 1
                errors.append({"row": int(idx) + 2, "reason": "lot_no 빈 값"})
                continue
            try:
                result = engine.add_inventory_from_dict(data)
                if result.get("success"):
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append({
                        "row": int(idx) + 2,
                        "lot_no": str(data.get("lot_no", "")),
                        "reason": result.get("message") or result.get("error") or "unknown",
                    })
            except Exception as e:
                fail_count += 1
                errors.append({
                    "row": int(idx) + 2,
                    "lot_no": str(data.get("lot_no", "")),
                    "reason": f"exception: {e}",
                })
                logger.warning(f"[bulk-import] row {idx} 실패: {e}")

        logger.info(f"[bulk-import] 완료: 성공 {success_count} / 실패 {fail_count} / 총 {len(df)}")

        return {
            "ok": True,
            "data": {
                "filename": file.filename,
                "total": int(len(df)),
                "success_count": success_count,
                "fail_count": fail_count,
                "header_row": header_used,
                "matched_columns": list(col_map.keys()),
                "errors": errors[:50],  # 최대 50건만
            },
            "message": f"{success_count}건 입고 완료 / {fail_count}건 실패",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[bulk-import] 예기치 않은 에러: {e}")
        raise HTTPException(500, f"Internal error: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ────────────────────────────────────────────────────────────
# v864.3 Phase 4-B: 반품 입고 (Excel 업로드) — F007
# 기존 features.parsers.return_inbound_parser + return_inbound_engine 재사용
# ────────────────────────────────────────────────────────────
@router.post("/return-excel", summary="🔄 반품 입고 — Excel 업로드 (F007)")
async def return_inbound_excel(file: UploadFile = File(...)):
    """
    반품 Excel → picking_table 매칭 → inventory 복구 (트랜잭션).
    - parse_return_inbound_excel 로 파싱
    - process_return_inbound(engine, parsed) 로 DB 반영 (전체 or 롤백)
    """
    if not file.filename:
        raise HTTPException(400, "파일명이 없습니다.")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".xlsx", ".xls"):
        raise HTTPException(400, f"Excel 파일만 지원 (.xlsx/.xls). 받은 파일: {file.filename}")

    # 엔진 확인
    try:
        from backend.api import engine, ENGINE_AVAILABLE
    except Exception as e:
        raise HTTPException(500, f"엔진 로드 실패: {e}")
    if not ENGINE_AVAILABLE or engine is None:
        raise HTTPException(500, "엔진이 사용 불가 상태입니다.")

    # 파서/엔진 함수 import
    try:
        from features.parsers.return_inbound_parser import parse_return_inbound_excel
        from features.parsers.return_inbound_engine import process_return_inbound
    except ImportError as e:
        raise HTTPException(500, f"반품 엔진 import 실패: {e}")

    tmp_path = None
    try:
        content = await file.read()
        if not content:
            raise HTTPException(400, "빈 파일")

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        logger.info(f"[return-excel] 수신: {file.filename} ({len(content)} bytes)")

        # 1. 파싱
        parsed = parse_return_inbound_excel(tmp_path)
        if not parsed.get("parse_ok"):
            return {
                "ok": False,
                "data": {
                    "filename": file.filename,
                    "parse_ok": False,
                    "errors": parsed.get("errors", []),
                    "items": parsed.get("items", []),
                },
                "error": "파싱 실패",
                "detail": {"code": "PARSE_FAILED", "errors": parsed.get("errors", [])},
                "message": "Excel 파싱 실패",
            }

        # 2. DB 반영 (트랜잭션)
        result = process_return_inbound(engine, parsed, source_file=file.filename)

        if not result.get("success"):
            return {
                "ok": False,
                "data": {
                    "filename": file.filename,
                    "returned": result.get("returned", 0),
                    "errors": result.get("errors", []),
                    "details": result.get("details", []),
                },
                "error": "반품 처리 실패",
                "detail": {"code": "RETURN_FAILED", "errors": result.get("errors", [])},
                "message": "반품 처리 중 실패 — 전체 롤백",
            }

        logger.info(
            f"[return-excel] 완료: {result.get('returned', 0)}건 반품 복구 ({file.filename})"
        )
        return {
            "ok": True,
            "data": {
                "filename": file.filename,
                "returned": result.get("returned", 0),
                "details": result.get("details", [])[:50],
            },
            "message": f"{result.get('returned', 0)}건 반품 입고 완료",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[return-excel] 예기치 않은 에러: {e}")
        raise HTTPException(500, f"Internal error: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass



class PdfInboundRequest(BaseModel):
    pdf_base64: str
    filename: str = "upload.pdf"


# ────────────────────────────────────────────────────────────
# F001 PDF 스캔 입고 — multipart 업로드 (base64 대안)
# 프론트에서 FormData 로 바로 PDF 전송 가능 (base64 인코딩 불필요)
# 내부적으로 /pdf base64 엔드포인트와 동일 로직 재사용
# ────────────────────────────────────────────────────────────
@router.post("/pdf-upload", summary="📄 PDF 스캔 입고 — multipart 업로드 (F001)")
async def pdf_inbound_upload(file: UploadFile = File(...)):
    """
    multipart/form-data 로 PDF 업로드 후 /api/inbound/pdf 와 동일하게 처리.
    """
    if not file.filename:
        raise HTTPException(400, "파일명 없음")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, f"PDF 파일만 지원. 받은 파일: {file.filename}")

    content = await file.read()
    if not content:
        raise HTTPException(400, "빈 파일")
    if content[:4] != b"%PDF":
        raise HTTPException(400, "유효한 PDF 파일이 아닙니다")

    # base64 인코딩 후 내부 함수 호출 — 로직 재사용
    import base64 as _b64
    req = PdfInboundRequest(
        pdf_base64=_b64.b64encode(content).decode("ascii"),
        filename=file.filename,
    )
    return pdf_inbound(req)


# ────────────────────────────────────────────────────────────
# [Sprint 1-2-B] OneStop 입고 — 4종 multipart + 크로스체크
#
# v864-2 source: gui_app_modular/dialogs/onestop_inbound.py
# Input: 4 multipart PDFs (BL, PL required; Invoice, DO optional)
# Flow:
#   1. 각 PDF 임시 저장
#   2. parsers.document_parser_modular.DocumentParserV3 로 4종 파싱
#   3. parsers.cross_check_engine.cross_check_documents 로 교차 검증
#   4. PL 결과만 기존 pdf_inbound 로직으로 DB 저장 (Sprint 1-2-C에서 4종 병합 저장)
#   5. 응답: cross_check 요약 + 18열 preview_rows + 저장 결과
# ────────────────────────────────────────────────────────────
def _safe_attr(obj, *names, default=""):
    """객체에서 첫 번째로 존재하고 truthy 한 속성값 반환."""
    if not obj:
        return default
    for n in names:
        v = getattr(obj, n, None)
        if v:
            return v
    return default


def _parse_one(parser, path, doc_type_method: str, **kwargs):
    """파싱 함수 호출. 실패 시 None 반환 (4종 중 하나 실패해도 나머지 진행).
    kwargs: bag_weight_kg, gemini_hint 등 파서에 직접 전달"""
    if not path:
        return None
    try:
        fn = getattr(parser, doc_type_method)
        return fn(path, **kwargs) if kwargs else fn(path)
    except Exception as e:
        logger.warning(f"{doc_type_method} 파싱 실패: {e}", exc_info=True)
        return None


@router.post(
    "/onestop-upload",
    summary="📥 OneStop 입고 — 4종 PDF multipart + 크로스체크 (v864-2 OneStopInboundDialog)",
)
async def onestop_inbound_upload(
    bl: "UploadFile | None" = File(None),
    pl: UploadFile = File(...),
    invoice: "UploadFile | None" = File(None),
    do_file: "UploadFile | None" = File(None),
    dry_run: bool = Query(True, description="True면 파싱만 실행, DB 저장은 하지 않음 (Sprint 1-2-C 기본값)"),
    bag_weight_kg: Optional[int] = Form(None, description="톤백 단위 무게 (500 or 1000). None이면 파서 기본값 사용"),
    gemini_hint: str = Form("", description="Gemini AI 파싱 힌트 (DB 템플릿에서 주입)"),
    template_id: Optional[str] = Form(None, description="사용된 inbound_template ID (로깅 용도)"),
    manual_arrival: str = Form("", description="manual ARRIVAL date (YYYY-MM-DD) fallback when DO absent"),
    manual_con_return: str = Form("", description="manual CON RETURN date (YYYY-MM-DD) fallback when DO absent"),
    use_gemini: bool = Form(False, description="True=좌표+Gemini 병행 파싱 (비교 모드)"),
):
    """
    4종 PDF 를 업로드하면 파싱 + 크로스체크 (+ 선택적 PL DB 저장) 수행.

    - `pl`: Packing List (필수)
    - `bl`: Bill of Lading (선택 — 크로스체크 용도)
    - `invoice`: Invoice / FA (선택 — 크로스체크 용도)
    - `do_file`: Delivery Order (선택 — 크로스체크 + 나중에 등록 가능)
    - `dry_run`: True(기본) = 파싱만, False = 기존처럼 PL 자동 저장 (레거시 호환)

    v864-2 워크플로우를 따르려면 `dry_run=True` 로 파싱 → 프론트에서 편집 →
    `/api/inbound/onestop-save` 호출로 최종 저장.
    """
    # 1. 각 파일 임시 저장
    inputs = [
        ("pl", pl, True),
        ("bl", bl, False),
        ("invoice", invoice, False),
        ("do", do_file, False),
    ]
    tmp_paths: "dict[str, str | None]" = {}
    for key, uf, required in inputs:
        if uf is None:
            if required:
                raise HTTPException(400, f"{key}: 파일이 없습니다 (필수)")
            tmp_paths[key] = None
            continue
        if not uf.filename or not uf.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"{key}: PDF 파일만 지원 (받음: {uf.filename})")
        content = await uf.read()
        if not content:
            raise HTTPException(400, f"{key}: 빈 파일")
        if content[:4] != b"%PDF":
            raise HTTPException(400, f"{key}: 유효한 PDF 파일이 아닙니다")
        tf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tf.write(content)
        tf.close()
        tmp_paths[key] = tf.name

    try:
        # 2. 파서 로드 + 4종 파싱
        try:
            from parsers.document_parser_modular.parser import DocumentParserV3
            parser = DocumentParserV3()
        except Exception as e:
            logger.error(f"DocumentParserV3 로드 실패: {e}", exc_info=True)
            raise HTTPException(500, f"파서 로드 실패: {e}")

        # PL에만 bag_weight_kg + gemini_hint 전달 (나머지 문서는 kwargs 없이)
        pl_kwargs = {}
        if bag_weight_kg is not None:
            pl_kwargs["bag_weight_kg"] = bag_weight_kg
        if gemini_hint:
            pl_kwargs["gemini_hint"] = gemini_hint
        _warn_messages: list = []
        tpl_product = ""
        tpl_carrier_id = ""
        if template_id:
            try:
                from config import DB_PATH as _DP
                import sqlite3 as _sq
                _con = _sq.connect(str(_DP))
                _r = _con.execute(
                    "SELECT product_hint, carrier_id FROM inbound_template WHERE template_id=?",
                    (template_id,)
                ).fetchone()
                _con.close()
                if _r:
                    tpl_product = (_r[0] or "").strip()
                    tpl_carrier_id = (_r[1] or "").strip()
            except Exception as _e:
                logger.warning(f"[onestop] 템플릿 조회 실패 (무시, fallback=빈 hint): {_e}")
                tpl_product = ""
                _warn_messages.append("템플릿 조회 실패")
            logger.info(f"[onestop] DB 템플릿 #{template_id} 적용 — bag_weight={bag_weight_kg}kg, hint='{gemini_hint[:40]}', product='{tpl_product}', carrier='{tpl_carrier_id}'")

        parsed = {
            "packing_list": _parse_one(parser, tmp_paths["pl"], "parse_packing_list", **pl_kwargs),
            "bl":           _parse_one(parser, tmp_paths["bl"], "parse_bl", **({} if not tpl_carrier_id else {"carrier_id": tpl_carrier_id})),
            "invoice":      _parse_one(parser, tmp_paths["invoice"], "parse_invoice"),
            "do":           _parse_one(parser, tmp_paths["do"], "parse_do", **({} if not tpl_carrier_id else {"carrier_id": tpl_carrier_id})),
        }
        # ── parse_alarm 체크 (v8.6.6) ──────────────────────────────
        _alarm_reports: dict = {}
        try:
            from utils.parse_alarm import check_bl, check_do, check_invoice, check_packing
            _alarm_reports = {
                "bl":      check_bl(parsed["bl"],            tpl_carrier_id),
                "do":      check_do(parsed["do"],            tpl_carrier_id),
                "invoice": check_invoice(parsed["invoice"],  tpl_carrier_id),
                "pl":      check_packing(parsed["packing_list"], tpl_carrier_id),
            }
            for _doc_key, _ar in _alarm_reports.items():
                _ar.log()  # logger.warning 으로 CRITICAL/WARNING 출력
                for _a in _ar.criticals:
                    _warn_messages.append(f"[{_doc_key.upper()} CRITICAL] {_a.field}: {_a.message}")
                for _a in _ar.warnings:
                    _warn_messages.append(f"[{_doc_key.upper()} WARNING] {_a.field}: {_a.message}")
        except Exception as _ae:
            logger.warning(f"[onestop] parse_alarm 실행 실패 (건너뜀): {_ae}")
            _alarm_reports = {}

        if parsed["packing_list"] is None:
            raise HTTPException(422, "Packing List 파싱 실패 (최소 1종은 파싱되어야 합니다)")

        # 3. 크로스체크
        xc_items, xc_summary, xc_counts = [], "", {}
        try:
            from parsers.cross_check_engine import cross_check_documents
            xc = cross_check_documents(
                invoice=parsed["invoice"],
                packing_list=parsed["packing_list"],
                bl=parsed["bl"],
                do=parsed["do"],
            )
            xc_summary = xc.summary
            xc_counts = {
                "critical": xc.critical_count,
                "warning":  xc.warning_count,
                "info":     xc.info_count,
                "has_critical": xc.has_critical,
            }
            xc_items = [
                {
                    "field": it.field_name,
                    "level": int(it.level),
                    "icon": it.level_icon,
                    "message": it.message,
                    "sources": it.sources,
                }
                for it in xc.items
            ]
        except Exception as e:
            logger.warning(f"cross_check_documents 실패 — 건너뜀: {e}", exc_info=True)
            xc = None
            xc_summary = f"크로스체크 오류 ({e.__class__.__name__}) — 결과 미검증"
            xc_counts = {"critical": 0, "warning": 0, "info": 0, "has_critical": False}
            _warn_messages.append(f"크로스체크 엔진 오류 ({e.__class__.__name__})")

        # 4. 18열 preview_rows 조립 (v864-2 PREVIEW_COLUMNS 매칭)
        preview_rows = []
        pl_obj = parsed["packing_list"]
        pl_rows = getattr(pl_obj, "rows", None) or getattr(pl_obj, "lots", None) or []
        bl_no = _safe_attr(parsed["bl"], "bl_no", "bl_number")
        inv_no = _safe_attr(parsed["invoice"], "invoice_no", "invoice_number")
        inv_sap = _safe_attr(parsed["invoice"], "sap_no", "sap_number", "po_no") if parsed.get("invoice") else ""
        ship_date = _safe_attr(parsed["bl"], "ship_date", "shipped_on_board")
        arrival = _safe_attr(parsed["do"], "arrival_date", "eta")
        # con_return / free_time: extract from DOData.free_time_info list (v864.2 port)
        _do_obj = parsed["do"]
        _ft_infos = (getattr(_do_obj, "free_time_info", None) or []) if _do_obj else []
        con_return = ""
        free_time = ""
        for _ft in _ft_infos:
            if isinstance(_ft, dict):
                _ftd = _ft.get("free_time_date") or _ft.get("free_time_until") or ""
            else:
                _ftd = getattr(_ft, "free_time_date", "") or getattr(_ft, "free_time_until", "") or ""
            if _ftd and str(_ftd) not in ("", "None"):
                try:
                    from utils.date_utils import normalize_date_str as _norm_date_str
                    con_return = _norm_date_str(_ftd) or str(_ftd)[:10]
                    break
                except Exception:
                    con_return = str(_ftd)[:10]
                    break
        if con_return and arrival and str(arrival) not in ("", "None"):
            try:
                from utils.date_utils import calculate_free_days as _calc_free_days
                _days = _calc_free_days(arrival, con_return)
                if _days is not None:
                    free_time = str(_days)
            except Exception:
                pass
        wh = (getattr(_do_obj, "warehouse_name", "") or getattr(_do_obj, "warehouse", "")) if _do_obj else ""
        # manual fallback: apply when DO absent or parse missed the field
        if not arrival and manual_arrival:
            arrival = manual_arrival
        if not con_return and manual_con_return:
            try:
                from utils.date_utils import normalize_date_str as _norm_date_str
                con_return = _norm_date_str(manual_con_return) or manual_con_return
            except Exception:
                con_return = manual_con_return
            if not free_time and arrival:
                try:
                    from utils.date_utils import calculate_free_days as _calc_free_days
                    _days = _calc_free_days(arrival, con_return)
                    if _days is not None:
                        free_time = str(_days)
                except Exception:
                    pass

        # PL 헤더 레벨 공통값 (행별 아님 — 1페이지 고정 좌표 추출)
        pl_header_product = str(getattr(pl_obj, "product", "") or "")
        pl_header_code    = str(getattr(pl_obj, "code", "") or "")

        for idx, row in enumerate(pl_rows, start=1):
            lot = str(_safe_attr(row, "lot_no", "lot")).strip()
            xc_tag = xc.get_row_tag(lot) if xc and lot else None
            preview_rows.append({
                "no": idx,
                "lot_no":      lot,
                "sap_no":      str(_safe_attr(row, "sap_no") or inv_sap),
                "bl_no":       str(bl_no),
                "product":     str(_safe_attr(row, "product", "product_name") or pl_header_product or tpl_product),
                "status":      "NEW",
                "container":   str(_safe_attr(row, "container_no", "container")),
                "code":        str(_safe_attr(row, "product_code", "code") or pl_header_code),
                "lot_sqm":     str(_safe_attr(row, "lot_sqm")),
                "mxbg":        str(_safe_attr(row, "mxbg_pallet", "maxibag")),
                "net_kg":      str(_safe_attr(row, "net_weight", "net_kg")),
                "gross_kg":    str(_safe_attr(row, "gross_weight", "gross_kg")),
                "invoice_no":  str(inv_no),
                "ship_date":   str(ship_date),
                "arrival":     str(arrival),
                "con_return":  str(con_return),
                "free_time":   str(free_time),
                "wh":          str(wh),
                "xc_tag":      xc_tag,
            })

        # 4-B. Gemini 병행 파싱 (compare_mode)
        compare_mode = False
        gemini_preview_rows: list = []
        gemini_compare_status = "not_requested"
        gemini_compare_message = ""
        if use_gemini:
            gemini_compare_status = "requested"
            try:
                g_pl = _gemini_parse_pdf(tmp_paths["pl"], pl.filename if pl else "")
                if g_pl is not None:
                    _g_header_product = str(getattr(g_pl, "product", "") or "")
                    _g_header_code    = str(getattr(g_pl, "code", "") or "")
                    g_rows = getattr(g_pl, "rows", None) or getattr(g_pl, "lots", None) or []
                    for _gi, _gr in enumerate(g_rows, start=1):
                        gemini_preview_rows.append({
                            "no": _gi,
                            "lot_no":     str(_safe_attr(_gr, "lot_no", "lot")).strip(),
                            "sap_no":     str(_safe_attr(_gr, "sap_no") or inv_sap),
                            "bl_no":      str(bl_no),
                            "product":    str(_safe_attr(_gr, "product", "product_name") or _g_header_product or tpl_product),
                            "status":     "NEW",
                            "container":  str(_safe_attr(_gr, "container_no", "container")),
                            "code":       str(_safe_attr(_gr, "product_code", "code") or _g_header_code),
                            "lot_sqm":    str(_safe_attr(_gr, "lot_sqm")),
                            "mxbg":       str(_safe_attr(_gr, "mxbg_pallet", "maxibag")),
                            "net_kg":     str(_safe_attr(_gr, "net_weight", "net_kg")),
                            "gross_kg":   str(_safe_attr(_gr, "gross_weight", "gross_kg")),
                            "invoice_no": str(inv_no),
                            "ship_date":  str(ship_date),
                            "arrival":    str(arrival),
                            "con_return": str(con_return),
                            "free_time":  str(free_time),
                            "wh":         str(wh),
                            "xc_tag":     None,
                        })
                    compare_mode = len(gemini_preview_rows) > 0
                    gemini_compare_status = "ok" if compare_mode else "empty"
                    if not compare_mode:
                        gemini_compare_message = "Gemini 파싱 결과가 0건입니다."
                    logger.info(f"[compare] Gemini PL: {len(gemini_preview_rows)} rows")
                else:
                    gemini_compare_status = "failed"
                    gemini_compare_message = "Gemini 파싱 실패 (결과 없음)"
                    _warn_messages.append("Gemini 파싱 실패 (결과 없음) — 좌표 결과만 표시")
            except Exception as _ge:
                logger.warning(f"[compare] Gemini PL error: {_ge}")
                gemini_compare_status = "error"
                gemini_compare_message = f"Gemini 파싱 오류 ({_ge.__class__.__name__})"
                _warn_messages.append(f"Gemini 파싱 오류 ({_ge.__class__.__name__}) — 좌표 결과만 표시")

        # 5. PL 데이터 DB 저장 — dry_run=True 면 스킵 (Sprint 1-2-C 기본값)
        saved_result = None
        if not dry_run:
            try:
                with open(tmp_paths["pl"], "rb") as f:
                    pl_bytes = f.read()
                import base64 as _b64
                save_req = PdfInboundRequest(
                    pdf_base64=_b64.b64encode(pl_bytes).decode("ascii"),
                    filename=pl.filename,
                )
                saved_result = pdf_inbound(save_req)
            except Exception as e:
                logger.warning(f"PL DB 저장 실패 (파싱은 성공): {e}", exc_info=True)
                saved_result = {"ok": False, "message": f"DB 저장 실패: {e}"}

        # 6. 응답 조립
        return {
            "ok": True,
            "message": (
                f"4종 파싱 완료 — PL LOT {len(preview_rows)}개"
                + (f" | {xc_summary}" if xc_summary else "")
            ),
            "warn_messages": _warn_messages,
            "data": {
                "preview_rows": preview_rows,
                "preview_count": len(preview_rows),
                "cross_check": {
                    "summary": xc_summary,
                    **xc_counts,
                    "items": xc_items,
                },
                "parsed_docs": {
                    "bl_loaded":      parsed["bl"] is not None,
                    "pl_loaded":      parsed["packing_list"] is not None,
                    "invoice_loaded": parsed["invoice"] is not None,
                    "do_loaded":      parsed["do"] is not None,
                },
                # ── 파싱 알람 결과 (v8.6.6) ──
                "parse_alarms": {
                    k: v.to_dict() for k, v in _alarm_reports.items()
                } if _alarm_reports else {},
                "parse_alarms_summary": {
                    k: {
                        "has_critical": v.has_critical,
                        "has_warning":  v.has_warning,
                        "critical_count": len(v.criticals),
                        "warning_count":  len(v.warnings),
                    } for k, v in _alarm_reports.items()
                } if _alarm_reports else {},
                "saved_result": (saved_result.get("data") if isinstance(saved_result, dict) else None),
                "compare_mode": compare_mode,
                "compare_requested": bool(use_gemini),
                "compare_status": gemini_compare_status,
                "compare_message": gemini_compare_message,
                "coord_rows":   preview_rows if use_gemini else [],
                "gemini_rows":  gemini_preview_rows,
                "bl_no":      str(bl_no),
                "invoice_no": str(inv_no),
                # ── BL 상세 (v8.6.6) ──
                "bl_detail": {
                    "vessel":            str(getattr(parsed["bl"], "vessel", "") or ""),
                    "voyage":            str(getattr(parsed["bl"], "voyage", "") or ""),
                    "port_of_loading":   str(getattr(parsed["bl"], "port_of_loading", "") or ""),
                    "port_of_discharge": str(getattr(parsed["bl"], "port_of_discharge", "") or ""),
                    "shipper":           str(getattr(parsed["bl"], "shipper_name", "") or getattr(parsed["bl"], "shipper", "") or ""),
                    "consignee":         str(getattr(parsed["bl"], "consignee_name", "") or getattr(parsed["bl"], "consignee", "") or ""),
                    "ship_date":         str(ship_date),
                    "gross_weight_kg":   getattr(parsed["bl"], "gross_weight_kg", None),
                    "carrier_id":        str(getattr(parsed["bl"], "carrier_id", "") or ""),
                } if parsed["bl"] else {},
                # ── Invoice 상세 (v8.6.6) ──
                "invoice_detail": {
                    "sap_no":           str(getattr(parsed["invoice"], "sap_no", "") or ""),
                    "invoice_no":       str(inv_no),
                    "bl_no":            str(getattr(parsed["invoice"], "bl_no", "") or ""),
                    "product_name":     str(getattr(parsed["invoice"], "product_name", "") or ""),
                    "product_code":     str(getattr(parsed["invoice"], "product_code", "") or ""),
                    "quantity_mt":      getattr(parsed["invoice"], "quantity_mt", None),
                    "unit_price":       getattr(parsed["invoice"], "unit_price", None),
                    "total_amount":     getattr(parsed["invoice"], "total_amount", None),
                    "currency":         str(getattr(parsed["invoice"], "currency", "") or ""),
                    "net_weight_kg":    getattr(parsed["invoice"], "net_weight_kg", None),
                    "gross_weight_kg":  getattr(parsed["invoice"], "gross_weight_kg", None),
                    "package_count":    getattr(parsed["invoice"], "package_count", None),
                    "package_type":     str(getattr(parsed["invoice"], "package_type", "") or ""),
                    "incoterm":         str(getattr(parsed["invoice"], "incoterm", "") or ""),
                    "origin":           str(getattr(parsed["invoice"], "origin", "") or ""),
                    "destination":      str(getattr(parsed["invoice"], "destination", "") or ""),
                    "customer_name":    str(getattr(parsed["invoice"], "customer_name", "") or ""),
                } if parsed["invoice"] else {},
                # ── DO 상세 (v8.6.6) ──
                "do_detail": {
                    "do_no":            str(getattr(parsed["do"], "do_no", "") or ""),
                    "bl_no":            str(getattr(parsed["do"], "bl_no", "") or ""),
                    "vessel":           str(getattr(parsed["do"], "vessel", "") or ""),
                    "voyage":           str(getattr(parsed["do"], "voyage", "") or ""),
                    "arrival_date":     str(arrival),
                    "issue_date":       str(getattr(parsed["do"], "issue_date", "") or ""),
                    "con_return":       str(con_return),
                    "free_time_days":   str(free_time),
                    "gross_weight_kg":  getattr(parsed["do"], "gross_weight_kg", None),
                    "mrn":              str(getattr(parsed["do"], "mrn", "") or ""),
                    "cbm":              getattr(parsed["do"], "cbm", None),
                } if parsed["do"] else {},
                # ── PL 헤더 상세 (v8.6.6) ──
                "pl_detail": {
                    "folio":            str(getattr(pl_obj, "folio", "") or ""),
                    "product":          str(getattr(pl_obj, "product", "") or ""),
                    "code":             str(pl_header_code),
                    "packing":          str(getattr(pl_obj, "packing", "") or ""),
                    "vessel":           str(getattr(pl_obj, "vessel", "") or ""),
                    "customer":         str(getattr(pl_obj, "customer", "") or ""),
                    "destination":      str(getattr(pl_obj, "destination", "") or ""),
                    "sap_no":           str(getattr(pl_obj, "sap_no", "") or getattr(parsed.get("invoice"), "sap_no", "") or ""),
                    "total_lots":       getattr(pl_obj, "total_lots", 0),
                    "total_maxibag":    getattr(pl_obj, "total_maxibag", 0),
                    "total_net_kg":     getattr(pl_obj, "total_net_weight_kg", 0),
                    "total_gross_kg":   getattr(pl_obj, "total_gross_weight_kg", 0),
                } if pl_obj else {},
            },
        }
    finally:
        for p in tmp_paths.values():
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


# ────────────────────────────────────────────────────────────
# [Sprint 1-2-C] OneStop 입고 — 편집된 미리보기 → DB 저장
#
# v864-2 workflow: 파싱 → 미리보기에서 편집 → 확인 → DB 저장
# Frontend 는 /onestop-upload?dry_run=true 로 파싱만 받은 뒤,
# 18열 테이블에서 더블클릭으로 셀 편집하고, "DB 업로드" 버튼 클릭시
# 편집된 preview_rows JSON 을 이 엔드포인트로 POST.
# ────────────────────────────────────────────────────────────
class OneStopSaveRequest(BaseModel):
    rows: "list[dict]"


# 프론트 preview_rows (18열) → engine.add_inventory_from_dict 표준 키 매핑
_ONESTOP_ROW_KEY_MAP = {
    "lot_no":           "lot_no",
    "sap_no":           "sap_no",
    "bl_no":            "bl_no",
    "product":          "product",
    "container":        "container_no",
    "code":             "product_code",
    "lot_sqm":          "lot_sqm",
    "mxbg":             "mxbg_pallet",
    "net_kg":           "net_weight",
    "gross_kg":         "gross_weight",
    "invoice_no":       "salar_invoice_no",
    "ship_date":        "ship_date",
    "arrival":          "arrival_date",
    "con_return":       "con_return",
    "free_time":        "free_time",
    "wh":               "warehouse",
}


def _onestop_row_to_engine_dict(row: dict) -> dict:
    """프론트 18열 row → engine.add_inventory_from_dict 입력 dict 변환."""
    out = {}
    for fe_key, eng_key in _ONESTOP_ROW_KEY_MAP.items():
        v = row.get(fe_key)
        if v is None:
            continue
        if isinstance(v, str):
            v = v.strip()
            if not v:
                continue
        out[eng_key] = v
    return out


@router.post(
    "/onestop-save",
    summary="📤 OneStop 입고 — 편집된 18열 미리보기 → DB 저장 (Sprint 1-2-C)",
)
def onestop_inbound_save(req: OneStopSaveRequest):
    """
    /onestop-upload?dry_run=true 로 파싱 후 프론트에서 편집된 preview_rows 를
    받아 실제 DB에 저장.

    각 row 는 18개 필드를 가진 dict (lot_no/sap_no/bl_no/... /wh) 이며,
    engine.add_inventory_from_dict 로 저장된다.
    """
    rows = req.rows or []
    if not rows:
        raise HTTPException(400, "rows 가 비어있습니다")

    # 엔진 확인
    try:
        from backend.api import engine, ENGINE_AVAILABLE
    except Exception as e:
        raise HTTPException(500, f"엔진 로드 실패: {e}")
    if not ENGINE_AVAILABLE or engine is None:
        raise HTTPException(500, "엔진이 사용 불가 상태입니다.")

    success_count, fail_count = 0, 0
    errors: "list[dict]" = []

    for idx, row in enumerate(rows, start=1):
        data = _onestop_row_to_engine_dict(row)
        if not data.get("lot_no"):
            fail_count += 1
            errors.append({"row": idx, "reason": "lot_no 빈 값"})
            continue
        try:
            result = engine.add_inventory_from_dict(data)
            if result.get("success"):
                success_count += 1
            else:
                fail_count += 1
                errors.append({
                    "row":    idx,
                    "lot_no": str(data.get("lot_no", "")),
                    "reason": result.get("message") or result.get("error") or "unknown",
                })
        except Exception as e:
            fail_count += 1
            errors.append({
                "row":    idx,
                "lot_no": str(data.get("lot_no", "")),
                "reason": f"exception: {e}",
            })
            logger.warning(f"[onestop-save] row {idx} 실패: {e}")

    logger.info(f"[onestop-save] 완료: 성공 {success_count} / 실패 {fail_count} / 총 {len(rows)}")

    return {
        "ok": True,
        "data": {
            "total":         len(rows),
            "success_count": success_count,
            "fail_count":    fail_count,
            "errors":        errors[:50],  # 최대 50건
        },
        "message": f"{success_count}건 입고 완료 / {fail_count}건 실패",
    }


@router.post("/pdf")
def pdf_inbound(req: PdfInboundRequest):
    """
    PDF 스캔 입고 처리.
    1. base64 디코드 -> 임시 파일
    2. parsers.pdf_parser 로 문서 파싱
    3. 파싱 결과 DB 저장 (engine_modules 재활용)
    4. 결과 반환
    """
    # 1. base64 decode
    try:
        pdf_bytes = base64.b64decode(req.pdf_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {e}")

    if len(pdf_bytes) < 4 or pdf_bytes[:4] != b"%PDF":
        raise HTTPException(status_code=400, detail="Not a valid PDF file")

    # 2. 임시 파일로 저장
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        # 3. Tier-1: pdf_parser (coordinate/text-based)
        parsed = None
        parse_error = None
        parse_method = "tier1_coord"
        try:
            from parsers.pdf_parser import SQMPdfParser
            parser = SQMPdfParser()
            parsed = parser.parse(tmp_path)
            logger.info(f"[Tier-1] PDF parsed OK: {req.filename}, type={type(parsed).__name__}")
        except ImportError:
            logger.warning("[Tier-1] pdf_parser unavailable (PyMuPDF missing?)")
            parse_error = "pdf_parser unavailable"
        except Exception as e:
            logger.warning(f"[Tier-1] pdf_parser error: {e}")
            parse_error = str(e)

        # Tier-1 quality check: PackingListData with 0 lots = incomplete
        tier1_lots = 0
        if parsed is not None and type(parsed).__name__ == "PackingListData":
            tier1_lots = getattr(parsed, "total_lots", 0)

        # 3-B. Tier-2 Fallback: Gemini Vision
        #   Condition: (1) Tier-1 failed (parsed None) OR (2) 0 lots
        gemini_used = False
        if parsed is None or tier1_lots == 0:
            reason = "parse failed" if parsed is None else f"0 lots (folio={getattr(parsed,'folio','')})"
            logger.info(f"[Tier-2] Gemini fallback attempt - reason: {reason}, file={req.filename}")
            gemini_result = _gemini_parse_pdf(tmp_path, req.filename)
            if gemini_result is not None and getattr(gemini_result, "total_lots", 0) > 0:
                parsed = gemini_result
                parse_error = None
                gemini_used = True
                parse_method = "tier2_gemini"
                logger.info(f"[Tier-2] Gemini fallback OK: lots={parsed.total_lots}")
            else:
                logger.warning("[Tier-2] Gemini fallback failed or 0 lots")

        # 4. DB 저장 — v864.3: PackingListData.lots 순회하여 engine.add_inventory_from_dict()
        saved_count = 0
        save_errors = []
        saved_lots = []
        parse_type = type(parsed).__name__ if parsed is not None else None
        if parsed is not None and parse_type == "PackingListData":
            try:
                from backend.api import engine, ENGINE_AVAILABLE
                if ENGINE_AVAILABLE and engine is not None and hasattr(engine, "add_inventory_from_dict"):
                    # 공통 필드 (product, vessel 등) 전파
                    common = {
                        # ── Packing List 헤더 필드 → 모든 LOT에 전파 ──
                        "product":          getattr(parsed, "product", "") or "",
                        "product_code":     getattr(parsed, "product_code", "") or "",
                        "vessel":           getattr(parsed, "vessel", "") or "",
                        "folio":            getattr(parsed, "folio", "") or "",
                        # ── 타 서류에서 채워지는 필드 (PackingListData에 병합돼 있을 경우) ──
                        "sap_no":           getattr(parsed, "sap_no", "") or "",
                        "bl_no":            getattr(parsed, "bl_no", "") or "",
                        "salar_invoice_no": getattr(parsed, "salar_invoice_no", "") or "",
                        "ship_date":        getattr(parsed, "ship_date", None),
                        "arrival_date":     getattr(parsed, "arrival_date", None),
                    }
                    for idx, lot in enumerate(getattr(parsed, "lots", []) or []):
                        lot_data = dict(common)
                        lot_data.update(lot or {})
                        if not lot_data.get("lot_no"):
                            save_errors.append({"index": idx, "reason": "lot_no 없음"})
                            continue
                        try:
                            result = engine.add_inventory_from_dict(lot_data)
                            if result.get("success"):
                                saved_count += 1
                                saved_lots.append(str(lot_data.get("lot_no")))
                            else:
                                save_errors.append({
                                    "index": idx,
                                    "lot_no": str(lot_data.get("lot_no", "")),
                                    "reason": result.get("message") or result.get("error") or "unknown",
                                })
                        except Exception as e:
                            save_errors.append({
                                "index": idx,
                                "lot_no": str(lot_data.get("lot_no", "")),
                                "reason": f"exception: {e}",
                            })
                else:
                    save_errors.append({"reason": "엔진 사용 불가"})
            except Exception as e:
                logger.warning(f"[pdf-inbound] DB save error: {e}")
                save_errors.append({"reason": f"exception: {e}"})

        # 5. Response
        if parsed is not None:
            fallback_note = " [Gemini fallback]" if gemini_used else ""
            return {
                "ok": True,
                "success": True,
                "message": (
                    f"PDF parse OK ({req.filename}){fallback_note} "
                    f"saved={saved_count} failed={len(save_errors)}"
                ),
                "data": {
                    "filename": req.filename,
                    "size_bytes": len(pdf_bytes),
                    "parse_type": parse_type,
                    "parse_method": parse_method,
                    "gemini_fallback_used": gemini_used,
                    "ai_provider_used": getattr(parsed, "_ai_provider", "openai" if gemini_used else "coordinate"),
                    "tier1_lots": tier1_lots,
                    "saved_count": saved_count,
                    "saved_lots": saved_lots[:50],
                    "errors": save_errors[:50],
                    "folio": getattr(parsed, "folio", "") if parse_type == "PackingListData" else None,
                    "product": getattr(parsed, "product", "") if parse_type == "PackingListData" else None,
                    "lots_total": len(getattr(parsed, "lots", []) or []) if parse_type == "PackingListData" else None,
                },
            }
        else:
            return {
                "ok": False,
                "success": False,
                "message": f"PDF parse failed (Tier-1 + Tier-2 both failed): {parse_error or 'unknown'}",
                "error": parse_error or "parse failed",
                "detail": {
                    "code": "PDF_PARSE_FAILED",
                    "parse_error": parse_error,
                    "gemini_attempted": True,
                    "hint": "Check Gemini API key in Settings > Gemini",
                },
                "data": {
                    "filename": req.filename,
                    "size_bytes": len(pdf_bytes),
                    "parse_error": parse_error,
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"pdf_inbound unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

# Invoice / BL / DO 업로드 → 기존 LOT 업데이트 엔드포인트 3개

_INVOICE_UPDATE_FIELDS = {
    "sap_no":           "sap_no",
    "salar_invoice_no": "salar_invoice_no",
    "ship_date":        "ship_date",
    "total_amount":     "total_amount",
    "unit_price":       "unit_price",
    "invoice_date":     "invoice_date",
}

_BL_UPDATE_FIELDS = {
    "bl_no":    "bl_no",
    "vessel":   "vessel",
    "voyage":   "voyage",
    "ship_date":"ship_date",
}

_DO_UPDATE_FIELDS = {
    "arrival_date": "arrival_date",
    "free_time":    "free_time",
    "do_no":        "do_no",
    "con_return":   "con_return",
    "bl_no":        "bl_no",
}


def _db_update_lots(db_con, where_col: str, where_vals: list, update_dict: dict) -> dict:
    """DB에서 where_col IN where_vals 인 LOT들을 update_dict 필드로 UPDATE.
    Returns: {updated: int, lots: [lot_no, ...], skipped_empty: int}
    """
    if not where_vals or not update_dict:
        return {"updated": 0, "lots": [], "skipped_empty": 0}

    # 빈 값 제거
    pairs = {k: v for k, v in update_dict.items() if v not in (None, "", [])}
    skipped = len(update_dict) - len(pairs)
    if not pairs:
        return {"updated": 0, "lots": [], "skipped_empty": skipped}

    set_clause = ", ".join(f"{k} = ?" for k in pairs)
    placeholders = ",".join("?" * len(where_vals))
    sql = f"UPDATE inventory SET {set_clause} WHERE {where_col} IN ({placeholders})"
    params = list(pairs.values()) + where_vals

    cur = db_con.execute(sql, params)
    db_con.commit()

    # 업데이트된 LOT 번호 조회
    cur2 = db_con.execute(
        f"SELECT lot_no FROM inventory WHERE {where_col} IN ({placeholders})",
        where_vals
    )
    lots = [r[0] for r in cur2.fetchall()]
    return {"updated": cur.rowcount, "lots": lots, "skipped_empty": skipped}


def _table_columns(con, table_name: str) -> set:
    return {str(r[1]) for r in con.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _ensure_do_authority_columns(con) -> None:
    """D/O 후속 업데이트 출처 추적용 컬럼/감사 테이블 보정."""
    cols = _table_columns(con, "inventory")
    alter_sql = []
    if "arrival_date_source" not in cols:
        alter_sql.append("ALTER TABLE inventory ADD COLUMN arrival_date_source TEXT DEFAULT ''")
    if "do_updated_at" not in cols:
        alter_sql.append("ALTER TABLE inventory ADD COLUMN do_updated_at TEXT DEFAULT ''")
    for sql in alter_sql:
        try:
            con.execute(sql)
        except Exception as e:
            logger.debug("[do-upload] inventory 컬럼 보정 스킵: %s", e)

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT NOT NULL,
            event_data  TEXT,
            batch_id    TEXT,
            tonbag_id   TEXT,
            user_note   TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            created_by  TEXT DEFAULT 'WEBVIEW'
        )
        """
    )
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_event
        ON audit_log(event_type, created_at)
        """
    )
    con.commit()


def _normalize_for_compare(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s in ("None", "null", "NULL") else s


def _db_update_lots_from_do(con, *, bl_no: str, container_nos: list, update_dict: dict, source_file: str = "") -> dict:
    """
    D/O 후속 업로드 전용 권위 업데이트.

    D/O arrival_date는 PL ETA/수동 입력보다 우선한다. 기존 값과 다르면
    D/O 값으로 덮어쓰고 LOT별 변경 전후를 audit_log에 남긴다.
    """
    _ensure_do_authority_columns(con)

    pairs = {k: v for k, v in update_dict.items() if v not in (None, "", [])}
    if not pairs:
        return {"updated": 0, "lots": [], "changes": [], "skipped_empty": len(update_dict)}

    inv_cols = _table_columns(con, "inventory")
    set_pairs = {k: v for k, v in pairs.items() if k in inv_cols}
    now = _dt.now().isoformat(timespec="seconds")
    if "arrival_date" in set_pairs and "arrival_date_source" in inv_cols:
        set_pairs["arrival_date_source"] = "DO"
    if "do_updated_at" in inv_cols:
        set_pairs["do_updated_at"] = now
    if "updated_at" in inv_cols:
        set_pairs["updated_at"] = now
    if not set_pairs:
        return {"updated": 0, "lots": [], "changes": [], "skipped_empty": len(update_dict) - len(pairs)}

    clauses = []
    params = []
    if bl_no:
        clauses.append("bl_no = ?")
        params.append(bl_no)
    clean_containers = [str(c).strip() for c in container_nos or [] if str(c or "").strip()]
    if clean_containers:
        clauses.append("container_no IN (" + ",".join("?" * len(clean_containers)) + ")")
        params.extend(clean_containers)
    if not clauses:
        return {"updated": 0, "lots": [], "changes": [], "skipped_empty": len(update_dict) - len(pairs)}

    rows = [dict(r) for r in con.execute(
        "SELECT * FROM inventory WHERE " + " OR ".join(f"({c})" for c in clauses),
        params,
    ).fetchall()]
    if not rows:
        return {"updated": 0, "lots": [], "changes": [], "skipped_empty": len(update_dict) - len(pairs)}

    set_clause = ", ".join(f"{k}=?" for k in set_pairs)
    update_values = list(set_pairs.values())
    changed_lots = []
    audit_changes = []

    for row in rows:
        row_changes = {}
        for k, new_val in pairs.items():
            if k not in inv_cols:
                continue
            old_val = _normalize_for_compare(row.get(k))
            new_norm = _normalize_for_compare(new_val)
            if old_val != new_norm:
                row_changes[k] = {"old": old_val, "new": new_norm}

        # 권위 출처 컬럼만 바뀌는 경우도 기록 가능하게 업데이트는 수행한다.
        con.execute(
            f"UPDATE inventory SET {set_clause} WHERE id=?",
            update_values + [row.get("id")],
        )
        lot_no = str(row.get("lot_no") or "")
        changed_lots.append(lot_no)
        if row_changes:
            audit_changes.append({"lot_no": lot_no, "changes": row_changes})
            con.execute(
                """
                INSERT INTO audit_log
                    (event_type, event_data, user_note, created_by, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "DO_AUTHORITATIVE_UPDATE",
                    json.dumps({
                        "lot_no": lot_no,
                        "bl_no": bl_no,
                        "container_no": row.get("container_no"),
                        "source_file": source_file or "",
                        "changes": row_changes,
                        "policy": "D/O arrival_date overrides PL ETA/manual values",
                    }, ensure_ascii=False),
                    f"D/O 후속 업로드 권위값 반영: {lot_no}",
                    "WEBVIEW_DO_UPLOAD",
                    now,
                ),
            )

    con.commit()
    return {
        "updated": len(changed_lots),
        "lots": list(dict.fromkeys(changed_lots)),
        "changes": audit_changes,
        "skipped_empty": len(update_dict) - len(pairs),
    }


def _open_db():
    import sqlite3
    from config import DB_PATH
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def _ensure_inbound_template_columns(con):
    """Backward-compatible schema patch for legacy DBs.

    Some deployed DBs still have the v7.2 slim schema and miss
    `lot_sqm`, `mxbg_pallet`, `sap_no`. Ensure required columns exist
    before template CRUD/select queries run.
    """
    cols = {str(r[1]).lower() for r in con.execute("PRAGMA table_info(inbound_template)").fetchall()}
    alter_sql = []
    if "lot_sqm" not in cols:
        alter_sql.append("ALTER TABLE inbound_template ADD COLUMN lot_sqm TEXT DEFAULT ''")
    if "mxbg_pallet" not in cols:
        alter_sql.append("ALTER TABLE inbound_template ADD COLUMN mxbg_pallet INTEGER DEFAULT 0")
    if "sap_no" not in cols:
        alter_sql.append("ALTER TABLE inbound_template ADD COLUMN sap_no TEXT DEFAULT ''")
    if "bl_format" not in cols:
        alter_sql.append("ALTER TABLE inbound_template ADD COLUMN bl_format TEXT DEFAULT ''")

    if not alter_sql:
        return

    for sql in alter_sql:
        con.execute(sql)
    con.commit()
    logger.info(f"[templates] inbound_template 컬럼 자동 보정 적용: {len(alter_sql)}건")

# ─────────────────────────────────────────────────────────
# GET /api/inbound/templates — inbound_template 목록 반환
# ─────────────────────────────────────────────────────────
@router.get("/templates", summary="📋 입고 파싱 템플릿 목록 (DB)")
def get_inbound_templates():
    """inbound_template 테이블에서 활성 템플릿 전체 반환.
    프론트의 DB 템플릿 picker 에서 사용."""
    try:
        con = _open_db()
        _ensure_inbound_template_columns(con)
        cur = con.execute(
            "SELECT template_id, template_name, carrier_id, bag_weight_kg, "
            "gemini_hint_packing, gemini_hint_invoice, gemini_hint_bl, "
            "product_hint, weight_format, note, is_active, "
            "lot_sqm, mxbg_pallet, sap_no "
            "FROM inbound_template "
            "WHERE is_active = 1 "
            "AND UPPER(COALESCE(carrier_id, '')) <> 'UNKNOWN' "
            "AND UPPER(COALESCE(template_id, '')) NOT LIKE 'UNKNOWN_%' "
            "ORDER BY template_name"
        )
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return {"ok": True, "templates": rows, "count": len(rows)}
    except Exception as e:
        logger.warning(f"inbound_template 조회 실패: {e}", exc_info=True)
        return {"ok": False, "templates": [], "count": 0, "error": str(e)}

# ─────────────────────────────────────────────────────────
# POST /api/inbound/templates — 신규 템플릿 생성
# PUT  /api/inbound/templates/{tid} — 템플릿 수정
# DELETE /api/inbound/templates/{tid} — 템플릿 삭제
# POST /api/inbound/templates/from-pdf — PDF 파싱 → 템플릿 데이터 추출
# POST /api/inbound/templates/from-excel — Excel 일괄 등록
# ─────────────────────────────────────────────────────────
import uuid as _uuid
from datetime import datetime as _dt

class TemplateUpsertRequest(BaseModel):
    carrier_id:    str   = "UNKNOWN"
    template_name: str
    product_hint:  str   = ""
    bag_weight_kg: int   = 500
    bl_format:     str   = ""
    note:          str   = ""
    gemini_hint_packing: str = ""
    lot_sqm:       str   = ""
    mxbg_pallet:   int   = 0
    sap_no:        str   = ""


def _tpl_new_id() -> str:
    return _dt.now().strftime("%Y%m%d_%H%M%S_") + str(_uuid.uuid4())[:8]


@router.post("/templates", summary="📋 입고 템플릿 신규 생성")
def create_template(req: TemplateUpsertRequest):
    try:
        con = _open_db()
        _ensure_inbound_template_columns(con)
        tid = _tpl_new_id()
        con.execute(
            "INSERT INTO inbound_template "
            "(template_id, template_name, carrier_id, bag_weight_kg, "
            "product_hint, bl_format, note, gemini_hint_packing, is_active, "
            "lot_sqm, mxbg_pallet, sap_no) "
            "VALUES (?,?,?,?,?,?,?,?,1,?,?,?)",
            (tid, req.template_name, req.carrier_id, req.bag_weight_kg,
             req.product_hint, req.bl_format, req.note, req.gemini_hint_packing,
             req.lot_sqm, req.mxbg_pallet, req.sap_no)
        )
        con.commit()
        con.close()
        logger.info(f"[templates] 신규 생성: {tid} / {req.template_name}")
        return {"ok": True, "template_id": tid, "message": f"템플릿 생성 완료: {req.template_name}"}
    except Exception as e:
        logger.error(f"[templates] 생성 실패: {e}", exc_info=True)
        raise HTTPException(500, f"템플릿 생성 실패: {e}")


@router.put("/templates/{tid}", summary="📋 입고 템플릿 수정")
def update_template(tid: str, req: TemplateUpsertRequest):
    try:
        con = _open_db()
        _ensure_inbound_template_columns(con)
        cur = con.execute(
            "UPDATE inbound_template SET "
            "template_name=?, carrier_id=?, bag_weight_kg=?, "
            "product_hint=?, bl_format=?, note=?, gemini_hint_packing=?, "
            "lot_sqm=?, mxbg_pallet=?, sap_no=? "
            "WHERE template_id=?",
            (req.template_name, req.carrier_id, req.bag_weight_kg,
             req.product_hint, req.bl_format, req.note, req.gemini_hint_packing,
             req.lot_sqm, req.mxbg_pallet, req.sap_no, tid)
        )
        con.commit()
        con.close()
        if cur.rowcount == 0:
            raise HTTPException(404, f"템플릿 ID 없음: {tid}")
        logger.info(f"[templates] 수정: {tid}")
        return {"ok": True, "updated": cur.rowcount}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"수정 실패: {e}")


@router.delete("/templates/{tid}", summary="📋 입고 템플릿 삭제")
def delete_template(tid: str):
    try:
        con = _open_db()
        _ensure_inbound_template_columns(con)
        # 실제 삭제 대신 is_active=0 (soft delete)
        cur = con.execute(
            "UPDATE inbound_template SET is_active=0 WHERE template_id=?", (tid,)
        )
        con.commit()
        con.close()
        if cur.rowcount == 0:
            raise HTTPException(404, f"템플릿 ID 없음: {tid}")
        return {"ok": True, "deleted": tid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"삭제 실패: {e}")


@router.post("/templates/from-pdf", summary="📄 PDF 입고서 파싱 → 템플릿 데이터 추출")
async def template_from_pdf(file: UploadFile = File(...)):
    """Packing List PDF를 파싱해서 선사·제품명·톤백무게를 추출.
    결과를 프론트에 반환 → 사용자가 확인 후 저장 버튼 클릭 시 POST /templates 호출."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "PDF 파일만 지원합니다")
    content = await file.read()
    if not content:
        raise HTTPException(400, "빈 파일")

    tf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tf.write(content)
    tf.close()
    try:
        from parsers.document_parser_modular.parser import DocumentParserV3
        parser = DocumentParserV3()

        # PL 파싱
        pl = None
        try:
            pl = parser.parse_packing_list(tf.name)
        except Exception as e:
            logger.warning(f"[tpl/from-pdf] PL 파싱 실패: {e}")

        # BL 파싱 시도 (같은 파일)
        bl = None
        try:
            bl = parser.parse_bl(tf.name)
        except Exception:
            pass

        # 데이터 추출
        extracted = {
            "carrier_id":    "",
            "product_hint":  "",
            "bag_weight_kg": 500,
            "bl_format":     "",
            "source_file":   file.filename,
        }

        if pl:
            rows = getattr(pl, "rows", None) or getattr(pl, "lots", None) or []
            if rows:
                r0 = rows[0]
                extracted["product_hint"] = str(
                    getattr(r0, "product", None) or getattr(r0, "product_name", None) or ""
                )
            if getattr(pl, "bag_weight_kg", None):
                extracted["bag_weight_kg"] = int(pl.bag_weight_kg)
            # 선사: PL에 없으면 파일명에서 추론
            for carrier in ["Maersk","ONE","MSC","Evergreen","HMM","CMA CGM",
                            "Hapag","Yang Ming","ZIM","PIL","Wan Hai"]:
                if carrier.lower() in file.filename.lower():
                    extracted["carrier_id"] = carrier
                    break

        if bl:
            carrier_raw = str(getattr(bl, "carrier", None) or getattr(bl, "shipping_company", None) or "")
            if carrier_raw:
                extracted["carrier_id"] = carrier_raw
            bl_no = str(getattr(bl, "bl_no", None) or "")
            if bl_no:
                # BL 번호 앞 3~4자리 알파벳 = 형식 코드
                import re as _re
                m = _re.match(r'^([A-Z]{2,6})', bl_no)
                if m:
                    extracted["bl_format"] = m.group(1)

        # 제안 템플릿 이름
        carrier_label = extracted["carrier_id"] or "선사미상"
        product_label = extracted["product_hint"][:20] if extracted["product_hint"] else "제품"
        extracted["suggested_name"] = f"{carrier_label} {product_label} {extracted['bag_weight_kg']}kg"

        return {"ok": True, "extracted": extracted,
                "message": f"파싱 완료: {file.filename} → 아래 내용을 확인 후 저장하세요"}
    finally:
        try:
            os.unlink(tf.name)
        except Exception:
            pass


@router.post("/templates/from-excel", summary="📊 Excel 파일 → 템플릿 일괄 등록")
async def templates_from_excel(file: UploadFile = File(...)):
    """Excel/CSV 파일에서 템플릿을 일괄 생성.

    Excel 컬럼 순서 (헤더 행 필수):
      carrier | template_name | product_name | bag_weight_kg | bl_format | note

    또는 한글 헤더:
      선사 | 템플릿이름 | 제품이름 | 톤백무게 | BL형식 | 메모
    """
    fname = file.filename or ""
    if not (fname.lower().endswith(".xlsx") or fname.lower().endswith(".xls")
            or fname.lower().endswith(".csv")):
        raise HTTPException(400, "xlsx / xls / csv 파일만 지원합니다")

    content = await file.read()
    if not content:
        raise HTTPException(400, "빈 파일")

    tf = tempfile.NamedTemporaryFile(
        suffix=os.path.splitext(fname)[1], delete=False
    )
    tf.write(content)
    tf.close()

    try:
        import pandas as pd
        if fname.lower().endswith(".csv"):
            df = pd.read_csv(tf.name, encoding="utf-8-sig")
        else:
            df = pd.read_excel(tf.name, engine="openpyxl")

        # 컬럼 정규화 (한글/영문 모두 허용)
        COL_MAP = {
            "carrier":       "carrier_id",
            "선사":           "carrier_id",
            "template_name": "template_name",
            "템플릿이름":      "template_name",
            "템플릿 이름":     "template_name",
            "product_name":  "product_hint",
            "제품이름":        "product_hint",
            "제품 이름":       "product_hint",
            "bag_weight_kg": "bag_weight_kg",
            "톤백무게":        "bag_weight_kg",
            "톤백 무게":       "bag_weight_kg",
            "bl_format":     "bl_format",
            "bl형식":         "bl_format",
            "BL형식":         "bl_format",
            "note":          "note",
            "메모":           "note",
        }
        df.columns = [COL_MAP.get(str(c).strip(), str(c).strip()) for c in df.columns]

        required = ["template_name"]
        for col in required:
            if col not in df.columns:
                raise HTTPException(400, f"필수 컬럼 없음: '{col}' (영문 또는 한글 헤더 필요)")

        con = _open_db()
        created, skipped = 0, 0
        for _, row in df.iterrows():
            tname = str(row.get("template_name", "")).strip()
            if not tname:
                skipped += 1
                continue
            tid = _tpl_new_id()
            try:
                con.execute(
                    "INSERT INTO inbound_template "
                    "(template_id, template_name, carrier_id, bag_weight_kg, "
                    "product_hint, bl_format, note, is_active) "
                    "VALUES (?,?,?,?,?,?,?,1)",
                    (
                        tid,
                        tname,
                        str(row.get("carrier_id", "UNKNOWN")).strip(),
                        int(float(row.get("bag_weight_kg", 500) or 500)),
                        str(row.get("product_hint", "")).strip(),
                        str(row.get("bl_format", "")).strip(),
                        str(row.get("note", "")).strip(),
                    )
                )
                created += 1
            except Exception as e:
                logger.warning(f"[tpl/excel] 행 스킵: {e}")
                skipped += 1
        con.commit()
        con.close()
        logger.info(f"[templates/excel] 생성 {created}건 / 스킵 {skipped}건")
        return {"ok": True, "created": created, "skipped": skipped,
                "message": f"Excel 등록 완료: {created}개 생성, {skipped}개 스킵"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[tpl/excel] 실패: {e}", exc_info=True)
        raise HTTPException(500, f"Excel 파싱 실패: {e}")
    finally:
        try:
            os.unlink(tf.name)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────
# POST /api/inbound/invoice
# ─────────────────────────────────────────────────────────
@router.post("/invoice", summary="Invoice(FA) PDF 업로드 → 기존 LOT 업데이트")
async def inbound_invoice(file: UploadFile = File(...)):
    """Invoice PDF 파싱 → folio 또는 sap_no로 LOT 매칭 → 금액/선적일 업데이트"""
    tmp_path = None
    try:
        pdf_bytes = await file.read()
        if len(pdf_bytes) < 4 or pdf_bytes[:4] != b"%PDF":
            raise HTTPException(400, "Not a valid PDF file")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        from parsers.pdf_parser import PDFParser
        parser = PDFParser()
        parsed = parser.parse(tmp_path)

        if parsed is None or type(parsed).__name__ != "InvoiceData":
            return {"ok": False, "message": "Invoice 파싱 실패 — Invoice 서류인지 확인하세요", "data": {}}

        inv = parsed
        logger.info(f"[invoice-upload] sap_no={inv.sap_no} vessel={inv.vessel} ship_date={inv.ship_date}")

        # 업데이트할 필드 준비 — inventory 테이블 컬럼 기준
        update_dict = {
            "sap_no":           getattr(inv, "sap_no", "") or "",
            "salar_invoice_no": getattr(inv, "invoice_no", "") or "",
            "ship_date":        str(getattr(inv, "ship_date", "") or ""),
            "total_amount":     getattr(inv, "total_amount", None),
            "unit_price":       getattr(inv, "unit_price", None),
            "invoice_date":     str(getattr(inv, "invoice_date", "") or ""),
        }

        con = _open_db()
        result_total = {"updated": 0, "lots": [], "skipped_empty": 0}

        # 매칭 1: sap_no 로 매칭
        if inv.sap_no:
            r = _db_update_lots(con, "sap_no", [inv.sap_no], update_dict)
            result_total["updated"] += r["updated"]
            result_total["lots"].extend(r["lots"])

        # 매칭 2: folio (invoice_no) 로 매칭 — folio 컬럼이 있는 경우
        if getattr(inv, "invoice_no", ""):
            try:
                r = _db_update_lots(con, "folio", [inv.invoice_no], update_dict)
                result_total["updated"] += r["updated"]
                result_total["lots"].extend(r["lots"])
            except Exception:
                pass

        # 중복 제거
        result_total["lots"] = list(set(result_total["lots"]))
        con.close()

        matched = len(result_total["lots"])
        return {
            "ok": True,
            "message": f"Invoice 업로드 완료 — {matched}개 LOT 업데이트 (sap_no={inv.sap_no})",
            "data": {
                "filename": file.filename,
                "sap_no": inv.sap_no,
                "invoice_no": getattr(inv, "invoice_no", ""),
                "updated_count": matched,
                "updated_lots": result_total["lots"][:50],
                "updated_fields": [k for k, v in update_dict.items() if v not in (None, "")],
                "ai_provider_used": getattr(inv, "_ai_provider", "gemini"),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"inbound_invoice error: {e}")
        raise HTTPException(500, str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except Exception: pass


# ─────────────────────────────────────────────────────────
# POST /api/inbound/bl
# ─────────────────────────────────────────────────────────
@router.post("/bl", summary="B/L PDF 업로드 → 기존 LOT 업데이트")
async def inbound_bl(file: UploadFile = File(...)):
    """BL PDF 파싱 → container_no로 LOT 매칭 → bl_no/vessel/voyage/ship_date 업데이트"""
    tmp_path = None
    try:
        pdf_bytes = await file.read()
        if len(pdf_bytes) < 4 or pdf_bytes[:4] != b"%PDF":
            raise HTTPException(400, "Not a valid PDF file")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        from parsers.pdf_parser import PDFParser
        parser = PDFParser()
        parsed = parser.parse(tmp_path)

        if parsed is None or type(parsed).__name__ != "BLData":
            return {"ok": False, "message": "B/L 파싱 실패 — B/L 서류인지 확인하세요", "data": {}}

        bl = parsed
        logger.info(f"[bl-upload] bl_no={bl.bl_no} vessel={bl.vessel} containers={len(bl.containers)}")

        update_dict = {
            "bl_no":     getattr(bl, "bl_no", "") or "",
            "vessel":    getattr(bl, "vessel", "") or "",
            "voyage":    getattr(bl, "voyage", "") or "",
            "ship_date": str(getattr(bl, "ship_date", "") or ""),
        }

        # 컨테이너 번호 목록 추출
        containers = getattr(bl, "containers", []) or []
        container_nos = []
        for c in containers:
            if isinstance(c, dict):
                cn = c.get("container_no") or c.get("container") or ""
            else:
                cn = str(c)
            cn = re.sub(r"[^A-Z0-9]", "", cn.upper())  # ISO6346-norm
            if cn:
                container_nos.append(cn)

        if not container_nos:
            return {"ok": False, "message": "BL에서 컨테이너 번호를 추출하지 못했습니다", "data": {}}

        con = _open_db()
        result = _db_update_lots(con, "container_no", container_nos, update_dict)
        con.close()

        lots = result.get("lots", []) or []
        matched = len(lots)
        return {
            "ok": True,
            "message": f"B/L 업로드 완료 — {matched}개 LOT 업데이트 (bl_no={bl.bl_no})",
            "data": {
                "filename": file.filename,
                "bl_no": bl.bl_no,
                "vessel": bl.vessel,
                "voyage": getattr(bl, "voyage", "") or "",
                "containers_parsed": container_nos,
                "updated_count": matched,
                "updated_lots": lots[:50],
                "updated_fields": [k for k, v in update_dict.items() if v not in (None, "")],
                "ai_provider_used": getattr(bl, "_ai_provider", "gemini"),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"inbound_bl error: {e}")
        raise HTTPException(500, str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except Exception: pass


# ─────────────────────────────────────────────────────────
# POST /api/inbound/do
# ─────────────────────────────────────────────────────────
@router.post("/do", summary="D/O PDF 업로드 → 기존 LOT 업데이트")
async def inbound_do(file: UploadFile = File(...)):
    """DO PDF 파싱 → bl_no + container_no로 LOT 매칭 → arrival_date/free_time 업데이트"""
    tmp_path = None
    try:
        pdf_bytes = await file.read()
        if len(pdf_bytes) < 4 or pdf_bytes[:4] != b"%PDF":
            raise HTTPException(400, "Not a valid PDF file")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        from parsers.pdf_parser import PDFParser
        parser = PDFParser()
        parsed = parser.parse(tmp_path)

        if parsed is None or type(parsed).__name__ != "DOData":
            return {"ok": False, "message": "D/O 파싱 실패 — D/O 서류인지 확인하세요", "data": {}}

        do = parsed
        logger.info(f"[do-upload] do_no={do.do_no} bl_no={do.bl_no} arrival={do.arrival_date}")

        _arrival_date = str(getattr(do, "arrival_date", "") or "")
        try:
            from utils.date_utils import normalize_date_str as _norm_date_str
            _arrival_date = _norm_date_str(_arrival_date) or _arrival_date
        except Exception:
            pass

        update_dict = {
            "arrival_date": _arrival_date,
            "do_no":        getattr(do, "do_no", "") or "",
            "bl_no":        getattr(do, "bl_no", "") or "",
        }

        # free_time: free_time_info contains the DO container return date.
        free_time_info = getattr(do, "free_time_info", []) or []
        _con_return = ""
        for _ft in free_time_info:
            if isinstance(_ft, dict):
                _ftd = _ft.get("free_time_date") or _ft.get("free_time_until") or _ft.get("con_return") or ""
                _days = _ft.get("storage_free_days") or _ft.get("free_time") or _ft.get("days") or ""
            else:
                _ftd = getattr(_ft, "free_time_date", "") or getattr(_ft, "free_time_until", "") or ""
                _days = getattr(_ft, "storage_free_days", 0) or ""
            if _ftd and str(_ftd) not in ("", "None"):
                try:
                    from utils.date_utils import normalize_date_str as _norm_date_str
                    _con_return = _norm_date_str(_ftd) or str(_ftd)[:10]
                except Exception:
                    _con_return = str(_ftd)[:10]
                if _days:
                    update_dict["free_time"] = str(_days)
                break
        if _con_return:
            update_dict["con_return"] = _con_return
            if not update_dict.get("free_time"):
                try:
                    from utils.date_utils import calculate_free_days as _calc_free_days
                    _days = _calc_free_days(_arrival_date, _con_return)
                    if _days is not None:
                        update_dict["free_time"] = str(_days)
                except Exception:
                    pass

        con = _open_db()
        result_total = {"updated": 0, "lots": []}

        # 매칭 1: bl_no 로 매칭
        if do.bl_no:
            r = _db_update_lots(con, "bl_no", [do.bl_no], update_dict)
            result_total["updated"] += r["updated"]
            result_total["lots"].extend(r["lots"])

        # 매칭 2: container_no 로 매칭
        containers = getattr(do, "containers", []) or []
        container_nos = []
        for c in containers:
            cn = c.get("container_no") or c.get("container") or "" if isinstance(c, dict) else str(c)
            if cn:
                container_nos.append(cn)

        if container_nos:
            r = _db_update_lots(con, "container_no", container_nos, update_dict)
            result_total["updated"] += r["updated"]
            result_total["lots"].extend(r["lots"])

        result_total["lots"] = list(set(result_total["lots"]))
        con.close()

        matched = len(result_total["lots"])
        return {
            "ok": True,
            "message": f"D/O 업로드 완료 — {matched}개 LOT 업데이트 (do_no={do.do_no})",
            "data": {
                "filename": file.filename,
                "do_no": do.do_no,
                "bl_no": do.bl_no,
                "arrival_date": str(do.arrival_date or ""),
                "updated_count": matched,
                "updated_lots": result_total["lots"][:50],
                "updated_fields": [k for k, v in update_dict.items() if v not in (None, "")],
                "ai_provider_used": getattr(do, "_ai_provider", "gemini"),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"inbound_do error: {e}")
        raise HTTPException(500, str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except Exception: pass
