#!/usr/bin/env python3
"""
MCP Tool Verification via CloudWatch Logs - Quick Check After Agent Invocation

This script monitors CloudWatch logs for MCP tool execution evidence.
Run this 30-60 seconds AFTER sending a request to the orchestrator agent.

The agent invocation can be triggered via:
1. AWS Console - Bedrock AgentCore Runtime
2. Lambda wrapper (see lambda_mcp_test_wrapper.py)
3. Dashboard - when integrated
4. curl commands (if you have AWS network access)
"""

import json
import boto3
import logging
from datetime import datetime, timedelta
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

session = boto3.Session(profile_name='StandardAccess-450410489798')
logs_client = session.client('logs', region_name='us-east-1')

# Log groups
DIAGNOSIS_AGENT_LOG = '/aws/bedrock-agentcore/runtimes/diagnosis_agent_runtime-r8AcIc5zbG-DEFAULT'

# MCP tool keywords indicating successful execution
MCP_SUCCESS_KEYWORDS = {
    'gateway_auth': ['access_token', 'Authenticating', 'authentication successful'],
    'tool_invocation': ['call_tool', 'calling_tool', 'invoke', 'GatewayClient'],
    'tool_names': ['get-spare-parts', 'schedule-maintenance', 'create-work-order'],
    'action_execution': ['Executing action', 'action taken', 'tool_results'],
}

def check_logs_for_mcp_evidence(minutes_back=5):
    """
    Check CloudWatch logs for MCP tool usage evidence.
    
    Args:
        minutes_back: How many minutes back to search (default 5 min)
    """
    
    print(f"\n{'='*80}")
    print("🔍 QUICK MCP TOOL VERIFICATION - CloudWatch Logs Check")
    print(f"{'='*80}")
    print(f"Checking logs from last {minutes_back} minutes...")
    print(f"Log Group: {DIAGNOSIS_AGENT_LOG}")
    
    try:
        # Get latest log stream
        streams_response = logs_client.describe_log_streams(
            logGroupName=DIAGNOSIS_AGENT_LOG,
            orderBy='LastEventTime',
            descending=True,
            limit=3
        )
        
        if not streams_response['logStreams']:
            print(f"\n⚠️  No log streams found")
            print(f"   Possible reasons:")
            print(f"   1. Agent hasn't been invoked yet")
            print(f"   2. No errors logged yet")
            return False
        
        # Calculate time window
        end_time = datetime.now().timestamp() * 1000
        start_time = (datetime.now() - timedelta(minutes=minutes_back)).timestamp() * 1000
        
        mcp_evidence = []
        total_lines = 0
        
        # Check each stream
        for stream in streams_response['logStreams']:
            stream_name = stream['logStreamName']
            
            try:
                events_response = logs_client.get_log_events(
                    logGroupName=DIAGNOSIS_AGENT_LOG,
                    logStreamName=stream_name,
                    startTime=int(start_time),
                    endTime=int(end_time),
                    limit=500
                )
                
                events = events_response.get('events', [])
                total_lines += len(events)
                
                # Check each event
                for event in events:
                    message = event['message'].lower()
                    timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                    
                    # Check for ANY MCP evidence
                    for category, keywords in MCP_SUCCESS_KEYWORDS.items():
                        for keyword in keywords:
                            if keyword.lower() in message:
                                mcp_evidence.append({
                                    'timestamp': timestamp.isoformat(),
                                    'category': category,
                                    'keyword': keyword,
                                    'message': event['message'][:200]
                                })
                                break  # Don't duplicate
            
            except Exception as e:
                logger.warning(f"Could not read stream {stream_name}: {e}")
        
        # Display results
        print(f"\n📊 Results:")
        print(f"   Total log lines analyzed: {total_lines}")
        print(f"   MCP evidence found: {len(mcp_evidence)}")
        
        if mcp_evidence:
            print(f"\n✅ SUCCESS - MCP Tool Evidence Detected!\n")
            
            # Group by category
            by_category = {}
            for evidence in mcp_evidence:
                cat = evidence['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(evidence)
            
            for category in ['gateway_auth', 'tool_invocation', 'tool_names', 'action_execution']:
                if category in by_category:
                    print(f"  📌 {category.upper().replace('_', ' ')}:")
                    for evidence in by_category[category][:3]:  # Show first 3
                        print(f"     • {evidence['keyword']}")
                        print(f"       Time: {evidence['timestamp']}")
                        print(f"       Log: {evidence['message']}")
            
            return True
        else:
            print(f"\n⚠️  No MCP Tool Evidence Yet\n")
            print(f"   This means:")
            print(f"   • Agent was invoked but didn't need to call tools (healthy device)")
            print(f"   • Agent encountered an error before reaching tool execution")
            print(f"   • Logs haven't been written yet (wait 10-15 more seconds)")
            print(f"\n   💡 Try again with:")
            print(f"      python3 quick_mcp_log_check.py")
            
            return False
    
    except Exception as e:
        logger.error(f"Error checking logs: {e}")
        return False


def show_next_steps():
    """Show what to do based on results."""
    
    print(f"\n{'='*80}")
    print("📋 NEXT STEPS")
    print(f"{'='*80}")
    
    print(f"""
✅ IF MCP Tools Were Found:
   1. ✓ MCP gateway authentication succeeded (Cognito)
   2. ✓ Agents can invoke Lambda functions via gateway
   3. ✓ MCP tool infrastructure is working!
   
   Next: Check dashboard for work orders / maintenance schedules

❓ IF No Evidence Yet:
   1. Ensure agent was invoked with anomalous device data
   2. Device must be in 'alert' or 'critical' health state
   3. Wait 30-60 seconds after invocation for logs to appear
   4. Re-run this script to check again
   
   Test device IDs with anomalies:
   • motor-004 (MOTOR, health_state='alert', degradation=0.312)
   • pump-004 (PUMP, health_state='critical', degradation=0.800)
   • compressor-003 (COMPRESSOR, health_state='alert', degradation=0.307)

🔧 TO TRIGGER AGENT INVOCATION:
   
   Option 1: Lambda Wrapper (Recommended)
   ──────────────────────────────────────
   python3 lambda_mcp_test_wrapper.py
   
   Option 2: AWS CLI (requires network access to AWS)
   ──────────────────────────────────────────────────
   See curl_commands_reference.md for examples
   
   Option 3: curl (requires AWS network access)
   ──────────────────────────────────────────────
   See: curl_commands_reference.md

📊 TO VERIFY COMPLETE FLOW:
   1. Invoke agent with anomalous device
   2. Wait 30 seconds
   3. Run: python3 quick_mcp_log_check.py
   4. Check for 'access_token', 'call_tool', tool names
   5. If found, MCP gateway is working! ✅
    """)


if __name__ == "__main__":
    print(f"""
╔════════════════════════════════════════════════════════════════════════════╗
║          QUICK MCP TOOL VERIFICATION                                      ║
║          (Run 30-60 sec AFTER invoking agent)                             ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Check for MCP evidence
    success = check_logs_for_mcp_evidence(minutes_back=5)
    
    # Show next steps
    show_next_steps()
    
    print(f"\n✅ Check complete at {datetime.now().isoformat()}")
