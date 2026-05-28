"""
Configuration module for Genie API OBO RLS.

Uses dataclasses instead of Pydantic for broader compatibility.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any


def _get_env(name: str, default: str = "", required: bool = False) -> str:
    """Get environment variable with optional default and required check."""
    value = os.environ.get(name, default)
    if required and not value:
        raise ValueError(f"Required environment variable {name} is not set")
    return value


# Input validation constants
MAX_QUESTION_LENGTH = 4000
FORBIDDEN_PATTERNS = [
    r';\s*DROP\s+',
    r';\s*DELETE\s+',
    r';\s*UPDATE\s+',
    r';\s*INSERT\s+',
    r'<script',
    r'javascript:',
]


@dataclass
class Settings:
    """
    Genie API configuration settings.
    
    Loads from environment variables with sensible defaults.
    """
    databricks_host: str = field(
        default_factory=lambda: _get_env("GENIE_DATABRICKS_HOST", required=True)
    )
    genie_space_id: str = field(
        default_factory=lambda: _get_env("GENIE_GENIE_SPACE_ID", required=True)
    )
    account_id: str = field(
        default_factory=lambda: _get_env("DATABRICKS_ACCOUNT_ID", required=True)
    )
    token_exchange_url: str = field(
        default_factory=lambda: _get_env("GENIE_TOKEN_EXCHANGE_URL", "")
    )
    token_scope: str = field(
        default_factory=lambda: _get_env("GENIE_TOKEN_SCOPE", "all-apis")
    )
    token_audience: str = field(
        default_factory=lambda: _get_env("GENIE_TOKEN_AUDIENCE", "")
    )
    cache_ttl_seconds: int = field(
        default_factory=lambda: int(_get_env("GENIE_CACHE_TTL_SECONDS", "300"))
    )

    def get_account_token_exchange_url(self) -> str:
        """
        Get the account-level token exchange URL.
        
        If token_exchange_url is set, use it. Otherwise, construct from account_id.
        """
        if self.token_exchange_url:
            return self.token_exchange_url
        return f"https://accounts.azuredatabricks.net/oidc/accounts/{self.account_id}/v1/token"


@dataclass
class BotSettings:
    """Bot Framework configuration settings."""
    microsoft_app_id: str = field(
        default_factory=lambda: _get_env("MICROSOFT_APP_ID", "")
    )
    microsoft_app_password: str = field(
        default_factory=lambda: _get_env("MICROSOFT_APP_PASSWORD", "")
    )
    microsoft_app_tenant_id: str = field(
        default_factory=lambda: _get_env("MICROSOFT_APP_TENANT_ID", "")
    )
    oauth_connection_name: str = field(
        default_factory=lambda: _get_env("OAUTH_CONNECTION_NAME", "databricks-sso")
    )


@dataclass
class AskRequest:
    """Request model for /genie/ask endpoint with validation."""
    question: str
    conversation_id: str | None = None

    def __post_init__(self) -> None:
        """Validate and sanitize request."""
        if not self.question:
            raise ValueError("question is required")

        self.question = self.question.strip()
        if not self.question:
            raise ValueError("question cannot be empty")

        if len(self.question) > MAX_QUESTION_LENGTH:
            raise ValueError(f"question exceeds maximum length of {MAX_QUESTION_LENGTH}")

        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, self.question, re.IGNORECASE):
                raise ValueError("question contains potentially unsafe content")

        if self.conversation_id is not None:
            self.conversation_id = self.conversation_id.strip()
            if self.conversation_id and not re.match(r'^[a-zA-Z0-9_-]+$', self.conversation_id):
                raise ValueError("conversation_id contains invalid characters")


@dataclass
class AskResponse:
    """Response model for /genie/ask endpoint."""
    conversation_id: str | None = None
    message_id: str | None = None
    content: str | None = None
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "content": self.content,
            "raw": self.raw,
        }
