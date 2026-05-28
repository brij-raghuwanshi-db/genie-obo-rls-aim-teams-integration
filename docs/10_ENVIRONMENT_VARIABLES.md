# Complete Environment Variables Reference

## Overview

This document lists all environment variables required and optional for the Genie API OBO RLS service.

---

## Quick Reference

### Required Variables

| Variable | Example | Source |
|----------|---------|--------|
| `MICROSOFT_APP_ID` | `12345678-1234-...` | Azure AD App Registration |
| `MICROSOFT_APP_PASSWORD` | `secret-value` | Azure AD App Registration |
| `MICROSOFT_APP_TENANT_ID` | `87654321-4321-...` | Azure AD |
| `OAUTH_CONNECTION_NAME` | `databricks-sso` | Azure Bot Service |
| `GENIE_DATABRICKS_HOST` | `https://workspace.azuredatabricks.net` | Databricks Workspace |
| `GENIE_GENIE_SPACE_ID` | `01abc234def567...` | Databricks Genie |
| `DATABRICKS_ACCOUNT_ID` | `11111111-2222-...` | Databricks Account |

### Optional Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GENIE_TOKEN_EXCHANGE_URL` | Auto-constructed | Custom token endpoint |
| `GENIE_TOKEN_SCOPE` | `all-apis` | Token scope |
| `GENIE_TOKEN_AUDIENCE` | (none) | Token audience |
| `GENIE_CACHE_TTL_SECONDS` | `300` | Token cache lifetime |
| `REDIS_URL` | (none) | Distributed cache |
| `AZURE_KEYVAULT_URL` | (none) | Key Vault endpoint |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | (none) | Monitoring |
| `APP_SERVICE_URL` | (none) | Public URL |

---

## Detailed Reference

### Bot Framework Configuration

#### MICROSOFT_APP_ID

**Required**: Yes

**Description**: The Application (client) ID from your Azure AD App Registration. This identifies your bot to the Microsoft Bot Framework.

**Source**: Azure Portal → Azure Active Directory → App registrations → Your app → Overview → Application (client) ID

**Example**:
```
MICROSOFT_APP_ID=12345678-1234-1234-1234-123456789012
```

**Format**: UUID/GUID

---

#### MICROSOFT_APP_PASSWORD

**Required**: Yes

**Description**: The client secret from your Azure AD App Registration. This authenticates your bot to the Microsoft Bot Framework.

**Source**: Azure Portal → Azure Active Directory → App registrations → Your app → Certificates & secrets → Client secrets

**Example**:
```
MICROSOFT_APP_PASSWORD=abc123~secret~value
```

**Security**:
- Store in Azure Key Vault for production
- Rotate regularly (every 6-12 months)
- Never commit to source control

---

#### MICROSOFT_APP_TENANT_ID

**Required**: Yes (for Single Tenant)

**Description**: Your Azure AD tenant ID. Required for single-tenant bot applications.

**Source**: Azure Portal → Azure Active Directory → Overview → Tenant ID

**Example**:
```
MICROSOFT_APP_TENANT_ID=87654321-4321-4321-4321-210987654321
```

**Format**: UUID/GUID

---

#### OAUTH_CONNECTION_NAME

**Required**: Yes

**Description**: The name of the OAuth connection configured in Azure Bot Service. This enables SSO between Teams and Databricks.

**Source**: Azure Portal → Bot Services → Your bot → Configuration → OAuth connection settings → Name

**Example**:
```
OAUTH_CONNECTION_NAME=databricks-sso
```

**Default**: `databricks-sso`

**Notes**:
- Must match exactly (case-sensitive)
- Connection must be configured with correct scopes

---

### Databricks Configuration

#### GENIE_DATABRICKS_HOST

**Required**: Yes

**Description**: The full URL of your Databricks workspace.

**Source**: Databricks workspace URL (in browser)

**Example**:
```
GENIE_DATABRICKS_HOST=https://adb-1234567890123456.12.azuredatabricks.net
```

**Format**: Full URL with https://

**Notes**:
- Include `https://`
- No trailing slash
- Use the workspace URL, not the account console URL

---

#### GENIE_GENIE_SPACE_ID

**Required**: Yes

**Description**: The unique identifier of your Genie Space.

**Source**: Databricks Workspace → AI/BI → Genie → Your Space → URL contains space ID

**Example**:
```
GENIE_GENIE_SPACE_ID=01efcd234567890abcdef
```

**Format**: Alphanumeric string

**Notes**:
- Found in the URL when viewing the Genie Space
- Example URL: `https://workspace.databricks.net/genie/spaces/01efcd234567890abcdef`

---

#### DATABRICKS_ACCOUNT_ID

**Required**: Yes

**Description**: Your Databricks Account ID. Used for account-level token federation (the USP).

**Source**: Databricks Account Console → URL or Settings

**Example**:
```
DATABRICKS_ACCOUNT_ID=11111111-2222-3333-4444-555555555555
```

**Format**: UUID/GUID

**Notes**:
- This is the ACCOUNT ID, not the workspace ID
- Found at: accounts.azuredatabricks.net in the URL or settings
- Required for user identity preservation

---

### Token Exchange Configuration

#### GENIE_TOKEN_EXCHANGE_URL

**Required**: No (auto-constructed from DATABRICKS_ACCOUNT_ID)

**Description**: Custom token exchange endpoint URL. If not set, it's automatically constructed from DATABRICKS_ACCOUNT_ID.

**Auto-constructed format**:
```
https://accounts.azuredatabricks.net/oidc/accounts/{DATABRICKS_ACCOUNT_ID}/v1/token
```

**Example** (if you need to override):
```
GENIE_TOKEN_EXCHANGE_URL=https://accounts.azuredatabricks.net/oidc/accounts/11111111-2222-3333-4444-555555555555/v1/token
```

**Notes**:
- Usually not needed
- Only set if you have a custom federation endpoint

---

#### GENIE_TOKEN_SCOPE

**Required**: No

**Description**: OAuth scope for the Databricks token.

**Example**:
```
GENIE_TOKEN_SCOPE=all-apis
```

**Default**: `all-apis`

**Options**:
- `all-apis` - Full access (recommended)
- Custom scopes if configured

---

#### GENIE_TOKEN_AUDIENCE

**Required**: No

**Description**: Optional audience claim for the token exchange.

**Example**:
```
GENIE_TOKEN_AUDIENCE=
```

**Default**: Empty (not included in request)

**Notes**:
- Usually not needed
- Only set if required by your federation policy

---

#### GENIE_CACHE_TTL_SECONDS

**Required**: No

**Description**: How long to cache exchanged tokens (in seconds).

**Example**:
```
GENIE_CACHE_TTL_SECONDS=300
```

**Default**: `300` (5 minutes)

**Range**: 30 - 3600

**Notes**:
- Lower values = more token exchanges, more security
- Higher values = fewer exchanges, tokens cached longer
- 300 seconds (5 minutes) is a good balance

---

### Scaling Configuration

#### REDIS_URL

**Required**: No (required for multi-instance)

**Description**: Redis connection URL for distributed token caching.

**Examples**:
```bash
# Local Redis
REDIS_URL=redis://localhost:6379/0

# Azure Redis Cache (with password)
REDIS_URL=redis://:your-access-key@your-redis.redis.cache.windows.net:6380/0?ssl=true

# Azure Redis Cache (connection string format)
REDIS_URL=rediss://:your-access-key@your-redis.redis.cache.windows.net:6380/0
```

**Format**: `redis://[username:password@]host:port/db[?options]`

**Notes**:
- Required when running multiple App Service instances
- Use `rediss://` or `?ssl=true` for TLS connections
- Azure Redis requires the access key as password

---

### Azure Services Configuration

#### AZURE_KEYVAULT_URL

**Required**: No (recommended for production)

**Description**: Azure Key Vault URL for secret management.

**Example**:
```
AZURE_KEYVAULT_URL=https://my-keyvault.vault.azure.net/
```

**Format**: Full URL with https://

**Notes**:
- App Service managed identity must have Key Vault access
- Secrets are loaded on startup and set as environment variables
- Secret name mappings are predefined in the code

**Key Vault Secret Names**:
| Secret Name | Maps To |
|-------------|---------|
| `genie-databricks-host` | `GENIE_DATABRICKS_HOST` |
| `genie-space-id` | `GENIE_GENIE_SPACE_ID` |
| `genie-token-exchange-url` | `GENIE_TOKEN_EXCHANGE_URL` |
| `microsoft-app-id` | `MICROSOFT_APP_ID` |
| `microsoft-app-password` | `MICROSOFT_APP_PASSWORD` |

---

#### APPLICATIONINSIGHTS_CONNECTION_STRING

**Required**: No (recommended for production)

**Description**: Azure Application Insights connection string for telemetry and monitoring.

**Source**: Azure Portal → Application Insights → Your resource → Overview → Connection String

**Example**:
```
APPLICATIONINSIGHTS_CONNECTION_STRING="<your-application-insights-connection-string>"
```

**Notes**:
- Enables custom events, exceptions, and traces
- Integrates with Azure Monitor
- Use connection string, not just instrumentation key

---

#### APP_SERVICE_URL

**Required**: No

**Description**: The public URL of your App Service. Used for generating callback URLs.

**Example**:
```
APP_SERVICE_URL=https://genie-api-obo-rls.azurewebsites.net
```

**Notes**:
- Usually not required
- May be needed for custom OAuth flows

---

## Deprecated / Unused Variables

The following variables may appear in older configurations or documentation but are **NOT used** by the current implementation.

### GENIE_OAUTH_CLIENT_ID

**Status**: DEPRECATED - NOT USED

**Reason**: This was used in an earlier Service Principal federation approach. The current Account-Level federation does NOT send `client_id` in the token exchange request - this is what preserves user identity.

**Do NOT set this variable.** If set, it will be ignored.

---

### GENIE_OAUTH_CLIENT_SECRET

**Status**: DEPRECATED - NOT USED

**Reason**: Same as above. Service Principal credentials are not used with Account-Level federation.

**Do NOT set this variable.** If set, it will be ignored.

---

### Historical Context

The project evolved through these approaches:

| Approach | Variables Used | Identity |
|----------|---------------|----------|
| Service Principal (old) | `GENIE_OAUTH_CLIENT_ID`, `GENIE_OAUTH_CLIENT_SECRET` | Service Principal |
| Account-Level Federation (current) | `DATABRICKS_ACCOUNT_ID` only | USER (preserved) |

The Account-Level approach was adopted because it preserves the user's identity for RLS enforcement. The Service Principal approach would execute all queries as the service principal, defeating RLS.

---

## Azure CLI Configuration Command

```bash
# Set all required variables at once
az webapp config appsettings set \
  --name genie-api-obo-rls \
  --resource-group rg-genie-prod \
  --settings \
    MICROSOFT_APP_ID="12345678-1234-1234-1234-123456789012" \
    MICROSOFT_APP_PASSWORD="your-secret-here" \
    MICROSOFT_APP_TENANT_ID="87654321-4321-4321-4321-210987654321" \
    OAUTH_CONNECTION_NAME="databricks-sso" \
    GENIE_DATABRICKS_HOST="https://your-workspace.azuredatabricks.net" \
    GENIE_GENIE_SPACE_ID="01efcd234567890abcdef" \
    DATABRICKS_ACCOUNT_ID="11111111-2222-3333-4444-555555555555" \
    GENIE_CACHE_TTL_SECONDS="300"
```

---

## Environment Variable JSON Template

For deployment automation, use this JSON template:

```json
{
  "MICROSOFT_APP_ID": "12345678-1234-1234-1234-123456789012",
  "MICROSOFT_APP_PASSWORD": "your-secret-here",
  "MICROSOFT_APP_TENANT_ID": "87654321-4321-4321-4321-210987654321",
  "OAUTH_CONNECTION_NAME": "databricks-sso",
  "GENIE_DATABRICKS_HOST": "https://your-workspace.azuredatabricks.net",
  "GENIE_GENIE_SPACE_ID": "01efcd234567890abcdef",
  "DATABRICKS_ACCOUNT_ID": "11111111-2222-3333-4444-555555555555",
  "GENIE_CACHE_TTL_SECONDS": "300",
  "AZURE_KEYVAULT_URL": "",
  "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
  "REDIS_URL": ""
}
```

Save as `app-settings.json` and deploy:

```bash
az webapp config appsettings set \
  --name genie-api-obo-rls \
  --resource-group rg-genie-prod \
  --settings @app-settings.json
```

---

## Validation Script

```bash
#!/bin/bash
# validate-env.sh - Check required environment variables

REQUIRED_VARS=(
  "MICROSOFT_APP_ID"
  "MICROSOFT_APP_PASSWORD"
  "MICROSOFT_APP_TENANT_ID"
  "OAUTH_CONNECTION_NAME"
  "GENIE_DATABRICKS_HOST"
  "GENIE_GENIE_SPACE_ID"
  "DATABRICKS_ACCOUNT_ID"
)

MISSING=0

for VAR in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!VAR}" ]; then
    echo "❌ Missing: $VAR"
    MISSING=$((MISSING + 1))
  else
    echo "✅ Set: $VAR"
  fi
done

if [ $MISSING -gt 0 ]; then
  echo ""
  echo "⚠️  $MISSING required variables are missing"
  exit 1
else
  echo ""
  echo "✅ All required variables are set"
  exit 0
fi
```

---

## Security Best Practices

1. **Never commit secrets** - Use `.gitignore` for `.env` files
2. **Use Key Vault** - Store secrets in Azure Key Vault
3. **Rotate regularly** - Change `MICROSOFT_APP_PASSWORD` every 6-12 months
4. **Principle of least privilege** - Only grant necessary permissions
5. **Audit access** - Monitor who accesses Key Vault secrets
