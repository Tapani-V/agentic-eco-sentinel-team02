#!/usr/bin/env python3
"""
Cognito User Pool Setup for Agentic AI POC Phase 1

Creates Cognito User Pool for authentication with:
- JWT token generation
- Test user for local development
- Client app for frontend
"""

import json
import boto3
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class CognitoSetup:
    """Manages Cognito User Pool creation and configuration."""
    
    def __init__(self, region: str):
        self.cognito_client = boto3.client("cognito-idp", region_name=region)
        self.region = region
    
    def create_user_pool(self, user_pool_name: str) -> str:
        """Create Cognito User Pool."""
        # Check if pool already exists
        try:
            pools = self.cognito_client.list_user_pools(MaxResults=60)
            for pool in pools["UserPools"]:
                if pool["Name"] == user_pool_name:
                    logger.info(f"✓ Using existing Cognito User Pool: {user_pool_name}")
                    logger.info(f"  Pool ID: {pool['Id']}")
                    return pool["Id"]
        except Exception as e:
            logger.warning(f"⚠ Could not list pools: {e}")
        
        # Pool doesn't exist, create it
        try:
            response = self.cognito_client.create_user_pool(
                PoolName=user_pool_name,
                Policies={
                    "PasswordPolicy": {
                        "MinimumLength": 8,
                        "RequireUppercase": True,
                        "RequireLowercase": True,
                        "RequireNumbers": True,
                        "RequireSymbols": False
                    }
                },
                LambdaConfig={},
                Schema=[
                    {
                        "Name": "email",
                        "AttributeDataType": "String",
                        "Required": True,
                        "Mutable": True
                    },
                    {
                        "Name": "name",
                        "AttributeDataType": "String",
                        "Required": False,
                        "Mutable": True
                    }
                ],
                AutoVerifiedAttributes=["email"],
                EmailVerificationMessage="Your verification code is {####}",
                EmailVerificationSubject="Equipment Diagnostics - Verification Code",
                EmailConfiguration={
                    "EmailSendingAccount": "COGNITO_DEFAULT"
                },
                UserPoolTags={
                    "Project": "agentic-ai-poc",
                    "Phase": "phase-1"
                }
            )
            
            user_pool_id = response["UserPool"]["Id"]
            logger.info(f"✓ Created Cognito User Pool: {user_pool_name}")
            logger.info(f"  Pool ID: {user_pool_id}")
            return user_pool_id
        
        except Exception as e:
            logger.error(f"✗ Failed to create user pool: {e}")
            raise
    
    def create_user_pool_client(self, user_pool_id: str, client_name: str) -> Dict[str, str]:
        """Create User Pool Client for frontend/API access."""
        try:
            response = self.cognito_client.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName=client_name,
                ExplicitAuthFlows=[
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_REFRESH_TOKEN_AUTH",
                    "ALLOW_USER_SRP_AUTH"
                ],
                AccessTokenValidity=1,
                IdTokenValidity=1,
                RefreshTokenValidity=30,
                TokenValidityUnits={
                    "AccessToken": "hours",
                    "IdToken": "hours",
                    "RefreshToken": "days"
                },
                ReadAttributes=["email", "name"]
            )
            
            client_id = response["UserPoolClient"]["ClientId"]
            logger.info(f"✓ Created User Pool Client: {client_name}")
            logger.info(f"  Client ID: {client_id}")
            
            return {
                "client_id": client_id,
                "user_pool_id": user_pool_id
            }
        
        except Exception as e:
            logger.error(f"✗ Failed to create user pool client: {e}")
            raise
    
    def create_test_user(self, user_pool_id: str, email: str, password: str) -> None:
        """Create test user for local development."""
        try:
            # Admin create user
            self.cognito_client.admin_create_user(
                UserPoolId=user_pool_id,
                Username=email,
                TemporaryPassword=password,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"},
                    {"Name": "name", "Value": "Test User"}
                ],
                MessageAction="SUPPRESS"
            )
            
            logger.info(f"✓ Created test user: {email}")
            
            # Set permanent password
            self.cognito_client.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=email,
                Password=password,
                Permanent=True
            )
            
            logger.info(f"✓ Password set permanently for: {email}")
        
        except self.cognito_client.exceptions.UsernameExistsException:
            logger.warning(f"⚠ Test user already exists: {email}")
        
        except Exception as e:
            logger.error(f"✗ Failed to create test user: {e}")
            raise
    
    def setup_cognito(self, user_pool_name: str, client_name: str, 
                     test_email: str, test_password: str) -> Dict[str, str]:
        """Setup complete Cognito infrastructure."""
        logger.info("=" * 60)
        logger.info("Starting Cognito User Pool Setup")
        logger.info("=" * 60)
        
        try:
            # Create user pool
            user_pool_id = self.create_user_pool(user_pool_name)
            
            # Create client
            client_info = self.create_user_pool_client(user_pool_id, client_name)
            
            # Create test user
            self.create_test_user(user_pool_id, test_email, test_password)
            
            logger.info("=" * 60)
            logger.info("✓ Cognito setup completed successfully")
            logger.info("=" * 60)
            
            return {
                "user_pool_id": user_pool_id,
                "client_id": client_info["client_id"],
                "test_email": test_email
            }
        
        except Exception as e:
            logger.error(f"✗ Cognito setup failed: {e}")
            raise


def setup_cognito(region: str, user_pool_name: str, client_name: str,
                 test_email: str, test_password: str) -> Dict[str, str]:
    """Main function to setup Cognito."""
    cognito_setup = CognitoSetup(region)
    return cognito_setup.setup_cognito(user_pool_name, client_name, test_email, test_password)


if __name__ == "__main__":
    import sys
    import argparse
    from pathlib import Path
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="Cognito User Pool Setup")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the env file to load (default: .env). Use this to point at a "
             "team-specific file (e.g. .env.team01) without touching the original."
    )
    parser.add_argument(
        "--agentcore-env-file",
        default=None,
        help="Path to persist COGNITO_USER_POOL_ID into (default: derived from --env-file, "
             "e.g. .env.team01 -> .agentcore.env.team01)."
    )
    cli_args = parser.parse_args()
    
    # Load environment variables
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.config import Config
    
    config = Config(env_file=cli_args.env_file)
    cognito_info = setup_cognito(
        config.region,
        config.cognito_user_pool_name,
        config.cognito_client_name,
        config.cognito_test_user_email,
        config.cognito_test_user_password
    )
    
    # Print results
    print("\n🔐 Cognito Configuration:")
    for key, value in cognito_info.items():
        print(f"  {key}: {value}")
    
    # Persist user_pool_id into the paired AgentCore env file so downstream
    # scripts (setup_cognito_token_flow.py, create_agentcore_gateway_starter.py,
    # etc.) don't need a manual copy step.
    agentcore_env_file = cli_args.agentcore_env_file
    if agentcore_env_file is None:
        suffix = cli_args.env_file[len(".env"):] if cli_args.env_file.startswith(".env") else ""
        agentcore_env_file = f".agentcore.env{suffix}"
    
    from scripts.setup_cognito_token_flow import merge_env_values
    merge_env_values(agentcore_env_file, {"COGNITO_USER_POOL_ID": cognito_info["user_pool_id"]})
    print(f"\n✓ Persisted COGNITO_USER_POOL_ID into {agentcore_env_file}")
