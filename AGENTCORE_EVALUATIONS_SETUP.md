# AgentCore Evaluations — Setup Notes

## What this feature is
Amazon Bedrock AgentCore **Evaluations** is a separate top-level AgentCore service (distinct from Observability/Tracing) that automatically scores agent quality using LLM-as-a-judge techniques, working from the OpenTelemetry traces/spans your runtimes already emit. Results surface inside CloudWatch alongside Observability data.

There are 3 evaluation types:
- **Online evaluation** — continuously samples a percentage of live production traffic from a CloudWatch log group / agent runtime endpoint. Runs on an ongoing basis via a service execution role. This is what the console's "Create evaluation configuration" flow sets up.
- **Batch evaluation** — one-off job scoring a set of past sessions (time range, session IDs, or full log group). Runs under **your own IAM credentials**, no separate service role needed.
- **On-demand evaluation** — score specific spans/traces by ID, synchronously, using your own IAM credentials.

The console error `Failed to create IAM role ... AgentCoreEvalRole-<timestamp> ... explicit deny` happens because our account's `GroupIT_ProjectStandardAccess` SCP denies `iam:CreateRole` unless a permissions boundary matching `GroupIT_*PermissionBoundary` is attached — and the console's auto-create-role flow doesn't attach one. So the console's "Create and use a new service role" option cannot work here; you must pre-create the role yourself and pick "Use an existing role" instead.

## The role: `AgentCoreEvalRole`
Created manually on 2026-08-20 (account `450410489798`, region `us-east-1`) because the console can't auto-create it under this account's guardrails.

- ARN: `arn:aws:iam::450410489798:role/AgentCoreEvalRole`
- Permissions boundary: `arn:aws:iam::450410489798:policy/GroupIT_ProjectPermissionBoundary` (required by the `GroupIT_ProjectStandardAccess` deny-unless-boundary-attached rule — same boundary used by `AgentCoreExecutionRole`)
- Trust policy: scoped per [AWS's official docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations-prerequisites.html) — only `bedrock-agentcore.amazonaws.com` can assume it, and only when the `SourceArn` is one of this account's own `evaluator/*` or `online-evaluation-config/*` resources.
- Inline permissions policy: `AgentCoreEvaluationsPermissions` — grants exactly what AWS docs specify:
  - `logs:DescribeLogGroups` / `GetQueryResults` / `StartQuery` — read agent trace sessions from CloudWatch Logs
  - `logs:CreateLogGroup` / `CreateLogStream` / `PutLogEvents` scoped to `/aws/bedrock-agentcore/evaluations/*` — write evaluation results
  - `logs:DescribeIndexPolicies` / `PutIndexPolicy` scoped to the `aws/spans` log group — configure log indexing for trace analysis (Transaction Search)
  - `bedrock:InvokeModel` / `InvokeModelWithResponseStream` on `foundation-model/*` and `inference-profile/*` — only needed if using a custom (LLM-as-judge) evaluator; built-in evaluators also route through this

Source JSON files used to create/update the role (kept in `/tmp`, not committed — recreate from this doc if needed):
- Trust policy: `/tmp/agentcore_eval_trust_policy_v2.json`
- Permissions policy: `/tmp/agentcore_eval_permissions_policy.json`

## How to use it in the console
1. Bedrock AgentCore console → **Evaluation** → **Create evaluation configuration**.
2. Pick data source (agent endpoint or CloudWatch log group + service name, e.g. `orchestrator_runtime.DEFAULT`).
3. Pick evaluators (built-in, e.g. `Builtin.Helpfulness`, `Builtin.GoalSuccessRate`).
4. Under **Amazon Bedrock IAM role**, choose **Use an existing role** → `AgentCoreEvalRole`. Do **not** choose "Create and use a new service role" — it will fail with the same `iam:CreateRole` explicit-deny error described above.

## If this role needs recreating elsewhere
Reference: [Evaluations prerequisites — Service execution role](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations-prerequisites.html#service-execution-role) (AWS Console option). Remember to attach `GroupIT_ProjectPermissionBoundary` at creation time — any `iam:CreateRole` call in this account without that boundary is explicitly denied by `GroupIT_ProjectStandardAccess`.

## IMPORTANT: zero-results root cause — wrong log group (2026-08-20)

After the role/permissions were correctly configured, both the online evaluation config and a batch evaluation still found **zero sessions**, despite `orchestrator_runtime` handling plenty of traffic. Root cause: the evaluation's `dataSourceConfig.cloudWatchLogs.logGroupNames` was set to the **per-runtime log group**:

```
/aws/bedrock-agentcore/runtimes/orchestrator_runtime-6UF3HDGyvL-DEFAULT
```

But that log group only contains `[runtime-logs]<uuid>` stdout streams — **no `spans` stream**. Per AWS's [span destination docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html#observability-configure-unified-traces), an agent's spans go either to its own log group's `spans` stream (if `UNIFIED_TRACES_DESTINATION_ENABLED=true`) or to the account's **shared `aws/spans` log group** (the default for agents created before a region supported the unified destination, or with the env var unset/false). This project's runtimes use the shared `aws/spans` destination — confirmed by scanning it directly and finding hundreds of `orchestrator_runtime.DEFAULT` spans/hour. The `serviceNames` filter (`orchestrator_runtime.DEFAULT`) was always correct — only the `logGroupNames` was wrong.

**Fix applied**: updated the online evaluation config's `dataSourceConfig` to:
```json
{
  "cloudWatchLogs": {
    "logGroupNames": ["aws/spans"],
    "serviceNames": ["orchestrator_runtime.DEFAULT"]
  }
}
```
via `bedrock-agentcore-control` `update_online_evaluation_config`. A batch evaluation created with the same corrected `dataSourceConfig` immediately began actually processing (stayed `IN_PROGRESS` for minutes and created a non-empty output log stream) instead of completing instantly with 0 sessions — confirming the fix.

**Lesson**: When setting up any new AgentCore Evaluations (online or batch) for an agent, first check whether that agent's spans land in its own log group's `spans` stream or in the shared `aws/spans` log group (`aws logs describe-log-streams` on the per-runtime log group — if there's no `spans` stream, use `aws/spans` in the evaluation's `dataSourceConfig` instead). Don't assume the per-runtime log group convention shown in AWS's example docs.
