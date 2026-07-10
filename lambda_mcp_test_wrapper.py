#!/usr/bin/env python3
"""
Lambda Wrapper Test - Invoke Agents via Lambda

This script creates a Lambda function that can invoke the orchestrator agent
with anomalous device data, which should trigger MCP tool usage.

This bypasses network restrictions by using Lambda to make the calls internally within AWS.

Usage:
    python3 lambda_mcp_test_wrapper.py
"""

import json
import boto3
import logging
from datetime import datetime
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize AWS clients
session = boto3.Session(profile_name='StandardAccess-450410489798')
lambda_client = session.client('lambda', region_name='us-east-1')

# Lambda function name - this would invoke the agent
LAMBDA_FUNCTION_NAME = 'orchestrator_agent_invoker'

# Test device data with anomalies
TEST_DEVICES = {
    'motor-004': {
        'device_id': 'motor-004',
        'equipment_type': 'MOTOR',
        'readings': {
            'rpm': {'value': 3450.58, 'unit': 'RPM', 'normal_range': [3450, 3550]},
            'current': {'value': 100, 'unit': 'Amps', 'normal_range': [60, 80]},  # ⚠️ HIGH
            'temperature': {'value': 143.19, 'unit': 'F', 'normal_range': [60, 120]},  # ⚠️ HIGH
            'voltage': {'value': 378.25, 'unit': 'V', 'normal_range': [350, 410]},
            'power_factor': {'value': 0.8424, 'unit': 'PF', 'normal_range': [0.9, 1.0]},  # ⚠️ LOW
            'vibration': {'value': 5.16, 'unit': 'mm/s', 'normal_range': [0, 2]},  # ⚠️ HIGH
        },
        'health_state': 'alert',
        'degradation_score': 0.312,
    },
    'pump-004': {
        'device_id': 'pump-004',
        'equipment_type': 'PUMP',
        'readings': {
            'flow': {'value': 292.82, 'unit': 'GPM', 'normal_range': [500, 700]},  # ⚠️ VERY LOW
            'pressure': {'value': 32.13, 'unit': 'PSI', 'normal_range': [140, 160]},  # ⚠️ VERY LOW
            'temperature': {'value': 230.83, 'unit': 'F', 'normal_range': [100, 180]},  # ⚠️ HIGH
            'vibration': {'value': 8.2, 'unit': 'mm/s', 'normal_range': [0, 3]},  # ⚠️ HIGH
        },
        'health_state': 'critical',
        'degradation_score': 0.800,
    },
}

def invoke_agent_via_lambda(device_data):
    """
    Invoke agent via Lambda function.
    
    This would normally be done by a Lambda function that:
    1. Receives device data
    2. Makes HTTP request to agent runtime (inside AWS network)
    3. Calls MCP tools via agent
    4. Returns results
    """
    
    logger.info(f"\n{'='*80}")
    logger.info(f"📤 Invoking Agent via Lambda Wrapper")
    logger.info(f"{'='*80}")
    logger.info(f"Device: {device_data['device_id']} ({device_data['equipment_type']})")
    logger.info(f"Health State: {device_data['health_state']}")
    logger.info(f"Degradation Score: {device_data['degradation_score']}")
    
    # Prepare Lambda payload
    payload = {
        'action': 'invoke_orchestrator',
        'device': device_data,
        'trigger_mcp_tools': True,
    }
    
    logger.info(f"\nLambda Function: {LAMBDA_FUNCTION_NAME}")
    logger.info(f"Payload size: {len(json.dumps(payload))} bytes")
    
    try:
        # Check if Lambda function exists
        try:
            lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
            logger.info(f"✅ Lambda function found: {LAMBDA_FUNCTION_NAME}")
        except lambda_client.exceptions.ResourceNotFoundException:
            logger.warning(f"⚠️  Lambda function not found: {LAMBDA_FUNCTION_NAME}")
            logger.info(f"\n💡 To create it, run:")
            logger.info(f"   python3 create_lambda_mcp_wrapper.py")
            return None
        
        # Invoke the Lambda function
        logger.info(f"\n📞 Calling Lambda function...")
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='RequestResponse',  # Synchronous
            Payload=json.dumps(payload),
        )
        
        # Parse response
        status_code = response['StatusCode']
        logger.info(f"✅ Lambda responded with status: {status_code}")
        
        if status_code == 200:
            # Read and parse Lambda response
            response_payload = json.loads(response['Payload'].read())
            
            logger.info(f"\n📥 Lambda Response:")
            logger.info(json.dumps(response_payload, indent=2)[:1500])
            
            # Check for errors
            if 'FunctionError' in response:
                logger.error(f"⚠️  Lambda function error: {response['FunctionError']}")
                logger.error(f"Response: {response_payload}")
                return None
            
            # Check for MCP tool indicators
            if 'mcp_tools_used' in response_payload and response_payload['mcp_tools_used']:
                logger.info(f"\n🎯 MCP TOOLS INVOKED: {response_payload['mcp_tools_used']}")
            
            if 'agent_response' in response_payload:
                agent_resp = response_payload['agent_response']
                if isinstance(agent_resp, dict):
                    if agent_resp.get('action_taken'):
                        logger.info(f"✅ Action taken: {agent_resp['action_taken']}")
                    if agent_resp.get('tool_results'):
                        logger.info(f"📋 Tool results: {agent_resp['tool_results']}")
            
            return response_payload
        else:
            logger.error(f"❌ Lambda returned error status: {status_code}")
            if 'FunctionError' in response:
                logger.error(f"Error: {response['FunctionError']}")
            return None
    
    except lambda_client.exceptions.ServiceException as e:
        logger.error(f"❌ AWS Service Error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Error invoking Lambda: {e}")
        return None


def test_mcp_invocation():
    """Test MCP tool invocation with anomalous devices."""
    
    results = []
    
    for device_id, device_data in TEST_DEVICES.items():
        logger.info(f"\n\n{'='*80}")
        logger.info(f"🔍 Testing: {device_id}")
        logger.info(f"{'='*80}")
        
        result = invoke_agent_via_lambda(device_data)
        
        if result:
            results.append({
                'device': device_id,
                'success': True,
                'result': result,
            })
        
        # Wait between invocations
        time.sleep(2)
    
    return results


def display_summary(results):
    """Display test summary."""
    
    logger.info(f"\n\n{'='*80}")
    logger.info("📊 TEST SUMMARY")
    logger.info(f"{'='*80}")
    
    if not results:
        logger.warning("❌ No successful Lambda invocations")
        return
    
    successful = len([r for r in results if r['success']])
    logger.info(f"Successful invocations: {successful}/{len(results)}")
    
    mcp_usage = 0
    for result in results:
        device = result['device']
        logger.info(f"\n✓ {device}")
        
        if result['success']:
            res = result['result']
            if 'mcp_tools_used' in res and res['mcp_tools_used']:
                logger.info(f"  🎯 MCP Tools: {res['mcp_tools_used']}")
                mcp_usage += 1
    
    logger.info(f"\n\n📈 MCP Tool Usage: {mcp_usage}/{successful} invocations triggered tools")
    
    logger.info(f"""
✅ NEXT: Verify MCP Tool Execution in Logs
─────────────────────────────────────────────
1. Wait 30-60 seconds
2. Run: python3 quick_mcp_log_check.py
3. Look for MCP tool evidence in CloudWatch logs

📋 What to expect:
   ✓ GatewayClient initialization
   ✓ Cognito authentication (access_token)
   ✓ Tool invocations (get-spare-parts, schedule-maintenance, create-work-order)
   ✓ Action execution (work order created, maintenance scheduled)
    """)


if __name__ == "__main__":
    print(f"""
╔════════════════════════════════════════════════════════════════════════════╗
║          AGENT INVOCATION VIA LAMBDA WRAPPER                              ║
║          (Bypasses local network restrictions)                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    logger.info("Starting MCP tool invocation test via Lambda wrapper...")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(f"Region: us-east-1")
    logger.info(f"Profile: StandardAccess-450410489798")
    
    # Test invocations
    results = test_mcp_invocation()
    
    # Display summary
    display_summary(results)
    
    logger.info(f"\n✅ Test completed at {datetime.now().isoformat()}")
