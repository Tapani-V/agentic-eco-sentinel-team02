"""Configuration constants for the AgentCore Memory Service module.

These constants control timeout behavior, circuit breaker thresholds,
memory entry lifecycle, and analysis parameters used throughout the
memory integration layer.
"""

# --- Timeout & Resilience (Requirement 10.4) ---

MEMORY_OPERATION_TIMEOUT: float = 2.0
"""Maximum time in seconds allowed for a single memory API call.
Operations exceeding this timeout are terminated and treated as failures."""

# --- Circuit Breaker (Requirement 10.3) ---

CIRCUIT_BREAKER_THRESHOLD: int = 3
"""Number of consecutive memory operation failures within a single invocation
before the circuit breaker opens, disabling all memory operations for the
remainder of that invocation."""

# --- Session Context (Requirement 2.5, 4.1) ---

SESSION_CONTEXT_TTL_HOURS: int = 24
"""Time-to-live in hours for session context entries. After this period,
session entries are eligible for expiration."""

# --- Capacity Management (Requirement 2.5) ---

MAX_ENTRIES_PER_DEVICE_NAMESPACE: int = 100
"""Maximum number of memory entries stored per device per namespace.
When this limit is reached, the oldest entries are evicted to make room."""

# --- Work Order Deduplication (Requirement 5.1) ---

DEDUP_WINDOW_HOURS: int = 72
"""Time window in hours for work order deduplication. If an existing work
order with the same device ID and diagnosis category is found within this
window, a new work order creation is skipped."""

# --- Diagnosis Confidence (Requirement 3.1) ---

CONFIDENCE_BOOST_FACTOR: float = 0.1
"""Additive boost applied to the confidence score when a diagnosis pattern
matches a previously stored pattern for the same device."""

MAX_CONFIDENCE: float = 1.0
"""Upper bound for confidence scores. The boosted confidence score is
capped at this value regardless of the number of historical matches."""

# --- Degradation Trend Detection (Requirements 6.2, 6.3) ---

DEGRADATION_TREND_WINDOW: int = 30
"""Number of most recent degradation score entries to retrieve for
trend analysis per device."""

DEGRADATION_TREND_THRESHOLD: int = 3
"""Minimum number of consecutive degradation score increases required
to flag a device as exhibiting an accelerating degradation trend."""
