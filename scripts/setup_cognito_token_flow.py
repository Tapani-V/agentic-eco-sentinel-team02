#!/usr/bin/env python3
"""
Set up Cognito resources required for agent→gateway token flow (section 6f).

This script:
1. Creates a Cognito resource server with scope 'agentcore/invoke'
2. Creates a Cognito hosted UI domain (for /oauth2/token endpoint)
3. Creates a confidential app client (with secret) for client_credentials flow
4. Updates .agentcore.env with new client ID, secret, token endpoint, and scope

After running this script you must recreate the gateway so its allowedClients
includes the new confidential client ID:
  python scripts/create_agentcore_gateway_starter.py

Then re-register tools:
  python scripts/register_mcp_tools_starter.py

Then test end-to-end:
  python scripts/test_agentcore_gateway_starter.py
"""
import os
import sys
import re
import json
import boto3
from dotenv import load_dotenv

load_dotenv(".agentcore.env")

REGION = os.getenv("AWS_REGION", "us-east-1")
PROFILE = os.getenv("AWS_PROFILE")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
DOMAIN_PREFIX = os.getenv("COGNITO_DOMAIN_PREFIX", "agentic-ai-poc-3-1-auth")
RESOURCE_SERVER_ID = "agentcore"
SCOPE_NAME = "invoke"
FULL_SCOPE = f"{RESOURCE_SERVER_ID}/{SCOPE_NAME}"
CONFIDENTIAL_CLIENT_NAME = "agentic-ai-poc-3-1-confidential-client"
ENV_FILE = ".agentcore.env"


def get_session():
    if PROFILE:
        return boto3.Session(profile_name=PROFILE, region_name=REGION)
    return boto3.Session(region_name=REGION)


def create_resource_server(client):
    """Create resource server with agentcore/invoke scope (idempotent)."""
    print("\n[1/3] Creating resource server...")
    try:
        resp = client.create_resource_server(
            UserPoolId=USER_POOL_ID,
            Identifier=RESOURCE_SERVER_ID,
            Name=RESOURCE_SERVER_ID,
            Scopes=[{"ScopeName": SCOPE_NAME, "ScopeDescription": "Invoke AgentCore Gateway"}],
        )
        print(f"  ✓ Resource server created: {RESOURCE_SERVER_ID}")
        return resp["ResourceServer"]
    except client.exceptions.InvalidParameterException as e:
        if "already exists" in str(e).lower():
            print(f"  ✓ Resource server already exists: {RESOURCE_SERVER_ID}")
            # Fetch and return existing
            resp = client.describe_resource_server(
                UserPoolId=USER_POOL_ID, Identifier=RESOURCE_SERVER_ID
            )
            return resp["ResourceServer"]
        raise


def create_domain(client):
    """Create Cognito hosted UI domain (idempotent)."""
    print("\n[2/3] Creating Cognito domain...")
    try:
        client.create_user_pool_domain(
            UserPoolId=USER_POOL_ID, Domain=DOMAIN_PREFIX
        )
        print(f"  ✓ Domain created: {DOMAIN_PREFIX}")
    except client.exceptions.InvalidParameterException as e:
        if "already exists" in str(e).lower() or "domain" in str(e).lower():
            print(f"  ✓ Domain already exists: {DOMAIN_PREFIX}")
        else:
            raise
    except Exception as e:
        # Some SDK versions raise generic ClientError for duplicate domain
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"  ✓ Domain already exists: {DOMAIN_PREFIX}")
        else:
            raise

    token_endpoint = f"https://{DOMAIN_PREFIX}.auth.{REGION}.amazoncognito.com/oauth2/token"
    print(f"  Token endpoint: {token_endpoint}")
    return token_endpoint


def create_confidential_client(client):
    """Create confidential app client with client_credentials flow."""
    print("\n[3/3] Creating confidential app client...")

    # Check if client already exists by name
    paginator = client.get_paginator("list_user_pool_clients")
    for page in paginator.paginate(UserPoolId=USER_POOL_ID, MaxResults=60):
        for c in page.get("UserPoolClients", []):
            if c.get("ClientName") == CONFIDENTIAL_CLIENT_NAME:
                # Already exists — fetch full details (includes secret)
                existing = client.describe_user_pool_client(
                    UserPoolId=USER_POOL_ID, ClientId=c["ClientId"]
                )["UserPoolClient"]
                client_id = existing["ClientId"]
                client_secret = existing.get("ClientSecret", "")
                if not client_secret:
                    print(f"  ⚠️  Client '{CONFIDENTIAL_CLIENT_NAME}' exists (ID: {client_id}) but has no secret.")
                    print("      Delete it and re-run, or create a new one manually.")
                    return client_id, ""
                print(f"  ✓ Confidential client already exists: {client_id}")
                return client_id, client_secret

    # Create new client
    resp = client.create_user_pool_client(
        UserPoolId=USER_POOL_ID,
        ClientName=CONFIDENTIAL_CLIENT_NAME,
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=[FULL_SCOPE],
        AllowedOAuthFlowsUserPoolClient=True,
        SupportedIdentityProviders=["COGNITO"],
    )
    new_client = resp["UserPoolClient"]
    client_id = new_client["ClientId"]
    client_secret = new_client["ClientSecret"]
    print(f"  ✓ Created confidential client: {client_id}")
    return client_id, client_secret


def update_env_file(client_id: str, client_secret: str, token_endpoint: str):
    """Update .agentcore.env with new values."""
    print(f"\n[✓] Updating {ENV_FILE}...")

    with open(ENV_FILE, "r") as f:
        content = f.read()

    replacements = {
        "COGNITO_APP_CLIENT_ID": client_id,
        "COGNITO_APP_CLIENT_SECRET": client_secret,
        "COGNITO_TOKEN_ENDPOINT": token_endpoint,
        "COGNITO_SCOPE": FULL_SCOPE,
        "COGNITO_DOMAIN_PREFIX": DOMAIN_PREFIX,
    }

    for key, value in replacements.items():
        # Match key=... (existing value or empty)
        pattern = rf"^{re.escape(key)}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, content, flags=re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            # Key doesn't exist yet — append before first blank line at end
            content = content.rstrip("\n") + f"\n{replacement}\n"

    with open(ENV_FILE, "w") as f:
        f.write(content)

    print(f"  ✓ COGNITO_APP_CLIENT_ID={client_id}")
    print(f"  ✓ COGNITO_APP_CLIENT_SECRET={'*' * 8}...{client_secret[-4:] if len(client_secret) > 4 else '****'}")
    print(f"  ✓ COGNITO_TOKEN_ENDPOINT={token_endpoint}")
    print(f"  ✓ COGNITO_SCOPE={FULL_SCOPE}")


def main():
    print("=" * 60)
    print("  Cognito Token Flow Setup (Section 6f)")
    print("=" * 60)

    if not USER_POOL_ID:
        print("❌ COGNITO_USER_POOL_ID not set in .agentcore.env")
        sys.exit(1)

    print(f"\n  User Pool ID:    {USER_POOL_ID}")
    print(f"  Region:          {REGION}")
    print(f"  Domain Prefix:   {DOMAIN_PREFIX}")
    print(f"  Resource Server: {RESOURCE_SERVER_ID}")
    print(f"  Scope:           {FULL_SCOPE}")

    session = get_session()
    cognito_client = session.client("cognito-idp", region_name=REGION)

    # Step 1: Resource server
    create_resource_server(cognito_client)

    # Step 2: Domain
    token_endpoint = create_domain(cognito_client)

    # Step 3: Confidential client
    client_id, client_secret = create_confidential_client(cognito_client)

    if not client_secret:
        print("\n⚠️  Could not retrieve client secret. Check above for details.")
        sys.exit(1)

    # Step 4: Update .agentcore.env
    update_env_file(client_id, client_secret, token_endpoint)

    print("\n" + "=" * 60)
    print("  ✅ Cognito token flow setup complete!")
    print("=" * 60)
    print("""
⚠️  IMPORTANT: Gateway must be recreated so its allowedClients
    includes the new confidential client ID.

    Next steps:
    1. Delete existing gateway targets + gateway (section 6g):
         python scripts/create_agentcore_gateway_starter.py
       (If gateway already exists it will be reused. To force
        recreation, delete first — see section 6g in step-by-step.)

    2. Re-register tools:
         python scripts/register_mcp_tools_starter.py

    3. Run full data-plane test:
         python scripts/test_agentcore_gateway_starter.py
""")


if __name__ == "__main__":
    main()
