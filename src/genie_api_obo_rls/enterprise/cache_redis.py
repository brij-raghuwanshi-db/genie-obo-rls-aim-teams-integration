"""
Redis-based token cache for multi-instance deployments.

This implementation shares token cache across all app instances,
enabling proper scaling without token re-exchange on every request.

USAGE:
    from genie_api_obo_rls.enterprise.cache_redis import RedisCache
    
    cache = RedisCache("redis://localhost:6379/0")
    cache.set("user_token_hash", "db_access_token", expires_in_seconds=3600)
    
REQUIREMENTS:
    pip install redis

ENVIRONMENT VARIABLES:
    REDIS_URL=redis://localhost:6379/0
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from .cache import CacheInterface


class RedisCache(CacheInterface):
    """
    Redis-based token cache for multi-instance deployments.
    
    Tokens are stored as JSON with expiration set via Redis TTL.
    This ensures tokens expire even if the app doesn't clean up.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        key_prefix: str = "genie:token:",
    ) -> None:
        """
        Initialize Redis cache.
        
        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
            key_prefix: Prefix for all cache keys
        """
        try:
            import redis
        except ImportError:
            raise ImportError("redis package required: pip install redis")
        
        url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._client = redis.from_url(url, decode_responses=True)
        self._prefix = key_prefix

    def _key(self, key: str) -> str:
        """Generate prefixed Redis key."""
        return f"{self._prefix}{key}"

    def get(self, key: str, min_ttl_seconds: int = 30) -> str | None:
        """
        Get a cached token if it exists and has sufficient TTL.
        
        Args:
            key: Cache key
            min_ttl_seconds: Minimum remaining TTL required
        
        Returns:
            Access token or None
        """
        redis_key = self._key(key)
        
        # Check TTL first
        ttl = self._client.ttl(redis_key)
        if ttl < min_ttl_seconds:
            return None
        
        # Get the value
        data = self._client.get(redis_key)
        if not data:
            return None
        
        try:
            parsed = json.loads(data)
            return parsed.get("access_token")
        except json.JSONDecodeError:
            return None

    def set(
        self,
        key: str,
        access_token: str,
        expires_in_seconds: int,
        refresh_token: str | None = None,
    ) -> None:
        """
        Cache a token with expiration.
        
        Args:
            key: Cache key
            access_token: The token to cache
            expires_in_seconds: Token lifetime
            refresh_token: Optional refresh token
        """
        redis_key = self._key(key)
        
        data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Use Redis TTL for expiration
        self._client.setex(
            redis_key,
            expires_in_seconds,
            json.dumps(data),
        )

    def get_with_refresh_token(self, key: str) -> tuple[str | None, str | None]:
        """
        Get both access token and refresh token.
        
        Returns:
            Tuple of (access_token, refresh_token), either may be None
        """
        redis_key = self._key(key)
        data = self._client.get(redis_key)
        
        if not data:
            return None, None
        
        try:
            parsed = json.loads(data)
            return parsed.get("access_token"), parsed.get("refresh_token")
        except json.JSONDecodeError:
            return None, None

    def revoke(self, key: str) -> bool:
        """
        Revoke a specific cached token.
        
        Returns:
            True if token was revoked, False if not found
        """
        redis_key = self._key(key)
        return self._client.delete(redis_key) > 0

    def revoke_all(self) -> int:
        """
        Revoke all cached tokens.
        
        Returns:
            Number of tokens revoked
        """
        pattern = f"{self._prefix}*"
        keys = self._client.keys(pattern)
        if not keys:
            return 0
        return self._client.delete(*keys)

    def cleanup_expired(self) -> int:
        """
        Remove expired tokens.
        
        Note: Redis handles expiration automatically via TTL,
        so this method always returns 0 for Redis.
        """
        return 0  # Redis handles expiration automatically

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache stats (count, memory, etc.)
        """
        pattern = f"{self._prefix}*"
        keys = self._client.keys(pattern)
        return {
            "count": len(keys),
            "prefix": self._prefix,
            "keys": keys[:10],  # First 10 keys for debugging
        }

    def ping(self) -> bool:
        """
        Check Redis connectivity.
        
        Returns:
            True if Redis is reachable
        """
        try:
            return self._client.ping()
        except Exception:
            return False
