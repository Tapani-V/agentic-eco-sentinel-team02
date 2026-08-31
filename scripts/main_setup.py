#!/usr/bin/env python3
"""
Main Setup Orchestration Script for Agentic AI POC Phase 1

Coordinates creation of all AWS resources in correct order:
1. IAM Roles (required by other services)
2. Cognito User Pool (for authentication)

Usage:
    python scripts/main_setup.py
"""

import sys
import logging
from pathlib import Path
from typing import Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config import Config
from scripts.iam_setup import setup_iam_roles
from scripts.cognito_setup import setup_cognito


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def print_header(text: str) -> None:
    """Print section header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_summary(results: Dict) -> None:
    """Print setup summary."""
    print_header("🎉 SETUP COMPLETE - SUMMARY")
    
    print("✓ IAM Roles Created:")
    for role_name, role_arn in results["iam_roles"].items():
        print(f"    {role_name}: {role_arn}")
    
    print("\n✓ Cognito Configuration:")
    cognito = results["cognito"]
    print(f"    User Pool ID: {cognito['user_pool_id']}")
    print(f"    Client ID: {cognito['client_id']}")
    print(f"    Test Email: {cognito['test_email']}")
    
    print("\n" + "=" * 70)
    print("📝 Next Steps:")
    print("=" * 70)
    print("""
1. ✅ Project structure created
2. ✅ .env file ready (update with your values)
3. ✅ IAM roles created with permission boundary
4. ✅ Cognito User Pool created

Ready for Week 1 Day 3-4: Synthetic sensor data generator

To proceed:
  - Review .env settings
  - Run: python scripts/main_setup.py verify
  - Then start building agents
""")


def verify_setup(config: Config) -> bool:
    """Verify that AWS resources were created."""
    print_header("🔍 Verifying AWS Resources")
    
    try:
        # Check IAM roles
        iam_client = __import__("boto3").client("iam", region_name=config.region)
        roles = [
            "agentic-ai-agent-role",
            "agentic-ai-lambda-execution-role",
            "agentic-ai-ecs-task-role"
        ]
        
        print("Checking IAM Roles...")
        for role_name in roles:
            try:
                response = iam_client.get_role(RoleName=role_name)
                print(f"  ✓ {role_name}")
            except iam_client.exceptions.NoSuchEntityException:
                print(f"  ✗ {role_name} not found")
                return False
        
        # Check Cognito
        cognito_client = __import__("boto3").client("cognito-idp", region_name=config.region)
        print("\nChecking Cognito User Pool...")
        try:
            pools = cognito_client.list_user_pools(MaxResults=60)
            found = False
            for pool in pools["UserPools"]:
                if pool["Name"] == config.cognito_user_pool_name:
                    print(f"  ✓ {pool['Name']} (ID: {pool['Id']})")
                    found = True
                    break
            if not found:
                print(f"  ✗ {config.cognito_user_pool_name} not found")
                return False
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False
        
        print("\n✅ All resources verified!")
        return True
    
    except Exception as e:
        logger.error(f"✗ Verification failed: {e}")
        return False


def main():
    """Main setup orchestration."""
    print_header("🚀 AGENTIC AI POC - PHASE 1 SETUP")
    
    # Load configuration
    try:
        config = Config()
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("\nPlease create .env file:")
        print("  cp .env.team01.example .env.<team_id>")
        print("  # Edit it with your team's values")
        sys.exit(1)
    
    # Validate configuration
    if not config.validate():
        sys.exit(1)
    
    print("📋 Configuration Loaded:")
    print(config)
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "verify":
            return verify_setup(config)
        else:
            print(f"❌ Unknown command: {sys.argv[1]}")
            print("Usage: python scripts/main_setup.py [verify]")
            sys.exit(1)
    
    # Run setup in order
    try:
        results = {}
        
        # Step 1: Create IAM roles
        print_header("Step 1: Creating IAM Roles")
        results["iam_roles"] = setup_iam_roles(
            config.region,
            config.account_id,
            config.permission_boundary
        )
        
        # Step 2: Create Cognito User Pool
        print_header("Step 2: Creating Cognito User Pool")
        results["cognito"] = setup_cognito(
            config.region,
            config.cognito_user_pool_name,
            config.cognito_client_name,
            config.cognito_test_user_email,
            config.cognito_test_user_password
        )
        
        # Print summary
        print_summary(results)
        
        return True
    
    except Exception as e:
        logger.error(f"\n❌ Setup failed: {e}")
        print("\n⚠️  Troubleshooting:")
        print("  - Check AWS SSO profile: aws configure list --profile <profile>")
        print("  - Verify permission boundary exists: aws iam get-policy --policy-arn arn:aws:iam::<account>:policy/GroupIT_ProjectPermissionBoundary")
        print("  - Check AWS credentials: aws sts get-caller-identity")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
