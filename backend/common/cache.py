"""
SQM v8.6.6 — LRU 캐시 + TTL (Tier 3 S2 Performance)
=====================================================
hot-path 조회 함수의 결과를 짧은 시간 캐싱하여 FastAPI 응답 속도 향상.

사용:
    from backend.common.cache import cached

    @cached(ttl_seconds=5)
    def get_inventory_summary():
        ...

주의: 캐시는 메모리 기반. 프로세스 재시작 시 휘발.
"""
from __future__ import annotations
import functools
import time
import threading
from typing import Callable, Any

_CACHE: dict[str, tuple[float, Any]] = {}
_LOCK = threading.RLock()


def cached(ttl_seconds: int = 5, max_size: int = 128):
    """시간 기반 LRU 캐시 데코레이터."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = f"{fn.__module__}.{fn.__qualname__}:{repr(args)}:{repr(sorted(kwargs.items()))}"
            now = time.time()
            with _LOCK:
                hit = _CACHE.get(key)
                if hit and (now - hit[0]) < ttl_seconds:
                    return hit[1]
            value = fn(*args, **kwargs)
            with _LOCK:
                if len(_CACHE) > max_size:
                    # 가장 오래된 항목 절반 제거
                    items = sorted(_CACHE.items(), key=lambda x: x[1][0])
                    for k, _ in items[:max_size // 2]:
                        _CACHE.pop(k, None)
                _CACHE[key] = (now, value)
            return value
        wrapper.cache_clear = lambda: _CACHE.clear()  # type: ignore[attr-defined]
        wrapper.cache_info = lambda: {"size": len(_CACHE)}  # type: ignore[attr-defined]
        return wrapper
    return decorator


def invalidate_all():
    """전체 캐시 무효화 (예: 입고/출고 후 호출)"""
    with _LOCK:
        _CACHE.clear()


def invalidate_prefix(prefix: str):
    """특정 모듈/함수 캐시만 무효화"""
    with _LOCK:
        keys = [k for k in _CACHE if k.startswith(prefix)]
        for k in keys:
            _CACHE.pop(k, None)
