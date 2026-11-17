"""
Orchestrator Service (Port 8000)

FastAPI wrapper around LangGraph workflow (core logic in src/graph/workflow.py)

Architecture Pattern:
- Core: src/graph/workflow.py (OrchestrationWorkflow class - reusable)
- Wrapper: src/services/orchestrator/app.py (FastAPI service - HTTP endpoints)

This matches the agent pattern:
- Agents: src/agents/health_agent.py, src/agents/diagnosis_agent.py,
          src/agents/sustainability_agent.py
- Wrappers: src/services/health_agent/app.py, src/services/diagnosis_agent/app.py
"""

# Load environment variables from .agentcore.env (local development)
# In AWS AgentCore Runtime, .agentcore.env won't exist and this will be skipped
import os
from pathlib import Path
from dotenv import load_dotenv

env_file = Path(__file__).parent.parent.parent / '.agentcore.env'
if env_file.exists():
    load_dotenv(env_file)

import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
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
    degradation_score: float = 0.0
    diagnosis: str = None
    confidence: float = None
    confidence_rule_based: Optional[float] = None
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

    # SustainabilityAgent fields.
    # All optional: the agent is deliberately skipped for healthy devices and
    # bypassed entirely for critical ones, so absence here is meaningful rather
    # than an error -- it is the safety guardrail showing up in the API.
    sust_recommendation: Optional[str] = Field(
        default=None, description="REPAIR_NOW | DEFER_TO_PLANNED_VISIT | CONTINUE_MONITORING"
    )
    sust_explanation: Optional[str] = Field(
        default=None, description="Plain-English rationale (Bedrock, or deterministic fallback)"
    )
    sust_co2: Optional[str] = Field(default=None, description="Carbon justification")
    sust_cost: Optional[str] = Field(default=None, description="Business justification")
    sust_risk_level: Optional[str] = Field(
        default=None, description="Low | Moderate | Elevated | Unquantified"
    )
    sust_scheduled_date: Optional[str] = Field(
        default=None, description="Service date chosen by the Sustainability Agent"
    )
    sust_options: List[Dict[str, Any]] = Field(
        default_factory=list, description="Full option comparison, including rejected options"
    )
    sust_grid: Optional[Dict[str, Any]] = Field(
        default=None, description="Grid carbon intensity used for the decision"
    )
    sust_breakeven: Optional[Dict[str, Any]] = Field(
        default=None, description="Daily energy waste at which deferral stops being carbon-positive"
    )
    sust_applied: bool = Field(
        default=False, description="Whether sustainability optimisation actually ran"
    )


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
    description="LangGraph workflow orchestrating HealthAgent, DiagnosisAgent and SustainabilityAgent",
    version="1.1.0"
)

# Initialize workflow (core logic)
workflow = OrchestrationWorkflow(
    health_agent_url=HEALTH_AGENT_URL,
    diagnosis_agent_url=DIAGNOSIS_AGENT_URL
)

# Initialize device loader for real device data
# Phase 2: Reads from S3 if SYNTHETIC_DATA_BUCKET is set, otherwise uses local files
# Configuration from .agentcore.env:
#   AWS_PROFILE: AWS SSO profile name (required for S3 access)
#   SYNTHETIC_DATA_BUCKET: S3 bucket name
#   SYNTHETIC_DATA_PREFIX: S3 prefix (default: devices/)
#   BOTO3_DISABLE_SSL_VERIFICATION: Set to 'true' for dev environments with SSL cert issues
#   USE_LOCAL_DATA: Set to 'true' to force local file access (dev only)
bucket = os.getenv("SYNTHETIC_DATA_BUCKET")
prefix = os.getenv("SYNTHETIC_DATA_PREFIX", "devices/")
device_loader = DeviceLoader(
    data_dir="data/generated",
    bucket=bucket,
    prefix=prefix
)
logger.info(f"DeviceLoader initialized: S3 bucket={bucket}, profile={os.getenv('AWS_PROFILE')}")


# ==================== Shared helpers ====================

def _initial_state(request: "OrchestratorRequest", start_time: float) -> WorkflowState:
    """Build the initial WorkflowState.

    LangGraph expects every declared state key to be present, so this is the
    single place where new state fields get initialised. Both endpoints use it,
    which is why adding a field can no longer be done in one place and forgotten
    in the other.
    """
    return {
        'device_id': request.device_id,
        'equipment_type': request.equipment_type,
        'current_reading': request.current_reading.dict(),
        'health_status': None,
        'degradation_score': 0.0,
        'anomalies': [],
        'diagnosis': None,
        'confidence': None,
        'confidence_rule_based': None,
        'severity': None,
        'action': None,
        'action_taken': None,
        'tool_results': {},
        'llm_used': False,
        'insights': '',
        'immediate_actions': [],
        'predicted_failure_date': None,
        'recommendation_details': '',
        # SustainabilityAgent
        'sust_recommendation': None,
        'sust_explanation': None,
        'sust_co2': None,
        'sust_cost': None,
        'sust_risk_level': None,
        'sust_scheduled_date': None,
        'sust_options': [],
        'sust_grid': None,
        'sust_breakeven': None,
        'sust_applied': False,
        'route': None,
        'start_time': start_time,
        'agents_used': [],
        'mcp_tools_used': []
    }


def _build_response(
    result: Dict[str, Any], path: str, processing_time_ms: float
) -> OrchestratorResponse:
    """Assemble the API response from the final workflow state."""
    return OrchestratorResponse(
        device_id=result['device_id'],
        health_status=result['health_status'],
        degradation_score=result.get('degradation_score', 0.0),
        diagnosis=result['diagnosis'],
        confidence=result['confidence'],
        confidence_rule_based=result.get('confidence_rule_based'),
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
        recommendation_details=result.get('recommendation_details', ''),
        # SustainabilityAgent
        sust_recommendation=result.get('sust_recommendation'),
        sust_explanation=result.get('sust_explanation'),
        sust_co2=result.get('sust_co2'),
        sust_cost=result.get('sust_cost'),
        sust_risk_level=result.get('sust_risk_level'),
        sust_scheduled_date=result.get('sust_scheduled_date'),
        sust_options=result.get('sust_options', []),
        sust_grid=result.get('sust_grid'),
        sust_breakeven=result.get('sust_breakeven'),
        sust_applied=result.get('sust_applied', False),
    )


def _track_request(result: Dict[str, Any], path: str) -> None:
    """Record agent and tool usage for the /agents-trace endpoints."""
    device_id = result['device_id']
    if device_id not in request_history:
        request_history[device_id] = []
    request_history[device_id].append({
        'timestamp': datetime.now().isoformat(),
        'agents_used': result.get('agents_used', []),
        'mcp_tools_used': result.get('mcp_tools_used', []),
        'action': result['action'],
        'health_status': result['health_status'],
        'path': path,
        'sust_recommendation': result.get('sust_recommendation'),
    })
    # Keep only last 50 records per device
    if len(request_history[device_id]) > 50:
        request_history[device_id] = request_history[device_id][-50:]


# ==================== FastAPI Endpoints ====================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Orchestrator"}


@app.get("/workflow-info")
async def workflow_info():
    """Get workflow structure info."""
    return {
        "workflow": "LangGraph 5-node workflow",
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
                "name": "sustainability",
                "purpose": (
                    "Decide WHEN and HOW to act: compares repair now, defer to a "
                    "planned visit, and continue monitoring using live grid carbon "
                    "intensity, a continuous energy-waste model, and a conformal "
                    "lower bound on remaining useful life"
                ),
                "calls": "SustainabilityAgent (in-process; holds a calibrated risk gate)",
                "tools": "estimate-carbon-impact; emits a tool plan for the Orchestrator",
                "guardrail": (
                    "Bypassed entirely for critical devices. Can only optimise "
                    "SCHEDULE_MAINTENANCE and MONITOR_ONLY; URGENT_REPAIR is never "
                    "downgraded or re-timed."
                )
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
    and runs it through the complete workflow
    (HealthAgent -> Router -> DiagnosisAgent -> Sustainability -> Aggregator).

    The agents will automatically use MCP tools if issues are detected.

    Example:
    - GET /devices/pump-001 -> Loads latest pump-001 reading and analyzes it
    - GET /devices/motor-005 -> Loads latest motor-005 reading and analyzes it
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
        initial_state: WorkflowState = _initial_state(request, start_time)

        # Run workflow (async)
        result = await workflow.run(initial_state)

        processing_time_ms = (time.time() - start_time) * 1000

        # Determine path taken
        path = 'health_only' if result['route'] == 'end' else 'full_diagnosis'

        # Build response
        response = _build_response(result, path, processing_time_ms)

        # Track this request in history
        _track_request(result, path)

        logger.info(f"{'='*70}")
        logger.info(f"DEVICE PROCESSING COMPLETE: {path} ({processing_time_ms:.0f}ms)")
        logger.info(f"Agents used: {result.get('agents_used', [])}")
        logger.info(f"MCP tools used: {result.get('mcp_tools_used', [])}")
        logger.info(f"Final Status: {result['health_status']} | Action: {result['action']}")
        if result.get('sust_recommendation'):
            logger.info(
                f"Sustainability: {result['sust_recommendation']} on "
                f"{result.get('sust_scheduled_date')} | risk={result.get('sust_risk_level')}"
            )
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
    3b. SustainabilityAgent: Choose when and how to act (if optimisable)
    4. Aggregator: Combine results

    Returns immediately with final report.
    """
    start_time = time.time()

    try:
        logger.info(f"\n{'='*70}")
        logger.info(f"WORKFLOW START: {request.device_id} ({request.equipment_type})")
        logger.info(f"{'='*70}")

        # Prepare initial state for workflow
        initial_state: WorkflowState = _initial_state(request, start_time)

        # Run workflow (async)
        result = await workflow.run(initial_state)

        processing_time_ms = (time.time() - start_time) * 1000

        # Determine path taken
        path = 'health_only' if result['route'] == 'end' else 'full_diagnosis'

        # Build response
        response = _build_response(result, path, processing_time_ms)

        # Track this request in history
        _track_request(result, path)

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