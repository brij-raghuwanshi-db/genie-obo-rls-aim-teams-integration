"""
Optional Azure services: Key Vault and Application Insights.

These integrations are optional and gracefully degrade if not configured.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

# =============================================================================
# Azure Key Vault
# =============================================================================

try:
    from azure.core.exceptions import AzureError
    from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
    from azure.keyvault.secrets import SecretClient
    KEYVAULT_AVAILABLE = True
except ImportError:
    KEYVAULT_AVAILABLE = False


class KeyVaultSecretProvider:
    """Provides secrets from Azure Key Vault with fallback to env vars."""

    def __init__(self, vault_url: str | None = None):
        self._vault_url = vault_url or os.environ.get("AZURE_KEYVAULT_URL")
        self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(self._vault_url) and KEYVAULT_AVAILABLE

    def _get_client(self):
        if self._client is None and self.is_configured:
            try:
                credential = ManagedIdentityCredential()
            except Exception:
                credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=self._vault_url, credential=credential)
        return self._client

    def get_secret(self, name: str, default: str | None = None) -> str | None:
        if not self.is_configured:
            return default
        try:
            return self._get_client().get_secret(name).value
        except Exception:
            return default

    def get_secret_or_env(self, secret_name: str, env_var: str, default: str | None = None) -> str | None:
        if self.is_configured:
            value = self.get_secret(secret_name)
            if value:
                return value
        return os.environ.get(env_var, default)


@lru_cache(maxsize=1)
def get_keyvault_provider() -> KeyVaultSecretProvider:
    return KeyVaultSecretProvider()


# Secret name mappings: Key Vault name -> environment variable
SECRET_MAPPINGS = {
    "genie-databricks-host": "GENIE_DATABRICKS_HOST",
    "genie-space-id": "GENIE_GENIE_SPACE_ID",
    "genie-token-exchange-url": "GENIE_TOKEN_EXCHANGE_URL",
    "microsoft-app-id": "MICROSOFT_APP_ID",
    "microsoft-app-password": "MICROSOFT_APP_PASSWORD",
}


def apply_keyvault_secrets_to_env(provider: KeyVaultSecretProvider | None = None) -> int:
    """Load secrets from Key Vault into environment variables. Returns count loaded."""
    if provider is None:
        provider = get_keyvault_provider()
    if not provider.is_configured:
        return 0

    count = 0
    for kv_name, env_name in SECRET_MAPPINGS.items():
        value = provider.get_secret(kv_name)
        if value:
            os.environ[env_name] = value
            count += 1
    return count


# =============================================================================
# Application Insights Telemetry
# =============================================================================

try:
    from opencensus.ext.azure.log_exporter import AzureLogHandler
    from opencensus.ext.azure.trace_exporter import AzureExporter
    from opencensus.trace import config_integration
    from opencensus.trace.samplers import ProbabilitySampler
    from opencensus.trace.tracer import Tracer
    OPENCENSUS_AVAILABLE = True
except ImportError:
    OPENCENSUS_AVAILABLE = False


class TelemetryClient:
    """Application Insights telemetry with graceful fallback to standard logging."""

    def __init__(self, connection_string: str | None = None):
        self._connection_string = connection_string or os.environ.get(
            "APPLICATIONINSIGHTS_CONNECTION_STRING"
        )
        self._logger: logging.Logger | None = None
        self._tracer: Any = None
        self._initialized = False

    @property
    def is_configured(self) -> bool:
        return bool(self._connection_string) and OPENCENSUS_AVAILABLE

    def initialize(self) -> bool:
        if self._initialized:
            return self.is_configured
        self._initialized = True

        if not self.is_configured:
            return False

        try:
            self._logger = logging.getLogger("genie_api_obo_rls")
            self._logger.setLevel(logging.INFO)
            self._logger.addHandler(AzureLogHandler(connection_string=self._connection_string))

            config_integration.trace_integrations(["requests"])
            self._tracer = Tracer(
                exporter=AzureExporter(connection_string=self._connection_string),
                sampler=ProbabilitySampler(rate=1.0),
            )
            return True
        except Exception as e:
            logging.warning(f"Failed to initialize Application Insights: {e}")
            return False

    def get_logger(self) -> logging.Logger:
        if not self._initialized:
            self.initialize()
        return self._logger or logging.getLogger("genie_api_obo_rls")

    def track_event(self, name: str, properties: dict[str, str] | None = None) -> None:
        extra = {"custom_dimensions": properties} if properties else {}
        self.get_logger().info(f"Event: {name}", extra=extra)

    def track_exception(self, exception: Exception, properties: dict[str, str] | None = None) -> None:
        extra = {"custom_dimensions": properties} if properties else {}
        self.get_logger().exception(f"Exception: {exception}", extra=extra)


@lru_cache(maxsize=1)
def get_telemetry_client() -> TelemetryClient:
    client = TelemetryClient()
    client.initialize()
    return client


def track_event(name: str, properties: dict[str, str] | None = None) -> None:
    get_telemetry_client().track_event(name, properties)


def track_exception(exception: Exception, properties: dict[str, str] | None = None) -> None:
    get_telemetry_client().track_exception(exception, properties)


def get_logger() -> logging.Logger:
    return get_telemetry_client().get_logger()
