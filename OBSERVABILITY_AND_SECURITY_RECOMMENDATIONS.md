# Observability & Security Recommendations

**Date:** 2026-08-18
**Status:** Analysis only — nothing in this document has been implemented yet.

This document captures a read-only audit of the current architecture
(orchestrator/health/diagnosis agents on AgentCore Runtime, Lambda + API
Gateway front door, FastAPI dashboard, Cognito for the MCP Gateway,
S3/DynamoDB) and recommends concrete, prioritized improvements for
observability and security.

## Key facts driving these recommendations

- API Gateway routes are created with `authorizationType='NONE'`
  ([scripts/deploy_lambda_api_gateway_boto3.py](scripts/deploy_lambda_api_gateway_boto3.py),
  [scripts/add_devices_api_routes.py](scripts/add_devices_api_routes.py)) —
  the public `/orchestrate*` endpoints have **no auth at all**.
- Cognito (client-credentials JWT, [src/gateway/client.py](src/gateway/client.py))
  is used only for the AgentCore Gateway → MCP tool calls, not for the public API.
- Secrets (Azure OpenAI key, Cognito client secret) come from `.env`/`os.getenv`
  — no Secrets Manager/Parameter Store.
- Logging is plain Python `logging` with emoji-decorated free text (e.g.
  `logger.info(f"Payload: {json.dumps(event)[:200]}")`), not structured JSON
  — and it logs raw payloads.
- No correlation/request ID is threaded through Lambda → Orchestrator →
  HealthAgent/DiagnosisAgent → MCP tools.
- No X-Ray/OpenTelemetry, no custom CloudWatch metrics/alarms, no WAF, no
  image/dependency scanning found.

---

## 1. Observability

### Idea 1 — Structured, correlated logging
Replace free-text `logger.info(f"...")` calls with structured JSON logs
carrying a shared `correlation_id`/`trace_id` generated at the Lambda
entrypoint and passed through every hop (Lambda → Orchestrator →
HealthAgent/DiagnosisAgent → MCP tools) via the payload.

**Why:** Each service currently logs independently with emoji strings that
aren't machine-parseable, and there is no way to join logs across the 3+
separate CloudWatch log groups (Lambda, and per-runtime
`/aws/bedrock-agentcore/runtimes/...`) for a single end-to-end request.

**How:** Adopt `aws-lambda-powertools` (Python) for Lambda, or plain
`python-json-logger`/`structlog` for the AgentCore containers. Generate the
ID once (e.g. `str(uuid4())` or reuse API Gateway's `requestId`), put it in
every payload's top-level key, and include it in every log line. Then
CloudWatch Logs Insights queries like `filter correlation_id = "..."`
reconstruct the whole request across services.

### Idea 2 — Distributed tracing with AWS X-Ray / OpenTelemetry
Add tracing spans across Lambda → API Gateway → AgentCore Runtime
invocations → MCP tool Lambdas, so you get a visual timeline/service map
instead of manually stitching logs.

**Why:** There is already a multi-hop chain (Lambda → Orchestrator container
→ Health/Diagnosis containers → MCP Lambda tools); latency/error
root-causing today means grepping 4+ log groups by hand.

**How:** Enable Active Tracing on the Lambda + API Gateway stage; use the
X-Ray SDK or OTel Python SDK inside the AgentCore containers (wrap `boto3`
`invoke_agent_runtime` calls and MCP tool calls as subsegments). AgentCore
Runtime containers can emit OTel via an ADOT collector sidecar if X-Ray
isn't directly supported for Bedrock AgentCore — worth confirming current
support level.

### Idea 3 — Custom CloudWatch metrics + dashboards + alarms
Emit business/operational metrics (not just default AWS ones): agent
invocation count/latency per runtime, health-degradation-score
distribution, DiagnosisAgent trigger rate, MCP tool call failures, LLM
(Azure OpenAI) call latency/error rate, fleet-summary cache hit ratio.

**Why:** There are rich domain signals (degradation_score, anomaly counts,
LLM confidence) that never leave the process today — they're only in log
lines, not queryable metrics. That means no alarms can fire on "diagnosis
confidence dropped" or "LLM verification failing repeatedly."

**How:** Use EMF (Embedded Metric Format) via Powertools `Metrics` (Lambda)
or `boto3 cloudwatch.put_metric_data` in the containers. Build one
CloudWatch dashboard per agent + a fleet-health overview; set alarms on
error rate, p99 latency, and DiagnosisAgent failure count, wired to SNS.

### Idea 4 — Health/readiness observability beyond `/ping`
Extend the existing `HEALTHCHECK`/`/ping` pattern with a richer `/health`
response (dependency checks: S3 reachability, DynamoDB, Cognito token
acquisition, downstream agent runtime reachability) surfaced to CloudWatch
as a metric, not just an HTTP 200.

**Why:** `/ping` currently only proves the process is up, not that its
dependencies (S3 synthetic-data bucket, Cognito token endpoint used by
`GatewayClient`) are actually reachable — failures there currently just show
as silent fallbacks or generic errors deep in a request.

**How:** Add a lightweight dependency-check function invoked periodically
(CloudWatch Synthetics canary or a scheduled Lambda) that hits `/health` on
each and publishes a metric per dependency.

### Idea 5 — Log retention & cost control policy
Set explicit CloudWatch Logs retention (currently likely "never expire" by
default on log groups created so far).

**Why:** Debug-level emoji logs (`json.dumps(event)[:200]` per request)
accumulate quickly and cost money indefinitely if retention isn't set.

**How:** `aws logs put-retention-policy` per log group (e.g. 30/90 days),
and reduce dashboard/orchestrator log verbosity in production via
`LOG_LEVEL` (already exists as a setting — just needs enforcing at
INFO/WARN in prod, DEBUG only locally).

---

## 2. Security

### Idea 1 — Authenticate the public API Gateway (highest priority)
Add a real authorizer to the `/orchestrate*` routes instead of
`authorizationType='NONE'`.

**Why:** This is the most significant gap — the production API that
triggers the multi-agent pipeline (and indirectly Azure OpenAI calls, MCP
tool actions like creating work orders) is completely open to anyone with
the URL.

**How:** Since Cognito is already in use, add a Cognito User Pool
Authorizer (or a Lambda authorizer validating a JWT) on API Gateway, and
have the dashboard obtain/attach a bearer token (client-credentials flow,
same pattern as `GatewayClient`). Alternatively, at minimum, add an API
Gateway **API key + usage plan** as a stop-gap, then layer real auth on top.

### Idea 2 — Move secrets out of `.env` into AWS Secrets Manager / SSM Parameter Store
**Why:** Cognito client secret and Azure OpenAI key currently live in
plaintext `.env` files (and env vars on Lambda/containers), which are easy
to accidentally commit, appear in `docker inspect`, or leak via CloudWatch
if ever logged.

**How:** Store them in Secrets Manager, grant the Lambda/AgentCore
execution roles `secretsmanager:GetSecretValue` scoped to specific secret
ARNs, and fetch+cache at cold start instead of reading raw env vars. Rotate
the Azure key/Cognito secret periodically using Secrets Manager rotation.

### Idea 3 — Add WAF + throttling in front of API Gateway
**Why:** Even once authenticated, there's no protection against
abuse/DoS/injection patterns hitting the public endpoint, and no request
throttling configured today.

**How:** Attach AWS WAF (managed rule groups: SQLi, common exploits,
rate-based rule) to the API Gateway stage; set stage-level throttling
(burst/rate limits) and per-client usage plans.

### Idea 4 — Least-privilege IAM review
**Why:** A generic `AgentCoreExecutionRole` was granted broad-ish access
(e.g., S3 `GetObject`/`ListBucket` on the whole synthetic-data bucket);
worth verifying no role has wildcard `*` resources/actions beyond what's
needed, especially since a permission boundary pattern already exists
(`GroupIT_ProjectPermissionBoundary`) — good practice, just needs auditing
per-role.

**How:** Run IAM Access Analyzer / `aws iam get-account-authorization-details`
review; scope S3 policy to specific prefixes; ensure MCP Lambda tools
(get_spare_parts, schedule_maintenance, create_work_order) each have their
own tightly scoped role rather than shared broad roles.

### Idea 5 — Container hardening
**Why:** `Dockerfile.health_agent` (and presumably diagnosis/orchestrator)
run as root with no non-root `USER`, no explicit read-only filesystem, and
pull `python:3.11-slim` without a pinned digest — increases blast radius if
a dependency is compromised.

**How:** Add a non-root `USER appuser` after installing deps, pin the base
image by digest, and consider `--read-only` root filesystem with a writable
`/tmp` volume only. Add ECR image scanning on push (`scanOnPush=true`) and
fail CI/deploy on critical CVEs.

### Idea 6 — Input validation & secret redaction in logs
**Why:** Handlers log `json.dumps(event)[:200]` — if a payload ever
contains an auth token, PII, or secret-bearing field, it lands in
CloudWatch. There's also limited schema validation before payloads flow
into agent logic (FastAPI/Pydantic models exist in `app.py`, but the
AgentCore `handler.py` entrypoints look like they take raw dicts).

**How:** Use Pydantic models to validate/parse every inbound payload at the
handler boundary (reject malformed input early with 4xx), and add a
redaction step (mask fields like `token`, `api_key`, `client_secret`)
before logging, e.g. via a Powertools logger formatter or a small
`redact()` helper applied before any `json.dumps(event)` log call.

### Idea 7 — Dependency & static analysis scanning in CI
**Why:** `requirements.txt` uses open-ended version ranges
(`boto3>=1.26.0`, etc.) with no lock file or vulnerability scanning step
found.

**How:** Add `pip-audit` or GitHub Dependabot/`safety` to CI, pin
dependencies with a lock file (`pip-compile`/`poetry.lock`), and add a SAST
tool (Bandit for Python) to catch things like hardcoded secrets or unsafe
`eval`/`subprocess` usage before merge.

### Idea 8 — CORS tightening for the dashboard
**Why:** [src/dashboard/config.py](src/dashboard/config.py) currently
allows only localhost origins, which is fine for dev, but if/when this
dashboard is deployed publicly, confirm `ALLOWED_ORIGINS` is explicitly set
per environment (not wildcarded) and never defaults to `*` in production
config.

**How:** Make `ALLOWED_ORIGINS` environment-driven (already partially is)
and add a startup assertion that fails fast if `DEBUG=false` and origins
still point to localhost.

---

## Suggested priority order

1. Auth on API Gateway (Security Idea 1) — currently wide open, biggest real risk.
2. Secrets Manager migration (Security Idea 2) + log redaction (Security Idea 6).
3. Structured logging + correlation IDs (Observability Idea 1) — unlocks most other observability work cheaply.
4. WAF/throttling (Security Idea 3), custom metrics/alarms (Observability Idea 3), container hardening (Security Idea 5).
5. Tracing (Observability Idea 2) and IAM/dependency-scanning cleanup (Security Ideas 4/7) as maturity follow-ups.
