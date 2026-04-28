"""
SQM Inventory - Performance Monitor
====================================

성능 측정 및 병목 분석

v4.19.0 - Phase 5
작성자: Ruby
"""

import json
import logging
import time
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Dict, List

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """성능 모니터링 클래스"""

    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.slow_queries: List[Dict] = []
        self.slow_threshold = 1.0  # 1초 이상이면 느림

    def measure(self, operation_name: str):
        """
        작업 시간 측정 데코레이터
        
        사용 예:
            @monitor.measure("입고_처리")
            def process_inbound(data):
                ...
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    elapsed = time.time() - start
                    self._record(operation_name, elapsed, func.__name__)
            return wrapper
        return decorator

    def _record(self, operation: str, elapsed: float, func_name: str):
        """측정 결과 기록"""
        if operation not in self.metrics:
            self.metrics[operation] = []

        self.metrics[operation].append(elapsed)

        # 느린 작업 기록
        if elapsed > self.slow_threshold:
            self.slow_queries.append({
                'operation': operation,
                'function': func_name,
                'elapsed': round(elapsed, 3),
                'timestamp': datetime.now().isoformat()
            })
            logger.warning(f"⚠️ 느린 작업: {operation} ({elapsed:.3f}초)")

    def get_stats(self, operation: str = None) -> Dict:
        """
        통계 조회
        
        Args:
            operation: 특정 작업 (None이면 전체)
        
        Returns:
            dict: {operation: {count, avg, min, max, total}}
        """
        if operation:
            return self._calc_stats(operation)

        # 전체 통계
        stats = {}
        for op in self.metrics:
            stats[op] = self._calc_stats(op)
        return stats

    def _calc_stats(self, operation: str) -> Dict:
        """작업별 통계 계산"""
        times = self.metrics.get(operation, [])
        if not times:
            return {
                'count': 0,
                'avg': 0,
                'min': 0,
                'max': 0,
                'total': 0
            }

        return {
            'count': len(times),
            'avg': round(sum(times) / len(times), 3),
            'min': round(min(times), 3),
            'max': round(max(times), 3),
            'total': round(sum(times), 3)
        }

    def get_slow_queries(self, limit: int = 10) -> List[Dict]:
        """
        느린 작업 조회
        
        Args:
            limit: 조회 개수
        
        Returns:
            List[dict]: 느린 작업 목록
        """
        # 느린 순으로 정렬
        sorted_queries = sorted(
            self.slow_queries,
            key=lambda x: x['elapsed'],
            reverse=True
        )
        return sorted_queries[:limit]

    def reset(self):
        """통계 초기화"""
        self.metrics.clear()
        self.slow_queries.clear()
        logger.info("성능 통계 초기화됨")

    def export_report(self, filepath: str):
        """
        성능 보고서 내보내기
        
        Args:
            filepath: 저장 경로 (JSON)
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'statistics': self.get_stats(),
            'slow_queries': self.get_slow_queries(50),
            'summary': self._generate_summary()
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"성능 보고서 저장: {filepath}")

    def _generate_summary(self) -> Dict:
        """요약 통계"""
        total_ops = sum(len(times) for times in self.metrics.values())
        total_time = sum(sum(times) for times in self.metrics.values())

        # 가장 느린 작업 Top 3
        avg_times = {
            op: self._calc_stats(op)['avg']
            for op in self.metrics
        }
        slowest = sorted(avg_times.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            'total_operations': total_ops,
            'total_time': round(total_time, 3),
            'slow_operations_count': len(self.slow_queries),
            'slowest_avg': [
                {'operation': op, 'avg_time': time}
                for op, time in slowest
            ]
        }


# 전역 모니터 인스턴스
monitor = PerformanceMonitor()


def measure_time(operation_name: str):
    """
    성능 측정 데코레이터 (간편 사용)
    
    사용 예:
        @measure_time("DB_조회")
        def fetch_data():
            ...
    """
    return monitor.measure(operation_name)


__all__ = ['PerformanceMonitor', 'monitor', 'measure_time']
