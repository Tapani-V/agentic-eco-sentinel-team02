#!/usr/bin/env python3
"""
Create AgentCore Gateway using the starter kit, set up Cognito OAuth, and output gateway info.
"""
import os
import json
from dotenv import load_dotenv
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
import boto3

load_dotenv(".agentcore.env")

REGION = os.getenv("AWS_REGION")
PROFILE = os.getenv("AWS_PROFILE")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID")
PERMISSION_BOUNDARY = os.getenv("PERMISSION_BOUNDARY")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")


def build_authorizer_config_from_existing_cognito() -> dict:
    if not USER_POOL_ID or not APP_CLIENT_ID:
        raise ValueError("COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID must be set in .agentcore.env")

    discovery_url = (
        f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/openid-configuration"
    )
    return {
        "customJWTAuthorizer": {
            "allowedClients": [APP_CLIENT_ID],
            "discoveryUrl": discovery_url,
        }
    }

# Use boto3 session with profile if set
session = boto3.Session(profile_name=PROFILE, region_name=REGION) if PROFILE else boto3.Session(region_name=REGION)
iam_client = session.client("iam")
sts_client = session.client("sts")


def resolve_permission_boundary_arn(boundary_value: str):
    """Accept either full ARN or policy name and return a valid boundary ARN."""
    if not boundary_value:
        return None

    candidate = boundary_value.strip()
    if candidate.startswith("arn:"):
        return candidate

    account_id = AWS_ACCOUNT_ID
    if not account_id:
        account_id = sts_client.get_caller_identity()["Account"]

    # Common case: boundary provided as policy name only
    guessed_arn = f"arn:aws:iam::{account_id}:policy/{candidate}"
    try:
        iam_client.get_policy(PolicyArn=guessed_arn)
        return guessed_arn
    except Exception:
        pass

    # Fallback: discover local customer-managed policies by name
    paginator = iam_client.get_paginator("list_policies")
    for page in paginator.paginate(Scope="Local"):
        for policy in page.get("Policies", []):
            if policy.get("PolicyName") == candidate:
                return policy.get("Arn")

    raise ValueError(
        f"Could not resolve permission boundary '{candidate}' to a valid IAM policy ARN. "
        f"Set PERMISSION_BOUNDARY in .agentcore.env to a full ARN."
    )

# Create Gateway execution role (if not exists)
def create_gateway_execution_role():
    role_name = "AgentCoreGatewayExecutionRole"
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }
    try:
        boundary_arn = resolve_permission_boundary_arn(PERMISSION_BOUNDARY)
        create_role_payload = {
            "RoleName": role_name,
            "AssumeRolePolicyDocument": json.dumps(trust_policy),
            "Description": "Execution role for AgentCore Gateway"
        }
        if boundary_arn:
            create_role_payload["PermissionsBoundary"] = boundary_arn

        role = iam_client.create_role(
            **create_role_payload
        )
        print(f"✓ Created Gateway execution role: {role_name}")
    except iam_client.exceptions.EntityAlreadyExistsException:
        role = iam_client.get_role(RoleName=role_name)
        print(f"✓ Gateway execution role already exists: {role_name}")
    return role["Role"]["Arn"]

def main():
    print("--- AgentCore Gateway Creation ---")
    if PROFILE:
        os.environ["AWS_PROFILE"] = PROFILE
    gateway_client = GatewayClient(region_name=REGION)
    gateway_client.logger.info("Using Cognito User Pool: %s, App Client: %s", USER_POOL_ID, APP_CLIENT_ID)
    # Build CUSTOM_JWT authorizer config from existing Cognito resources
    authorizer_config = build_authorizer_config_from_existing_cognito()
    # Create execution role
    gateway_role_arn = create_gateway_execution_role()

    GATEWAY_NAME = "AgenticAI-PoC-3-1-MCP-Gateway"

    # Try to create the gateway; if it already exists, fetch it instead
    try:
        gateway = gateway_client.create_mcp_gateway(
            name=GATEWAY_NAME,
            authorizer_config=authorizer_config,
            role_arn=gateway_role_arn
        )
        print(f"✓ Gateway created: {GATEWAY_NAME}")
    except Exception as e:
        if "already exists" in str(e).lower() or "conflict" in str(e).lower() or "validation" in str(e).lower():
            print(f"ℹ️ Gateway '{GATEWAY_NAME}' already exists. Fetching existing gateway info...")
            result = gateway_client.get_gateway(name=GATEWAY_NAME)
            if result.get("status") == "success":
                gateway = result["gateway"]
            else:
                raise RuntimeError(f"Could not fetch existing gateway: {result.get('message')}")
        else:
            raise

    gateway_id = gateway.get('gatewayId') or gateway.get('gatewayArn', '').split('/')[-1]
    gateway_url = gateway.get('gatewayUrl', '')
    # Prefer the role from the fetched gateway; fall back to the one we just created/confirmed
    role_arn = gateway.get('roleArn') or gateway_role_arn

    print(f"Gateway ID: {gateway_id}")
    print(f"Gateway URL: {gateway_url}")
    print(f"Role ARN:    {role_arn}")

    # Save gateway info for downstream scripts
    with open("gateway_info.json", "w") as f:
        import json
        json.dump({
            "gateway_id": gateway_id,
            "gateway_url": gateway_url,
            "role_arn": role_arn
        }, f, indent=2)
    print("✓ Gateway info saved to gateway_info.json")

if __name__ == "__main__":
    main()
