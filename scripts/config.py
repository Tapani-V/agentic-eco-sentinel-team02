#!/usr/bin/env python3
"""
Configuration loader for Agentic AI POC

Loads settings from .env file with validation.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Load and validate environment configuration."""
    
    def __init__(self, env_file: str = ".env"):
        # Load .env file from project root
        env_path = Path(__file__).parent.parent / env_file
        if env_path.exists():
            load_dotenv(env_path)
        else:
            raise FileNotFoundError(
                f"Configuration file not found: {env_path}\n"
                f"Please create .env from .env.template"
            )
    
    @property
    def region(self) -> str:
        """AWS region."""
        return os.getenv("AWS_REGION", "us-east-1")
    
    @property
    def profile(self) -> str:
        """AWS SSO profile name."""
        return os.getenv("AWS_PROFILE", "default")
    
    @property
    def account_id(self) -> str:
        """AWS account ID."""
        account_id = os.getenv("AWS_ACCOUNT_ID")
        if not account_id:
            raise ValueError("AWS_ACCOUNT_ID not set in .env")
        return account_id
    
    @property
    def permission_boundary(self) -> str:
        """IAM permission boundary policy name."""
        boundary = os.getenv("PERMISSION_BOUNDARY")
        if not boundary:
            raise ValueError("PERMISSION_BOUNDARY not set in .env")
        return boundary
    
    @property
    def project_name(self) -> str:
        """Project name for resource naming."""
        return os.getenv("PROJECT_NAME", "agentic-ai-poc")
    
    @property
    def environment(self) -> str:
        """Environment (development/staging/production)."""
        return os.getenv("ENVIRONMENT", "development")
    
    # Cognito settings
    @property
    def cognito_user_pool_name(self) -> str:
        """Cognito User Pool name."""
        return os.getenv("COGNITO_USER_POOL_NAME", "agentic-ai-poc-user-pool")
    
    @property
    def cognito_client_name(self) -> str:
        """Cognito User Pool Client name."""
        return os.getenv("COGNITO_CLIENT_NAME", "agentic-ai-client")
    
    @property
    def cognito_test_user_email(self) -> str:
        """Test user email."""
        return os.getenv("COGNITO_TEST_USER_EMAIL", "test@example.com")
    
    @property
    def cognito_test_user_password(self) -> str:
        """Test user password."""
        password = os.getenv("COGNITO_TEST_USER_PASSWORD")
        if not password:
            raise ValueError("COGNITO_TEST_USER_PASSWORD not set in .env")
        return password
    
    # DynamoDB settings
    @property
    def dynamodb_table_name(self) -> str:
        """DynamoDB table name."""
        return os.getenv("DYNAMODB_TABLE_NAME", "agentic-ai-conversation-memory")
    
    @property
    def dynamodb_billing_mode(self) -> str:
        """DynamoDB billing mode."""
        return os.getenv("DYNAMODB_BILLING_MODE", "PAY_PER_REQUEST")
    
    # Azure OpenAI settings (optional)
    @property
    def azure_openai_api_key(self) -> str:
        """Azure OpenAI API key."""
        return os.getenv("AZURE_OPENAI_API_KEY", "")
    
    @property
    def azure_openai_endpoint(self) -> str:
        """Azure OpenAI endpoint."""
        return os.getenv("AZURE_OPENAI_ENDPOINT", "")
    
    @property
    def azure_openai_deployment(self) -> str:
        """Azure OpenAI deployment name."""
        return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    def validate(self) -> bool:
        """Validate all required configuration."""
        required = [
            "account_id",
            "permission_boundary",
            "cognito_test_user_password"
        ]
        
        missing = []
        for field in required:
            try:
                getattr(self, field)
            except ValueError as e:
                missing.append(str(e))
        
        if missing:
            print("❌ Configuration errors:")
            for error in missing:
                print(f"  - {error}")
            return False
        
        return True
    
    def __str__(self) -> str:
        """Print configuration (masks sensitive values)."""
        return f"""
Configuration:
  Region: {self.region}
  Profile: {self.profile}
  Account ID: {self.account_id}
  Permission Boundary: {self.permission_boundary}
  Environment: {self.environment}
  
  Cognito Pool: {self.cognito_user_pool_name}
  DynamoDB Table: {self.dynamodb_table_name}
  LLM Enabled: {bool(self.azure_openai_api_key)}
"""
