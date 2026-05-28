"""
Token Exchange - The core innovation for user identity preservation.

This module implements the ACCOUNT-LEVEL token federation that preserves
user identity when exchanging Azure AD tokens for Databricks tokens.

The key insight: By NOT including client_id in the token exchange request,
Databricks issues a token for THE USER, not a service principal.

How identity flows:
1. The entire Azure AD JWT is sent (contains oid, email, and other claims)
2. Databricks uses the 'oid' claim to MATCH the user (via AIM - Automatic Identity Mgmt)
3. current_user() in SQL returns the user's EMAIL (for RLS filters)

This enables Row-Level Security (RLS) based on current_user() in Unity Catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from .config import Settings


class TokenExchangeError(RuntimeError):
    """Raised when token exchange fails."""
    pass


@dataclass(frozen=True)
class TokenExchangeResult:
    """Result of a successful token exchange."""
    access_token: str
    expires_in: int
    refresh_token: str | None = None


def get_account_token_url(account_id: str) -> str:
    """
    Construct the account-level token exchange URL.
    
    Args:
        account_id: Databricks Account ID
    
    Returns:
        Token exchange URL
    """
    return f"https://accounts.azuredatabricks.net/oidc/accounts/{account_id}/v1/token"


def exchange_token(
    aad_token: str,
    account_id: str,
    scope: str = "all-apis",
    audience: str | None = None,
    timeout: int = 30,
) -> TokenExchangeResult:
    """
    Exchange Azure AD token for Databricks token using Account-Level Federation.
    
    THIS IS THE USP: No client_id means the token is for THE USER.
    
    Args:
        aad_token: Azure AD access token (JWT) for the user
        account_id: Databricks Account ID
        scope: Token scope (default: "all-apis")
        audience: Optional audience parameter
        timeout: Request timeout in seconds
    
    Returns:
        TokenExchangeResult with Databricks token
    
    Raises:
        TokenExchangeError: If exchange fails
    """
    url = get_account_token_url(account_id)
    
    # CRITICAL: No client_id = USER identity preserved
    data: dict[str, Any] = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": aad_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "scope": scope,
    }
    
    if audience:
        data["audience"] = audience
    
    try:
        response = requests.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        raise TokenExchangeError("Token exchange timed out")
    except requests.exceptions.ConnectionError as e:
        raise TokenExchangeError(f"Connection failed: {e}")
    except Exception as e:
        raise TokenExchangeError(f"Request failed: {e}")
    
    if response.status_code >= 400:
        raise TokenExchangeError(f"Exchange failed: {response.status_code} - {response.text}")
    
    payload = response.json()
    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    refresh_token = payload.get("refresh_token")
    
    if not access_token or not isinstance(expires_in, int):
        raise TokenExchangeError("Invalid response: missing access_token or expires_in")
    
    return TokenExchangeResult(
        access_token=access_token,
        expires_in=expires_in,
        refresh_token=refresh_token,
    )


def exchange_token_with_settings(
    settings: "Settings",
    aad_token: str,
) -> TokenExchangeResult:
    """
    Exchange token using Settings object.
    
    Convenience function that extracts parameters from Settings.
    
    Args:
        settings: Configuration settings
        aad_token: Azure AD access token
    
    Returns:
        TokenExchangeResult
    """
    return exchange_token(
        aad_token=aad_token,
        account_id=settings.account_id,
        scope=settings.token_scope or "all-apis",
        audience=settings.token_audience or None,
    )


# =============================================================================
# Async version (optional - requires httpx)
# =============================================================================

async def exchange_token_async(
    aad_token: str,
    account_id: str,
    scope: str = "all-apis",
    audience: str | None = None,
    timeout: float = 30.0,
) -> TokenExchangeResult:
    """
    Async version of token exchange using httpx.
    
    Args:
        aad_token: Azure AD access token
        account_id: Databricks Account ID
        scope: Token scope
        audience: Optional audience
        timeout: Request timeout
    
    Returns:
        TokenExchangeResult
    
    Raises:
        TokenExchangeError: If exchange fails
    """
    try:
        import httpx
    except ImportError:
        raise TokenExchangeError("httpx required for async token exchange: pip install httpx")
    
    url = get_account_token_url(account_id)
    
    data: dict[str, Any] = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": aad_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "scope": scope,
    }
    
    if audience:
        data["audience"] = audience
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=timeout,
            )
            response.raise_for_status()
    except httpx.TimeoutException:
        raise TokenExchangeError("Token exchange timed out")
    except httpx.ConnectError as e:
        raise TokenExchangeError(f"Connection failed: {e}")
    except httpx.HTTPStatusError as e:
        raise TokenExchangeError(f"Exchange failed: {e.response.status_code}")
    except Exception as e:
        raise TokenExchangeError(f"Request failed: {e}")
    
    payload = response.json()
    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    refresh_token = payload.get("refresh_token")
    
    if not access_token or not isinstance(expires_in, int):
        raise TokenExchangeError("Invalid response")
    
    return TokenExchangeResult(
        access_token=access_token,
        expires_in=expires_in,
        refresh_token=refresh_token,
    )
