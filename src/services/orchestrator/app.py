#!/usr/bin/env python3
"""
Orchestrator Service (Port 8000)

Week 2 Day 5-7 Implementation
FastAPI wrapper around LangGraph workflow (core logic in src/graph/workflow.py)

Architecture Pattern:
├── Core: src/graph/workflow.py (OrchestrationWorkflow class - reusable)
└── Wrapper: src/services/orchestrator/app.py (FastAPI service - HTTP endpoints)

This matches the agent pattern:
├── Agents: src/agents/health_agent.py, src/agents/diagnosis_agent.py
└── Wrappers: src/services/health_agent/app.py, src/services/diagnosis_agent/app.py
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException
import uvicorn

from src.graph.workflow import OrchestrationWorkflow, WorkflowState
from src.utils.device_loader import DeviceLoader


# Pydantic models
class CurrentReading(BaseModel):
    """Current sensor reading."""
    readings: Dict[str, Any] = Field(
        description="Sensor data: {sensor_name: {value, unit, normal_range}}"
    )


class OrchestratorRequest(BaseModel):
    """Request to process device."""
    device_id: str
    equipment_type: str
    current_reading: CurrentReading


class OrchestratorResponse(BaseModel):
    """Final response from orchestrator."""
    device_id: str
    health_status: str
    diagnosis: str = None
    confidence: float = None
    action: str = None
    action_taken: str = None
    tool_results: Dict[str, Any] = Field(default_factory=dict)
    llm_used: bool = False
    path: str = Field(description="health_only (healthy device) | full_diagnosis (needs investigation)")
    processing_time_ms: float
    timestamp: str
    agents_used: list = Field(default_factory=list, description="Which agents were called for this request")
    mcp_tools_used: list = Field(default_factory=list, description="Which MCP tools were invoked")
    # Recommendation fields for dashboard display
    insights: str = Field(default="", description="Analysis reasoning explaining the action (LLM-based or Rule-Based)")
    immediate_actions: list = Field(default_factory=list, description="Steps to take now")
    predicted_failure_date: Optional[str] = Field(default=None, description="ISO date of predicted failure")
    recommendation_details: str = Field(default="", description="Detailed maintenance recommendation")


# Configuration
HEALTH_AGENT_URL = "http://health-agent:8001"  # Docker service name
DIAGNOSIS_AGENT_URL = "http://diagnosis-agent:8002"  # Docker service name

# In-memory request tracking (Phase 2.8 - Agent Usage Visibility)
# Keeps last 100 requests for agent/tool usage retrieval
request_history = {}  # {device_id: {timestamp: {...}, agents: [...], tools: [...]}}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Orchestrator Service",
    description="LangGraph workflow orchestrating HealthAgent and DiagnosisAgent (Week 2 Day 5-7)",
    version="1.0.0"
)

# Initialize workflow (core logic)
workflow = OrchestrationWorkflow(
    health_agent_url=HEALTH_AGENT_URL,
    diagnosis_agent_url=DIAGNOSIS_AGENT_URL
)

# Initialize device loader for real device data
device_loader = DeviceLoader(data_dir="data/generated")


# ==================== FastAPI Endpoints ====================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Orchestrator"}


@app.get("/workflow-info")
async def workflow_info():
    """Get workflow structure info."""
    return {
        "workflow": "LangGraph 4-node workflow (Week 2 Day 5-7)",
        "architecture": {
            "core": "src/graph/workflow.py (OrchestrationWorkflow class)",
            "wrapper": "src/services/orchestrator/app.py (FastAPI service)"
        },
        "nodes": [
            {
                "name": "health_agent",
                "purpose": "Classify device health (healthy/warning/critical)",
                "calls": "HealthAgent service via HTTP POST /analyze",
                "tools": "None"
            },
            {
                "name": "router",
                "purpose": "Route based on health_status (conditional)",
                "calls": "None",
                "optimization": "Skip DiagnosisAgent for healthy devices (cost/time optimization)"
            },
            {
                "name": "diagnosis_agent",
                "purpose": "4-step root cause analysis + action execution",
                "calls": "DiagnosisAgent service via HTTP POST /diagnose",
                "tools": "MCP tools (get-spare-parts, schedule-maintenance, create-work-order)"
            },
            {
                "name": "aggregator",
                "purpose": "Combine results into final response",
                "calls": "None"
            }
        ],
        "story_timings": {
            "story_1_healthy": "80ms (health_only path)",
            "story_2_simple": "200ms (full_diagnosis with high confidence)",
            "story_3_ambiguous": "450ms (full_diagnosis with LLM + tools)",
            "story_4_critical": "120ms (full_diagnosis with obvious pattern)"
        }
    }


@app.get("/devices")
async def list_devices():
    """List all available devices from data/generated/."""
    try:
        devices = device_loader.list_available_devices()
        return {
            "total": len(devices),
            "devices": devices
        }
    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/devices/{device_id}/summary")
async def get_device_summary(device_id: str):
    """Get device summary with history stats."""
    try:
        summary = device_loader.get_device_summary(device_id)
        if not summary:
            raise HTTPException(
                status_code=404,
                detail=f"Device {device_id} not found"
            )
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get device summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/devices/{device_id}")
async def process_device_from_file(device_id: str) -> OrchestratorResponse:
    """
    Process device from real sensor data (data/generated/{device_id}.json).
    
    This endpoint loads the latest reading from the device's JSON file
    and runs it through the complete workflow (HealthAgent → Router → DiagnosisAgent → Aggregator).
    
    The agents will automatically use MCP tools if issues are detected.
    
    Example:
    - GET /devices/pump-001 → Loads latest pump-001 reading and analyzes it
    - GET /devices/motor-005 → Loads latest motor-005 reading and analyzes it
    """
    start_time = time.time()
    
    try:
        # Load device status from real data file
        device_status = device_loader.get_device_status(device_id)
        if not device_status:
            raise HTTPException(
                status_code=404,
                detail=f"Device {device_id} not found in data/generated/"
            )
        
        logger.info(f"\n{'='*70}")
        logger.info(f"DEVICE ENDPOINT: Loading {device_id} from data/generated/")
        logger.info(f"Health state in file: {device_status.get('health_state')}")
        logger.info(f"Degradation score: {device_status.get('degradation_score')}")
        logger.info(f"{'='*70}")
        
        # Create request from device data
        request = OrchestratorRequest(
            device_id=device_status['device_id'],
            equipment_type=device_status['equipment_type'],
            current_reading=CurrentReading(
                readings=device_status['current_reading']['readings']
            )
        )
        
        # Prepare initial state for workflow
        initial_state: WorkflowState = {
            'device_id': request.device_id,
            'equipment_type': request.equipment_type,
            'current_reading': request.current_reading.dict(),
            'health_status': None,
            'degradation_score': 0.0,
            'anomalies': [],
            'diagnosis': None,
            'confidence': None,
            'severity': None,
            'action': None,
            'action_taken': None,
            'tool_results': {},
            'llm_used': False,
            'insights': '',
            'immediate_actions': [],
            'predicted_failure_date': None,
            'recommendation_details': '',
            'route': None,
            'start_time': start_time,
            'agents_used': [],
            'mcp_tools_used': []
        }
        
        # Run workflow (async)
        result = await workflow.run(initial_state)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Determine path taken
        path = 'health_only' if result['route'] == 'end' else 'full_diagnosis'
        
        # Build response
        response = OrchestratorResponse(
            device_id=result['device_id'],
            health_status=result['health_status'],
            diagnosis=result['diagnosis'],
            confidence=result['confidence'],
            action=result['action'],
            action_taken=result['action_taken'],
            tool_results=result.get('tool_results', {}),
            llm_used=result['llm_used'],
            path=path,
            processing_time_ms=processing_time_ms,
            timestamp=datetime.now().isoformat(),
            agents_used=result.get('agents_used', []),
            mcp_tools_used=result.get('mcp_tools_used', []),
            insights=result.get('insights', ''),
            immediate_actions=result.get('immediate_actions', []),
            predicted_failure_date=result.get('predicted_failure_date'),
            recommendation_details=result.get('recommendation_details', '')
        )
        
        # Track this request in history
        device_id = result['device_id']
        if device_id not in request_history:
            request_history[device_id] = []
        request_history[device_id].append({
            'timestamp': datetime.now().isoformat(),
            'agents_used': result.get('agents_used', []),
            'mcp_tools_used': result.get('mcp_tools_used', []),
            'action': result['action'],
            'health_status': result['health_status'],
            'path': path
        })
        
        # Keep only last 50 records per device
        if len(request_history[device_id]) > 50:
            request_history[device_id] = request_history[device_id][-50:]
        
        logger.info(f"{'='*70}")
        logger.info(f"DEVICE PROCESSING COMPLETE: {path} ({processing_time_ms:.0f}ms)")
        logger.info(f"Agents used: {result.get('agents_used', [])}")
        logger.info(f"MCP tools used: {result.get('mcp_tools_used', [])}")
        logger.info(f"Final Status: {result['health_status']} | Action: {result['action']}")
        logger.info(f"{'='*70}\n")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Device processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Device processing failed: {str(e)}"
        )



@app.post("/process", response_model=OrchestratorResponse)
async def process_device(request: OrchestratorRequest) -> OrchestratorResponse:
    """
    Process device through complete workflow.
    
    Workflow:
    1. HealthAgent: Classify health
    2. Router: Decide routing (cost optimization)
    3. DiagnosisAgent: Diagnose (if needed)
    4. Aggregator: Combine results
    
    Returns immediately with final report.
    """
    start_time = time.time()
    
    try:
        logger.info(f"\n{'='*70}")
        logger.info(f"WORKFLOW START: {request.device_id} ({request.equipment_type})")
        logger.info(f"{'='*70}")
        
        # Prepare initial state for workflow
        initial_state: WorkflowState = {
            'device_id': request.device_id,
            'equipment_type': request.equipment_type,
            'current_reading': request.current_reading.dict(),
            'health_status': None,
            'degradation_score': 0.0,
            'anomalies': [],
            'diagnosis': None,
            'confidence': None,
            'severity': None,
            'action': None,
            'action_taken': None,
            'tool_results': {},
            'llm_used': False,
            'insights': '',
            'immediate_actions': [],
            'predicted_failure_date': None,
            'recommendation_details': '',
            'route': None,
            'start_time': start_time,
            'agents_used': [],
            'mcp_tools_used': []
        }
        
        # Run workflow (async)
        result = await workflow.run(initial_state)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Determine path taken
        path = 'health_only' if result['route'] == 'end' else 'full_diagnosis'
        
        # Build response
        response = OrchestratorResponse(
            device_id=result['device_id'],
            health_status=result['health_status'],
            diagnosis=result['diagnosis'],
            confidence=result['confidence'],
            action=result['action'],
            action_taken=result['action_taken'],
            tool_results=result.get('tool_results', {}),
            llm_used=result['llm_used'],
            path=path,
            processing_time_ms=processing_time_ms,
            timestamp=datetime.now().isoformat(),
            agents_used=result.get('agents_used', []),
            mcp_tools_used=result.get('mcp_tools_used', []),
            insights=result.get('insights', ''),
            immediate_actions=result.get('immediate_actions', []),
            predicted_failure_date=result.get('predicted_failure_date'),
            recommendation_details=result.get('recommendation_details', '')
        )
        
        # Track this request in history
        device_id = result['device_id']
        if device_id not in request_history:
            request_history[device_id] = []
        request_history[device_id].append({
            'timestamp': datetime.now().isoformat(),
            'agents_used': result.get('agents_used', []),
            'mcp_tools_used': result.get('mcp_tools_used', []),
            'action': result['action'],
            'health_status': result['health_status'],
            'path': path
        })
        
        # Keep only last 50 records per device
        if len(request_history[device_id]) > 50:
            request_history[device_id] = request_history[device_id][-50:]
        
        logger.info(f"{'='*70}")
        logger.info(f"WORKFLOW COMPLETE: {path} ({processing_time_ms:.0f}ms)")
        logger.info(f"Agents used: {result.get('agents_used', [])}")
        logger.info(f"MCP tools used: {result.get('mcp_tools_used', [])}")
        logger.info(f"{'='*70}\n")
        
        return response
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Workflow failed: {str(e)}"
        )


# ==================== Agent Usage Tracking Endpoints (Phase 2.8) ====================

@app.get("/agents-trace/{device_id}")
async def get_agents_trace(device_id: str):
    """
    Get detailed agent and MCP tool usage history for a device.
    
    Phase 2.8 Feature: Visibility into multi-agent request processing
    
    Shows:
    - Which agents were called for each request
    - Which MCP tools were invoked
    - Health status and actions taken
    - Timestamps of each request
    
    Example: GET /agents-trace/pump-001
    Returns last 50 requests for pump-001 with full agent/tool details
    """
    if device_id not in request_history:
        return {
            "device_id": device_id,
            "message": "No request history found for this device",
            "total_requests": 0,
            "requests": []
        }
    
    history = request_history[device_id]
    
    return {
        "device_id": device_id,
        "total_requests": len(history),
        "requests": history
    }


@app.get("/agents-summary")
async def get_agents_summary():
    """
    Get summary of all devices that have been processed.
    
    Shows how many requests per device and which agents/tools are most used.
    """
    summary = {
        "total_devices": len(request_history),
        "devices": []
    }
    
    for device_id, history in request_history.items():
        if not history:
            continue
        
        # Aggregate stats
        agents_set = set()
        tools_set = set()
        paths = {'health_only': 0, 'full_diagnosis': 0}
        actions = {}
        
        for req in history:
            agents_set.update(req['agents_used'])
            tools_set.update(req['mcp_tools_used'])
            paths[req['path']] = paths.get(req['path'], 0) + 1
            action = req['action']
            actions[action] = actions.get(action, 0) + 1
        
        summary['devices'].append({
            "device_id": device_id,
            "total_requests": len(history),
            "agents_used": list(agents_set),
            "mcp_tools_used": list(tools_set),
            "routing_paths": paths,
            "actions_taken": actions,
            "last_request": history[-1]['timestamp'] if history else None
        })
    
    return summary


if __name__ == "__main__":
    logger.info("Starting Orchestrator service on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
