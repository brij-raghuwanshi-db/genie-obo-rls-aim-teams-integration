# Azure Web Apps Deployment Readiness Checklist

## Pre-Deployment Validation

This checklist ensures the application is ready for Azure Web Apps deployment.

---

## Application Readiness

### Code Quality

- [x] **Python 3.11+ compatible** - Uses modern Python features
- [x] **No hardcoded secrets** - All configuration via environment variables
- [x] **Startup script provided** - `startup.sh` for Azure
- [x] **Health endpoint available** - `/healthz` returns status
- [x] **Dependencies declared** - `requirements.txt` up to date
- [x] **No local file dependencies** - Stateless design
- [x] **Logging to stdout/stderr** - Azure captures automatically
- [x] **Graceful error handling** - Returns proper HTTP codes

### Dependencies Review

| Package | Purpose | Azure Compatible |
|---------|---------|------------------|
| fastapi | REST API | ✅ |
| uvicorn | ASGI server | ✅ |
| aiohttp | Async HTTP | ✅ |
| requests | Sync HTTP | ✅ |
| httpx | Async HTTP | ✅ |
| botbuilder-core | Bot Framework | ✅ |
| botbuilder-dialogs | OAuth | ✅ |
| azure-identity | Managed Identity | ✅ |
| azure-keyvault-secrets | Key Vault | ✅ |
| matplotlib | Charts | ✅ (use Agg backend) |
| opencensus-ext-azure | App Insights | ✅ |

### Known Azure Compatibility Issues

| Issue | Solution | Status |
|-------|----------|--------|
| typing-extensions conflict | Removed pydantic | ✅ Resolved |
| matplotlib display backend | Use 'Agg' backend | ✅ Implemented |
| Bot Framework tenant | Set channel_auth_tenant | ✅ Implemented |

---

## Azure Resource Checklist

### Required Resources

- [ ] **Resource Group** - Logical container
- [ ] **App Service Plan** - Linux, Python 3.11
- [ ] **App Service** - Web application
- [ ] **Bot Service** - Azure Bot registration
- [ ] **Azure AD App Registration** - Authentication

### Optional Resources

- [ ] **Key Vault** - Secret management (recommended)
- [ ] **Application Insights** - Monitoring (recommended)
- [ ] **Redis Cache** - Distributed caching (for scaling)
- [ ] **Virtual Network** - Network isolation (enterprise)

---

## Configuration Checklist

### App Service Configuration

```bash
# Verify these settings
az webapp config show --name <app-name> --resource-group <rg-name>
```

| Setting | Required Value | Status |
|---------|---------------|--------|
| Python Version | 3.11 | [ ] |
| Linux FX Version | PYTHON|3.11 | [ ] |
| Always On | true (production) | [ ] |
| HTTPS Only | true | [ ] |
| Startup Command | startup.sh | [ ] |
| SCM Type | LocalGit or Zip | [ ] |

### Environment Variables

Run this to verify all required variables:

```bash
az webapp config appsettings list \
  --name <app-name> \
  --resource-group <rg-name> \
  --output table
```

Required variables (see [Environment Variables doc](10_ENVIRONMENT_VARIABLES.md)):

- [ ] MICROSOFT_APP_ID
- [ ] MICROSOFT_APP_PASSWORD
- [ ] MICROSOFT_APP_TENANT_ID
- [ ] OAUTH_CONNECTION_NAME
- [ ] GENIE_DATABRICKS_HOST
- [ ] GENIE_GENIE_SPACE_ID
- [ ] DATABRICKS_ACCOUNT_ID

---

## Security Checklist

### App Service Security

- [ ] **HTTPS Only** enabled
- [ ] **TLS 1.2** minimum version
- [ ] **Managed Identity** enabled
- [ ] **IP restrictions** configured (if required)
- [ ] **VNet integration** enabled (if required)

```bash
# Enable HTTPS only
az webapp update \
  --name <app-name> \
  --resource-group <rg-name> \
  --https-only true

# Set minimum TLS version
az webapp config set \
  --name <app-name> \
  --resource-group <rg-name> \
  --min-tls-version 1.2

# Enable managed identity
az webapp identity assign \
  --name <app-name> \
  --resource-group <rg-name>
```

### Key Vault Integration (if using)

```bash
# Grant Key Vault access to managed identity
az keyvault set-policy \
  --name <keyvault-name> \
  --object-id <managed-identity-principal-id> \
  --secret-permissions get list
```

### Azure AD App Security

- [ ] **Single tenant** only
- [ ] **Admin consent** granted for permissions
- [ ] **Client secret** not expired
- [ ] **Redirect URIs** configured correctly

---

## Bot Service Checklist

### Configuration

- [ ] **Messaging endpoint** set to `https://<app-name>.azurewebsites.net/api/messages`
- [ ] **App ID** matches Azure AD app
- [ ] **Tenant ID** matches Azure AD tenant

### OAuth Connection

- [ ] **Connection name** matches `OAUTH_CONNECTION_NAME`
- [ ] **Service provider** is Azure AD v2
- [ ] **Scopes** include required permissions
- [ ] **Test connection** succeeds

### Teams Channel

- [ ] **Teams channel** enabled
- [ ] **Terms accepted**
- [ ] **Bot manifest** created (if custom)

---

## Monitoring Checklist

### Application Insights (if using)

- [ ] **Connection string** in environment variables
- [ ] **Live metrics** showing data
- [ ] **Custom events** appearing (BotServerStarted, etc.)

### Alerts (recommended)

| Alert | Condition | Action |
|-------|-----------|--------|
| Error rate | >5% in 5 min | Email |
| Response time | >30s avg | Email |
| Availability | <99% | Email + SMS |
| Token exchange failures | >10 in 10 min | Email |

### Log Setup

```bash
# Enable application logging
az webapp log config \
  --name <app-name> \
  --resource-group <rg-name> \
  --application-logging filesystem \
  --level information \
  --detailed-error-messages true \
  --failed-request-tracing true
```

---

## Deployment Verification

### Step 1: Health Check

```bash
# After deployment, verify health
curl https://<app-name>.azurewebsites.net/healthz
# Expected: {"status": "ok", "version": "1.0"}
```

### Step 2: Bot Framework Validation

```bash
# In Azure Portal, Bot Service > Test in Web Chat
# Send: Hello
# Expected: Welcome message
```

### Step 3: Token Exchange Test

1. Send a query in Teams
2. Sign in if prompted
3. Verify results return

### Step 4: RLS Validation

1. Query data that has RLS filters
2. Verify user sees only their data
3. Test with different users if possible

---

## Scaling Readiness

### Single Instance (Default)

- [ ] Memory cache configured
- [ ] Works for <100 concurrent users
- [ ] No additional configuration needed

### Multi-Instance (Scaled)

- [ ] Redis Cache deployed
- [ ] `REDIS_URL` environment variable set
- [ ] Update code to use `RedisCache` instead of `MemoryCache`
- [ ] Session affinity disabled
- [ ] Auto-scale rules configured

```bash
# Configure auto-scaling
az monitor autoscale create \
  --resource-group <rg-name> \
  --resource <app-service-plan-name> \
  --resource-type Microsoft.Web/serverfarms \
  --name autoscale-<app-name> \
  --min-count 2 \
  --max-count 10 \
  --count 2

az monitor autoscale rule create \
  --resource-group <rg-name> \
  --autoscale-name autoscale-<app-name> \
  --condition "CpuPercentage > 70 avg 10m" \
  --scale out 1
```

---

## Pre-Go-Live Checklist

### Functional Testing

- [ ] Health endpoint responds
- [ ] Bot welcome message works
- [ ] SSO sign-in completes
- [ ] Simple query returns results
- [ ] Complex query returns results
- [ ] Charts generate correctly
- [ ] CSV download works
- [ ] Conversation history works
- [ ] Sign-out works
- [ ] New conversation works

### Non-Functional Testing

- [ ] Response time acceptable (<30s for simple queries)
- [ ] Multiple concurrent users tested
- [ ] Memory usage stable
- [ ] No connection leaks

### Security Testing

- [ ] HTTPS enforcement verified
- [ ] Unauthorized access denied (401)
- [ ] RLS filters working
- [ ] Token expiration handled

### Documentation

- [ ] Runbook created for operations
- [ ] User guide distributed
- [ ] Support contacts identified
- [ ] Escalation path defined

---

## Quick Deployment Commands

```bash
# Full deployment script
RESOURCE_GROUP="rg-genie-prod"
APP_NAME="genie-api-obo-rls"
LOCATION="eastus"

# 1. Create resources
az group create --name $RESOURCE_GROUP --location $LOCATION

az appservice plan create \
  --name asp-genie-prod \
  --resource-group $RESOURCE_GROUP \
  --sku B2 \
  --is-linux

az webapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan asp-genie-prod \
  --runtime "PYTHON:3.11"

# 2. Configure
az webapp config set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --startup-file "startup.sh"

az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings @app-settings.json

# 3. Deploy code
zip -r deploy.zip . -x "*.git*" -x "*__pycache__*"
az webapp deploy \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --src-path deploy.zip \
  --type zip

# 4. Verify
curl https://$APP_NAME.azurewebsites.net/healthz
```

---

## Rollback Procedure

If deployment fails:

```bash
# List recent deployments
az webapp deployment list \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP

# Redeploy previous version (if using git)
az webapp deployment source sync \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP

# Or rollback using deployment slots
az webapp deployment slot swap \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --slot staging \
  --target-slot production
```

---

## Final Approval

| Item | Verified By | Date |
|------|-------------|------|
| Code Review | | |
| Security Review | | |
| Performance Test | | |
| UAT Sign-off | | |
| Go-Live Approval | | |
