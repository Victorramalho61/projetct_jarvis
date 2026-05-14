"""Circuit breaker + retry para chamadas ao SQL Server Benner."""
import logging
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)


class CBState(Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker thread-safe para conexões Benner."""

    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout_s: int = 120):
        self.name = name
        self._threshold = failure_threshold
        self._timeout   = recovery_timeout_s
        self._state     = CBState.CLOSED
        self._failures  = 0
        self._last_fail: datetime | None = None
        self._lock      = threading.RLock()

    @property
    def state(self) -> CBState:
        return self._state

    def is_open(self) -> bool:
        with self._lock:
            if self._state == CBState.OPEN:
                if self._last_fail and (datetime.now(timezone.utc) - self._last_fail).total_seconds() >= self._timeout:
                    self._state = CBState.HALF_OPEN
                    log.info("[CB] %s → HALF_OPEN", self.name)
                    return False
                return True
            return False

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        if self.is_open():
            raise CircuitOpenError(f"Circuit {self.name} OPEN — Benner indisponível")
        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self):
        with self._lock:
            self._failures = 0
            if self._state != CBState.CLOSED:
                log.info("[CB] %s → CLOSED", self.name)
            self._state = CBState.CLOSED

    def _on_failure(self):
        with self._lock:
            self._failures += 1
            self._last_fail = datetime.now(timezone.utc)
            if self._failures >= self._threshold:
                if self._state != CBState.OPEN:
                    log.error("[CB] %s → OPEN (%d falhas consecutivas)", self.name, self._failures)
                self._state = CBState.OPEN

    def metrics(self) -> dict:
        return {"name": self.name, "state": self._state.value, "consecutive_failures": self._failures}


class CircuitOpenError(Exception):
    pass


_benner_cb = CircuitBreaker("benner", failure_threshold=3, recovery_timeout_s=120)


def get_benner_circuit_breaker() -> CircuitBreaker:
    return _benner_cb


def sql_retry(fn: Callable) -> Callable:
    """Retry 3x com backoff 2s→10s + jitter para erros transitórios de SQL."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda rs: log.warning(
            "Retry %d/3 Benner SQL (erro: %s)",
            rs.attempt_number, rs.outcome.exception()
        ),
    )(fn)
