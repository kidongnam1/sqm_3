"""
SQM 재고관리 - Gemini AI 대화형 재고 조회 (v2.9.43)

기능:
- 자연어로 재고 조회 (예: "리튬카보네이트 현재고 알려줘")
- 조회 결과 Excel 내보내기
- 조회 결과 PDF 리포트 생성
- 대화 히스토리 유지

사용법:
    from gemini_chat_query import GeminiChatQuery
    
    chat = GeminiChatQuery(db_path="inventory.db", api_key="YOUR_KEY")
    result = chat.ask("리튬카보네이트 제품 현재고 알려줘")
    logger.debug(f"{result['answer']}")
    
    # Excel 내보내기
    chat.export_last_result_to_excel("output.xlsx")
"""
import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 쿼리 템플릿 정의
# ═══════════════════════════════════════════════════════════════════════

QUERY_TEMPLATES = {
    "전체_재고_요약": """
        SELECT 
            COUNT(*) as lot_count,
            ROUND(SUM(initial_weight)/1000, 2) as total_inbound_mt,
            ROUND(SUM(current_weight)/1000, 2) as total_current_mt,
            ROUND((SUM(initial_weight) - SUM(current_weight))/1000, 2) as total_outbound_mt
        FROM inventory
    """,

    "제품별_재고": """
        SELECT 
            product as 제품,
            COUNT(*) as LOT수,
            ROUND(SUM(initial_weight)/1000, 2) as 입고량_MT,
            ROUND(SUM(current_weight)/1000, 2) as 현재고_MT,
            ROUND(SUM(current_weight)*100.0/SUM(initial_weight), 1) as 잔량율
        FROM inventory
        {where_clause}
        GROUP BY product
        ORDER BY 현재고_MT DESC
    """,

    "SAP별_재고": """
        SELECT 
            sap_no as SAP_NO,
            product as 제품,
            COUNT(*) as LOT수,
            ROUND(SUM(initial_weight)/1000, 2) as 입고량_MT,
            ROUND(SUM(current_weight)/1000, 2) as 현재고_MT
        FROM inventory
        {where_clause}
        GROUP BY sap_no
        ORDER BY sap_no
    """,

    "LOT_목록": """
        SELECT 
            lot_no as LOT_NO,
            sap_no as SAP_NO,
            bl_no as BL_NO,
            product as 제품,
            ROUND(initial_weight/1000, 3) as 입고량_MT,
            ROUND(current_weight/1000, 3) as 현재고_MT,
            status as 상태,
            arrival_date as 입고일
        FROM inventory
        {where_clause}
        ORDER BY arrival_date DESC, lot_no
        LIMIT {limit}
    """,

    "SubLOT_목록": """
        SELECT 
            t.lot_no as LOT_NO,
            t.sub_lt as Sub_LOT,
            t.weight as 중량_KG,
            t.status as 상태,
            t.inbound_date as 입고일,
            t.outbound_date as 출고일,
            i.product as 제품
        FROM inventory_tonbag t
        LEFT JOIN inventory i ON t.lot_no = i.lot_no
        {where_clause}
        ORDER BY t.lot_no, t.sub_lt
        LIMIT {limit}
    """,

    "월별_현황": """
        SELECT 
            strftime('%Y-%m', arrival_date) as 월,
            COUNT(*) as LOT수,
            ROUND(SUM(initial_weight)/1000, 2) as 입고량_MT
        FROM inventory
        {where_clause}
        GROUP BY 월
        ORDER BY 월
    """,

    "상태별_현황": """
        SELECT 
            status as 상태,
            COUNT(*) as 수량,
            ROUND(SUM(current_weight)/1000, 2) as 중량_MT
        FROM inventory
        {where_clause}
        GROUP BY status
    """,

    "출고_현황": """
        SELECT 
            t.outbound_date as 출고일,
            COUNT(*) as 출고수량,
            ROUND(SUM(t.weight)/1000, 2) as 출고량_MT,
            i.product as 제품
        FROM inventory_tonbag t
        LEFT JOIN inventory i ON t.lot_no = i.lot_no
        WHERE t.status = 'PICKED'
        {and_clause}
        GROUP BY t.outbound_date, i.product
        ORDER BY t.outbound_date DESC
        LIMIT {limit}
    """,

    "저재고_LOT": """
        SELECT 
            lot_no as LOT_NO,
            product as 제품,
            ROUND(current_weight/1000, 3) as 현재고_MT,
            ROUND(current_weight*100.0/initial_weight, 1) as 잔량율
        FROM inventory
        WHERE current_weight > 0 
        AND current_weight < initial_weight * {threshold}
        ORDER BY 잔량율 ASC
        LIMIT {limit}
    """,
    "예약_배정_현황": """
        SELECT 
            status as 상태,
            COUNT(*) as 건수,
            ROUND(SUM(COALESCE(qty_mt, 0)), 2) as 수량_MT
        FROM allocation_plan
        GROUP BY status
        ORDER BY 
            CASE status WHEN 'RESERVED' THEN 1 WHEN 'EXECUTED' THEN 2 WHEN 'CANCELLED' THEN 3 ELSE 4 END
    """,
    "예약_배정_목록": """
        SELECT 
            ap.lot_no as LOT_NO,
            ap.sub_lt as Sub_LT,
            ap.customer as 고객,
            ap.sale_ref as SALE_REF,
            ap.qty_mt as 수량_MT,
            ap.outbound_date as 출고예정일,
            ap.status as 상태,
            ap.created_at as 예약일시
        FROM allocation_plan ap
        {where_clause}
        ORDER BY ap.created_at DESC
        LIMIT {limit}
    """,
}

# 제품명 매핑 (한글 → DB값)
# v3.6.9: 공통 모듈에서 PRODUCT_MAPPING import (중복 제거)
try:
    from features.ai.gemini_utils import PRODUCT_MAPPING
except ImportError:
    try:
        from gemini_utils import PRODUCT_MAPPING
    except ImportError:
        # fallback: 최소한의 매핑
        PRODUCT_MAPPING = {
            "리튬카보네이트": "LITHIUM CARBONATE",
            "탄산리튬": "LITHIUM CARBONATE",
            "리튬하이드록사이드": "LITHIUM HYDROXIDE",
            "수산화리튬": "LITHIUM HYDROXIDE",
            "리튬클로라이드": "LITHIUM CHLORIDE",
            "염화리튬": "LITHIUM CHLORIDE",
            "포타슘클로라이드": "POTASSIUM CHLORIDE",
            "염화칼륨": "POTASSIUM CHLORIDE",
            "소듐나이트레이트": "SODIUM NITRATE",
            "질산나트륨": "SODIUM NITRATE",
        }


@dataclass
class QueryResult:
    """쿼리 결과"""
    success: bool
    query_type: str
    sql: str
    data: List[Dict]
    columns: List[str]
    row_count: int
    answer: str
    timestamp: datetime = field(default_factory=datetime.now)
    error: str = ""


class GeminiChatQuery:
    """Gemini AI 대화형 재고 조회"""

    def __init__(self, db_path: str, api_key: str = None):
        """
        Args:
            db_path: 데이터베이스 경로
            api_key: Gemini API 키 (없으면 환경변수에서 로드)
        """
        self.db_path = db_path
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

        self.db = None
        self.chat_history: List[Dict] = []
        self.last_result: Optional[QueryResult] = None

        self._init_db()
        self._init_gemini()

    def _init_db(self):
        """DB 초기화"""
        try:
            from engine_modules.database import SQMDatabase
            self.db = SQMDatabase(self.db_path)
            logger.info(f"DB 연결 성공: {self.db_path}")
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"DB 연결 실패: {e}")
            raise

    def _init_gemini(self):
        """Gemini API 초기화 (v3.6.9: google-genai SDK로 통일)"""
        self.gemini_available = False
        self.client = None
        self.model_name = "gemini-2.5-flash"

        if not self.api_key:
            logger.warning("Gemini API 키가 없습니다. 규칙 기반 파싱만 사용합니다.")
            return

        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.gemini_available = True
            logger.info(f"Gemini API 초기화 성공 (모델: {self.model_name})")
        except ImportError:
            logger.warning("google-genai 패키지가 없습니다: pip install google-genai")
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(f"Gemini API 초기화 실패: {e}")

    def ask(self, question: str) -> Dict[str, Any]:
        """
        자연어 질문으로 재고 조회
        
        Args:
            question: 자연어 질문
            
        Returns:
            dict: {
                'success': bool,
                'answer': str,
                'data': list,
                'columns': list,
                'row_count': int,
                'query_type': str,
                'elapsed_ms': int  # v3.6.9: 응답 시간 (ms)
            }
        """
        import time
        _ask_start = time.time()

        logger.info(f"질문: {question}")

        # 1. 질문 분석
        intent = self._analyze_intent(question)
        logger.info(f"의도 분석: {intent}")

        # 2. SQL 생성 및 실행
        result = self._execute_query(intent, question)

        # 3. 결과 저장
        self.last_result = result
        self.chat_history.append({
            "role": "user",
            "content": question,
            "timestamp": datetime.now().isoformat()
        })
        self.chat_history.append({
            "role": "assistant",
            "content": result.answer,
            "timestamp": datetime.now().isoformat()
        })

        _elapsed_ms = int((time.time() - _ask_start) * 1000)
        logger.info(f"질문 처리 완료: {_elapsed_ms}ms")

        return {
            "success": result.success,
            "answer": result.answer,
            "data": result.data,
            "columns": result.columns,
            "row_count": result.row_count,
            "query_type": result.query_type,
            "sql": result.sql,
            "elapsed_ms": _elapsed_ms
        }

    def _analyze_intent(self, question: str) -> Dict[str, Any]:
        """질문 의도 분석"""
        q = question.lower()

        intent = {
            "query_type": "전체_재고_요약",
            "product": None,
            "sap_no": None,
            "bl_no": None,
            "lot_no": None,
            "date_range": None,
            "status": None,
            "limit": 100,
            "threshold": 0.3,  # 저재고 기준
        }

        # 제품 추출
        for kr_name, en_name in PRODUCT_MAPPING.items():
            if kr_name in q:
                intent["product"] = en_name
                break

        # SAP NO 추출
        sap_match = re.search(r'sap\s*(?:no|번호)?\s*[:\s]?\s*(\d{7})', q)
        if sap_match:
            intent["sap_no"] = sap_match.group(1)
        else:
            sap_match = re.search(r'22\d{5}', q)
            if sap_match:
                intent["sap_no"] = sap_match.group(0)

        # BL NO 추출
        bl_match = re.search(r'bl\s*(?:no|번호)?\s*[:\s]?\s*([A-Z]{4}\d+)', q, re.I)
        if bl_match:
            intent["bl_no"] = bl_match.group(1).upper()

        # LOT NO 추출
        lot_match = re.search(r'lot\s*(?:no|번호)?\s*[:\s]?\s*(\d{8,11})', q)  # v8.6.4: 8~11자리
        if lot_match:
            intent["lot_no"] = lot_match.group(1)
        else:
            lot_match = re.search(r'112\d{7}', q)
            if lot_match:
                intent["lot_no"] = lot_match.group(0)

        # 날짜/월 추출
        month_match = re.search(r'(\d{4})년?\s*(\d{1,2})월', q)
        if month_match:
            intent["date_range"] = f"{month_match.group(1)}-{int(month_match.group(2)):02d}"

        # 쿼리 타입 결정
        if "allocation" in q or "allocaton" in q or "예약" in q or "배정" in q or "allocation table" in q:
            # "allocation table에서 몇 개 allocation됐니?" → 예약/배정 현황
            if "목록" in q or "리스트" in q or "내역" in q:
                intent["query_type"] = "예약_배정_목록"
            else:
                intent["query_type"] = "예약_배정_현황"
        elif "전체" in q and ("요약" in q or "현황" in q):
            intent["query_type"] = "전체_재고_요약"
        elif "제품" in q and "별" in q:
            intent["query_type"] = "제품별_재고"
        elif "sap" in q and "별" in q:
            intent["query_type"] = "SAP별_재고"
        elif "월" in q and "별" in q:
            intent["query_type"] = "월별_현황"
        elif "상태" in q and "별" in q:
            intent["query_type"] = "상태별_현황"
        elif "출고" in q and ("현황" in q or "내역" in q or "목록" in q):
            intent["query_type"] = "출고_현황"
        elif "저재고" in q or "부족" in q or ("잔량" in q and ("이하" in q or "미만" in q)):
            intent["query_type"] = "저재고_LOT"
            # 퍼센트 추출
            pct_match = re.search(r'(\d+)\s*%', q)
            if pct_match:
                intent["threshold"] = int(pct_match.group(1)) / 100
        elif "sublot" in q or "sub-lot" in q or "서브롯" in q or "서브 롯" in q:
            intent["query_type"] = "SubLOT_목록"
        elif "lot" in q and ("목록" in q or "리스트" in q or "조회" in q):
            intent["query_type"] = "LOT_목록"
        elif intent["product"] or intent["sap_no"]:
            # 특정 조건이 있으면 LOT 목록
            if "재고" in q or "현황" in q:
                intent["query_type"] = "제품별_재고"
            else:
                intent["query_type"] = "LOT_목록"
        elif "현재고" in q or "재고" in q:
            if intent["product"]:
                intent["query_type"] = "제품별_재고"
            else:
                intent["query_type"] = "전체_재고_요약"

        return intent

    def _execute_query(self, intent: Dict, question: str) -> QueryResult:
        """쿼리 실행"""
        query_type = intent["query_type"]

        try:
            # WHERE 절 구성 — ? 파라미터 바인딩 사용 (SQL 인젝션 방지 P0-1)
            where_parts: list = []
            and_parts: list = []
            params: list = []

            if intent["product"]:
                where_parts.append("product = ?")
                and_parts.append("i.product = ?")
                params.append(intent["product"])

            if intent["sap_no"]:
                where_parts.append("sap_no = ?")
                and_parts.append("i.sap_no = ?")
                params.append(intent["sap_no"])

            if intent["bl_no"]:
                where_parts.append("bl_no = ?")
                and_parts.append("i.bl_no = ?")
                params.append(intent["bl_no"])

            if intent["lot_no"]:
                where_parts.append("lot_no = ?")
                and_parts.append("i.lot_no = ?")
                params.append(intent["lot_no"])

            if intent["date_range"]:
                where_parts.append("arrival_date LIKE ?")
                and_parts.append("i.arrival_date LIKE ?")
                params.append(f"{intent['date_range']}%")

            # 예약_배정: allocation_plan 테이블만 사용 → lot_no / created_at 조건만
            if query_type in ("예약_배정_현황", "예약_배정_목록"):
                ap_parts: list = []
                ap_params: list = []
                if intent.get("lot_no"):
                    ap_parts.append("ap.lot_no = ?")
                    ap_params.append(intent["lot_no"])
                if intent.get("date_range"):
                    ap_parts.append("ap.created_at LIKE ?")
                    ap_params.append(f"{intent['date_range']}%")
                where_parts = ap_parts
                and_parts = ap_parts
                params = ap_params

            where_clause = ""
            and_clause = ""
            if where_parts:
                where_clause = "WHERE " + " AND ".join(where_parts)
                and_clause = "AND " + " AND ".join(and_parts)

            # SQL 생성 — limit/threshold는 숫자이므로 format 안전
            sql_template = QUERY_TEMPLATES.get(query_type, QUERY_TEMPLATES["전체_재고_요약"])
            sql = sql_template.format(
                where_clause=where_clause,
                and_clause=and_clause,
                limit=int(intent.get("limit", 100)),
                threshold=float(intent.get("threshold", 0.3))
            )

            # 실행 — 파라미터 바인딩으로 SQL 인젝션 방지
            rows = self.db.fetchall(sql, tuple(params))

            # 결과를 딕셔너리 리스트로 변환
            if rows and isinstance(rows[0], dict):
                # SQMDatabase가 이미 dict로 반환
                data = rows
                columns = list(rows[0].keys()) if rows else []
            else:
                # tuple/Row인 경우 — params 함께 전달
                cursor = self.db.execute(sql, tuple(params))
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                data = [dict(zip(columns, row)) for row in rows]

            # 답변 생성
            answer = self._generate_answer(query_type, data, columns, intent, question)

            return QueryResult(
                success=True,
                query_type=query_type,
                sql=sql,
                data=data,
                columns=columns,
                row_count=len(data),
                answer=answer
            )

        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            err_msg = str(e)
            logger.error(f"쿼리 실행 오류: {e}")
            if "allocation_plan" in err_msg and query_type in ("예약_배정_현황", "예약_배정_목록"):
                answer = (
                    "Allocation(예약) 테이블이 DB에 없습니다. "
                    "앱을 한 번 종료 후 다시 실행하면 테이블이 자동 생성됩니다."
                )
            else:
                answer = f"조회 중 오류가 발생했습니다: {err_msg}"
            return QueryResult(
                success=False,
                query_type=query_type,
                sql="",
                data=[],
                columns=[],
                row_count=0,
                answer=answer,
                error=err_msg
            )

    def _generate_answer(self, query_type: str, data: List[Dict],
                         columns: List[str], intent: Dict, question: str) -> str:
        """자연어 답변 생성"""
        if not data:
            # 쿼리 타입별 맞춤 빈 결과 안내
            if query_type == "저재고_LOT":
                pct = int(intent.get("threshold", 0.3) * 100)
                return f"✅ 잔량율 {pct}% 이하인 LOT가 없습니다.\n현재 모든 LOT가 충분한 재고를 보유하고 있습니다."
            elif query_type == "제품별_재고" and intent.get("product"):
                return (f"📋 '{intent['product']}' 제품의 재고가 없습니다.\n"
                        f"현재 DB에 등록된 제품을 확인하려면 '제품별 재고'를 조회하세요.")
            return "📋 조회 결과가 없습니다."

        # Gemini 사용 가능하면 AI 답변 생성
        if self.gemini_available and len(data) <= 50:
            try:
                import time
                _start = time.time()
                answer = self._generate_ai_answer(data, columns, question)
                _elapsed = int((time.time() - _start) * 1000)
                logging.info(f"AI 답변 생성 완료 ({_elapsed}ms)")

                # v5.6.8: AI 답변 검증 — 데이터가 있는데 "없습니다"라고 하면 fallback
                if data and any(kw in answer for kw in ['없습니다', '정보가 없', '데이터가 없', '찾을 수 없']):
                    logging.warning(f"AI 답변이 데이터({len(data)}건)와 모순 → 규칙 기반 fallback")
                else:
                    return answer
            except PermissionError as e:
                return f"⚠️ API 키 오류: {e}\nsettings.ini의 api_key를 확인하세요."
            except RuntimeError:
                return "⚠️ API 한도 초과: 잠시 후 다시 시도해주세요."
            except TimeoutError:
                pass  # 규칙 기반으로 fallback
            except (ValueError, TypeError, KeyError) as e:
                logging.debug(f"AI 답변 생성 실패: {e}")  # 실패시 규칙 기반으로

        # 규칙 기반 답변
        if query_type == "전체_재고_요약":
            r = data[0]
            return (
                f"📊 전체 재고 현황\n\n"
                f"• 총 LOT 수: {r.get('lot_count', 0):,}개\n"
                f"• 총 입고량: {r.get('total_inbound_mt', 0):,.1f} MT\n"
                f"• 현재 재고: {r.get('total_current_mt', 0):,.1f} MT\n"
                f"• 총 출고량: {r.get('total_outbound_mt', 0):,.1f} MT"
            )

        elif query_type == "제품별_재고":
            lines = ["📊 제품별 재고 현황\n"]
            for r in data:
                lines.append(
                    f"• {r.get('제품', '')}: {r.get('현재고_MT', 0):,.1f} MT "
                    f"({r.get('LOT수', 0)}개 LOT, 잔량율 {r.get('잔량율', 0):.1f}%)"
                )
            return "\n".join(lines)

        elif query_type == "SAP별_재고":
            lines = [f"📊 SAP NO별 재고 현황 ({len(data)}건)\n"]
            for r in data[:10]:  # 상위 10개만
                lines.append(
                    f"• {r.get('SAP_NO', '')}: {r.get('현재고_MT', 0):,.1f} MT "
                    f"({r.get('제품', '')})"
                )
            if len(data) > 10:
                lines.append(f"\n... 외 {len(data)-10}건")
            return "\n".join(lines)

        elif query_type == "월별_현황":
            lines = ["📊 월별 입고 현황\n"]
            for r in data:
                lines.append(
                    f"• {r.get('월', '')}: {r.get('입고량_MT', 0):,.1f} MT ({r.get('LOT수', 0)}개 LOT)"
                )
            return "\n".join(lines)

        elif query_type in ("LOT_목록", "SubLOT_목록"):
            product_info = ""
            if intent.get("product"):
                # 제품 매핑 역변환 (영문→한글)
                kr_map = {"LITHIUM CARBONATE": "리튬카보네이트", "NICKEL SULFATE": "니켈설페이트"}
                kr = kr_map.get(intent["product"], intent["product"])
                total_mt = sum(r.get("현재고_MT", 0) for r in data)
                product_info = f" ({kr})"
                return (
                    f"📋 {kr} 재고 현황{product_info}\n\n"
                    f"• LOT 수: {len(data)}개\n"
                    f"• 총 현재고: {total_mt:,.1f} MT\n\n"
                    f"(상세 데이터는 Excel/PDF로 내보내기 가능)"
                )
            return f"📋 조회 결과: {len(data)}건\n\n(상세 데이터는 Excel/PDF로 내보내기 가능)"

        elif query_type == "저재고_LOT":
            lines = [f"⚠️ 저재고 LOT ({len(data)}건)\n"]
            for r in data[:10]:
                lines.append(
                    f"• {r.get('LOT_NO', '')}: {r.get('현재고_MT', 0):.2f} MT "
                    f"(잔량 {r.get('잔량율', 0):.1f}%) - {r.get('제품', '')}"
                )
            return "\n".join(lines)
        elif query_type == "예약_배정_현황":
            total = sum(r.get("건수", 0) for r in data)
            if total == 0:
                return "📋 Allocation(예약/배정) 현황\n\n• 예약된 건수: 0건 (allocation_plan에 데이터 없음)"
            lines = [f"📋 Allocation(예약/배정) 현황 — 총 {total}건\n"]
            status_kr = {"RESERVED": "예약중", "EXECUTED": "출고실행됨", "CANCELLED": "취소됨"}
            for r in data:
                st = r.get("상태", "")
                lines.append(
                    f"• {status_kr.get(st, st)}: {r.get('건수', 0)}건 "
                    f"({r.get('수량_MT', 0):,.1f} MT)"
                )
            return "\n".join(lines)
        elif query_type == "예약_배정_목록":
            if not data:
                return "📋 예약/배정 목록: 0건"
            return f"📋 예약/배정 목록: {len(data)}건\n\n(상세는 Excel/PDF 내보내기 가능)"

        else:
            return f"조회 결과: {len(data)}건"

    def _generate_ai_answer(self, data: List[Dict], columns: List[str], question: str) -> str:
        """Gemini로 AI 답변 생성"""
        if not self.client:
            return self._generate_answer_fallback(data, columns)

        prompt = f"""
다음은 재고 조회 결과입니다. 사용자의 질문에 대해 친절하고 간결하게 한국어로 답변해주세요.

중요: DB에서 제품명은 영문으로 저장되어 있습니다.
- 'LITHIUM CARBONATE' = 리튬카보네이트 (탄산리튬)
- 'NICKEL SULFATE' = 니켈설페이트 (황산니켈)
사용자가 한글로 물어봐도, 조회 결과에 해당 영문 제품이 있으면 동일한 제품으로 답변하세요.

질문: {question}

조회 결과 (컬럼: {columns}):
{json.dumps(data[:20], ensure_ascii=False, indent=2)}

총 {len(data)}건

답변 형식:
- 핵심 정보를 먼저 요약
- 필요시 상세 내역 나열
- 이모지 적절히 사용
- 200자 이내로 간결하게
"""

        try:
            from features.ai.gemini_utils import call_gemini_safe
            response = call_gemini_safe(
                self.client, self.model_name, prompt, timeout=30
            )
        except ImportError:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
        return response.text

    def export_to_excel(self, filepath: str = None) -> str:
        """마지막 조회 결과를 Excel로 내보내기"""
        if not self.last_result or not self.last_result.data:
            return "내보낼 데이터가 없습니다."

        try:
            import pandas as pd

            if filepath is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = f"재고조회_{self.last_result.query_type}_{timestamp}.xlsx"

            df = pd.DataFrame(self.last_result.data)

            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='조회결과', index=False)

                # 열 너비 자동 조정
                worksheet = writer.sheets['조회결과']
                for idx, col in enumerate(df.columns):
                    max_len = max(
                        df[col].astype(str).map(len).max(),
                        len(str(col))
                    ) + 2
                    worksheet.column_dimensions[chr(65 + idx)].width = min(max_len, 50)

            logger.info(f"Excel 내보내기 완료: {filepath}")
            return filepath

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Excel 내보내기 실패: {e}")
            return f"오류: {str(e)}"

    def export_to_pdf(self, filepath: str = None) -> str:
        """마지막 조회 결과를 PDF로 내보내기"""
        if not self.last_result or not self.last_result.data:
            return "내보낼 데이터가 없습니다."

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )

            if filepath is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = f"재고조회_{self.last_result.query_type}_{timestamp}.pdf"

            # 한글 폰트 등록 시도
            try:
                pdfmetrics.registerFont(TTFont('Malgun', 'malgun.ttf'))
                font_name = 'Malgun'
            except (ValueError, TypeError, KeyError):
                font_name = 'Helvetica'

            doc = SimpleDocTemplate(
                filepath,
                pagesize=landscape(A4),
                rightMargin=10*mm,
                leftMargin=10*mm,
                topMargin=10*mm,
                bottomMargin=10*mm
            )

            elements = []
            styles = getSampleStyleSheet()

            # 제목
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontName=font_name,
                fontSize=16,
                spaceAfter=20
            )
            elements.append(Paragraph(f"재고 조회 결과 - {self.last_result.query_type}", title_style))
            elements.append(Paragraph(f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Spacer(1, 10*mm))

            # 테이블
            data = self.last_result.data[:100]  # 최대 100행
            columns = self.last_result.columns

            table_data = [columns]  # 헤더
            for row in data:
                table_data.append([str(row.get(col, '')) for col in columns])

            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))

            elements.append(table)

            # 요약
            elements.append(Spacer(1, 10*mm))
            elements.append(Paragraph(f"총 {len(data)}건 / 전체 {self.last_result.row_count}건", styles['Normal']))

            doc.build(elements)

            logger.info(f"PDF 내보내기 완료: {filepath}")
            return filepath

        except ImportError:
            return "PDF 생성을 위해 reportlab 패키지가 필요합니다."
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"PDF 내보내기 실패: {e}")
            return f"오류: {str(e)}"

    def get_history(self) -> List[Dict]:
        """대화 히스토리 반환"""
        return self.chat_history

    def clear_history(self):
        """대화 히스토리 초기화"""
        self.chat_history = []
        self.last_result = None


# ═══════════════════════════════════════════════════════════════════════
# 테스트
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 테스트 실행
    TEST_DB = "./test_inventory.db"

    if not os.path.exists(TEST_DB):
        logger.debug(f"테스트 DB가 없습니다: {TEST_DB}")
        exit(1)

    chat = GeminiChatQuery(db_path=TEST_DB)

    logger.debug("=" * 60)
    logger.debug("  SQM 재고 AI 조회 테스트")
    logger.debug("=" * 60)

    # 테스트 질문들
    questions = [
        "전체 재고 현황 알려줘",
        "제품별 재고 현황",
        "리튬카보네이트 현재고",
        "2025년 3월 입고분",
        "저재고 LOT 목록 (30% 이하)",
        "SAP NO별 재고 현황",
    ]

    for q in questions:
        logger.debug(f"\n질문: {q}")
        logger.debug("-" * 40)
        result = chat.ask(q)
        logger.debug(f"{result['answer']}")
        logger.debug(f"(조회 건수: {result['row_count']})")

    # Excel 내보내기 테스트
    logger.debug("\n" + "=" * 60)
    logger.debug("Excel 내보내기 테스트...")
    excel_path = chat.export_to_excel()
    logger.debug(f"생성됨: {excel_path}")
