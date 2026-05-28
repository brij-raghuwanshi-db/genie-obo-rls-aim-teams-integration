# Quick Reference Card

## One-Page Summary for Operations

---

## Service URLs

| Environment | URL |
|-------------|-----|
| Health Check | `https://<app>/healthz` |
| Bot Endpoint | `https://<app>/api/messages` |
| API Endpoint | `https://<app>/v1/genie/ask` |

---

## Required Environment Variables

```bash
MICROSOFT_APP_ID=<uuid>
MICROSOFT_APP_PASSWORD=<secret>
MICROSOFT_APP_TENANT_ID=<uuid>
OAUTH_CONNECTION_NAME=databricks-sso
GENIE_DATABRICKS_HOST=https://<workspace>.azuredatabricks.net
GENIE_GENIE_SPACE_ID=<space-id>
DATABRICKS_ACCOUNT_ID=<uuid>
```

---

## Bot Commands

| Command | Action |
|---------|--------|
| `<question>` | Query Genie |
| `new` | Start fresh |
| `history` | List conversations |
| `signout` | Sign out |

---

## Diagnostic Commands

```bash
# Health check
curl https://<app>.azurewebsites.net/healthz

# View logs
az webapp log tail --name <app> --resource-group <rg>

# Restart
az webapp restart --name <app> --resource-group <rg>
```

---

## Common Issues

| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| 401 error | Bad token | Re-authenticate |
| 503 error | Circuit open | Wait 60s |
| No response | Endpoint wrong | Check /api/messages |
| RLS not working | Wrong token type | Check no client_id in exchange |

---

## Key Architecture Points

1. **Token Exchange**: Account-level (NO client_id) = USER identity
2. **RLS**: Enforced by Unity Catalog using `current_user()`
3. **Caching**: 5 min token cache, use Redis for multi-instance
4. **Polling**: Genie is async, polls every 1-60s

---

## Emergency Contacts

| Issue | Contact |
|-------|---------|
| Azure | Microsoft Support |
| Databricks | Databricks Support |
| Application | Your IT Team |

---

## Health Check Response

```json
{"status": "ok", "version": "1.0"}
```

If not OK → Check logs → Restart → Escalate
