#!/usr/bin/env python3
"""
IAM Role Setup for Agentic AI POC Phase 1

Creates IAM roles with permission boundaries for:
- Agent execution role
- Lambda tool execution roles
- ECS task execution role
"""

import json
import boto3
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class IAMSetup:
    """Manages IAM role creation with permission boundaries."""
    
    def __init__(self, region: str, account_id: str, permission_boundary: str):
        self.iam_client = boto3.client("iam", region_name=region)
        self.account_id = account_id
        self.permission_boundary_arn = f"arn:aws:iam::{account_id}:policy/{permission_boundary}"
        self.region = region
    
    def _get_assume_role_policy(self, service: str) -> Dict:
        """Generate assume role policy for AWS service."""
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": service
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
    
    def _create_role(self, role_name: str, service: str) -> str:
        """Create IAM role with permission boundary."""
        try:
            assume_role_policy = self._get_assume_role_policy(service)
            
            response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                PermissionsBoundary=self.permission_boundary_arn,
                Description=f"Role for {role_name}",
                Tags=[
                    {"Key": "Project", "Value": "agentic-ai-poc"},
                    {"Key": "Phase", "Value": "phase-1"}
                ]
            )
            
            role_arn = response["Role"]["Arn"]
            logger.info(f"✓ Created role: {role_name}")
            logger.info(f"  ARN: {role_arn}")
            return role_arn
        
        except self.iam_client.exceptions.EntityAlreadyExistsException:
            logger.warning(f"⚠ Role already exists: {role_name}")
            response = self.iam_client.get_role(RoleName=role_name)
            return response["Role"]["Arn"]
    
    def _attach_policy(self, role_name: str, policy_name: str, policy_document: Dict) -> None:
        """Attach inline policy to role."""
        try:
            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document)
            )
            logger.info(f"✓ Attached policy {policy_name} to {role_name}")
        except Exception as e:
            logger.error(f"✗ Failed to attach policy: {e}")
            raise
    
    def create_agent_role(self) -> str:
        """Create role for local agent execution."""
        role_name = "team01-agent-role"
        role_arn = self._create_role(role_name, "ec2.amazonaws.com")
        
        # Policy for agents to call AWS services
        agent_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeAgent",
                        "bedrock:InvokeModel",
                        "bedrock-runtime:InvokeAgent",
                        "bedrock-runtime:InvokeModel"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "cognito-idp:InitiateAuth",
                        "cognito-idp:GetUser"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "lambda:InvokeFunction"
                    ],
                    "Resource": [
                        f"arn:aws:lambda:{self.region}:{self.account_id}:function:mcp-1-*",
                        f"arn:aws:lambda:{self.region}:{self.account_id}:function:mcp-2-*"
                    ]
                }
            ]
        }
        
        self._attach_policy(role_name, "team01-agent-policy", agent_policy)
        return role_arn
    
    def create_lambda_execution_role(self) -> str:
        """Create role for Lambda tool execution."""
        role_name = "team01-lambda-execution-role"
        role_arn = self._create_role(role_name, "lambda.amazonaws.com")
        
        # Policy for Lambda tools (basic + DynamoDB access)
        lambda_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": "arn:aws:logs:*:*:*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject"
                    ],
                    "Resource": f"arn:aws:s3:::team01-*/*"
                }
            ]
        }
        
        self._attach_policy(role_name, "team01-lambda-policy", lambda_policy)
        return role_arn
    
    def create_ecs_task_role(self) -> str:
        """Create role for ECS task execution (MCP-3, MCP-4)."""
        role_name = "team01-ecs-task-role"
        role_arn = self._create_role(role_name, "ecs-tasks.amazonaws.com")
        
        # Policy for ECS tasks (includes external API access)
        ecs_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": "arn:aws:logs:*:*:*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue"
                    ],
                    "Resource": [
                        f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:team01-*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject"
                    ],
                    "Resource": f"arn:aws:s3:::team01-*/*"
                }
            ]
        }
        
        self._attach_policy(role_name, "team01-ecs-policy", ecs_policy)
        return role_arn
    
    def setup_all_roles(self) -> Dict[str, str]:
        """Create all required IAM roles."""
        logger.info("=" * 60)
        logger.info("Starting IAM Role Creation")
        logger.info("=" * 60)
        
        try:
            roles = {
                "agent_role": self.create_agent_role(),
                "lambda_execution_role": self.create_lambda_execution_role(),
                "ecs_task_role": self.create_ecs_task_role()
            }
            
            logger.info("=" * 60)
            logger.info("✓ All IAM roles created successfully")
            logger.info("=" * 60)
            
            return roles
        
        except Exception as e:
            logger.error(f"✗ Failed to create IAM roles: {e}")
            raise


def setup_iam_roles(region: str, account_id: str, permission_boundary: str) -> Dict[str, str]:
    """Main function to setup all IAM roles."""
    iam_setup = IAMSetup(region, account_id, permission_boundary)
    return iam_setup.setup_all_roles()


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    # Load environment variables
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.config import Config
    
    config = Config()
    roles = setup_iam_roles(config.region, config.account_id, config.permission_boundary)
    
    # Print results
    print("\n📋 Created IAM Roles:")
    for role_name, role_arn in roles.items():
        print(f"  {role_name}: {role_arn}")
