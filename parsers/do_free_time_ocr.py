"""
D/O Free Time OCR 폴백 — "절대 안 죽는" 설계 (루비 추천)

Gemini가 con_return/프리타임을 못 채웠을 때:
1. 컨테이너 마스터 리스트 추출 (Container No. 표 → normalize_container 정답키)
2. FreeTime 표 ROI 크롭 → 줄마다 날짜 강제 추출
3. 정확매칭 → 퍼지매칭(difflib) → 모드날짜+인덱스 매칭
4. 예외로 죽지 않고 errors[] 반환

필요: pytesseract, opencv-python, numpy, PyMuPDF(fitz), Pillow
(미설치 시 ok=False, errors에 메시지)
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

_RE_DATE = re.compile(r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})")

logger = logging.getLogger(__name__)


def _safe_run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _has_ocr_deps() -> Tuple[bool, str]:
    try:
        return True, ""
    except ImportError as e:
        return False, f"OCR 의존성 미설치: {e}"


def normalize_container(s: str) -> str:
    """컨테이너 번호 정규화: 공백/하이픈 제거, 대문자, OCR 혼동 보정"""
    if not s:
        return ""
    s = str(s).upper()
    s = re.sub(r"\s+", "", s)
    s = s.replace("-", "")
    s = s.replace("O", "0")
    m = re.search(r"([A-Z]{4}\d{7})", s)
    return m.group(1) if m else s


def best_fuzzy_match(target: str, candidates: List[str], min_ratio: float = 0.78) -> Optional[Tuple[str, float]]:
    """퍼지매칭(오염된 컨테이너번호를 정답키에 붙임)"""
    try:
        import difflib
    except ImportError:
        return None
    best = None
    best_r = 0.0
    for c in candidates:
        r = difflib.SequenceMatcher(None, target, c).ratio()
        if r > best_r:
            best_r = r
            best = c
    if best and best_r >= min_ratio:
        return best, best_r
    return None


def normalize_date_str(s: str) -> Optional[str]:
    """날짜 문자열을 YYYY-MM-DD로 정규화"""
    s = str(s).strip()
    m = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    m = re.match(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s)
    if m:
        d, mo, y = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return None


def _render_pdf_page_to_image(pdf_path: str, page_index: int = 0, zoom: float = 3.0):
    from core.pdf_engine import open_pdf
    from PIL import Image
    doc = open_pdf(pdf_path)
    page = doc.load_page(page_index)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def _preprocess_for_ocr(pil_img, scale: float = 2.0):
    import cv2
    import numpy as np
    img = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    if scale != 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    thr = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 11
    )
    return thr


def _ocr_data(bin_img, psm: int = 6):
    import pytesseract
    cfg = f"--psm {psm}"
    return pytesseract.image_to_data(bin_img, lang="eng", output_type=pytesseract.Output.DICT, config=cfg)


def _ocr_text(bin_img, psm: int = 6):
    import pytesseract
    cfg = f"--psm {psm}"
    return pytesseract.image_to_string(bin_img, lang="eng", config=cfg)


def _find_anchor_bbox(d: Dict[str, Any], keywords: List[str]) -> Optional[Tuple[int, int, int, int]]:
    texts = d.get("text", [])
    lefts = d.get("left", [])
    tops = d.get("top", [])
    widths = d.get("width", [])
    heights = d.get("height", [])
    confs = d.get("conf", [])
    kw = [re.sub(r"[^A-Za-z_]", "", k).upper() for k in keywords]
    for i, w in enumerate(texts):
        if not w:
            continue
        ww = re.sub(r"[^A-Za-z_]", "", str(w)).upper()
        if not ww or (ww not in kw and not any(k in ww for k in kw)):
            continue
        try:
            c = float(confs[i])
        except (TypeError, ValueError):
            c = 0.0
        if c < 30:
            continue
        x0, y0 = lefts[i], tops[i]
        x1, y1 = x0 + widths[i], y0 + heights[i]
        return (x0, y0, x1, y1)
    return None


def _extract_containers_from_do(bin_page) -> List[str]:
    d = _ocr_data(bin_page, psm=6)
    anchor = _find_anchor_bbox(d, keywords=["Container"])
    h, w = bin_page.shape[:2]
    if anchor is None:
        roi = bin_page[int(h*0.30):int(h*0.70), int(w*0.02):int(w*0.55)]
    else:
        x0, y0, x1, y1 = anchor
        roi = bin_page[max(0, y0-40):min(h, y0+520), max(0, x0-40):min(w, x0+720)]
    text = _ocr_text(roi, psm=6)
    glued = re.sub(r"\s+", "", text.upper()).replace("-", "").replace("O", "0")
    found = re.findall(r"[A-Z]{4}\d{7}", glued)
    uniq = []
    for c in found:
        if c not in uniq:
            uniq.append(c)
    return uniq


def _extract_free_time_rows(bin_page) -> Tuple[List[Tuple[Optional[str], str]], Dict[str, Any]]:
    d = _ocr_data(bin_page, psm=6)
    anchor = _find_anchor_bbox(d, keywords=["FreeTime", "Free_Time", "FREE", "Free"])
    debug = {"anchor_found": bool(anchor)}
    h, w = bin_page.shape[:2]
    if anchor is None:
        roi = bin_page[int(h*0.58):int(h*0.92), int(w*0.55):int(w*0.98)]
        debug["roi_mode"] = "ratio"
    else:
        x0, y0, x1, y1 = anchor
        roi = bin_page[max(0, y0-40):min(h, y0+520), max(0, x0-260):min(w, x0+520)]
        debug["roi_mode"] = "anchor"
    text = _ocr_text(roi, psm=6)
    debug["roi_ocr_text"] = text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    rows: List[Tuple[Optional[str], str]] = []
    for ln in lines:
        mdate = _RE_DATE.search(ln)
        if not mdate:
            continue
        date_raw = mdate.group(1)
        mc = re.search(r"([A-Z]{3,5}\s*[0-9][0-9A-Z\s-]{5,})", ln.upper())
        c_raw = mc.group(1) if mc else None
        rows.append((c_raw, date_raw))
    return rows, debug


def _map_free_time_to_containers(
    containers: List[str],
    free_rows: List[Tuple[Optional[str], str]]
) -> Tuple[Dict[str, str], List[str]]:
    errors = []
    result: Dict[str, str] = {}
    parsed_rows = []
    for c_raw, date_raw in free_rows:
        d = normalize_date_str(date_raw)
        if not d:
            continue
        c_norm = normalize_container(c_raw) if c_raw else None
        parsed_rows.append((c_norm, d))
    if not containers:
        errors.append("컨테이너 마스터 리스트를 추출하지 못했습니다.")
        return result, errors
    if not parsed_rows:
        errors.append("FreeTime 영역에서 날짜를 1개도 추출하지 못했습니다.")
        return result, errors
    used = set()
    for c_guess, d in parsed_rows:
        if not c_guess:
            continue
        if c_guess in containers and c_guess not in used:
            result[c_guess] = d
            used.add(c_guess)
            continue
        fm = best_fuzzy_match(c_guess, [c for c in containers if c not in used], min_ratio=0.78)
        if fm:
            best_c, _ = fm
            result[best_c] = d
            used.add(best_c)
    if len(result) < len(containers):
        dates = [d for (_, d) in parsed_rows]
        uniq_dates = list(dict.fromkeys(dates))
        if len(uniq_dates) == 1 and len(parsed_rows) >= len(containers) - 1:
            mode_date = uniq_dates[0]
            for c in containers:
                if c not in result:
                    result[c] = mode_date
            errors.append("일부 행 매칭 실패 → 모드 날짜로 보정(추정) 적용")
        else:
            errors.append("FreeTime 날짜가 여러 개라 모드 보정 불가(일부 누락 가능)")
    missing = [c for c in containers if c not in result]
    if missing:
        errors.append(f"FreeTime 매핑 누락 컨테이너: {missing}")
    return result, errors


def parse_do_free_time(pdf_or_image_path: str, debug_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    절대 예외로 죽지 않는 D/O Free Time(반납일) OCR 추출.
    반환: { "ok": bool, "containers": [], "free_time_map": { "컨테이너번호": "YYYY-MM-DD" }, "errors": [], "debug": {} }
    """
    out = {
        "ok": False,
        "containers": [],
        "free_time_map": {},
        "errors": [],
        "debug": {},
    }
    ok_deps, err_deps = _has_ocr_deps()
    if not ok_deps:
        out["errors"].append(err_deps or "pytesseract/opencv/numpy/PyMuPDF/Pillow 중 일부 미설치")
        return out
    if debug_dir:
        try:
            os.makedirs(debug_dir, exist_ok=True)
        except OSError as e:
            logger.debug(f"Suppressed: {e}")
    pil_img = None
    if pdf_or_image_path.lower().endswith(".pdf"):
        pil_img, err = _safe_run(_render_pdf_page_to_image, pdf_or_image_path, 0, 3.0)
        if err:
            out["errors"].append(f"PDF 렌더 실패: {err}")
            return out
    else:
        try:
            from PIL import Image
            pil_img, err = _safe_run(Image.open, pdf_or_image_path)
        except Exception as e:
            out["errors"].append(f"이미지 로드 실패: {e}")
            return out
        if err:
            out["errors"].append(f"이미지 로드 실패: {err}")
            return out
    bin_page, err = _safe_run(_preprocess_for_ocr, pil_img, 2.0)
    if err:
        out["errors"].append(f"OCR 전처리 실패: {err}")
        return out
    if debug_dir and bin_page is not None:
        try:
            import cv2
            cv2.imwrite(os.path.join(debug_dir, "page_bin.png"), bin_page)
        except Exception as e:
            logger.debug(f"Suppressed: {e}")
    containers, err = _safe_run(_extract_containers_from_do, bin_page)
    if err:
        out["errors"].append(f"컨테이너 추출 실패: {err}")
        containers = containers or []
    out["containers"] = containers or []
    free_rows, err = _safe_run(_extract_free_time_rows, bin_page)
    if err:
        out["errors"].append(f"FreeTime 행 추출 실패: {err}")
        rows, dbg = [], {"anchor_found": False}
    else:
        rows, dbg = free_rows or ([], {})
    out["debug"]["free_rows_debug"] = dbg
    out["debug"]["free_rows_raw"] = rows if isinstance(rows, list) else []
    free_map, errs = _map_free_time_to_containers(out["containers"], rows if isinstance(rows, list) else [])
    out["free_time_map"] = free_map
    out["errors"].extend(errs or [])
    if free_map:
        out["ok"] = True
    return out
