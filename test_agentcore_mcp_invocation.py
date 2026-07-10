#!/usr/bin/env python3
"""
Test Script: Invoke Agents on AWS AgentCore Runtime with Anomalous Device Data

This script sends device data with anomalies to the orchestrator agent,
which should trigger diagnosis and MCP tool usage (work order creation, etc.)

Usage:
    python3 test_agentcore_mcp_invocation.py
"""

import json
import boto3
import logging
from pathlib import Path
from datetime import datetime
import time
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize AWS clients
session = boto3.Session(profile_name='StandardAccess-450410489798')
credentials = session.get_credentials()

# Agent endpoints
ORCHESTRATOR_ENDPOINT = "https://agentcore-runtime.us-east-1.amazonaws.com/runtimes/orchestrator_runtime-6UF3HDGyvL"

def load_device_data(device_file):
    """Load device data from generated files."""
    file_path = Path('data/generated') / device_file
    
    if not file_path.exists():
        logger.error(f"Device file not found: {file_path}")
        return None
    
    with open(file_path) as f:
        readings = json.load(f)
    
    if not readings:
        logger.error(f"No readings found in {file_path}")
        return None
    
    # Return the first reading
    return readings[0]


def prepare_agent_request(device_reading):
    """Prepare request for orchestrator agent."""
    
    request = {
        "device_id": device_reading['device_id'],
        "equipment_type": device_reading['equipment_type'],
        "current_reading": {
            "readings": device_reading['readings']
        }
    }
    
    return request


def invoke_orchestrator_agent(device_request):
    """Invoke orchestrator agent with device data via HTTP."""
    
    logger.info(f"\n{'='*80}")
    logger.info(f"📤 Invoking Orchestrator Agent")
    logger.info(f"{'='*80}")
    logger.info(f"Device: {device_request['device_id']} ({device_request['equipment_type']})")
    logger.info(f"Endpoint: {ORCHESTRATOR_ENDPOINT}")
    logger.info(f"Request payload: {json.dumps(device_request, indent=2)[:500]}...")
    
    try:
        # Prepare signed request
        url = f"{ORCHESTRATOR_ENDPOINT}/process"
        
        # Create AWS signed request
        request = AWSRequest(
            method='POST',
            url=url,
            data=json.dumps(device_request),
            headers={'Content-Type': 'application/json'}
        )
        
        # Sign the request with SigV4
        SigV4Auth(credentials, 'agentcore', 'us-east-1').add_auth(request)
        
        # Send the signed request
        response = requests.post(
            url,
            data=request.body,
            headers=dict(request.headers),
            timeout=120  # Long timeout for agent processing
        )
        
        logger.info(f"\n✅ Agent invocation successful!")
        logger.info(f"Response status: {response.status_code}")
        
        try:
            result = response.json()
            logger.info(f"\n📥 Agent Response:")
            logger.info(json.dumps(result, indent=2)[:1500])
            
            # Check for MCP tool usage indicators
            if 'mcp_tools_used' in result and result['mcp_tools_used']:
                logger.info(f"\n🎯 MCP TOOLS USED: {result['mcp_tools_used']}")
            if 'action_taken' in result and result['action_taken']:
                logger.info(f"✅ Action taken: {result['action_taken']}")
            
            return result
        except json.JSONDecodeError:
            logger.info(f"\n📥 Response (text): {response.text[:500]}")
            return {"raw_response": response.text}
    
    except requests.exceptions.RequestException as e:
        logger.error(f"\n❌ Error invoking agent: {e}")
        return None
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        return None


def test_anomalous_devices():
    """Test agents with devices that have anomalies."""
    
    # Devices with anomalies that should trigger MCP tools
    test_devices = [
        'motor-004.json',      # Alert: high current, high temp, high vibration
        'pump-004.json',       # Check if has anomalies
        'compressor-003.json', # Check if has anomalies
    ]
    
    results = []
    
    for device_file in test_devices:
        logger.info(f"\n\n{'='*80}")
        logger.info(f"🔍 Testing device: {device_file}")
        logger.info(f"{'='*80}")
        
        # Load device data
        device_reading = load_device_data(device_file)
        if not device_reading:
            continue
        
        logger.info(f"Device health state: {device_reading['health_state']}")
        logger.info(f"Degradation score: {device_reading['degradation_score']:.3f}")
        
        # Prepare request
        request = prepare_agent_request(device_reading)
        
        # Invoke agent
        result = invoke_orchestrator_agent(request)
        
        if result:
            results.append({
                'device': device_file,
                'device_id': device_reading['device_id'],
                'health_state': device_reading['health_state'],
                'degradation_score': device_reading['degradation_score'],
                'result': result
            })
        
        # Wait between invocations
        time.sleep(2)
    
    return results


def display_summary(results):
    """Display summary of test results."""
    
    logger.info(f"\n\n{'='*80}")
    logger.info("📊 TEST SUMMARY")
    logger.info(f"{'='*80}")
    
    if not results:
        logger.info("❌ No successful invocations")
        return
    
    logger.info(f"Total devices tested: {len(results)}")
    
    mcp_tool_usage = 0
    for result in results:
        logger.info(f"\n✓ {result['device']}")
        logger.info(f"  Device ID: {result['device_id']}")
        logger.info(f"  Health State: {result['health_state']}")
        logger.info(f"  Degradation: {result['degradation_score']:.3f}")
        
        if 'mcp_tools_used' in result['result']:
            tools = result['result']['mcp_tools_used']
            if tools:
                logger.info(f"  🎯 MCP Tools: {tools}")
                mcp_tool_usage += 1
        
        if 'action_taken' in result['result']:
            logger.info(f"  ✅ Action: {result['result']['action_taken']}")
    
    logger.info(f"\n\n📈 MCP Tool Usage: {mcp_tool_usage}/{len(results)} devices")
    
    logger.info(f"""
✅ Next Steps:
   1. Wait 10-15 seconds for logs to appear
   2. Run: python3 verify_mcp_gateway_access.py
   3. Look for MCP tool keywords in logs:
      - "GatewayClient"
      - "call_tool"
      - "get-spare-parts", "schedule-maintenance", "create-work-order"
      - "access_token" (Cognito auth success)
    """)


if __name__ == "__main__":
    logger.info(f"""
╔════════════════════════════════════════════════════════════════════════════╗
║         MCP TOOL INVOCATION TEST - AgentCore Runtime                      ║
╚════════════════════════════════════════════════════════════════════════════╝
""")
    
    # Test with anomalous devices
    results = test_anomalous_devices()
    
    # Display summary
    display_summary(results)
    
    logger.info(f"\n✅ Test completed at {datetime.now().isoformat()}")
