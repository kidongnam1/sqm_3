# -*- coding: utf-8 -*-
"""
[Sprint 2-B] Settings + Carrier Rules
- API key management (read source / save to keyring)
- Carrier BL/DO rules CRUD
v864-2 source: dialogs/settings_dialog.py (869 lines, SettingsDialogMixin)
"""
import os
import sqlite3
import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Body, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


def _db():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    db_path = os.path.join(root, "data", "db", "sqm_inventory.db")
    con = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS carrier_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            carrier_id  TEXT NOT NULL,
            doc_type    TEXT NOT NULL CHECK(doc_type IN ('BL','DO')),
            rule_name   TEXT NOT NULL,
            pattern     TEXT,
            description TEXT,
            sample_value TEXT,
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT,
            updated_at  TEXT,
            UNIQUE(carrier_id, doc_type, rule_name)
        )
    """)
    con.commit()
    return con


# ==============================================================
# API Key Management
# ==============================================================
@router.get("/api-keys", summary="API 키 상태 조회 [Sprint 2-B]")
def get_api_keys_status():
    """
    환경변수 / keyring / settings.ini 에서 API 키 출처 확인.
    실제 키 값은 마스킹 처리.
    """
    try:
        # config.py의 _load_settings 활용
        try:
            from config import _load_settings
            settings = _load_settings()
        except Exception:
            settings = {}

        def mask(v):
            if not v:
                return ""
            v = str(v)
            if len(v) <= 8:
                return "***"
            return v[:4] + "***" + v[-4:]

        gemini_key = settings.get("api_key", "")
        gemini_source = settings.get("api_key_source", None)
        openai_key = settings.get("openai_api_key", "")

        # 환경변수 직접 확인 (현재 프로세스 기준)
        env_keys = {
            "GEMINI_API_KEY": bool(os.environ.get("GEMINI_API_KEY")),
            "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY")),
            "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY")),
        }

        # keyring 확인
        keyring_available = False
        keyring_keys = {}
        try:
            import keyring
            keyring_available = True
            for k in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
                v = keyring.get_password("SQM_Inventory", k)
                keyring_keys[k] = bool(v)
        except Exception:
            pass

        return {
            "ok": True,
            "data": {
                "gemini": {
                    "configured": bool(gemini_key),
                    "source":     gemini_source,
                    "masked":     mask(gemini_key),
                    "model":      settings.get("model", "gemini-2.5-flash"),
                },
                "openai": {
                    "configured": bool(openai_key),
                    "masked":     mask(openai_key),
                    "model":      settings.get("openai_model", "gpt-4o"),
                },
                "env_present":     env_keys,
                "keyring_present": keyring_keys,
                "keyring_available": keyring_available,
                "settings_ini_path": "settings.ini",
                "use_gemini":        settings.get("use_gemini", True),
                "save_raw_response": settings.get("save_raw_gemini_response", False),
            },
        }
    except Exception as e:
        logger.error(f"get_api_keys_status error: {e}")
        raise HTTPException(500, str(e))


@router.post("/api-keys", summary="API 키 저장 (keyring) [Sprint 2-B]")
def save_api_key(payload: Dict[str, Any] = Body(...)):
    """
    Body: { service: 'gemini'|'openai'|'anthropic', api_key: '...' }
    keyring 에 저장 (환경변수보다 안전).
    """
    service = (payload or {}).get("service", "").lower()
    key = (payload or {}).get("api_key", "")
    if service not in ("gemini", "openai", "anthropic"):
        raise HTTPException(400, "service: gemini|openai|anthropic")
    if not key or not str(key).strip():
        raise HTTPException(400, "api_key 빈값")
    try:
        import keyring
        kr_key = {
            "gemini":    "GEMINI_API_KEY",
            "openai":    "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }[service]
        keyring.set_password("SQM_Inventory", kr_key, str(key).strip())
        return {"ok": True, "message": f"{service} API key 저장됨 (keyring)"}
    except ImportError:
        raise HTTPException(500, "keyring 미설치")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/api-keys/{service}", summary="API 키 삭제 (keyring) [Sprint 2-B]")
def delete_api_key(service: str):
    if service.lower() not in ("gemini", "openai", "anthropic"):
        raise HTTPException(400, "service: gemini|openai|anthropic")
    try:
        import keyring
        kr_key = {
            "gemini":    "GEMINI_API_KEY",
            "openai":    "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }[service.lower()]
        try:
            keyring.delete_password("SQM_Inventory", kr_key)
        except Exception:
            pass
        return {"ok": True, "message": f"{service} API key 삭제됨"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ==============================================================
# Carrier Rules (BL/DO patterns)
# ==============================================================
@router.get("/carrier-rules", summary="🚢 선사 BL/DO 규칙 목록 [Sprint 2-B]")
def list_carrier_rules(carrier_id: Optional[str] = None, doc_type: Optional[str] = None):
    try:
        con = _db()
        sql = "SELECT * FROM carrier_rules WHERE 1=1"
        params = []
        if carrier_id:
            sql += " AND carrier_id = ?"
            params.append(carrier_id)
        if doc_type:
            sql += " AND doc_type = ?"
            params.append(doc_type)
        sql += " ORDER BY carrier_id, doc_type, rule_name"
        rows = con.execute(sql, params).fetchall()
        # 사용 가능한 선사 목록 (distinct)
        carriers = con.execute("SELECT DISTINCT carrier_id FROM carrier_rules ORDER BY carrier_id").fetchall()
        con.close()
        return {
            "ok": True,
            "data": {
                "items": [dict(r) for r in rows],
                "total": len(rows),
                "available_carriers": [r[0] for r in carriers],
            },
        }
    except Exception as e:
        logger.error(f"list_carrier_rules error: {e}")
        raise HTTPException(500, str(e))


@router.post("/carrier-rules", summary="🚢 선사 규칙 생성 [Sprint 2-B]")
def create_carrier_rule(payload: Dict[str, Any] = Body(...)):
    carrier = (payload or {}).get("carrier_id", "").strip()
    doc_type = (payload or {}).get("doc_type", "").strip().upper()
    rule_name = (payload or {}).get("rule_name", "").strip()
    if not carrier or not doc_type or not rule_name:
        raise HTTPException(400, "carrier_id + doc_type + rule_name 필수")
    if doc_type not in ("BL", "DO", "PL", "INVOICE"):
        raise HTTPException(400, "doc_type: BL|DO|PL|INVOICE")
    fields = {
        "carrier_id":   carrier,
        "doc_type":     doc_type,
        "rule_name":    rule_name,
        "pattern":      payload.get("pattern", ""),
        "description":  payload.get("description", ""),
        "sample_value": payload.get("sample_value", ""),
        "is_active":    1 if payload.get("is_active", True) else 0,
    }
    try:
        con = _db()
        cur = con.execute(
            "INSERT INTO carrier_rules (carrier_id, doc_type, rule_name, pattern, description, sample_value, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            list(fields.values()),
        )
        new_id = cur.lastrowid
        con.commit(); con.close()
        return {"ok": True, "data": {**fields, "id": new_id}, "message": "규칙 생성됨"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/carrier-rules/{rule_id}", summary="🚢 선사 규칙 수정 [Sprint 2-B]")
def update_carrier_rule(rule_id: int, updates: Dict[str, Any] = Body(...)):
    allowed = {"carrier_id", "doc_type", "rule_name", "pattern", "description", "sample_value", "is_active"}
    fields = {k: v for k, v in (updates or {}).items() if k in allowed}
    if not fields:
        raise HTTPException(400, "수정 가능 필드 없음")
    if "is_active" in fields:
        fields["is_active"] = 1 if fields["is_active"] else 0
    if "doc_type" in fields:
        fields["doc_type"] = str(fields["doc_type"]).upper()
        if fields["doc_type"] not in ("BL", "DO", "PL", "INVOICE"):
            raise HTTPException(400, "doc_type 잘못됨")
    sets = ", ".join(f"{k}=?" for k in fields.keys())
    values = list(fields.values()) + [rule_id]
    try:
        con = _db()
        cur = con.execute(
            f"UPDATE carrier_rules SET {sets}, updated_at=datetime('now') WHERE id=?",
            values,
        )
        if cur.rowcount == 0:
            con.close()
            raise HTTPException(404, f"rule {rule_id} 없음")
        con.commit(); con.close()
        return {"ok": True, "data": {"id": rule_id, "updated": list(fields.keys())}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/carrier-rules/{rule_id}", summary="🚢 선사 규칙 삭제 [Sprint 2-B]")
def delete_carrier_rule(rule_id: int):
    try:
        con = _db()
        cur = con.execute("DELETE FROM carrier_rules WHERE id=?", (rule_id,))
        if cur.rowcount == 0:
            con.close()
            raise HTTPException(404, f"rule {rule_id} 없음")
        con.commit(); con.close()
        return {"ok": True, "message": f"rule {rule_id} 삭제됨"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ==============================================================
# Carrier Rule Auto-Detection via PDF (좌표 + 정규식, Gemini 불필요)
# ==============================================================

# 선사별 BL번호 알려진 접두사 패턴 (bl_mixin.py BL_FORMAT_MAP 기준)
_BL_FORMAT_MAP = {
    'MAERSK':    [r'MAEU\d{9}'],
    'MSC':       [r'MSCU[A-Z0-9]{6,10}', r'MEDU[A-Z0-9]{6,10}'],
    'ONE':       [r'ONEU[A-Z0-9]{6,10}'],
    'HAPAG':     [r'HLCU[A-Z0-9]{6,10}'],
    'HMM':       [r'HMMU[A-Z0-9]{6,10}'],
    'CMA':       [r'CMA[A-Z0-9]{6,10}'],
    'EVERGREEN': [r'EVER[A-Z0-9]{6,10}'],
    'COSCO':     [r'COSU[A-Z0-9]{6,10}'],
}

# 필드 라벨 키워드 → 텍스트 기반 탐색
_FIELD_LABELS = {
    'vessel':             [r'vessel[\s:]+([A-Z][A-Z0-9 ]{2,30})', r'ship[\s:]+([A-Z][A-Z0-9 ]{2,30})'],
    'voyage_no':          [r'voyage[\s:no.]*([A-Z0-9]{3,12})', r'voy[\s:no.]*([A-Z0-9]{3,12})'],
    'port_of_loading':    [r'port of loading[\s:]+([A-Z][A-Z, ]+)', r'pol[\s:]+([A-Z][A-Z, ]+)'],
    'port_of_discharge':  [r'port of discharge[\s:]+([A-Z][A-Z, ]+)', r'pod[\s:]+([A-Z][A-Z, ]+)'],
    'issue_date':         [r'(\d{4}-\d{2}-\d{2})', r'(\d{1,2}[./]\d{1,2}[./]\d{4})'],
}


@router.post("/carrier-rules/auto-detect", summary="📄 PDF 자동 분석 → 선사 규칙 추출 (Gemini 불필요)")
async def auto_detect_carrier_rules(request: Request):
    """
    샘플 PDF 업로드 → PyMuPDF 텍스트 추출 → 정규식으로 BL/DO 필드 자동 인식.
    Gemini API 없이 동작. 인식된 패턴을 carrier_rules 테이블에 저장.
    """
    import re
    from datetime import datetime as _dt

    form = await request.form()
    carrier_id = (form.get("carrier_id") or "").strip().upper()
    doc_type   = (form.get("doc_type")   or "BL").strip().upper()
    pdf_file   = form.get("file")

    if not carrier_id:
        raise HTTPException(400, "carrier_id 필수")
    if not pdf_file or not hasattr(pdf_file, "read"):
        raise HTTPException(400, "PDF 파일 필수")
    if doc_type not in ("BL", "DO"):
        raise HTTPException(400, "doc_type: BL|DO")

    # PDF → 텍스트 + 단어 좌표
    pdf_bytes = await pdf_file.read()
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        W, H = page.rect.width, page.rect.height
        full_text = page.get_text("text") or ""
        words_raw = page.get_text("words")
        doc.close()
    except Exception as e:
        raise HTTPException(500, f"PDF 읽기 실패: {e}")

    text_upper = full_text.upper()

    # ── BL/DO 번호 추출 ──────────────────────────────────────────
    bl_no = ""
    pattern = ""
    patterns_for_carrier = _BL_FORMAT_MAP.get(carrier_id, [])

    # 1) 알려진 선사 패턴으로 먼저 시도
    for pat in patterns_for_carrier:
        m = re.search(pat, full_text, re.IGNORECASE)
        if m:
            bl_no = m.group(0).upper()
            pattern = pat
            break

    # 2) 알 수 없는 선사: 알파벳 접두사 + 숫자 조합 후보 탐색
    if not bl_no:
        candidates = re.findall(r'\b([A-Z]{3,5}\d{6,10})\b', full_text)
        if candidates:
            bl_no = candidates[0]
            pre = re.match(r'^([A-Z]+)', bl_no)
            num = re.search(r'(\d+)$', bl_no)
            if pre and num:
                pattern = f"{pre.group(1)}\\d{{{len(num.group(1))}}}"

    # ── 기타 필드 텍스트 추출 ───────────────────────────────────
    extracted = {"bl_no": bl_no, "bl_no_pattern": pattern,
                 "carrier_detected": carrier_id, "doc_type": doc_type}
    for field, pats in _FIELD_LABELS.items():
        for pat in pats:
            m = re.search(pat, full_text, re.IGNORECASE)
            if m:
                extracted[field] = m.group(1).strip()
                break
        else:
            extracted.setdefault(field, "")

    # ── carrier_rules 저장 ───────────────────────────────────────
    now = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
    saved = []
    con = _db()
    try:
        if pattern:
            cur = con.execute(
                "INSERT OR IGNORE INTO carrier_rules "
                "(carrier_id, doc_type, rule_name, pattern, description, sample_value, is_active, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,1,?,?)",
                (carrier_id, doc_type, f"{doc_type}_NO_AUTO",
                 pattern,
                 f"{carrier_id} {doc_type} 번호 패턴 (PDF 자동 감지)",
                 bl_no, now, now)
            )
            if cur.rowcount:
                saved.append(f"{doc_type}_NO_AUTO")
        con.commit()
    finally:
        con.close()

    return {
        "ok": True,
        "data": {
            "extracted": extracted,
            "pattern": pattern,
            "saved_rules": saved,
            "text_preview": full_text[:400],
        }
    }


# ==============================================================
# Email / SMTP config  (Stage 2)
# ==============================================================
import json
import configparser
import pathlib

def _settings_ini_path():
    here = pathlib.Path(__file__).resolve().parent.parent.parent
    return here / "settings.ini"

def _email_json_path():
    here = pathlib.Path(__file__).resolve().parent.parent.parent
    return here / "data" / "email_config.json"

@router.get("/email", summary="📧 이메일 SMTP 설정 조회 (Stage 2)")
def get_email_config():
    p = _email_json_path()
    if p.exists():
        try:
            cfg = json.loads(p.read_text("utf-8"))
            # 비밀번호 마스킹
            masked = {**cfg, "smtp_pass": "●" * 8 if cfg.get("smtp_pass") else ""}
            return {"ok": True, "data": masked}
        except Exception as e:
            logger.warning(f"email config read error: {e}")
    return {"ok": True, "data": {
        "smtp_host": "smtp.gmail.com", "smtp_port": 587,
        "smtp_user": "", "smtp_pass": "",
        "from_addr": "", "recipients": "",
        "tls": True, "enabled": False,
    }}

@router.post("/email", summary="📧 이메일 SMTP 설정 저장 (Stage 2)")
def save_email_config(data: Dict[str, Any] = Body(...)):
    p = _email_json_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if p.exists():
        try:
            existing = json.loads(p.read_text("utf-8"))
        except Exception:
            pass
    # 비밀번호가 마스킹이면 기존값 유지
    if data.get("smtp_pass", "").startswith("●"):
        data["smtp_pass"] = existing.get("smtp_pass", "")
    merged = {**existing, **data}
    p.write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")
    return {"ok": True, "message": "이메일 설정 저장됨"}

@router.post("/email/test", summary="📧 이메일 SMTP 테스트 전송 (Stage 2)")
def test_email_config(data: Dict[str, Any] = Body(...)):
    import smtplib
    import ssl
    import email.message
    host = data.get("smtp_host", "smtp.gmail.com")
    port = int(data.get("smtp_port", 587))
    user = data.get("smtp_user", "")
    passwd = data.get("smtp_pass", "")
    to_addr = data.get("recipients") or user
    if not user or not passwd:
        raise HTTPException(400, "SMTP 사용자/비밀번호가 없습니다")
    try:
        msg = email.message.EmailMessage()
        msg["Subject"] = "[SQM v864.3] 이메일 설정 테스트"
        msg["From"] = data.get("from_addr") or user
        msg["To"] = to_addr
        msg.set_content("SQM v864.3 이메일 설정 테스트 메시지입니다.")
        if data.get("tls", True):
            ctx = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=10) as s:
                s.ehlo(); s.starttls(context=ctx); s.login(user, passwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, port, timeout=10) as s:
                s.login(user, passwd); s.send_message(msg)
        return {"ok": True, "message": f"테스트 메일 전송 완료 → {to_addr}"}
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(400, "인증 실패: 앱 비밀번호를 확인하세요")
    except Exception as e:
        raise HTTPException(500, f"SMTP 오류: {e}")


# ==============================================================
# Auto Backup config  (Stage 2)
# ==============================================================
def _backup_json_path():
    here = pathlib.Path(__file__).resolve().parent.parent.parent
    return here / "data" / "auto_backup_config.json"

@router.get("/backup", summary="⏰ 자동 백업 설정 조회 (Stage 2)")
def get_backup_config():
    p = _backup_json_path()
    default = {"enabled": False, "interval_min": 60, "retention": 10, "path": "backup/", "last_backup": None}
    if p.exists():
        try:
            cfg = json.loads(p.read_text("utf-8"))
            return {"ok": True, "data": {**default, **cfg}}
        except Exception:
            pass
    return {"ok": True, "data": default}

@router.post("/backup", summary="⏰ 자동 백업 설정 저장 (Stage 2)")
def save_backup_config(data: Dict[str, Any] = Body(...)):
    p = _backup_json_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if p.exists():
        try:
            existing = json.loads(p.read_text("utf-8"))
        except Exception:
            pass
    merged = {**existing, **data}
    p.write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")
    return {"ok": True, "message": "자동 백업 설정 저장됨"}


# ==============================================================
# DB table stats  (Stage 2 — TestDbResetModal)
# ==============================================================
@router.get("/table-stats", summary="🗄️ DB 테이블별 행 수 조회 (Stage 2)")
def get_table_stats():
    SHOW_TABLES = [
        "inventory", "inventory_tonbag", "outbound", "outbound_item",
        "allocation_plan", "picking_table", "sold_table", "return_history",
        "stock_movement", "audit_log", "parsing_log", "outbound_event_log",
    ]
    try:
        con = _db()
        result = {}
        for tbl in SHOW_TABLES:
            try:
                row = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
                result[tbl] = row[0] if row else 0
            except Exception:
                result[tbl] = -1  # 테이블 없음
        con.close()
        return {"ok": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/table-delete", summary="🗑️ 선택 테이블 삭제 (Stage 2 — 개발 전용)")
def delete_selected_tables(data: Dict[str, Any] = Body(...)):
    ALLOWED = {
        "outbound", "outbound_item", "allocation_plan", "picking_table",
        "sold_table", "return_history", "stock_movement", "audit_log",
        "parsing_log", "outbound_event_log",
        # 절대 허용 안 함: inventory, inventory_tonbag (실 데이터)
    }
    tables = [t for t in (data.get("tables") or []) if t in ALLOWED]
    if not tables:
        raise HTTPException(400, "삭제할 테이블이 없거나 허용되지 않는 테이블입니다")
    try:
        con = _db()
        deleted = {}
        for tbl in tables:
            cur = con.execute(f"DELETE FROM {tbl}")
            deleted[tbl] = cur.rowcount
        con.commit(); con.close()
        total = sum(deleted.values())
        return {"ok": True, "message": f"{len(tables)}개 테이블 {total}행 삭제됨", "data": deleted}
    except Exception as e:
        raise HTTPException(500, str(e))
