#!/usr/bin/env python3
"""
Example: Conversation resumption with Databricks Genie.

This example demonstrates how to:
1. List existing conversations from Databricks
2. Resume the most recent conversation
3. Continue asking follow-up questions

Key Insight: Conversations are stored in DATABRICKS, not locally.
The Genie API provides list_conversations, list_messages, delete_conversation
endpoints to manage conversation history.

Usage:
    export AAD_TOKEN="eyJ..."
    export DATABRICKS_ACCOUNT_ID="12345678-..."
    export DATABRICKS_HOST="https://your-workspace.azuredatabricks.net"
    export GENIE_SPACE_ID="your-space-id"
    python examples/conversation_resumption.py
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
        sys.exit(1)

    print("=" * 60)
    print("Conversation Resumption Example")
    print("=" * 60)

    # Step 1: Get Databricks token
    print("\n1. Authenticating...")
    try:
        token = exchange_token(aad_token, account_id)
        print("   ✓ Authenticated successfully")
    except TokenExchangeError as e:
        print(f"   ✗ Authentication failed: {e}")
        sys.exit(1)

    # Step 2: Initialize client
    client = GenieClient(host, space_id)

    # Step 3: List existing conversations
    print("\n2. Checking for existing conversations...")
    conversations = client.list_conversations(token, page_size=5)
    
    if conversations:
        print(f"   Found {len(conversations)} conversation(s):")
        for i, conv in enumerate(conversations, 1):
            title = conv.get("title", "Untitled")
            conv_id = conv.get("conversation_id", "")[:8]
            print(f"      {i}. {title} (ID: {conv_id}...)")
    else:
        print("   No existing conversations found")

    # Step 4: Resume or start conversation
    conversation_id = None
    if conversations:
        print("\n3. Resuming most recent conversation...")
        conversation_id = conversations[0].get("conversation_id")
        
        # List messages in the conversation to show history
        messages = client.list_messages(token, conversation_id)
        if messages:
            print(f"   Previous messages in this conversation:")
            for msg in messages[:3]:  # Show last 3 messages
                content = msg.get("content", "")[:50]
                print(f"      - {content}...")
    else:
        print("\n3. Starting a new conversation...")

    # Step 5: Ask a question
    question = "Show me the top 5 results"
    print(f"\n4. Asking: '{question}'")
    
    result = client.ask(token, question, conversation_id=conversation_id)
    
    # Step 6: Display response
    status = result.get("status", "UNKNOWN")
    new_conv_id = result.get("conversation_id")
    
    print(f"   Status: {status}")
    print(f"   Conversation ID: {new_conv_id[:8] if new_conv_id else 'N/A'}...")
    
    if status == "COMPLETED":
        for att in result.get("attachments", []):
            if "text" in att:
                text = att["text"]
                content = text.get("content", "") if isinstance(text, dict) else str(text)
                print(f"\n   Response: {content[:200]}...")

    # Step 7: Ask follow-up (same conversation)
    print("\n5. Asking follow-up question in same conversation...")
    follow_up = "Can you show that as a percentage?"
    print(f"   Question: '{follow_up}'")
    
    follow_up_result = client.ask(token, follow_up, conversation_id=new_conv_id)
    print(f"   Status: {follow_up_result.get('status')}")

    print("\n" + "=" * 60)
    print("Key Points:")
    print("- Conversations persist in Databricks, not locally")
    print("- Use list_conversations to find past conversations")
    print("- Pass conversation_id to continue existing conversations")
    print("- User identity (for RLS) is preserved across sessions")
    print("=" * 60)


if __name__ == "__main__":
    main()
