"""
AgentCore Runtime Handler for DiagnosisAgent

This is the entry point that AgentCore Runtime invokes directly.
It handles the AgentCore invocation protocol and delegates to the DiagnosisAgent logic.
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

from src.agents.diagnosis_agent import DiagnosisAgent


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    AgentCore Runtime handler for DiagnosisAgent.
    
    Args:
        event: Invocation payload
            {
                "device_id": "motor-004",
                "equipment_type": "MOTOR",
                "health_status": "warning",
                "degradation_score": 0.5,
                "anomalies": [...]
            }
        context: Lambda context
        
    Returns:
        {
            "statusCode": 200,
            "body": {
                "diagnosis": "...",
                "action": "...",
                "confidence": 0.8,
                "severity": "medium",
                "mcp_tools_used": [...]
            }
        }
    """
    try:
        logger.info(f"DiagnosisAgent handler invoked")
        logger.info(f"Payload: {json.dumps(event)[:200]}")
        
        # Parse input
        device_id = event.get('device_id', 'unknown')
        equipment_type = event.get('equipment_type', 'UNKNOWN')
        health_status = event.get('health_status', 'unknown')
        degradation_score = event.get('degradation_score', 0.0)
        anomalies = event.get('anomalies', [])
        
        logger.info(f"Diagnosing device {device_id} - Status: {health_status}")
        
        # Initialize diagnosis agent
        agent = DiagnosisAgent()
        
        # Prepare input for agent
        input_data = {
            'device_id': device_id,
            'equipment_type': equipment_type,
            'health_status': health_status,
            'degradation_score': degradation_score,
            'anomalies': anomalies
        }
        
        # Run the async execute method
        result = asyncio.run(agent.execute(input_data))
        
        logger.info(f"Diagnosis result: {result.get('action')}")
        
        return {
            'statusCode': 200,
            'body': result
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in DiagnosisAgent handler: {error_msg}")
        logger.exception("Full traceback:")
        
        return {
            'statusCode': 500,
            'body': {
                'error': 'DiagnosisAgent processing failed',
                'details': error_msg[:200]
            }
        }


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Alternative entry point name"""
    return lambda_handler(event, context)
