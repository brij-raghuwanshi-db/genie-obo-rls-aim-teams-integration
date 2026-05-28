# Genie OBO RLS AIM Teams Integration

Microsoft Teams Bot and Direct API integration with Databricks Genie that preserves the end user's identity through On-Behalf-Of (OBO) token exchange, so Unity Catalog permissions and Row-Level Security (RLS) continue to apply in AIM-enabled workspaces.

## The USP (Unique Selling Proposition)

**User Identity Preservation**: When a user asks "Show me my sales data" through Teams, they see THEIR data, not everyone's data. This is achieved by:

1. Exchanging the user's Azure AD token for a Databricks token (OBO flow)
2. Using ACCOUNT-LEVEL federation (no client_id = USER identity)
3. Unity Catalog enforces RLS using `current_user()`

See [docs/03_USP_UNIQUE_SELLING_PROPOSITION.md](docs/03_USP_UNIQUE_SELLING_PROPOSITION.md) for detailed explanation.

## Token Exchange Reference

The core implementation is in `src/genie_api_obo_rls/core/token_exchange.py`. The important detail is that the exchange uses the **Databricks account-level token endpoint** and intentionally does **not** send `client_id` or `client_secret`.

That is what preserves the signed-in user's identity:

```python
url = f"https://accounts.azuredatabricks.net/oidc/accounts/{account_id}/v1/token"

data = {
    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
    "subject_token": aad_token,
    "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
    "scope": "all-apis",
}

response = requests.post(
    url,
    data=data,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    timeout=30,
)
```

Do not add `client_id` or `client_secret` to this request. Including either changes the exchange pattern toward service-principal identity, which breaks the intended Unity Catalog behavior where `current_user()` resolves to the end user and RLS policies apply to that user.

The full Teams/API flow uses the same pattern through `exchange_aad_for_databricks_token_async()` in `src/genie_api_obo_rls/auth.py`.

## Features

- **Natural Language Queries** - Ask Genie questions through Teams or API
- **User Identity (RLS)** - Each user sees only their authorized data
- **Conversation Resumption** - Continue where you left off after logout/login
- **Suggested Questions** - Clickable follow-up suggestions from Genie
- **Chart Generation** - Automatic chart recommendations with multiple types
- **CSV/PNG Export** - Download data and charts
- **Silent Token Refresh** - Seamless authentication without prompts

## Quick Start

### 1. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp env.example .env
# Edit .env with your Azure, Databricks, and Bot Framework values.
```

Required values are documented in `env.example` and `docs/10_ENVIRONMENT_VARIABLES.md`. Do not commit `.env`.

### 3. Run Locally

```bash
# Direct API mode
python3 -m genie_api_obo_rls.main server --mode api --port 8000

# Teams bot mode
python3 -m genie_api_obo_rls.main server --mode bot --port 8000
```

Health checks are available at `http://127.0.0.1:8000/healthz` and `http://127.0.0.1:8000/v1/healthz`.

### 4. Optional Standalone Example

For the smallest possible reference implementation, see `examples/golden_nugget.py`.

## Project Structure

```
genie_api_obo_rls/
├── src/genie_api_obo_rls/
│   ├── core/                     # Reusable components
│   │   ├── token_exchange.py     # OBO flow (the USP)
│   │   ├── genie_client.py       # Genie API wrapper
│   │   └── config.py             # Configuration
│   │
│   ├── enterprise/               # Production features
│   │   ├── cache.py              # Token caching (memory)
│   │   ├── cache_redis.py        # Token caching (Redis)
│   │   └── circuit_breaker.py    # Resilience
│   │
│   ├── api.py                    # FastAPI endpoints
│   ├── bot.py                    # Teams Bot handler
│   └── main.py                   # Entry point
│
├── examples/                     # Usage examples
├── tests/                        # Unit tests
├── scripts/sql/                  # Databricks RLS setup
└── docs/                         # Documentation
```

## Documentation

| Document | Description |
|----------|-------------|
| [docs/01_ARCHITECTURE.md](docs/01_ARCHITECTURE.md) | System architecture and request flow |
| [docs/02_COMPLETE_IMPLEMENTATION_GUIDE.md](docs/02_COMPLETE_IMPLEMENTATION_GUIDE.md) | End-to-end Azure, Databricks, and Teams setup |
| [docs/03_USP_UNIQUE_SELLING_PROPOSITION.md](docs/03_USP_UNIQUE_SELLING_PROPOSITION.md) | Why account-level OBO matters for RLS |
| [docs/09_AZURE_WEBAPP_READINESS_CHECKLIST.md](docs/09_AZURE_WEBAPP_READINESS_CHECKLIST.md) | Deployment readiness checklist |
| [docs/10_ENVIRONMENT_VARIABLES.md](docs/10_ENVIRONMENT_VARIABLES.md) | Complete environment variable reference |
| [docs/11_API_REFERENCE.md](docs/11_API_REFERENCE.md) | REST API reference |
| [docs/13_FAQ.md](docs/13_FAQ.md) | Customer-facing FAQ on source code, Azure Web App, admin tasks, and token claims |

## Key API Endpoints

### Genie Query

```bash
# Start new conversation
curl -X POST https://your-app/v1/genie/ask \
  -H "Authorization: Bearer $AAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me total sales by region"}'

# Continue conversation
curl -X POST https://your-app/v1/genie/ask \
  -H "Authorization: Bearer $AAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Now filter by Q4", "conversation_id": "abc123"}'
```

### Health Check

```bash
curl https://your-app/v1/healthz
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `<your question>` | Query Genie |
| `new` / `reset` | Start fresh conversation |
| `history` | List recent conversations |
| `signout` | Sign out |

## Scaling

For multi-instance deployments (Azure App Service scale-out, AKS):

```bash
# Add to .env
REDIS_URL=redis://your-redis:6379/0
```

Then use `RedisCache` instead of `MemoryCache` in your initialization.

## Public Repo Safety

This repository is designed to be configured with placeholders and environment variables. Keep real tokens, client secrets, storage keys, exported cloud resources, and `.env` files out of git.

## License

MIT
