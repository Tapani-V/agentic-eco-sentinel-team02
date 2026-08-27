"""Circuit breaker for memory operations.

Protects the workflow from cascading failures when the AgentCore Memory
service is unavailable. Opens after a configurable number of consecutive
failures (default 3), disabling memory operations for the remainder of
the current Lambda invocation.
"""

import logging

from src.memory.config import CIRCUIT_BREAKER_THRESHOLD

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker for memory operations.

    Opens after consecutive failures within a single invocation,
    disabling memory operations for the remainder of that invocation.
    A single success at any point resets the failure counter to zero.
    """

    def __init__(self, failure_threshold: int = CIRCUIT_BREAKER_THRESHOLD):
        self.failure_threshold = failure_threshold
        self.consecutive_failures = 0
        self.is_open = False

    def record_success(self) -> None:
        """Reset failure counter on successful operation."""
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        """Increment failure counter; open circuit if threshold reached."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.is_open = True
            logger.error(
                "Circuit breaker OPEN: %d consecutive memory operation failures. "
                "Memory operations disabled for remainder of this invocation.",
                self.consecutive_failures,
            )

    def allow_request(self) -> bool:
        """Check if operations are currently allowed.

        Returns True when the circuit is closed (operations allowed),
        False when open (operations blocked).
        """
        return not self.is_open

    def reset(self) -> None:
        """Reset circuit breaker state (e.g. for a new invocation)."""
        self.consecutive_failures = 0
        self.is_open = False
