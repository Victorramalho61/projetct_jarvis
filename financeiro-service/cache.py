from threading import RLock

from cachetools import TTLCache

# TTLs em segundos por módulo — espelham os do voesync-financial_reconciliation original
_CACHES: dict[str, tuple[TTLCache, RLock]] = {
    "empresas":          (TTLCache(maxsize=10,  ttl=3600), RLock()),
    "dashboard":         (TTLCache(maxsize=100, ttl=3600), RLock()),
    "conciliacao":       (TTLCache(maxsize=500, ttl=600),  RLock()),
    "balanco":           (TTLCache(maxsize=500, ttl=900),  RLock()),
    "razao":             (TTLCache(maxsize=500, ttl=600),  RLock()),
    "receitas":          (TTLCache(maxsize=500, ttl=900),  RLock()),
    "despesas":          (TTLCache(maxsize=500, ttl=900),  RLock()),
    "adiantamentos":     (TTLCache(maxsize=500, ttl=600),  RLock()),
    "impostos_retidos":  (TTLCache(maxsize=500, ttl=600),  RLock()),
    "log_movimentacoes": (TTLCache(maxsize=500, ttl=300),  RLock()),
}


def cache_get(modulo: str, key: str):
    cache, lock = _CACHES[modulo]
    with lock:
        return cache.get(key)


def cache_set(modulo: str, key: str, value) -> None:
    cache, lock = _CACHES[modulo]
    with lock:
        cache[key] = value
