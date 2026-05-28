"""Tests for Genie API client."""

import requests_mock

from genie_api_obo_rls.genie import GenieClient


def test_start_conversation():
    client = GenieClient("https://test.databricks.com", "space-1")

    with requests_mock.Mocker() as m:
        m.post(
            "https://test.databricks.com/api/2.0/genie/spaces/space-1/start-conversation",
            json={"conversation_id": "conv-1", "message": {"id": "msg-1", "content": "Hello!"}},
        )
        result = client.start_conversation("user-token", "What is 2+2?")

    assert result["conversation_id"] == "conv-1"
    assert result["message"]["content"] == "Hello!"


def test_send_message():
    client = GenieClient("https://test.databricks.com", "space-1")

    with requests_mock.Mocker() as m:
        m.post(
            "https://test.databricks.com/api/2.0/genie/spaces/space-1/conversations/conv-1/messages",
            json={"message": {"id": "msg-2", "content": "Follow-up response"}},
        )
        result = client.send_message("user-token", "conv-1", "Follow-up question")

    assert result["message"]["content"] == "Follow-up response"


def test_host_trailing_slash_handled():
    """Ensure trailing slash in host is handled correctly."""
    client = GenieClient("https://test.databricks.com/", "space-1")
    assert client._host == "https://test.databricks.com"
