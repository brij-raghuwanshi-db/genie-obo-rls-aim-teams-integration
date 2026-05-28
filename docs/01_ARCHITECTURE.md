# Architecture Overview

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              GENIE API OBO RLS SERVICE                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────────┐    │
│  │   Teams     │     │             │     │    Azure App Service            │    │
│  │  Web Chat   │────▶│ Azure Bot   │────▶│  (dbrx-webapp-genie-obo-rls)    │    │
│  │ Direct API  │     │  Service    │     │                                 │    │
│  │             │◀────│             │◀────│  ┌─────────────────────────┐    │    │
│  └─────────────┘     └─────────────┘     │  │    GenieBot (bot.py)    │    │    │
│                                          │  │   TeamsActivityHandler  │    │    │
│                                          │  └───────────┬─────────────┘    │    │
│                                          │              │                  │    │
│                                          │              ▼                  │    │
│                                          │  ┌─────────────────────────┐    │    │
│                                          │  │   Authentication Layer   │   │    │
│                                          │  │   (auth.py)              │   │    │
│                                          │  │   - Teams SSO Dialog     │   │    │
│                                          │  │   - Token Exchange       │   │    │
│                                          │  │   - Token Cache          │   │    │
│                                          │  └───────────┬─────────────┘    │    │
│                                          │              │                  │    │
│                                          │              ▼                  │    │
│                                          │  ┌─────────────────────────┐    │    │
│                                          │  │ FastAPI Layer (api.py)  │    │    │
│                                          │  │  - /v1/genie/ask        │    │    │
│                                          │  │  - /v1/healthz          │    │    │
│                                          │  └───────────┬─────────────┘    │    │
│                                          │              │                  │    │
│                                          │              ▼                  │    │
│                                          │  ┌─────────────────────────┐    │    │
│                                          │  │  Genie Client (genie.py)│    │    │
│                                          │  │  - start_conversation   │    │    │
│                                          │  │  - send_message         │    │    │
│                                          │  │  - poll_for_response    │    │    │
│                                          │  │  - list_conversations   │    │    │
│                                          │  └───────────┬─────────────┘    │    │
│                                          │              │                  │    │
│                                          └──────────────┼──────────────────┘    │
│                                                         │                       │
├─────────────────────────────────────────────────────────┼───────────────────────┤
│                                                         │                       │
│  ┌─────────────────────────────────────────────────────┼─────────────────────┐  │
│  │                    AZURE AD & DATABRICKS            │                     │  │
│  │                                                     ▼                     │  │
│  │  ┌─────────────────┐    Token Exchange    ┌─────────────────────────┐     │  │
│  │  │    Azure AD     │◀────────────────────▶│  Databricks Account     │     │  │
│  │  │                 │                      │  Federation Service     │     │  │
│  │  │  - User Auth    │                      │                         │     │  │
│  │  │  - JWT Tokens   │   NO client_id =     │ accounts.azuredatabricks│     │  │
│  │  │  - OID Claims   │   USER Identity      │  .net/oidc/accounts/    │     │  │
│  │  └─────────────────┘                      │  {account_id}/v1/token  │     │  │
│  │                                           └────────────┬────────────┘     │  │
│  │                                                        │                  │  │
│  │                                                        ▼                  │  │
│  │                                           ┌─────────────────────────┐     │  │
│  │                                           │  Databricks Workspace   │     │  │
│  │                                           │   (dbrx-wk-*)           │     │  │
│  │                                           │                         │     │  │
│  │                                           │  ┌───────────────────┐  │     │  │
│  │                                           │  │   Genie Space     │  │     │  │
│  │                                           │  │   Conversation    │  │     │  │
│  │                                           │  │   API             │  │     │  │
│  │                                           │  └─────────┬─────────┘  │     │  │
│  │                                           │            │            │     │  │
│  │                                           │            ▼            │     │  │
│  │                                           │  ┌───────────────────┐  │     │  │
│  │                                           │  │  Unity Catalog    │  │     │  │
│  │                                           │  │  - Row-Level      │  │     │  │
│  │                                           │  │    Security (RLS) │  │     │  │
│  │                                           │  │  - current_user() │  │     │  │
│  │                                           │  └───────────────────┘  │     │  │
│  │                                           └─────────────────────────┘     │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Entry Points

| Component | File | Purpose |
|-----------|------|---------|
| **Main Entry** | `main.py` | CLI and server orchestration |
| **Bot Server** | `bot.py` | Teams Bot Framework handler |
| **API Server** | `api.py` | FastAPI REST endpoints |

### 2. Core Layer (`src/genie_api_obo_rls/core/`)

| Component | File | Purpose |
|-----------|------|---------|
| **Token Exchange** | `token_exchange.py` | OBO flow for user identity |
| **Genie Client** | `genie_client.py` | Databricks Genie API wrapper |
| **Configuration** | `config.py` | Settings and validation |

### 3. Enterprise Layer (`src/genie_api_obo_rls/enterprise/`)

| Component | File | Purpose |
|-----------|------|---------|
| **Memory Cache** | `cache.py` | In-process token caching |
| **Redis Cache** | `cache_redis.py` | Distributed caching |
| **Circuit Breaker** | `circuit_breaker.py` | Resilience pattern |

### 4. Bot Layer (`src/genie_api_obo_rls/bot/`)

| Component | File | Purpose |
|-----------|------|---------|
| **Adaptive Cards** | `cards/templates/` | UI components for Teams |

### 5. Visualization Layer

| Component | File | Purpose |
|-----------|------|---------|
| **Chart Generation** | `charts.py` | matplotlib-based charts |

## Data Flow

### 1. Authentication Flow

```
User → Teams → Bot Service → App Service → Azure AD SSO
                                                 │
                                                 ▼
                                     OAuth Token (AAD JWT)
                                                 │
                                                 ▼
                                     Token Exchange (Account-Level)
                                     NO client_id = USER identity
                                                 │
                                                 ▼
                                     Databricks Token (USER)
```

### ASCII Token Exchange Sequence

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              TOKEN EXCHANGE SEQUENCE (OBO Flow)                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   User   │  │  Teams/  │  │  Bot     │  │  App     │  │Databricks│  │  Genie   │
│          │  │  WebChat │  │  Service │  │  Service │  │  Account │  │   API    │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │             │             │
     │ 1. Open Bot │             │             │             │             │
     │────────────►│             │             │             │             │
     │             │             │             │             │             │
     │             │ 2. Activity │             │             │             │
     │             │────────────►│             │             │             │
     │             │             │             │             │             │
     │             │             │ 3. POST     │             │             │
     │             │             │ /api/messages             │             │
     │             │             │────────────►│             │             │
     │             │             │             │             │             │
     │             │             │ 4. Check    │             │             │
     │             │             │ cached token│             │             │
     │             │             │◄────────────│             │             │
     │             │             │             │             │             │
     ├─────────────┴─────────────┴─────────────┴─────────────┴─────────────┤
     │         [IF NO VALID TOKEN - OAUTH FLOW]                            │
     ├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┤
     │             │             │             │             │             │
     │             │ 5a. Initiate│             │             │             │
     │             │ OAuth       │             │             │             │
     │◄────────────│────────────►│             │             │             │
     │             │             │             │             │             │
     │ 5b. Azure   │             │             │             │             │
     │ AD Login    │             │             │             │             │
     │   Popup     │             │             │             │             │
     │◄────────────│             │             │             │             │
     │             │             │             │             │             │
     │ 5c. User    │             │             │             │             │
     │ Authenticates             │             │             │             │
     │────────────►│             │             │             │             │
     │             │             │             │             │             │
     │             │ 5d. AAD     │             │             │             │
     │             │ Token cached│             │             │             │
     │             │◄────────────│             │             │             │
     │             │             │             │             │             │
     ├─────────────┴─────────────┴─────────────┴─────────────┴─────────────┤
     │         [END OAUTH FLOW]                                            │
     ├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┤
     │             │             │             │             │             │
     │ 6. Ask      │             │             │             │             │
     │ "show sales │ 7. Forward  │ 8. Forward  │             │             │
     │  by region" │    message  │    to bot.py│             │             │
     │────────────►│────────────►│────────────►│             │             │
     │             │             │             │             │             │
     │             │             │ 9. Get SSO  │             │             │
     │             │             │    token    │             │             │
     │             │             │◄────────────│             │             │
     │             │             │             │             │             │
     │             │             │             │ 10. Token   │             │
     │             │             │             │ Exchange    │             │
     │             │             │             │ (NO client_id!)           │
     │             │             │             │────────────►│             │
     │             │             │             │             │             │
     │             │             │             │ 11. Return  │             │
     │             │             │             │ Databricks  │             │
     │             │             │             │ Token       │             │
     │             │             │             │ (sub=user@  │             │
     │             │             │             │  company.com)             │
     │             │             │             │◄────────────│             │
     │             │             │             │             │             │
     │             │             │             │ 12. Call    │             │
     │             │             │             │ Genie API   │             │
     │             │             │             │ with USER   │             │
     │             │             │             │ token       │             │
     │             │             │             │────────────►│────────────►│
     │             │             │             │             │             │
     │             │             │             │             │ 13. Execute │
     │             │             │             │             │ Query with  │
     │             │             │             │             │ RLS:        │
     │             │             │             │             │ current_user│
     │             │             │             │             │ ()='user@   │
     │             │             │             │             │ company.com'│
     │             │             │             │◄────────────│◄────────────│
     │             │             │             │             │             │
     │             │             │ 14. Format  │             │             │
     │             │             │ response    │             │             │
     │             │             │◄────────────│             │             │
     │             │             │             │             │             │
     │ 15. Display │             │             │             │             │
     │ filtered    │◄────────────│◄────────────│             │             │
     │ results     │             │             │             │             │
     │             │             │             │             │             │
     ▼             ▼             ▼             ▼             ▼             ▼

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ KEY INSIGHT: Step 10 sends NO client_id in the token exchange request.                          │
│ This is Account-Level Federation - the resulting Databricks token preserves USER identity.      │
│ Unity Catalog sees current_user() = 'user@company.com' and enforces RLS automatically.          │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2. Query Flow

```
User Question → Bot Handler → Token Validation → Genie Client
                                                      │
                                                      ▼
                                              start_conversation
                                              OR send_message
                                                      │
                                                      ▼
                                              Poll for Response
                                              (exponential backoff)
                                                      │
                                                      ▼
                                              Extract Response
                                              + Chart Data
                                              + Suggestions
                                                      │
                                                      ▼
                                              Format & Send
                                              to User
```

### 3. RLS Enforcement Flow

```
Genie Query (with USER token)
          │
          ▼
   Unity Catalog
   current_user() = 'user@company.com'
          │
          ▼
   Row Filter Applied
   WHERE owner = current_user()
          │
          ▼
   User Sees ONLY Their Data
```

## Module Dependencies

```
main.py
├── bot.py (mode=bot)
│   ├── auth.py (TeamsSsoDialog, TokenCache)
│   ├── genie.py (GenieClient)
│   ├── charts.py (chart generation)
│   └── config.py (BotSettings, Settings)
│
├── api.py (mode=api)
│   ├── auth.py (token exchange)
│   ├── genie.py (GenieClient)
│   └── config.py (Settings, AskRequest, AskResponse)
│
└── services.py (optional)
    ├── Azure Key Vault
    └── Application Insights
```

## Network Topology

| Source | Destination | Port | Protocol |
|--------|-------------|------|----------|
| Teams Client | Azure Bot Service | 443 | HTTPS |
| Azure Bot Service | App Service | 443 | HTTPS |
| App Service | Azure AD | 443 | HTTPS |
| App Service | Databricks Account | 443 | HTTPS |
| App Service | Databricks Workspace | 443 | HTTPS |
| App Service | Redis (optional) | 6380 | TLS |
| App Service | Key Vault (optional) | 443 | HTTPS |

## Scaling Architecture

### Single Instance (Default)
- In-memory token cache
- Suitable for <100 concurrent users

### Multi-Instance (Scaled)
```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    │  (Azure FD/AG)  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌──────────┐   ┌──────────┐   ┌──────────┐
       │Instance 1│   │Instance 2│   │Instance 3│
       └────┬─────┘   └────┬─────┘   └────┬─────┘
            │              │              │
            └──────────────┼──────────────┘
                           ▼
                  ┌─────────────────┐
                  │   Azure Redis   │
                  │  (Shared Cache) │
                  └─────────────────┘
```

## Security Boundaries

1. **Network Boundary**: VNet integration recommended for production
2. **Identity Boundary**: Azure AD tenant isolation
3. **Data Boundary**: Unity Catalog RLS at SQL level
4. **Secret Boundary**: Azure Key Vault for credentials

---

## AWS Databricks Variant

The architecture is **cloud-agnostic**. Teams users can query Databricks hosted on AWS with minimal configuration changes.

### Cross-Cloud Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CROSS-CLOUD DEPLOYMENT                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│       MICROSOFT 365 / AZURE                        AMAZON WEB SERVICES          │
│       ──────────────────────                       ────────────────────          │
│                                                                                  │
│   ┌──────────────┐                               ┌──────────────────┐           │
│   │  Microsoft   │                               │  Databricks on   │           │
│   │    Teams     │                               │      AWS         │           │
│   └──────┬───────┘                               └────────▲─────────┘           │
│          │                                                │                      │
│          ▼                                                │                      │
│   ┌──────────────┐        Federation Policy      ┌───────┴────────┐            │
│   │   Azure AD   │◀─────────────────────────────▶│  Databricks    │            │
│   │  (Entra ID)  │   "Trust AAD tokens"          │  Account       │            │
│   └──────┬───────┘                               └────────────────┘            │
│          │                                                                       │
│          ▼                                                                       │
│   ┌──────────────┐       OBO Token Exchange      ┌────────────────┐            │
│   │  Bot App     │──────────────────────────────▶│  accounts.     │            │
│   │  (Azure)     │   (Account-Level, NO client_id)  cloud.       │            │
│   └──────────────┘                               │  databricks.com│            │
│                                                   └────────────────┘            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### What Changes

| Component | Azure Databricks | AWS Databricks |
|-----------|------------------|----------------|
| **Workspace URL** | `*.azuredatabricks.net` | `*.cloud.databricks.com` |
| **Token Endpoint** | `accounts.azuredatabricks.net/oidc/accounts/{id}/v1/token` | `accounts.cloud.databricks.com/oidc/accounts/{id}/v1/token` |
| **Identity Provider** | Azure AD | Azure AD (same!) |
| **Application Code** | No change | No change |
| **Unity Catalog** | Identical | Identical |
| **RLS Policies** | Identical | Identical |

### Configuration

Set the token exchange URL via environment variable:

```bash
# For AWS Databricks
GENIE_TOKEN_EXCHANGE_URL=https://accounts.cloud.databricks.com/oidc/accounts/{account_id}/v1/token
GENIE_DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
```

The code in `config.py` handles this automatically:

```python
def get_account_token_exchange_url(self) -> str:
    if self.token_exchange_url and "accounts.azuredatabricks.net" in self.token_exchange_url:
        return self.token_exchange_url
    # Can also work with accounts.cloud.databricks.com
    return f"https://accounts.azuredatabricks.net/oidc/accounts/{self.account_id}/v1/token"
```

### Key Insight

Even with Databricks on AWS, **identity comes from Azure AD** because:

1. Microsoft Teams requires Azure AD
2. Databricks Account Federation supports multi-cloud
3. The OIDC token exchange standard works identically

**The solution is truly cloud-agnostic** - same user experience, same RLS enforcement.
