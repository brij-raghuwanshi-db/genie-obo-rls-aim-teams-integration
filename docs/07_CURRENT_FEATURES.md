# Current Features

## Feature Overview

This document provides a comprehensive list of all features currently implemented in the Genie API OBO RLS service.

---

## Core Features

### 1. Natural Language Queries

| Feature | Status | Description |
|---------|--------|-------------|
| Text queries | ✅ Implemented | Ask questions in natural language |
| Multi-turn conversations | ✅ Implemented | Follow-up questions in context |
| Conversation resumption | ✅ Implemented | Resume after logout/login |
| Query history | ✅ Implemented | List past conversations |

**Usage Example (Teams)**:
```
User: Show me total sales by region
Bot: [Returns table with sales data]

User: Now filter by Q4
Bot: [Returns filtered table]
```

### 2. User Identity Preservation (RLS + Column Masking)

| Feature | Status | Description |
|---------|--------|-------------|
| OBO token exchange | ✅ Implemented | Azure AD → Databricks token |
| User identity in Genie | ✅ Implemented | current_user() returns email |
| Row-Level Security | ✅ Delegated | Unity Catalog row filters enforced |
| Column Masking | ✅ Delegated | Unity Catalog column masks enforced |
| Per-user data isolation | ✅ Implemented | Users see only their authorized data |

**How it works**:
```
Alice asks "Show my orders"  → Alice sees Alice's orders only
Bob asks "Show my orders"    → Bob sees Bob's orders only
```

**Column Masking Example**:
```sql
-- Unity Catalog column mask (configured by admin)
CREATE FUNCTION mask_salary(salary DECIMAL)
RETURNS DECIMAL
RETURN CASE WHEN is_member('hr_team') THEN salary ELSE NULL END;

ALTER TABLE employees ALTER COLUMN salary SET MASK mask_salary;
```

Since `current_user()` and `is_member()` reflect the actual user's identity, both row filters and column masks work automatically.

### 3. Data Visualization

| Feature | Status | Description |
|---------|--------|-------------|
| Auto chart recommendation | ✅ Implemented | Suggests best chart type |
| Bar charts | ✅ Implemented | Categorical comparisons |
| Line charts | ✅ Implemented | Time series trends |
| Pie charts | ✅ Implemented | Proportions (≤10 categories) |
| Scatter plots | ✅ Implemented | Correlation analysis |
| Histograms | ✅ Implemented | Distribution analysis |
| Chart type switching | ✅ Implemented | Change chart type on demand |

**Chart Selection Logic**:
```
1 numeric column          → Histogram
1 categorical + 1 numeric → Bar or Pie
2 numeric columns         → Scatter
Date + numeric            → Line
Default                   → Bar
```

### 4. Data Export

| Feature | Status | Description |
|---------|--------|-------------|
| CSV download | ✅ Implemented | Export query results |
| PNG download | ✅ Implemented | Export chart images |
| Markdown tables | ✅ Implemented | Display in chat |

---

## Teams Bot Features

### 5. Microsoft Teams Integration

| Feature | Status | Description |
|---------|--------|-------------|
| Direct message | ✅ Implemented | 1:1 chat with bot |
| Teams SSO | ✅ Implemented | Silent sign-in |
| Adaptive Cards | ✅ Implemented | Rich UI components |
| Typing indicator | ✅ Implemented | Shows bot is processing |
| Welcome message | ✅ Implemented | On first interaction |

### 6. Bot Commands

| Command | Action |
|---------|--------|
| `<any question>` | Query Genie |
| `new` / `reset` | Start new conversation |
| `history` / `list` | Show recent conversations |
| `signout` / `logout` | Sign out user |

### 7. Interactive UI Elements

| Element | Description |
|---------|-------------|
| Show Chart button | Generate chart from results |
| Chart type buttons | Switch between chart types |
| Download CSV button | Export data |
| Download PNG button | Export chart |
| Suggested questions | Clickable follow-up suggestions |

**Adaptive Card Example**:
```
┌─────────────────────────────────────┐
│ 📊 Chart available (bar chart)     │
├─────────────────────────────────────┤
│ [📊 Show Bar Chart] [📄 Download]  │
└─────────────────────────────────────┘
```

---

## API Features

### 8. REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/genie/ask` | POST | Query Genie |
| `/v1/healthz` | GET | Health check |
| `/genie/ask` | POST | Legacy endpoint |
| `/healthz` | GET | Legacy health check |
| `/api/messages` | POST | Bot Framework messages |

### 9. API Request/Response

**Request**:
```json
{
  "question": "Show me sales by region",
  "conversation_id": "optional-existing-id"
}
```

**Response**:
```json
{
  "conversation_id": "conv-abc123",
  "message_id": "msg-xyz789",
  "content": "Query result description",
  "raw": { /* Full Genie API response */ }
}
```

---

## Enterprise Features

### 10. Token Caching

| Feature | Status | Description |
|---------|--------|-------------|
| In-memory cache | ✅ Default | Single instance |
| Redis cache | ✅ Optional | Multi-instance |
| TTL management | ✅ Implemented | Configurable expiration |
| Automatic cleanup | ✅ Implemented | Remove expired tokens |
| Refresh token support | ✅ Implemented | Proactive refresh |

### 11. Resilience Patterns

| Pattern | Status | Description |
|---------|--------|-------------|
| Circuit breaker | ✅ Implemented | Prevent cascading failures |
| Retry with backoff | ✅ Implemented | Transient failure handling |
| Timeout handling | ✅ Implemented | 10 minute max for queries |
| Graceful degradation | ✅ Implemented | Return errors, don't crash |

**Circuit Breaker States**:
```
CLOSED → OPEN (after 5 failures)
OPEN → HALF-OPEN (after 60 seconds)
HALF-OPEN → CLOSED (after 2 successes)
```

### 12. Azure Integration

| Service | Status | Description |
|---------|--------|-------------|
| Key Vault | ✅ Optional | Secret management |
| Application Insights | ✅ Optional | Telemetry/monitoring |
| Managed Identity | ✅ Supported | No credentials needed |

---

## Conversation Management

### 13. Conversation Features

| Feature | Status | Description |
|---------|--------|-------------|
| Start conversation | ✅ Implemented | New Genie session |
| Continue conversation | ✅ Implemented | Follow-up questions |
| List conversations | ✅ Implemented | View history |
| Delete conversation | ✅ Implemented | Remove from history |
| Auto-resume | ✅ Implemented | Resume most recent |

### 14. Message Processing

| Feature | Status | Description |
|---------|--------|-------------|
| Status polling | ✅ Implemented | Wait for completion |
| Exponential backoff | ✅ Implemented | Efficient polling |
| Timeout handling | ✅ Implemented | 10 minute limit |
| Error extraction | ✅ Implemented | User-friendly errors |

---

## Response Processing

### 15. Response Formatting

| Format | Status | Description |
|--------|--------|-------------|
| Markdown tables | ✅ Implemented | Query results |
| SQL code blocks | ✅ Implemented | Show generated SQL |
| Analysis descriptions | ✅ Implemented | AI explanations |
| Row limits | ✅ Implemented | 50 rows displayed, 5000 max |

### 16. Attachment Handling

| Type | Status | Description |
|------|--------|-------------|
| Text attachments | ✅ Implemented | Natural language |
| Query attachments | ✅ Implemented | SQL code |
| Query result attachments | ✅ Implemented | Data tables |
| Suggested questions | ✅ Implemented | Follow-up suggestions |

---

## Authentication Features

### 17. SSO Flow

| Feature | Status | Description |
|---------|--------|-------------|
| Silent token acquisition | ✅ Implemented | No prompt if cached |
| Interactive sign-in | ✅ Implemented | OAuth dialog |
| Sign-out | ✅ Implemented | Clear tokens |
| Pending question handling | ✅ Implemented | Resume after auth |

### 18. Token Management

| Feature | Status | Description |
|---------|--------|-------------|
| Automatic caching | ✅ Implemented | Reduce exchanges |
| TTL validation | ✅ Implemented | 30 second buffer |
| Cache key hashing | ✅ Implemented | SHA-256 |
| Token revocation | ✅ Implemented | On sign-out |

---

## Configuration Features

### 19. Environment Variables

| Category | Variables |
|----------|-----------|
| Bot Framework | MICROSOFT_APP_ID, MICROSOFT_APP_PASSWORD, MICROSOFT_APP_TENANT_ID |
| Databricks | GENIE_DATABRICKS_HOST, GENIE_GENIE_SPACE_ID, DATABRICKS_ACCOUNT_ID |
| Token Exchange | GENIE_TOKEN_EXCHANGE_URL, GENIE_TOKEN_SCOPE, GENIE_TOKEN_AUDIENCE |
| Caching | GENIE_CACHE_TTL_SECONDS, REDIS_URL |
| Azure Services | AZURE_KEYVAULT_URL, APPLICATIONINSIGHTS_CONNECTION_STRING |

### 20. Input Validation

| Validation | Description |
|------------|-------------|
| Max question length | 4000 characters |
| SQL injection patterns | Blocked |
| XSS patterns | Blocked |
| Conversation ID format | Alphanumeric + dash + underscore |

---

## Feature Matrix by Interface

| Feature | Teams Bot | Direct API | CLI |
|---------|-----------|------------|-----|
| Natural language queries | ✅ | ✅ | ✅ |
| User identity (RLS) | ✅ | ✅ | ✅ |
| Charts | ✅ | ❌ | ❌ |
| CSV export | ✅ | ❌ | ❌ |
| Suggested questions | ✅ | ❌ | ❌ |
| Conversation resumption | ✅ | ✅ | ✅ |
| Interactive UI | ✅ | ❌ | ❌ |
| Health check | ✅ | ✅ | ❌ |

---

## Not Yet Implemented

| Feature | Priority | Notes |
|---------|----------|-------|
| Column-level security | Low | Use views in Genie Space |
| Query scheduling | Low | Out of scope |
| Admin dashboard | Medium | Use Azure Portal |
| Multi-language support | Low | English only |
| File uploads | Low | Text queries only |
| Proactive notifications | Medium | Potential future feature |
| Group chat support | Medium | 1:1 only recommended |
