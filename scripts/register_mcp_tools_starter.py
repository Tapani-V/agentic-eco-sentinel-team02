#!/usr/bin/env python3
"""
Register MCP tools (Lambda/App Runner) with AgentCore Gateway using the starter kit.
"""
import os
import json
import argparse
from dotenv import load_dotenv
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

_arg_parser = argparse.ArgumentParser(add_help=False)
_arg_parser.add_argument(
    "--env-file",
    default=".agentcore.env",
    help="Path to the env file to load (default: .agentcore.env). Use this to point at a "
         "team-specific file (e.g. .agentcore.env.team01) without touching the original."
)
_args, _ = _arg_parser.parse_known_args()

load_dotenv(_args.env_file)

REGION = os.getenv("AWS_REGION")
PROFILE = os.getenv("AWS_PROFILE")
TEAM_ID = os.getenv("TEAM_ID")
GET_SPARE_PARTS_LAMBDA_ARN = os.getenv("GET_SPARE_PARTS_LAMBDA_ARN")
SCHEDULE_MAINTENANCE_LAMBDA_ARN = os.getenv("SCHEDULE_MAINTENANCE_LAMBDA_ARN")
CREATE_WORK_ORDER_URL = os.getenv("CREATE_WORK_ORDER_URL")

if PROFILE:
    os.environ["AWS_PROFILE"] = PROFILE

# Team-specific gateway_info file keeps each team's Gateway details isolated
# (falls back to the shared filename when TEAM_ID isn't set).
GATEWAY_INFO_FILE = f"gateway_info.{TEAM_ID}.json" if TEAM_ID else "gateway_info.json"
with open(GATEWAY_INFO_FILE) as f:
    gateway_info = json.load(f)
GATEWAY_ID = gateway_info["gateway_id"]
GATEWAY_ROLE_ARN = gateway_info.get("role_arn", "")

client = GatewayClient(region_name=REGION)

# Fetch the full gateway dict (needed by create_mcp_gateway_target)
gateway = client.get_gateway(gateway_identifier=GATEWAY_ID)
# get_gateway returns a dict; ensure it has gatewayId and roleArn
if "gatewayId" not in gateway:
    gateway["gatewayId"] = GATEWAY_ID
if "roleArn" not in gateway and GATEWAY_ROLE_ARN:
    gateway["roleArn"] = GATEWAY_ROLE_ARN

def register_lambda_tool(name, lambda_arn, input_schema, output_schema):
    target_payload = {
        "lambdaArn": lambda_arn,
        "toolSchema": {
            "inlinePayload": [{
                "name": name,
                "description": name,
                "inputSchema": input_schema,
                "outputSchema": output_schema
            }]
        }
    }
    # Target name must match ([0-9a-zA-Z][-]?){1,100} — no underscores allowed
    target_name = name.replace("_", "-")
    client.create_mcp_gateway_target(
        gateway=gateway,
        name=target_name,
        target_type="lambda",
        target_payload=target_payload
    )
    print(f"✓ Registered Lambda tool: {name}")

def register_http_tool(name, url, input_schema, output_schema):
    # App Runner is a public endpoint — bypass the toolkit (which forces credentials)
    # and call the boto3 bedrock-agentcore client directly
    import boto3
    boto_session = boto3.Session(profile_name=PROFILE, region_name=REGION) if PROFILE else boto3.Session(region_name=REGION)
    boto_client = boto_session.client("bedrock-agentcore-control")

    openapi_spec = {
        "openapi": "3.0.0",
        "info": {"title": name, "version": "1.0"},
        "servers": [{"url": url.rsplit("/", 1)[0]}],  # base URL without path
        "paths": {
            "/" + url.rsplit("/", 1)[-1]: {
                "post": {
                    "operationId": name,
                    "description": name,
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": input_schema}}
                    },
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {"application/json": {"schema": output_schema}}
                        }
                    }
                }
            }
        }
    }
    target_name = name.replace("_", "-")
    boto_client.create_gateway_target(
        gatewayIdentifier=GATEWAY_ID,
        name=target_name,
        targetConfiguration={
            "mcp": {
                "openApiSchema": {
                    "inlinePayload": json.dumps(openapi_spec)
                }
            }
        },
        credentialProviderConfigurations=[{
            "credentialProviderType": "GATEWAY_IAM_ROLE",
            "credentialProvider": {
                "iamCredentialProvider": {
                    "service": "apprunner",
                    "region": REGION
                }
            }
        }]
    )
    print(f"✓ Registered HTTP tool: {name}")

def safe_register(fn, *args):
    try:
        fn(*args)
    except Exception as e:
        if "already exists" in str(e).lower() or "conflict" in str(e).lower():
            print(f"ℹ️ Target already registered, skipping: {args[0]}")
        else:
            raise

def main():
    get_spare_parts_input = {
        "type": "object",
        "properties": {
            "part_type": {"type": "string", "description": "Type of spare part"},
            "category": {"type": "string", "description": "Optional category filter"}
        },
        "required": ["part_type"]
    }
    get_spare_parts_output = {
        "type": "object",
        "properties": {
            "parts": {"type": "array"},
            "count": {"type": "integer"}
        }
    }
    schedule_maintenance_input = {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "maintenance_type": {"type": "string"},
            "scheduled_date": {"type": "string"}
        },
        "required": ["device_id", "maintenance_type", "scheduled_date"]
    }
    schedule_maintenance_output = {
        "type": "object",
        "properties": {
            "maintenance_id": {"type": "string"},
            "status": {"type": "string"}
        }
    }
    create_work_order_input = {
        "type": "object",
        "properties": {
            "work_order_type": {"type": "string"},
            "priority": {"type": "string"},
            "description": {"type": "string"}
        },
        "required": ["work_order_type", "priority", "description"]
    }
    create_work_order_output = {
        "type": "object",
        "properties": {
            "work_order_id": {"type": "string"},
            "status": {"type": "string"},
            "created_at": {"type": "string"}
        }
    }

    safe_register(register_lambda_tool, "get_spare_parts", GET_SPARE_PARTS_LAMBDA_ARN, get_spare_parts_input, get_spare_parts_output)
    safe_register(register_lambda_tool, "schedule_maintenance", SCHEDULE_MAINTENANCE_LAMBDA_ARN, schedule_maintenance_input, schedule_maintenance_output)
    safe_register(register_http_tool, "create_work_order", CREATE_WORK_ORDER_URL, create_work_order_input, create_work_order_output)
    print("✓ All MCP tools registered.")

if __name__ == "__main__":
    main()
