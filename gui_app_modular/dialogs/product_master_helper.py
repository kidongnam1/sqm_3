# -*- coding: utf-8 -*-
"""
SQM v6.2.7 — 제품 마스터 헬퍼
================================
입고 화면 제품 콤보박스, 제품 코드 자동완성,
제품별 재고 리포트 등 공용 유틸리티.
"""

import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


def get_product_choices(db, include_code: bool = True) -> List[str]:
    """
    활성 제품 목록을 콤보박스용 문자열 리스트로 반환.
    
    Args:
        db: SQMDatabase 인스턴스
        include_code: True면 "LCA — Lithium Carbonate Anhydrous" 형태
    
    Returns:
        ["LCA — Lithium Carbonate Anhydrous", ...]
    """
    try:
        rows = db.fetchall(
            "SELECT code, full_name, korean_name FROM product_master "
            "WHERE is_active = 1 ORDER BY sort_order, code"
        ) or []
        result = []
        for r in rows:
            r = dict(r) if not isinstance(r, dict) else r
            if include_code:
                result.append(f"{r['code']} — {r['full_name']}")
            else:
                result.append(r['full_name'])
        return result
    except Exception as e:
        logger.debug(f"product_master 조회 실패 (테이블 미생성?): {e}")
        # 폴백: 기본 제품명
        return [
            "NSH — Nickel Sulfate Hexahydrate",
            "LCA — Lithium Carbonate Anhydrous",
            "CSH — Cobalt Sulfate Heptahydrate",
            "NCM — Nickel Cobalt Manganese",
            "NCA — Nickel Cobalt Aluminum",
            "LFP — Lithium Iron Phosphate",
            "LMO — Lithium Manganese Oxide",
            "LCO — Lithium Cobalt Oxide",
        ]


def parse_product_choice(choice: str) -> Tuple[str, str]:
    """
    콤보박스 선택값에서 (code, full_name) 추출.
    
    "LCA — Lithium Carbonate Anhydrous" → ("LCA", "Lithium Carbonate Anhydrous")
    "Lithium Carbonate" → ("", "Lithium Carbonate")
    """
    if ' — ' in choice:
        parts = choice.split(' — ', 1)
        return parts[0].strip(), parts[1].strip()
    return '', choice.strip()


def get_product_code_map(db) -> Dict[str, str]:
    """
    full_name → code 매핑 딕셔너리.
    입고 시 product명으로 product_code 자동 매칭.
    """
    try:
        rows = db.fetchall(
            "SELECT code, full_name FROM product_master WHERE is_active = 1"
        ) or []
        result = {}
        for r in rows:
            r = dict(r) if not isinstance(r, dict) else r
            result[r['full_name'].upper()] = r['code']
            # 부분 매칭 키도 추가
            for part in r['full_name'].upper().split():
                if len(part) > 4:
                    result[part] = r['code']
        return result
    except Exception:
        return {}


def auto_detect_product_code(db, product_name: str) -> str:
    """
    제품명으로 product_code 자동 감지.
    
    Args:
        product_name: "Lithium Carbonate Anhydrous" 또는 "LITHIUM CARBONATE" 등
    
    Returns:
        "LCA" 또는 "" (미매칭)
    """
    if not product_name:
        return ''
    
    name_upper = product_name.strip().upper()
    
    try:
        # 1) 정확 매칭
        row = db.fetchone(
            "SELECT code FROM product_master "
            "WHERE UPPER(full_name) = ? AND is_active = 1",
            (name_upper,)
        )
        if row:
            return row['code'] if isinstance(row, dict) else row[0]
        
        # 2) 포함 매칭 (product_name이 full_name에 포함)
        rows = db.fetchall(
            "SELECT code, full_name FROM product_master WHERE is_active = 1"
        ) or []
        for r in rows:
            r = dict(r) if not isinstance(r, dict) else r
            if name_upper in r['full_name'].upper() or r['full_name'].upper() in name_upper:
                return r['code']
        
        # 3) 키워드 매칭
        keywords = {
            'LITHIUM CARBONATE': 'LCA',
            'NICKEL SULFATE': 'NSH',
            'COBALT SULFATE': 'CSH',
            'NCM': 'NCM', 'NCA': 'NCA',
            'LFP': 'LFP', 'LMO': 'LMO', 'LCO': 'LCO',
            'IRON PHOSPHATE': 'LFP',
            'MANGANESE OXIDE': 'LMO',
            'COBALT OXIDE': 'LCO',
        }
        for kw, code in keywords.items():
            if kw in name_upper:
                return code
        
    except Exception as e:
        logger.debug(f"product_code 자동감지 실패: {e}")
    
    return ''


def get_product_inventory_report(db) -> List[Dict]:
    """
    제품별 재고 현황 리포트 (product_master JOIN).
    
    Returns:
        [{'code': 'LCA', 'full_name': '...', 'korean_name': '탄산리튬',
          'lot_count': 5, 'tonbag_count': 50, 'total_kg': 25001.0,
          'available_kg': 20000.0, 'reserved_kg': 5000.0, 'picked_kg': 0}, ...]
    """
    try:
        # product_master가 있으면 JOIN
        rows = db.fetchall("""
            SELECT 
                COALESCE(pm.code, '기타') as code,
                COALESCE(pm.full_name, i.product) as full_name,
                COALESCE(pm.korean_name, '') as korean_name,
                COUNT(DISTINCT i.lot_no) as lot_count,
                COALESCE(SUM(i.mxbg_pallet), 0) as tonbag_count,
                COALESCE(SUM(i.initial_weight), 0) as total_kg,
                COALESCE(SUM(i.current_weight), 0) as current_kg
            FROM inventory i
            LEFT JOIN product_master pm 
                ON (UPPER(i.product) LIKE '%' || UPPER(pm.full_name) || '%'
                    OR UPPER(pm.full_name) LIKE '%' || UPPER(i.product) || '%'
                    OR i.product_code = pm.code)
            GROUP BY COALESCE(pm.code, i.product)
            ORDER BY total_kg DESC
        """) or []
        
        result = []
        for r in rows:
            r = dict(r) if not isinstance(r, dict) else r
            # 톤백 상태별 집계
            code = r.get('code', '')
            full_name = r.get('full_name', '')
            
            # 톤백 레벨 상태 집계
            status_rows = db.fetchall("""
                SELECT t.status, COUNT(*) as cnt, COALESCE(SUM(t.weight), 0) as kg
                FROM inventory_tonbag t
                JOIN inventory i ON t.lot_no = i.lot_no
                LEFT JOIN product_master pm 
                    ON (UPPER(i.product) LIKE '%' || UPPER(pm.full_name) || '%'
                        OR UPPER(pm.full_name) LIKE '%' || UPPER(i.product) || '%'
                        OR i.product_code = pm.code)
                WHERE COALESCE(pm.code, i.product) = ?
                GROUP BY t.status
            """, (code,)) or []
            
            status_map = {}
            for sr in status_rows:
                sr = dict(sr) if not isinstance(sr, dict) else sr
                status_map[sr.get('status', '')] = {
                    'count': sr.get('cnt', 0),
                    'kg': sr.get('kg', 0)
                }
            
            result.append({
                'code': code,
                'full_name': full_name,
                'korean_name': r.get('korean_name', ''),
                'lot_count': r.get('lot_count', 0),
                'tonbag_count': r.get('tonbag_count', 0),
                'total_kg': r.get('total_kg', 0),
                'current_kg': r.get('current_kg', 0),
                'available_count': status_map.get('AVAILABLE', {}).get('count', 0),
                'available_kg': status_map.get('AVAILABLE', {}).get('kg', 0),
                'reserved_count': status_map.get('RESERVED', {}).get('count', 0),
                'reserved_kg': status_map.get('RESERVED', {}).get('kg', 0),
                'picked_count': status_map.get('PICKED', {}).get('count', 0),
                'picked_kg': status_map.get('PICKED', {}).get('kg', 0),
            })
        
        return result
        
    except Exception as e:
        logger.error(f"제품별 재고 리포트 오류: {e}")
        # product_master 없을 때 폴백
        try:
            rows = db.fetchall("""
                SELECT product,
                       COUNT(*) as lot_count,
                       COALESCE(SUM(initial_weight), 0) as total_kg,
                       COALESCE(SUM(current_weight), 0) as current_kg,
                       COALESCE(SUM(mxbg_pallet), 0) as tonbag_count
                FROM inventory
                GROUP BY product ORDER BY total_kg DESC
            """) or []
            return [dict(r) if not isinstance(r, dict) else r for r in rows]
        except Exception:
            return []
