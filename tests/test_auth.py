"""Tests for authentication module."""

from unittest.mock import patch, MagicMock

import pytest
import requests_mock

from genie_api_obo_rls.auth import (
    TokenCache,
    TokenExchangeError,
    exchange_aad_for_databricks_token,
)
from genie_api_obo_rls.config import Settings


@pytest.fixture
def settings():
    return Settings(
        databricks_host="https://test.databricks.com",
        genie_space_id="space-1",
        account_id="test-account-id",
        token_exchange_url="https://accounts.azuredatabricks.net/oidc/accounts/test-account-id/v1/token",
        token_scope="all-apis",
    )


class TestTokenCache:
    def test_get_nonexistent(self):
        cache = TokenCache()
        assert cache.get("nonexistent") is None

    def test_set_and_get(self):
        cache = TokenCache()
        cache.set("key", "token-value", expires_in_seconds=3600)
        assert cache.get("key") == "token-value"

    def test_expired_token_removed(self):
        cache = TokenCache()
        cache.set("key", "token-value", expires_in_seconds=1)
        # Token with only 1 second TTL should be considered expired (min_ttl=30)
        assert cache.get("key", min_ttl_seconds=30) is None


class TestTokenExchange:
    def test_exchange_success(self, settings):
        cache = TokenCache()

        with requests_mock.Mocker() as m:
            m.post(
                str(settings.token_exchange_url),
                json={"access_token": "dbx-token", "expires_in": 3600},
            )
            result = exchange_aad_for_databricks_token(settings, "aad-token", cache)

        assert result.access_token == "dbx-token"
        assert result.expires_in == 3600

    def test_exchange_caches_result(self, settings):
        cache = TokenCache()

        with requests_mock.Mocker() as m:
            m.post(
                str(settings.token_exchange_url),
                json={"access_token": "dbx-token", "expires_in": 3600},
            )
            first = exchange_aad_for_databricks_token(settings, "aad-token", cache)
            second = exchange_aad_for_databricks_token(settings, "aad-token", cache)

        assert first.access_token == second.access_token
        assert m.call_count == 1  # Only called once due to caching

    def test_exchange_failure(self, settings):
        cache = TokenCache()

        with requests_mock.Mocker() as m:
            m.post(str(settings.token_exchange_url), status_code=400, text="Bad Request")

            with pytest.raises(TokenExchangeError) as exc_info:
                exchange_aad_for_databricks_token(settings, "bad-token", cache)

            assert "400" in str(exc_info.value)
