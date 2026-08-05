"""
AgentCore Runtime Handler for HealthAgent

This is the entry point that AgentCore Runtime invokes directly.
It handles the AgentCore invocation protocol and delegates to the HealthAgent logic.
"""

import json
import logging
import asyncio
from typing import Dict, Any
import sys

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

from src.agents.health_agent import HealthAgent


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    AgentCore Runtime handler for HealthAgent.
    
    This function is invoked by AgentCore Runtime when the agent is called.
    
    Args:
        event: Invocation payload from AgentCore
            {
                "device_id": "motor-004",
                "equipment_type": "MOTOR",
                "current_reading": {...}
            }
        context: Lambda context (unused for AgentCore)
        
    Returns:
        {
            "statusCode": 200,
            "body": {
                "device_id": "...",
                "health_status": "...",
                "degradation_score": 0.5,
                "anomalies": [...],
                "timestamp": "..."
            }
        }
    """
    try:
        logger.info(f"HealthAgent handler invoked")
        logger.info(f"Payload: {json.dumps(event)[:200]}")
        
        # Parse input
        device_id = event.get('device_id', 'unknown')
        equipment_type = event.get('equipment_type', 'UNKNOWN')
        current_reading = event.get('current_reading', {})
        
        logger.info(f"Processing device {device_id} ({equipment_type})")
        
        # Initialize health agent
        agent = HealthAgent()
        
        # current_reading may already be shaped as {"readings": {...}} (e.g. when
        # sourced from DeviceLoader/S3 via the orchestrator's get_device action),
        # or may be a flat sensor dict (e.g. a direct POST /orchestrate caller).
        # Normalize to always be {"readings": {...}} WITHOUT double-wrapping,
        # since HealthAgent.execute() expects current_reading['readings'].
        if isinstance(current_reading, dict) and 'readings' in current_reading:
            normalized_reading = current_reading
        else:
            normalized_reading = {'readings': current_reading}
        
        # Prepare input for agent
        input_data = {
            'device_id': device_id,
            'equipment_type': equipment_type,
            'current_reading': normalized_reading
        }
        
        # Run the async execute method
        result = asyncio.run(agent.execute(input_data))
        
        logger.info(f"Analysis result: {result.get('health_status')}")
        
        return {
            'statusCode': 200,
            'body': result
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in HealthAgent handler: {error_msg}")
        logger.exception("Full traceback:")
        
        return {
            'statusCode': 500,
            'body': {
                'error': 'HealthAgent processing failed',
                'details': error_msg[:200]
            }
        }


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Alternative entry point name (some runtimes use 'handler' instead of 'lambda_handler')"""
    return lambda_handler(event, context)
