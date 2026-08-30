# Dashboard Follow-Up Issues

## 1. Separate Read-Only Dashboard Analysis From Action Execution

The Frankfurt dashboard's live device analysis currently invokes the complete
HealthAgent -> DiagnosisAgent workflow. For warning or critical devices,
DiagnosisAgent can call MCP tools that create maintenance records or work
orders. The five-minute Lambda analysis cache reduces repeated calls, but a
cold cache or expired cache can still repeat those actions during dashboard
polling.

Follow-up direction: add a read-only health-analysis path for dashboard
refreshes, and reserve `schedule-maintenance` and `create-work-order` for an
explicit user or agent action.

## 2. Per-Team Synthetic Sensor Data

`team01-synthetic-data` already exists in `eu-central-1` and contains the
17 device JSON files under `devices/`, but team01 runtimes currently use the
shared `agentic-ai-poc-synthetic-data` bucket.

To make synthetic data fully isolated per team:
- Set `SYNTHETIC_DATA_BUCKET=team01-synthetic-data` in the team env file.
- Change `scripts/deploy_to_agentcore_boto3.py` to read
  `SYNTHETIC_DATA_BUCKET` and `SYNTHETIC_DATA_PREFIX` from its selected env
  file instead of hardcoding the shared bucket.
- Extend `AgentCoreExecutionRole`'s `SyntheticDataS3ReadAccess` policy with
  `s3:ListBucket` on `team01-synthetic-data` and `s3:GetObject` on
  `team01-synthetic-data/*`.
- Redeploy the team01 AgentCore runtimes.
