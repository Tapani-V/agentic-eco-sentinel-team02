#!/usr/bin/env python3
"""
Test script to invoke the orchestrator agent and verify MCP tool responses.
"""

import json
import boto3
import logging
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import requests
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load endpoints
with open('agent_endpoints.json', 'r') as f:
    endpoints = json.load(f)

orchestrator_endpoint = endpoints['agents']['orchestrator']
logger.info(f"Testing orchestrator endpoint: {orchestrator_endpoint}")

# Create session with AWS profile
session = boto3.Session(profile_name='StandardAccess-450410489798')

# Create Bedrock AgentCore client
client = session.client(
    'bedrock-agentcore-control',
    region_name='us-east-1'
)

# Test message
test_request = {
    "device_id": "DEVICE_TEST_001",
    "equipment_type": "Compressor",
    "current_reading": 75.5,
    "query": "Analyze the compressor performance"
}

print("\n" + "="*70)
print("AGENT WORKFLOW TEST")
print("="*70)
print(f"Timestamp: {datetime.now().isoformat()}")
print(f"Orchestrator Endpoint: {orchestrator_endpoint}")
print(f"Test Request: {json.dumps(test_request, indent=2)}")
print("="*70 + "\n")

try:
    # List agent runtimes to verify they're running
    logger.info("Step 1: Checking agent status...")
    response = client.list_agent_runtimes()
    
    our_agents = {
        'orchestrator': None,
        'health_agent': None,
        'diagnosis_agent': None
    }
    
    for agent in response.get('agentRuntimes', []):
        for agent_type in our_agents.keys():
            if agent_type in agent['agentRuntimeName']:
                our_agents[agent_type] = {
                    'name': agent['agentRuntimeName'],
                    'status': agent['status'],
                    'id': agent['agentRuntimeId'],
                    'lastUpdated': agent['lastUpdatedAt']
                }
    
    print("✅ Agent Status:")
    for agent_type, info in our_agents.items():
        if info:
            print(f"   {agent_type:20} → {info['status']} (ID: {info['id']})")
    print()
    
    # Check if orchestrator is ready
    if our_agents['orchestrator'] and our_agents['orchestrator']['status'] == 'READY':
        logger.info("✅ Orchestrator is READY")
    else:
        logger.warning("⚠️  Orchestrator is NOT ready")
    
    # Check CloudWatch logs for execution details
    logger.info("\nStep 2: Checking CloudWatch logs for MCP tool invocations...")
    logs_client = session.client('logs', region_name='us-east-1')
    
    # Get log streams for orchestrator
    log_group = '/aws/bedrock-agentcore/runtimes/orchestrator_runtime-6UF3HDGyvL-DEFAULT'
    
    try:
        streams = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )
        
        if streams['logStreams']:
            latest_stream = streams['logStreams'][0]
            print(f"\n📋 Latest Log Stream: {latest_stream['logStreamName']}")
            print(f"   Last Event: {datetime.fromtimestamp(latest_stream['lastEventTimestamp']/1000).isoformat()}")
            
            # Get recent log events
            events = logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=latest_stream['logStreamName'],
                limit=20
            )
            
            if events['events']:
                print(f"\n📝 Recent Log Events (last 20):")
                for event in events['events']:
                    print(f"   {event['message']}")
    except Exception as e:
        logger.warning(f"Could not read logs: {e}")
    
except Exception as e:
    logger.error(f"Error during test: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
