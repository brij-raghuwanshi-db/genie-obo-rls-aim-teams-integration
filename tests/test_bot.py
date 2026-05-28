"""Tests for the Teams Bot."""

import pytest

from genie_api_obo_rls.bot import GenieBot
from genie_api_obo_rls.config import BotSettings, Settings


@pytest.fixture
def bot_settings():
    return BotSettings(
        microsoft_app_id="test-app-id",
        microsoft_app_password="test-password",
        oauth_connection_name="test-connection",
    )


@pytest.fixture
def genie_settings():
    return Settings(
        databricks_host="https://test.databricks.com",
        genie_space_id="space-1",
        account_id="test-account-id",
        token_exchange_url="https://accounts.azuredatabricks.net/oidc/accounts/test-account-id/v1/token",
    )


@pytest.fixture
def bot(bot_settings, genie_settings):
    return GenieBot(bot_settings=bot_settings, genie_settings=genie_settings)


def test_bot_initialization(bot, bot_settings, genie_settings):
    """Test bot initializes with correct settings."""
    assert bot._bot_settings.microsoft_app_id == "test-app-id"
    assert bot._genie_settings.genie_space_id == "space-1"


def test_extract_response_with_content(bot):
    """Test extracting response with content."""
    result = {"message": {"content": "Hello from Genie!"}}
    assert bot._extract_response(result) == "Hello from Genie!"


def test_extract_response_without_content(bot):
    """Test extracting response without content falls back to raw."""
    result = {"id": "conv-1"}
    response = bot._extract_response(result)
    assert "conv-1" in response


def test_format_table_empty(bot):
    """Test formatting empty table."""
    attachment = {"data": {"columns": [], "rows": []}}
    assert "no data" in bot._format_table(attachment).lower()


def test_format_table_with_data(bot):
    """Test formatting table with data."""
    attachment = {
        "data": {
            "columns": ["name", "sales"],
            "rows": [["Alice", 100], ["Bob", 200]],
        }
    }
    result = bot._format_table(attachment)
    assert "name" in result
    assert "Alice" in result
    assert "100" in result
