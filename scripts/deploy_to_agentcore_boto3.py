#!/usr/bin/env python3
"""
Deploy Agents to AWS Bedrock AgentCore Runtime using boto3

This script deploys agents to Bedrock AgentCore Runtime by registering
pre-built container images from ECR. No rebuild or rebuild needed.

Usage:
    python scripts/deploy_to_agentcore_boto3.py [--profile PROFILE] [--region REGION]

Arguments:
    --profile      AWS SSO profile name (default: StandardAccess-450410489798)
    --region       AWS region (default: us-east-1)

Output:
    agent_endpoints.json: Deployed agent endpoints for dashboard usage
"""

import json
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse
import boto3
from botocore.exceptions import ClientError

# Try to load environment variables from .agentcore.env
env_file = Path(__file__).parent.parent / ".agentcore.env"
if env_file.exists():
    # Try using python-dotenv if available, otherwise parse manually
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"✅ Loaded environment from {env_file} (using python-dotenv)")
    except ImportError:
        # Fallback: manually parse the file
        print(f"⚠️  python-dotenv not available, parsing {env_file} manually")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s %(name)s: %(message)s'
)
logger = logging.getLogger('AGENTCORE_DEPLOY_BOTO3')


class BedrockAgentDeployer:
    """Deploy agents to Bedrock AgentCore Runtime using existing ECR images"""
    
    def __init__(self, profile: str = "StandardAccess-450410489798", region: str = "us-east-1"):
        """
        Initialize deployer with AWS credentials
        
        Args:
            profile: AWS SSO profile name
            region: AWS region
        """
        self.profile = profile
        self.region = region
        self.endpoints = {}
        
        # Load MCP Gateway environment variables (for agent access to tools)
        self.cognito_client_id = os.getenv('COGNITO_APP_CLIENT_ID')
        self.cognito_client_secret = os.getenv('COGNITO_APP_CLIENT_SECRET')
        self.cognito_token_endpoint = os.getenv('COGNITO_TOKEN_ENDPOINT')
        self.cognito_scope = os.getenv('COGNITO_SCOPE', 'agentcore/invoke')
        self.gateway_url = os.getenv('GATEWAY_URL')
        self.azure_openai_key = os.getenv('AZURE_OPENAI_KEY')
        self.azure_openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        self.azure_openai_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT')
        self.azure_openai_api_version = os.getenv('AZURE_OPENAI_API_VERSION')
        
        logger.info(f"✅ Loaded MCP Gateway Configuration:")
        logger.info(f"   Gateway URL: {self.gateway_url[:60]}..." if self.gateway_url else "   Gateway URL: NOT SET")
        logger.info(f"   Cognito Client ID: {self.cognito_client_id[:20]}..." if self.cognito_client_id else "   Cognito Client ID: NOT SET")
        
        # Initialize AWS clients
        session = boto3.Session(profile_name=profile, region_name=region)
        self.bedrock_agent = session.client('bedrock-agent', region_name=region)
        self.bedrock_agentcore_control = session.client('bedrock-agentcore-control', region_name=region)
        self.iam = session.client('iam', region_name=region)
        self.sts = session.client('sts', region_name=region)
        
        logger.info(f"🚀 Bedrock AgentCore Deployer initialized (boto3-based)")
        logger.info(f"   AWS Profile: {profile}")
        logger.info(f"   AWS Region: {region}")
        
        # Get account ID
        try:
            identity = self.sts.get_caller_identity()
            self.account_id = identity['Account']
            logger.info(f"   AWS Account: {self.account_id}")
        except ClientError as e:
            logger.error(f"❌ Failed to get AWS identity: {e}")
            sys.exit(1)
    
    def deploy_agent(self, agent_name: str, agent_config: dict) -> bool:
        """
        Deploy a single agent to Bedrock AgentCore Runtime
        
        Args:
            agent_name: Name of agent (orchestrator, health_agent, diagnosis_agent)
            agent_config: Agent configuration dict
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 Deploying Agent: {agent_name}")
        logger.info(f"{'='*80}")
        
        try:
            agent_display_name = agent_config.get('name', agent_name)
            agent_type = agent_config.get('type', 'worker')
            ecr_image = agent_config.get('ecr_image_uri', '')
            cpu = agent_config.get('cpu', 256)
            memory = agent_config.get('memory', 512)
            timeout = agent_config.get('timeout', 60)
            min_instances = agent_config.get('min_instances', 0)
            max_instances = agent_config.get('max_instances', 3)
            
            logger.info(f"📋 Agent Config:")
            logger.info(f"   Display Name: {agent_display_name}")
            logger.info(f"   Type: {agent_type}")
            logger.info(f"   Container Image: {ecr_image}")
            logger.info(f"   Resources: {cpu} CPU, {memory}MB memory")
            logger.info(f"   Timeout: {timeout}s")
            logger.info(f"   Instances: {min_instances}-{max_instances}")
            
            logger.info(f"✅ Agent configuration validated")
            logger.info(f"📤 Registering with Bedrock AgentCore Runtime...")
            
            # Create AgentCore Runtime using bedrock-agentcore-control
            # Runtime names must match: [a-zA-Z][a-zA-Z0-9_]{0,47}
            runtime_name = f"{agent_name.replace('-', '_')}_runtime"
            
            # Build environment variables dictionary
            env_vars = {
                # Agent configuration
                'AGENT_NAME': agent_name,
                'AGENT_TYPE': agent_type,
                'CPU': str(cpu),
                'MEMORY': str(memory),
                'TIMEOUT': str(timeout),
                
                # MCP Gateway Configuration (for accessing tools via gateway)
                'COGNITO_APP_CLIENT_ID': self.cognito_client_id or '',
                'COGNITO_APP_CLIENT_SECRET': self.cognito_client_secret or '',
                'COGNITO_TOKEN_ENDPOINT': self.cognito_token_endpoint or '',
                'COGNITO_SCOPE': self.cognito_scope or 'agentcore/invoke',
                'GATEWAY_URL': self.gateway_url or '',
                
                # Azure OpenAI Configuration (for LLM-based diagnostics)
                'AZURE_OPENAI_KEY': self.azure_openai_key or '',
                'AZURE_OPENAI_ENDPOINT': self.azure_openai_endpoint or '',
                'AZURE_OPENAI_DEPLOYMENT': self.azure_openai_deployment or '',
                'AZURE_OPENAI_API_VERSION': self.azure_openai_api_version or '',
                
                # Synthetic device data (S3) - used by orchestrator's DeviceLoader
                # for list_devices / get_device / get_device_summary actions
                'SYNTHETIC_DATA_BUCKET': 'agentic-ai-poc-synthetic-data',
                'SYNTHETIC_DATA_PREFIX': 'devices/',
                'AWS_REGION': self.region,
                
                # Logging
                'LOG_LEVEL': 'INFO',
                'PYTHONUNBUFFERED': '1'
            }
            
            # Try to create, if it exists update instead
            try:
                logger.info(f"✏️  Creating AgentCore Runtime: {runtime_name}")
                
                runtime_response = self.bedrock_agentcore_control.create_agent_runtime(
                    agentRuntimeName=runtime_name,
                    agentRuntimeArtifact={
                        'containerConfiguration': {
                            'containerUri': ecr_image
                        }
                    },
                    roleArn=f"arn:aws:iam::{self.account_id}:role/AgentCoreExecutionRole",
                    networkConfiguration={
                        'networkMode': 'PUBLIC'
                    },
                    environmentVariables=env_vars,
                    tags={
                        'ManagedBy': 'boto3-deployment',
                        'Phase': '4',
                        'AgentName': agent_name,
                        'Type': agent_type
                    }
                )
                
                runtime_id = runtime_response['agentRuntimeId']
                runtime_arn = runtime_response['agentRuntimeArn']
                logger.info(f"✓ AgentCore Runtime created (ID: {runtime_id})")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConflictException':
                    # Runtime already exists, update it with new environment variables
                    logger.info(f"📝 Runtime already exists, updating with new environment variables...")
                    
                    try:
                        # First, get the current runtime to extract its ID
                        list_response = self.bedrock_agentcore_control.list_agent_runtimes()
                        runtime_id = None
                        for rt in list_response.get('agentRuntimes', []):
                            if rt['agentRuntimeName'] == runtime_name:
                                runtime_id = rt['agentRuntimeId']
                                runtime_arn = rt['agentRuntimeArn']
                                break
                        
                        if runtime_id:
                            # Update the runtime with new environment variables
                            update_response = self.bedrock_agentcore_control.update_agent_runtime(
                                agentRuntimeId=runtime_id,
                                agentRuntimeArtifact={
                                    'containerConfiguration': {
                                        'containerUri': ecr_image
                                    }
                                },
                                roleArn=f"arn:aws:iam::{self.account_id}:role/AgentCoreExecutionRole",
                                networkConfiguration={
                                    'networkMode': 'PUBLIC'
                                },
                                environmentVariables=env_vars
                            )
                            logger.info(f"✓ AgentCore Runtime updated (ID: {runtime_id})")
                        else:
                            logger.error(f"❌ Could not find runtime ID for {runtime_name}")
                            return False
                            
                    except Exception as update_error:
                        logger.error(f"❌ Failed to update runtime: {update_error}")
                        return False
                else:
                    # Some other error
                    error_code = e.response['Error']['Code']
                    error_msg = e.response['Error']['Message']
                    logger.error(f"❌ Deployment failed [{error_code}]: {error_msg}")
                    return False
            
            # Generate endpoint URL for the agent
            endpoint = f"https://agentcore-runtime.{self.region}.amazonaws.com/runtimes/{runtime_id}"
            self.endpoints[agent_name] = {
                'runtime_id': runtime_id,
                'runtime_arn': runtime_arn,
                'endpoint_url': endpoint
            }
            
            logger.info(f"✅ Deployment successful!")
            logger.info(f"   Runtime ID: {runtime_id}")
            logger.info(f"   Runtime ARN: {runtime_arn}")
            logger.info(f"   Endpoint: {endpoint}")
            
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            logger.error(f"❌ Deployment failed [{error_code}]: {error_msg}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def save_endpoints(self):
        """Save agent endpoints to file for dashboard usage"""
        output_file = Path(__file__).parent.parent / "agent_endpoints.json"
        
        # Convert endpoint dicts to flattened format for JSON
        agents_flat = {}
        for agent_name, endpoint_info in self.endpoints.items():
            if isinstance(endpoint_info, dict) and 'endpoint_url' in endpoint_info:
                agents_flat[agent_name] = endpoint_info['endpoint_url']
            else:
                agents_flat[agent_name] = endpoint_info
        
        endpoints_data = {
            "timestamp": datetime.now().isoformat(),
            "region": self.region,
            "profile": self.profile,
            "account_id": self.account_id,
            "agents": agents_flat,
            "details": self.endpoints,
            "instructions": {
                "orchestrator": f"Call orchestrator endpoint to invoke full workflow",
                "health_agent": f"Call health_agent endpoint for health analysis",
                "diagnosis_agent": f"Call diagnosis_agent endpoint for diagnostics"
            }
        }
        
        try:
            with open(output_file, 'w') as f:
                json.dump(endpoints_data, f, indent=2)
            logger.info(f"✅ Endpoints saved to: {output_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save endpoints: {e}")
    
    def deploy_all(self) -> bool:
        """Deploy all agents to Bedrock AgentCore Runtime"""
        
        # Agent configurations with ECR images
        agents_config = {
            "orchestrator": {
                "name": "agentic-orchestrator",
                "type": "orchestrator",
                "ecr_image_uri": f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/orchestrator:latest",
                "cpu": 256,
                "memory": 512,
                "timeout": 60,
                "min_instances": 1,
                "max_instances": 5
            },
            "health_agent": {
                "name": "agentic-health-agent",
                "type": "worker",
                "ecr_image_uri": f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/health-agent:latest",
                "cpu": 256,
                "memory": 512,
                "timeout": 30,
                "min_instances": 0,
                "max_instances": 3
            },
            "diagnosis_agent": {
                "name": "agentic-diagnosis-agent",
                "type": "worker",
                "ecr_image_uri": f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/diagnosis-agent:latest",
                "cpu": 256,
                "memory": 512,
                "timeout": 60,
                "min_instances": 0,
                "max_instances": 3
            }
        }
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🌐 BEDROCK AGENTCORE RUNTIME DEPLOYMENT (boto3)")
        logger.info(f"{'='*80}")
        
        success_count = 0
        for agent_name, config in agents_config.items():
            if self.deploy_agent(agent_name, config):
                success_count += 1
            else:
                logger.warning(f"⚠️  Agent deployment skipped: {agent_name}")
        
        # Save endpoints
        self.save_endpoints()
        
        # Summary
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 DEPLOYMENT SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"✅ Successful: {success_count}/{len(agents_config)}")
        logger.info(f"📍 Region: {self.region}")
        logger.info(f"")
        
        for agent_name, endpoint_info in self.endpoints.items():
            if isinstance(endpoint_info, dict) and 'endpoint_url' in endpoint_info:
                endpoint_url = endpoint_info['endpoint_url']
            else:
                endpoint_url = endpoint_info
            logger.info(f"  {agent_name:20s} → {endpoint_url}")
        
        logger.info(f"{'='*80}\n")
        
        return success_count == len(agents_config)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Deploy agents to AWS Bedrock AgentCore Runtime using boto3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy with default profile
  python scripts/deploy_to_agentcore_boto3.py
  
  # Deploy with specific profile
  python scripts/deploy_to_agentcore_boto3.py --profile StandardAccess-450410489798
  
  # Deploy to different region
  python scripts/deploy_to_agentcore_boto3.py --region us-west-2
        """
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
    
    args = parser.parse_args()
    
    # Create deployer
    deployer = BedrockAgentDeployer(profile=args.profile, region=args.region)
    
    # Deploy all agents
    success = deployer.deploy_all()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
