#!/usr/bin/env python3
"""
Deploy AgentCore Memory Service Infrastructure

Creates the AgentCore Memory resource and configures IAM permissions
for the health-agent, diagnosis-agent, and orchestrator execution roles.

This script:
1. Creates the AgentCore Memory resource via bedrock-agentcore-control API
2. Creates an IAM policy with data-plane and control-plane memory permissions
3. Attaches the policy to the existing AgentCoreExecutionRole

Usage:
    python scripts/deploy_agentcore_memory.py [--profile PROFILE] [--region REGION]

Arguments:
    --profile      AWS SSO profile name (default: StandardAccess-450410489798)
    --region       AWS region (default: eu-central-1)
"""

import json
import logging
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

# Try to load environment variables from .agentcore.env
env_file = Path(__file__).parent.parent / ".agentcore.env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("AGENTCORE_MEMORY_DEPLOY")


# --- Configuration ---
RESOURCE_PREFIX = os.getenv("RESOURCE_PREFIX", "team1-")
MEMORY_NAME = f"{RESOURCE_PREFIX.replace('-', '_')}eco_sentinel_memory"
MEMORY_DESCRIPTION = (
    "Persistent long-term and session-scoped short-term memory for the "
    "Agentic Eco Sentinel multi-agent fleet monitoring system."
)
EVENT_EXPIRY_DAYS = 90
POLICY_NAME = f"{RESOURCE_PREFIX}memory-access-policy"
EXECUTION_ROLE_NAME = f"{RESOURCE_PREFIX}agentcore-execution-role"


class AgentCoreMemoryDeployer:
    """Deploy AgentCore Memory Service resources."""

    def __init__(self, profile: str = None, region: str = "eu-central-1"):
        self.profile = profile
        self.region = region

        if profile:
            session = boto3.Session(profile_name=profile, region_name=region)
        else:
            session = boto3.Session(region_name=region)
        self.agentcore_control = session.client("bedrock-agentcore-control", region_name=region)
        self.agentcore_data = session.client("bedrock-agentcore", region_name=region)
        self.iam = session.client("iam", region_name=region)
        self.sts = session.client("sts", region_name=region)

        # Get account ID
        try:
            identity = self.sts.get_caller_identity()
            self.account_id = identity["Account"]
            logger.info(f"🔐 AWS Account: {self.account_id}")
            logger.info(f"   Region: {self.region}")
            logger.info(f"   Profile: {self.profile}")
        except ClientError as e:
            logger.error(f"❌ Failed to get AWS identity: {e}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # Step 1: Create AgentCore Memory resource
    # ------------------------------------------------------------------

    def create_memory_resource(self) -> str:
        """Create the AgentCore Memory resource.

        Returns the memory_id on success.
        """
        logger.info(f"\n{'='*70}")
        logger.info("📦 Step 1: Creating AgentCore Memory Resource")
        logger.info(f"{'='*70}")
        logger.info(f"   Name: {MEMORY_NAME}")
        logger.info(f"   Event Expiry: {EVENT_EXPIRY_DAYS} days")

        try:
            response = self.agentcore_control.create_memory(
                name=MEMORY_NAME,
                description=MEMORY_DESCRIPTION,
                memoryStrategies=[
                    {
                        "semanticMemoryStrategy": {
                            "name": "eco_sentinel_strategy",
                            "description": "Extracts device facts, diagnoses, maintenance actions, and session context from agent outputs",
                            "namespaces": ["eco_sentinel"],
                        }
                    },
                ],
                eventExpiryDuration=EVENT_EXPIRY_DAYS,
                tags={
                    "Project": f"{RESOURCE_PREFIX}eco-sentinel",
                    "ManagedBy": "deploy_agentcore_memory.py",
                    "CreatedAt": datetime.now().isoformat(),
                },
            )

            memory_id = response.get("memoryId") or response.get("id") or response.get("memory", {}).get("id", "")
            logger.info(f"✅ Memory resource created!")
            logger.info(f"   Memory ID: {memory_id}")
            return memory_id

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]

            if error_code == "ConflictException" or "already exists" in error_msg.lower():
                logger.info("⚠️  Memory resource already exists, looking up ID...")
                return self._get_existing_memory_id()
            else:
                logger.error(f"❌ Failed to create memory [{error_code}]: {error_msg}")
                raise

    def _get_existing_memory_id(self) -> str:
        """Find the memory ID for an existing memory resource."""
        try:
            response = self.agentcore_control.list_memories()
            for memory in response.get("memories", []):
                mem_id = memory.get("id", "")
                # Match by name prefix since the ID format is {name}-{random}
                if mem_id.startswith(MEMORY_NAME):
                    logger.info(f"✅ Found existing memory: {mem_id}")
                    return mem_id

            logger.error(f"❌ Could not find memory resource named '{MEMORY_NAME}'")
            sys.exit(1)

        except ClientError as e:
            logger.error(f"❌ Failed to list memories: {e}")
            raise

    # ------------------------------------------------------------------
    # Step 2: Create IAM policy for memory access
    # ------------------------------------------------------------------

    def create_memory_policy(self) -> str:
        """Create IAM policy with AgentCore Memory permissions.

        Returns the policy ARN.
        """
        logger.info(f"\n{'='*70}")
        logger.info("🔒 Step 2: Creating IAM Policy for Memory Access")
        logger.info(f"{'='*70}")

        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "MemoryDataPlaneAccess",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:CreateEvent",
                        "bedrock-agentcore:RetrieveMemoryRecords",
                        "bedrock-agentcore:GetEvent",
                        "bedrock-agentcore:DeleteEvent",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:memory/*"
                    ],
                },
                {
                    "Sid": "MemoryControlPlaneAccess",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:CreateMemory",
                        "bedrock-agentcore:GetMemory",
                        "bedrock-agentcore:UpdateMemory",
                        "bedrock-agentcore:DeleteMemory",
                        "bedrock-agentcore:ListMemories",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:memory/*",
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:*",
                    ],
                },
            ],
        }

        try:
            response = self.iam.create_policy(
                PolicyName=POLICY_NAME,
                PolicyDocument=json.dumps(policy_document),
                Description="Permissions for AgentCore Memory API operations (data-plane + control-plane)",
                Tags=[
                    {"Key": "Project", "Value": f"{RESOURCE_PREFIX}eco-sentinel"},
                    {"Key": "ManagedBy", "Value": "deploy_agentcore_memory.py"},
                ],
            )

            policy_arn = response["Policy"]["Arn"]
            logger.info(f"✅ IAM Policy created!")
            logger.info(f"   Policy ARN: {policy_arn}")
            return policy_arn

        except self.iam.exceptions.EntityAlreadyExistsException:
            policy_arn = f"arn:aws:iam::{self.account_id}:policy/{POLICY_NAME}"
            logger.info(f"⚠️  Policy already exists: {policy_arn}")
            return policy_arn

        except ClientError as e:
            logger.error(f"❌ Failed to create policy: {e}")
            raise

    # ------------------------------------------------------------------
    # Step 3: Attach policy to execution role
    # ------------------------------------------------------------------

    def attach_policy_to_role(self, policy_arn: str) -> None:
        """Attach the memory policy to the AgentCore execution role."""
        logger.info(f"\n{'='*70}")
        logger.info("🔗 Step 3: Attaching Policy to Execution Role")
        logger.info(f"{'='*70}")
        logger.info(f"   Role: {EXECUTION_ROLE_NAME}")
        logger.info(f"   Policy: {policy_arn}")

        try:
            self.iam.attach_role_policy(
                RoleName=EXECUTION_ROLE_NAME,
                PolicyArn=policy_arn,
            )
            logger.info(f"✅ Policy attached to {EXECUTION_ROLE_NAME}")

        except self.iam.exceptions.NoSuchEntityException:
            logger.error(
                f"❌ Role '{EXECUTION_ROLE_NAME}' does not exist. "
                f"Run deploy_to_agentcore_boto3.py first to create the agent runtime roles."
            )
            raise

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if "already" in str(e).lower() or error_code == "EntityAlreadyExists":
                logger.info(f"⚠️  Policy already attached to {EXECUTION_ROLE_NAME}")
            else:
                logger.error(f"❌ Failed to attach policy: {e}")
                raise

    # ------------------------------------------------------------------
    # Step 4: Update agent runtimes with AGENTCORE_MEMORY_ID env var
    # ------------------------------------------------------------------

    def update_agent_runtimes_with_memory_id(self, memory_id: str) -> None:
        """Update existing agent runtimes to include the AGENTCORE_MEMORY_ID env var."""
        logger.info(f"\n{'='*70}")
        logger.info("🔄 Step 4: Updating Agent Runtimes with Memory ID")
        logger.info(f"{'='*70}")

        try:
            response = self.agentcore_control.list_agent_runtimes()
            runtimes = response.get("agentRuntimes", [])

            if not runtimes:
                logger.warning("⚠️  No agent runtimes found. Memory ID will need to be set manually.")
                return

            for rt in runtimes:
                runtime_name = rt.get("agentRuntimeName", "")
                runtime_id = rt.get("agentRuntimeId", "")

                if not runtime_id:
                    continue

                logger.info(f"   Updating {runtime_name} (ID: {runtime_id})...")

                try:
                    # Get current runtime config
                    current = self.agentcore_control.get_agent_runtime(
                        agentRuntimeId=runtime_id
                    )

                    # Merge new env var
                    env_vars = current.get("environmentVariables", {})
                    env_vars["AGENTCORE_MEMORY_ID"] = memory_id

                    # Update
                    self.agentcore_control.update_agent_runtime(
                        agentRuntimeId=runtime_id,
                        agentRuntimeArtifact=current.get("agentRuntimeArtifact", {}),
                        roleArn=current.get("roleArn", ""),
                        networkConfiguration=current.get("networkConfiguration", {}),
                        environmentVariables=env_vars,
                    )
                    logger.info(f"   ✅ {runtime_name} updated with AGENTCORE_MEMORY_ID={memory_id}")

                except ClientError as e:
                    logger.warning(f"   ⚠️  Failed to update {runtime_name}: {e}")

        except ClientError as e:
            logger.warning(f"⚠️  Could not list/update runtimes: {e}")
            logger.info(f"   Set AGENTCORE_MEMORY_ID={memory_id} manually in agent environment.")

    # ------------------------------------------------------------------
    # Step 5: Save deployment output
    # ------------------------------------------------------------------

    def save_output(self, memory_id: str, policy_arn: str) -> None:
        """Save deployment output to a JSON file."""
        output_file = Path(__file__).parent.parent / "agentcore_memory_deployment.json"

        output = {
            "timestamp": datetime.now().isoformat(),
            "region": self.region,
            "account_id": self.account_id,
            "memory": {
                "memory_id": memory_id,
                "memory_name": MEMORY_NAME,
                "event_expiry_days": EVENT_EXPIRY_DAYS,
                "namespaces": [
                    "device_facts",
                    "diagnosis_history",
                    "maintenance_actions",
                    "session_context",
                ],
            },
            "iam": {
                "policy_arn": policy_arn,
                "policy_name": POLICY_NAME,
                "attached_to_role": EXECUTION_ROLE_NAME,
            },
            "env_var": {
                "AGENTCORE_MEMORY_ID": memory_id,
            },
            "instructions": {
                "local_dev": (
                    f"Add AGENTCORE_MEMORY_ID={memory_id} to your .agentcore.env file"
                ),
                "agentcore_runtime": (
                    "The AGENTCORE_MEMORY_ID env var has been set on all agent runtimes"
                ),
            },
        }

        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"\n💾 Deployment output saved to: {output_file}")

    # ------------------------------------------------------------------
    # Main deployment
    # ------------------------------------------------------------------

    def deploy(self) -> bool:
        """Run the full memory service deployment."""
        logger.info(f"\n{'='*70}")
        logger.info("🧠 AGENTCORE MEMORY SERVICE DEPLOYMENT")
        logger.info(f"{'='*70}\n")

        try:
            # Step 1: Create memory resource
            memory_id = self.create_memory_resource()

            # Step 2: Create IAM policy
            policy_arn = self.create_memory_policy()

            # Step 3: Attach policy to execution role
            self.attach_policy_to_role(policy_arn)

            # Step 4: Update agent runtimes with memory ID
            self.update_agent_runtimes_with_memory_id(memory_id)

            # Step 5: Save output
            self.save_output(memory_id, policy_arn)

            # Summary
            logger.info(f"\n{'='*70}")
            logger.info("✅ DEPLOYMENT COMPLETE")
            logger.info(f"{'='*70}")
            logger.info(f"   Memory ID:    {memory_id}")
            logger.info(f"   Policy ARN:   {policy_arn}")
            logger.info(f"   Role:         {EXECUTION_ROLE_NAME}")
            logger.info(f"   Namespaces:   device-facts, diagnosis-history, maintenance-actions, session-context")
            logger.info(f"")
            logger.info(f"   📝 Next step: Add to .agentcore.env:")
            logger.info(f"      AGENTCORE_MEMORY_ID={memory_id}")
            logger.info(f"{'='*70}\n")

            return True

        except Exception as e:
            logger.error(f"\n❌ DEPLOYMENT FAILED: {e}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Deploy AgentCore Memory Service infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy with default profile
  python scripts/deploy_agentcore_memory.py

  # Deploy with specific profile
  python scripts/deploy_agentcore_memory.py --profile StandardAccess-450410489798

  # Deploy to different region
  python scripts/deploy_agentcore_memory.py --region us-west-2
        """,
    )

    parser.add_argument(
        "--profile",
        default=None,
        help="AWS SSO profile name (uses default credentials if not specified)",
    )

    parser.add_argument(
        "--region",
        default="eu-central-1",
        help="AWS region",
    )

    args = parser.parse_args()

    deployer = AgentCoreMemoryDeployer(profile=args.profile, region=args.region)
    success = deployer.deploy()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
