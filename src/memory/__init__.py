"""Memory module for AgentCore Memory Service integration.

Provides persistent long-term memory and session-scoped short-term memory
for the Agentic Eco Sentinel multi-agent system via AWS Bedrock AgentCore.

Public API:
- MemoryClient: Unified client for memory read/write operations
- CircuitBreaker: Resilience pattern for memory service outages
- Schema models: DegradationEntry, DiagnosisEntry, WorkOrderEntry,
  SessionContextEntry, MemoryRecord
- generate_session_id: Deterministic session ID generation
- Config constants: Timeout, threshold, and capacity settings
"""

from src.memory.circuit_breaker import CircuitBreaker
from src.memory.schemas import (
    DegradationEntry,
    DiagnosisEntry,
    MemoryRecord,
    SessionContextEntry,
    WorkOrderEntry,
    generate_session_id,
)
from src.memory.config import (
    CIRCUIT_BREAKER_THRESHOLD,
    CONFIDENCE_BOOST_FACTOR,
    DEDUP_WINDOW_HOURS,
    DEGRADATION_TREND_THRESHOLD,
    DEGRADATION_TREND_WINDOW,
    MAX_CONFIDENCE,
    MAX_ENTRIES_PER_DEVICE_NAMESPACE,
    MEMORY_OPERATION_TIMEOUT,
    SESSION_CONTEXT_TTL_HOURS,
)

from src.memory.client import MemoryClient

__all__ = [
    # Client
    "MemoryClient",
    # Resilience
    "CircuitBreaker",
    # Schema models
    "DegradationEntry",
    "DiagnosisEntry",
    "WorkOrderEntry",
    "SessionContextEntry",
    "MemoryRecord",
    # Utilities
    "generate_session_id",
    # Config constants
    "MEMORY_OPERATION_TIMEOUT",
    "CIRCUIT_BREAKER_THRESHOLD",
    "SESSION_CONTEXT_TTL_HOURS",
    "MAX_ENTRIES_PER_DEVICE_NAMESPACE",
    "DEDUP_WINDOW_HOURS",
    "CONFIDENCE_BOOST_FACTOR",
    "MAX_CONFIDENCE",
    "DEGRADATION_TREND_WINDOW",
    "DEGRADATION_TREND_THRESHOLD",
]
