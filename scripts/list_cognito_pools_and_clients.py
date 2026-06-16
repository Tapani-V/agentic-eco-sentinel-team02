#!/usr/bin/env python3
"""
List Cognito User Pools and App Clients for your AWS account/region.
Supports SSO profiles (set AWS_PROFILE env var or pass --profile argument).
"""
import boto3
import argparse
import os

def list_user_pools(client):
    pools = []
    paginator = client.get_paginator('list_user_pools')
    for page in paginator.paginate(MaxResults=60):
        pools.extend(page['UserPools'])
    return pools

def list_app_clients(client, user_pool_id):
    clients = []
    paginator = client.get_paginator('list_user_pool_clients')
    for page in paginator.paginate(UserPoolId=user_pool_id, MaxResults=60):
        clients.extend(page['UserPoolClients'])
    return clients

def main():
    parser = argparse.ArgumentParser(description="List Cognito User Pools and App Clients.")
    parser.add_argument('--region', required=True, help='AWS region')
    parser.add_argument('--profile', help='AWS profile name (for SSO)')
    args = parser.parse_args()

    if args.profile:
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
    else:
        session = boto3.Session(region_name=args.region)
    client = session.client('cognito-idp')

    print("\nListing Cognito User Pools:")
    pools = list_user_pools(client)
    for pool in pools:
        print(f"- Name: {pool['Name']}, ID: {pool['Id']}")
        clients = list_app_clients(client, pool['Id'])
        for c in clients:
            print(f"    App Client Name: {c['ClientName']}, App Client ID: {c['ClientId']}")

if __name__ == "__main__":
    main()
