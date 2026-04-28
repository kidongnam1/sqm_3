"""
SQM Inventory - Query Cache
============================

자주 조회되는 데이터 캐싱으로 성능 향상

v4.19.0 - Phase 5
작성자: Ruby
"""

import hashlib
import logging
import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QueryCache:
    """쿼리 결과 캐시"""

    def __init__(self, ttl: int = 60):
        """
        Args:
            ttl: Time To Live (초) - 캐시 유효 시간
        """
        self.cache = {}
        self.ttl = ttl
        self.hits = 0
        self.misses = 0
        self._lock = threading.RLock()  # P1-6: 스레드 안전 캐시 접근 보호
    def _make_key(self, sql: str, params: tuple) -> str:
        """캐시 키 생성"""
        key_str = f"{sql}:{params}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, sql: str, params: tuple = ()) -> Optional[Any]:
        """캐시에서 조회"""
        key = self._make_key(sql, params)

        with self._lock:  # P1-6: RLock 보호
            if key in self.cache:
                data, timestamp = self.cache[key]

                # TTL 체크
                if time.time() - timestamp < self.ttl:
                    self.hits += 1
                    logger.debug(f"✅ 캐시 HIT: {sql[:50]}...")
                    return data
                else:
                    # 만료된 캐시 삭제
                    del self.cache[key]

            self.misses += 1
            return None

    def set(self, sql: str, params: tuple, data: Any):
        """캐시에 저장"""
        key = self._make_key(sql, params)
        with self._lock:  # P1-6: RLock 보호
            self.cache[key] = (data, time.time())

    def invalidate(self, pattern: str = None):
        """
        캐시 무효화
        
        Args:
            pattern: SQL 패턴 (None이면 전체 삭제)
        """
        with self._lock:  # P1-6: RLock 보호
            if pattern is None:
                self.cache.clear()
                logger.info("캐시 전체 삭제")
            else:
                # 패턴 매칭 삭제
                keys_to_delete = [
                    key for key in self.cache if pattern in key
                ]
                for key in keys_to_delete:
                    del self.cache[key]
                logger.info(f"캐시 삭제: {len(keys_to_delete)}개 (pattern={pattern})")

    def get_stats(self) -> dict:
        """캐시 통계"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            'hits': self.hits,
            'misses': self.misses,
            'total': total,
            'hit_rate': round(hit_rate, 2),
            'cache_size': len(self.cache)
        }


# 전역 캐시 인스턴스
cache = QueryCache(ttl=60)


def cached_query(ttl: int = 60):
    """
    쿼리 결과 캐싱 데코레이터
    
    사용 예:
        @cached_query(ttl=120)
        def get_inventory():
            return db.fetchall("SELECT * FROM inventory")
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 키 생성 (함수명 + 인자)
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            key_hash = hashlib.md5(cache_key.encode()).hexdigest()

            # 캐시 조회
            if key_hash in cache.cache:
                data, timestamp = cache.cache[key_hash]
                if time.time() - timestamp < ttl:
                    cache.hits += 1
                    return data

            # 캐시 미스 - 실제 실행
            cache.misses += 1
            result = func(*args, **kwargs)

            # 결과 캐싱
            cache.cache[key_hash] = (result, time.time())

            return result
        return wrapper
    return decorator


__all__ = ['QueryCache', 'cache', 'cached_query']
