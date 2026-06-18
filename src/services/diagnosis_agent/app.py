#!/usr/bin/env python3
"""
DiagnosisAgent FastAPI Service (Port 8002)

Week 2 Day 5-7 Implementation
Performs root cause analysis with 4-step process:
1. Pattern matching (equipment-specific rules)
2. Confidence check (≥0.85 = trust, <0.85 = call LLM)
3. Optional LLM enhancement
4. Execute action (with MCP tool calls)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException
import uvicorn

from src.agents.diagnosis_agent import DiagnosisAgent


# Pydantic models
class DiagnosisAgentRequest(BaseModel):
    """Request to diagnose a device (from Orchestrator via HealthAgent analysis)."""
    device_id: str
    equipment_type: str
    health_status: str = Field(description="healthy | warning | critical")
    degradation_score: float
    anomalies: List[str] = Field(default_factory=list)
    current_reading: Dict[str, Any] = Field(
        description="Sensor readings: {sensor_name: {value, unit, normal_range}}"
    )


class DiagnosisAgentResponse(BaseModel):
    """Response from diagnosis analysis."""
    device_id: str
    diagnosis: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_rule_based: Optional[float] = Field(ge=0.0, le=1.0, default=None)
    severity: str = Field(description="low | medium | high")
    action: str = Field(
        description="URGENT_REPAIR | SCHEDULE_MAINTENANCE | CHECK_PARTS_FIRST | MONITOR_ONLY"
    )
    action_taken: str
    tool_results: Dict[str, Any] = Field(default_factory=dict)
    llm_used: bool = False
    analysis_timestamp: str
    # Recommendation fields for dashboard display
    insights: str = Field(default="", description="Analysis reasoning explaining the action (LLM-based or Rule-Based)")
    immediate_actions: list = Field(default_factory=list, description="Steps to take now")
    predicted_failure_date: Optional[str] = Field(default=None, description="ISO date of predicted failure")
    recommendation_details: str = Field(default="", description="Detailed maintenance recommendation")


# Initialize FastAPI app
app = FastAPI(
    title="DiagnosisAgent Service",
    description="Root cause analysis with MCP tool orchestration (Week 2 Day 5-7)",
    version="1.0.0"
)

# Initialize DiagnosisAgent
diagnosis_agent = DiagnosisAgent()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "DiagnosisAgent"}


@app.post("/diagnose", response_model=DiagnosisAgentResponse)
async def diagnose_device(request: DiagnosisAgentRequest) -> DiagnosisAgentResponse:
    """
    Diagnose device issue with 4-step process:
    
    Step 1: Match equipment patterns (rules with confidence)
    Step 2: Check confidence threshold (≥0.85 = trust, <0.85 = need LLM)
    Step 3: Optional LLM enhancement (when uncertain)
    Step 4: Execute action (with MCP tool calls)
    
    Returns 4 action types:
    - URGENT_REPAIR: Critical issue, create work order immediately (MCP tool: create-work-order)
    - SCHEDULE_MAINTENANCE: Plan maintenance (MCP tool: schedule-maintenance)
    - CHECK_PARTS_FIRST: Verify parts availability (MCP tool: get-spare-parts)
    - MONITOR_ONLY: Insufficient data, continue monitoring
    """
    try:
        logger.info(f"Diagnosing device: {request.device_id} ({request.equipment_type})")
        logger.info(f"  Health: {request.health_status}, Confidence threshold: 0.85")
        
        # Call DiagnosisAgent.execute() with 4-step process
        result = await diagnosis_agent.execute({
            'device_id': request.device_id,
            'equipment_type': request.equipment_type,
            'health_status': request.health_status,
            'degradation_score': request.degradation_score,
            'anomalies': request.anomalies,
            'current_reading': request.current_reading
        })
        
        if result.get('status') != 'completed':
            raise Exception(result.get('error', 'Diagnosis failed'))
        
        # Build response
        response = DiagnosisAgentResponse(
            device_id=result['device_id'],
            diagnosis=result['diagnosis'],
            confidence=result['confidence'],
            confidence_rule_based=result.get('confidence_rule_based'),
            severity=result['severity'],
            action=result['action'],
            action_taken=result['action_taken'],
            tool_results=result.get('tool_results', {}),
            llm_used=result.get('llm_used', False),
            analysis_timestamp=result['analysis_timestamp'],
            insights=result.get('insights', ''),
            immediate_actions=result.get('immediate_actions', []),
            predicted_failure_date=result.get('predicted_failure_date'),
            recommendation_details=result.get('recommendation_details', '')
        )
        
        logger.info(f"Diagnosis complete: {response.action} (confidence: {response.confidence:.2f})")
        return response
        
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Diagnosis failed: {str(e)}"
        )


@app.post("/diagnose-batch")
async def diagnose_batch(devices: List[DiagnosisAgentRequest]):
    """Diagnose multiple devices."""
    results = []
    for device in devices:
        try:
            result = await diagnose_device(device)
            results.append(result.dict())
        except Exception as e:
            logger.error(f"Batch diagnosis failed for device: {e}")
            results.append({
                "device_id": device.device_id,
                "error": str(e)
            })
    
    return {
        "results": results,
        "total": len(devices),
        "successful": sum(1 for r in results if "error" not in r)
    }


if __name__ == "__main__":
    # Run service on port 8002
    logger.info("Starting DiagnosisAgent service on port 8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
