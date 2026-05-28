"""
Genie API OBO RLS Service

Teams Bot and Direct API integration with Databricks Genie,
preserving user identity for Row-Level Security via OBO token exchange.

Package Structure:
- core/: Reusable components (token exchange, genie client, config)
- enterprise/: Production features (caching, circuit breaker)
- bot/: Teams-specific components (handlers, cards)
- visualization/: Chart generation and data export
"""

__version__ = "0.1.0"

# Legacy imports for backward compatibility
from .config import AskRequest, AskResponse, BotSettings, Settings
from .auth import TokenCache, TokenExchangeError, exchange_aad_for_databricks_token
from .genie import GenieClient
from .bot import GenieBot, create_bot_app
from .services import KeyVaultSecretProvider, TelemetryClient

# New modular structure (preferred imports)
from . import core
from . import enterprise
from . import visualization

__all__ = [
    "__version__",
    # Submodules (preferred)
    "core",
    "enterprise",
    "visualization",
    # Legacy exports (backward compatibility)
    "Settings",
    "BotSettings",
    "AskRequest",
    "AskResponse",
    "TokenCache",
    "TokenExchangeError",
    "exchange_aad_for_databricks_token",
    "GenieClient",
    "GenieBot",
    "create_bot_app",
    "KeyVaultSecretProvider",
    "TelemetryClient",
]
