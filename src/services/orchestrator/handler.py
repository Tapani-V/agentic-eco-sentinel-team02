"""
AgentCore Runtime Handler for OrchestratorAgent

This is the entry point that AgentCore Runtime invokes directly.
It orchestrates calls to HealthAgent and DiagnosisAgent via a LangGraph
StateGraph workflow (src.graph.workflow_agentcore.AgentCoreworkflow), whose
nodes call the other agents via boto3.invoke_agent_runtime().

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

import asyncio
import json
import logging
import boto3
from typing import Dict, Any
import sys
import time
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

# Lazily initialized AgentCoreworkflow (built once per warm container, reused
# across invocations - avoids rebuilding the StateGraph and re-fetching the
# account ID on every single request).
_workflow = None


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


def _get_workflow():
    """Lazily construct the LangGraph AgentCoreworkflow (fetches account ID once)."""
    global _workflow
    if _workflow is None:
        from src.graph.workflow_agentcore import AgentCoreworkflow
        account_id = boto3.client('sts', region_name='us-east-1').get_caller_identity()['Account']
        _workflow = AgentCoreworkflow(
            health_agent_runtime_id=HEALTH_AGENT_RUNTIME_ID,
            diagnosis_agent_runtime_id=DIAGNOSIS_AGENT_RUNTIME_ID,
            account_id=account_id,
            region='us-east-1'
        )
    return _workflow


async def _analyze_device(device_id: str, equipment_type: str, current_reading: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core orchestration: run the HealthAgent -> DiagnosisAgent LangGraph workflow.
    
    Returns the response body dict (not wrapped in statusCode/body).
    """
    workflow = _get_workflow()
    
    initial_state = {
        'device_id': device_id,
        'equipment_type': equipment_type,
        'current_reading': current_reading,
        'health_status': '',
        'degradation_score': 0.0,
        'anomalies': [],
        'diagnosis': '',
        'confidence': 0.0,
        'confidence_rule_based': None,
        'severity': '',
        'action': '',
        'action_taken': '',
        'tool_results': {},
        'llm_used': False,
        'insights': '',
        'immediate_actions': [],
        'predicted_failure_date': None,
        'recommendation_details': '',
        'route': '',
        'start_time': time.time(),
        'agents_used': [],
        'mcp_tools_used': []
    }
    
    final_state = await workflow.run(initial_state)
    
    path = 'health_only' if final_state['route'] == 'end' else 'full_diagnosis'
    
    final_result = {
        'device_id': final_state['device_id'],
        'equipment_type': final_state['equipment_type'],
        'health_status': final_state['health_status'],
        'degradation_score': final_state['degradation_score'],
        'anomalies': final_state['anomalies'],
        'diagnosis': final_state['diagnosis'],
        'confidence': final_state['confidence'],
        'severity': final_state['severity'],
        'action': final_state['action'],
        'action_taken': final_state['action_taken'],
        'agents_used': final_state['agents_used'],
        # tool_results holds the actual MCP tool call outputs (e.g.
        # {'create-work-order': {'work_order_id': 'WO-...', ...}}) - the
        # dashboard reads this directly to populate work orders/maintenance/
        # spare parts.
        'tool_results': final_state['tool_results'],
        'mcp_tools_used': final_state['mcp_tools_used'],
        'path': path,
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
            
            result_body = asyncio.run(_analyze_device(
                device_id=device_status['device_id'],
                equipment_type=device_status['equipment_type'],
                current_reading=device_status['current_reading']
            ))
            return {'statusCode': 200, 'body': result_body}
        
        # ---- default action: analyze (existing behavior - reading supplied directly) ----
        device_id = event.get('device_id', 'unknown')
        equipment_type = event.get('equipment_type', 'UNKNOWN')
        current_reading = event.get('current_reading', {})
        
        logger.info(f"Processing device {device_id} ({equipment_type})")
        
        result_body = asyncio.run(_analyze_device(device_id, equipment_type, current_reading))
        
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
