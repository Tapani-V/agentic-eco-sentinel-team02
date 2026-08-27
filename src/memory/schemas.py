"""Pydantic schemas for AgentCore Memory entries.

Defines the data models for each memory namespace and a utility function
for generating deterministic session IDs.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class DegradationEntry(BaseModel):
    """Stored in device-facts namespace when HealthAgent computes a score."""

    device_id: str
    equipment_type: str
    degradation_score: float = Field(ge=0.0, le=1.0)
    health_status: str  # healthy | warning | critical
    anomaly_count: int
    anomalies: List[str]
    timestamp: str  # ISO 8601


class DiagnosisEntry(BaseModel):
    """Stored in diagnosis-history namespace after DiagnosisAgent completes."""

    device_id: str
    equipment_type: str
    anomalies_detected: List[str]
    diagnosis_result: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    action_taken: str
    severity: str
    llm_used: bool
    timestamp: str  # ISO 8601


class WorkOrderEntry(BaseModel):
    """Stored in maintenance-actions namespace when a work order is created."""

    device_id: str
    work_order_id: str
    diagnosis_category: str
    severity: str
    action_type: str  # URGENT_REPAIR | SCHEDULE_MAINTENANCE
    creation_timestamp: str  # ISO 8601


class SessionContextEntry(BaseModel):
    """Stored in session-context namespace for cross-agent sharing."""

    session_id: str
    agent_name: str  # HealthAgent | DiagnosisAgent
    device_id: str
    payload: dict  # Full agent output
    timestamp: str  # ISO 8601
    completed: bool = False


class MemoryRecord(BaseModel):
    """Represents a record retrieved from AgentCore Memory."""

    memory_record_id: str
    content_text: str
    namespace: str
    created_at: datetime
    score: Optional[float] = None
    metadata: dict = Field(default_factory=dict)


def generate_session_id(device_id: str, invocation_timestamp: float) -> str:
    """Generate stable session ID for a workflow invocation.

    Format: sess-{device_id}-{timestamp_ms}
    Must be >= 33 chars for AgentCore compatibility.
    """
    ts_ms = int(invocation_timestamp * 1000)
    session_id = f"sess-{device_id}-{ts_ms}"
    # Pad if needed to meet 33-char minimum
    if len(session_id) < 33:
        session_id = session_id.ljust(33, "0")
    return session_id
