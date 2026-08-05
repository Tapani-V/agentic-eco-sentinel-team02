"""
AgentCore Runtime Handler for OrchestratorAgent

This is the entry point that AgentCore Runtime invokes directly.
It orchestrates calls to HealthAgent and DiagnosisAgent via boto3.invoke_agent_runtime().

This is what Lambda will call via boto3.invoke_agent_runtime().

Supported invocation payloads (dispatched via the optional "action" field):
- {"device_id", "equipment_type", "current_reading"}  (no "action", or action="analyze")
    Analyze a device using the supplied reading (existing/default behavior).
- {"action": "list_devices"}
    List all available device IDs (from S3 synthetic data bucket).
- {"action": "get_device", "device_id": "..."}
    Load the device's latest raw reading from S3 and run the full analysis
    workflow on it (mirrors the old local GET /devices/{device_id} route).
- {"action": "get_device_summary", "device_id": "..."}
    Return device summary/history stats (mirrors old GET /devices/{id}/summary).
- {"action": "health"}
    Simple health check.
"""

import json
import logging
import boto3
from typing import Dict, Any
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


# Agent runtime IDs (from deployment)
HEALTH_AGENT_RUNTIME_ID = 'health_agent_runtime-fAr31a5AEi'
DIAGNOSIS_AGENT_RUNTIME_ID = 'diagnosis_agent_runtime-r8AcIc5zbG'

# Lazily initialized DeviceLoader (only needed for list_devices/get_device/get_device_summary)
_device_loader = None


def _get_device_loader():
    """Lazily construct the DeviceLoader (reads S3 config from env vars)."""
    global _device_loader
    if _device_loader is None:
        import os
        # Import here (not at module load time) to keep the "analyze" path
        # (the hot path, called on every request) free of this dependency.
        from src.utils.device_loader import DeviceLoader
        _device_loader = DeviceLoader(
            data_dir="data/generated",
            bucket=os.getenv("SYNTHETIC_DATA_BUCKET"),
            prefix=os.getenv("SYNTHETIC_DATA_PREFIX", "devices/")
        )
    return _device_loader


def invoke_agent(runtime_id: str, device_id: str, payload: Dict[str, Any], account_id: str) -> Dict[str, Any]:
    """
    Invoke another agent via boto3.invoke_agent_runtime().
    
    Args:
        runtime_id: Runtime ID of target agent
        device_id: Device ID (for session ID generation)
        payload: Payload to send to agent
        account_id: AWS account ID
        
    Returns:
        Agent response (parsed JSON)
    """
    try:
        # Construct ARN
        agent_runtime_arn = f"arn:aws:bedrock-agentcore:us-east-1:{account_id}:runtime/{runtime_id}"
        
        # Generate session ID (must be >= 33 chars)
        session_id = f"{device_id}-{runtime_id[:8]}-{int(datetime.now().timestamp() * 1000000)}"
        
        logger.info(f"Invoking {runtime_id} with session_id length {len(session_id)}")
        
        # Create client and invoke
        agentcore_client = boto3.client('bedrock-agentcore', region_name='us-east-1')
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn,
            runtimeSessionId=session_id,
            payload=json.dumps(payload)
        )
        
        # Read and parse response
        response_body = response['response'].read()
        result = json.loads(response_body.decode('utf-8'))
        
        logger.info(f"✅ {runtime_id} response received")
        
        return result
        
    except Exception as e:
        logger.error(f"Error invoking {runtime_id}: {type(e).__name__}: {str(e)}")
        raise


def _analyze_device(device_id: str, equipment_type: str, current_reading: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core orchestration: call HealthAgent, then optionally DiagnosisAgent.
    
    Returns the response body dict (not wrapped in statusCode/body).
    """
    # Get account ID
    sts = boto3.client('sts', region_name='us-east-1')
    account_id = sts.get_caller_identity()['Account']
    logger.info(f"Account ID: {account_id}")
    
    # STEP 1: Call HealthAgent
    logger.info("STEP 1: Invoking HealthAgent...")
    
    health_payload = {
        'device_id': device_id,
        'equipment_type': equipment_type,
        'current_reading': current_reading
    }
    
    health_result = invoke_agent(
        HEALTH_AGENT_RUNTIME_ID,
        device_id,
        health_payload,
        account_id
    )
    
    # Extract health data
    health_body = health_result.get('body', {})
    health_status = health_body.get('health_status', 'unknown')
    degradation_score = health_body.get('degradation_score', 0.0)
    anomalies = health_body.get('anomalies', [])
    
    logger.info(f"Health status: {health_status}, Degradation: {degradation_score}")
    
    # STEP 2: Route based on health status
    if health_status == 'healthy':
        logger.info("Device is healthy, skipping DiagnosisAgent")
        
        return {
            'device_id': device_id,
            'equipment_type': equipment_type,
            'health_status': health_status,
            'degradation_score': degradation_score,
            'anomalies': anomalies,
            'diagnosis': 'Device operating normally',
            'confidence': 1.0,
            'action': 'MONITOR_ONLY',
            'action_taken': 'No action required',
            'agents_used': ['HealthAgent'],
            'path': 'health_only',
            'timestamp': datetime.now().isoformat()
        }
    
    # STEP 3: Call DiagnosisAgent for non-healthy devices
    logger.info("STEP 2: Invoking DiagnosisAgent...")
    
    diagnosis_payload = {
        'device_id': device_id,
        'equipment_type': equipment_type,
        'health_status': health_status,
        'degradation_score': degradation_score,
        'anomalies': anomalies
    }
    
    diagnosis_result = invoke_agent(
        DIAGNOSIS_AGENT_RUNTIME_ID,
        device_id,
        diagnosis_payload,
        account_id
    )
    
    # Extract diagnosis data
    diagnosis_body = diagnosis_result.get('body', {})
    
    # STEP 4: Return combined result
    final_result = {
        'device_id': device_id,
        'equipment_type': equipment_type,
        'health_status': health_status,
        'degradation_score': degradation_score,
        'anomalies': anomalies,
        'diagnosis': diagnosis_body.get('diagnosis'),
        'confidence': diagnosis_body.get('confidence', 0.0),
        'severity': diagnosis_body.get('severity', 'unknown'),
        'action': diagnosis_body.get('action'),
        'action_taken': diagnosis_body.get('action_taken', ''),
        'agents_used': ['HealthAgent', 'DiagnosisAgent'],
        # tool_results holds the actual MCP tool call outputs (e.g.
        # {'create-work-order': {'work_order_id': 'WO-...', ...}}) - the
        # dashboard reads this directly to populate work orders/maintenance/
        # spare parts. mcp_tools_used is derived from its keys (DiagnosisAgent
        # itself does not return a 'mcp_tools_used' field, only 'tool_results').
        'tool_results': diagnosis_body.get('tool_results', {}),
        'mcp_tools_used': list(diagnosis_body.get('tool_results', {}).keys()),
        'path': 'full_diagnosis',
        'timestamp': datetime.now().isoformat()
    }
    
    logger.info(f"Orchestration complete: Action={final_result['action']}")
    return final_result


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    AgentCore Runtime handler for OrchestratorAgent.
    
    Dispatches based on the optional "action" field - see module docstring
    for supported payloads.
    """
    try:
        logger.info(f"OrchestratorAgent handler invoked")
        logger.info(f"Payload: {json.dumps(event)[:200]}")
        
        action = event.get('action', 'analyze')
        
        # ---- action: health ----
        if action == 'health':
            return {
                'statusCode': 200,
                'body': {'status': 'healthy', 'service': 'OrchestratorAgent'}
            }
        
        # ---- action: list_devices ----
        if action == 'list_devices':
            devices = _get_device_loader().list_available_devices()
            return {
                'statusCode': 200,
                'body': {'total': len(devices), 'devices': devices}
            }
        
        # ---- action: get_device_summary ----
        if action == 'get_device_summary':
            device_id = event.get('device_id')
            if not device_id:
                return {'statusCode': 400, 'body': {'error': 'device_id is required'}}
            summary = _get_device_loader().get_device_summary(device_id)
            if not summary:
                return {'statusCode': 404, 'body': {'error': f'Device {device_id} not found'}}
            return {'statusCode': 200, 'body': summary}
        
        # ---- action: get_device (load raw reading from S3, then analyze) ----
        if action == 'get_device':
            device_id = event.get('device_id')
            if not device_id:
                return {'statusCode': 400, 'body': {'error': 'device_id is required'}}
            
            device_status = _get_device_loader().get_device_status(device_id)
            if not device_status:
                return {'statusCode': 404, 'body': {'error': f'Device {device_id} not found'}}
            
            result_body = _analyze_device(
                device_id=device_status['device_id'],
                equipment_type=device_status['equipment_type'],
                current_reading=device_status['current_reading']
            )
            return {'statusCode': 200, 'body': result_body}
        
        # ---- default action: analyze (existing behavior - reading supplied directly) ----
        device_id = event.get('device_id', 'unknown')
        equipment_type = event.get('equipment_type', 'UNKNOWN')
        current_reading = event.get('current_reading', {})
        
        logger.info(f"Processing device {device_id} ({equipment_type})")
        
        result_body = _analyze_device(device_id, equipment_type, current_reading)
        
        return {
            'statusCode': 200,
            'body': result_body
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in OrchestratorAgent handler: {error_msg}")
        
        return {
            'statusCode': 500,
            'body': {
                'error': 'OrchestratorAgent processing failed',
                'details': error_msg[:200]
            }
        }


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Alternative entry point name"""
    return lambda_handler(event, context)
