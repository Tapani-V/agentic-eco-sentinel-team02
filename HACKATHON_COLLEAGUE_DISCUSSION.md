# Colleague Discussion Guide — Hackathon Setup

**Purpose:** structured questions and decisions to work through with your colleague before
finalizing the `event/hackathon` branch. Two parts: (1) questions to understand his
existing implementation, (2) decisions that need to be made jointly for the event.

---

## Part 1 — Questions about his implementation

### LLM switch (Bedrock Nova Lite)
1. Is the switch from Azure OpenAI to `amazon.nova-lite-v1:0` fully tested end-to-end, or
   still partially validated?
2. Any prompt/output differences from Azure OpenAI he had to work around (formatting,
   token limits, response structure)?
3. Any Bedrock model-access or quota setup needed in the account that isn't obvious from
   the code (e.g. requesting model access in the Bedrock console)?

### AgentCore Memory Service
4. Did he ever run this end-to-end through the real orchestrator handler, or only through
   `tests/test_cold_start.py` directly against `AgentCoreworkflow`?
5. Is he aware that `handler.py`'s `_get_workflow()` never passes a `MemoryClient`
   instance, and `initial_state` never sets `memory_enabled`/`session_id` — meaning the
   feature is currently inert in the live handler even on his most recent branch?
6. Was wiring it into the handler an intentional next step he ran out of time for, or was
   it meant to stay a standalone/library feature for now?
7. If we decide to finish wiring it before the event — any gotchas he'd flag (DynamoDB
   table provisioning, IAM permissions for the memory store, cold-start behavior)?

### Deployment pipeline (CodeBuild + boto3)
8. Did he personally run `scripts/deploy_codebuild_pipeline.py` end-to-end successfully?
   Any IAM roles/prerequisites it assumes but doesn't create itself?
9. What was his actual deployment sequence — CodeBuild pipeline for image build/push, then
   which registration script (`deploy_to_agentcore.py` starter-toolkit, or
   `deploy_to_agentcore_boto3.py`)?
10. Did he hit the same starter-toolkit issues you did, or avoid that path entirely?

### React dashboard / CloudFront
11. Is `feat/cloudfront-deployment` fully functional and tested against the live API, or
    still work-in-progress?
12. Any known issues or incomplete pieces in the React frontend he'd want fixed before
    handing it to hackathon participants (if we go that route)?

### Shared infrastructure
13. Are the two Secrets Manager secrets (`agentic-ai-poc-3-1-cognito-secret`,
    `agentic-ai-poc-gateway-url`) currently populated and valid? Who manages/rotates them?
14. Is `DYNAMODB_TABLE_NAME` (seen in env config) a leftover from an earlier design, or
    something still actively used?

### Process
15. Is he OK with the hackathon branch cherry-picking only specific pieces (LLM switch,
    CodeBuild script) from `migration/agentcore-updated`, rather than merging it wholesale?
16. Does he want to co-present or be available during the event for questions on the parts
    he built, if a team picks memory, CodeBuild, or the React dashboard as their track?

---

## Part 2 — Decisions to finalize together

Each item below has the current recommendation (from prior analysis) plus the trade-off,
so you can decide together rather than re-litigating from scratch.

### 1. Memory feature: fix or cut from the hackathon branch?
- **Recommendation:** cut for now, offer as an advanced/bonus track using the existing
  `src/memory/` module as a library.
- **Trade-off:** fixing it is a small, well-scoped patch (pass `MemoryClient` into the
  workflow constructor + set 4 state fields) — feasible before Sept 2 if you'd rather
  ship it as a working feature than a stretch goal.

### 2. Dashboard: Jinja2 or React?
- **Recommendation:** keep Jinja2 — lower setup cost, no npm/TypeScript needed, merge
  conflicts solved by assigning disjoint sections per team.
- **Trade-off:** React gives per-component isolation and a nicer demo "wow factor," at
  the cost of a steeper ramp-up for non-expert participants in a single day.

### 3. Deployment model for the event day
- **Recommendation:** all teams work locally (`uvicorn`/docker-compose) against the
  shared, already-deployed AWS Gateway/Cognito/S3 data. AgentCore Runtime deployment is
  an optional stretch goal only, not part of the normal build loop.
- **Trade-off:** if you want every team to experience a real cloud deployment, that adds
  meaningful time (image build/push + runtime registration takes minutes per agent) and
  risk (starter-toolkit fragility, runtime name collisions between teams).

### 4. AgentCore runtime naming (only relevant if #3 allows stretch-goal deployment)
- **Recommendation:** require a `TEAM_ID` in each team's config so runtime names are
  namespaced (e.g. `health_agent_teamA_runtime`), preventing one team's deploy from
  overwriting another's.
- **Decide:** who assigns team IDs, and who owns cleanup of these test runtimes after the
  event.

### 5. MCP tool catalog — only 2 tools exist today
- **Recommendation:** add 2-4 more generic tools before the event (e.g.
  maintenance-history lookup, notification, logging) so teams have real variety without
  touching the shared Gateway themselves. For anything beyond that, teams use a local
  "mock tool" pattern instead of registering new Gateway targets mid-event.
- **Decide:** who builds the extra tools (you, him, split), and by when.

### 6. Credentials & cost guardrails for the event day
- **Decide:** shared read/invoke-scoped credentials distributed to all teams, or
  individual per-team credentials? Is a billing/budget alarm worth setting up for the day
  given 3-4 teams hitting Bedrock/Gateway simultaneously?

### 7. Branch & documentation scope for `event/hackathon`
- **Recommendation:** lean root with only `README.md`, `ARCHITECTURE.md`,
  `HACKATHON_README.md`; both docker-compose and AgentCore Dockerfiles kept side by side
  in clearly separate locations; handler files renamed away from `lambda_handler` for
  clarity.
- **Decide:** does he want to review this branch before it's treated as final, given it
  deliberately excludes his memory and React work for now?

### 8. Team tracks (pick 3-4)
- **Current shortlist:** new agent, new MCP tool (via mock pattern or the expanded
  catalog), new equipment type, dashboard feature, memory wiring (bonus/advanced).
- **Decide:** does he have other feature ideas worth adding as a track?

### 9. Presentation responsibilities
- **Decide:** who presents architecture vs. live demo vs. handles Q&A; does he co-present
  any section, especially parts he personally built.

### 10. Shared-state hygiene during the event
- **Decide:** do teams get a naming/namespace convention (e.g. device-id prefix per team)
  to avoid polluting shared S3/DynamoDB data with test writes, and who resets data
  before/after the event.

### 11. Docker-compose Dockerfile mismatch — fix scope
- **Context:** confirmed bug — `docker-compose.yml` points at the root
  `Dockerfile.<agent>` files, which are actually wired for AgentCore Runtime (port 8080,
  `agentcore_entrypoint.py`), not local dev (port 800x, `app.py`). Nested
  `src/services/<agent>/Dockerfile` files already exist and are the correct local-dev
  ones, just not referenced by docker-compose.
- **Decide:** fix this only on `event/hackathon`, or also on the shared/main branch since
  it's a real bug independent of the hackathon?

### 12. Timeline / logistics
- **Decide:** block time with him for the Sept 1 dry run and confirm his availability on
  Sept 2 itself.

### 13. Shared DynamoDB/Gateway tables — no local emulation exists
- **Context:** confirmed `docker-compose.yml` has no local DynamoDB/mock service — it
  mounts `~/.aws:/root/.aws:ro` and loads `.agentcore.env`, so local docker-compose runs
  call the exact same real AWS AgentCore Gateway → Lambda → DynamoDB tables
  (`agentic-maintenance-schedule`, etc.) as an AgentCore Runtime deployment would. There's
  no separate "local" data store to reset between teams.
- **Recommendation:** namespace by device-ID prefix per team (cheap, no infra change)
  rather than provisioning separate tables/gateways per team.
- **Decide:** is device-ID prefixing sufficient, or does he want per-team
  tables/Gateway targets given this is genuinely shared, real production infrastructure?

---

## Decision log (fill in during the session)

| # | Topic | Decision | Owner | Due |
|---|---|---|---|---|
| 1 | Memory: fix or cut | | | |
| 2 | Dashboard: Jinja2 or React | | | |
| 3 | Deployment model for event day | | | |
| 4 | Runtime naming convention | | | |
| 5 | MCP tool catalog expansion | | | |
| 6 | Credentials & cost guardrails | | | |
| 7 | Branch/docs scope sign-off | | | |
| 8 | Final team tracks | | | |
| 9 | Presentation responsibilities | | | |
| 10 | Shared-state hygiene | | | |
| 11 | Docker-compose fix scope | | | |
| 12 | Dry-run / event-day availability | | | |
| 13 | Shared DynamoDB/Gateway isolation approach | | | |
