#!/usr/bin/env python3
"""
Deploys MCP Lambda functions to AWS (fully isolated per-team model):
- Creates/updates a team-specific IAM role with correct permissions and permission boundary
- Packages Lambda code (and dependencies if needed)
- Deploys/updates team-specific Lambda functions ("<team_id>-get-spare-parts",
  "<team_id>-schedule-maintenance")
- Sets environment variables
- Tests invocation with sample payloads

Requirements:
- boto3
- awscli (for local testing, optional)
- env file with TEAM_ID, AWS_REGION, AWS_PROFILE, AWS_ACCOUNT_ID, PERMISSION_BOUNDARY
  (e.g. .agentcore.env.team01)

Usage:
  python scripts/deploy_mcp_lambdas.py --env-file .agentcore.env.team01
"""
import os
import sys
import json
import zipfile
import shutil
import tempfile
import time
import argparse
import re
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

_arg_parser = argparse.ArgumentParser()
_arg_parser.add_argument(
    "--env-file",
    default=".agentcore.env",
    help="Path to the env file to load (default: .agentcore.env). Use this to point at a "
         "team-specific file (e.g. .agentcore.env.team01) without touching the original."
)
_args = _arg_parser.parse_args()

load_dotenv(_args.env_file)

AWS_REGION = os.getenv('AWS_REGION', 'eu-central-1')
AWS_PROFILE = os.getenv('AWS_PROFILE')
AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID')
PERMISSION_BOUNDARY = os.getenv('PERMISSION_BOUNDARY')
TEAM_ID = os.getenv('TEAM_ID')

if not TEAM_ID:
    sys.exit("TEAM_ID must be set (in the env file or environment) - it names every "
             "resource this script creates, for full per-team isolation.")

# Build permission boundary ARN from name if not already an ARN
if PERMISSION_BOUNDARY and not PERMISSION_BOUNDARY.startswith('arn:'):
    PERMISSION_BOUNDARY_ARN = f"arn:aws:iam::{AWS_ACCOUNT_ID}:policy/{PERMISSION_BOUNDARY}"
else:
    PERMISSION_BOUNDARY_ARN = PERMISSION_BOUNDARY

# Lambda and IAM config - all resource names derived from TEAM_ID for full per-team isolation
LAMBDA_FUNCTIONS = [
    {
        'name': f'{TEAM_ID}-get-spare-parts',
        'handler': 'get_spare_parts_handler.lambda_handler',
        'filename': 'get_spare_parts_handler.py',
        'env': {
            'MCP_TOOLS_BUCKET': f'{TEAM_ID}-mcp-tools',
        },
        'test_event': {
            "part_type": "bearing"
        }
    },
    {
        'name': f'{TEAM_ID}-schedule-maintenance',
        'handler': 'schedule_maintenance_handler.lambda_handler',
        'filename': 'schedule_maintenance_handler.py',
        'env': {
            'MAINTENANCE_TABLE': f'{TEAM_ID}-maintenance-schedules',
        },
        'test_event': {
            "device_id": "DEV-001",
            "maintenance_type": "preventive",
            "scheduled_date": "2026-06-01"
        }
    }
]
LAMBDA_ROLE_NAME = f'{TEAM_ID}-mcp-tools-lambda-role'
LAMBDA_ASSUME_ROLE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }
    ]
}
LAMBDA_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{TEAM_ID}-mcp-tools/*"]
        },
        {
            "Effect": "Allow",
            "Action": ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem", "dynamodb:Query"],
            "Resource": [
                f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT_ID}:table/{TEAM_ID}-maintenance-schedules",
                f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT_ID}:table/{TEAM_ID}-work-orders"
            ]
        },
        {
            "Effect": "Allow",
            "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}

# Helper: Package Lambda code
def package_lambda(src_path, out_zip):
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(src_path, Path(src_path).name)
    print(f"Packaged {src_path} -> {out_zip}")

# Helper: Create/Update IAM Role
def ensure_iam_role(iam):
    try:
        role = iam.get_role(RoleName=LAMBDA_ROLE_NAME)
        print(f"IAM role {LAMBDA_ROLE_NAME} exists. Updating policy and trust policy if needed...")
        # Update trust policy to ensure Lambda can assume it
        iam.update_assume_role_policy(
            RoleName=LAMBDA_ROLE_NAME,
            PolicyDocument=json.dumps(LAMBDA_ASSUME_ROLE_POLICY)
        )
    except ClientError:
        print(f"Creating IAM role {LAMBDA_ROLE_NAME}...")
        role = iam.create_role(
            RoleName=LAMBDA_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(LAMBDA_ASSUME_ROLE_POLICY),
            PermissionsBoundary=PERMISSION_BOUNDARY_ARN
        )
        # Wait for IAM propagation
        print("Waiting for IAM role propagation...")
        time.sleep(15)
    # Attach policy
    iam.put_role_policy(
        RoleName=LAMBDA_ROLE_NAME,
        PolicyName=f'{TEAM_ID}-mcp-tools-lambda-policy',
        PolicyDocument=json.dumps(LAMBDA_POLICY)
    )
    return iam.get_role(RoleName=LAMBDA_ROLE_NAME)['Role']['Arn']

# Helper: Deploy Lambda
def deploy_lambda(lambda_client, function, role_arn, zip_path):
    fn_name = function['name']
    handler = function['handler']
    env_vars = function['env']
    # Check if function exists
    exists = False
    try:
        lambda_client.get_function(FunctionName=fn_name)
        exists = True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            exists = False
        else:
            raise

    if exists:
        print(f"Updating Lambda {fn_name}...")
        # Retry update if AWS reports update in progress
        for _ in range(15):
            try:
                with open(zip_path, 'rb') as f:
                    lambda_client.update_function_code(FunctionName=fn_name, ZipFile=f.read())
                lambda_client.update_function_configuration(
                    FunctionName=fn_name,
                    Role=role_arn,
                    Handler=handler,
                    Runtime='python3.9',
                    Environment={'Variables': env_vars},
                    Timeout=30,
                    MemorySize=256
                )
                break
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceConflictException':
                    print("Update in progress, waiting...")
                    time.sleep(4)
                else:
                    raise
        else:
            print(f"Warning: Lambda {fn_name} update did not succeed after retries.")
    else:
        print(f"Creating Lambda {fn_name}...")
        with open(zip_path, 'rb') as f:
            lambda_client.create_function(
                FunctionName=fn_name,
                Runtime='python3.9',
                Role=role_arn,
                Handler=handler,
                Code={'ZipFile': f.read()},
                Environment={'Variables': env_vars},
                Timeout=30,
                MemorySize=256
            )

    # Wait for Lambda to become Active
    print(f"Waiting for Lambda {fn_name} to become Active...")
    for _ in range(18):  # up to ~36 seconds
        resp = lambda_client.get_function(FunctionName=fn_name)
        state = resp['Configuration']['State']
        if state == 'Active':
            break
        time.sleep(2)
    else:
        print(f"Warning: Lambda {fn_name} did not become Active in time. Proceeding anyway.")

# Helper: Test Lambda
def test_lambda(lambda_client, function):
    fn_name = function['name']
    event = function['test_event']
    print(f"Testing {fn_name} with event: {event}")
    resp = lambda_client.invoke(
        FunctionName=fn_name,
        Payload=json.dumps(event).encode(),
    )
    payload = resp['Payload'].read().decode()
    print(f"Response: {payload}")


def merge_env_values(env_file, values):
    """Update named environment variables without changing other entries."""
    with open(env_file, 'r') as file:
        content = file.read()

    for key, value in values.items():
        pattern = rf"^{re.escape(key)}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, content, flags=re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            content = content.rstrip('\n') + f"\n{replacement}\n"

    with open(env_file, 'w') as file:
        file.write(content)

# Main deploy logic
def main():
    session = boto3.Session(profile_name=AWS_PROFILE) if AWS_PROFILE else boto3.Session()
    iam = session.client('iam')
    lambda_client = session.client('lambda', region_name=AWS_REGION)
    # 1. IAM Role
    role_arn = ensure_iam_role(iam)
    # 2. Package and deploy each Lambda
    for fn in LAMBDA_FUNCTIONS:
        src = f"tools/lambdas/{fn['filename']}"
        zip_path = f"/tmp/{fn['name']}.zip"
        package_lambda(src, zip_path)
        deploy_lambda(lambda_client, fn, role_arn, zip_path)
        test_lambda(lambda_client, fn)
    lambda_arns = {
        'GET_SPARE_PARTS_LAMBDA_ARN': lambda_client.get_function(
            FunctionName=f'{TEAM_ID}-get-spare-parts'
        )['Configuration']['FunctionArn'],
        'SCHEDULE_MAINTENANCE_LAMBDA_ARN': lambda_client.get_function(
            FunctionName=f'{TEAM_ID}-schedule-maintenance'
        )['Configuration']['FunctionArn'],
    }
    merge_env_values(_args.env_file, lambda_arns)
    print(f"✓ MCP Lambda ARNs saved to {_args.env_file}")
    print("\nDeployment complete.")

if __name__ == "__main__":
    main()
