"""
Configuration and models for Genie API OBO RLS service.

This module contains all configuration classes and data models.
Uses standard Python dataclasses instead of pydantic for broader compatibility.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any


def _get_env(key: str, default: str = "", required: bool = False) -> str:
    """Get environment variable with optional default."""
    value = os.environ.get(key, default)
    if required and not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value


def _get_env_int(key: str, default: int) -> int:
    """Get environment variable as integer."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# =============================================================================
# Genie API Configuration
# =============================================================================

@dataclass
class Settings:
    """Configuration for Databricks Genie API integration.
    
    Loads from environment variables with GENIE_ prefix.
    
    IMPORTANT: As of Jan 24, 2026, we use ACCOUNT-LEVEL token federation
    instead of Service Principal federation. This preserves user identity
    for Unity Catalog Row-Level Security (RLS).
    
    Key change: Token exchange uses account endpoint WITHOUT client_id.
    """
    
    databricks_host: str = field(default_factory=lambda: _get_env("GENIE_DATABRICKS_HOST", required=True))
    genie_space_id: str = field(default_factory=lambda: _get_env("GENIE_GENIE_SPACE_ID", required=True))
    
    # ==========================================================================
    # ACCOUNT-LEVEL TOKEN FEDERATION (for USER identity preservation)
    # ==========================================================================
    # Databricks Account ID - REQUIRED for account-level token exchange
    # This enables user identity passthrough (vs SP identity with workspace endpoint)
    account_id: str = field(default_factory=lambda: _get_env("DATABRICKS_ACCOUNT_ID", required=True))
    
    # Token exchange URL - can be overridden, but defaults to account-level endpoint
    # Format: https://accounts.azuredatabricks.net/oidc/accounts/{account_id}/v1/token
    token_exchange_url: str = field(default_factory=lambda: _get_env("GENIE_TOKEN_EXCHANGE_URL", ""))
    
    # Token configuration
    token_scope: str = field(default_factory=lambda: _get_env("GENIE_TOKEN_SCOPE", ""))
    token_audience: str = field(default_factory=lambda: _get_env("GENIE_TOKEN_AUDIENCE", ""))
    cache_ttl_seconds: int = field(default_factory=lambda: _get_env_int("GENIE_CACHE_TTL_SECONDS", 300))

    # Multi-space configuration
    # Mapping of "Friendly Name" -> "Space ID"
    genie_spaces: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        if not self.databricks_host:
            raise ValueError("GENIE_DATABRICKS_HOST is required")
        
        # Parse GENIE_SPACES if present
        spaces_json = _get_env("GENIE_SPACES", "")
        if spaces_json:
            try:
                import json
                self.genie_spaces = json.loads(spaces_json)
            except Exception as e:
                print(f"Error parsing GENIE_SPACES: {e}")
                # Fallback to empty, will be populated below if single ID exists
        
        # Backward compatibility: Ensure at least one space exists from legacy env var
        if not self.genie_spaces and self.genie_space_id:
            self.genie_spaces = {"Default": self.genie_space_id}
            
        if not self.genie_spaces:
            raise ValueError("At least one Genie Space must be configured (via GENIE_SPACES or GENIE_GENIE_SPACE_ID)")
            
        if not self.account_id:
            raise ValueError("DATABRICKS_ACCOUNT_ID is required for account-level token federation")
        # Ensure cache TTL is within reasonable bounds
        self.cache_ttl_seconds = max(30, min(3600, self.cache_ttl_seconds))
    
    def get_account_token_exchange_url(self) -> str:
        """
        Get the account-level token exchange URL.
        
        If GENIE_TOKEN_EXCHANGE_URL is set and contains 'accounts.azuredatabricks.net',
        use it. Otherwise, construct from account_id.
        
        Returns:
            Account-level token exchange URL for user identity preservation
        """
        if self.token_exchange_url and "accounts.azuredatabricks.net" in self.token_exchange_url:
            return self.token_exchange_url
        # Construct account-level URL
        return f"https://accounts.azuredatabricks.net/oidc/accounts/{self.account_id}/v1/token"


# =============================================================================
# Bot Framework Configuration
# =============================================================================

@dataclass
class BotSettings:
    """Configuration for Azure Bot Service integration.
    
    Loads from environment variables.
    """
    
    microsoft_app_id: str = field(default_factory=lambda: _get_env("MICROSOFT_APP_ID", ""))
    microsoft_app_password: str = field(default_factory=lambda: _get_env("MICROSOFT_APP_PASSWORD", ""))
    microsoft_app_tenant_id: str = field(default_factory=lambda: _get_env("MICROSOFT_APP_TENANT_ID", ""))
    oauth_connection_name: str = field(default_factory=lambda: _get_env("OAUTH_CONNECTION_NAME", "databricks-sso"))
    app_service_url: str = field(default_factory=lambda: _get_env("APP_SERVICE_URL", ""))


# =============================================================================
# API Request/Response Models
# =============================================================================

# Input validation constants
MAX_QUESTION_LENGTH = 4000
FORBIDDEN_PATTERNS = [
    r';\s*DROP\s+',      # SQL injection
    r';\s*DELETE\s+',    # SQL injection
    r';\s*UPDATE\s+',    # SQL injection
    r';\s*INSERT\s+',    # SQL injection
    r'<script',          # XSS
    r'javascript:',      # XSS
]


@dataclass
class AskRequest:
    """Request model for /genie/ask endpoint with validation."""
    question: str
    conversation_id: str | None = None

    def __post_init__(self) -> None:
        """Validate and sanitize request."""
        # Required field check
        if not self.question:
            raise ValueError("question is required")
        
        # Strip whitespace
        self.question = self.question.strip()
        
        if not self.question:
            raise ValueError("question cannot be empty")
        
        # Length check
        if len(self.question) > MAX_QUESTION_LENGTH:
            raise ValueError(f"question exceeds maximum length of {MAX_QUESTION_LENGTH} characters")
        
        # Forbidden pattern check
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, self.question, re.IGNORECASE):
                raise ValueError("question contains potentially unsafe content")
        
        # Validate conversation_id format if provided
        if self.conversation_id is not None:
            self.conversation_id = self.conversation_id.strip()
            if self.conversation_id and not re.match(r'^[a-zA-Z0-9_-]+$', self.conversation_id):
                raise ValueError("conversation_id contains invalid characters")


@dataclass
class AskResponse:
    """Response model for /genie/ask endpoint."""
    conversation_id: str | None
    message_id: str | None
    content: str | None
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "content": self.content,
            "raw": self.raw,
        }
