#!/usr/bin/env python3
"""
Test AgentCore Gateway with:
- control-plane target listing
- Cognito client-credentials token retrieval
- MCP tools/list
- MCP tools/call

Improvements:
- Shared requests.Session()
- Explicit certifi CA bundle
- Retry support
- Better logging and error handling
- Optional disabling of proxy env vars
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional, Set

import boto3
import certifi
import requests
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException, SSLError
from urllib3.util.retry import Retry


# -------------------------------------------------------------------
# Config helpers
# -------------------------------------------------------------------

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def safe_json_loads(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return value


def pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def print_step(title: str) -> None:
    print(f"\n{'=' * 80}")
    print(title)
    print(f"{'=' * 80}")


# -------------------------------------------------------------------
# Load config
# -------------------------------------------------------------------

load_dotenv(".agentcore.env")

REGION = os.getenv("AWS_REGION")
PROFILE = os.getenv("AWS_PROFILE")

USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")  # kept for reference
APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID")
APP_CLIENT_SECRET = os.getenv("COGNITO_APP_CLIENT_SECRET")
COGNITO_SCOPE = os.getenv("COGNITO_SCOPE", "openid")
COGNITO_TOKEN_ENDPOINT = os.getenv("COGNITO_TOKEN_ENDPOINT")

HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
DISABLE_PROXY_ENV = env_bool("DISABLE_PROXY_ENV", False)

GATEWAY_INFO_FILE = os.getenv("GATEWAY_INFO_FILE", "gateway_info.json")

if not REGION:
    print("❌ Missing AWS_REGION in .agentcore.env")
    sys.exit(1)

if not os.path.exists(GATEWAY_INFO_FILE):
    print(f"❌ Missing gateway info file: {GATEWAY_INFO_FILE}")
    sys.exit(1)

with open(GATEWAY_INFO_FILE, "r", encoding="utf-8") as f:
    gateway_info = json.load(f)

GATEWAY_ID = gateway_info["gateway_id"]
GATEWAY_URL = gateway_info["gateway_url"]

# Optional safety: if gateway_url does not end with /mcp, append it
if not GATEWAY_URL.rstrip("/").endswith("/mcp"):
    GATEWAY_URL = GATEWAY_URL.rstrip("/") + "/mcp"


# -------------------------------------------------------------------
# Session helpers
# -------------------------------------------------------------------

def build_http_session() -> requests.Session:
    session_http = requests.Session()

    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    session_http.mount("https://", adapter)
    session_http.mount("http://", adapter)

    if DISABLE_PROXY_ENV:
        session_http.trust_env = False

    return session_http


def post_json(
    session_http: requests.Session,
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: int = HTTP_TIMEOUT,
) -> Dict[str, Any]:
    resp = session_http.post(
        url,
        headers=headers,
        json=payload,
        timeout=timeout,
        verify=certifi.where(),
    )
    resp.raise_for_status()
    return resp.json()


# -------------------------------------------------------------------
# OAuth token
# -------------------------------------------------------------------

def get_access_token(session_http: requests.Session) -> str:
    if not (APP_CLIENT_ID and APP_CLIENT_SECRET and COGNITO_TOKEN_ENDPOINT):
        raise RuntimeError(
            "Missing one or more required Cognito settings: "
            "COGNITO_APP_CLIENT_ID, COGNITO_APP_CLIENT_SECRET, COGNITO_TOKEN_ENDPOINT"
        )

    print_step("Step 2: Fetch Cognito access token")

    token_resp = session_http.post(
        COGNITO_TOKEN_ENDPOINT,
        data={
            "grant_type": "client_credentials",
            "scope": COGNITO_SCOPE,
        },
        auth=(APP_CLIENT_ID, APP_CLIENT_SECRET),
        timeout=HTTP_TIMEOUT,
        verify=certifi.where(),
    )
    token_resp.raise_for_status()

    token_json = token_resp.json()
    access_token = token_json.get("access_token")

    if not access_token:
        raise RuntimeError(f"No access_token in token response: {pretty(token_json)}")

    print("✅ Access token acquired successfully")
    return access_token


# -------------------------------------------------------------------
# Gateway RPC helpers
# -------------------------------------------------------------------

def gateway_rpc(
    session_http: requests.Session,
    access_token: str,
    rpc_id: int,
    method: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    payload = {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": method,
        "params": params,
    }

    return post_json(
        session_http=session_http,
        url=GATEWAY_URL,
        payload=payload,
        headers=headers,
        timeout=HTTP_TIMEOUT,
    )


def resolve_tool_name(available_tool_names: Set[str], candidates: List[str]) -> str:
    """
    Find the actual gateway tool name matching one of the candidate substrings.
    Example available name:
      get-spare-parts___get_spare_parts
    """
    for name in available_tool_names:
        for candidate in candidates:
            if candidate in name:
                return name
    return candidates[0]


def extract_tool_names(list_payload: Dict[str, Any]) -> Set[str]:
    tools = list_payload.get("result", {}).get("tools", [])
    return {
        t.get("name")
        for t in tools
        if isinstance(t, dict) and t.get("name")
    }


def try_decode_tool_content(call_result: Dict[str, Any]) -> Any:
    """
    AgentCore tool responses often have the form:
    {
      "result": {
        "isError": false,
        "content": [
          { "type": "text", "text": "{\"statusCode\":200, ... }" }
        ]
      }
    }

    This helper tries to decode nested JSON for easier reading.
    """
    try:
        result = call_result.get("result", {})
        content = result.get("content", [])
        if not content:
            return call_result

        first = content[0]
        if not isinstance(first, dict):
            return call_result

        text_value = first.get("text")
        if not isinstance(text_value, str):
            return call_result

        decoded_outer = safe_json_loads(text_value)
        if not isinstance(decoded_outer, dict):
            return decoded_outer

        if "body" in decoded_outer and isinstance(decoded_outer["body"], str):
            decoded_outer["body"] = safe_json_loads(decoded_outer["body"])

        return decoded_outer
    except Exception:
        return call_result


def call_tool(
    session_http: requests.Session,
    access_token: str,
    call_id: int,
    tool_name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    print_step(f"Step 4.{call_id}: tools/call -> {tool_name}")
    print("Arguments:")
    print(pretty(arguments))

    call_result = gateway_rpc(
        session_http=session_http,
        access_token=access_token,
        rpc_id=call_id,
        method="tools/call",
        params={
            "name": tool_name,
            "arguments": arguments,
        },
    )

    print("Raw response:")
    print(pretty(call_result))

    decoded = try_decode_tool_content(call_result)
    if decoded != call_result:
        print("\nDecoded content:")
        print(pretty(decoded))

    return call_result


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main() -> int:
    try:
        print_step("Step 0: Runtime info")
        print(f"AWS Region            : {REGION}")
        print(f"AWS Profile           : {PROFILE or '(default profile)'}")
        print(f"Gateway ID            : {GATEWAY_ID}")
        print(f"Gateway URL           : {GATEWAY_URL}")
        print(f"HTTP timeout          : {HTTP_TIMEOUT}s")
        print(f"Disable proxy env     : {DISABLE_PROXY_ENV}")
        print(f"certifi CA bundle     : {certifi.where()}")

        # Step 1: Control plane
        print_step("Step 1: List registered gateway targets (control plane)")
        aws_session = (
            boto3.Session(profile_name=PROFILE, region_name=REGION)
            if PROFILE
            else boto3.Session(region_name=REGION)
        )
        control_client = aws_session.client("bedrock-agentcore-control")

        targets = control_client.list_gateway_targets(gatewayIdentifier=GATEWAY_ID)
        target_names = [t.get("name") for t in targets.get("items", [])]
        print("✅ Registered targets:", target_names)

        # Step 2: HTTP session + token
        session_http = build_http_session()
        access_token = get_access_token(session_http)

        # Step 3: tools/list
        print_step("Step 3: tools/list")
        list_payload = gateway_rpc(
            session_http=session_http,
            access_token=access_token,
            rpc_id=1,
            method="tools/list",
            params={},
        )

        print("tools/list response:")
        print(pretty(list_payload))

        available_tool_names = extract_tool_names(list_payload)
        print("\nResolved available tool names:")
        for name in sorted(available_tool_names):
            print(f" - {name}")

        get_spare_parts_name = resolve_tool_name(
            available_tool_names,
            ["get_spare_parts", "get-spare-parts"],
        )
        schedule_maintenance_name = resolve_tool_name(
            available_tool_names,
            ["schedule_maintenance", "schedule-maintenance"],
        )
        create_work_order_name = resolve_tool_name(
            available_tool_names,
            ["create_work_order", "create-work-order"],
        )

        print("\nTool resolution:")
        print(f"get_spare_parts      -> {get_spare_parts_name}")
        print(f"schedule_maintenance -> {schedule_maintenance_name}")
        print(f"create_work_order    -> {create_work_order_name}")

        # Step 4: tools/call
        call_tool(
            session_http=session_http,
            access_token=access_token,
            call_id=2,
            tool_name=get_spare_parts_name,
            arguments={"part_type": "bearing"},
        )

        call_tool(
            session_http=session_http,
            access_token=access_token,
            call_id=3,
            tool_name=schedule_maintenance_name,
            arguments={
                "device_id": "device-001",
                "maintenance_type": "preventive",
                "scheduled_date": "2026-06-10",
            },
        )

        call_tool(
            session_http=session_http,
            access_token=access_token,
            call_id=4,
            tool_name=create_work_order_name,
            arguments={
                "work_order_type": "repair",
                "priority": "high",
                "description": "Test work order from gateway validation script",
            },
        )

        print_step("Done")
        print("✅ All control-plane and data-plane checks completed successfully")
        return 0

    except SSLError as e:
        print("\n❌ SSL error while calling gateway or token endpoint")
        print(str(e))
        print("\nTroubleshooting tips:")
        print("- Check VPN / proxy / corporate network interception")
        print("- Try setting DISABLE_PROXY_ENV=true in .agentcore.env")
        print("- Make sure certifi is installed and importable")
        return 2

    except RequestException as e:
        print("\n❌ HTTP request error")
        print(str(e))
        return 3

    except (ClientError, BotoCoreError) as e:
        print("\n❌ AWS SDK / control-plane error")
        print(str(e))
        return 4

    except Exception as e:
        print("\n❌ Unexpected error")
        print(str(e))
        return 5


if __name__ == "__main__":
    sys.exit(main())