# Genie API OBO RLS - Documentation v2

## Complete Documentation Suite

This directory contains comprehensive documentation for the Genie API OBO RLS service.

---

## Document Index

| # | Document | Description |
|---|----------|-------------|
| 01 | [ARCHITECTURE.md](01_ARCHITECTURE.md) | System architecture, data flows, component diagrams |
| 02 | [COMPLETE_IMPLEMENTATION_GUIDE.md](02_COMPLETE_IMPLEMENTATION_GUIDE.md) | Step-by-step deployment instructions |
| 03 | [USP_UNIQUE_SELLING_PROPOSITION.md](03_USP_UNIQUE_SELLING_PROPOSITION.md) | Core innovation - user identity preservation |
| 04 | [DRAWBACKS_AND_LIMITATIONS.md](04_DRAWBACKS_AND_LIMITATIONS.md) | Honest assessment of limitations |
| 05 | [ENTERPRISE_FEASIBILITY.md](05_ENTERPRISE_FEASIBILITY.md) | Production readiness analysis |
| 06 | [SECURITY_AUDIT.md](06_SECURITY_AUDIT.md) | Security assessment and recommendations |
| 07 | [CURRENT_FEATURES.md](07_CURRENT_FEATURES.md) | Complete feature list |
| 08 | [TEAMS_WEBCHAT_USER_GUIDE.md](08_TEAMS_WEBCHAT_USER_GUIDE.md) | End-user guide for Teams/Web Chat |
| 09 | [AZURE_WEBAPP_READINESS_CHECKLIST.md](09_AZURE_WEBAPP_READINESS_CHECKLIST.md) | Deployment readiness checklist |
| 10 | [ENVIRONMENT_VARIABLES.md](10_ENVIRONMENT_VARIABLES.md) | Complete environment variable reference |
| 11 | [API_REFERENCE.md](11_API_REFERENCE.md) | REST API documentation |
| 12 | [TROUBLESHOOTING.md](12_TROUBLESHOOTING.md) | Common issues and solutions |

---

## Quick Start

### For Developers
1. Read [ARCHITECTURE.md](01_ARCHITECTURE.md) for system overview
2. Follow [COMPLETE_IMPLEMENTATION_GUIDE.md](02_COMPLETE_IMPLEMENTATION_GUIDE.md) for deployment
3. Reference [API_REFERENCE.md](11_API_REFERENCE.md) for integration

### For Operations
1. Review [AZURE_WEBAPP_READINESS_CHECKLIST.md](09_AZURE_WEBAPP_READINESS_CHECKLIST.md) before deployment
2. Configure using [ENVIRONMENT_VARIABLES.md](10_ENVIRONMENT_VARIABLES.md)
3. Use [TROUBLESHOOTING.md](12_TROUBLESHOOTING.md) for issue resolution

### For Security Teams
1. Review [SECURITY_AUDIT.md](06_SECURITY_AUDIT.md) for findings
2. Understand [USP_UNIQUE_SELLING_PROPOSITION.md](03_USP_UNIQUE_SELLING_PROPOSITION.md) for RLS design

### For Business Stakeholders
1. Read [USP_UNIQUE_SELLING_PROPOSITION.md](03_USP_UNIQUE_SELLING_PROPOSITION.md) for value proposition
2. Review [ENTERPRISE_FEASIBILITY.md](05_ENTERPRISE_FEASIBILITY.md) for production readiness
3. Understand [DRAWBACKS_AND_LIMITATIONS.md](04_DRAWBACKS_AND_LIMITATIONS.md) for limitations

### For End Users
1. Follow [TEAMS_WEBCHAT_USER_GUIDE.md](08_TEAMS_WEBCHAT_USER_GUIDE.md) for usage instructions

---

## Project Summary

### What This Project Does

**Genie API OBO RLS** enables natural language queries to Databricks Genie through Microsoft Teams while preserving per-user Row-Level Security (RLS).

### The Core Innovation

When a user asks "Show me my sales data" through Teams:
1. Their Azure AD token is exchanged for a Databricks token **preserving their identity**
2. Genie executes the query **as that user**
3. Unity Catalog RLS ensures they see **only their authorized data**

### Key Features

- Natural language queries via Teams or API
- Per-user Row-Level Security enforcement
- Automatic chart generation
- Conversation resumption
- CSV/PNG export
- Enterprise-grade resilience (circuit breaker, retry, caching)

---

## Architecture at a Glance

```
User → Teams → Bot Service → App Service → Token Exchange → Genie → RLS → Data
                                              │
                                              ▼
                                    User Identity Preserved
                                    current_user() = 'user@company.com'
```

---

## Environment Variables Summary

### Required

```bash
MICROSOFT_APP_ID=<azure-ad-app-id>
MICROSOFT_APP_PASSWORD=<azure-ad-secret>
MICROSOFT_APP_TENANT_ID=<azure-tenant-id>
OAUTH_CONNECTION_NAME=databricks-sso
GENIE_DATABRICKS_HOST=https://workspace.azuredatabricks.net
GENIE_GENIE_SPACE_ID=<genie-space-id>
DATABRICKS_ACCOUNT_ID=<databricks-account-id>
```

### Optional

```bash
GENIE_CACHE_TTL_SECONDS=300
REDIS_URL=redis://localhost:6379/0
AZURE_KEYVAULT_URL=https://keyvault.vault.azure.net/
APPLICATIONINSIGHTS_CONNECTION_STRING=<connection-string>
```

---

## Deployment Quick Reference

```bash
# 1. Deploy App Service
az webapp create --name genie-api --resource-group rg-genie --plan asp-genie --runtime "PYTHON:3.11"

# 2. Configure
az webapp config appsettings set --name genie-api --resource-group rg-genie --settings @settings.json

# 3. Set startup command
az webapp config set --name genie-api --resource-group rg-genie --startup-file "startup.sh"

# 4. Deploy code
zip -r deploy.zip . && az webapp deploy --name genie-api --resource-group rg-genie --src-path deploy.zip --type zip

# 5. Verify
curl https://genie-api.azurewebsites.net/healthz
```

---

## Support

For issues not covered in [TROUBLESHOOTING.md](12_TROUBLESHOOTING.md):

1. Check Azure service health
2. Review Application Insights logs
3. Contact your organization's IT support
4. For Databricks issues: Databricks Support
5. For Bot Framework issues: Microsoft Support

---

## Version

Documentation Version: 2.0
Last Updated: January 2026
