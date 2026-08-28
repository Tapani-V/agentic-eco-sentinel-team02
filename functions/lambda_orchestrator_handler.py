"""
AgentCore Orchestrator bridge helpers.

Purpose:
    Library imported by functions/api_gateway_handler.py (the actual Lambda
    entry point). Owns the boto3.invoke_agent_runtime() calls to the
    Orchestrator AgentCore Runtime - HTTP routing/response shaping lives in
    api_gateway_handler.py, not here.

Flow:
    api_gateway_handler.py → invoke_orchestrator_action()/invoke_orchestrator_agent()
                                         ↓
                              Orchestrator Agent (AgentCore)
                                         ↓
                                    HealthAgent
                                         ↓
                                    DiagnosisAgent
                                         ↓
                                    MCP Tools (if needed)

Environment Variables:
    - ORCHESTRATOR_ENDPOINT: URL to orchestrator agent endpoint
    - COGNITO_APP_CLIENT_ID: OAuth2 client ID
    - COGNITO_APP_CLIENT_SECRET: OAuth2 client secret
    - COGNITO_TOKEN_ENDPOINT: Cognito token endpoint
    - COGNITO_SCOPE: Scope for token request
    - GATEWAY_URL: MCP gateway URL (passed to agents)
    - LOG_LEVEL: DEBUG/INFO/WARNING/ERROR (default: INFO)

Author: Agentic AI POC Phase 3.1
Date: 2026-07-23
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import boto3

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# Environment variables
ORCHESTRATOR_ENDPOINT = os.getenv('ORCHESTRATOR_ENDPOINT')
COGNITO_APP_CLIENT_ID = os.getenv('COGNITO_APP_CLIENT_ID')
COGNITO_APP_CLIENT_SECRET = os.getenv('COGNITO_APP_CLIENT_SECRET')
COGNITO_TOKEN_ENDPOINT = os.getenv('COGNITO_TOKEN_ENDPOINT')
COGNITO_SCOPE = os.getenv('COGNITO_SCOPE', 'agentcore/invoke')
GATEWAY_URL = os.getenv('GATEWAY_URL')

# Tokens cache (in-memory for Lambda execution context)
_token_cache = {'access_token': None, 'expires_at': None}


def log_info(message: str, context: Optional[Dict] = None):
    """Log info with optional context"""
    if context:
        logger.info(f"{message} | {json.dumps(context)[:200]}")
    else:
        logger.info(message)


def log_error(message: str, error: Optional[Exception] = None, context: Optional[Dict] = None):
    """Log error with optional exception and context"""
    if error:
        logger.error(f"{message} | {type(error).__name__}: {str(error)[:200]}")
    else:
        logger.error(message)
    if context:
        logger.error(f"Context: {json.dumps(context)[:200]}")





def invoke_orchestrator_agent(
    device_id: str,
    equipment_type: str,
    current_reading: Dict[str, Any],
    timeout: int = 60
) -> Dict[str, Any]:
    """
    Invoke OrchestratorAgent via boto3.invoke_agent_runtime().
    
    The OrchestratorAgent will:
    1. Call HealthAgent to assess device health
    2. Based on health status, optionally call DiagnosisAgent
    3. Return combined results
    
    All agent-to-agent communication happens through AgentCore Runtime.
    
    Args:
        device_id: Device identifier (e.g., 'motor-004')
        equipment_type: Equipment type (e.g., 'MOTOR', 'PUMP')
        current_reading: Device readings dictionary
        timeout: Request timeout in seconds
        
    Returns:
        Orchestration result with health and diagnosis data
    """
    payload = {
        'device_id': device_id,
        'equipment_type': equipment_type,
        'current_reading': current_reading
    }
    return _invoke_orchestrator_runtime(payload, session_prefix=device_id)


def invoke_orchestrator_action(action: str, device_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Invoke OrchestratorAgent with an "action" payload (list_devices, get_device,
    get_device_summary, health) instead of a direct analyze request. The
    orchestrator agent itself owns fetching device data (from S3) and running
    the analysis workflow - this Lambda just bridges HTTP to the agent.
    
    Args:
        action: One of 'list_devices', 'get_device', 'get_device_summary', 'health'
        device_id: Required for 'get_device' and 'get_device_summary'
        
    Returns:
        Orchestrator agent response (parsed JSON)
    """
    payload: Dict[str, Any] = {'action': action}
    if device_id:
        payload['device_id'] = device_id
    return _invoke_orchestrator_runtime(payload, session_prefix=device_id or action)


def _invoke_orchestrator_runtime(payload: Dict[str, Any], session_prefix: str) -> Dict[str, Any]:
    """
    Low-level boto3.invoke_agent_runtime() call against the OrchestratorAgent,
    shared by both the "analyze" (POST) and "action" (GET) invocation styles.
    
    Args:
        payload: Payload dict to send to the orchestrator agent
        session_prefix: Used to build a unique, >=33 char session ID
        
    Returns:
        Orchestrator agent response (parsed JSON), or an error dict with
        'statusCode' set on failure.
    """
    try:
        # Agent runtime ID (from AgentCore deployment)
        orchestrator_runtime_id = os.getenv('ORCHESTRATOR_RUNTIME_ID', 'orchestrator_runtime_team01-2mBWLh67eI')
        
        # Get account ID
        region = os.getenv('AWS_REGION_NAME', os.getenv('AWS_REGION', 'eu-central-1'))
        sts = boto3.client('sts', region_name=region)
        account_id = sts.get_caller_identity()['Account']
        
        log_info(f"Invoking OrchestratorAgent", {
            'account_id': account_id,
            'payload_action': payload.get('action', 'analyze')
        })
        
        # Construct ARN for orchestrator agent
        agent_runtime_arn = f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{orchestrator_runtime_id}"
        
        # Generate session ID (must be >= 33 chars). Pad short prefixes (e.g.
        # action names like "health" with no device_id) so the total length
        # always satisfies AgentCore's minimum requirement.
        session_id = f"{session_prefix}-{orchestrator_runtime_id[:8]}-{int(datetime.now().timestamp() * 1000000)}"
        if len(session_id) < 33:
            session_id = session_id.ljust(33, '0')
        
        log_info(f"Invoking OrchestratorAgent", {
            'session_id_length': len(session_id),
            'arn': agent_runtime_arn
        })
        
        # Create client and invoke via AgentCore Runtime
        agentcore_client = boto3.client('bedrock-agentcore', region_name=region)
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn,
            runtimeSessionId=session_id,
            payload=json.dumps(payload)
        )
        
        # Read and parse response
        response_body = response['response'].read()
        result = json.loads(response_body.decode('utf-8'))
        
        log_info(f"✅ OrchestratorAgent response received", {
            'status_code': result.get('statusCode')
        })
        
        return result
        
    except Exception as e:
        error_type = type(e).__name__
        log_error(f"Orchestration error: {error_type}", e, {
            'session_prefix': session_prefix
        })
        
        # Map specific exceptions to HTTP status codes
        if 'Timeout' in error_type or 'ReadTimeout' in error_type:
            status_code = 504
        elif 'ValidationError' in error_type or 'Invalid' in error_type:
            status_code = 400
        elif 'NotFound' in error_type:
            status_code = 404
        elif 'AccessDenied' in error_type or 'Unauthorized' in error_type or 'Forbidden' in error_type:
            status_code = 403
        else:
            status_code = 500
        
        return {
            'statusCode': status_code,
            'error': 'Orchestration error',
            'details': str(e)[:200]
        }


# NOTE: HTTP request parsing, CORS response shaping, and GET-route dispatch
# (previously parse_api_gateway_event/create_response/handle_get_request/
# lambda_handler) now live in functions/api_gateway_handler.py, which is the
# actual configured Lambda entry point (FastAPI + Mangum). Only the
# AgentCore-bridge functions above are still used.
