#!/usr/bin/env python3
"""
Smoke-test a deployed AWS Bedrock AgentCore Runtime by invoking it directly.

Uses the same boto3 invoke_agent_runtime() pattern as
src/graph/workflow_agentcore.py, so a successful call here means the deployed
container, its BedrockAgentCoreApp entrypoint, and IAM/network setup are all
working end to end.

Usage:
    python scripts/invoke_agentcore_runtime.py health_agent
    python scripts/invoke_agentcore_runtime.py diagnosis_agent
    python scripts/invoke_agentcore_runtime.py orchestrator
    python scripts/invoke_agentcore_runtime.py orchestrator --payload '{"action": "list_devices"}'

Runtime IDs are read from agent_endpoints.<TEAM_ID>.json (written by
scripts/deploy_to_agentcore_boto3.py; TEAM_ID from .agentcore.env or --team-id),
falling back to agent_endpoints.json (the original shared deployment) if no
team-specific file exists. Use --runtime-id to override entirely.
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import boto3

DEFAULT_PAYLOADS = {
    "health_agent": {
        "device_id": "COMPRESSOR_UNIT_42",
        "equipment_type": "Air_Compressor",
        "current_reading": {"vibration": 2.1, "pressure": 105.0, "temperature": 68.0},
    },
    "diagnosis_agent": {
        "device_id": "COMPRESSOR_UNIT_42",
        "equipment_type": "Air_Compressor",
        "health_status": "warning",
        "degradation_score": 0.62,
        "anomalies": ["high_vibration"],
        "current_reading": {"vibration": 4.8, "pressure": 90.0, "temperature": 75.0},
    },
    "orchestrator": {
        "device_id": "COMPRESSOR_UNIT_42",
        "equipment_type": "Air_Compressor",
        "current_reading": {"vibration": 2.1, "pressure": 105.0, "temperature": 68.0},
    },
}


def load_runtime_id(agent: str, team_id: str = None) -> str:
    root = Path(__file__).parent.parent
    team_id = team_id or os.getenv('TEAM_ID', '').strip()
    candidates = [root / f"agent_endpoints.{team_id}.json"] if team_id else []
    candidates.append(root / "agent_endpoints.json")
    for endpoints_file in candidates:
        if endpoints_file.exists():
            with open(endpoints_file) as f:
                endpoints = json.load(f)
            return endpoints["details"][agent]["runtime_id"]
    raise FileNotFoundError(f"No agent_endpoints file found (looked for: {[str(c) for c in candidates]})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("agent", choices=["health_agent", "diagnosis_agent", "orchestrator"])
    parser.add_argument("--payload", help="JSON payload to send (defaults to a sample reading for the chosen agent)")
    parser.add_argument("--runtime-id", help="Override the runtime ID looked up from agent_endpoints.<team_id>.json")
    parser.add_argument("--team-id", default=None, help="Team namespace (default: TEAM_ID from .agentcore.env)")
    parser.add_argument("--account-id", default="450410489798")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile", help="AWS SSO profile name (uses default credentials if omitted)")
    args = parser.parse_args()

    runtime_id = args.runtime_id or load_runtime_id(args.agent, team_id=args.team_id)
    payload = json.loads(args.payload) if args.payload else DEFAULT_PAYLOADS[args.agent]
    session_id = f"smoketest-{args.agent}-{uuid.uuid4().hex}"

    session = boto3.Session(profile_name=args.profile) if args.profile else boto3.Session()
    client = session.client("bedrock-agentcore", region_name=args.region)
    agent_runtime_arn = f"arn:aws:bedrock-agentcore:{args.region}:{args.account_id}:runtime/{runtime_id}"

    print(f"Invoking {runtime_id}")
    print(f"  ARN:     {agent_runtime_arn}")
    print(f"  Session: {session_id}")
    print(f"  Payload: {json.dumps(payload)}")

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_runtime_arn,
        runtimeSessionId=session_id,
        payload=json.dumps(payload),
    )
    result = json.loads(response["response"].read().decode("utf-8"))

    print("\nResponse:")
    print(json.dumps(result, indent=2))

    status_code = result.get("statusCode", 200) if isinstance(result, dict) else 200
    sys.exit(0 if status_code < 400 else 1)


if __name__ == "__main__":
    main()
