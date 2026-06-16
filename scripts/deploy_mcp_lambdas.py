#!/usr/bin/env python3
"""
Deploys MCP Lambda functions to AWS:
- Creates/updates IAM role with correct permissions and permission boundary
- Packages Lambda code (and dependencies if needed)
- Deploys/updates Lambda functions
- Sets environment variables
- Tests invocation with sample payloads

Requirements:
- boto3
- awscli (for local testing, optional)
- .env file with AWS_REGION, AWS_PROFILE, AWS_ACCOUNT_ID, PERMISSION_BOUNDARY

Usage:
  python scripts/deploy_mcp_lambdas.py
"""
import os
import sys
import json
import zipfile
import shutil
import tempfile
import time
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load .env
load_dotenv()

AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_PROFILE = os.getenv('AWS_PROFILE')
AWS_ACCOUNT_ID = os.getenv('AWS_ACCOUNT_ID')
PERMISSION_BOUNDARY = os.getenv('PERMISSION_BOUNDARY')

# Build permission boundary ARN from name if not already an ARN
if PERMISSION_BOUNDARY and not PERMISSION_BOUNDARY.startswith('arn:'):
    PERMISSION_BOUNDARY_ARN = f"arn:aws:iam::{AWS_ACCOUNT_ID}:policy/{PERMISSION_BOUNDARY}"
else:
    PERMISSION_BOUNDARY_ARN = PERMISSION_BOUNDARY

# Lambda and IAM config
LAMBDA_FUNCTIONS = [
    {
        'name': 'get_spare_parts',
        'handler': 'get_spare_parts_handler.lambda_handler',
        'filename': 'get_spare_parts_handler.py',
        'env': {
            'MCP_TOOLS_BUCKET': 'agentic-ai-poc-3-1-mcp-tools',
        },
        'test_event': {
            "part_type": "bearing"
        }
    },
    {
        'name': 'schedule_maintenance',
        'handler': 'schedule_maintenance_handler.lambda_handler',
        'filename': 'schedule_maintenance_handler.py',
        'env': {
            'MAINTENANCE_TABLE': 'maintenance_schedules',
        },
        'test_event': {
            "device_id": "DEV-001",
            "maintenance_type": "preventive",
            "scheduled_date": "2026-06-01"
        }
    }
]
LAMBDA_ROLE_NAME = 'MCPToolsLambdaRole'
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
            "Resource": ["arn:aws:s3:::agentic-ai-poc-3-1-mcp-tools/*"]
        },
        {
            "Effect": "Allow",
            "Action": ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem", "dynamodb:Query"],
            "Resource": [
                f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT_ID}:table/maintenance_schedules",
                f"arn:aws:dynamodb:{AWS_REGION}:{AWS_ACCOUNT_ID}:table/work_orders"
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
        PolicyName='MCPToolsLambdaPolicy',
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
    print("\nDeployment complete.")

if __name__ == "__main__":
    main()
