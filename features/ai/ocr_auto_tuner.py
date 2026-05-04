"""
OCR 자동 튜닝 모듈 (v3.0)
=========================

429 오류 빈도와 응답 시간을 기반으로 OCR 동시성을 자동 조절합니다.

핵심 기능:
- 429 오류 감지 시 자동 백오프
- 응답 시간 기반 동시성 증가/감소
- 최적 동시성 자동 탐색
"""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class TunerMetrics:
    """튜닝 메트릭"""
    total_requests: int = 0
    success_count: int = 0
    error_429_count: int = 0
    error_other_count: int = 0
    avg_response_time: float = 0.0
    current_concurrency: int = 3
    min_concurrency: int = 1
    max_concurrency: int = 10

    # 최근 응답 시간 (슬라이딩 윈도우)
    recent_times: deque = field(default_factory=lambda: deque(maxlen=20))

    # 429 발생 타임스탬프 (백오프 계산용)
    last_429_time: float = 0.0
    consecutive_429: int = 0


class OCRAutoTuner:
    """
    OCR 동시성 자동 튜너
    
    사용법:
        tuner = OCRAutoTuner(ocr_function)
        results = tuner.process_batch(file_list)
    """

    # 튜닝 파라미터
    TARGET_RESPONSE_TIME = 2.0      # 목표 응답 시간 (초)
    BACKOFF_BASE = 1.5              # 429 발생 시 백오프 배수
    INCREASE_THRESHOLD = 0.8        # 응답시간이 목표의 80% 이하면 동시성 증가
    DECREASE_THRESHOLD = 1.5        # 응답시간이 목표의 150% 이상이면 동시성 감소
    COOLDOWN_AFTER_429 = 5.0        # 429 후 쿨다운 시간 (초)

    def __init__(self, ocr_func: Callable,
                 min_concurrency: int = 1,
                 max_concurrency: int = 10,
                 initial_concurrency: int = 3):
        """
        Args:
            ocr_func: OCR 처리 함수 (file_path -> result)
            min_concurrency: 최소 동시성
            max_concurrency: 최대 동시성
            initial_concurrency: 초기 동시성
        """
        self.ocr_func = ocr_func
        self.metrics = TunerMetrics(
            current_concurrency=initial_concurrency,
            min_concurrency=min_concurrency,
            max_concurrency=max_concurrency
        )
        self._lock = threading.Lock()
        self._executor: Optional[ThreadPoolExecutor] = None

        # 콜백 (UI 업데이트용)
        self.on_progress: Optional[Callable[[int, int, str], None]] = None
        self.on_concurrency_change: Optional[Callable[[int], None]] = None

    def _record_request(self, response_time: float, is_429: bool, is_error: bool):
        """요청 결과 기록 및 동시성 조절"""
        with self._lock:
            self.metrics.total_requests += 1

            if is_429:
                self.metrics.error_429_count += 1
                self.metrics.consecutive_429 += 1
                self.metrics.last_429_time = time.time()
                self._decrease_concurrency(aggressive=True)

            elif is_error:
                self.metrics.error_other_count += 1

            else:
                self.metrics.success_count += 1
                self.metrics.consecutive_429 = 0
                self.metrics.recent_times.append(response_time)

                # 응답 시간 기반 동시성 조절
                if len(self.metrics.recent_times) >= 5:
                    avg_time = sum(self.metrics.recent_times) / len(self.metrics.recent_times)
                    self.metrics.avg_response_time = avg_time

                    # 429 쿨다운 체크
                    time_since_429 = time.time() - self.metrics.last_429_time
                    if time_since_429 < self.COOLDOWN_AFTER_429:
                        return  # 쿨다운 중에는 증가하지 않음

                    if avg_time < self.TARGET_RESPONSE_TIME * self.INCREASE_THRESHOLD:
                        self._increase_concurrency()
                    elif avg_time > self.TARGET_RESPONSE_TIME * self.DECREASE_THRESHOLD:
                        self._decrease_concurrency()

    def _increase_concurrency(self):
        """동시성 증가"""
        old = self.metrics.current_concurrency
        self.metrics.current_concurrency = min(
            self.metrics.current_concurrency + 1,
            self.metrics.max_concurrency
        )
        if old != self.metrics.current_concurrency:
            logger.info(f"[OCR튜너] 동시성 증가: {old} → {self.metrics.current_concurrency}")
            if self.on_concurrency_change:
                self.on_concurrency_change(self.metrics.current_concurrency)

    def _decrease_concurrency(self, aggressive: bool = False):
        """동시성 감소"""
        old = self.metrics.current_concurrency

        if aggressive:
            # 429 발생 시 급격히 감소
            decrease = max(1, self.metrics.current_concurrency // 2)
            self.metrics.current_concurrency = max(
                self.metrics.current_concurrency - decrease,
                self.metrics.min_concurrency
            )
        else:
            self.metrics.current_concurrency = max(
                self.metrics.current_concurrency - 1,
                self.metrics.min_concurrency
            )

        if old != self.metrics.current_concurrency:
            logger.warning(f"[OCR튜너] 동시성 감소: {old} → {self.metrics.current_concurrency}" +
                          (" (429 감지)" if aggressive else ""))
            if self.on_concurrency_change:
                self.on_concurrency_change(self.metrics.current_concurrency)

    def _process_single(self, file_path: str, index: int) -> Dict[str, Any]:
        """단일 파일 처리"""
        start_time = time.time()
        is_429 = False
        is_error = False
        result = None
        error_msg = None

        try:
            result = self.ocr_func(file_path)

        except (FileNotFoundError, OSError, PermissionError) as e:
            error_msg = str(e)
            is_error = True

            # 429 감지 (다양한 형태)
            if '429' in error_msg or 'rate limit' in error_msg.lower() or 'quota' in error_msg.lower():
                is_429 = True
                # 429 발생 시 즉시 대기
                backoff_time = self.BACKOFF_BASE ** min(self.metrics.consecutive_429, 5)
                logger.warning(f"[OCR튜너] 429 감지, {backoff_time:.1f}초 대기")
                time.sleep(backoff_time)

        response_time = time.time() - start_time
        self._record_request(response_time, is_429, is_error)

        return {
            'index': index,
            'file_path': file_path,
            'success': not is_error,
            'result': result,
            'error': error_msg,
            'response_time': response_time,
            'is_429': is_429
        }

    def process_batch(self, file_paths: list,
                      progress_callback: Callable[[int, int, str], None] = None) -> list:
        """
        배치 처리 (자동 동시성 조절)
        
        Args:
            file_paths: 처리할 파일 경로 목록
            progress_callback: 진행률 콜백 (current, total, message)
            
        Returns:
            처리 결과 목록
        """
        if progress_callback:
            self.on_progress = progress_callback

        total = len(file_paths)
        results = [None] * total
        completed = 0

        # 동적 executor 사용 (동시성 변경 시 재생성)
        with ThreadPoolExecutor(max_workers=self.metrics.max_concurrency) as executor:
            futures = {}
            pending_indices = list(range(total))

            while pending_indices or futures:
                # 현재 동시성만큼 작업 제출
                while pending_indices and len(futures) < self.metrics.current_concurrency:
                    idx = pending_indices.pop(0)
                    future = executor.submit(self._process_single, file_paths[idx], idx)
                    futures[future] = idx

                # 완료된 작업 수집
                done_futures = [f for f in futures if f.done()]

                for future in done_futures:
                    idx = futures.pop(future)
                    try:
                        result = future.result()
                        results[idx] = result
                        completed += 1

                        if self.on_progress:
                            status = "✓" if result['success'] else ("⚠429" if result['is_429'] else "✗")
                            self.on_progress(
                                completed, total,
                                f"[{completed}/{total}] {status} 동시성:{self.metrics.current_concurrency}"
                            )
                    except (ValueError, TypeError, AttributeError) as e:
                        results[idx] = {'index': idx, 'success': False, 'error': str(e)}
                        completed += 1

                # 대기
                if futures and not done_futures:
                    time.sleep(0.1)

        return results

    def get_stats(self) -> Dict:
        """현재 통계 반환"""
        with self._lock:
            return {
                'total_requests': self.metrics.total_requests,
                'success_count': self.metrics.success_count,
                'error_429_count': self.metrics.error_429_count,
                'error_other_count': self.metrics.error_other_count,
                'avg_response_time': self.metrics.avg_response_time,
                'current_concurrency': self.metrics.current_concurrency,
                'success_rate': (self.metrics.success_count / max(1, self.metrics.total_requests)) * 100
            }


# 간편 사용 함수
def create_ocr_tuner(ocr_func: Callable,
                     min_workers: int = 1,
                     max_workers: int = 10) -> OCRAutoTuner:
    """OCR 튜너 생성 헬퍼"""
    return OCRAutoTuner(
        ocr_func,
        min_concurrency=min_workers,
        max_concurrency=max_workers,
        initial_concurrency=min(3, max_workers)
    )



# =============================================================================
# GeminiCallGate — 단일 호출 게이트 (acquire/release 패턴)
# gemini_parser.py에서 사용하는 인터페이스 구현
# =============================================================================

class GeminiCallGate:
    """
    Gemini API 단일 호출을 위한 Circuit Breaker + Semaphore 게이트.

    OCRAutoTuner가 배치 처리용이라면, 이 클래스는 단건 호출용입니다.
    gemini_parser.py의 acquire/release/record_result 인터페이스를 구현합니다.

    Circuit Breaker 상태:
      - CLOSED (정상): 요청 허용
      - OPEN (차단): 연속 429가 임계값 초과 시 → 일정 시간 후 HALF-OPEN
      - HALF-OPEN: 1건 시험 허용 → 성공 시 CLOSED, 실패 시 OPEN 복귀
    """

    OPEN_THRESHOLD_429 = 5        # 연속 429 발생 시 OPEN 전환 임계값
    HALF_OPEN_COOLDOWN = 30.0     # OPEN → HALF-OPEN 대기 시간 (초)
    MAX_CONCURRENCY = 3           # 동시 허용 호출 수

    def __init__(self):
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(self.MAX_CONCURRENCY)
        self._consecutive_429 = 0
        self._open_since: float = 0.0
        self._state = "CLOSED"   # CLOSED / OPEN / HALF_OPEN

        # 메트릭
        self._total = 0
        self._success = 0
        self._error_429 = 0
        self._response_times: deque = field_factory()
        self._concurrency = self.MAX_CONCURRENCY

    def acquire(self) -> bool:
        """
        호출 권한 획득.
        Returns:
            True  — 호출 가능 (세마포어 획득 성공)
            False — Circuit Breaker가 OPEN 상태 (호출 차단)
        """
        with self._lock:
            if self._state == "OPEN":
                elapsed = time.time() - self._open_since
                if elapsed >= self.HALF_OPEN_COOLDOWN:
                    self._state = "HALF_OPEN"
                    logger.info("[GeminiGate] OPEN → HALF_OPEN (쿨다운 완료)")
                else:
                    remaining = self.HALF_OPEN_COOLDOWN - elapsed
                    logger.warning(
                        f"[GeminiGate] Circuit OPEN — {remaining:.0f}초 후 재시도 가능"
                    )
                    return False

        acquired = self._semaphore.acquire(blocking=False)
        if not acquired:
            logger.debug("[GeminiGate] 세마포어 포화 — 대기 중 (blocking acquire)")
            self._semaphore.acquire(blocking=True, timeout=30)
        return True

    def release(self):
        """호출 권한 반환 (finally 블록에서 반드시 호출)."""
        try:
            self._semaphore.release()
        except ValueError:
            pass  # 이미 최대치인 경우 무시

    def record_result(
        self,
        success: bool,
        response_time: float = 0.0,
        is_429: bool = False,
        error_message: str = "",
    ):
        """
        API 호출 결과 기록 및 Circuit Breaker 상태 갱신.

        Args:
            success: 호출 성공 여부
            response_time: 응답 시간 (초)
            is_429: 429 Rate Limit 오류 여부
            error_message: 오류 메시지 (실패 시)
        """
        with self._lock:
            self._total += 1

            if is_429:
                self._error_429 += 1
                self._consecutive_429 += 1
                logger.warning(
                    f"[GeminiGate] 429 감지 (연속 {self._consecutive_429}회)"
                )
                if self._consecutive_429 >= self.OPEN_THRESHOLD_429:
                    self._state = "OPEN"
                    self._open_since = time.time()
                    logger.error(
                        f"[GeminiGate] Circuit OPEN — 연속 429 {self._consecutive_429}회 초과"
                    )
            elif success:
                self._success += 1
                self._consecutive_429 = 0
                self._response_times.append(response_time)
                if self._state == "HALF_OPEN":
                    self._state = "CLOSED"
                    logger.info("[GeminiGate] HALF_OPEN → CLOSED (복구 성공)")

    @property
    def stats(self) -> dict:
        """현재 게이트 상태 요약 (로깅용)."""
        with self._lock:
            total = max(1, self._total)
            avg_rt = (
                sum(self._response_times) / len(self._response_times)
                if self._response_times
                else 0.0
            )
            return {
                "concurrency": self._concurrency,
                "success_rate": self._success / total,
                "avg_response_time": avg_rt,
                "state": self._state,
                "total": self._total,
                "error_429": self._error_429,
            }


def _field_factory_helper():
    """deque(maxlen=20) 팩토리 (클래스 body 밖에서 호출용)."""
    return deque(maxlen=20)


# 모듈 레벨 헬퍼 — 클래스 내 기본값으로 쓸 수 없어서 외부 노출
field_factory = _field_factory_helper


# 모듈 레벨 싱글톤
_gate_instance: Optional[GeminiCallGate] = None
_gate_lock = threading.Lock()


def get_ocr_tuner() -> GeminiCallGate:
    """
    GeminiCallGate 싱글톤 반환.

    gemini_parser.py에서 `from ocr_auto_tuner import get_ocr_tuner` 로 임포트.
    동일한 프로세스에서 항상 같은 인스턴스를 반환 (스레드 안전).
    """
    global _gate_instance
    if _gate_instance is None:
        with _gate_lock:
            if _gate_instance is None:
                _gate_instance = GeminiCallGate()
                logger.debug("[GeminiGate] 싱글톤 생성 완료")
    return _gate_instance

if __name__ == '__main__':
    logger.debug("OCR 자동 튜너 v3.0")
    logger.debug("=" * 40)
    logger.debug("기능: 429 오류 기반 동시성 자동 조절")
