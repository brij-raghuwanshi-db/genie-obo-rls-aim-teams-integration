# Unique Selling Proposition (USP)

## The Core Innovation

### One Sentence Summary

**This service enables natural language queries to Databricks Genie through Microsoft Teams while preserving per-user Row-Level Security (RLS) - users see ONLY their authorized data.**

---

## The Problem It Solves

### Traditional Approach (Service Principal)

```
User A → Teams Bot → Service Principal Token → Genie → ALL DATA
User B → Teams Bot → Service Principal Token → Genie → ALL DATA
```

**Problem**: Both users see the same data because the token represents a SERVICE PRINCIPAL, not the user.

### Our Approach (User Identity)

```
User A → Teams Bot → User A's Token → Genie → User A's DATA ONLY
User B → Teams Bot → User B's Token → Genie → User B's DATA ONLY
```

**Solution**: Each user's token preserves their identity, enabling Unity Catalog RLS.

---

## The Technical Innovation

### What Makes This Different

The key innovation is in how we exchange tokens:

```python
# WRONG: Service Principal Token Exchange (identity lost)
data = {
    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
    "subject_token": aad_token,
    "client_id": "sp-client-id",        # ← This makes it SP identity!
    "client_secret": "sp-secret",
}

# CORRECT: Account-Level Token Exchange (identity preserved)
data = {
    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
    "subject_token": aad_token,
    "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
    "scope": "all-apis",
    # NO client_id = USER identity preserved!
}
```

### How Identity Flows

1. **User authenticates** in Teams → Azure AD issues JWT with `oid` claim
2. **JWT is sent** to Databricks Account Federation endpoint (NOT workspace)
3. **Databricks validates** the JWT against the Federation Policy
4. **User is identified** via the `oid` claim using Automatic Identity Management
5. **Token is issued** representing THE USER (not a service principal)
6. **Genie query executes** with `current_user() = 'user@company.com'`
7. **RLS filter applies** → User sees only their data

### The Golden Code

```python
# This is the entire USP in ~10 lines
def exchange_token(aad_token: str, account_id: str) -> str:
    url = f"https://accounts.azuredatabricks.net/oidc/accounts/{account_id}/v1/token"
    
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": aad_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "scope": "all-apis",
        # NO client_id = USER identity
    }
    
    response = requests.post(url, data=data)
    return response.json()["access_token"]  # This token IS the user
```

---

## Business Value

### For End Users

| Benefit | Description |
|---------|-------------|
| **Security** | Users can only see data they're authorized to access |
| **Simplicity** | Ask questions in natural language via Teams |
| **Continuity** | Resume conversations after logout/login |
| **Visualization** | Automatic chart recommendations |

### For Organizations

| Benefit | Description |
|---------|-------------|
| **Compliance** | Data access is audited at user level |
| **Governance** | Unity Catalog RLS enforced automatically |
| **Cost Reduction** | No need for separate per-user deployments |
| **Scalability** | One service handles all users with proper isolation |

### For IT/Security Teams

| Benefit | Description |
|---------|-------------|
| **Auditability** | Every query is traced to a specific user |
| **Least Privilege** | Users automatically get only their rows AND masked columns |
| **Central Control** | RLS + Column Masking policies managed in Unity Catalog |
| **No Secrets Sharing** | No service principal credentials exposed to users |

---

## Comparison Matrix

| Feature | Traditional Bot | This Service |
|---------|-----------------|--------------|
| User Identity | Lost (SP) | Preserved |
| RLS Enforcement | Manual/None | Automatic |
| Column Masking | Manual/None | Automatic |
| Audit Trail | Service-level | User-level |
| Data Isolation | None | Complete |
| Compliance | Weak | Strong |
| Secret Management | Complex | Simple |

---

## Technical Prerequisites

For this to work, you need:

### 1. Databricks Account Federation Policy

```json
{
  "name": "azure-ad-federation",
  "issuer": "https://sts.windows.net/{tenant-id}/",
  "audiences": ["https://azuredatabricks.net"],
  "subject_claim": "oid"
}
```

### 2. Automatic Identity Management (AIM)

- Users are auto-provisioned on first authentication
- No pre-provisioning required
- `oid` claim maps to Databricks user

### 3. Unity Catalog RLS + Column Masking

```sql
-- Row filter using current_user()
CREATE FUNCTION rls_filter() RETURNS BOOLEAN
RETURN owner = current_user();

ALTER TABLE my_table SET ROW FILTER rls_filter ON ();

-- Column mask using current_user() / is_member()
CREATE FUNCTION mask_pii(value STRING) RETURNS STRING
RETURN CASE 
  WHEN is_member('pii_viewers') OR current_user() = owner THEN value
  ELSE '***MASKED***'
END;

ALTER TABLE my_table ALTER COLUMN ssn SET MASK mask_pii;
```

Both row filters and column masks are enforced because `current_user()` returns the actual user's identity.

---

## Real-World Example

### Scenario: Sales Data

**Table**: `sales.orders`
**RLS Filter**: `WHERE sales_rep_email = current_user()`

**User A (alice@company.com) asks**: "Show me my Q4 sales"
```
Result: Alice's orders only
| order_id | amount | sales_rep_email      |
|----------|--------|----------------------|
| 1001     | 5000   | alice@company.com    |
| 1003     | 7500   | alice@company.com    |
```

**User B (bob@company.com) asks**: "Show me my Q4 sales"
```
Result: Bob's orders only
| order_id | amount | sales_rep_email    |
|----------|--------|--------------------|
| 1002     | 3000   | bob@company.com    |
| 1004     | 2500   | bob@company.com    |
```

**Same query, same Genie Space, different results** - that's the USP.

---

## Why This Matters

### Without This Service

- Build separate deployments per user
- OR give everyone access to all data
- OR build complex middleware to filter results
- OR don't use Genie for sensitive data

### With This Service

- One deployment serves all users
- Each user sees only their data
- RLS is enforced at the database level
- Full audit trail per user

---

## Summary

**The USP is user identity preservation through account-level token federation, enabling per-user Row-Level Security in Databricks Genie queries from Microsoft Teams.**

Everything else in this project (charts, conversations, Teams UI) is just UX on top of this core innovation.
