#!/usr/bin/env python3
"""
HealthAgent FastAPI Service (Port 8001)

Week 2 Day 5-7 Implementation
Analyzes device health and returns classification.
Does NOT call tools - only analysis.
"""

import logging
from typing import Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException
import uvicorn

# Import the HealthAgent from existing codebase
from src.agents.health_agent import HealthAgent


# Pydantic models for request/response
class SensorReading(BaseModel):
    """Single sensor reading."""
    value: float
    unit: str = ""
    normal_range: list = Field(default=[0, 100])


class HealthAgentRequest(BaseModel):
    """Request body for health analysis."""
    device_id: str
    equipment_type: str = "UNKNOWN"
    current_reading: Dict[str, Any] = Field(
        description="Sensor readings: {sensor_name: {value, unit, normal_range}}"
    )


class HealthAgentResponse(BaseModel):
    """Response from health analysis."""
    device_id: str
    health_status: str = Field(description="healthy | warning | critical")
    degradation_score: float = Field(ge=0.0, le=1.0)
    anomalies: list = Field(default_factory=list)
    analysis_timestamp: str


# Initialize FastAPI app
app = FastAPI(
    title="HealthAgent Service",
    description="Analyzes device health status via threshold-based rules (Week 2 Day 5-7)",
    version="1.0.0"
)

# Initialize HealthAgent
health_agent = HealthAgent()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "HealthAgent"}


@app.post("/analyze", response_model=HealthAgentResponse)
async def analyze_device_health(request: HealthAgentRequest) -> HealthAgentResponse:
    """
    Analyze device health based on sensor data.
    
    Step 1 of Week 2 Day 5-7 workflow:
    - Pure classification (no tool calls)
    - Returns health_status: healthy/warning/critical
    - Calculates degradation_score: 0.0-1.0
    - Detects anomalies (sensors out of range)
    
    NO LLM, NO TOOLS are called by HealthAgent
    """
    try:
        logger.info(f"Analyzing health for device: {request.device_id}")
        
        # Call HealthAgent.execute()
        result = await health_agent.execute({
            'device_id': request.device_id,
            'equipment_type': request.equipment_type,
            'current_reading': request.current_reading
        })
        
        if result.get('status') != 'completed':
            raise Exception(result.get('error', 'Analysis failed'))
        
        # Build response
        response = HealthAgentResponse(
            device_id=result['device_id'],
            health_status=result['health_status'],
            degradation_score=result['degradation_score'],
            anomalies=result.get('anomalies', []),
            analysis_timestamp=result['analysis_timestamp']
        )
        
        logger.info(f"Health analysis complete: {response.health_status}")
        return response
        
    except Exception as e:
        logger.error(f"Health analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Health analysis failed: {str(e)}"
        )


@app.post("/analyze-batch")
async def analyze_batch(devices: list[HealthAgentRequest]):
    """Analyze multiple devices."""
    results = []
    for device in devices:
        try:
            result = await analyze_device_health(device)
            results.append(result.dict())
        except Exception as e:
            logger.error(f"Batch analysis failed for device: {e}")
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
    # Run service on port 8001
    logger.info("Starting HealthAgent service on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
