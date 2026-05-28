"""
Databricks Genie Conversation API client.

This module provides a simple client for interacting with the Genie API.
The Genie API is asynchronous - messages are submitted and must be polled
until completion.

API Reference:
- https://docs.databricks.com/aws/en/genie/conversation-api
- https://learn.microsoft.com/en-us/azure/databricks/genie/conversation-api
"""

from __future__ import annotations

import time
from typing import Any

import requests


class GenieClient:
    """
    Client for Databricks Genie Conversation API.

    Best practices from Databricks documentation:
    - Poll for status updates every 1 to 5 seconds
    - Use exponential backoff for polling (up to 60 seconds max)
    - Limit polling to 10 minutes for most queries
    - API returns maximum 5,000 rows per query result
    - Throughput limit: 5 queries per minute per workspace (free tier)
    """

    # Polling configuration - per Databricks best practices
    INITIAL_POLL_INTERVAL = 1.0  # Start with 1 second
    MAX_POLL_INTERVAL = 60.0     # Max 60 seconds between polls
    BACKOFF_MULTIPLIER = 1.5     # Exponential backoff multiplier
    MAX_POLL_DURATION = 600      # 10 minutes max wait time (per docs)

    # Known message statuses from Genie API
    COMPLETED_STATUSES = {"COMPLETED"}
    FAILED_STATUSES = {"FAILED", "CANCELLED", "ERROR"}
    IN_PROGRESS_STATUSES = {
        "SUBMITTED",
        "IN_PROGRESS",
        "EXECUTING",
        "EXECUTING_QUERY",
        "PENDING",
        "FETCHING_METADATA",   # Genie is fetching table/schema info
        "FILTERING_CONTEXT",   # Genie is filtering relevant context
        "ASKING_AI",           # Genie is generating response via AI
        "PENDING_WAREHOUSE",   # Waiting for SQL warehouse
        "QUERYING",            # Executing SQL query
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
            host: Databricks workspace URL (e.g., https://workspace.cloud.databricks.com)
            space_id: Genie Space ID
            session: Optional requests session for connection pooling
        """
        self._host = host.rstrip("/")
        self._space_id = space_id
        self._session = session or requests.Session()

    def start_conversation(self, user_token: str, question: str) -> dict[str, Any]:
        """
        Start a new Genie conversation with a question.

        This method submits the question and polls until the response is ready.
        """
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/start-conversation"
        result = self._post(url, user_token, {"content": question})

        # Extract IDs for polling
        conversation_id = result.get("conversation_id")
        message_id = result.get("message_id") or result.get("id")

        if not conversation_id or not message_id:
            return result

        # Poll for the response
        return self._poll_for_response(user_token, conversation_id, message_id)

    def send_message(
        self,
        user_token: str,
        conversation_id: str,
        question: str,
    ) -> dict[str, Any]:
        """
        Send a follow-up message to an existing conversation.

        This method submits the question and polls until the response is ready.
        """
        url = (
            f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/"
            f"{conversation_id}/messages"
        )
        result = self._post(url, user_token, {"content": question})

        # Extract message ID for polling
        message_id = result.get("id") or result.get("message_id")

        if not message_id:
            return result

        # Poll for the response
        return self._poll_for_response(user_token, conversation_id, message_id)

    def get_message(
        self,
        user_token: str,
        conversation_id: str,
        message_id: str,
    ) -> dict[str, Any]:
        """Get the status and content of a specific message."""
        url = (
            f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/"
            f"{conversation_id}/messages/{message_id}"
        )
        return self._get(url, user_token)

    def _poll_for_response(
        self,
        user_token: str,
        conversation_id: str,
        message_id: str,
    ) -> dict[str, Any]:
        """
        Poll the message endpoint until the response is ready.

        Uses exponential backoff per Databricks best practices:
        - Start with 1 second intervals
        - Increase delay up to 60 seconds max
        - Limit total polling time to 10 minutes

        Returns the completed message with the actual response content.
        """
        start_time = time.time()
        attempt = 0
        current_interval = self.INITIAL_POLL_INTERVAL

        while True:
            elapsed = time.time() - start_time
            if elapsed >= self.MAX_POLL_DURATION:
                return {
                    "status": "TIMEOUT",
                    "error": f"Response not ready after {elapsed:.1f} seconds",
                    "conversation_id": conversation_id,
                    "id": message_id,
                }

            attempt += 1

            try:
                result = self.get_message(user_token, conversation_id, message_id)
                status = result.get("status", "UNKNOWN")

                if status in self.COMPLETED_STATUSES:
                    return result

                elif status in self.FAILED_STATUSES:
                    return result

                elif status in self.IN_PROGRESS_STATUSES:
                    # Still processing - use exponential backoff
                    time.sleep(current_interval)
                    # Exponential backoff with cap
                    current_interval = min(current_interval * self.BACKOFF_MULTIPLIER, self.MAX_POLL_INTERVAL)

                else:
                    # Unknown status - treat as in progress, continue polling
                    time.sleep(current_interval)
                    current_interval = min(current_interval * self.BACKOFF_MULTIPLIER, self.MAX_POLL_INTERVAL)

            except requests.exceptions.HTTPError:
                # For HTTP errors, use backoff and retry
                time.sleep(current_interval)
                current_interval = min(current_interval * self.BACKOFF_MULTIPLIER, self.MAX_POLL_INTERVAL)

            except Exception:
                # For unexpected errors, fail fast after a few retries
                if attempt >= 3:
                    raise
                time.sleep(current_interval)

    def _post(self, url: str, user_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request to the Genie API."""
        response = self._session.post(
            url,
            headers={
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _get(self, url: str, user_token: str) -> dict[str, Any]:
        """Make a GET request to the Genie API."""
        response = self._session.get(
            url,
            headers={
                "Authorization": f"Bearer {user_token}",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _get_with_params(
        self, url: str, user_token: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a GET request with query parameters."""
        response = self._session.get(
            url,
            headers={
                "Authorization": f"Bearer {user_token}",
            },
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _delete(self, url: str, user_token: str) -> bool:
        """Make a DELETE request to the Genie API."""
        response = self._session.delete(
            url,
            headers={
                "Authorization": f"Bearer {user_token}",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.status_code in (200, 204)

    # =========================================================================
    # Conversation Management APIs
    # =========================================================================

    def list_conversations(
        self,
        user_token: str,
        page_size: int = 100,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """
        List all conversations in this Genie Space for the authenticated user.

        Args:
            user_token: Databricks access token (user identity)
            page_size: Number of conversations to return (default: 100)
            page_token: Token for pagination (from previous response)

        Returns:
            dict with 'conversations' list and optional 'next_page_token'

            Each conversation contains:
            - conversation_id: Unique identifier
            - title: Auto-generated title from first message
            - created_time: ISO timestamp
            - last_updated_time: ISO timestamp
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
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """
        List all messages in a specific conversation.

        Args:
            user_token: Databricks access token (user identity)
            conversation_id: The conversation ID
            page_size: Number of messages to return (default: 100)
            page_token: Token for pagination (from previous response)

        Returns:
            dict with 'messages' list and optional 'next_page_token'

            Each message contains:
            - id: Message ID
            - content: The question or response text
            - status: Message status (COMPLETED, etc.)
            - created_time: ISO timestamp
            - attachments: List of query results, etc.
        """
        url = (
            f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/"
            f"{conversation_id}/messages"
        )
        params: dict[str, Any] = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        return self._get_with_params(url, user_token, params)

    def delete_conversation(
        self,
        user_token: str,
        conversation_id: str,
    ) -> bool:
        """
        Delete a conversation and all its messages.

        Args:
            user_token: Databricks access token (user identity)
            conversation_id: The conversation ID to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        url = (
            f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/"
            f"{conversation_id}"
        )
        try:
            return self._delete(url, user_token)
        except requests.exceptions.HTTPError:
            return False

    def get_conversation(
        self,
        user_token: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        """
        Get metadata for a specific conversation.

        Args:
            user_token: Databricks access token (user identity)
            conversation_id: The conversation ID

        Returns:
            Conversation metadata including title, timestamps, etc.
        """
        url = (
            f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/"
            f"{conversation_id}"
        )
        return self._get(url, user_token)

    def get_most_recent_conversation(
        self,
        user_token: str,
    ) -> str | None:
        """
        Get the most recent conversation ID for the authenticated user.

        This is a convenience method for conversation resumption.

        Args:
            user_token: Databricks access token (user identity)

        Returns:
            The most recent conversation_id, or None if no conversations exist
        """
        try:
            result = self.list_conversations(user_token, page_size=1)
            conversations = result.get("conversations", [])
            if conversations:
                return conversations[0].get("conversation_id")
            return None
        except requests.exceptions.HTTPError:
            return None

    def get_message_attachment_query_result(
        self,
        user_token: str,
        conversation_id: str,
        message_id: str,
        attachment_id: str,
    ) -> dict[str, Any]:
        """
        Get the query result for a specific message attachment.

        This is the recommended API per Databricks documentation:
        GET /api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result

        Use this when Genie returns a query with attachment_id but doesn't
        include the actual query_result (common for larger result sets).

        Note: API returns maximum 5,000 rows per query result.

        Args:
            user_token: Databricks access token
            conversation_id: The conversation ID
            message_id: The message ID
            attachment_id: The attachment ID from the query attachment

        Returns:
            Query result data including statement_response with columns and rows
        """
        # Per Databricks API docs - use /attachments/{id}/query-result endpoint
        url = (
            f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/"
            f"{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result"
        )

        try:
            return self._get(url, user_token)
        except requests.exceptions.HTTPError:
            # Try the legacy endpoint as fallback
            return self._get_query_result_legacy(user_token, conversation_id, message_id, attachment_id)
        except Exception as e:
            return {"error": str(e)}

    def _get_query_result_legacy(
        self,
        user_token: str,
        conversation_id: str,
        message_id: str,
        attachment_id: str,
    ) -> dict[str, Any]:
        """
        Legacy endpoint for query results (deprecated but may still work).
        GET /api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}/query-result/{attachment_id}
        """
        url = (
            f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/"
            f"{conversation_id}/messages/{message_id}/query-result/{attachment_id}"
        )

        try:
            return self._get(url, user_token)
        except requests.exceptions.HTTPError as e:
            return {"error": str(e)}

    # Alias for backward compatibility
    def get_query_result(
        self,
        user_token: str,
        conversation_id: str,
        message_id: str,
        attachment_id: str,
    ) -> dict[str, Any]:
        """Alias for get_message_attachment_query_result (backward compatibility)."""
        return self.get_message_attachment_query_result(
            user_token, conversation_id, message_id, attachment_id
        )
