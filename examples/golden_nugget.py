"""
=============================================================================
DATABRICKS GENIE + USER IDENTITY (RLS) - THE GOLDEN NUGGET
=============================================================================

This single file contains everything you need to:
1. Exchange Azure AD token → Databricks token (preserving USER identity)
2. Query Databricks Genie as THAT USER (RLS enforced)
3. List and resume past conversations

Copy this file. That's it. Everything else in this project is just UI/UX.

PREREQUISITES:
- Databricks Account Federation Policy configured for your Azure AD tenant
- Automatic Identity Management (AIM) enabled - users are recognized automatically
  via the 'oid' claim when they first authenticate (no pre-provisioning needed)
- Python 3.11+ with `requests` library

USAGE:
    from golden_nugget import exchange_token, GenieClient
    
    # 1. Exchange Azure AD token for Databricks token
    aad_token = "eyJ..."  # From Azure AD OAuth flow
    db_token = exchange_token(
        aad_token=aad_token,
        account_id="your-databricks-account-id"
    )
    
    # 2. Query Genie as the user
    client = GenieClient("https://your-workspace.databricks.com", "genie-space-id")
    result = client.ask(db_token, "Show me my sales data")
    
    # 3. Resume conversation
    recent_conv = client.get_most_recent_conversation(db_token)
    if recent_conv:
        result = client.ask(db_token, "Now filter by Q4", conversation_id=recent_conv)

Copyright (c) 2026 - Released under MIT License
=============================================================================
"""

from __future__ import annotations

import time
from typing import Any

import requests


# =============================================================================
# TOKEN EXCHANGE - The Core Innovation
# =============================================================================

class TokenExchangeError(Exception):
    """Raised when token exchange fails."""
    pass


def exchange_token(
    aad_token: str,
    account_id: str,
    scope: str = "all-apis",
    timeout: int = 30,
) -> str:
    """
    Exchange Azure AD token for Databricks token using Account-Level Federation.
    
    THIS IS THE USP: No client_id means the token is for THE USER, not a service principal.
    This enables Row-Level Security (RLS) based on current_user() in Unity Catalog.
    
    How it works:
    - The entire Azure AD JWT is sent (contains oid, email, and other claims)
    - Databricks uses the 'oid' claim to IDENTIFY/MATCH the user (via AIM)
    - current_user() in SQL returns the user's EMAIL (for RLS filters)
    
    Args:
        aad_token: Azure AD access token (JWT) for the user
        account_id: Databricks Account ID (from account console)
        scope: Token scope (default: "all-apis")
        timeout: Request timeout in seconds
    
    Returns:
        Databricks access token representing THE USER's identity
    
    Raises:
        TokenExchangeError: If exchange fails
    
    Example:
        >>> token = exchange_token("eyJ...", "12345678-1234-1234-1234-123456789012")
        >>> # Use this token - Databricks sees you as the original AAD user
    """
    url = f"https://accounts.azuredatabricks.net/oidc/accounts/{account_id}/v1/token"
    
    # CRITICAL: No client_id in payload = USER identity preserved
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": aad_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "scope": scope,
    }
    
    try:
        response = requests.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise TokenExchangeError(f"Connection failed: {e}") from e
    
    if response.status_code >= 400:
        raise TokenExchangeError(f"Exchange failed: {response.status_code} - {response.text}")
    
    result = response.json()
    token = result.get("access_token")
    if not token:
        raise TokenExchangeError("No access_token in response")
    
    return token


# =============================================================================
# GENIE CLIENT - Minimal but Complete
# =============================================================================

class GenieClient:
    """
    Minimal Databricks Genie client with conversation management.
    
    Supports:
    - Starting new conversations
    - Continuing existing conversations
    - Listing past conversations (for resumption)
    - Automatic polling with backoff
    """
    
    def __init__(self, host: str, space_id: str) -> None:
        """
        Initialize Genie client.
        
        Args:
            host: Databricks workspace URL (e.g., "https://workspace.databricks.com")
            space_id: Genie Space ID
        """
        self._host = host.rstrip("/")
        self._space_id = space_id
        self._session = requests.Session()
    
    def ask(
        self,
        token: str,
        question: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Ask Genie a question.
        
        Args:
            token: Databricks access token (from exchange_token)
            question: Natural language question
            conversation_id: Continue existing conversation (optional)
        
        Returns:
            Genie response with status, attachments, etc.
        """
        if conversation_id:
            url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/{conversation_id}/messages"
        else:
            url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/start-conversation"
        
        response = self._post(url, token, {"content": question})
        
        # Extract IDs for polling
        conv_id = response.get("conversation_id") or conversation_id
        msg_id = response.get("message_id") or response.get("id")
        
        if conv_id and msg_id:
            return self._poll(token, conv_id, msg_id)
        return response
    
    def list_conversations(self, token: str, page_size: int = 100) -> list[dict]:
        """List past conversations for the authenticated user."""
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations"
        result = self._get(url, token, {"page_size": page_size})
        return result.get("conversations", [])
    
    def get_most_recent_conversation(self, token: str) -> str | None:
        """Get the most recent conversation ID, or None if no conversations."""
        conversations = self.list_conversations(token, page_size=1)
        return conversations[0].get("conversation_id") if conversations else None
    
    def list_messages(self, token: str, conversation_id: str) -> list[dict]:
        """List all messages in a conversation."""
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/{conversation_id}/messages"
        result = self._get(url, token)
        return result.get("messages", [])
    
    def delete_conversation(self, token: str, conversation_id: str) -> bool:
        """Delete a conversation. Returns True on success."""
        url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/{conversation_id}"
        try:
            self._delete(url, token)
            return True
        except Exception:
            return False
    
    def _poll(self, token: str, conv_id: str, msg_id: str, max_wait: int = 600) -> dict:
        """Poll until response is ready (with exponential backoff)."""
        start = time.time()
        interval = 1.0
        
        while time.time() - start < max_wait:
            url = f"{self._host}/api/2.0/genie/spaces/{self._space_id}/conversations/{conv_id}/messages/{msg_id}"
            result = self._get(url, token)
            status = result.get("status", "")
            
            if status == "COMPLETED":
                return result
            if status in ("FAILED", "CANCELLED", "ERROR"):
                return result
            
            time.sleep(interval)
            interval = min(interval * 1.5, 60)
        
        return {"status": "TIMEOUT", "error": "Response not ready in time"}
    
    def _post(self, url: str, token: str, data: dict) -> dict:
        resp = self._session.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    
    def _get(self, url: str, token: str, params: dict | None = None) -> dict:
        resp = self._session.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    
    def _delete(self, url: str, token: str) -> None:
        resp = self._session.delete(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Example usage - replace with your values
    import os
    
    # These would come from your environment or OAuth flow
    AAD_TOKEN = os.environ.get("AAD_TOKEN", "your-azure-ad-token")
    ACCOUNT_ID = os.environ.get("DATABRICKS_ACCOUNT_ID", "your-account-id")
    HOST = os.environ.get("DATABRICKS_HOST", "https://your-workspace.databricks.com")
    SPACE_ID = os.environ.get("GENIE_SPACE_ID", "your-genie-space-id")
    
    print("=" * 60)
    print("GOLDEN NUGGET - Databricks Genie with User Identity")
    print("=" * 60)
    
    # Step 1: Exchange token
    print("\n1. Exchanging Azure AD token for Databricks token...")
    try:
        db_token = exchange_token(AAD_TOKEN, ACCOUNT_ID)
        print(f"   Success! Token: {db_token[:20]}...")
    except TokenExchangeError as e:
        print(f"   Failed: {e}")
        exit(1)
    
    # Step 2: Initialize client
    print("\n2. Initializing Genie client...")
    client = GenieClient(HOST, SPACE_ID)
    
    # Step 3: Check for existing conversation to resume
    print("\n3. Checking for existing conversations...")
    recent = client.get_most_recent_conversation(db_token)
    if recent:
        print(f"   Found recent conversation: {recent[:8]}...")
    else:
        print("   No existing conversations")
    
    # Step 4: Ask a question
    print("\n4. Asking Genie: 'Show me total sales by region'")
    result = client.ask(db_token, "Show me total sales by region", conversation_id=recent)
    
    print(f"   Status: {result.get('status')}")
    
    # Extract and print response
    for att in result.get("attachments", []):
        if "text" in att:
            content = att["text"].get("content", "") if isinstance(att["text"], dict) else att["text"]
            print(f"   Response: {content[:100]}...")
        if "query" in att:
            sql = att["query"].get("query", "")
            print(f"   SQL: {sql[:80]}...")
    
    print("\n" + "=" * 60)
    print("Done! This is all you need for Genie + RLS.")
    print("=" * 60)
