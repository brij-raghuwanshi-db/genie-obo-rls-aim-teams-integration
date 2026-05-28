"""
Authentication module for OBO token exchange and Teams SSO.

This module handles:
- Token caching (in-memory, thread-safe)
- AAD to Databricks token exchange (OBO flow)
- Teams SSO token acquisition via Bot Framework
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import TYPE_CHECKING, Any

import httpx
import requests
from botbuilder.core import TurnContext
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from botbuilder.dialogs import (
    ComponentDialog,
    DialogTurnResult,
    WaterfallDialog,
    WaterfallStepContext,
)
from botbuilder.dialogs.prompts import OAuthPrompt, OAuthPromptSettings

if TYPE_CHECKING:
    from .config import BotSettings, Settings


# =============================================================================
# Token Cache
# =============================================================================

@dataclass
class CachedToken:
    """Cached token with optional refresh capability."""
    access_token: str
    expires_at: datetime
    refresh_token: str | None = None


class TokenCache:
    """Thread-safe token cache with refresh and revocation support."""

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
                # Token expired or expiring soon
                return None
            return cached.access_token

    def set(
        self,
        key: str,
        access_token: str,
        expires_in_seconds: int,
        refresh_token: str | None = None,
    ) -> None:
        """Cache a token with expiration and optional refresh token."""
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
        refresh_fn: Any = None,
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

            # Token still valid with comfortable buffer
            if time_remaining > min_ttl_seconds:
                return cached.access_token

            # Try to refresh if we have refresh token and function
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
                    # Refresh failed, return current token if still valid
                    if time_remaining > 0:
                        return cached.access_token
                    return None

            # Token expired
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


# =============================================================================
# Circuit Breaker
# =============================================================================

@dataclass
class CircuitBreakerState:
    """State for circuit breaker pattern."""
    failures: int = 0
    last_failure: datetime | None = None
    is_open: bool = False


class CircuitBreaker:
    """Circuit breaker for external service calls."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout_seconds: int = 60):
        self._state = CircuitBreakerState()
        self._lock = Lock()
        self._threshold = failure_threshold
        self._recovery_timeout = timedelta(seconds=recovery_timeout_seconds)

    def is_available(self) -> bool:
        """Check if circuit is closed (available) or open (unavailable)."""
        with self._lock:
            if not self._state.is_open:
                return True
            # Check if recovery timeout has passed
            if self._state.last_failure:
                elapsed = datetime.now(timezone.utc) - self._state.last_failure
                if elapsed > self._recovery_timeout:
                    self._state.is_open = False
                    self._state.failures = 0
                    return True
            return False

    def record_failure(self) -> None:
        """Record a failure. Opens circuit if threshold reached."""
        with self._lock:
            self._state.failures += 1
            self._state.last_failure = datetime.now(timezone.utc)
            if self._state.failures >= self._threshold:
                self._state.is_open = True

    def record_success(self) -> None:
        """Record a success. Resets failure count."""
        with self._lock:
            self._state.failures = 0
            self._state.is_open = False


# Module-level circuit breaker instance for Databricks token exchange
_databricks_circuit_breaker = CircuitBreaker()


# =============================================================================
# Token Exchange (OBO Flow)
# =============================================================================

class TokenExchangeError(RuntimeError):
    """Raised when token exchange fails."""
    pass


@dataclass(frozen=True)
class TokenExchangeResult:
    """Result of a successful token exchange."""
    access_token: str
    expires_in: int


def _cache_key(user_assertion: str, scope: str, audience: str) -> str:
    """Generate a cache key from token exchange parameters."""
    raw = f"{user_assertion}:{scope}:{audience}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def exchange_aad_for_databricks_token(
    settings: "Settings",
    user_assertion: str,
    cache: TokenCache,
) -> TokenExchangeResult:
    """
    Exchange an Azure AD token for a Databricks token using ACCOUNT-LEVEL Federation.

    This uses ACCOUNT-LEVEL token federation to preserve user identity for 
    Unity Catalog Row-Level Security (RLS). The key difference from SP-level:
    
    - Account-level: NO client_id, token is for THE USER
    - SP-level: WITH client_id, token is for THE SERVICE PRINCIPAL

    The account-level Federation Policy validates the AAD token and uses the
    'oid' claim to identify the user in Databricks (via Automatic Identity Mgmt).
    Once identified, current_user() in SQL returns the user's EMAIL for RLS filters.

    Args:
        settings: Genie API settings with account_id configuration
        user_assertion: The user's Azure AD access token (JWT)
        cache: Token cache for storing exchanged tokens

    Returns:
        TokenExchangeResult with the Databricks access token (USER identity)

    Raises:
        TokenExchangeError: If the exchange fails
    """
    cache_key = _cache_key(user_assertion, settings.token_scope, settings.token_audience)
    cached = cache.get(cache_key)
    if cached:
        return TokenExchangeResult(access_token=cached, expires_in=settings.cache_ttl_seconds)

    # Get the ACCOUNT-LEVEL token exchange URL
    token_url = settings.get_account_token_exchange_url()

    # ACCOUNT-LEVEL Federation token exchange - NO client_id
    # This tells Databricks to issue token for THE USER (from oid claim)
    data: dict[str, Any] = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": user_assertion,
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "scope": settings.token_scope or "all-apis",
    }

    if settings.token_audience:
        data["audience"] = settings.token_audience

    request_headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        response = requests.post(
            token_url,
            data=data,
            headers=request_headers,
            timeout=30
        )
    except requests.exceptions.Timeout:
        raise TokenExchangeError("Token exchange request timed out after 30 seconds")
    except requests.exceptions.ConnectionError as conn_err:
        raise TokenExchangeError(f"Token exchange connection failed: {conn_err}")
    except Exception as req_err:
        raise TokenExchangeError(f"Token exchange request failed: {req_err}")

    if response.status_code >= 400:
        raise TokenExchangeError(f"Token exchange failed: {response.status_code} {response.text}")

    payload = response.json()
    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    if not access_token or not isinstance(expires_in, int):
        raise TokenExchangeError("Token exchange response missing access_token/expires_in")

    cache.set(cache_key, access_token, expires_in)
    return TokenExchangeResult(access_token=access_token, expires_in=expires_in)


# =============================================================================
# Async Token Exchange with Retry (httpx)
# =============================================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
)
async def _make_token_request_async(
    client: httpx.AsyncClient,
    url: str,
    data: dict[str, Any],
) -> httpx.Response:
    """Make token request with retry on transient failures."""
    response = await client.post(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response


async def exchange_aad_for_databricks_token_async(
    settings: "Settings",
    user_assertion: str,
    cache: TokenCache,
) -> TokenExchangeResult:
    """
    Exchange Azure AD token for Databricks token (async version).

    Uses circuit breaker and retry logic for resilience.
    This is the recommended function for async contexts (bot, async API).

    Args:
        settings: Genie API settings with account_id configuration
        user_assertion: The user's Azure AD access token (JWT)
        cache: Token cache for storing exchanged tokens

    Returns:
        TokenExchangeResult with the Databricks access token (USER identity)

    Raises:
        TokenExchangeError: If the exchange fails
    """
    # Check circuit breaker
    if not _databricks_circuit_breaker.is_available():
        raise TokenExchangeError("Service temporarily unavailable (circuit open)")

    # Check cache
    cache_key = _cache_key(user_assertion, settings.token_scope, settings.token_audience)
    cached = cache.get(cache_key)
    if cached:
        return TokenExchangeResult(access_token=cached, expires_in=settings.cache_ttl_seconds)

    # Prepare request
    token_url = settings.get_account_token_exchange_url()
    data: dict[str, Any] = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": user_assertion,
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "scope": settings.token_scope or "all-apis",
    }
    if settings.token_audience:
        data["audience"] = settings.token_audience

    # Make request with retry
    try:
        async with httpx.AsyncClient() as client:
            response = await _make_token_request_async(client, token_url, data)

        _databricks_circuit_breaker.record_success()

    except httpx.HTTPStatusError as e:
        _databricks_circuit_breaker.record_failure()
        if e.response.status_code == 401:
            raise TokenExchangeError("Authentication failed - invalid token") from e
        if e.response.status_code == 403:
            raise TokenExchangeError("Access denied") from e
        raise TokenExchangeError(f"Token exchange failed: HTTP {e.response.status_code}") from e
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        _databricks_circuit_breaker.record_failure()
        raise TokenExchangeError(f"Connection failed: {e}") from e
    except Exception as e:
        _databricks_circuit_breaker.record_failure()
        raise TokenExchangeError(f"Unexpected error: {e}") from e

    # Parse response
    payload = response.json()
    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    refresh_token = payload.get("refresh_token")  # May not be present

    if not access_token or not isinstance(expires_in, int):
        raise TokenExchangeError("Invalid token response")

    # Cache with optional refresh token
    cache.set(cache_key, access_token, expires_in, refresh_token)

    return TokenExchangeResult(access_token=access_token, expires_in=expires_in)


# =============================================================================
# Teams SSO
# =============================================================================

@dataclass
class SsoTokenResult:
    """Result of SSO token acquisition."""
    success: bool
    token: str | None = None
    user_id: str | None = None
    error: str | None = None


class TeamsSsoDialog(ComponentDialog):
    """Dialog to handle Teams SSO token acquisition."""

    def __init__(self, settings: "BotSettings", genie_settings: "Settings | None" = None):
        super().__init__(TeamsSsoDialog.__name__)
        self._connection_name = settings.oauth_connection_name

        self.add_dialog(
            OAuthPrompt(
                OAuthPrompt.__name__,
                OAuthPromptSettings(
                    connection_name=self._connection_name,
                    text="Please sign in to access Genie.",
                    title="Sign In",
                    timeout=300000,
                ),
            )
        )

        self.add_dialog(
            WaterfallDialog("SsoWaterfall", [self._prompt_step, self._login_step])
        )
        self.initial_dialog_id = "SsoWaterfall"

    async def _prompt_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        return await step_context.begin_dialog(OAuthPrompt.__name__)

    async def _login_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        token_response = step_context.result
        if token_response and token_response.token:
            step_context.context.turn_state["sso_token"] = token_response.token
            step_context.context.turn_state["sso_user_id"] = (
                step_context.context.activity.from_property.id
            )
            return await step_context.end_dialog(
                SsoTokenResult(
                    success=True,
                    token=token_response.token,
                    user_id=step_context.context.activity.from_property.id,
                )
            )
        return await step_context.end_dialog(
            SsoTokenResult(success=False, error="Failed to acquire SSO token")
        )


async def get_token_from_context(turn_context: TurnContext, connection_name: str) -> SsoTokenResult:
    """Attempt to get a token silently from the Bot Framework token store."""
    try:
        adapter = turn_context.adapter
        token_response = await adapter.get_user_token(turn_context, connection_name, None)
        if token_response and token_response.token:
            return SsoTokenResult(
                success=True,
                token=token_response.token,
                user_id=turn_context.activity.from_property.id,
            )
        return SsoTokenResult(success=False, error="No cached token - user needs to sign in")
    except Exception as e:
        return SsoTokenResult(success=False, error=str(e))


async def sign_out_user(turn_context: TurnContext, connection_name: str) -> bool:
    """Sign out the user by clearing their cached tokens."""
    try:
        await turn_context.adapter.sign_out_user(turn_context, connection_name)
        return True
    except Exception:
        return False
