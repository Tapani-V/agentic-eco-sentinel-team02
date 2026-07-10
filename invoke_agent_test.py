#!/usr/bin/env python3
"""
Test script to invoke the orchestrator agent and monitor MCP tool execution.
"""

import json
import boto3
import requests
import time
import threading
from datetime import datetime
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load endpoints
with open('agent_endpoints.json', 'r') as f:
    endpoints = json.load(f)

orchestrator_endpoint = endpoints['agents']['orchestrator']

# Create session with AWS profile
session = boto3.Session(profile_name='StandardAccess-450410489798')

# Test request
test_request = {
    "device_id": "COMPRESSOR_UNIT_42",
    "equipment_type": "Air_Compressor",
    "current_reading": 78.5,
    "timestamp": datetime.now().isoformat(),
    "query": "Perform health analysis and diagnostics for this compressor unit"
}

print("\n" + "="*80)
print("AGENT INVOCATION TEST - MCP TOOL EXECUTION MONITORING")
print("="*80)
print(f"Timestamp: {datetime.now().isoformat()}")
print(f"Orchestrator Endpoint: {orchestrator_endpoint}")
print(f"\nTest Request:")
print(json.dumps(test_request, indent=2))
print("="*80 + "\n")

# Monitor CloudWatch logs
def monitor_logs(duration_seconds=60):
    """Monitor CloudWatch logs for MCP tool invocations"""
    logs_client = session.client('logs', region_name='us-east-1')
    log_group = '/aws/bedrock-agentcore/runtimes/orchestrator_runtime-6UF3HDGyvL-DEFAULT'
    
    start_time = int(time.time() * 1000) - 5000  # Start 5 seconds ago
    end_time = start_time + (duration_seconds * 1000)
    
    logger.info(f"Monitoring logs from {log_group} for {duration_seconds} seconds...")
    
    try:
        # Get log streams
        streams_resp = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=5
        )
        
        if not streams_resp['logStreams']:
            logger.warning("No log streams found")
            return
        
        # Get events from all streams
        all_events = []
        for stream in streams_resp['logStreams']:
            try:
                events_resp = logs_client.get_log_events(
                    logGroupName=log_group,
                    logStreamName=stream['logStreamName'],
                    startTime=start_time,
                    endTime=end_time
                )
                all_events.extend(events_resp.get('events', []))
            except Exception as e:
                logger.warning(f"Could not read stream {stream['logStreamName']}: {e}")
        
        # Sort by timestamp
        all_events.sort(key=lambda x: x['timestamp'])
        
        if all_events:
            print("\n" + "="*80)
            print("📋 CLOUDWATCH LOGS - MCP TOOL EXECUTION")
            print("="*80)
            for event in all_events:
                timestamp = datetime.fromtimestamp(event['timestamp'] / 1000).isoformat()
                message = event['message']
                
                # Highlight MCP tool-related messages
                if any(keyword in message.lower() for keyword in 
                       ['mcp', 'tool', 'invoke', 'response', 'health', 'diagnosis', 'device', 'equipment']):
                    print(f"✓ [{timestamp}]")
                    print(f"  {message}\n")
                elif any(keyword in message.lower() for keyword in ['error', 'exception', 'traceback']):
                    print(f"✗ [{timestamp}] ERROR")
                    print(f"  {message}\n")
            print("="*80 + "\n")
        else:
            logger.info("No new log events found in monitoring period")
    
    except Exception as e:
        logger.error(f"Error monitoring logs: {e}")

# Start log monitoring in background
log_monitor = threading.Thread(target=monitor_logs, args=(30,), daemon=True)
log_monitor.start()

# Invoke the agent
print("🚀 INVOKING ORCHESTRATOR AGENT...\n")

try:
    # Get credentials
    credentials = session.get_credentials()
    
    # Prepare the request
    request_url = f"{orchestrator_endpoint}/invoke"
    
    # Create AWS request
    request = AWSRequest(
        method='POST',
        url=request_url,
        data=json.dumps(test_request),
        headers={'Content-Type': 'application/json'}
    )
    
    # Sign the request with SigV4
    SigV4Auth(credentials, 'bedrock-agentruntime', 'us-east-1').add_auth(request)
    
    logger.info(f"Sending signed POST request to {request_url}")
    
    # Make the request
    response = requests.post(
        request_url,
        headers=dict(request.headers),
        data=json.dumps(test_request),
        timeout=45
    )
    
    logger.info(f"Response Status: {response.status_code}")
    
    if response.status_code in [200, 202]:
        print("✅ AGENT INVOCATION SUCCESSFUL!\n")
        try:
            result = response.json()
            print("Response:")
            print(json.dumps(result, indent=2))
        except:
            print("Response (raw):")
            print(response.text)
    elif response.status_code == 401:
        print("❌ Authentication Error - Check AWS credentials")
        print(response.text)
    elif response.status_code == 404:
        print("❌ Endpoint Not Found - Agent may not be deployed")
        print(response.text)
    else:
        print(f"❌ Error {response.status_code}")
        print(response.text)
    
    # Wait for logs to be processed
    print("\n⏳ Waiting for CloudWatch logs to update...\n")
    time.sleep(5)
    
except Exception as e:
    print(f"❌ Error invoking agent: {e}")
    import traceback
    traceback.print_exc()

# Allow time for log monitoring to complete
time.sleep(10)

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
print("\n💡 INTERPRETATION:")
print("   - If you see 'mcp' or 'tool' messages → MCP tools were invoked ✓")
print("   - If you see device/equipment data → Tools received and processed input ✓")
print("   - If you see analysis/diagnostics results → Tools executed successfully ✓")
print("\n" + "="*80)
