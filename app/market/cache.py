"""Shared TTL cache for market data.

Keeps Finnhub responses in memory for a configurable duration so that:
  1. Multiple requests hitting the same tickers don't fan out into redundant API calls.
  2. The chatbot reads from cache (never makes a live Finnhub call mid-conversation).
  3. Rate-limit headroom stays well within Finnhub's free-tier 60 calls/min.

Thread-safe via a simple lock.
"""

import time
import threading
from typing import Any, Optional


class TTLCache:
    """Minimal thread-safe in-memory cache with per-key TTL expiry."""

    def __init__(self, default_ttl: int = 90):
        """
        Args:
            default_ttl: Time-to-live in seconds for cached entries. 90s balances
                         freshness vs. rate-limit conservation for Finnhub free tier.
        """
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, expiry_ts)
        self._lock = threading.Lock()
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if present and not expired, else None."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if time.time() > expiry:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value with the given TTL (or default)."""
        with self._lock:
            expiry = time.time() + (ttl if ttl is not None else self._default_ttl)
            self._store[key] = (value, expiry)

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Flush the entire cache."""
        with self._lock:
            self._store.clear()

    def stats(self) -> dict:
        """Return basic cache statistics for debugging."""
        with self._lock:
            now = time.time()
            total = len(self._store)
            alive = sum(1 for _, (__, exp) in self._store.items() if exp > now)
            return {"total_keys": total, "alive_keys": alive, "expired_keys": total - alive}


# Singleton cache shared across the app (market data layer + chat context builder)
market_cache = TTLCache(default_ttl=90)
