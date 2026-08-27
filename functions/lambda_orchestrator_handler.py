"""
Lambda Handler for AgentCore Orchestrator Integration

Purpose:
    Bridge between API Gateway and AgentCore Orchestrator Runtime.
    Enables external systems (Dashboard, curl, external APIs) to invoke agents
    without direct AWS network access.

Flow:
    API Gateway Event → Lambda Handler → Orchestrator Agent (AgentCore)
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


def parse_api_gateway_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse API Gateway event to extract device data.
    
    Supports both:
    - Direct JSON body: {"device_id": "...", "equipment_type": "...", "current_reading": {...}}
    - Base64 encoded body (application/octet-stream)
    
    Args:
        event: API Gateway event
        
    Returns:
        Dictionary with device_id, equipment_type, current_reading
    """
    # Extract body
    body = event.get('body', '{}')
    
    # Handle base64 encoding
    if event.get('isBase64Encoded'):
        body = base64.b64decode(body).decode('utf-8')
    
    # Parse JSON
    if isinstance(body, str):
        try:
            body_json = json.loads(body)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in request body: {body[:200]}")
            return {'error': 'Invalid JSON in request body'}
    else:
        body_json = body
    
    # Extract required fields
    device_id = body_json.get('device_id')
    equipment_type = body_json.get('equipment_type')
    current_reading = body_json.get('current_reading')
    
    # Validate
    if not all([device_id, equipment_type, current_reading]):
        missing = []
        if not device_id:
            missing.append('device_id')
        if not equipment_type:
            missing.append('equipment_type')
        if not current_reading:
            missing.append('current_reading')
        
        return {
            'error': f'Missing required fields: {", ".join(missing)}',
            'details': 'Required: device_id (string), equipment_type (string), current_reading (object)'
        }
    
    return {
        'device_id': device_id,
        'equipment_type': equipment_type,
        'current_reading': current_reading
    }


def create_response(
    status_code: int,
    body: Dict[str, Any],
    cors_origin: str = '*'
) -> Dict[str, Any]:
    """
    Create API Gateway response with CORS headers.
    
    Args:
        status_code: HTTP status code
        body: Response body dictionary
        cors_origin: CORS origin (default: allow all)
        
    Returns:
        API Gateway response format
    """
    return {
        'statusCode': status_code,
        'body': json.dumps(body),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': cors_origin,
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'POST,OPTIONS',
        }
    }


def handle_get_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route GET requests to the appropriate OrchestratorAgent "action" payload.
    
    Supported routes:
        GET /health                              -> action=health
        GET /devices                             -> action=list_devices
        GET /devices/{device_id}                 -> action=get_device
        GET /devices/{device_id}/summary         -> action=get_device_summary
        GET /fleet-summary                       -> aggregated fleet KPIs
    """
    path_params = event.get('pathParameters') or {}
    device_id = path_params.get('device_id') or path_params.get('proxy', '')
    path = event.get('path') or ''
    
    # Strip /api prefix from CloudFront routing
    if '/api/' in path:
        path = path.split('/api')[-1]
    
    if path.endswith('/health'):
        action = 'health'
    elif 'fleet-summary' in path:
        return handle_fleet_summary()
    elif path.endswith('/summary'):
        action = 'get_device_summary'
    elif '/devices/' in path:
        # Extract device_id from path: /devices/motor-001
        parts = path.split('/devices/')
        if len(parts) > 1:
            device_id = parts[1].split('/')[0]
        action = 'get_device'
    elif path.endswith('/devices'):
        action = 'list_devices'
    else:
        action = 'list_devices'
    
    log_info(f"GET request routed to action '{action}'", {
        'path': path,
        'device_id': device_id
    })
    
    agent_result = invoke_orchestrator_action(action=action, device_id=device_id)
    
    if 'error' in agent_result:
        status_code = agent_result.get('statusCode', 500)
        log_error("Agent action failed", context={'action': action, 'error': agent_result.get('error')})
        return create_response(status_code, agent_result)
    
    status_code = agent_result.get('statusCode', 200)
    body = agent_result.get('body', agent_result)
    return create_response(status_code, body)


def handle_fleet_summary() -> Dict[str, Any]:
    """
    Build fleet summary by calling the orchestrator for device list,
    then fetching each device's health via get_device_summary in parallel.
    """
    log_info("Fleet summary requested — fetching device list from orchestrator")
    
    # Step 1: Get device IDs from orchestrator
    devices_result = invoke_orchestrator_action(action='list_devices')
    
    device_ids = []
    if isinstance(devices_result, dict):
        if 'body' in devices_result:
            body = devices_result['body']
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except:
                    pass
            if isinstance(body, dict):
                device_ids = body.get('devices', [])
            elif isinstance(body, list):
                device_ids = body
        else:
            device_ids = devices_result.get('devices', [])
    
    log_info(f"Got {len(device_ids)} device IDs, fetching summaries in parallel...")
    
    # Step 2: Fetch health data for each device in parallel
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def fetch_device(did):
        if not isinstance(did, str):
            return did
        try:
            detail = invoke_orchestrator_action(action='get_device_summary', device_id=did)
            if isinstance(detail, dict) and 'error' not in detail:
                body = detail.get('body', detail)
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except:
                        pass
                if isinstance(body, dict):
                    body.setdefault('device_id', did)
                    return body
        except:
            pass
        return {'device_id': did}
    
    devices = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_device, did): did for did in device_ids}
        for future in as_completed(futures):
            devices.append(future.result())
    
    # Step 3: Aggregate health KPIs
    total = len(devices)
    healthy = 0
    warning = 0
    critical = 0
    
    for d in devices:
        if isinstance(d, dict):
            state = d.get('current_health', d.get('health_state', '')).lower()
            if state in ('healthy', 'normal', 'good'):
                healthy += 1
            elif state in ('warning', 'degraded'):
                warning += 1
            elif state in ('critical', 'failure', 'failed'):
                critical += 1
    
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_devices': total,
        'healthy_devices': healthy,
        'warning_devices': warning,
        'critical_devices': critical,
        'fleet_health_percent': round((healthy / total * 100) if total else 0),
        'degradation_trend': 'stable',
        'devices_list': devices,
        '_problematic_devices': [d for d in devices if isinstance(d, dict) and d.get('current_health', d.get('health_state', '')).lower() not in ('healthy', 'normal', 'good', '')],
        'work_orders': [],
        'maintenance_schedules': [],
        'spare_parts': [],
    }
    
    log_info(f"Fleet summary: {total} devices, {healthy} healthy, {warning} warning, {critical} critical")
    return create_response(200, summary)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for API Gateway orchestrator invocation.
    
    Input (from API Gateway):
    {
      "body": {
        "device_id": "motor-004",
        "equipment_type": "MOTOR",
        "current_reading": {
          "readings": {
            "current": {"value": 100, "unit": "Amps", "normal_range": [60, 80]},
            "temperature": {"value": 143.19, "unit": "F", "normal_range": [60, 120]},
            ...
          }
        }
      }
    }
    
    Output:
    {
      "statusCode": 200,
      "body": JSON with agent results
    }
    """
    invocation_start = datetime.now()
    
    log_info(f"Lambda invoked at {invocation_start.isoformat()}", {
        'request_id': context.request_id if hasattr(context, 'request_id') else 'N/A',
        'function_name': context.function_name if hasattr(context, 'function_name') else 'N/A'
    })
    
    # Handle OPTIONS request (CORS preflight)
    if event.get('httpMethod') == 'OPTIONS':
        logger.debug("Handling CORS preflight request")
        return create_response(200, {'message': 'CORS preflight OK'})
    
    # Handle GET requests (devices list/detail/summary, health) - these use
    # "action" payloads to the orchestrator agent instead of a direct analyze body.
    if event.get('httpMethod') == 'GET':
        return handle_get_request(event)
    
    # Parse request
    parse_result = parse_api_gateway_event(event)
    if 'error' in parse_result:
        log_error("Invalid request format", context=parse_result)
        return create_response(400, parse_result)
    
    device_id = parse_result['device_id']
    equipment_type = parse_result['equipment_type']
    current_reading = parse_result['current_reading']
    
    log_info(f"Processing device {device_id} ({equipment_type})")
    
    # Invoke agent
    agent_result = invoke_orchestrator_agent(
        device_id=device_id,
        equipment_type=equipment_type,
        current_reading=current_reading,
        timeout=60
    )
    
    # Determine status code
    if 'error' in agent_result:
        status_code = agent_result.get('statusCode', 500)
        log_error(f"Agent invocation failed", context={
            'device_id': device_id,
            'error': agent_result.get('error')
        })
    else:
        status_code = 200
        processing_time = (datetime.now() - invocation_start).total_seconds() * 1000
        agent_result['processing_time_ms'] = int(processing_time)
        log_info(f"✅ Agent processing complete", {
            'device_id': device_id,
            'processing_time_ms': int(processing_time),
            'action': agent_result.get('action'),
            'confidence': agent_result.get('confidence')
        })
    
    return create_response(status_code, agent_result)


# Test handler (for local testing)
if __name__ == '__main__':
    # Mock event and context
    mock_event = {
        'httpMethod': 'POST',
        'body': json.dumps({
            'device_id': 'motor-004',
            'equipment_type': 'MOTOR',
            'current_reading': {
                'readings': {
                    'rpm': {'value': 3450.58, 'unit': 'RPM', 'normal_range': [3450, 3550]},
                    'current': {'value': 100, 'unit': 'Amps', 'normal_range': [60, 80]},
                    'temperature': {'value': 143.19, 'unit': 'F', 'normal_range': [60, 120]},
                    'voltage': {'value': 378.25, 'unit': 'V', 'normal_range': [350, 410]},
                    'power_factor': {'value': 0.8424, 'unit': 'PF', 'normal_range': [0.9, 1.0]},
                    'vibration': {'value': 5.16, 'unit': 'mm/s', 'normal_range': [0, 2]}
                }
            }
        })
    }
    
    class MockContext:
        request_id = 'local-test-123'
        function_name = 'lambda-orchestrator-handler'
    
    result = lambda_handler(mock_event, MockContext())
    print(json.dumps(result, indent=2))
