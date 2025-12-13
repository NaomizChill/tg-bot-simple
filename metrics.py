import threading
import time
import functools
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Any, Callable, TypeVar

T = TypeVar("T")

class Counter:
    """Простой потокобезопасный счетчик."""
    def __init__(self, name: str):
        self.name = name
        self.value = 0
    def inc(self, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("Значение должно быть >= 0")
        self.value += amount
    def get(self) -> int:
        return self.value

@dataclass
class LatencyStats:
    """Статистика по задержке в миллисекундах."""
    count: int = 0
    total_ms: int = 0
    min_ms: int = 0
    max_ms: int = 0

    def observe(self, ms: int) -> None:
        if ms < 0: return
        if self.count == 0:
            self.min_ms = self.max_ms = ms
        else:
            self.min_ms = min(self.min_ms, ms)
            self.max_ms = max(self.max_ms, ms)
        self.count += 1
        self.total_ms += ms

    @property
    def avg_ms(self) -> float:
        if self.count == 0: return 0.0
        return self.total_ms / self.count

class MetricsRegistry:
    """Реестр всех метрик в памяти процесса."""
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, Counter] = {}
        self._latencies: Dict[str, LatencyStats] = {}

    def counter(self, name: str) -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name)
            return self._counters[name]

    def latency(self, name: str) -> LatencyStats:
        with self._lock:
            if name not in self._latencies:
                self._latencies[name] = LatencyStats()
            return self._latencies[name]

    # ПРАВИЛЬНЫЙ ВАРИАНТ
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            counters_snap = {name: c.get() for name, c in self._counters.items()}

            # Создаем "снимок" для latencies вручную, чтобы добавить avg_ms
            latencies_snap = {}
            for name, latency_stat in self._latencies.items():
                latencies_snap[name] = {
                    "count": latency_stat.count,
                    "total_ms": latency_stat.total_ms,
                    "min_ms": latency_stat.min_ms,
                    "max_ms": latency_stat.max_ms,
                    "avg_ms": latency_stat.avg_ms  # <--- Теперь мы его добавляем
                }

            return {"counters": counters_snap, "latencies": latencies_snap}

# Глобальный реестр метрик
metric = MetricsRegistry()

def timed(metric_name: str, logger: logging.Logger | None = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Декоратор для замера времени выполнения функции."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            t0 = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                t1 = time.perf_counter()
                dt_ms = int((t1 - t0) * 1000)
                metric.latency(metric_name).observe(dt_ms)
                if logger:
                    logger.debug(f"timed {func.__qualname__}: {dt_ms} ms")
        return wrapper
    return decorator