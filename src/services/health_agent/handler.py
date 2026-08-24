"""
AgentCore Runtime entry point for HealthAgent.

This file itself IS the container's server: AgentCore Runtime POSTs invocation
payloads to /invocations (and health-checks /ping) on port 8080, both served
by BedrockAgentCoreApp - no separate wrapper script needed.
"""

import json
import logging
import asyncio
import sys
from typing import Dict, Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from src.agents.health_agent import HealthAgent

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
agent = HealthAgent()


@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Payload: {"device_id": "motor-004", "equipment_type": "MOTOR", "current_reading": {...}}
    Returns: {"statusCode": 200, "body": {"device_id": ..., "health_status": ..., ...}}
    """
    try:
        logger.info(f"Payload: {json.dumps(payload)[:200]}")

        device_id = payload.get('device_id', 'unknown')
        equipment_type = payload.get('equipment_type', 'UNKNOWN')
        current_reading = payload.get('current_reading', {})

        # current_reading may already be shaped as {"readings": {...}} (e.g. when
        # sourced from DeviceLoader/S3 via the orchestrator's get_device action),
        # or may be a flat sensor dict (e.g. a direct POST /orchestrate caller).
        # Normalize to always be {"readings": {...}} WITHOUT double-wrapping,
        # since HealthAgent.execute() expects current_reading['readings'].
        if isinstance(current_reading, dict) and 'readings' in current_reading:
            normalized_reading = current_reading
        else:
            normalized_reading = {'readings': current_reading}

        result = asyncio.run(agent.execute({
            'device_id': device_id,
            'equipment_type': equipment_type,
            'current_reading': normalized_reading
        }))

        logger.info(f"Analysis result: {result.get('health_status')}")
        return {'statusCode': 200, 'body': result}

    except Exception as e:
        logger.exception("HealthAgent invocation failed")
        return {
            'statusCode': 500,
            'body': {'error': 'HealthAgent processing failed', 'details': str(e)[:200]}
        }


if __name__ == "__main__":
    app.run(port=8080)
