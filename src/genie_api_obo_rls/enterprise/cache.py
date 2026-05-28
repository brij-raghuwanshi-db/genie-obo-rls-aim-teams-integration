"""
Token caching with pluggable backends.

Default implementation uses in-memory storage (single instance only).
For multi-instance deployments, use RedisCache from cache_redis.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Callable


@dataclass
class CachedToken:
    """Cached token with metadata."""
    access_token: str
    expires_at: datetime
    refresh_token: str | None = None


class CacheInterface(ABC):
    """Abstract interface for token caching."""

    @abstractmethod
    def get(self, key: str, min_ttl_seconds: int = 30) -> str | None:
        """Get a cached token if valid."""
        pass

    @abstractmethod
    def set(
        self,
        key: str,
        access_token: str,
        expires_in_seconds: int,
        refresh_token: str | None = None,
    ) -> None:
        """Cache a token."""
        pass

    @abstractmethod
    def revoke(self, key: str) -> bool:
        """Revoke a specific token."""
        pass

    @abstractmethod
    def revoke_all(self) -> int:
        """Revoke all tokens. Returns count."""
        pass


class MemoryCache(CacheInterface):
    """
    Thread-safe in-memory token cache.
    
    NOTE: This cache is per-process only. In multi-instance deployments,
    each instance has its own cache. Use RedisCache for shared caching.
    """

    def __init__(self) -> None:
        self._store: dict[str, CachedToken] = {}
        self._lock = Lock()

    def get(self, key: str, min_ttl_seconds: int = 30) -> str | None:
        """Get a cached token if it exists and has sufficient TTL."""
        now = datetime.now(timezone.utc)
        with self._lock:
            cached = self._store.get(key)
            if not cached:
                return None
            if cached.expires_at <= now + timedelta(seconds=min_ttl_seconds):
                return None
            return cached.access_token

    def set(
        self,
        key: str,
        access_token: str,
        expires_in_seconds: int,
        refresh_token: str | None = None,
    ) -> None:
        """Cache a token with expiration."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        with self._lock:
            self._store[key] = CachedToken(
                access_token=access_token,
                expires_at=expires_at,
                refresh_token=refresh_token,
            )

    def get_or_refresh(
        self,
        key: str,
        refresh_fn: Callable[[str], tuple[str, int]] | None = None,
        min_ttl_seconds: int = 60,
    ) -> str | None:
        """
        Get token, attempting refresh if near expiry.

        Args:
            key: Cache key
            refresh_fn: Function that takes refresh_token and returns (access_token, expires_in)
            min_ttl_seconds: Minimum remaining TTL before attempting refresh

        Returns:
            Access token or None if not available
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            cached = self._store.get(key)
            if not cached:
                return None

            time_remaining = (cached.expires_at - now).total_seconds()

            if time_remaining > min_ttl_seconds:
                return cached.access_token

            if cached.refresh_token and refresh_fn and time_remaining > 0:
                try:
                    new_access_token, new_expires_in = refresh_fn(cached.refresh_token)
                    self._store[key] = CachedToken(
                        access_token=new_access_token,
                        expires_at=now + timedelta(seconds=new_expires_in),
                        refresh_token=cached.refresh_token,
                    )
                    return new_access_token
                except Exception:
                    if time_remaining > 0:
                        return cached.access_token
                    return None

            if time_remaining <= 0:
                del self._store[key]
                return None

            return cached.access_token

    def revoke(self, key: str) -> bool:
        """Revoke a specific cached token."""
        with self._lock:
            return self._store.pop(key, None) is not None

    def revoke_all(self) -> int:
        """Revoke all cached tokens. Returns count revoked."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def cleanup_expired(self) -> int:
        """Remove all expired tokens. Returns count removed."""
        now = datetime.now(timezone.utc)
        with self._lock:
            expired_keys = [k for k, v in self._store.items() if v.expires_at <= now]
            for k in expired_keys:
                del self._store[k]
            return len(expired_keys)

    def __len__(self) -> int:
        """Return the number of cached tokens."""
        with self._lock:
            return len(self._store)


# Default cache implementation - alias for backward compatibility
TokenCache = MemoryCache
