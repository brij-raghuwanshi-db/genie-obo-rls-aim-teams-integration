"""
Databricks Genie Conversation API client.

This module provides a client for the Genie API with:
- Conversation management (start, continue, list, delete)
- Message retrieval with polling
- Query result fetching

Best practices from Databricks documentation:
- Poll for status updates every 1 to 5 seconds
- Use exponential backoff for polling (up to 60 seconds max)
- Limit polling to 10 minutes for most queries
- API returns maximum 5,000 rows per query result
"""

from __future__ import annotations

import time
from typing import Any

import requests


class GenieClient:
    """
    Client for Databricks Genie Conversation API.
    
    Example:
        client = GenieClient("https://workspace.databricks.com", "space-id")
        result = client.start_conversation(token, "Show me sales data")
    """

    # Polling configuration
    INITIAL_POLL_INTERVAL = 1.0
    MAX_POLL_INTERVAL = 60.0
    BACKOFF_MULTIPLIER = 1.5
    MAX_POLL_DURATION = 600  # 10 minutes

    # Message statuses
    COMPLETED_STATUSES = {"COMPLETED"}
    FAILED_STATUSES = {"FAILED", "CANCELLED", "ERROR"}
    IN_PROGRESS_STATUSES = {
        "SUBMITTED", "IN_PROGRESS", "EXECUTING", "EXECUTING_QUERY",
        "PENDING", "FETCHING_METADATA", "FILTERING_CONTEXT", "ASKING_AI",
        "PENDING_WAREHOUSE", "QUERYING",
    }

    def __init__(
        self,
        host: str,
        space_id: str,
        session: requests.Session | None = None,
    ) -> None:
        """
        Initialize the Genie client.

        Args:
            host: Databricks workspace URL
            space_id: Genie Space ID
            session: Optional requests session for connection pooling
        """
        self._host = host.rstrip("/")
        self._space_id = space_id
        self._session = session or requests.Session()

    @property
    def host(self) -> str:
        """Get the Databricks host URL."""
        return self._host

    @property
    def space_id(self) -> str:
        """Get the Genie Space ID."""
        return self._space_id

    # =========================================================================
    # Conversation API
    # =========================================================================

    def start_conversation(self, user_token: str, question: str) -> dict[str, Any]:
        """Start a new conversation with a question."""
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/start-conversation"
        result = self._post(url, user_token, {"content": question})
        
        conv_id = result.get("conversation_id")
        msg_id = result.get("message_id") or result.get("id")
        
        if conv_id and msg_id:
            return self._poll_for_response(user_token, conv_id, msg_id)
        return result

    def send_message(
        self,
        user_token: str,
        conversation_id: str,
        question: str,
    ) -> dict[str, Any]:
        """Send a follow-up message to an existing conversation."""
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/{conversation_id}/messages"
        result = self._post(url, user_token, {"content": question})
        
        msg_id = result.get("id") or result.get("message_id")
        if msg_id:
            return self._poll_for_response(user_token, conversation_id, msg_id)
        return result

    def get_message(
        self,
        user_token: str,
        conversation_id: str,
        message_id: str,
    ) -> dict[str, Any]:
        """Get the status and content of a specific message."""
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/{conversation_id}/messages/{message_id}"
        return self._get(url, user_token)

    # =========================================================================
    # Conversation Management
    # =========================================================================

    def list_conversations(
        self,
        user_token: str,
        page_size: int = 100,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """
        List all conversations in this Genie Space.
        
        Returns:
            dict with 'conversations' list and optional 'next_page_token'
        """
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations"
        params: dict[str, Any] = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        return self._get_with_params(url, user_token, params)

    def list_messages(
        self,
        user_token: str,
        conversation_id: str,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """List all messages in a conversation."""
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/{conversation_id}/messages"
        return self._get_with_params(url, user_token, {"page_size": page_size})

    def delete_conversation(self, user_token: str, conversation_id: str) -> bool:
        """Delete a conversation. Returns True on success."""
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/{conversation_id}"
        try:
            return self._delete(url, user_token)
        except requests.exceptions.HTTPError:
            return False

    def get_conversation(self, user_token: str, conversation_id: str) -> dict[str, Any]:
        """Get metadata for a specific conversation."""
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/{conversation_id}"
        return self._get(url, user_token)

    def get_most_recent_conversation(self, user_token: str) -> str | None:
        """Get the most recent conversation ID, or None if none exist."""
        try:
            result = self.list_conversations(user_token, page_size=1)
            conversations = result.get("conversations", [])
            return conversations[0].get("conversation_id") if conversations else None
        except requests.exceptions.HTTPError:
            return None

    # =========================================================================
    # Query Results
    # =========================================================================

    def get_query_result(
        self,
        user_token: str,
        conversation_id: str,
        message_id: str,
        attachment_id: str,
    ) -> dict[str, Any]:
        """Get the query result for a specific attachment."""
        url = (
            f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/"
            f"{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result"
        )
        try:
            return self._get(url, user_token)
        except requests.exceptions.HTTPError:
            # Try legacy endpoint
            legacy_url = (
                f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/"
                f"{conversation_id}/messages/{message_id}/query-result/{attachment_id}"
            )
            try:
                return self._get(legacy_url, user_token)
            except requests.exceptions.HTTPError as e:
                return {"error": str(e)}

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _poll_for_response(
        self,
        user_token: str,
        conversation_id: str,
        message_id: str,
    ) -> dict[str, Any]:
        """Poll until response is ready with exponential backoff."""
        start_time = time.time()
        interval = self.INITIAL_POLL_INTERVAL

        while True:
            elapsed = time.time() - start_time
            if elapsed >= self.MAX_POLL_DURATION:
                return {
                    "status": "TIMEOUT",
                    "error": f"Response not ready after {elapsed:.1f}s",
                    "conversation_id": conversation_id,
                    "id": message_id,
                }

            try:
                result = self.get_message(user_token, conversation_id, message_id)
                status = result.get("status", "UNKNOWN")

                if status in self.COMPLETED_STATUSES:
                    return result
                if status in self.FAILED_STATUSES:
                    return result

                time.sleep(interval)
                interval = min(interval * self.BACKOFF_MULTIPLIER, self.MAX_POLL_INTERVAL)

            except requests.exceptions.HTTPError:
                time.sleep(interval)
                interval = min(interval * self.BACKOFF_MULTIPLIER, self.MAX_POLL_INTERVAL)

    def _post(self, url: str, user_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request."""
        response = self._session.post(
            url,
            headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _get(self, url: str, user_token: str) -> dict[str, Any]:
        """Make a GET request."""
        response = self._session.get(
            url,
            headers={"Authorization": f"Bearer {user_token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _get_with_params(
        self,
        url: str,
        user_token: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a GET request with query parameters."""
        response = self._session.get(
            url,
            headers={"Authorization": f"Bearer {user_token}"},
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _delete(self, url: str, user_token: str) -> bool:
        """Make a DELETE request."""
        response = self._session.delete(
            url,
            headers={"Authorization": f"Bearer {user_token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.status_code in (200, 204)
