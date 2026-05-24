from __future__ import annotations

import threading
import time


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int, cooldown_s: int) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._cooldown_s = max(1, cooldown_s)
        self._lock = threading.Lock()
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            until = self._open_until.get(key)
            if until is None:
                return True
            if now >= until:
                self._open_until.pop(key, None)
                self._failures[key] = 0
                return True
            return False

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failures[key] = 0
            self._open_until.pop(key, None)

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._failures[key] = self._failures.get(key, 0) + 1
            if self._failures[key] >= self._failure_threshold:
                self._open_until[key] = time.time() + self._cooldown_s
