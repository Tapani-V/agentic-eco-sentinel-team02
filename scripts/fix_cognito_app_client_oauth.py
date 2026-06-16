#!/usr/bin/env python3
"""
Enable/repair Cognito App Client OAuth settings for AgentCore use.

What this script does:
- Enables OAuth flows on the app client
- Ensures Authorization Code Grant is enabled (flow: code)
- Ensures required scopes exist (default: openid,email)
- Adds callback/logout URLs (if provided)

Usage examples:
  python scripts/fix_cognito_app_client_oauth.py --profile StandardAccess-450410489798 --region us-east-1 \
    --callback-url https://example.com/callback --logout-url https://example.com/logout

  python scripts/fix_cognito_app_client_oauth.py --callback-url http://localhost:3000/callback --logout-url http://localhost:3000/logout
"""

import argparse
import os
import sys
from dotenv import load_dotenv
import boto3


def as_list(v):
    return v if isinstance(v, list) else []


def unique_keep_order(items):
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def main():
    load_dotenv(".agentcore.env")

    parser = argparse.ArgumentParser(description="Fix Cognito App Client OAuth settings")
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE"), help="AWS profile (SSO supported)")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"), help="AWS region")
    parser.add_argument("--user-pool-id", default=os.getenv("COGNITO_USER_POOL_ID"), help="Cognito User Pool ID")
    parser.add_argument("--app-client-id", default=os.getenv("COGNITO_APP_CLIENT_ID"), help="Cognito App Client ID")
    parser.add_argument("--scope", action="append", default=["openid", "email"], help="Required OAuth scope (repeat flag)")
    parser.add_argument("--flow", action="append", default=["code"], help="OAuth flow(s) to ensure (repeat flag)")
    parser.add_argument("--callback-url", action="append", default=[], help="Callback URL(s) to add")
    parser.add_argument("--logout-url", action="append", default=[], help="Logout URL(s) to add")
    args = parser.parse_args()

    if not args.user_pool_id or not args.app_client_id:
        print("❌ Missing COGNITO_USER_POOL_ID or COGNITO_APP_CLIENT_ID.")
        sys.exit(2)

    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile

    try:
        session = boto3.Session(**session_kwargs)
        c = session.client("cognito-idp")

        current = c.describe_user_pool_client(
            UserPoolId=args.user_pool_id,
            ClientId=args.app_client_id,
        )["UserPoolClient"]
    except Exception as e:
        print(f"❌ Failed to read app client: {e}")
        print("Tip: run aws sso login --profile <profile> and retry.")
        sys.exit(1)

    current_scopes = as_list(current.get("AllowedOAuthScopes"))
    current_flows = as_list(current.get("AllowedOAuthFlows"))
    current_callbacks = as_list(current.get("CallbackURLs"))
    current_logouts = as_list(current.get("LogoutURLs"))
    supported_idps = as_list(current.get("SupportedIdentityProviders")) or ["COGNITO"]

    new_scopes = unique_keep_order(current_scopes + as_list(args.scope))
    new_flows = unique_keep_order(current_flows + as_list(args.flow))
    new_callbacks = unique_keep_order(current_callbacks + as_list(args.callback_url))
    new_logouts = unique_keep_order(current_logouts + as_list(args.logout_url))

    # update requires many fields if they were set originally and should be preserved
    update_payload = {
        "UserPoolId": args.user_pool_id,
        "ClientId": args.app_client_id,
        "AllowedOAuthFlowsUserPoolClient": True,
        "AllowedOAuthFlows": new_flows,
        "AllowedOAuthScopes": new_scopes,
        "SupportedIdentityProviders": supported_idps,
    }

    if new_callbacks:
        update_payload["CallbackURLs"] = new_callbacks
    if new_logouts:
        update_payload["LogoutURLs"] = new_logouts

    # preserve common mutable fields when present
    preserve_fields = [
        "AccessTokenValidity",
        "IdTokenValidity",
        "RefreshTokenValidity",
        "TokenValidityUnits",
        "ExplicitAuthFlows",
        "PreventUserExistenceErrors",
        "EnableTokenRevocation",
        "EnablePropagateAdditionalUserContextData",
        "AuthSessionValidity",
        "ReadAttributes",
        "WriteAttributes",
        "DefaultRedirectURI",
    ]
    for f in preserve_fields:
        if f in current and current[f] is not None:
            update_payload[f] = current[f]

    try:
        c.update_user_pool_client(**update_payload)
    except Exception as e:
        print(f"❌ Failed to update app client: {e}")
        sys.exit(1)

    print("✅ Cognito App Client updated.")
    print(f"Flows: {new_flows}")
    print(f"Scopes: {new_scopes}")
    print(f"CallbackURLs: {new_callbacks}")
    print(f"LogoutURLs: {new_logouts}")


if __name__ == "__main__":
    main()
