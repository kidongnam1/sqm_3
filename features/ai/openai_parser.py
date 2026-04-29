"""
SQM - OpenAI 문서 파서 (Gemini 실패 시 폴백)

환경변수 OPENAI_API_KEY 또는 settings.ini [OpenAI] api_key 설정 시
Packing List / Invoice 파싱 실패 시 자동으로 OpenAI(gpt-4o)를 시도합니다.

의존성: pip install openai (선택)
"""

import base64
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


def _pdf_first_page_png(pdf_path: str) -> Optional[bytes]:
    """PDF 첫 페이지를 PNG 바이트로 반환. 실패 시 None."""
    if not HAS_PYMUPDF:
        return None
    try:
        doc = fitz.open(pdf_path)
        try:
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            return pix.tobytes("png")
        finally:
            doc.close()
    except (ValueError, TypeError, KeyError, IndexError) as e:
        logger.debug(f"OpenAI PDF 변환 실패: {e}")
        return None


def _extract_json_from_text(text: str) -> dict:
    """응답 텍스트에서 JSON 객체 추출."""
    if not text or not text.strip():
        return {}
    text = text.strip()
    # ```json ... ``` 블록
    m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError as _e:
            logger.debug(f"[openai_parser] 무시: {_e}")
    # 첫 { ~ 마지막 }
    i = text.find('{')
    j = text.rfind('}')
    if i >= 0 and j > i:
        try:
            return json.loads(text[i:j + 1])
        except json.JSONDecodeError as _e:
            logger.debug(f"[openai_parser] 무시: {_e}")
    return {}


def _parse_euro_weight(value) -> float:
    """유럽식/미국식 숫자 → float (kg)."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(' ', '')
    if not s:
        return 0.0
    # 유럽: 5.131,250 → 5131.25
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    try:
        return float(s)
    except ValueError:
        return 0.0


def try_parse_packing_list(pdf_path: str, api_key: Optional[str] = None, model: Optional[str] = None):
    """
    Packing List PDF를 OpenAI Vision으로 파싱 (폴백용).
    
    Returns:
        PackingListResult (success=True, lots 채워짐) 또는 실패 시 None
    """
    if not HAS_OPENAI:
        logger.info("[OpenAI] 폴백 불가: openai 패키지 미설치 — pip install openai")
        return None
    if not HAS_PYMUPDF:
        logger.info("[OpenAI] 폴백 불가: PyMuPDF 미설치")
        return None
    if not api_key:
        try:
            from core.config import OPENAI_API_KEY
            api_key = OPENAI_API_KEY
        except (ValueError, TypeError, KeyError, IndexError) as _e:
            logger.debug(f"Suppressed: {_e}")
    if not api_key or not api_key.strip():
        logger.info("[OpenAI] 폴백 불가: OPENAI_API_KEY 미설정 (환경변수 또는 settings.ini [OpenAI] api_key)")
        return None
    if not model:
        try:
            from core.config import OPENAI_MODEL
            model = OPENAI_MODEL or "gpt-4o"
        except (ValueError, TypeError, KeyError, IndexError):
            model = "gpt-4o"

    from features.ai.gemini_parser import LOTItem, PackingListResult

    png_bytes = _pdf_first_page_png(pdf_path)
    if not png_bytes:
        return None

    b64 = base64.standard_b64encode(png_bytes).decode("ascii")
    prompt = """이 Packing List 문서를 분석하여 아래 JSON 형식으로 정확히 추출해주세요.
숫자: 유럽식(5.131,250=5131.250)을 소수점 포함 kg로. Net/Gross Weight는 원본 그대로.
JSON만 응답하세요.
```json
{
    "folio": "문서 번호 (7자리)",
    "product": "제품명",
    "packing": "포장 정보",
    "code": "제품 코드 (MIC로 시작)",
    "vessel": "선박명",
    "customer": "고객사",
    "destination": "목적지",
    "lots": [
        {"list_no": 1, "container_no": "", "lot_no": "", "lot_sqm": "", "mxbg": 10, "net_weight_kg": 0, "gross_weight_kg": 0, "del_no": "", "al_no": ""}
    ],
    "total_net_weight_kg": 0,
    "total_gross_weight_kg": 0
}
```"""

    try:
        client = openai.OpenAI(api_key=api_key.strip())
        resp = client.chat.completions.create(
            model=model.strip(),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }
            ],
            max_tokens=4096,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return None
        data = _extract_json_from_text(text)
        if not data or not data.get("lots"):
            return None

        result = PackingListResult()
        result.folio = str(data.get("folio", ""))
        result.product = data.get("product", "")
        result.packing = data.get("packing", "")
        result.code = data.get("code", "")
        result.vessel = data.get("vessel", "")
        result.customer = data.get("customer", "")
        result.destination = data.get("destination", "")
        result.total_net_weight_kg = _parse_euro_weight(data.get("total_net_weight_kg", 0))
        result.total_gross_weight_kg = _parse_euro_weight(data.get("total_gross_weight_kg", 0))
        for lot_data in data.get("lots", []):
            result.lots.append(LOTItem(
                list_no=int(lot_data.get("list_no", 0)),
                container_no=str(lot_data.get("container_no", "")),
                lot_no=str(lot_data.get("lot_no", "")),
                lot_sqm=str(lot_data.get("lot_sqm", "")),
                mxbg=int(lot_data.get("mxbg", 10)),
                net_weight_kg=_parse_euro_weight(lot_data.get("net_weight_kg", 0)),
                gross_weight_kg=_parse_euro_weight(lot_data.get("gross_weight_kg", 0)),
                del_no=str(lot_data.get("del_no", "")),
                al_no=str(lot_data.get("al_no", "")),
            ))
        result.success = len(result.lots) > 0
        if result.success:
            logger.info(f"[OpenAI] Packing List 폴백 성공: {len(result.lots)} LOT")
        return result if result.success else None
    except (ValueError, TypeError, KeyError, IndexError) as e:
        logger.warning(f"[OpenAI] Packing List 폴백 실패: {e}")
        return None


def try_parse_invoice(pdf_path: str, api_key: Optional[str] = None, model: Optional[str] = None):
    """
    Invoice PDF를 OpenAI Vision으로 파싱 (폴백용).
    
    Returns:
        InvoiceResult (success=True) 또는 실패 시 None
    """
    if not HAS_OPENAI or not HAS_PYMUPDF:
        if not HAS_OPENAI:
            logger.info("[OpenAI] Invoice 폴백 불가: openai 패키지 미설치 — pip install openai")
        return None
    if not api_key:
        try:
            from core.config import OPENAI_API_KEY
            api_key = OPENAI_API_KEY
        except (ValueError, TypeError, KeyError, IndexError) as _e:
            logger.debug(f"Suppressed: {_e}")
    if not api_key or not api_key.strip():
        logger.info("[OpenAI] Invoice 폴백 불가: OPENAI_API_KEY 미설정")
        return None
    if not model:
        try:
            from core.config import OPENAI_MODEL
            model = OPENAI_MODEL or "gpt-4o"
        except (ValueError, TypeError, KeyError, IndexError):
            model = "gpt-4o"

    from features.ai.gemini_parser import InvoiceResult

    png_bytes = _pdf_first_page_png(pdf_path)
    if not png_bytes:
        return None

    b64 = base64.standard_b64encode(png_bytes).decode("ascii")
    prompt = """이 Invoice(상업송장/FACTURA) 문서를 분석하여 아래 JSON으로 추출하세요.
SAP NO: "Ref.SQM/Our Order"에서 22로 시작 10자리. LOT 목록: "N° LOTES:" 뒤 LOT번호만(10자리).
JSON만 응답하세요.
```json
{
    "sap_no": "2200033057",
    "invoice_no": "16130",
    "bl_no": "",
    "product": "",
    "product_code": "",
    "quantity_mt": 0,
    "unit_price": 0,
    "total_amount": 0,
    "currency": "USD",
    "incoterm": "",
    "origin": "",
    "destination": "",
    "vessel": "",
    "lot_numbers": []
}
```"""

    try:
        client = openai.OpenAI(api_key=api_key.strip())
        resp = client.chat.completions.create(
            model=model.strip(),
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]},
            ],
            max_tokens=4096,
        )
        text = (resp.choices[0].message.content or "").strip()
        data = _extract_json_from_text(text)
        if not data:
            return None

        result = InvoiceResult()
        result.sap_no = str(data.get("sap_no", ""))
        result.invoice_no = str(data.get("invoice_no", ""))
        result.bl_no = str(data.get("bl_no", ""))
        result.product = data.get("product", "")
        result.product_code = data.get("product_code", "")
        result.quantity_mt = _parse_euro_weight(data.get("quantity_mt", 0))
        result.unit_price = _parse_euro_weight(data.get("unit_price", 0))
        result.total_amount = _parse_euro_weight(data.get("total_amount", 0))
        result.currency = data.get("currency", "USD")
        result.incoterm = data.get("incoterm", "")
        result.origin = data.get("origin", "")
        result.destination = data.get("destination", "")
        result.vessel = data.get("vessel", "")
        result.lot_numbers = list(data.get("lot_numbers", []) or [])
        result.success = bool(result.sap_no or result.invoice_no or result.lot_numbers)
        if result.success:
            logger.info("[OpenAI] Invoice 폴백 성공")
        return result if result.success else None
    except (ValueError, TypeError, KeyError, IndexError) as e:
        logger.warning(f"[OpenAI] Invoice 폴백 실패: {e}")
        return None


def try_parse_bl(pdf_path: str, api_key: Optional[str] = None, model: Optional[str] = None):
    """
    B/L PDF를 OpenAI Vision으로 파싱 (폴백용).
    Returns:
        BLResult (success=True) 또는 실패 시 None
    """
    if not HAS_OPENAI or not HAS_PYMUPDF:
        if not HAS_OPENAI:
            logger.info("[OpenAI] B/L 폴백 불가: openai 패키지 미설치 — pip install openai")
        return None
    if not api_key:
        try:
            from core.config import OPENAI_API_KEY
            api_key = OPENAI_API_KEY
        except (ValueError, TypeError, KeyError, IndexError) as _e:
            logger.debug(f"Suppressed: {_e}")
    if not api_key or not api_key.strip():
        logger.info("[OpenAI] B/L 폴백 불가: OPENAI_API_KEY 미설정")
        return None
    if not model:
        try:
            from core.config import OPENAI_MODEL
            model = OPENAI_MODEL or "gpt-4o"
        except (ValueError, TypeError, KeyError, IndexError):
            model = "gpt-4o"

    from features.ai.gemini_parser import BLResult, ContainerDetail

    png_bytes = _pdf_first_page_png(pdf_path)
    if not png_bytes:
        return None

    b64 = base64.standard_b64encode(png_bytes).decode("ascii")
    prompt = """이 B/L(선하증권) 문서를 분석하여 아래 JSON으로 추출하세요.
B/L No, 컨테이너 번호(XXXX0000000 형식), Seal No, SAP NO(22로 시작 10자리) 추출. JSON만 응답하세요.
```json
{
    "bl_no": "258468669",
    "booking_no": "",
    "sap_no": "2200033057",
    "vessel": "",
    "voyage": "",
    "port_of_loading": "",
    "port_of_discharge": "",
    "shipper": "",
    "consignee": "",
    "containers": [{"container_no": "", "seal_no": "", "weight_kg": 0}],
    "total_containers": 0,
    "total_weight_kg": 0,
    "shipped_date": ""
}
```"""

    try:
        client = openai.OpenAI(api_key=api_key.strip())
        resp = client.chat.completions.create(
            model=model.strip(),
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]},
            ],
            max_tokens=4096,
        )
        text = (resp.choices[0].message.content or "").strip()
        data = _extract_json_from_text(text)
        if not data:
            return None

        result = BLResult()
        result.bl_no = str(data.get("bl_no", ""))
        result.booking_no = str(data.get("booking_no", ""))
        result.sap_no = str(data.get("sap_no", ""))
        result.vessel = data.get("vessel", "")
        result.voyage = data.get("voyage", "")
        result.port_of_loading = data.get("port_of_loading", "")
        result.port_of_discharge = data.get("port_of_discharge", "")
        result.shipper = data.get("shipper", "")
        result.consignee = data.get("consignee", "")
        result.total_containers = int(data.get("total_containers", 0))
        result.total_weight_kg = _parse_euro_weight(data.get("total_weight_kg", 0))
        result.shipped_date = data.get("shipped_date", "") or data.get("eta", "")
        for cont in data.get("containers", []) or []:
            result.containers.append(ContainerDetail(
                container_no=str(cont.get("container_no", "")),
                seal_no=str(cont.get("seal_no", "")),
                weight_kg=_parse_euro_weight(cont.get("weight_kg", 0)),
            ))
        result.container_numbers = [c.container_no for c in result.containers if c.container_no]
        result.success = bool(result.bl_no)
        if result.success:
            logger.info(f"[OpenAI] B/L 폴백 성공: BL={result.bl_no}, 컨테이너 {len(result.containers)}개")
        return result if result.success else None
    except (ValueError, TypeError, KeyError, IndexError) as e:
        logger.warning(f"[OpenAI] B/L 폴백 실패: {e}")
        return None


def try_parse_do(pdf_path: str, api_key: Optional[str] = None, model: Optional[str] = None):
    """
    D/O PDF를 OpenAI Vision으로 파싱 (폴백용).
    Returns:
        DOResult (success=True) 또는 실패 시 None
    """
    if not HAS_OPENAI or not HAS_PYMUPDF:
        if not HAS_OPENAI:
            logger.info("[OpenAI] D/O 폴백 불가: openai 패키지 미설치 — pip install openai")
        return None
    if not api_key:
        try:
            from core.config import OPENAI_API_KEY
            api_key = OPENAI_API_KEY
        except (ValueError, TypeError, KeyError, IndexError) as _e:
            logger.debug(f"Suppressed: {_e}")
    if not api_key or not api_key.strip():
        logger.info("[OpenAI] D/O 폴백 불가: OPENAI_API_KEY 미설정")
        return None
    if not model:
        try:
            from core.config import OPENAI_MODEL
            model = OPENAI_MODEL or "gpt-4o"
        except (ValueError, TypeError, KeyError, IndexError):
            model = "gpt-4o"

    from features.ai.gemini_parser import ContainerDetail, DOResult

    png_bytes = _pdf_first_page_png(pdf_path)
    if not png_bytes:
        return None

    b64 = base64.standard_b64encode(png_bytes).decode("ascii")
    prompt = """이 D/O(화물인도지시서) 문서를 분석하여 아래 JSON으로 추출하세요.
D/O No, B/L No(숫자만 가능), 컨테이너, 선박 입항일(arrival_date), Free Time, 반납지. JSON만 응답하세요.
```json
{
    "do_no": "",
    "bl_no": "",
    "bl_no_full": "",
    "vessel": "",
    "voyage": "",
    "port_of_loading": "",
    "port_of_discharge": "",
    "shipper": "",
    "consignee": "",
    "containers": [{"container_no": "", "seal_no": "", "size_type": "", "free_time": "", "return_place": ""}],
    "total_weight_kg": 0,
    "arrival_date": "",
    "issue_date": ""
}
```"""

    try:
        client = openai.OpenAI(api_key=api_key.strip())
        resp = client.chat.completions.create(
            model=model.strip(),
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]},
            ],
            max_tokens=4096,
        )
        text = (resp.choices[0].message.content or "").strip()
        data = _extract_json_from_text(text)
        if not data:
            return None

        result = DOResult()
        result.do_no = str(data.get("do_no", ""))
        result.bl_no = str(data.get("bl_no", ""))
        result.bl_no_full = str(data.get("bl_no_full", ""))
        result.vessel = data.get("vessel", "")
        result.voyage = data.get("voyage", "")
        result.port_of_loading = data.get("port_of_loading", "")
        result.port_of_discharge = data.get("port_of_discharge", "")
        result.shipper = data.get("shipper", "")
        result.consignee = data.get("consignee", "")
        result.total_weight_kg = _parse_euro_weight(data.get("total_weight_kg", 0))
        result.arrival_date = data.get("arrival_date", "") or data.get("eta", "")
        result.issue_date = data.get("issue_date", "")
        result.release_date = data.get("release_date", "") or result.issue_date
        for cont in data.get("containers", []) or []:
            result.containers.append(ContainerDetail(
                container_no=str(cont.get("container_no", "")),
                seal_no=str(cont.get("seal_no", "")),
                size_type=str(cont.get("size_type", "")),
                free_time=str(cont.get("free_time", "")),
                return_place=str(cont.get("return_place", "")),
            ))
        result.container_numbers = [c.container_no for c in result.containers if c.container_no]
        result.success = bool(result.bl_no or result.do_no)
        if result.success:
            logger.info(f"[OpenAI] D/O 폴백 성공: BL={result.bl_no}")
        return result if result.success else None
    except (ValueError, TypeError, KeyError, IndexError) as e:
        logger.warning(f"[OpenAI] D/O 폴백 실패: {e}")
        return None
