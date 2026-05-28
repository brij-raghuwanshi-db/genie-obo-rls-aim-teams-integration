"""
FastAPI direct API for Genie queries.

This module provides a REST API for programmatic access to Genie.
Deploy to: Azure App Service (dbrx-webapp-genie-obo-rls)

API versioning:
- /v1/* endpoints are the current stable API
- Legacy endpoints (without /v1) are maintained for backward compatibility
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request

from .auth import TokenCache, TokenExchangeError, exchange_aad_for_databricks_token_async
from .config import AskRequest, AskResponse, Settings
from .genie import GenieClient

app = FastAPI(
    title="Genie API OBO RLS Service",
    version="1.0.0",
    description="Databricks Genie API with user identity preservation for RLS",
)

token_cache = TokenCache()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def _extract_bearer_token(authorization: str | None) -> str:
    """Extract bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1]


# =============================================================================
# Version 1 Router
# =============================================================================

v1_router = APIRouter(prefix="/v1", tags=["v1"])


@v1_router.get("/healthz")
def healthz_v1() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0"}


@v1_router.post("/genie/ask")
async def ask_genie_v1(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """
    Query Databricks Genie with user identity preserved.

    Requires a valid Azure AD bearer token in the Authorization header.
    The token is exchanged for a Databricks token using OBO flow,
    ensuring Row-Level Security is enforced based on the user's identity.

    Uses circuit breaker and retry logic for resilience.
    """
    # Parse request body
    try:
        body = await request.json()
        payload = AskRequest(
            question=body.get("question", ""),
            conversation_id=body.get("conversation_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid request body") from e

    settings = get_settings()
    aad_token = _extract_bearer_token(authorization)

    # Use async token exchange with circuit breaker and retry
    try:
        exchanged = await exchange_aad_for_databricks_token_async(
            settings, aad_token, token_cache
        )
    except TokenExchangeError as exc:
        if "circuit open" in str(exc).lower():
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    client = GenieClient(str(settings.databricks_host), settings.genie_space_id)

    if payload.conversation_id:
        result = client.send_message(
            exchanged.access_token, payload.conversation_id, payload.question
        )
    else:
        result = client.start_conversation(exchanged.access_token, payload.question)

    response = AskResponse(
        conversation_id=result.get("conversation_id") or result.get("id"),
        message_id=result.get("message_id") or result.get("message", {}).get("id"),
        content=(result.get("message", {}) or {}).get("content"),
        raw=result,
    )
    return response.to_dict()


# Include versioned router
app.include_router(v1_router)


# =============================================================================
# Legacy Endpoints (backward compatibility)
# =============================================================================


@app.get("/healthz")
def healthz_legacy() -> dict[str, str]:
    """Health check endpoint (legacy, use /v1/healthz)."""
    return healthz_v1()


@app.post("/genie/ask")
async def ask_genie_legacy(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Query Databricks Genie (legacy, use /v1/genie/ask)."""
    return await ask_genie_v1(request, authorization)
