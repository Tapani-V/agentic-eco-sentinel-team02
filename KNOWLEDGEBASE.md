# Knowledge Base

Reference notes on how this project's components actually communicate,
written for engineers who need to reason about integration points without
re-reading the full source tree each time.

---

## 1. AgentCore Runtime invocation is not a plain HTTP REST call

**Summary:** You cannot point the dashboard directly at an AgentCore Runtime
by setting `ORCHESTRATOR_URL` to a runtime ARN/ID. AgentCore Runtime and
plain HTTP REST APIs are two fundamentally different invocation mechanisms,
and the dashboard's HTTP client only understands the latter.

### How the dashboard talks to "the orchestrator" today

`OrchestratorClient` in
[src/dashboard/routes/api.py](src/dashboard/routes/api.py#L110-L165) is a
thin wrapper around `httpx.AsyncClient`. Every call it makes is a standard,
unauthenticated HTTP `GET`/`POST` against `settings.ORCHESTRATOR_URL` plus a
REST path (e.g. `/devices`, `/health`, `/diagnose`). This works against:

- Local Docker Compose (`http://localhost:8000`) — the FastAPI orchestrator
  service exposes exactly those REST paths.
- The shared Lambda + API Gateway endpoint
  (`https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate`)
  — API Gateway is, again, a plain HTTPS REST surface.

Both targets are interchangeable from the dashboard's point of view because
both speak the same protocol: unauthenticated JSON-over-HTTP.

### How AgentCore Runtime is actually invoked

AgentCore Runtime has no equivalent public REST surface. Per
[functions/lambda_orchestrator_handler.py](functions/lambda_orchestrator_handler.py#L131-L172),
invoking a deployed runtime requires:

1. A **`boto3` client for the `bedrock-agentcore` service**
   (`boto3.client('bedrock-agentcore', region_name=...)`), not an HTTP
   client such as `httpx`/`requests`.
2. The specific API operation `invoke_agent_runtime(...)`, addressed by a
   runtime **ARN** (`arn:aws:bedrock-agentcore:<region>:<account_id>:runtime/<runtime_id>`),
   not a URL with REST paths.
3. **AWS SigV4 request signing**, handled transparently by `boto3` using
   real AWS credentials — there is no way to invoke it with a bare URL and
   no credentials, the way `httpx.get(url)` works.
4. Its own request/response payload contract (structured invocation
   payload), which does not match the plain JSON REST endpoints
   (`/devices`, `/diagnose`, etc.) the dashboard/orchestrator app expose.

None of this is compatible with `httpx.AsyncClient().get(url)`. Swapping
`ORCHESTRATOR_URL` for a runtime ARN would simply fail — there is no HTTP
listener at that "address" for `httpx` to connect to.

### Why the Lambda bridge exists

`functions/lambda_orchestrator_handler.py` exists specifically to translate
between these two worlds:

- It is fronted by API Gateway, so it presents a plain HTTP REST endpoint
  to callers (the dashboard).
- Internally, it uses `boto3` to perform the SigV4-signed
  `invoke_agent_runtime` call against a **hardcoded** runtime ID
  (`orchestrator_runtime_id`, currently `orchestrator_runtime-6UF3HDGyvL`),
  and translates the AgentCore Runtime response back into plain JSON for
  the caller.

Because that runtime ID is hardcoded rather than parameterized, pointing
the shared Lambda at a different (e.g. team-specific) AgentCore Runtime
deployment requires editing and redeploying that Lambda — there is no
client-side (dashboard-side) way to do this by changing a URL/environment
variable alone. See `TEAM_TESTING_STEPS.md` for the documented, reversible
procedure for doing this temporarily.

### Practical takeaway

| Target | Protocol | Auth | Client |
|---|---|---|---|
| Local Docker Compose orchestrator | Plain HTTP REST | None | `httpx` |
| Shared Lambda / API Gateway | Plain HTTPS REST | None (as configured) | `httpx` |
| AgentCore Runtime | AWS API (`invoke_agent_runtime`) | SigV4 (AWS credentials) | `boto3` |

If a future requirement is "let the dashboard call AgentCore Runtime
directly," the dashboard itself would need a `boto3`-based client (and AWS
credentials available to it), not just a URL change.
