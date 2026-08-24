# Hackathon Prep Plan

**Event date:** September 2, 2026
**Teams:** 3-4
**Prepared:** August 24, 2026 (9 days before the event)

This document captures the plan for preparing a dedicated hackathon branch of this
project, what to teach participants, and how to run the event day itself. It is a
planning document — no code has been changed yet as a result of it.

---

## 1. Branch strategy

Create `hackathon/main` off the current `migration/agentcore-langgraph` branch (already
has LangGraph orchestration reintroduced — keep it as the base). Do **not** merge the
colleague's `migration/agentcore-updated` wholesale. Instead, cherry-pick selectively:

| Bring in? | Item | Reason |
|---|---|---|
| ✅ Yes | LLM switch → Amazon Bedrock Nova Lite (`amazon.nova-lite-v1:0`) | Current branch uses Azure OpenAI, which undermines the "AWS-specific hackathon" story. This is the single highest-priority fix. |
| ✅ Yes | `scripts/deploy_codebuild_pipeline.py` (boto3-based CodeBuild image pipeline) | Lets teams without local Docker still get images built/pushed to ECR, without depending on the fragile starter-toolkit. |
| ⚠️ Decide | React dashboard (`feat/cloudfront-deployment`) | See section 3 — recommendation is to NOT bring this in for the default track. |
| ❌ No (as-is) | AgentCore Memory Service | Verified non-functional in the live orchestrator handler (see section 2, item 2). Don't ship inert code participants will assume works. |
| ❌ No | ECS-based dashboard deployment | Heavier ops surface than needed for a single-day event. |

---

## 2. Must-fix / must-decide list before the branch is "hackathon-ready"

1. **LLM → Bedrock Nova Lite.** Non-negotiable for the AWS-specific framing of the event.
2. **AgentCore Memory feature — fix or cut.** Root cause already diagnosed: `handler.py`'s
   `_get_workflow()` never passes a `MemoryClient` instance into `AgentCoreworkflow(...)`,
   and `initial_state` never sets `memory_enabled`/`session_id`/`device_profile`/
   `diagnosis_history`. Two options:
   - Complete the wiring before the event, then offer "extend memory" as a track.
   - Leave it out of the hackathon branch entirely, and offer "wire up memory from
     scratch" (using the existing `src/memory/` module) as an advanced/bonus track.
3. **Deployment target for the event day** — decided as: local-only via `docker-compose`
   / `uvicorn`, against the already-deployed shared AWS Gateway/Cognito/S3 data. No team
   deploys its own AgentCore Runtime during the event (see section 6). AgentCore
   deployment is an optional stretch goal only, using the existing boto3 script.
4. **Trim root-level documentation clutter.** The repo currently has 80+ markdown files
   from personal iteration history. The hackathon branch should have a lean root with
   only the docs participants actually need.

---

## 3. Dashboard: Jinja2 vs. React

**Recommendation: keep the current Jinja2 dashboard, do not switch to React for the
default track.**

Reasoning:
- React buys per-component merge-conflict isolation, but costs npm/Vite setup per
  laptop, TypeScript literacy, and a new component/data-fetching pattern to teach —
  too much new surface area for a one-day event with non-expert participants.
- The Jinja2 monolith's merge-conflict risk (one 1282-line `index.html`) is solved more
  cheaply by assigning each team a disjoint section of the dashboard (e.g. Team A:
  alerts tab, Team B: maintenance tab, Team C: a new KPI card) so nobody edits the same
  lines.
- The presenter already knows this codebase; React would need to be mastered well
  enough to debug live on the day, which is extra risk for no clear payoff.

If the "wow factor" of React is still wanted, offer it as an optional advanced track
for whichever single team is most comfortable with JavaScript/TypeScript — not as the
default for everyone.

---

## 4. Kickoff curriculum (~30-45 minutes)

Suggested order for the intro talk:

1. **Big picture (5 min)** — 3 services (HealthAgent, DiagnosisAgent, Orchestrator) plus
   a dashboard, all talking to real AWS: Cognito-secured MCP Gateway, S3 device data,
   Bedrock LLM.
2. **LangGraph orchestration (10 min)** — the shared state dict, the 4 nodes, and the
   router's conditional edge. Use the diagram below and the "mailroom" analogy:
   - The **router node** is the person who reads a letter and decides "URGENT" or
     "ROUTINE" (the actual `if` check).
   - The **`route_condition` function** is the intern who just reads the stamp aloud —
     no decision-making, just reporting what was already decided.
   - The **routing dictionary** (`{'end': 'aggregator', 'diagnose': 'diagnosis_agent'}`)
     is the wall chart saying which bin each stamp goes into.

   ```mermaid
   graph LR
       A[health_agent] --> B[router]
       B -- healthy --> D[aggregator]
       B -- warning/critical --> C[diagnosis_agent]
       C --> D
       D --> E[END]
   ```

3. **Core-vs-wrapper pattern (5 min)** — every agent has a "brain" file
   (`src/agents/*.py`, plain Python, no framework) and a "phone line" file
   (`src/services/*/app.py`, the FastAPI wrapper). This is the single idea that makes
   "add a new agent" approachable for non-experts.
4. **MCP tools (5 min)** — how agents call tools like `create-work-order` and
   `get-spare-parts` via `GatewayClient`. Calling an existing tool from a new context is
   an easier extension point than building a whole new agent.
5. **Live demo (10 min)** — add a trivial new node to the graph live, to prove the
   pattern is real and give teams a template to copy.
6. **How to run it locally** — one command, one URL, no AWS deployment needed for the
   day.

---

## 5. Suggested team tracks (pick 3-4, low mutual conflict)

- **New agent** — e.g. a `MaintenanceSchedulerAgent`: new graph node, own FastAPI
  service.
- **New MCP tool integration** — extend an existing agent to call a new (or mocked)
  tool.
- **New equipment type** — extend HealthAgent's threshold rules and synthetic data for
  a device type that doesn't exist yet.
- **Dashboard feature** — new tab/widget on an assigned, disjoint section of the
  Jinja2 template.
- **(Advanced / bonus) Wire up AgentCore Memory** — using the diagnosed gap as a
  starting point; a good "detective work" track for a stronger team.

---

## 6. How the project is made available to participants

All teams run **locally** via `docker-compose` (or plain `uvicorn`, three processes)
against the single, already-deployed shared AWS Gateway/Cognito/S3 data. No team
provisions or deploys its own AgentCore Runtime during the event — that avoids the
deployment fragility already identified with the starter-toolkit and CodeBuild IAM
setup. Deploying to AgentCore Runtime (via the existing boto3 script) is offered only
as a stretch goal for teams that finish early.

Each participant needs:
- Repo clone (`hackathon/main` branch)
- Python virtual environment
- A distributed, pre-populated `.agentcore.env` (or read-only IAM credentials) for the
  shared Cognito/Gateway values
- Docker (optional — `uvicorn` alone is sufficient)

A single `QUICKSTART.md` plus a working setup script is worth preparing so day-one
setup isn't lost to `pip install` debugging.

---

## 7. Timeline (August 24 → September 2)

| When | What |
|---|---|
| Aug 24-26 | Decide open items with colleague; create `hackathon/main`; cherry-pick Bedrock LLM fix and CodeBuild script. |
| Aug 26-28 | Decide on memory (fix vs. cut); trim root-level docs; confirm local dev path works end-to-end from a fresh clone. |
| Aug 28-30 | Write `QUICKSTART.md` and a one-page "add an agent" cheat sheet; assign the team tracks. |
| Aug 30-31 | Build slides (architecture diagram, LangGraph explainer, live-demo script). |
| Sept 1 | Full dry run: fresh clone → setup → live "add a node" demo, timed. |
| Sept 2 | Hackathon. |

---

## 8. Discussion items with colleague

- Merge his memory work now (fix the wiring), or shelve it as a bonus track?
- OK with cherry-picking only the LLM and CodeBuild pieces rather than the full
  `migration/agentcore-updated` branch?
- Available during the event for questions on his pieces (memory, CodeBuild) if a team
  picks those tracks?
- Shared AWS credentials/Secrets access for the day — already provisioned, or still
  needs setting up?

---

## 9. Open decisions before implementation starts

1. Fix the memory wiring gap, or cut it and offer it as a bonus track?
2. Jinja2 (recommended) or React for the dashboard track?
3. Local-only for the event day, with AgentCore deployment as a stretch goal — confirmed?
4. Start creating `hackathon/main` and the cherry-picks now, or review this plan with
   the colleague first?
