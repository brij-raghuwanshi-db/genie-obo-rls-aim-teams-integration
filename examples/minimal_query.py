#!/usr/bin/env python3
"""
Minimal example: Query Databricks Genie with user identity (RLS).

This example uses only the golden_nugget.py - the standalone core that
contains everything needed for token exchange and Genie queries.

Prerequisites:
- Azure AD token (from OAuth flow)
- Databricks Account ID (from account console)
- Genie Space ID (from workspace)
- Automatic Identity Management (AIM) enabled in Databricks
  (users are recognized automatically via 'oid' claim - no pre-provisioning needed)

Usage:
    export AAD_TOKEN="eyJ..."
    export DATABRICKS_ACCOUNT_ID="12345678-..."
    export DATABRICKS_HOST="https://your-workspace.azuredatabricks.net"
    export GENIE_SPACE_ID="your-space-id"
    python examples/minimal_query.py
"""

import os
import sys

# Add parent directory to path to import golden_nugget
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from golden_nugget import exchange_token, GenieClient, TokenExchangeError


def main():
    # Get configuration from environment
    aad_token = os.environ.get("AAD_TOKEN")
    account_id = os.environ.get("DATABRICKS_ACCOUNT_ID")
    host = os.environ.get("DATABRICKS_HOST")
    space_id = os.environ.get("GENIE_SPACE_ID")

    # Validate configuration
    missing = []
    if not aad_token:
        missing.append("AAD_TOKEN")
    if not account_id:
        missing.append("DATABRICKS_ACCOUNT_ID")
    if not host:
        missing.append("DATABRICKS_HOST")
    if not space_id:
        missing.append("GENIE_SPACE_ID")

    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("\nSet these environment variables and try again.")
        sys.exit(1)

    print("=" * 60)
    print("Minimal Genie Query Example")
    print("=" * 60)

    # Step 1: Exchange Azure AD token for Databricks token
    print("\n1. Exchanging Azure AD token for Databricks token...")
    try:
        databricks_token = exchange_token(aad_token, account_id)
        print(f"   ✓ Token obtained: {databricks_token[:20]}...")
    except TokenExchangeError as e:
        print(f"   ✗ Token exchange failed: {e}")
        sys.exit(1)

    # Step 2: Initialize Genie client
    print("\n2. Initializing Genie client...")
    client = GenieClient(host, space_id)
    print(f"   ✓ Client ready for space: {space_id}")

    # Step 3: Ask a question
    question = "What tables are available?"
    print(f"\n3. Asking Genie: '{question}'")
    
    result = client.ask(databricks_token, question)
    status = result.get("status", "UNKNOWN")
    print(f"   Status: {status}")

    # Step 4: Display response
    if status == "COMPLETED":
        print("\n4. Response:")
        for att in result.get("attachments", []):
            if "text" in att:
                text = att["text"]
                if isinstance(text, dict):
                    content = text.get("content", "")
                else:
                    content = str(text)
                print(f"   {content}")
            elif "query" in att:
                query = att["query"]
                sql = query.get("query", "") if isinstance(query, dict) else ""
                if sql:
                    print(f"   SQL: {sql[:100]}...")
    else:
        print(f"\n4. Query did not complete: {result.get('error', 'Unknown error')}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
