# SQM v866 MASTER-P2: Phase 2 (Backend API)
**읽은 후 MASTER_P3.md 로 진행**
**progress.txt 에 각 TASK 완료 기록 필수**

---
## 절대 원칙 (항상 적용)
- engine_modules/ 얇게 감싸기만 (수정 금지)
- 모든 API 응답: {"success": bool, "data": any, "message": str}
- SOLD 전환은 scan_api.py 에서만
- 에러 시 RETRY 3회 + Ruby 즉시 수정 후 다음 TASK 진행 (중단 금지)
- error_report.md는 기록용으로만 사용 (작성해도 STOP하지 말 것)

---
## 체크포인트 규칙
완료 시: progress.txt 에 "DONE: [TASK명]" 추가

---
# PHASE 2 — 백엔드 API 완성 (Agent B)

**현황:** backend/api/ 에 대부분 구현됨. 누락/미완성 항목 보완.

## P2-TASK-01: API 엔드포인트 전수 검증

**예상: 20분**

```bash
# 현재 등록된 라우터 목록 확인
grep -n "router\.\|app\.\|@app\." backend/api/__init__.py | head -50

# 각 엔드포인트 응답 형식 확인
# → 모든 응답이 {"success": bool, "data": ..., "message": str} 형식인지 확인
grep -rn "return {" backend/api/ --include="*.py" | grep -v "success" | head -20
# → success 없는 응답 발견 시 수정 대상
```

## P2-TASK-02: Scan API 신규 생성

**파일:** `backend/api/scan_api.py` (신규)
**연결:** `engine_modules/inventory_modular/engine.py` → SQMInventoryEngineV3
**예상: 30분**

```python
# backend/api/scan_api.py

from fastapi import APIRouter
from config import DB_PATH
from engine_modules.inventory_modular.engine import SQMInventoryEngineV3

router = APIRouter(prefix="/api/scan", tags=["scan"])

@router.post("/lookup")
async def scan_lookup(uid: str):
    """UID로 톤백 현재 상태 조회"""
    try:
        engine = SQMInventoryEngineV3(str(DB_PATH))
        # engine의 기존 조회 함수 활용
        result = engine.get_tonbag_by_uid(uid)  # 실제 함수명 확인 필요
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/confirm_outbound")
async def scan_confirm_outbound(uid: str):
    """PICKED → OUTBOUND → SOLD (유일한 SOLD 전환 경로)"""
    try:
        engine = SQMInventoryEngineV3(str(DB_PATH))
        result = engine.confirm_outbound_by_scan(uid)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/return")
async def scan_return(uid: str, reason: str = ""):
    """OUTBOUND → RETURN"""
    try:
        engine = SQMInventoryEngineV3(str(DB_PATH))
        result = engine.process_return_by_scan(uid, reason)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.put("/move")
async def scan_move(uid: str, to_location: str):
    """톤백 위치 변경 (status 유지)"""
    try:
        engine = SQMInventoryEngineV3(str(DB_PATH))
        result = engine.move_tonbag(uid, to_location)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}
```

**주의:** engine 실제 함수명은 아래 확인 후 사용:
```bash
grep -n "def confirm_outbound\|def process_return\|def move_tonbag\|def get_tonbag" \
    engine_modules/inventory_modular/engine.py | head -20
```

**검증:**
```bash
python -m py_compile backend/api/scan_api.py
```
**완료 후:** progress.txt 기록

## P2-TASK-03: Integrity API 신규 생성

**파일:** `backend/api/integrity_api.py` (신규)
**예상: 20분**

```python
# backend/api/integrity_api.py
from fastapi import APIRouter
from config import DB_PATH
import sqlite3

router = APIRouter(prefix="/api/integrity", tags=["integrity"])

@router.get("/check")
async def integrity_check():
    """전체 무게 정합성 검사
    공식: initial_weight = current_weight + picked_weight (±1.0kg)
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        # inventory 테이블에서 무게 불일치 LOT 조회
        rows = conn.execute("""
            SELECT lot_no,
                   initial_weight,
                   current_weight,
                   picked_weight,
                   ABS(initial_weight - (current_weight + picked_weight)) as diff
            FROM inventory
            WHERE ABS(initial_weight - (current_weight + picked_weight)) > 1.0
        """).fetchall()
        conn.close()

        total = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        error_list = [dict(r) for r in rows]

        return {
            "success": True,
            "data": {
                "total": total,
                "ok": total - len(error_list),
                "error": len(error_list),
                "details": error_list
            }
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
```

**검증:**
```bash
python -m py_compile backend/api/integrity_api.py
```
**완료 후:** progress.txt 기록

## P2-TASK-04: 신규 라우터 backend/__init__.py 등록

```python
# backend/api/__init__.py 하단에 추가
from backend.api.scan_api import router as scan_router
from backend.api.integrity_api import router as integrity_router

app.include_router(scan_router)
app.include_router(integrity_router)
```

**검증:**
```bash
python -c "from backend.api import app; print('라우터 수:', len(app.routes))"
```
**완료 후:** progress.txt 기록

---


---
## P2 완료 후 다음 단계
progress.txt 에 "DONE: PHASE2" 기록
python scripts/telegram_notify.py sync2 4
→ MASTER_P3.md 로 진행
