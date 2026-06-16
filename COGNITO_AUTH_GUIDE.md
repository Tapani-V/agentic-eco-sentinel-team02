# Cognito Authentication Guide — AgentCore Gateway Project

A complete reference for how AWS Cognito authentication works and how this project uses it.

---

## Table of Contents

1. [What is AWS Cognito?](#1-what-is-aws-cognito)
2. [Key Cognito Concepts](#2-key-cognito-concepts)
3. [OAuth2 Flows Explained](#3-oauth2-flows-explained)
4. [Our Project Architecture](#4-our-project-architecture)
5. [The Two Authentication Planes](#5-the-two-authentication-planes)
6. [Step-by-Step Token Flow](#6-step-by-step-token-flow)
7. [Cognito Resources in This Project](#7-cognito-resources-in-this-project)
8. [Gateway JWT Validation](#8-gateway-jwt-validation)
9. [Token Lifecycle & Caching](#9-token-lifecycle--caching)
10. [Security Considerations](#10-security-considerations)
11. [Troubleshooting](#11-troubleshooting)
12. [Quick Reference Card](#12-quick-reference-card)

---

## 1. What is AWS Cognito?

AWS Cognito is a managed identity service that handles authentication and authorization. It has two main components:

| Component | Purpose | Used In This Project? |
|-----------|---------|----------------------|
| **User Pools** | User directory + OAuth2 token service | ✅ Yes |
| **Identity Pools** | Exchange tokens for temporary AWS credentials | ❌ No (we use tokens directly) |

**In this project**, we use a Cognito **User Pool** purely as an **OAuth2 token vending machine** — agents request access tokens using machine-to-machine credentials, and the AgentCore Gateway validates those tokens.

---

## 2. Key Cognito Concepts

### User Pool

A container that holds:
- User accounts (not used here — we have no human users logging in)
- App clients (machine identities)
- Resource servers (permission definitions)
- A domain (public URL for OAuth2 endpoints)

**Our User Pool:**
```
Name: agentic-ai-poc-3-1-user-pool
ID:   us-east-1_R6pOfxcKV
```

### App Client

An application registered with the User Pool. Like a "service account" — it identifies WHO is requesting tokens.

**Two types:**

| Type | Has Secret? | Use Case |
|------|-------------|----------|
| **Public** client | No | Browser/mobile apps (can't keep secrets) |
| **Confidential** client | Yes | Server-to-server (can safely store secrets) |

**We use a confidential client** because our agents are backend services that can securely store the client secret.

### Resource Server

Defines a namespace of **scopes** (permissions). Think of it as declaring what operations exist.

```
Resource Server: agentcore
Scope:           invoke
Full scope:      agentcore/invoke
```

When a token is issued, it contains the scope — the gateway checks: "Does this token have `agentcore/invoke` permission?"

### Domain

A URL hostname attached to the User Pool. Without it, there's no endpoint to call.

```
Domain: agentic-ai-poc-3-1-auth
Full URL: https://agentic-ai-poc-3-1-auth.auth.us-east-1.amazoncognito.com
Token endpoint: https://agentic-ai-poc-3-1-auth.auth.us-east-1.amazoncognito.com/oauth2/token
```

**Analogy:** The User Pool is a bank. The domain is the bank's street address. Without the address, no one can walk up and request anything.

---

## 3. OAuth2 Flows Explained

OAuth2 defines several ways to get tokens. Only one matters for this project:

### client_credentials Grant (Machine-to-Machine)

```
┌──────────────┐                          ┌──────────────────────┐
│  Agent       │  POST /oauth2/token      │  Cognito User Pool   │
│  (service)   │ ─────────────────────►   │  (token endpoint)    │
│              │  Body:                    │                      │
│              │   grant_type=             │                      │
│              │     client_credentials    │                      │
│              │   scope=agentcore/invoke  │                      │
│              │  Auth: Basic(id:secret)   │                      │
│              │                           │                      │
│              │  ◄─────────────────────   │                      │
│              │  { "access_token": "..." }│                      │
└──────────────┘                          └──────────────────────┘
```

**When to use:** Service-to-service communication where no human is involved. The service proves its identity with a client ID + secret, and gets back an access token.

**Other flows (NOT used here):**

| Flow | Purpose | Why Not Used |
|------|---------|--------------|
| Authorization Code | Human login via browser redirect | No human users calling gateway |
| Implicit | Legacy browser flow | Deprecated, insecure |
| Password | Direct username/password | Not machine-to-machine |

---

## 4. Our Project Architecture

### The Two-Hop Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FULL RUNTIME FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐         HOP 1              ┌─────────────┐                    │
│  │ Caller  │ ─────────────────────────► │ Agent       │                    │
│  │ (curl/  │  (open in dev,             │ Service     │                    │
│  │  dash-  │   API auth in prod)        │ (LangGraph) │                    │
│  │  board) │                            │             │                    │
│  └─────────┘                            └──────┬──────┘                    │
│                                                 │                          │
│                                                 │ HOP 2                    │
│                                                 │ Bearer token             │
│                                                 ▼                          │
│                                         ┌─────────────────┐               │
│                                         │ AgentCore       │               │
│                                         │ Gateway         │               │
│                                         │ (validates JWT) │               │
│                                         └────────┬────────┘               │
│                                                  │                         │
│                                    ┌─────────────┼─────────────┐          │
│                                    ▼             ▼             ▼          │
│                              ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│                              │ Lambda:  │ │ Lambda:  │ │ AppRunner│      │
│                              │ get-     │ │ schedule-│ │ create-  │      │
│                              │ spare-   │ │ mainten- │ │ work-    │      │
│                              │ parts    │ │ ance     │ │ order    │      │
│                              └──────────┘ └──────────┘ └──────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Where Cognito Fits

```
                    ┌────────────────────────────────────────┐
                    │         Cognito User Pool              │
                    │                                        │
                    │  Resource Server: agentcore            │
                    │  Scope: invoke                         │
                    │  Domain: agentic-ai-poc-3-1-auth       │
                    │  Client: confidential (ID + secret)    │
                    │                                        │
                    └──────────────────┬─────────────────────┘
                                       │
                         ┌─────────────┼─────────────┐
                         │             │             │
                    (1) Token     (2) OIDC       (3) Scope
                    request      discovery      validation
                         │             │             │
                         ▼             ▼             ▼
                    ┌─────────┐  ┌──────────┐  ┌──────────┐
                    │ Agent   │  │ Gateway  │  │ Gateway  │
                    │ fetches │  │ fetches  │  │ checks   │
                    │ token   │  │ signing  │  │ token    │
                    │         │  │ keys     │  │ has      │
                    │         │  │ (JWKS)   │  │ correct  │
                    │         │  │          │  │ scope    │
                    └─────────┘  └──────────┘  └──────────┘
```

---

## 5. The Two Authentication Planes

### Control Plane (IAM / SigV4)

| Aspect | Detail |
|--------|--------|
| **What** | Managing gateway resources (list tools, create gateway, register targets) |
| **Auth method** | AWS IAM credentials (your AWS profile) |
| **How** | boto3 automatically signs requests with your access keys |
| **Example** | `control_client.list_gateway_targets(gatewayIdentifier=...)` |
| **Token needed?** | No Cognito token — just valid AWS credentials |

### Data Plane (Cognito Bearer Token)

| Aspect | Detail |
|--------|--------|
| **What** | Actually invoking tools through the gateway (`tools/list`, `tools/call`) |
| **Auth method** | Cognito OAuth2 access token (Bearer) |
| **How** | HTTP request with `Authorization: Bearer <token>` header |
| **Example** | `POST https://gateway-url/mcp` with tool invocation payload |
| **Token needed?** | Yes — gateway rejects without valid JWT |

### Why Two Different Auth Methods?

```
Control Plane (boto3/IAM):
  "I'm an AWS administrator managing infrastructure"
  → Proves: you have IAM permissions to configure the gateway

Data Plane (Cognito token):
  "I'm an agent service invoking tools at runtime"
  → Proves: you're an authorized service with the right scope
```

The gateway is designed this way because:
- **Control plane** = admin operations, protected by IAM (same as all AWS services)
- **Data plane** = runtime traffic, protected by JWT (standard, fast, stateless validation)

---

## 6. Step-by-Step Token Flow

### What happens when an agent needs to call a tool:

```
Step 1: Agent checks token cache
        ┌──────────────────────────────────┐
        │ Is there a cached token?         │
        │ Is it still valid (not expired)? │
        └──────────┬───────────────────────┘
                   │
          ┌────────┴────────┐
          │ YES             │ NO
          ▼                 ▼
    Use cached        Step 2: Request new token
    token             ┌──────────────────────────────────────┐
                      │ POST https://agentic-ai-poc-3-1-auth │
                      │   .auth.us-east-1.amazoncognito.com  │
                      │   /oauth2/token                      │
                      │                                      │
                      │ Body:                                │
                      │   grant_type=client_credentials      │
                      │   scope=agentcore/invoke             │
                      │                                      │
                      │ Headers:                             │
                      │   Authorization: Basic base64(id:sec)│
                      │   Content-Type: x-www-form-urlencoded│
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      Step 3: Cognito validates client
                      ┌──────────────────────────────────────┐
                      │ - Is client ID valid?                │
                      │ - Does secret match?                 │
                      │ - Is client allowed client_credentials│
                      │ - Does resource server define scope? │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      Step 4: Cognito returns access token
                      ┌──────────────────────────────────────┐
                      │ {                                    │
                      │   "access_token": "eyJhbGci...",     │
                      │   "expires_in": 3600,               │
                      │   "token_type": "Bearer"            │
                      │ }                                    │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      Step 5: Agent caches token
                      (stores token + expiry time)
                                         │
                                         ▼
                      Step 6: Agent calls gateway
                      ┌──────────────────────────────────────┐
                      │ POST https://gateway-url/mcp         │
                      │                                      │
                      │ Headers:                             │
                      │   Authorization: Bearer eyJhbGci...  │
                      │   Content-Type: application/json     │
                      │                                      │
                      │ Body:                                │
                      │ {                                    │
                      │   "jsonrpc": "2.0",                  │
                      │   "method": "tools/call",           │
                      │   "params": {                       │
                      │     "name": "get-spare-parts",      │
                      │     "arguments": {"part_type":"..."}│
                      │   }                                 │
                      │ }                                    │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      Step 7: Gateway validates JWT
                      ┌──────────────────────────────────────┐
                      │ - Decode JWT header → get key ID     │
                      │ - Fetch JWKS from Cognito OIDC URL   │
                      │ - Verify signature with public key   │
                      │ - Check exp (not expired)            │
                      │ - Check iss (correct user pool)      │
                      │ - Check client_id in allowedClients  │
                      │ - Check scope includes required scope│
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      Step 8: Gateway routes to tool
                      (Lambda / App Runner)
                                         │
                                         ▼
                      Step 9: Tool executes & returns result
                      ┌──────────────────────────────────────┐
                      │ {                                    │
                      │   "jsonrpc": "2.0",                  │
                      │   "result": {                       │
                      │     "parts": [...],                 │
                      │     "count": 3                      │
                      │   }                                 │
                      │ }                                    │
                      └──────────────────────────────────────┘
```

---

## 7. Cognito Resources in This Project

### Resource Inventory

| Resource | Name/Value | Purpose |
|----------|------------|---------|
| User Pool | `agentic-ai-poc-3-1-user-pool` | Container for all OAuth2 resources |
| User Pool ID | `us-east-1_R6pOfxcKV` | Unique identifier |
| Domain | `agentic-ai-poc-3-1-auth` | Provides `/oauth2/token` endpoint |
| Resource Server | `agentcore` | Defines `invoke` scope |
| Scope | `agentcore/invoke` | Permission to call gateway |
| Public App Client | `2a8at414274aard1bvn12gt3h2` | Original (no secret, used for gateway `allowedClients`) |
| Confidential App Client | *(created by setup script)* | Has secret, used for `client_credentials` |

### How They Were Created

| Resource | Created By |
|----------|-----------|
| User Pool | `scripts/cognito_setup.py` (Week 1) |
| Public App Client | `scripts/cognito_setup.py` (Week 1) |
| Resource Server | `scripts/setup_cognito_token_flow.py` (Week 2) |
| Domain | `scripts/setup_cognito_token_flow.py` (Week 2) |
| Confidential Client | `scripts/setup_cognito_token_flow.py` (Week 2) |

### Configuration File: `.agentcore.env`

```dotenv
# These are used by all scripts:
COGNITO_USER_POOL_ID=us-east-1_R6pOfxcKV
COGNITO_APP_CLIENT_ID=<confidential_client_id>
COGNITO_APP_CLIENT_SECRET=<confidential_client_secret>
COGNITO_DOMAIN_PREFIX=agentic-ai-poc-3-1-auth
COGNITO_TOKEN_ENDPOINT=https://agentic-ai-poc-3-1-auth.auth.us-east-1.amazoncognito.com/oauth2/token
COGNITO_SCOPE=agentcore/invoke
```

---

## 8. Gateway JWT Validation

### How the Gateway Knows to Trust Cognito

When the gateway is created, it's configured with a `customJWTAuthorizer`:

```python
{
    "customJWTAuthorizer": {
        "allowedClients": ["<client_id>"],
        "discoveryUrl": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_R6pOfxcKV/.well-known/openid-configuration"
    }
}
```

### What `discoveryUrl` Does

The gateway fetches this URL (OIDC Discovery) which returns:

```json
{
  "issuer": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_R6pOfxcKV",
  "jwks_uri": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_R6pOfxcKV/.well-known/jwks.json",
  "token_endpoint": "...",
  ...
}
```

From `jwks_uri`, the gateway gets the **public signing keys** used to verify token signatures. This is standard OpenID Connect.

### What the Gateway Checks in Each Request

```
Incoming request → Extract Bearer token → Decode JWT → Validate:

1. ✓ Signature valid?     (using JWKS public keys from Cognito)
2. ✓ Token not expired?   (exp claim > current time)
3. ✓ Issuer correct?      (iss == user pool URL)
4. ✓ Client allowed?      (client_id in allowedClients list)
5. ✓ Scope sufficient?    (scope includes required scope, if configured)

All pass → Route to tool
Any fail → Return 401 Unauthorized
```

### Anatomy of the JWT Access Token

```
Header:
{
  "kid": "abc123...",          ← Key ID (which JWKS key to use)
  "alg": "RS256"              ← Signing algorithm
}

Payload:
{
  "sub": "<client_id>",       ← Subject (the client)
  "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_R6pOfxcKV",
  "client_id": "<client_id>", ← App client that requested the token
  "token_use": "access",      ← This is an access token
  "scope": "agentcore/invoke",← Granted scopes
  "exp": 1717900000,          ← Expiration (Unix timestamp)
  "iat": 1717896400           ← Issued at
}

Signature:
  RS256(header + "." + payload, cognito_private_key)
```

---

## 9. Token Lifecycle & Caching

### Token Timing

| Property | Value | Meaning |
|----------|-------|---------|
| `expires_in` | 3600 (default) | Token valid for 1 hour |
| Refresh | Not applicable | `client_credentials` tokens can't be refreshed — request a new one |
| Best practice | Cache until ~5 min before expiry | Avoid unnecessary token requests |

### Caching Strategy (for Agent Runtime)

```python
import time
import requests

class TokenCache:
    def __init__(self, client_id, client_secret, token_endpoint, scope):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_endpoint = token_endpoint
        self.scope = scope
        self._token = None
        self._expires_at = 0

    def get_token(self) -> str:
        """Get valid token, refreshing if expired."""
        # Refresh 5 minutes before actual expiry
        if self._token and time.time() < (self._expires_at - 300):
            return self._token

        resp = requests.post(
            self.token_endpoint,
            data={"grant_type": "client_credentials", "scope": self.scope},
            auth=(self.client_id, self.client_secret),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        self._token = data["access_token"]
        self._expires_at = time.time() + data["expires_in"]
        return self._token
```

### Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| 401 from token endpoint | Wrong client_id or secret | Check `.agentcore.env` values |
| 401 from gateway | Token expired or client not in `allowedClients` | Refresh token; recreate gateway with correct client |
| 403 from gateway | Scope mismatch | Ensure token has `agentcore/invoke` scope |
| Connection refused on token endpoint | Domain not created | Run `setup_cognito_token_flow.py` |

---

## 10. Security Considerations

### What's Sensitive

| Item | Sensitivity | Storage |
|------|-------------|---------|
| Client ID | Low (public identifier) | `.agentcore.env`, safe in code |
| Client Secret | **HIGH** (authenticates the service) | `.agentcore.env`, never in git |
| Access Token | Medium (short-lived, 1hr) | In-memory only, never logged |
| User Pool ID | Low (public, in OIDC discovery URL) | `.agentcore.env` |

### Best Practices

1. **`.agentcore.env` is in `.gitignore`** — secrets never committed
2. **Tokens are short-lived** — even if leaked, they expire in 1 hour
3. **Least privilege scope** — token only grants `agentcore/invoke`, nothing else
4. **No human credentials involved** — purely machine-to-machine
5. **Client secret rotation** — create a new client + delete old one periodically

### What If Client Secret Is Compromised?

1. Delete the compromised app client in Cognito
2. Re-run `scripts/setup_cognito_token_flow.py` (creates new client + updates env)
3. Recreate gateway with new client in `allowedClients`
4. Old tokens immediately fail (client no longer exists)

---

## 11. Troubleshooting

### "Token has expired and refresh failed"

**Cause:** AWS SSO session expired (for control-plane/boto3 calls, not Cognito)
**Fix:**
```bash
aws sso login --profile StandardAccess-450410489798
```

### "invalid_client" from token endpoint

**Cause:** Client ID or secret is wrong
**Check:**
```bash
# Verify client exists and has a secret
aws cognito-idp describe-user-pool-client \
  --user-pool-id us-east-1_R6pOfxcKV \
  --client-id <YOUR_CLIENT_ID> \
  --region us-east-1 \
  --profile StandardAccess-450410489798
```

### "invalid_scope" from token endpoint

**Cause:** Resource server doesn't define the requested scope
**Check:**
```bash
aws cognito-idp describe-resource-server \
  --user-pool-id us-east-1_R6pOfxcKV \
  --identifier agentcore \
  --region us-east-1 \
  --profile StandardAccess-450410489798
```

### Gateway returns 401

**Possible causes:**
1. Token expired → request new one
2. Client ID not in gateway's `allowedClients` → recreate gateway
3. Token issued by wrong user pool → check `COGNITO_USER_POOL_ID`

**Debug:** Decode token at https://jwt.io to inspect claims

### "No token endpoint" / Connection error

**Cause:** Cognito domain not created
**Fix:**
```bash
python scripts/setup_cognito_token_flow.py
```

### `agentcore-gateway-*` stale User Pools

**Cause:** Created by starter toolkit's EZ Auth during early testing
**Safe to delete:** Yes, after confirming no active gateway references them
```bash
aws cognito-idp delete-user-pool --user-pool-id <POOL_ID> --region us-east-1
```

---

## 12. Quick Reference Card

### Get a Token (curl)

```bash
curl -X POST \
  "https://agentic-ai-poc-3-1-auth.auth.us-east-1.amazoncognito.com/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "<CLIENT_ID>:<CLIENT_SECRET>" \
  -d "grant_type=client_credentials&scope=agentcore/invoke"
```

### Call Gateway with Token

```bash
TOKEN="eyJhbGci..."  # from above response

curl -X POST \
  "https://agenticai-poc-3-1-mcp-gateway-kvxs7ruhsl.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

### Key Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup_cognito_token_flow.py` | Create resource server + domain + confidential client |
| `scripts/create_agentcore_gateway_starter.py` | Create/configure gateway with Cognito authorizer |
| `scripts/test_agentcore_gateway_starter.py` | Test control-plane + data-plane (if secret set) |
| `scripts/check_cognito_app_client_oauth.py` | Verify app client OAuth config |

### Key Environment Variables

| Variable | Example | Used By |
|----------|---------|---------|
| `COGNITO_USER_POOL_ID` | `us-east-1_R6pOfxcKV` | Gateway creation (discovery URL) |
| `COGNITO_APP_CLIENT_ID` | `abc123...` | Token request + gateway allowedClients |
| `COGNITO_APP_CLIENT_SECRET` | `xyz789...` | Token request (proves identity) |
| `COGNITO_TOKEN_ENDPOINT` | `https://...amazoncognito.com/oauth2/token` | Where to request tokens |
| `COGNITO_SCOPE` | `agentcore/invoke` | What permission to request |
| `COGNITO_DOMAIN_PREFIX` | `agentic-ai-poc-3-1-auth` | Used to construct token endpoint |

---

## Summary Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   SETUP TIME (one-time, done by scripts)                                │
│                                                                         │
│   1. Create User Pool ─── cognito_setup.py                              │
│   2. Create Resource Server ─┐                                          │
│   3. Create Domain ──────────┼── setup_cognito_token_flow.py            │
│   4. Create Confidential ────┘                                          │
│      Client                                                             │
│   5. Create Gateway with ─── create_agentcore_gateway_starter.py        │
│      allowedClients=[client_id]                                         │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   RUNTIME (every agent tool call)                                       │
│                                                                         │
│   Agent                    Cognito              Gateway         Tool     │
│     │                        │                    │              │       │
│     │──── client_credentials─►│                    │              │       │
│     │◄─── access_token ──────│                    │              │       │
│     │                        │                    │              │       │
│     │──── Bearer token + MCP request ────────────►│              │       │
│     │                        │                    │── validate ──│       │
│     │                        │                    │── route ────►│       │
│     │                        │                    │◄── result ───│       │
│     │◄─── MCP response ──────────────────────────│              │       │
│     │                        │                    │              │       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

*Last updated: June 9, 2026*
