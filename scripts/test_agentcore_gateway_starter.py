#!/usr/bin/env python3
"""Test AgentCore Gateway without creating new Cognito resources."""
import os
import json
from dotenv import load_dotenv
import boto3
import requests

load_dotenv(".agentcore.env")

REGION = os.getenv("AWS_REGION")
PROFILE = os.getenv("AWS_PROFILE")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID")
APP_CLIENT_SECRET = os.getenv("COGNITO_APP_CLIENT_SECRET")
COGNITO_SCOPE = os.getenv("COGNITO_SCOPE", "openid")
COGNITO_TOKEN_ENDPOINT = os.getenv("COGNITO_TOKEN_ENDPOINT")

with open("gateway_info.json") as f:
    gateway_info = json.load(f)
GATEWAY_ID = gateway_info["gateway_id"]
GATEWAY_URL = gateway_info["gateway_url"]

# Always validate targets via control-plane (no Cognito token needed)
session = boto3.Session(profile_name=PROFILE, region_name=REGION) if PROFILE else boto3.Session(region_name=REGION)
control_client = session.client("bedrock-agentcore-control")
targets = control_client.list_gateway_targets(gatewayIdentifier=GATEWAY_ID)
print("Registered targets:", [t.get("name") for t in targets.get("items", [])])

# Optional data-plane test with existing Cognito app client credentials
if APP_CLIENT_SECRET and APP_CLIENT_ID and COGNITO_TOKEN_ENDPOINT:
    token_resp = requests.post(
        COGNITO_TOKEN_ENDPOINT,
        data={"grant_type": "client_credentials", "scope": COGNITO_SCOPE},
        auth=(APP_CLIENT_ID, APP_CLIENT_SECRET),
        timeout=30,
    )
    token_resp.raise_for_status()
    access_token = token_resp.json().get("access_token")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
    resp = requests.post(
        GATEWAY_URL,
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        timeout=30,
    )
    list_payload = resp.json()
    print("tools/list response:", list_payload)

    def call_tool(call_id: int, tool_name: str, arguments: dict):
        payload = {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        call_resp = requests.post(GATEWAY_URL, headers=headers, json=payload, timeout=30)
        print(f"tools/call [{tool_name}] response:", call_resp.json())

    # Extract tool names returned by gateway (if present)
    # Gateway returns names in format: <target>___<tool> (e.g. "get-spare-parts___get_spare_parts")
    available_tool_names = set()
    try:
        tools = list_payload.get("result", {}).get("tools", [])
        available_tool_names = {t.get("name") for t in tools if isinstance(t, dict) and t.get("name")}
    except Exception:
        available_tool_names = set()

    def resolve_tool_name(candidates: list[str]) -> str:
        """Find the actual gateway tool name matching any of the candidate substrings."""
        for name in available_tool_names:
            for candidate in candidates:
                if candidate in name:
                    return name
        # Fallback to first candidate
        return candidates[0]

    get_spare_parts_name = resolve_tool_name(["get_spare_parts", "get-spare-parts"])
    schedule_maintenance_name = resolve_tool_name(["schedule_maintenance", "schedule-maintenance"])
    create_work_order_name = resolve_tool_name(["create_work_order", "create-work-order"])

    # Sample end-to-end calls (best effort)
    call_tool(2, get_spare_parts_name, {"part_type": "bearing"})
    call_tool(
        3,
        schedule_maintenance_name,
        {
            "device_id": "device-001",
            "maintenance_type": "preventive",
            "scheduled_date": "2026-06-10",
        },
    )
    call_tool(
        4,
        create_work_order_name,
        {
            "work_order_type": "repair",
            "priority": "high",
            "description": "Test work order from gateway validation script",
        },
    )
else:
    print("ℹ️ Skipping data-plane token test. Set COGNITO_APP_CLIENT_SECRET and COGNITO_TOKEN_ENDPOINT to enable it.")
