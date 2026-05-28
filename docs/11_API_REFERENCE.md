# API Reference

## Overview

The Genie API OBO RLS service exposes both Bot Framework endpoints and REST API endpoints.

---

## Base URLs

| Environment | Base URL |
|-------------|----------|
| Azure App Service | `https://<app-name>.azurewebsites.net` |
| Local Development | `http://localhost:8000` |

---

## Authentication

### REST API Authentication

All REST API endpoints (except health checks) require a bearer token in the `Authorization` header.

```bash
Authorization: Bearer <azure-ad-access-token>
```

**Token Requirements**:
- Must be a valid Azure AD access token
- Must be issued for the user making the request
- Must include required scopes for Databricks access

### Bot Framework Authentication

Bot endpoints are authenticated by the Microsoft Bot Framework using the adapter's built-in validation.

---

## REST API Endpoints

### Health Check

#### GET /v1/healthz

Check service health.

**Authentication**: None

**Request**:
```bash
curl https://your-app.azurewebsites.net/v1/healthz
```

**Response**:
```json
{
  "status": "ok",
  "version": "1.0"
}
```

**Status Codes**:
| Code | Description |
|------|-------------|
| 200 | Service is healthy |
| 503 | Service unavailable |

---

#### GET /healthz (Legacy)

Legacy health check endpoint.

**Authentication**: None

**Response**: Same as `/v1/healthz`

---

### Genie Query

#### POST /v1/genie/ask

Query Databricks Genie with natural language.

**Authentication**: Required (Bearer token)

**Request Headers**:
```
Authorization: Bearer <azure-ad-token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "question": "Show me total sales by region",
  "conversation_id": "optional-existing-conversation-id"
}
```

**Request Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `question` | string | Yes | Natural language query (max 4000 chars) |
| `conversation_id` | string | No | Continue existing conversation |

**Response**:
```json
{
  "conversation_id": "01abc234-5678-90de-fghi-jklmnopqrstu",
  "message_id": "msg-xyz-789",
  "content": "Query description or result summary",
  "raw": {
    "status": "COMPLETED",
    "conversation_id": "01abc234-5678-90de-fghi-jklmnopqrstu",
    "id": "msg-xyz-789",
    "attachments": [
      {
        "text": {
          "content": "Analysis description"
        }
      },
      {
        "query": {
          "query": "SELECT region, SUM(amount) FROM sales GROUP BY region",
          "description": "Aggregating sales by region"
        }
      },
      {
        "query_result": {
          "columns": ["region", "total_sales"],
          "rows": [
            ["East", 125000],
            ["West", 98000]
          ]
        }
      }
    ]
  }
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `conversation_id` | string | Conversation identifier for follow-up |
| `message_id` | string | Message identifier |
| `content` | string | Summary content (may be null) |
| `raw` | object | Full Genie API response |

**Status Codes**:

| Code | Description |
|------|-------------|
| 200 | Query successful |
| 400 | Invalid request (bad JSON, empty question) |
| 401 | Missing or invalid authentication |
| 403 | Access denied |
| 503 | Service unavailable (circuit breaker open) |

**Error Response**:
```json
{
  "detail": "Error message describing the issue"
}
```

**Example - New Conversation**:
```bash
curl -X POST https://your-app.azurewebsites.net/v1/genie/ask \
  -H "Authorization: Bearer $AAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me total sales by region"}'
```

**Example - Continue Conversation**:
```bash
curl -X POST https://your-app.azurewebsites.net/v1/genie/ask \
  -H "Authorization: Bearer $AAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Now filter by Q4",
    "conversation_id": "01abc234-5678-90de-fghi-jklmnopqrstu"
  }'
```

---

#### POST /genie/ask (Legacy)

Legacy endpoint - same functionality as `/v1/genie/ask`.

---

## Bot Framework Endpoint

### POST /api/messages

Bot Framework messaging endpoint. Receives activities from Microsoft Teams and other channels.

**Authentication**: Bot Framework (validated by adapter)

**Request**: Bot Framework Activity object

**Response**: Bot Framework response or 201 Created

**Notes**:
- This endpoint is called by the Bot Framework, not directly by clients
- Configure this URL in Azure Bot Service as the messaging endpoint

---

## Data Models

### AskRequest

```typescript
interface AskRequest {
  question: string;       // Required, max 4000 chars
  conversation_id?: string;  // Optional, alphanumeric + dash + underscore
}
```

**Validation Rules**:
- `question` must not be empty
- `question` must not exceed 4000 characters
- `question` must not contain SQL injection patterns
- `question` must not contain XSS patterns
- `conversation_id` must match `^[a-zA-Z0-9_-]+$`

### AskResponse

```typescript
interface AskResponse {
  conversation_id: string | null;
  message_id: string | null;
  content: string | null;
  raw: GenieApiResponse;
}
```

### GenieApiResponse (raw field)

```typescript
interface GenieApiResponse {
  status: "COMPLETED" | "FAILED" | "TIMEOUT" | "CANCELLED" | "ERROR";
  conversation_id: string;
  id: string;  // message_id
  error?: string;
  attachments?: Attachment[];
}

interface Attachment {
  text?: { content: string };
  query?: { query: string; description: string };
  query_result?: QueryResult;
  suggested_questions?: string[];
}

interface QueryResult {
  columns: string[];
  rows: any[][];
  row_count?: number;
}
```

---

## Rate Limits

| Limit | Value | Source |
|-------|-------|--------|
| Genie queries per minute (free tier) | 5 | Databricks |
| Bot messages per second | ~5 | Bot Framework |
| Token exchanges per minute | ~100 | Azure AD |

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 400 | Bad Request | Check request format |
| 401 | Unauthorized | Check/refresh token |
| 403 | Forbidden | User lacks permissions |
| 404 | Not Found | Check endpoint URL |
| 429 | Too Many Requests | Implement backoff |
| 500 | Internal Error | Retry with backoff |
| 503 | Service Unavailable | Wait and retry |

### Error Response Format

```json
{
  "detail": "Human-readable error message"
}
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Missing Authorization header" | No token provided | Add Bearer token |
| "Invalid Authorization header" | Malformed header | Use "Bearer <token>" format |
| "Token exchange failed" | Invalid AAD token | Get fresh token |
| "Service temporarily unavailable" | Circuit breaker open | Wait 60 seconds |
| "question is required" | Empty question | Provide question text |

---

## Code Examples

### Python

```python
import requests

def query_genie(aad_token: str, question: str, conversation_id: str = None):
    url = "https://your-app.azurewebsites.net/v1/genie/ask"
    headers = {
        "Authorization": f"Bearer {aad_token}",
        "Content-Type": "application/json"
    }
    payload = {"question": question}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

# Usage
result = query_genie(token, "Show me sales by region")
print(result["raw"]["attachments"])
```

### JavaScript/TypeScript

```typescript
async function queryGenie(
  aadToken: string,
  question: string,
  conversationId?: string
): Promise<AskResponse> {
  const response = await fetch(
    "https://your-app.azurewebsites.net/v1/genie/ask",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${aadToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        conversation_id: conversationId,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
}

// Usage
const result = await queryGenie(token, "Show me sales by region");
console.log(result.raw.attachments);
```

### cURL

```bash
# New conversation
curl -X POST https://your-app.azurewebsites.net/v1/genie/ask \
  -H "Authorization: Bearer $AAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me total sales"}'

# Continue conversation
curl -X POST https://your-app.azurewebsites.net/v1/genie/ask \
  -H "Authorization: Bearer $AAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Filter by Q4", "conversation_id": "abc123"}'
```

---

## GenieClient Conversation Management APIs

The `GenieClient` class in `genie.py` provides additional methods for conversation management. These are used internally by the bot and can be used directly when integrating with `golden_nugget.py`.

### list_conversations

List all conversations for the authenticated user.

```python
def list_conversations(
    user_token: str,
    page_size: int = 100,
    page_token: str | None = None,
) -> dict[str, Any]
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_token` | string | Yes | Databricks access token |
| `page_size` | int | No | Number of conversations (default: 100) |
| `page_token` | string | No | Pagination token from previous response |

**Response**:
```json
{
  "conversations": [
    {
      "conversation_id": "01abc234...",
      "title": "Sales Analysis Q4",
      "created_time": "2026-01-28T10:30:00Z",
      "last_updated_time": "2026-01-28T11:45:00Z"
    }
  ],
  "next_page_token": "optional-token-for-pagination"
}
```

---

### list_messages

List all messages in a specific conversation.

```python
def list_messages(
    user_token: str,
    conversation_id: str,
    page_size: int = 100,
    page_token: str | None = None,
) -> dict[str, Any]
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_token` | string | Yes | Databricks access token |
| `conversation_id` | string | Yes | Conversation to list messages from |
| `page_size` | int | No | Number of messages (default: 100) |
| `page_token` | string | No | Pagination token |

**Response**:
```json
{
  "messages": [
    {
      "id": "msg-xyz-789",
      "content": "Show me sales by region",
      "status": "COMPLETED",
      "created_time": "2026-01-28T10:30:00Z",
      "attachments": [...]
    }
  ],
  "next_page_token": "optional-token"
}
```

---

### get_conversation

Get metadata for a specific conversation.

```python
def get_conversation(
    user_token: str,
    conversation_id: str,
) -> dict[str, Any]
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_token` | string | Yes | Databricks access token |
| `conversation_id` | string | Yes | Conversation ID |

**Response**: Conversation metadata including title, timestamps.

---

### delete_conversation

Delete a conversation and all its messages.

```python
def delete_conversation(
    user_token: str,
    conversation_id: str,
) -> bool
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_token` | string | Yes | Databricks access token |
| `conversation_id` | string | Yes | Conversation to delete |

**Returns**: `True` if deleted successfully, `False` otherwise.

---

### get_most_recent_conversation

Get the most recent conversation ID for the user.

```python
def get_most_recent_conversation(user_token: str) -> str | None
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_token` | string | Yes | Databricks access token |

**Returns**: Conversation ID string, or `None` if no conversations exist.

**Usage**: Used internally for automatic conversation resumption.

---

### get_message_attachment_query_result

Fetch query results for a specific message attachment.

```python
def get_message_attachment_query_result(
    user_token: str,
    conversation_id: str,
    message_id: str,
    attachment_id: str,
) -> dict[str, Any]
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_token` | string | Yes | Databricks access token |
| `conversation_id` | string | Yes | Conversation ID |
| `message_id` | string | Yes | Message ID |
| `attachment_id` | string | Yes | Attachment ID from query attachment |

**Returns**: Query result with `statement_response` containing columns and rows.

**Note**: Genie API returns maximum 5,000 rows per query result.

---

## SDK / Client Library

For convenience, use the `golden_nugget.py` module:

```python
from golden_nugget import exchange_token, GenieClient

# Exchange Azure AD token for Databricks token
db_token = exchange_token(aad_token, account_id)

# Query Genie
client = GenieClient(databricks_host, space_id)
result = client.ask(db_token, "Show me sales by region")

# Continue conversation
result = client.ask(db_token, "Filter by Q4", conversation_id=result["conversation_id"])
```
