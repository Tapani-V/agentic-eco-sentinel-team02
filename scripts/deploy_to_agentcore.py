#!/usr/bin/env python3
"""
Deploy Agents to AWS Bedrock AgentCore Runtime using bedrock-agentcore-starter-toolkit

This script deploys agents using the official AWS Bedrock AgentCore starter toolkit.
Each agent has an agentcore.yaml configuration file that defines its specifications.

Usage:
    python scripts/deploy_to_agentcore.py [--local] [--profile StandardAccess-450410489798] [--region us-east-1]

Arguments:
    --local          Deploy locally instead of to cloud (for testing)
    --profile        AWS SSO profile name (default: StandardAccess-450410489798)
    --region         AWS region (default: us-east-1)
    --dry-run        Show deployment plan without actually deploying

Configuration Files:
    agents/orchestrator/agentcore.yaml
    agents/health_agent/agentcore.yaml
    agents/diagnosis_agent/agentcore.yaml

Output:
    agent_endpoints.json: Deployed agent endpoints for dashboard usage
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Optional
import argparse
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s %(name)s: %(message)s'
)
logger = logging.getLogger('AGENTCORE_DEPLOY')


class AgentCoreDeployerToolkit:
    """Deploy agents to AWS Bedrock AgentCore Runtime using official toolkit"""
    
    def __init__(self, profile: str = "StandardAccess-450410489798", region: str = "us-east-1", local: bool = False):
        """
        Initialize deployer with AWS credentials
        
        Args:
            profile: AWS SSO profile name
            region: AWS region
            local: Whether to deploy locally (for testing)
        """
        self.profile = profile
        self.region = region
        self.local = local
        self.agents_dir = Path(__file__).parent.parent / "agents"
        self.endpoints = {}
        
        logger.info(f"🚀 AgentCore Deployer initialized (Toolkit-based)")
        logger.info(f"   Mode: {'LOCAL' if local else 'CLOUD'}")
        logger.info(f"   AWS Profile: {profile}")
        logger.info(f"   AWS Region: {region}")
        logger.info(f"   Agents Dir: {self.agents_dir}")
        
        # Import bedrock toolkit
        try:
            from bedrock_agentcore_starter_toolkit.operations.runtime import launch_bedrock_agentcore
            self.launch_bedrock_agentcore = launch_bedrock_agentcore
            logger.info("✅ bedrock-agentcore-starter-toolkit imported successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import bedrock-agentcore-starter-toolkit: {e}")
            logger.error("   Install with: pip install bedrock-agentcore-starter-toolkit")
            sys.exit(1)
    
    def deploy_agent(self, agent_name: str) -> Optional[str]:
        """
        Deploy a single agent to AgentCore Runtime
        
        Args:
            agent_name: Name of agent directory (orchestrator, health_agent, diagnosis_agent)
            
        Returns:
            Agent endpoint URL if successful, None otherwise
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 Deploying Agent: {agent_name}")
        logger.info(f"{'='*80}")
        
        # Find config file
        config_file = self.agents_dir / agent_name / "agentcore.yaml"
        
        if not config_file.exists():
            logger.error(f"❌ Configuration file not found: {config_file}")
            logger.error(f"   Expected: {config_file}")
            return None
        
        logger.info(f"📋 Configuration: {config_file}")
        
        try:
            # Deploy using toolkit
            logger.info(f"📤 Deploying to AgentCore Runtime...")
            
            result = self.launch_bedrock_agentcore(
                config_path=config_file,
                agent_name=agent_name,
                local=self.local,
                auto_update_on_conflict=True,
                use_codebuild=False  # Skip CodeBuild - use pre-built images from ECR
            )
            
            # Extract endpoint from result
            if self.local:
                # Local deployment uses port
                endpoint = f"http://localhost:{result.port or 8001}"
                logger.info(f"✅ Local deployment successful!")
                logger.info(f"   Port: {result.port}")
            else:
                # Cloud deployment uses agent_arn or agent_id
                endpoint = f"https://{agent_name}.agentcore.aws.amazon.com"
                if result.agent_id:
                    endpoint = f"https://agent-{result.agent_id}.agentcore.us-east-1.amazonaws.com"
                logger.info(f"✅ Cloud deployment successful!")
                logger.info(f"   Agent ID: {result.agent_id}")
                logger.info(f"   Agent ARN: {result.agent_arn}")
            
            logger.info(f"   Endpoint: {endpoint}")
            logger.info(f"   Tag: {result.tag}")
            
            return endpoint
            
        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}")
            logger.error(f"   Check configuration file syntax")
            logger.error(f"   Verify AWS credentials and permissions")
            return None
    
    def save_endpoints(self):
        """Save agent endpoints to agent_endpoints.json for dashboard usage"""
        output_file = self.agents_dir.parent / "agent_endpoints.json"
        
        endpoints_data = {
            "timestamp": datetime.now().isoformat(),
            "mode": "local" if self.local else "cloud",
            "region": self.region,
            "profile": self.profile,
            "agents": self.endpoints,
            "instructions": {
                "orchestrator": f"Call {self.endpoints.get('orchestrator', 'N/A')} to invoke full workflow",
                "health_agent": f"Call {self.endpoints.get('health_agent', 'N/A')} for health analysis",
                "diagnosis_agent": f"Call {self.endpoints.get('diagnosis_agent', 'N/A')} for diagnostics"
            }
        }
        
        try:
            with open(output_file, 'w') as f:
                json.dump(endpoints_data, f, indent=2)
            logger.info(f"✅ Endpoints saved to: {output_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save endpoints: {e}")
    
    def deploy_all(self) -> bool:
        """Deploy all agents to AgentCore Runtime"""
        agents_to_deploy = [
            "orchestrator",
            "health_agent",
            "diagnosis_agent"
        ]
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🌐 AGENTCORE RUNTIME DEPLOYMENT (using bedrock-agentcore-starter-toolkit)")
        logger.info(f"{'='*80}")
        
        success_count = 0
        for agent_name in agents_to_deploy:
            endpoint = self.deploy_agent(agent_name)
            if endpoint:
                self.endpoints[agent_name] = endpoint
                success_count += 1
            else:
                logger.warning(f"⚠️  Agent deployment skipped: {agent_name}")
        
        # Save endpoints
        self.save_endpoints()
        
        # Summary
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 DEPLOYMENT SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"✅ Successful: {success_count}/{len(agents_to_deploy)}")
        logger.info(f"📍 Mode: {'LOCAL (testing)' if self.local else 'CLOUD'}")
        logger.info(f"")
        
        for agent_name, endpoint in self.endpoints.items():
            logger.info(f"  {agent_name:20s} → {endpoint}")
        
        logger.info(f"{'='*80}\n")
        
        return success_count == len(agents_to_deploy)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Deploy agents to AWS Bedrock AgentCore Runtime using official toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy to cloud with default profile
  python scripts/deploy_to_agentcore.py
  
  # Deploy locally for testing
  python scripts/deploy_to_agentcore.py --local
  
  # Deploy with specific AWS profile
  python scripts/deploy_to_agentcore.py --profile StandardAccess-450410489798
  
  # Deploy to different region
  python scripts/deploy_to_agentcore.py --region us-west-2
  
  # Dry run (show what would be deployed)
  python scripts/deploy_to_agentcore.py --dry-run
        """
    )
    
    parser.add_argument(
        '--local',
        action='store_true',
        help='Deploy locally (for testing) instead of to cloud'
    )
    
    parser.add_argument(
        '--profile',
        default='StandardAccess-450410489798',
        help='AWS SSO profile name'
    )
    
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deployed without actual deployment'
    )
    
    args = parser.parse_args()
    
    # Create deployer
    deployer = AgentCoreDeployerToolkit(profile=args.profile, region=args.region, local=args.local)
    
    # Dry run: just show agent configurations
    if args.dry_run:
        logger.info("\n🔍 DRY RUN: Showing agent configurations")
        for agent_dir in deployer.agents_dir.iterdir():
            if agent_dir.is_dir():
                config_file = agent_dir / "agentcore.yaml"
                if config_file.exists():
                    logger.info(f"\n📋 Configuration: {agent_dir.name}")
                    with open(config_file, 'r') as f:
                        content = f.read()
                        logger.info(f"   First 300 chars: {content[:300]}...")
        return 0
    
    # Deploy all agents
    success = deployer.deploy_all()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
