# FAQ: Genie Teams Integration with OBO, RLS, and AIM

This FAQ answers common customer questions about using this repository to build a Microsoft Teams integration for Databricks Genie while preserving end-user identity for Unity Catalog permissions and row-level security.

## Is the source code available?

Yes. The source code is in this public GitHub repository:

`https://github.com/brij-raghuwanshi-db/genie-obo-rls-aim-teams-integration`

Key files to review:

- `src/genie_api_obo_rls/bot.py`: Microsoft Teams Bot Framework handler.
- `src/genie_api_obo_rls/api.py`: Direct FastAPI endpoint for Genie queries.
- `src/genie_api_obo_rls/auth.py`: Teams SSO token retrieval, Databricks token exchange, retry, circuit breaker, and token cache.
- `src/genie_api_obo_rls/core/token_exchange.py`: Minimal reference implementation of the OBO token exchange.
- `src/genie_api_obo_rls/genie.py`: Databricks Genie Conversation API client.
- `env.example`: Placeholder environment variables.

## Can this be discussed with a customer or Cx?

Yes. The repository is intended to be customer-shareable. It contains placeholder-based configuration, public setup documentation, and no checked-in secrets.

Useful discussion docs:

- `README.md`: quick overview, setup, and token exchange reference.
- `docs/01_ARCHITECTURE.md`: architecture and request flow.
- `docs/02_COMPLETE_IMPLEMENTATION_GUIDE.md`: end-to-end setup.
- `docs/03_USP_UNIQUE_SELLING_PROPOSITION.md`: why account-level OBO matters.
- `docs/04_DRAWBACKS_AND_LIMITATIONS.md`: limitations and caveats.
- `docs/05_ENTERPRISE_FEASIBILITY.md`: production readiness considerations.
- `docs/06_SECURITY_AUDIT.md`: security posture and recommendations.

## Do we need Azure Web App?

Not strictly. You need a backend service that can receive Bot Framework messages over public HTTPS and call Databricks Genie. This repository uses Azure App Service / Azure Web App because it is simple, common for Teams Bot deployments, and works well with environment variables, managed identity, Key Vault, and Application Insights.

Azure Web App is the documented path in this repo, but equivalent hosting options can work:

- Azure App Service / Web App: recommended default for this sample.
- Azure Container Apps: good if you prefer container deployment.
- AKS: useful for enterprise Kubernetes environments.
- Azure Functions: possible, but Bot Framework state, long-running Genie polling, and async request behavior need extra care.
- Any HTTPS service: acceptable if it can host the Bot Framework endpoint and satisfy customer network/security requirements.

For Teams, the important requirement is the bot messaging endpoint, for example:

```text
https://<your-host>/api/messages
```

For direct API access, the service exposes:

```text
https://<your-host>/v1/genie/ask
```

## What Azure admin involvement is required?

Usually, yes. An Azure administrator or application administrator is needed for tenant-level application and bot setup.

Typical Azure admin tasks:

- Create or approve the Azure App Registration.
- Configure the App ID URI, usually `api://<your-app-id>`.
- Add the `access_as_user` exposed API scope.
- Configure redirect URI `https://token.botframework.com/.auth/web/redirect`.
- Create a client secret or configure a more secure credential pattern.
- Grant admin consent for required delegated permissions such as `openid`, `profile`, `email`, and `User.Read`.
- Create and configure Azure Bot Service.
- Configure the Bot OAuth connection with Azure AD v2.
- Enable the Teams channel.
- Provision hosting, such as Azure Web App, Container Apps, or another HTTPS host.
- Optionally configure Key Vault, managed identity, Application Insights, networking, and access restrictions.

## Do we need to add the email optional claim to the access token?

It depends on which claim your Databricks federation policy uses as the subject.

This repository's main implementation and guide use `oid` as the subject claim because the Azure AD object ID is stable and works well with AIM-based user matching:

```json
{
  "issuer": "https://sts.windows.net/<your-tenant-id>/",
  "audiences": ["api://<your-app-id>"],
  "subject_claim": "oid"
}
```

If your customer chooses `subject_claim = email`, then the Azure AD access token must reliably contain an `email` claim, and that value must match the Databricks user identity expected by the account/workspace. In that design, adding the `email` optional claim to the access token is typically required.

Do not mix these approaches accidentally. Pick one subject claim, configure the Azure token claims accordingly, and verify token exchange plus `current_user()` behavior end to end.

## Should the federation policy use `oid` or `email`?

Use the claim that matches the customer's identity governance model.

`oid` is often preferred when:

- You want a stable Azure AD object identifier.
- Users may change email addresses.
- AIM and identity federation are expected to map users based on stable Entra ID identity.

`email` can be appropriate when:

- Databricks users are governed by email address.
- The access token reliably includes the `email` claim.
- The customer has confirmed that the email value matches Databricks user identities.

The repo defaults to the `oid` pattern in `docs/02_COMPLETE_IMPLEMENTATION_GUIDE.md`. If using `email`, update the federation policy and Azure optional claims consistently.

## What Databricks admin involvement is required?

A Databricks account admin is typically required.

Typical Databricks admin tasks:

- Enable identity federation / AIM in the Databricks Account Console.
- Create the federation policy with the Azure AD issuer, audience, and subject claim.
- Confirm users can be matched or provisioned through AIM.
- Ensure the workspace is Unity Catalog-enabled.
- Grant the right workspace, catalog, schema, table, SQL warehouse, and Genie Space permissions.
- Configure Unity Catalog row filters or other access controls.
- Validate that `current_user()` resolves to the end user, not the bot or service principal.

Workspace admins or data owners may also be needed to configure Genie Spaces, SQL warehouses, Unity Catalog grants, and RLS policies.

## Apart from the listed steps, what else might need admin involvement?

Common additional approvals include:

- Security review for public endpoint exposure.
- Network controls, private endpoint, firewall, or IP allowlist decisions.
- Key Vault ownership and secret rotation policy.
- Application Insights or centralized logging approval.
- Teams app publishing or organizational Teams policy approval.
- Production change management and support ownership.
- Data access approval for Genie Spaces, Unity Catalog objects, and SQL warehouses.

## What is the most important token exchange detail?

The backend exchanges the user's Azure AD access token at the Databricks account-level token endpoint and does not send `client_id` or `client_secret` in that token exchange request.

Reference:

```python
url = f"https://accounts.azuredatabricks.net/oidc/accounts/{account_id}/v1/token"

data = {
    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
    "subject_token": aad_token,
    "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
    "scope": "all-apis",
}
```

This is the critical pattern that preserves user identity for Unity Catalog access checks and RLS.

## How do we validate that RLS is working?

Use a test user with limited data access and ask Genie a question that should only return that user's rows.

Recommended validation:

- Confirm the Teams user signs in through the Bot OAuth connection.
- Confirm token exchange succeeds.
- In Databricks, verify `current_user()` resolves to the end user's identity.
- Query a table with a Unity Catalog row filter.
- Compare results across two users with different entitlements.
- Confirm the bot never uses a service principal token to query Genie on behalf of all users.

## Does this repository include production hardening?

It includes a production-oriented baseline, not a turnkey enterprise platform.

Included:

- Teams Bot Framework integration.
- Direct FastAPI API.
- Account-level OBO token exchange.
- In-memory token cache.
- Retry and circuit breaker behavior.
- Optional Key Vault and Application Insights integration.
- Chart and CSV/PNG export helpers.
- Deployment and readiness docs.

Common production additions:

- Redis or another distributed cache for multi-instance deployments.
- Stronger operational dashboards and alerting.
- Private networking and IP restrictions.
- CI/CD pipeline.
- Automated tests in the customer's environment.
- Formal Teams app packaging and tenant publishing process.
