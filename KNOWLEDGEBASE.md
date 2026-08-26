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


# On Nova Lite model

The code is configured for it — MODEL_ID = "amazon.nova-lite-v1:0" in llm_client.py:28. Few things to know:

It's conditional, not called on every request. LLMClient.verify_diagnosis() is only invoked by DiagnosisAgent when rule-based confidence is < 0.85 (per the module docstring). If your test devices produce high-confidence rule-based diagnoses, Nova Lite is never actually called that run.



Look for these exact log lines from the code:

LLM client initialized (model: amazon.nova-lite-v1:0, region: ...) — logged once at startup (llm_client.py:37).
[LLM] Calling Amazon Nova Lite for <device_id> verification — logged right before the actual Bedrock call (llm_client.py:122).
[LLM] Verification complete for <device_id> followed by Rule: ... / LLM: ... comparison lines — logged after a successful response (llm_client.py:170-172).


To confirm in the AWS Console directly:

CloudWatch → Metrics → AWS/Bedrock namespace → by ModelId — filter for amazon.nova-lite-v1:0 and check the Invocations metric around the time you ran your test. A count > 0 confirms Bedrock actually received calls for that model.
Bedrock model invocation logging (if enabled for the account under Bedrock Console → Settings → Model invocation logging → CloudWatch Logs/S3) — this records every invocation including the exact modelId, input prompt, and output, giving you the strongest possible confirmation.

---

## 2. Pointing the shared Lambda at a team-specific orchestrator runtime

**Summary:** The dashboard cannot be pointed at an AgentCore Runtime
directly (see Section 1), and the Lambda + API Gateway that bridges HTTP to
`invoke_agent_runtime` is currently **shared by every team**, with the
target runtime ID hardcoded. To test the dashboard against your own team's
AgentCore Runtime deployment (e.g. `team01`), the shared Lambda must be
temporarily edited and redeployed to point at your team's runtime.

**Status:** this is a temporary workaround. The team has since decided to
move to a **separate API Gateway + separate Lambda per team**, which will
remove the need for this manual edit/revert cycle entirely (each team's
Lambda will simply be hardcoded/parameterized to its own runtime, with no
shared resource to step on). Until that per-team infrastructure exists, use
the steps below — and always revert step 4 afterward.

### Steps (full detail also in `TEAM_TESTING_STEPS.md`)

1. Deploy your team's agents to AgentCore Runtime (writes
   `agent_endpoints.<TEAM_ID>.json`):
   ```bash
   export AWS_PROFILE=StandardAccess-450410489798
   ./scripts/deploy_team_agents.sh
   ```
2. Read your team's orchestrator runtime ID out of that file:
   ```bash
   python3 -c "import json; print(json.load(open('agent_endpoints.team01.json'))['details']['orchestrator']['runtime_id'])"
   ```
3. Edit the hardcoded ID in
   [functions/lambda_orchestrator_handler.py](functions/lambda_orchestrator_handler.py#L144):
   ```python
   orchestrator_runtime_id = 'orchestrator_runtime-6UF3HDGyvL'   # replace with the ID from step 2
   ```
4. Redeploy just that Lambda (reuses the existing function/API Gateway,
   same endpoint URL):
   ```bash
   export AWS_PROFILE=StandardAccess-450410489798
   python3 scripts/deploy_lambda_api_gateway_boto3.py
   ```
5. Run the dashboard with no `ORCHESTRATOR_URL` override — its default
   already points at the shared API Gateway endpoint:
   ```bash
   python3 -m src.dashboard.app
   ```
6. **Revert when done** — change `orchestrator_runtime_id` in step 3 back
   to `orchestrator_runtime-6UF3HDGyvL` and re-run step 4. Skipping this
   leaves every other team's dashboard silently hitting your team's
   runtime instead of the shared reference deployment, since the endpoint
   URL itself never changes.