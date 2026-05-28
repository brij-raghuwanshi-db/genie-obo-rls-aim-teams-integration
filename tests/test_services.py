"""Tests for optional services (Key Vault, Telemetry)."""

import logging
import os
from unittest.mock import patch, MagicMock

from genie_api_obo_rls.services import (
    KeyVaultSecretProvider,
    TelemetryClient,
)


class TestKeyVaultSecretProvider:
    def test_not_configured(self):
        """Test provider when not configured."""
        provider = KeyVaultSecretProvider(vault_url=None)
        assert not provider.is_configured
        assert provider.get_secret("test") is None
        assert provider.get_secret("test", "default") == "default"

    def test_get_secret_or_env_fallback(self):
        """Test fallback to environment variable."""
        provider = KeyVaultSecretProvider(vault_url=None)
        os.environ["TEST_SECRET_VAR"] = "from-env"
        try:
            result = provider.get_secret_or_env("test-secret", "TEST_SECRET_VAR", "default")
            assert result == "from-env"
        finally:
            del os.environ["TEST_SECRET_VAR"]

    def test_get_secret_or_env_default(self):
        """Test default value when nothing available."""
        provider = KeyVaultSecretProvider(vault_url=None)
        os.environ.pop("NONEXISTENT_VAR", None)
        result = provider.get_secret_or_env("test", "NONEXISTENT_VAR", "my-default")
        assert result == "my-default"


class TestTelemetryClient:
    def test_not_configured(self):
        """Test client when not configured."""
        client = TelemetryClient(connection_string=None)
        assert not client.is_configured

    def test_get_logger_fallback(self):
        """Test logger fallback when not configured."""
        client = TelemetryClient(connection_string=None)
        logger = client.get_logger()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "genie_api_obo_rls"

    def test_track_event_no_error(self):
        """Test tracking event doesn't raise when not configured."""
        client = TelemetryClient(connection_string=None)
        client.track_event("TestEvent", {"key": "value"})  # Should not raise

    def test_track_exception_no_error(self):
        """Test tracking exception doesn't raise when not configured."""
        client = TelemetryClient(connection_string=None)
        try:
            raise ValueError("test")
        except Exception as e:
            client.track_exception(e, {"context": "test"})  # Should not raise
