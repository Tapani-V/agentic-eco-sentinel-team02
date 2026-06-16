#!/usr/bin/env python3
"""
Create IAM role for AWS App Runner to pull from ECR with AmazonEC2ContainerRegistryReadOnly policy and permission boundary.
"""
import boto3
import json
import sys

REGION = "us-east-1"  # Change if needed
ACCOUNT_ID = None  # Will be set dynamically
PERMISSION_BOUNDARY = "GroupIT_ProjectPermissionBoundary"  # Change if needed
ROLE_NAME = "apprunner-ecr-pull-role"
POLICY_ARN = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
SERVICE = "build.apprunner.amazonaws.com"

def main():
    session = boto3.session.Session(region_name=REGION)
    sts = session.client("sts")
    global ACCOUNT_ID
    ACCOUNT_ID = sts.get_caller_identity()["Account"]
    iam = session.client("iam")
    pb_arn = f"arn:aws:iam::{ACCOUNT_ID}:policy/{PERMISSION_BOUNDARY}"

    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": SERVICE},
                "Action": "sts:AssumeRole"
            }
        ]
    }

    try:
        resp = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            PermissionsBoundary=pb_arn,
            Description="App Runner ECR pull role for MCP tool",
            Tags=[
                {"Key": "Project", "Value": "agentic-ai-poc"},
                {"Key": "Phase", "Value": "phase-1"}
            ]
        )
        print(f"✓ Created role: {ROLE_NAME}")
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"⚠ Role already exists: {ROLE_NAME}")

    # Attach managed policy
    iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=POLICY_ARN)
    print(f"✓ Attached AmazonEC2ContainerRegistryReadOnly policy to {ROLE_NAME}")

    role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/{ROLE_NAME}"
    print(f"App Runner ECR pull role ARN: {role_arn}")
    print("Use this ARN in your App Runner deployment.")

if __name__ == "__main__":
    main()
