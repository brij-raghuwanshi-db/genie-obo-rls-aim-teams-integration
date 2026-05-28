# Troubleshooting Guide

## Quick Diagnostics

### Health Check

```bash
# Verify service is running
curl https://your-app.azurewebsites.net/healthz
# Expected: {"status": "ok"}
```

### Log Streaming

```bash
# Stream live logs from Azure
az webapp log tail \
  --name genie-api-obo-rls \
  --resource-group rg-genie-prod
```

---

## Common Issues and Solutions

### Authentication Issues

#### Issue: "Missing Authorization header"

**Symptoms**:
- API returns 401
- Error message: "Missing Authorization header"

**Cause**: No bearer token provided in request

**Solution**:
```bash
# Ensure Authorization header is included
curl -X POST https://your-app/v1/genie/ask \
  -H "Authorization: Bearer $AAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "test"}'
```

---

#### Issue: "Invalid Authorization header"

**Symptoms**:
- API returns 401
- Error message: "Invalid Authorization header"

**Cause**: Authorization header format is wrong

**Solution**:
- Use format: `Bearer <token>` (note the space)
- Ensure token is not empty

```bash
# Correct format
Authorization: Bearer eyJ0eXAiOiJKV1...

# Wrong formats
Authorization: eyJ0eXAiOiJKV1...  # Missing "Bearer"
Authorization: bearer eyJ0eXAi...  # Wrong case (may work)
Authorization: Bearer: eyJ0eXA...  # Extra colon
```

---

#### Issue: "Token exchange failed"

**Symptoms**:
- API returns 401
- Error mentions token exchange
- In Teams: "Authentication failed"

**Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| Azure AD token expired | Get fresh token, re-authenticate |
| Federation policy misconfigured | Verify issuer URL matches Azure AD |
| Account ID wrong | Check DATABRICKS_ACCOUNT_ID |
| Network issue | Check App Service can reach Databricks |

**Diagnostic Steps**:

1. **Check token validity**:
   ```bash
   # Decode token (paste at jwt.io)
   echo $AAD_TOKEN | cut -d'.' -f2 | base64 -d 2>/dev/null | jq .
   ```

2. **Verify federation endpoint**:
   ```bash
   curl -X POST https://accounts.azuredatabricks.net/oidc/accounts/$ACCOUNT_ID/v1/token \
     -d "grant_type=urn:ietf:params:oauth:grant-type:token-exchange" \
     -d "subject_token=$AAD_TOKEN" \
     -d "subject_token_type=urn:ietf:params:oauth:token-type:jwt" \
     -d "scope=all-apis"
   ```

3. **Check federation policy in Databricks Account Console**

---

#### Issue: "Service temporarily unavailable (circuit open)"

**Symptoms**:
- API returns 503
- Multiple failures preceded this

**Cause**: Circuit breaker triggered after 5 consecutive failures

**Solution**:
- Wait 60 seconds for circuit to reset
- Check underlying issue (Databricks availability, network)
- Monitor logs for root cause

**Diagnostic**:
```bash
# Check if Databricks is reachable
curl -I https://your-workspace.azuredatabricks.net/
```

---

### Teams Bot Issues

#### Issue: Bot doesn't respond in Teams

**Symptoms**:
- Messages sent but no response
- No error shown

**Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| Messaging endpoint wrong | Check Bot Service config |
| App Service stopped | Restart App Service |
| App ID mismatch | Verify MICROSOFT_APP_ID |

**Diagnostic Steps**:

1. **Verify Bot Service endpoint**:
   - Azure Portal → Bot Services → Configuration
   - Messaging endpoint should be: `https://your-app.azurewebsites.net/api/messages`

2. **Test in Web Chat**:
   - Azure Portal → Bot Services → Test in Web Chat
   - If this works but Teams doesn't, issue is Teams channel config

3. **Check App Service logs**:
   ```bash
   az webapp log tail --name genie-api-obo-rls --resource-group rg-genie
   ```

---

#### Issue: "Please sign in" keeps appearing

**Symptoms**:
- User signs in successfully
- Next message asks to sign in again

**Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| OAuth connection misconfigured | Check scopes in Bot Service |
| Token not being cached | Check cache configuration |
| Multi-instance without Redis | Deploy Redis for session consistency |

**Diagnostic Steps**:

1. **Check OAuth connection in Azure Portal**:
   - Bot Services → Configuration → OAuth connection settings
   - Test Connection should succeed

2. **Verify scopes**:
   ```
   openid profile email https://azuredatabricks.net/user_impersonation
   ```

3. **Check for instance switching** (multi-instance):
   ```bash
   # Add Redis for distributed caching
   REDIS_URL=redis://your-redis:6379/0
   ```

---

#### Issue: Bot returns "Sorry, something went wrong"

**Symptoms**:
- Generic error message
- No specific details

**Cause**: Unhandled exception in bot code

**Solution**:
1. Check Application Insights for exceptions
2. Check App Service logs for stack trace
3. Enable detailed error messages (dev only)

**Diagnostic**:
```bash
# Get detailed logs
az webapp log download \
  --name genie-api-obo-rls \
  --resource-group rg-genie \
  --log-file logs.zip
```

---

### Query Issues

#### Issue: Query times out

**Symptoms**:
- Bot says "Query took too long"
- API returns timeout error

**Cause**: Genie processing exceeded 10 minutes

**Solutions**:
- Simplify the query (fewer joins, less data)
- Ask more specific questions
- Check if SQL Warehouse is running

**Note**: Complex queries requiring data processing across multiple large tables may legitimately take a long time.

---

#### Issue: "No data returned" but data exists

**Symptoms**:
- Query returns empty
- User knows data should exist

**Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| RLS filtering out data | User doesn't have access to that data |
| Wrong table referenced by Genie | Provide more context in question |
| Data doesn't match query criteria | Verify filters |

**How to Verify RLS**:
```sql
-- Run in Databricks as the user
SELECT current_user();
-- Verify this matches the expected email

-- Test the base table access
SELECT COUNT(*) FROM catalog.schema.table;
```

---

#### Issue: Wrong data returned

**Symptoms**:
- Query returns unexpected results
- Data seems to belong to someone else

**CRITICAL**: This could indicate RLS failure

**Immediate Actions**:
1. Stop using the service
2. Check token exchange is NOT including client_id
3. Verify `current_user()` returns correct email in Databricks

**Diagnostic**:
```python
# Check the token being used
import jwt
decoded = jwt.decode(databricks_token, options={"verify_signature": False})
print(decoded.get("sub"))  # Should be user email
```

---

### Chart Issues

#### Issue: Chart doesn't appear

**Symptoms**:
- "Show Chart" clicked but no image
- Error message about chart generation

**Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| >100 rows | Reduce query result size |
| No numeric data | Charts require numbers |
| matplotlib not installed | Check requirements.txt |
| Backend issue | Use 'Agg' backend (default) |

---

#### Issue: Chart looks wrong

**Symptoms**:
- Data displayed incorrectly
- Wrong chart type

**Solution**:
- Click different chart type button
- For complex data, export to CSV and use Excel

---

### Deployment Issues

#### Issue: App Service not starting

**Symptoms**:
- Health check fails
- Logs show startup errors

**Common Causes**:

1. **Missing environment variables**:
   ```bash
   az webapp config appsettings list --name genie-api-obo-rls --resource-group rg-genie
   ```

2. **Startup command wrong**:
   ```bash
   az webapp config show --name genie-api-obo-rls --resource-group rg-genie | jq '.startupFile'
   # Should be: startup.sh
   ```

3. **Dependency installation failed**:
   ```bash
   # Check Kudu logs
   https://your-app.scm.azurewebsites.net/api/deployments
   ```

---

#### Issue: "ModuleNotFoundError"

**Symptoms**:
- App crashes on startup
- Import error in logs

**Cause**: PYTHONPATH not set correctly

**Solution**:
Check `startup.sh` includes:
```bash
export PYTHONPATH="/home/site/wwwroot/src:$PYTHONPATH"
```

---

## Diagnostic Commands

### Azure CLI

```bash
# Check app status
az webapp show --name genie-api-obo-rls --resource-group rg-genie --query state

# View settings
az webapp config appsettings list --name genie-api-obo-rls --resource-group rg-genie -o table

# Restart app
az webapp restart --name genie-api-obo-rls --resource-group rg-genie

# Get logs
az webapp log download --name genie-api-obo-rls --resource-group rg-genie
```

### Application Insights Queries

```kusto
// Recent errors
exceptions
| where timestamp > ago(1h)
| project timestamp, problemId, outerMessage
| order by timestamp desc

// Token exchange failures
traces
| where message contains "Token exchange"
| where severityLevel >= 3
| order by timestamp desc

// Bot events
customEvents
| where name in ("BotServerStarted", "GenieQuery")
| order by timestamp desc
```

### Databricks Queries

```sql
-- Check current user identity
SELECT current_user();

-- Verify RLS is active on a table
SHOW ROW FILTERS ON catalog.schema.table;

-- Test query manually
SELECT * FROM catalog.schema.table LIMIT 10;
```

---

## Escalation Path

### Level 1: Self-Service
- Check this troubleshooting guide
- Review logs in Azure Portal
- Verify environment variables

### Level 2: IT Support
- Check Azure resource health
- Verify network connectivity
- Review Bot Service configuration

### Level 3: Development Team
- Code-level debugging required
- Configuration changes needed
- Bug report submission

### Level 4: External Support
- Databricks Support (Genie API issues)
- Microsoft Support (Bot Framework issues)
- Azure Support (Infrastructure issues)

---

## Log Locations

| Log Type | Location |
|----------|----------|
| Application logs | Azure Portal → App Service → Log stream |
| Deployment logs | Kudu SCM → Deployments |
| Bot Framework logs | Azure Portal → Bot Service → Channels |
| Databricks audit | Databricks Account Console → Audit logs |
| Application Insights | Azure Portal → Application Insights → Logs |

---

## Health Check Script

```python
#!/usr/bin/env python3
"""Health check script for Genie API OBO RLS"""

import os
import requests
import sys

def check_health():
    base_url = os.getenv("APP_URL", "http://localhost:8000")
    
    # 1. Health endpoint
    try:
        r = requests.get(f"{base_url}/healthz", timeout=5)
        if r.status_code == 200:
            print("✅ Health endpoint: OK")
        else:
            print(f"❌ Health endpoint: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint: {e}")
        return False
    
    # 2. Required environment variables
    required = [
        "MICROSOFT_APP_ID",
        "GENIE_DATABRICKS_HOST",
        "DATABRICKS_ACCOUNT_ID",
    ]
    for var in required:
        if os.getenv(var):
            print(f"✅ {var}: Set")
        else:
            print(f"❌ {var}: Missing")
    
    return True

if __name__ == "__main__":
    success = check_health()
    sys.exit(0 if success else 1)
```
