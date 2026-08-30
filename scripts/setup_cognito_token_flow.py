#!/usr/bin/env python3
"""
Set up Cognito resources required for agent→gateway token flow (section 6f).

This script:
1. Creates a Cognito resource server with scope 'agentcore/invoke'
2. Creates a Cognito hosted UI domain (for /oauth2/token endpoint)
3. Creates a confidential app client (with secret) for client_credentials flow
4. Updates the target env file with new client ID, secret, token endpoint, and scope

Region/user-pool/domain/client-name/env-file are all overridable via CLI flags
so the same script can be pointed at any region/team's pool (e.g. Frankfurt)
without touching another region/team's env file. With no flags, behavior is
unchanged from the original North Virginia (.agentcore.env) setup.

After running this script you must update the gateway so its allowedClients
includes the new confidential client ID:
  python scripts/create_agentcore_gateway_starter.py

Then re-register tools:
  python scripts/register_mcp_tools_starter.py

Then test end-to-end:
  python scripts/test_agentcore_gateway_starter.py

Usage:
  python scripts/setup_cognito_token_flow.py \
      [--region REGION] [--user-pool-id ID] [--domain-prefix PREFIX] \
      [--client-name NAME] [--profile PROFILE] [--env-file PATH]
"""
import os
import sys
import re
import argparse
import boto3
from dotenv import load_dotenv

RESOURCE_SERVER_ID = "agentcore"
SCOPE_NAME = "invoke"
FULL_SCOPE = f"{RESOURCE_SERVER_ID}/{SCOPE_NAME}"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", default=".agentcore.env", help="Env file to load defaults from and write results to (default: .agentcore.env)")
    parser.add_argument("--region", default=None, help="AWS region (default: AWS_REGION from --env-file, else us-east-1)")
    parser.add_argument("--profile", default=None, help="AWS profile (default: AWS_PROFILE from --env-file)")
    parser.add_argument("--user-pool-id", default=None, help="Cognito user pool ID (default: COGNITO_USER_POOL_ID from --env-file)")
    parser.add_argument("--domain-prefix", default=None, help="Hosted UI domain prefix, must be globally unique (default: COGNITO_DOMAIN_PREFIX from --env-file)")
    parser.add_argument("--client-name", default=None, help="Confidential app client name (default: agentic-ai-poc-3-1-confidential-client)")
    return parser.parse_args()


def get_session(profile, region):
    if profile:
        return boto3.Session(profile_name=profile, region_name=region)
    return boto3.Session(region_name=region)


def create_resource_server(client, user_pool_id):
    """Create resource server with agentcore/invoke scope (idempotent)."""
    print("\n[1/3] Creating resource server...")
    try:
        resp = client.create_resource_server(
            UserPoolId=user_pool_id,
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
                UserPoolId=user_pool_id, Identifier=RESOURCE_SERVER_ID
            )
            return resp["ResourceServer"]
        raise


def create_domain(client, user_pool_id, domain_prefix, region):
    """Create Cognito hosted UI domain (idempotent)."""
    print("\n[2/3] Creating Cognito domain...")
    try:
        client.create_user_pool_domain(
            UserPoolId=user_pool_id, Domain=domain_prefix
        )
        print(f"  ✓ Domain created: {domain_prefix}")
    except client.exceptions.InvalidParameterException as e:
        if "already exists" in str(e).lower() or "domain" in str(e).lower():
            print(f"  ✓ Domain already exists: {domain_prefix}")
        else:
            raise
    except Exception as e:
        # Some SDK versions raise generic ClientError for duplicate domain
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"  ✓ Domain already exists: {domain_prefix}")
        else:
            raise

    token_endpoint = f"https://{domain_prefix}.auth.{region}.amazoncognito.com/oauth2/token"
    print(f"  Token endpoint: {token_endpoint}")
    return token_endpoint


def create_confidential_client(client, user_pool_id, client_name):
    """Create confidential app client with client_credentials flow."""
    print("\n[3/3] Creating confidential app client...")

    # Check if client already exists by name
    paginator = client.get_paginator("list_user_pool_clients")
    for page in paginator.paginate(UserPoolId=user_pool_id, MaxResults=60):
        for c in page.get("UserPoolClients", []):
            if c.get("ClientName") == client_name:
                # Already exists — fetch full details (includes secret)
                existing = client.describe_user_pool_client(
                    UserPoolId=user_pool_id, ClientId=c["ClientId"]
                )["UserPoolClient"]
                client_id = existing["ClientId"]
                client_secret = existing.get("ClientSecret", "")
                if not client_secret:
                    print(f"  ⚠️  Client '{client_name}' exists (ID: {client_id}) but has no secret.")
                    print("      Delete it and re-run, or create a new one manually.")
                    return client_id, ""
                print(f"  ✓ Confidential client already exists: {client_id}")
                return client_id, client_secret

    # Create new client
    resp = client.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName=client_name,
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


def merge_env_values(env_file: str, values: dict) -> None:
    """Merge key=value pairs into env_file via targeted line-replace (creates
    the file if it doesn't exist, leaves all other keys/lines untouched)."""
    content = ""
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            content = f.read()

    for key, value in values.items():
        # Match key=... (existing value or empty)
        pattern = rf"^{re.escape(key)}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, content, flags=re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            # Key doesn't exist yet — append before first blank line at end
            content = content.rstrip("\n") + f"\n{replacement}\n"

    with open(env_file, "w") as f:
        f.write(content)


def update_env_file(env_file, client_id: str, client_secret: str, token_endpoint: str, domain_prefix: str):
    """Update the target env file with new values (creates the file if it doesn't exist)."""
    print(f"\n[✓] Updating {env_file}...")

    merge_env_values(env_file, {
        "COGNITO_APP_CLIENT_ID": client_id,
        "COGNITO_APP_CLIENT_SECRET": client_secret,
        "COGNITO_TOKEN_ENDPOINT": token_endpoint,
        "COGNITO_SCOPE": FULL_SCOPE,
        "COGNITO_DOMAIN_PREFIX": domain_prefix,
    })

    print(f"  ✓ COGNITO_APP_CLIENT_ID={client_id}")
    print(f"  ✓ COGNITO_APP_CLIENT_SECRET={'*' * 8}...{client_secret[-4:] if len(client_secret) > 4 else '****'}")
    print(f"  ✓ COGNITO_TOKEN_ENDPOINT={token_endpoint}")
    print(f"  ✓ COGNITO_SCOPE={FULL_SCOPE}")


def main():
    args = parse_args()
    load_dotenv(args.env_file)

    region = args.region or os.getenv("AWS_REGION", "us-east-1")
    profile = args.profile or os.getenv("AWS_PROFILE")
    user_pool_id = args.user_pool_id or os.getenv("COGNITO_USER_POOL_ID")
    domain_prefix = args.domain_prefix or os.getenv("COGNITO_DOMAIN_PREFIX", "agentic-ai-poc-3-1-auth")
    client_name = args.client_name or os.getenv("COGNITO_CLIENT_NAME", "agentic-ai-poc-3-1-confidential-client")

    print("=" * 60)
    print("  Cognito Token Flow Setup (Section 6f)")
    print("=" * 60)

    if not user_pool_id:
        print(f"❌ COGNITO_USER_POOL_ID not set in {args.env_file} and no --user-pool-id given")
        sys.exit(1)

    print(f"\n  Env File:        {args.env_file}")
    print(f"  User Pool ID:    {user_pool_id}")
    print(f"  Region:          {region}")
    print(f"  Domain Prefix:   {domain_prefix}")
    print(f"  Client Name:     {client_name}")
    print(f"  Resource Server: {RESOURCE_SERVER_ID}")
    print(f"  Scope:           {FULL_SCOPE}")

    session = get_session(profile, region)
    cognito_client = session.client("cognito-idp", region_name=region)

    # Step 1: Resource server
    create_resource_server(cognito_client, user_pool_id)

    # Step 2: Domain
    token_endpoint = create_domain(cognito_client, user_pool_id, domain_prefix, region)

    # Step 3: Confidential client
    client_id, client_secret = create_confidential_client(cognito_client, user_pool_id, client_name)

    if not client_secret:
        print("\n⚠️  Could not retrieve client secret. Check above for details.")
        sys.exit(1)

    # Step 4: Update the target env file
    update_env_file(args.env_file, client_id, client_secret, token_endpoint, domain_prefix)

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
