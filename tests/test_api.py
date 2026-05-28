"""Tests for the FastAPI endpoints."""

from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from genie_api_obo_rls.api import app
from genie_api_obo_rls.config import Settings
from genie_api_obo_rls.auth import TokenExchangeResult


client = TestClient(app)


def test_healthz():
    """Test health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.0"}


def test_ask_genie_missing_auth():
    """Test that missing auth returns 401."""
    response = client.post("/genie/ask", json={"question": "test"})
    assert response.status_code == 401


def test_ask_genie_invalid_auth():
    """Test that invalid auth format returns 401."""
    response = client.post(
        "/genie/ask",
        json={"question": "test"},
        headers={"Authorization": "InvalidFormat"},
    )
    assert response.status_code == 401


@patch("genie_api_obo_rls.api.exchange_aad_for_databricks_token_async")
@patch("genie_api_obo_rls.api.GenieClient")
@patch("genie_api_obo_rls.api.get_settings")
def test_ask_genie_success(mock_settings, mock_genie_class, mock_exchange):
    """Test successful Genie query."""
    mock_settings.return_value = Settings(
        databricks_host="https://test.databricks.com",
        genie_space_id="space-1",
        account_id="test-account-id",
        token_exchange_url="https://accounts.azuredatabricks.net/oidc/accounts/test-account-id/v1/token",
    )
    mock_exchange.return_value = TokenExchangeResult(access_token="dbx-token", expires_in=300)

    mock_genie = MagicMock()
    mock_genie.start_conversation.return_value = {
        "conversation_id": "conv-1",
        "message": {"id": "msg-1", "content": "Hello!"},
    }
    mock_genie_class.return_value = mock_genie

    response = client.post(
        "/genie/ask",
        json={"question": "Hello"},
        headers={"Authorization": "Bearer aad-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == "conv-1"
    assert data["content"] == "Hello!"
