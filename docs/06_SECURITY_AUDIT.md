# Security Audit Report

## Audit Metadata

| Field | Value |
|-------|-------|
| Audit Date | January 2026 |
| Scope | Full source code review |
| Framework | OWASP Top 10, Azure Security Baseline |

---

## Executive Summary

The Genie API OBO RLS service demonstrates **good security practices** with a few areas requiring attention before production deployment.

| Category | Finding Count | Critical | High | Medium | Low |
|----------|---------------|----------|------|--------|-----|
| Authentication | 0 | 0 | 0 | 0 | 0 |
| Authorization | 1 | 0 | 0 | 1 | 0 |
| Input Validation | 0 | 0 | 0 | 0 | 0 |
| Data Protection | 2 | 0 | 1 | 1 | 0 |
| Configuration | 2 | 0 | 0 | 2 | 0 |
| Dependencies | 1 | 0 | 0 | 0 | 1 |
| **Total** | **6** | **0** | **1** | **4** | **1** |

---

## Authentication Analysis

### Azure AD SSO Implementation

**File**: `auth.py`

```python
class TeamsSsoDialog(ComponentDialog):
    """Dialog to handle Teams SSO token acquisition."""
    
    def __init__(self, settings: "BotSettings", genie_settings: "Settings | None" = None):
        super().__init__(TeamsSsoDialog.__name__)
        self._connection_name = settings.oauth_connection_name
        
        self.add_dialog(
            OAuthPrompt(
                OAuthPrompt.__name__,
                OAuthPromptSettings(
                    connection_name=self._connection_name,
                    text="Please sign in to access Genie.",
                    title="Sign In",
                    timeout=300000,  # 5 minute timeout
                ),
            )
        )
```

**Assessment**: ✅ SECURE
- Uses Bot Framework OAuthPrompt (industry standard)
- Proper timeout configured
- Connection name configurable (not hardcoded)

### Token Exchange Implementation

**File**: `auth.py`

```python
async def exchange_aad_for_databricks_token_async(
    settings: "Settings",
    user_assertion: str,
    cache: TokenCache,
) -> TokenExchangeResult:
    # Check circuit breaker
    if not _databricks_circuit_breaker.is_available():
        raise TokenExchangeError("Service temporarily unavailable (circuit open)")
    
    # Prepare request - NO client_id = USER identity
    data: dict[str, Any] = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": user_assertion,
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "scope": settings.token_scope or "all-apis",
    }
```

**Assessment**: ✅ SECURE
- No credentials in token exchange (user identity preserved)
- Circuit breaker prevents cascading failures
- Proper error handling

---

## Authorization Analysis

### Bearer Token Extraction

**File**: `api.py`

```python
def _extract_bearer_token(authorization: str | None) -> str:
    """Extract bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1]
```

**Assessment**: ✅ SECURE
- Proper validation of Authorization header format
- Correct HTTP status codes

### FINDING: No Rate Limiting

**Severity**: MEDIUM

**Location**: `api.py`, `bot.py`

**Description**: No rate limiting is implemented at the application level. Malicious users could flood the service with requests.

**Recommendation**: 
1. Deploy behind Azure API Management with rate limiting
2. OR implement rate limiting middleware:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/v1/genie/ask")
@limiter.limit("10/minute")
async def ask_genie_v1(request: Request, ...):
    ...
```

---

## Input Validation Analysis

### Request Validation

**File**: `config.py`

```python
FORBIDDEN_PATTERNS = [
    r';\s*DROP\s+',      # SQL injection
    r';\s*DELETE\s+',    # SQL injection
    r';\s*UPDATE\s+',    # SQL injection
    r';\s*INSERT\s+',    # SQL injection
    r'<script',          # XSS
    r'javascript:',      # XSS
]

@dataclass
class AskRequest:
    """Request model for /genie/ask endpoint with validation."""
    question: str
    conversation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.question:
            raise ValueError("question is required")
        
        self.question = self.question.strip()
        
        if len(self.question) > MAX_QUESTION_LENGTH:
            raise ValueError(f"question exceeds maximum length of {MAX_QUESTION_LENGTH}")
        
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, self.question, re.IGNORECASE):
                raise ValueError("question contains potentially unsafe content")
```

**Assessment**: ✅ SECURE
- Input length limits enforced
- SQL injection patterns blocked
- XSS patterns blocked
- Whitespace trimming applied

---

## Data Protection Analysis

### FINDING: Token Stored in Memory Without Encryption

**Severity**: HIGH

**Location**: `auth.py`, `enterprise/cache.py`

**Description**: Tokens are cached in memory without encryption. If memory is compromised (e.g., via memory dump), tokens could be extracted.

```python
@dataclass
class CachedToken:
    """Cached token with metadata."""
    access_token: str  # Plain text!
    expires_at: datetime
    refresh_token: str | None = None
```

**Recommendation**:
1. Use short TTL (currently 5 minutes - GOOD)
2. Consider encrypting tokens at rest:

```python
from cryptography.fernet import Fernet

class EncryptedTokenCache(MemoryCache):
    def __init__(self, encryption_key: bytes):
        super().__init__()
        self._cipher = Fernet(encryption_key)
    
    def set(self, key: str, access_token: str, ...):
        encrypted = self._cipher.encrypt(access_token.encode())
        super().set(key, encrypted.decode(), ...)
```

### FINDING: Potential Token Leakage in Error Messages

**Severity**: MEDIUM

**Location**: `auth.py`

**Description**: Error handling may include token content in exceptions.

```python
if response.status_code >= 400:
    raise TokenExchangeError(f"Token exchange failed: {response.status_code} {response.text}")
```

The `response.text` might contain token information.

**Recommendation**: Sanitize error messages:

```python
if response.status_code >= 400:
    # Don't include response body which might contain sensitive data
    raise TokenExchangeError(f"Token exchange failed: HTTP {response.status_code}")
```

---

## Configuration Security

### FINDING: Secrets May Be Logged

**Severity**: MEDIUM

**Location**: `main.py`, `services.py`

**Description**: Print statements in initialization could expose secrets in logs.

```python
def _initialize_services() -> None:
    try:
        from .services import apply_keyvault_secrets_to_env
        count = apply_keyvault_secrets_to_env()
        if count > 0:
            print(f"Loaded {count} secrets from Key Vault")  # OK - just count
```

**Assessment**: Currently safe (only logging count), but recommend using structured logging:

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Key Vault initialization", extra={"secrets_loaded": count})
```

### FINDING: Default Values May Be Insecure

**Severity**: MEDIUM

**Location**: `config.py`

```python
oauth_connection_name: str = field(default_factory=lambda: _get_env("OAUTH_CONNECTION_NAME", "databricks-sso"))
```

**Assessment**: Default value "databricks-sso" is acceptable but should be documented.

---

## Dependency Analysis

### FINDING: No Dependency Scanning

**Severity**: LOW

**Description**: No automated dependency vulnerability scanning is configured.

**Recommendation**: Add GitHub Dependabot or similar:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
```

### Current Dependencies Review

| Package | Version | Known Vulnerabilities |
|---------|---------|----------------------|
| fastapi | >=0.110 | None known |
| requests | >=2.32 | None known |
| httpx | >=0.27 | None known |
| botbuilder-core | >=4.14 | None known |
| azure-identity | >=1.15 | None known |

---

## Network Security

### TLS Configuration

**Assessment**: ✅ SECURE
- Azure App Service enforces HTTPS by default
- No custom TLS configuration needed

### API Endpoints

| Endpoint | Method | Auth Required | Notes |
|----------|--------|---------------|-------|
| /healthz | GET | No | Expected |
| /v1/healthz | GET | No | Expected |
| /api/messages | POST | Yes (Bot Framework) | Validated by adapter |
| /v1/genie/ask | POST | Yes (Bearer) | Validated |
| /genie/ask | POST | Yes (Bearer) | Legacy |

**Assessment**: ✅ SECURE
- Health endpoints appropriately unauthenticated
- All data endpoints require authentication

---

## Secure Coding Practices

### Error Handling

```python
async def on_error(context: TurnContext, error: Exception) -> None:
    print(f"[on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()
    await context.send_activity("Sorry, something went wrong processing your request.")
```

**Assessment**: ⚠️ MEDIUM RISK
- Full traceback printed to stderr (may contain sensitive info)
- User receives generic message (GOOD)

**Recommendation**: In production, send tracebacks to Application Insights only:

```python
async def on_error(context: TurnContext, error: Exception) -> None:
    track_exception(error)  # To Application Insights
    await context.send_activity("Sorry, something went wrong.")
```

### Secrets Handling

**File**: `services.py`

```python
SECRET_MAPPINGS = {
    "genie-databricks-host": "GENIE_DATABRICKS_HOST",
    "genie-space-id": "GENIE_GENIE_SPACE_ID",
    "microsoft-app-id": "MICROSOFT_APP_ID",
    "microsoft-app-password": "MICROSOFT_APP_PASSWORD",  # Secret!
}
```

**Assessment**: ✅ SECURE
- Secrets loaded from Key Vault to environment variables
- Never logged or exposed

---

## Recommendations Summary

### Critical (Fix Before Production)

None identified.

### High Priority

1. **Encrypt cached tokens** or accept risk with short TTL
2. **Sanitize error messages** to prevent token leakage

### Medium Priority

1. **Add rate limiting** via API gateway or middleware
2. **Use structured logging** instead of print statements
3. **Remove traceback logging** in production

### Low Priority

1. **Add dependency scanning** (Dependabot)
2. **Document security configuration** requirements

---

## Compliance Mappings

### OWASP Top 10 (2021)

| Risk | Status | Notes |
|------|--------|-------|
| A01 Broken Access Control | ✅ Mitigated | RLS + Azure AD |
| A02 Cryptographic Failures | ⚠️ Review | Token caching |
| A03 Injection | ✅ Mitigated | Input validation |
| A04 Insecure Design | ✅ Mitigated | Proper architecture |
| A05 Security Misconfiguration | ⚠️ Review | Document requirements |
| A06 Vulnerable Components | ✅ Current | Audit regularly |
| A07 Auth Failures | ✅ Mitigated | Azure AD + Bot Framework |
| A08 Software Integrity | ✅ Mitigated | Standard deployment |
| A09 Logging Failures | ⚠️ Review | Enhance logging |
| A10 SSRF | ✅ Mitigated | No user-controlled URLs |

---

## Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Security Reviewer | | | |
| Technical Lead | | | |
| Product Owner | | | |
