# Team-Specific Testing Steps (after deploying to AgentCore Runtime)

Quick reference for testing your team's deployment end-to-end, including a
temporary way to point the shared dashboard/API Gateway/Lambda at your
team-specific orchestrator runtime. This is for **solo testing only** — see
the warning in Step 7.

## 1. Run local agents via Docker Compose

```bash
docker compose up --build
```

If Docker itself isn't responding (commands hang or can't reach the daemon),
restart the Docker service: `sudo service docker restart`.

Swagger UIs to check endpoints directly:
- `http://localhost:8000/docs` (orchestrator)
- `http://localhost:8001/docs` (health-agent)
- `http://localhost:8002/docs` (diagnosis-agent)

Quick dashboard check against these local containers (no AWS involved). Run
from the repo root as a module (not `cd src/dashboard && python app.py` —
that breaks on relative imports); on WSL/Ubuntu use `python3`, not `python`:

```bash
ORCHESTRATOR_URL=http://localhost:8000 python3 -m src.dashboard.app
```

Open `http://localhost:8080`.

## 2. Deploy your team-specific agents to AgentCore Runtime

```bash
export AWS_PROFILE=StandardAccess-450410489798
./scripts/deploy_team_agents.sh
```

`TEAM_ID` is read from `.agentcore.env` (currently `team01`). This writes
`agent_endpoints.team01.json` (gitignored, per-team file).

## 3. Get your team's orchestrator runtime ID

```bash
python -c "import json; print(json.load(open('agent_endpoints.team01.json'))['details']['orchestrator']['runtime_id'])"
```

## 4. Edit the Lambda's hardcoded runtime ID (temporary, for this test)

In `functions/lambda_orchestrator_handler.py` (~line 144):

```python
orchestrator_runtime_id = 'orchestrator_runtime-6UF3HDGyvL'
```

Replace with the ID from Step 3.

## 5. Redeploy just that Lambda

```bash
export AWS_PROFILE=StandardAccess-450410489798
python scripts/deploy_lambda_api_gateway_boto3.py
```

This script does `get_function()` → since `orchestrator-handler-450410489798`
already exists, it just calls `update_function_code`/
`update_function_configuration`, and reuses the existing API Gateway
(`agentcore-orchestrator-api`) if the name matches. Same endpoint URL as
before: `https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate`.

## 6. Connect the dashboard to the API Gateway endpoint

This is already `src/dashboard/config.py`'s default — just run it with no
override, from the repo root (use `python3` on WSL/Ubuntu):

```bash
python3 -m src.dashboard.app
```

Open `http://localhost:8080` — it will now be hitting your team's
orchestrator runtime.

## 7. IMPORTANT — revert when done

This Lambda + API Gateway is **shared by every team** in the hackathon (it's
the reason `TEAM_ID` namespacing was only ever applied to the AgentCore
Runtime deploy path, not to this Lambda). While your team's ID is set here,
every other team's dashboard pointed at the same default API Gateway URL
would get your team's results instead of the shared reference deployment.

After testing, change `functions/lambda_orchestrator_handler.py` back to the
original shared ID:

```python
orchestrator_runtime_id = 'orchestrator_runtime-6UF3HDGyvL'
```

and re-run Step 5 (`python scripts/deploy_lambda_api_gateway_boto3.py`) again
to restore the shared endpoint for everyone else.
