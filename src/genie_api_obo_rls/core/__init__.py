"""
Core module - Reusable components for Databricks Genie with user identity.

This module contains the essential components that can be used independently:
- Token exchange (OBO flow for user identity preservation)
- Genie client (API wrapper with conversation management)
- Configuration (settings and validation)
"""

from .token_exchange import (
    exchange_token,
    exchange_token_async,
    TokenExchangeError,
    TokenExchangeResult,
)
from .genie_client import GenieClient
from .config import Settings, BotSettings, AskRequest, AskResponse

__all__ = [
    # Token exchange
    "exchange_token",
    "exchange_token_async",
    "TokenExchangeError",
    "TokenExchangeResult",
    # Genie client
    "GenieClient",
    # Configuration
    "Settings",
    "BotSettings",
    "AskRequest",
    "AskResponse",
]
