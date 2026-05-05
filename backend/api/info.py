"""
SQM v8.6.6 — Info / Help 정적 응답 엔드포인트
Phase 4-A Group 2: F057, F058, F059, F060, F062

UI 다이얼로그 없이 JSON 으로 안내 데이터를 반환.
프론트(sqm-inline.js)에서 모달/Toast/패널로 렌더링.
"""
import os
import sys
import logging
from fastapi import APIRouter
from backend.common.errors import ok_response

router = APIRouter(prefix="/api/info", tags=["info"])
logger = logging.getLogger(__name__)


# ── F057: 사용법 ────────────────────────────────────────────────
@router.get("/usage", summary="📖 사용법")
def get_usage():
    """Feature F057: 주요 워크플로우 안내"""
    return ok_response(data={
        "title": "📖 SQM v864.3 사용법",
        "sections": [
            {
                "title": "🟢 입고 워크플로우",
                "steps": [
                    "1. 파일 > 입고 > PDF 스캔 입고 → BL/D/O PDF 업로드",
                    "2. 파일 > 입고 > D/O 후속 연결 → 선사 D/O 문서 연결",
                    "3. 재고 탭에서 입고된 LOT 확인",
                ]
            },
            {
                "title": "🔴 출고 워크플로우",
                "steps": [
                    "1. 파일 > 출고 > Allocation 입력 → 판매배정 등록",
                    "2. 파일 > 출고 > 승인 대기 → 배정 승인",
                    "3. 파일 > 출고 > 즉시 출고 (원스톱) → 최종 출고 처리",
                    "4. 출고 탭에서 완료 이력 확인",
                ]
            },
            {
                "title": "📦 재고 조회",
                "steps": [
                    "사이드바 > Inventory 탭 → 전체 LOT 목록",
                    "사이드바 > Allocation 탭 → 판매배정 현황",
                    "사이드바 > Dashboard 탭 → KPI 요약",
                ]
            },
            {
                "title": "💾 백업/복구",
                "steps": [
                    "파일 > 백업 > 백업 생성 → DB 파일 복사본 생성",
                    "파일 > 백업 > 백업 목록 → 이전 백업 조회",
                    "파일 > 백업 > 복원 → 선택한 백업으로 복구",
                ]
            },
        ]
    })


# ── F058: 단축키 안내 ────────────────────────────────────────────
@router.get("/shortcuts", summary="⌨️ 단축키 안내")
def get_shortcuts():
    """Feature F058: 키보드 단축키 13개 목록"""
    return ok_response(data={
        "title": "⌨️ 단축키 안내",
        "shortcuts": [
            {"key": "Ctrl+O",          "action": "파일 열기"},
            {"key": "Ctrl+S",          "action": "파일 저장"},
            {"key": "Ctrl+Shift+S",    "action": "다른 이름으로 저장"},
            {"key": "Ctrl+F",          "action": "검색 포커스"},
            {"key": "F5",              "action": "데이터 새로고침"},
            {"key": "Ctrl+R",          "action": "데이터 새로고침"},
            {"key": "Ctrl+Tab",        "action": "다음 탭"},
            {"key": "Ctrl+Shift+Tab",  "action": "이전 탭"},
            {"key": "F11",             "action": "전체 화면"},
            {"key": "Escape",          "action": "닫기 / 메뉴 닫기"},
            {"key": "Ctrl+Q",          "action": "프로그램 종료"},
            {"key": "Ctrl+N",          "action": "신규 입고"},
            {"key": "Ctrl+E",          "action": "내보내기"},
        ]
    })


# ── F059: STATUS 상태값 안내 ─────────────────────────────────────
@router.get("/status-guide", summary="📊 STATUS 상태값 안내")
def get_status_guide():
    """Feature F059: LOT / 톤백 상태값 정의"""
    return ok_response(data={
        "title": "📊 STATUS 상태값 안내",
        "lot_statuses": [
            {"status": "AVAILABLE",  "color": "#2e7d32", "label": "가용",     "desc": "출고 가능한 정상 재고"},
            {"status": "RESERVED",   "color": "#1565c0", "label": "예약됨",   "desc": "판매 배정(Allocation) 완료, 출고 대기"},
            {"status": "PICKED",     "color": "#e65100", "label": "선택됨",   "desc": "Picking List에 배정, 출고 진행 중"},
            {"status": "OUTBOUND",   "color": "#6a1b9a", "label": "출고완료", "desc": "출고 처리 완료"},
            {"status": "SOLD",       "color": "#37474f", "label": "판매완료", "desc": "최종 판매 확정"},
            {"status": "RETURNED",   "color": "#c62828", "label": "반품",     "desc": "반품 입고 처리됨"},
        ],
        "tonbag_statuses": [
            {"status": "AVAILABLE",  "desc": "가용 상태 (입고 후 기본값)"},
            {"status": "RESERVED",   "desc": "판매배정에 포함됨"},
            {"status": "PICKED",     "desc": "피킹 리스트에 선택됨"},
            {"status": "SOLD",       "desc": "출고 확정됨"},
            {"status": "RETURNED",   "desc": "반품 처리됨"},
        ]
    })


# ── F060: DB 백업/복구 가이드 ────────────────────────────────────
@router.get("/backup-guide", summary="💾 DB 백업/복구 가이드")
def get_backup_guide():
    """Feature F060: 백업 및 복구 절차 안내"""
    return ok_response(data={
        "title": "💾 DB 백업/복구 가이드",
        "backup_steps": [
            "1. 파일 > 백업 > 백업 생성 클릭",
            "2. backup/ 폴더에 sqm_backup_YYYYMMDD_HHMMSS.db 파일 생성",
            "3. 최대 5개 보관 (자동 오래된 파일 삭제)",
        ],
        "restore_steps": [
            "1. 파일 > 백업 > 백업 목록에서 복원할 버전 선택",
            "2. 파일 > 백업 > 복원 클릭",
            "3. 현재 DB를 선택한 백업으로 교체",
            "4. 프로그램 재시작 권장",
        ],
        "caution": [
            "⚠️ 복원 시 현재 데이터 전부 덮어써짐 — 먼저 현재 백업 생성 권장",
            "⚠️ 백업 파일은 backup/ 폴더 외부로도 복사 보관 권장 (외장하드 등)",
            "⚠️ DB 파일 직접 복사/삭제 금지 — WAL 파일 포함 이동 필요",
        ]
    })


# ── F062: 버전 정보 ─────────────────────────────────────────────
@router.get("/version", summary="📝 버전 정보")
def get_version():
    """Feature F062: version.py 기반 버전 정보"""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(here))
        sys.path.insert(0, root)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "version", os.path.join(root, "version.py"))
        ver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ver)
        return ok_response(data={
            "app_name":    getattr(ver, "APP_NAME",    "SQM 재고관리 시스템"),
            "app_name_en": getattr(ver, "APP_NAME_EN", "SQM Inventory"),
            "version":     getattr(ver, "__version__", "unknown"),
            "release_date":getattr(ver, "RELEASE_DATE","unknown"),
            "build_date":  getattr(ver, "BUILD_DATE",  "unknown"),
            "build_note":  getattr(ver, "BUILD_NOTE",  ""),
        })
    except Exception as e:
        logger.warning("version.py load failed: %s", e)
        return ok_response(data={
            "app_name": "SQM 재고관리 시스템",
            "version":  "8.6.4",
            "note":     "version.py 로드 실패 — 기본값 표시"
        })
