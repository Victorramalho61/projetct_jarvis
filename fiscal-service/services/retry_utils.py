import time
import logging
import requests

_logger = logging.getLogger(__name__)

_TRANSIENT_ERRORS = (
    requests.Timeout,
    requests.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
)


def with_backoff(fn, max_attempts: int = 3, base_delay: float = 5.0):
    """
    Retenta fn() para erros de rede transientes com espera exponencial: 5s → 10s → 20s.
    NÃO aplicar a erros de autenticação (401/403) ou cStat 656 — falha rápida é correta nesses casos.
    """
    for attempt in range(max_attempts):
        try:
            return fn()
        except _TRANSIENT_ERRORS as exc:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)
            _logger.warning(
                "Tentativa %d/%d falhou (%s: %s). Retry em %.0fs...",
                attempt + 1,
                max_attempts,
                type(exc).__name__,
                exc,
                delay,
            )
            time.sleep(delay)
