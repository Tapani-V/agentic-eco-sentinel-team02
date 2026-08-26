# AgentCore Memory — Known Issues in Current Implementation

Notes from reviewing the current AgentCore Memory Service implementation
(`src/memory/`, its integration in `src/graph/workflow_agentcore.py`, and
related deploy/seed scripts). These are the concrete gaps found before any
integration into a new branch.

## 1. Memory is never actually activated in the deployed AgentCore Runtime path

`AgentCoreworkflow.__init__` accepts an optional `memory_client=None`, and the
node functions gate every read/write behind `if state.get('memory_enabled') and
self.memory_client`. The AgentCore Runtime entrypoint (`orchestrator/handler.py`
→ `_get_workflow()`) never reads `AGENTCORE_MEMORY_ID`, never constructs a
`MemoryClient`, and never passes one into `AgentCoreworkflow(...)`. The
`initial_state` dict it builds also never sets `memory_enabled`, `session_id`,
or the other memory-related keys.

Result: every memory read/write in the LangGraph nodes is silently skipped in
the actual deployed runtime. The feature is fully coded but inert in production
as currently wired.

## 2. Memory is only "live" in the local dashboard, and only for reading

The only place a `MemoryClient` is actually constructed and used is the local
FastAPI orchestrator app (`orchestrator/app.py`), and only to enrich dashboard
API responses (`memory_context` field) — a read-only display path. The
HTTP-based workflow used there does not pass `memory_client` into the
workflow at all, so it doesn't influence any agent decision (confidence,
routing, dedup, etc.) — only what the dashboard displays.

## 3. The seeded "memory" data is fully synthetic and unrelated to the project's real device dataset

The memory-seeding script generates its own device list, degradation score
curves, and anomaly names via `random.uniform()`/`random.sample()` calls,
hardcoded per equipment "profile" (`healthy`, `degrading`, `critical`,
`intermittent`). It reuses the same device *names* as the real synthetic
dataset for visual consistency, but none of the actual historical values are
read from the project's real device data files. It writes directly into the
Memory resource via boto3, bypassing all orchestration/agent code. This is
useful to make the dashboard look populated but is not evidence that the
memory read/write path works when driven by real agent traffic.

## 4. Work-order deduplication does not actually prevent duplicate work orders

The dedup check (looking for a recent matching diagnosis category in memory)
runs inside the orchestrator's diagnosis-agent workflow node, gating only
whether a *memory* record gets written (`store_work_order`). By the time this
check runs, the DiagnosisAgent has already executed and already called the
real `create-work-order` MCP tool directly (see `_execute_action` in the
diagnosis agent) — the real work order in DynamoDB is created regardless of
what the dedup check decides afterward.

For dedup to actually prevent a duplicate real work order, the check needs to
happen *before* invoking DiagnosisAgent (or a flag needs to be passed into
DiagnosisAgent's payload so it can itself skip the create-work-order call).

## 5. Trend detection / confidence boosting have limited value against the project's current data

The project's sensor data source is a static, pre-generated array per device
(uploaded once to S3, never appended to). "Get the latest reading" always
returns the same last entry of that array — repeated analysis of the same
device returns an identical reading every time. Memory's cross-invocation
trend detection and diagnosis-confidence boosting are designed around data
that changes between calls; against a frozen dataset they either detect
nothing new or trigger identically on every repeat run, so they don't
currently demonstrate real value. They would become meaningful once sensor
data is live/streaming or the loader is changed to advance through history
per call.

## 6. Overlap with existing DynamoDB tables

The memory `maintenance-actions` namespace stores a lightweight duplicate of
work order identifying fields (`device_id`, `work_order_id`,
`diagnosis_category`, `severity`, `action_type`, `creation_timestamp`) that
already live in the real `work_orders` DynamoDB table (with the full record —
status, assigned_to, hours, description, etc.). These two copies are written
independently and have no sync mechanism, so they can drift. DynamoDB should
remain the single system of record; the memory copy should only ever be used
as a disposable dedup cache, never treated as authoritative by the dashboard
or any other consumer.

## 7. No confirmed end-to-end validation with real deployed traffic

Test coverage that exists (`test_circuit_breaker.py`, `test_cold_start.py`,
`test_memory_client.py`) exercises the `MemoryClient` in isolation with mocked
boto3 clients. Combined with points 1–3 above, there is no evidence the full
loop (real device analysis → agent decision informed by memory → memory
write → later read influencing a later decision) has ever actually run
end-to-end against a live-deployed AgentCore Runtime.
