"""
AgentCore Runtime entry point for DiagnosisAgent.

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

from src.agents.diagnosis_agent import DiagnosisAgent

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
agent = DiagnosisAgent()


@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Payload: {"device_id", "equipment_type", "health_status", "degradation_score", "anomalies"}
    Returns: {"statusCode": 200, "body": {"diagnosis": ..., "action": ..., "confidence": ..., ...}}
    """
    try:
        logger.info(f"Payload: {json.dumps(payload)[:200]}")

        device_id = payload.get('device_id', 'unknown')
        equipment_type = payload.get('equipment_type', 'UNKNOWN')
        health_status = payload.get('health_status', 'unknown')
        degradation_score = payload.get('degradation_score', 0.0)
        anomalies = payload.get('anomalies', [])
        current_reading = payload.get('current_reading', {})

        result = asyncio.run(agent.execute({
            'device_id': device_id,
            'equipment_type': equipment_type,
            'health_status': health_status,
            'degradation_score': degradation_score,
            'anomalies': anomalies,
            'current_reading': current_reading
        }))

        logger.info(f"Diagnosis result: {result.get('action')}")
        return {'statusCode': 200, 'body': result}

    except Exception as e:
        logger.exception("DiagnosisAgent invocation failed")
        return {
            'statusCode': 500,
            'body': {'error': 'DiagnosisAgent processing failed', 'details': str(e)[:200]}
        }


if __name__ == "__main__":
    app.run(port=8080)
