#!/usr/bin/env python3
"""
Check Cognito App Client OAuth settings required for AgentCore gateway auth.

Usage:
  python scripts/check_cognito_app_client_oauth.py
  python scripts/check_cognito_app_client_oauth.py --profile StandardAccess-450410489798 --region us-east-1
  python scripts/check_cognito_app_client_oauth.py --expected-callback http://localhost:3000/callback --expected-logout http://localhost:3000/logout
"""

import argparse
import os
import sys
from typing import List

import boto3
from dotenv import load_dotenv


def as_list(value):
    return value if isinstance(value, list) else []


def contains_all(items: List[str], required: List[str]) -> List[str]:
    return [r for r in required if r not in items]


def main():
    load_dotenv(".agentcore.env")

    parser = argparse.ArgumentParser(description="Validate Cognito App Client OAuth configuration.")
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE"), help="AWS profile (SSO profile supported)")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"), help="AWS region")
    parser.add_argument("--user-pool-id", default=os.getenv("COGNITO_USER_POOL_ID"), help="Cognito User Pool ID")
    parser.add_argument("--app-client-id", default=os.getenv("COGNITO_APP_CLIENT_ID"), help="Cognito App Client ID")
    parser.add_argument("--expected-callback", action="append", default=[], help="Expected callback URL (repeat option for multiple)")
    parser.add_argument("--expected-logout", action="append", default=[], help="Expected logout URL (repeat option for multiple)")
    parser.add_argument("--required-scope", action="append", default=["openid", "email"], help="Required OAuth scope (repeat option for multiple)")
    args = parser.parse_args()

    if not args.user_pool_id or not args.app_client_id:
        print("❌ Missing COGNITO_USER_POOL_ID or COGNITO_APP_CLIENT_ID (pass flags or set in .agentcore.env).")
        sys.exit(2)

    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile

    try:
        session = boto3.Session(**session_kwargs)
        client = session.client("cognito-idp")
        resp = client.describe_user_pool_client(
            UserPoolId=args.user_pool_id,
            ClientId=args.app_client_id,
        )
    except Exception as e:
        print(f"❌ Failed to read Cognito App Client: {e}")
        print("Tip: if using SSO, run 'aws sso login --profile <your-profile>' first.")
        sys.exit(1)

    c = resp.get("UserPoolClient", {})

    allowed_flows = as_list(c.get("AllowedOAuthFlows"))
    allowed_scopes = as_list(c.get("AllowedOAuthScopes"))
    callback_urls = as_list(c.get("CallbackURLs"))
    logout_urls = as_list(c.get("LogoutURLs"))
    oauth_enabled = bool(c.get("AllowedOAuthFlowsUserPoolClient", False))

    print("\n=== Cognito App Client OAuth Check ===")
    print(f"User Pool ID: {args.user_pool_id}")
    print(f"App Client ID: {args.app_client_id}")
    print(f"OAuth enabled (AllowedOAuthFlowsUserPoolClient): {oauth_enabled}")
    print(f"Allowed flows: {allowed_flows}")
    print(f"Allowed scopes: {allowed_scopes}")
    print(f"Callback URLs: {callback_urls}")
    print(f"Logout URLs: {logout_urls}")

    failures = []

    if not oauth_enabled:
        failures.append("OAuth flows are not enabled for this app client.")

    if "code" not in allowed_flows:
        failures.append("Authorization code grant is not enabled (missing flow: code).")

    missing_scopes = contains_all(allowed_scopes, args.required_scope)
    if missing_scopes:
        failures.append(f"Missing required scopes: {missing_scopes}")

    if args.expected_callback:
        missing_callbacks = contains_all(callback_urls, args.expected_callback)
        if missing_callbacks:
            failures.append(f"Missing expected callback URL(s): {missing_callbacks}")

    if args.expected_logout:
        missing_logouts = contains_all(logout_urls, args.expected_logout)
        if missing_logouts:
            failures.append(f"Missing expected logout URL(s): {missing_logouts}")

    print("\n=== Result ===")
    if failures:
        print("❌ Configuration NOT ready:")
        for f in failures:
            print(f" - {f}")
        sys.exit(1)

    print("✅ Configuration looks good for AgentCore OAuth usage.")


if __name__ == "__main__":
    main()
