# Drawbacks and Limitations

## Overview

This document provides an honest assessment of the limitations, drawbacks, and potential issues with the Genie API OBO RLS service.

---

## Technical Limitations

### 1. Token Exchange Dependency

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Requires Databricks Account Federation | Complex initial setup | One-time configuration |
| Federation Policy must match Azure AD | Configuration errors break auth | Validation scripts provided |
| Account ID must be known | Additional config requirement | Document clearly |

**Detail**: The account-level token exchange is the core innovation, but it requires:
- Databricks Account Console access (admin-level)
- Federation Policy correctly configured
- AIM (Automatic Identity Management) enabled

If any of these are misconfigured, authentication silently falls back to an invalid state.

### 2. Single-Tenant Only

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Azure AD Single Tenant | Can't serve multiple organizations | Deploy per-tenant |
| Federation Policy per tenant | Multi-tenant requires multiple policies | Document pattern |

**Detail**: The service is designed for single-tenant deployments. Multi-tenant scenarios require:
- Separate app registrations per tenant
- Separate Federation policies per tenant
- Routing logic to select correct configuration

### 3. Polling-Based Architecture

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Genie API is async (polling) | Latency 3-60+ seconds | User sees "typing" indicator |
| Long-running queries timeout | 10 minute max | User feedback on timeout |
| Multiple HTTP requests per query | Increased cost/complexity | Connection pooling |

**Detail**: The Databricks Genie API does not support webhooks or streaming. Every query requires:
1. Submit request
2. Poll every 1-60 seconds (exponential backoff)
3. Potentially fetch query results separately

This adds latency and complexity compared to synchronous APIs.

### 4. In-Memory State (Default)

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Token cache per-instance | Cache misses on scale-out | Use Redis |
| Conversation state in memory | Lost on app restart | Databricks stores conversations |
| Bot dialog state in memory | SSO flow may fail on instance switch | User signs in again |

**Detail**: Default deployment uses `MemoryStorage` and `MemoryCache`. In multi-instance deployments:
- User may hit different instance → token re-exchange required
- OAuth dialog state may be lost → user prompted to sign in again

---

## Security Considerations

### 1. Token Caching Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Cached tokens accessible in memory | Low | Short TTL (5 min default) |
| Redis cache compromise | Low | Use Azure Redis with TLS |
| Token leakage in logs | Medium | Sanitize logging |

**Recommendation**: Never log token values. Use Key Vault for secrets.

### 2. Trust in Databricks Federation

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Federation policy misconfiguration | Medium | Validate before production |
| AIM creates unexpected users | Low | Monitor user provisioning |
| Token scope too broad | Medium | Use minimal scopes |

**Detail**: We trust Databricks to correctly validate the Azure AD JWT and issue a user-scoped token. If this is misconfigured, RLS may not work correctly.

### 3. No Request-Level Authentication

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Direct API requires bearer token | N/A | By design |
| Bot Service validates requests | N/A | Bot Framework handles |
| No rate limiting built-in | Medium | Add via API gateway |

**Recommendation**: Deploy behind Azure API Management or similar for rate limiting.

---

## Operational Limitations

### 1. Dependency Chain

```
Teams → Bot Service → App Service → Azure AD → Databricks Account → Databricks Workspace → Genie → Unity Catalog
```

**Impact**: Failure at any point breaks the service.

| Dependency | SLA | Impact if Down |
|------------|-----|----------------|
| Microsoft Teams | 99.9% | Users can't send messages |
| Azure Bot Service | 99.9% | Messages don't reach app |
| Azure App Service | 99.95% | Service unavailable |
| Azure AD | 99.99% | Authentication fails |
| Databricks | Varies | Queries fail |

### 2. No Offline Capability

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Requires live Databricks connection | No cached/offline results | By design |
| Network latency impacts UX | Slower responses | Regional deployment |
| No query result caching | Same query hits Databricks again | Consider response cache |

### 3. Limited Error Information

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Genie errors may be opaque | Hard to debug | Check Databricks audit logs |
| Token exchange errors generic | "Exchange failed" not helpful | Enhanced error handling |
| RLS violations silent | Query returns empty, no error | Document behavior |

---

## Feature Limitations

### 1. Chart Capabilities

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Max 100 rows for charts | Large datasets can't be visualized | Show warning |
| Limited chart types | Only bar, line, pie, scatter, histogram | Sufficient for most cases |
| Static images only | No interactivity | Use CSV export for analysis |
| matplotlib dependency | 30MB+ package | Required for charts |

### 2. Conversation Features

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| No conversation branching | Linear conversation only | By Genie design |
| No conversation sharing | Can't share with colleagues | Export results |
| 5,000 row limit per query | Large exports limited | Pagination not supported |
| No streaming responses | Must wait for full response | Typing indicator |

### 3. Teams Integration

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Adaptive Cards v1.4 only | Some features unavailable | Standard cards work |
| No proactive messaging | Can't push alerts to users | Not in scope |
| File attachments limited | Can't send large files | Use data URLs |
| Group chat limited | Best in 1:1 chat | Document recommendation |

---

## Performance Limitations

### 1. Response Times

| Operation | Typical Time | Worst Case |
|-----------|--------------|------------|
| Token exchange | 200-500ms | 2s |
| Genie query (simple) | 3-10s | 30s |
| Genie query (complex) | 10-30s | 10 min |
| Chart generation | 500ms-2s | 5s |

### 2. Throughput

| Metric | Limit | Source |
|--------|-------|--------|
| Genie queries/minute/workspace | 5 (free tier) | Databricks |
| Bot messages/second | ~5 | Bot Framework |
| Token exchanges/minute | ~100 | Azure AD |

### 3. Scaling Limits

| Configuration | Max Users | Notes |
|---------------|-----------|-------|
| Single instance + memory cache | ~50 concurrent | Token re-exchange overhead |
| Single instance + Redis | ~100 concurrent | App Service limits |
| Multi-instance + Redis | ~500 concurrent | Need load testing |

---

## Cost Considerations

### Azure Costs

| Resource | Estimated Cost | Notes |
|----------|----------------|-------|
| App Service B2 | ~$70/month | Minimum recommended |
| Bot Service Standard | ~$0.50/1K messages | Volume-based |
| Redis Cache Basic | ~$16/month | If scaling |
| Key Vault | ~$0.03/10K operations | Minimal |
| Application Insights | ~$2.30/GB | Log volume dependent |

### Databricks Costs

| Resource | Estimated Cost | Notes |
|----------|----------------|-------|
| Genie queries | Included in workspace | No extra charge |
| SQL Warehouse | $0.10-0.50/DBU | Query execution |
| Unity Catalog | Included | No extra charge |

---

## Known Issues

### 1. Bot Framework Compatibility

```
botbuilder-core 4.14+ may conflict with typing-extensions on Azure
```
**Workaround**: Pin typing-extensions version or remove pydantic

### 2. matplotlib on Azure

```
matplotlib requires system fonts that may not be present on Azure Linux
```
**Workaround**: Use 'Agg' backend (implemented)

### 3. Redis Connection Pooling

```
High concurrency may exhaust Redis connections
```
**Workaround**: Configure appropriate connection limits

---

## What This Service Does NOT Do

1. **Does not support scheduled queries** - Interactive only
2. **Does not provide data export to external systems** - Users download manually
3. **Does not support custom authentication providers** - Azure AD only
4. **Does not provide admin dashboards** - Use Databricks/Azure Portal
5. **Does not support WebSocket/real-time** - Polling only
6. **Does not handle file uploads** - Text queries only

**Note**: Column masking IS supported via Unity Catalog (uses same `current_user()` identity).

---

## Recommendations for Mitigation

1. **Deploy with Redis** for multi-instance scenarios
2. **Use Key Vault** for all secrets in production
3. **Enable Application Insights** for monitoring
4. **Set up alerts** for authentication failures
5. **Test RLS thoroughly** before production
6. **Document timeouts** for end users
7. **Plan for Databricks maintenance windows**
