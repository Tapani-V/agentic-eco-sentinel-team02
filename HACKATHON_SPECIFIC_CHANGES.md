# Hackathon-Specific Changes / Known Issues (To Be Fixed in a Separate Branch)

This document tracks known issues discovered while preparing hackathon material for this
project. **No code has been changed yet** — these are notes for follow-up work on a
dedicated fix branch, not a description of changes already made.

---

## Issue 1: `docker-compose.yml` builds the wrong Dockerfiles for local dev

### Symptom
Running `docker-compose up` today will **not** produce a working local dev environment.

### Root cause
- `docker-compose.yml` builds from the root-level `Dockerfile.health_agent`,
  `Dockerfile.diagnosis_agent`, and `Dockerfile.orchestrator`.
- These three root Dockerfiles were changed (commit `79b99ff`, "Fix AgentCore Runtime
  invocation protocol and agent logic bugs") to target **AWS Bedrock AgentCore Runtime**:
  they `CMD` into `agentcore_entrypoint.py`, listen on port `8080`, and health-check `/ping`.
- `docker-compose.yml` itself still expects the **old local-dev contract**: ports
  `8001`/`8002`/`8000`, health checks against `/health`, and orchestrator env vars like
  `HEALTH_AGENT_URL=http://health-agent:8001`.
- Verified via `git show`/`git diff` across the repo's history that `docker-compose.yml`'s
  `dockerfile:` fields have **always** pointed at these root Dockerfiles — never at the
  nested `src/services/<agent>/Dockerfile` files (see Issue 1a below). This is not a
  regression from a recent edit; the mismatch was introduced when the root Dockerfiles were
  repurposed for AgentCore without updating `docker-compose.yml` to match.

### Issue 1a: the nested `src/services/<agent>/Dockerfile` files are orphaned
- `src/services/health_agent/Dockerfile`, `src/services/diagnosis_agent/Dockerfile`, and
  `src/services/orchestrator/Dockerfile` still contain the *correct* original local-dev
  content (e.g. `CMD ["python", "-m", "uvicorn", "src.services.diagnosis_agent.app:app",
  "--port", "8002"]`, healthcheck via `httpx.get('http://localhost:8002/health')`).
- These files exist since the initial commit and have never been modified — but they are
  also **never referenced by any docker-compose.yml at any point in git history**. The only
  place that even checks for their existence is `scripts/preflight_check.sh` (an
  existence check, not a build step).

### Recommended fix (not yet implemented)
Point `docker-compose.yml`'s three `dockerfile:` fields at the nested
`src/services/<agent>/Dockerfile` files instead of the root `Dockerfile.<agent>` files.
This is a 3-line change, requires no changes to the AgentCore build/deploy scripts (they
reference the root Dockerfiles directly by filename, not via docker-compose), and restores
the local dev flow to match what docker-compose already expects (ports, `/health`, env vars).

### Workaround for hackathon participants (until fixed)
Skip Docker Compose for local dev entirely; run each agent directly with uvicorn:
```bash
python -m uvicorn src.services.health_agent.app:app --port 8001
python -m uvicorn src.services.diagnosis_agent.app:app --port 8002
python -m uvicorn src.services.orchestrator.app:app --port 8000
```

---

## Issue 2: Confusing "Lambda-style" (`lambda_handler`) naming in AgentCore handlers

### What exists today
Each agent has an AgentCore-specific entry point at
`src/services/<agent>/handler.py` (e.g.
[src/services/diagnosis_agent/handler.py](src/services/diagnosis_agent/handler.py)), which
defines:
```python
def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    ...

def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Alternative entry point name"""
    return lambda_handler(event, context)
```
These are loaded generically by the shared `agentcore_entrypoint.py`, which checks
`hasattr(module, 'lambda_handler')` then falls back to `hasattr(module, 'handler')`, and
wraps whichever one it finds with `bedrock_agentcore.runtime.BedrockAgentCoreApp`.

### Why this is confusing
- **AgentCore itself does not require this naming.** It only requires a callable shaped
  `(payload) -> result`, wired up via `@app.entrypoint` inside `agentcore_entrypoint.py`.
  The names `event`, `context`, and `lambda_handler` are pure convention, not a technical
  requirement of AgentCore Runtime.
- **These handler.py files are not actually deployed as real AWS Lambda functions.**
  Confirmed via repo-wide search: they are only ever referenced by
  `agentcore_entrypoint.py` and the three root Dockerfiles' `CMD` lines. The genuinely
  Lambda-deployed files in this repo are different ones entirely —
  `tools/lambdas/schedule_maintenance_handler.py`, `tools/lambdas/get_spare_parts_handler.py`,
  and `functions/lambda_orchestrator_handler.py`. The `lambda_handler` name here was
  borrowed purely for naming consistency with those other files, not because the code is
  reused across both deployment targets.
- **The `context` parameter is dead weight.** It's accepted and documented but never
  actually used anywhere inside these handler.py files — kept only to visually resemble a
  Lambda signature.
- **There's a redundant second name (`handler`) for the same function**, which exists only
  because `agentcore_entrypoint.py`'s fallback check looks for it. Two names, no functional
  difference — likely to trip people up when explaining "which one actually gets called?"
- Verified via git history: `handler.py` (with this naming) was introduced in the **same
  commit** that migrated these agents to AgentCore (`79b99ff`) — it wasn't inherited from an
  earlier, genuinely-Lambda-deployed version of the file.

### Rename impact if changed later (analysis only, not yet done)
- Renaming the **function** inside `handler.py` is safe as long as either `lambda_handler`
  or `handler` still exists as an attribute on the module (that's all
  `agentcore_entrypoint.py` checks for). Rename both away, and the container will fail at
  startup with `AttributeError: No handler function found in <module>`.
- Renaming/moving the **file** requires updating the corresponding `CMD` line in that
  agent's root Dockerfile (e.g. `Dockerfile.diagnosis_agent`'s
  `src.services.diagnosis_agent.handler` argument) and rebuilding the image.
- Blast radius is isolated per agent — health_agent, diagnosis_agent, and orchestrator each
  have their own independent `handler.py` + Dockerfile, so a rename in one doesn't affect
  the others.
- Local dev (`src/services/<agent>/app.py`, run via uvicorn) does not import anything from
  `handler.py` — confirmed via search, zero cross-references — so this rename would have
  **no effect** on the local uvicorn dev flow, only on the AgentCore/Docker deployment path.

### Recommended fix (not yet implemented)
Consider renaming `lambda_handler`/`handler` to something more neutral (e.g. `invoke` or
`process`) across the three `handler.py` files, and updating `agentcore_entrypoint.py`'s
`hasattr` checks to match — purely a clarity improvement, not a bug fix.

---

## Issue 3: `min_instances`/`max_instances` scaling config is dead — never reaches AWS

### What exists today
Each agent's `agents/<agent>/agentcore.yaml` declares a scaling block, e.g.
[agents/health_agent/agentcore.yaml](agents/health_agent/agentcore.yaml):
```yaml
deployment:
  scaling:
    min_instances: 0
    max_instances: 3
    target_utilization: 70
```
`scripts/deploy_to_agentcore_boto3.py` (the script that actually created the live runtimes)
also has its **own separate, hardcoded** copy of these numbers in an `agents_config` dict
(different values per agent — e.g. orchestrator 1-5, workers 0-3).

### Root cause / verified facts
- `deploy_to_agentcore_boto3.py` never opens or reads `agentcore.yaml` at all — it only uses
  its own hardcoded `agents_config` dict.
- Even that hardcoded dict's `min_instances`/`max_instances` are read into local variables
  and used **only for a log line** (`logger.info(f"Instances: {min_instances}-{max_instances}")`).
  They are never included in the actual `create_agent_runtime()` / `update_agent_runtime()`
  boto3 calls — those only send `agentRuntimeName`, `agentRuntimeArtifact` (container image
  URI), `roleArn`, `networkConfiguration`, `environmentVariables`, and `tags`. No CPU,
  memory, or instance-count field is ever sent to AWS.
- So neither the YAML nor the script's hardcoded numbers have ever actually configured
  anything in AWS — both are dead/cosmetic config.

### How scaling actually works instead (confirmed via AWS official docs)
AgentCore Runtime's default compute type is **microVMs**: "fully managed, serverless
sessions that start instantly and scale on demand" — each user session runs in its own
dedicated, isolated microVM that is provisioned on invocation and terminated after the
session completes, with consumption-based billing. There is no customer-configurable
"instance count" being set by this project at all — scaling is fully automatic and
per-session at the AWS infrastructure level, unrelated to the `min_instances`/
`max_instances` values sitting in the YAML/script.
- Source: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html

### Recommended fix (not yet implemented)
Either remove the misleading `scaling:` blocks from `agentcore.yaml` and the hardcoded dict
in `deploy_to_agentcore_boto3.py` (since they do nothing), or clearly comment them as
"informational only, not applied" to avoid confusing future readers into thinking this
project is doing explicit instance-count scaling configuration.

---

## Decision: keep boto3 deployment, do NOT switch to starter-toolkit + CodeBuild

### Why boto3-direct was chosen over the toolkit originally
Documented in `agentcore_migration_implementation_steps.md` ("Why Boto3 Direct API vs
toolkit framework"): simpler (no framework dependencies), cleaner (no config duplication),
faster (deploys pre-built images, no rebuild step), and avoids toolkit bugs hit elsewhere in
this project (`create_mcp_gateway_target()` crashing on `openApiSchema` with empty
credentials — see `agentcore_creation_doc.md` and `WEEK2_DAY1_4_STEP_BY_STEP.md`).

### The starter-toolkit's CodeBuild path also hit an IAM wall in the reference project
`reference/plant_Advisor/02_plant_advisor_runtime_mem.ipynb` shows the toolkit's
`Runtime.launch()` defaults to `use_codebuild=True`, which tries to **auto-create** a
CodeBuild execution role — this failed with `AccessDenied` on `iam:CreateRole` due to this
AWS account's `GroupIT_ProjectStandardAccess` guardrail policy (see
`/memories/repo/aws_iam_guardrails.md`). The guardrail only blocks role creation that lacks
the `GroupIT_ProjectPermissionBoundary` permissions boundary — so this is fixable by
pre-creating the CodeBuild execution role via CLI with that boundary attached, then setting
`codebuild.execution_role: <arn>` in `.bedrock_agentcore.yaml` instead of leaving it `null`
(auto-create).

### Why we're not doing this fix/switch for the hackathon anyway
- Deployment mechanics (CodeBuild+toolkit vs. boto3+manual ECR push) and code structure
  (generic `agentcore_entrypoint.py` vs. simplified per-agent files) are **orthogonal** —
  either code structure can pair with either deployment method.
- Hackathon participants work locally via `uvicorn` by default; AgentCore deployment is
  opt-in/gated, so almost nobody touches the deploy scripts during the event — fixing this
  only helps admins, not participants.
- CodeBuild adds more moving parts (its own IAM role, a source S3 bucket, extra service
  permissions) — more that can break mid-hackathon, for a benefit (skipping slow local
  ARM64 cross-builds) that doesn't matter to teams writing agent logic.
- It's unvalidated for this project's actual 3-agent/3-runtime shape (Plant Advisor is
  single-agent) — risky to introduce right before a time-boxed event on top of an
  already-working, already-curl-verified boto3 pipeline.
- If hackathon teams get separate/isolated AWS sandbox accounts, the CodeBuild-role
  pre-creation step would need to be redone per account anyway — it relocates the
  governance friction rather than removing it.

**Conclusion**: keep `deploy_to_agentcore_boto3.py` as-is. If any pre-hackathon cleanup
time is spent, spend it on Issue 2 (simplifying the 3 `handler.py` files to the
Plant-Advisor-style single-file-per-agent pattern) — that's what participants actually read
and extend, with zero risk to the already-working deployment pipeline.

---

## Status
All three issues are confirmed via code/git history/AWS docs but **intentionally not fixed
yet**. Planned to be addressed on a separate branch, to avoid disrupting the
current branch.
