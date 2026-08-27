"""MemoryClient for AgentCore Memory operations.

Unified client wrapping both the control-plane (bedrock-agentcore-control)
and data-plane (bedrock-agentcore) boto3 APIs behind a simple async interface.

Every API call is guarded by a circuit breaker and enforces a configurable
timeout (default 2 seconds). Write failures return None; read failures
return an empty list — ensuring the core workflow never blocks on memory
service issues.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3

from src.memory.circuit_breaker import CircuitBreaker
from src.memory.config import DEDUP_WINDOW_HOURS, MEMORY_OPERATION_TIMEOUT
from src.memory.schemas import DiagnosisEntry, MemoryRecord, WorkOrderEntry

logger = logging.getLogger(__name__)


class MemoryClient:
    """Unified client for AgentCore Memory operations.

    Uses two boto3 clients:
    - bedrock-agentcore-control: provisioning (create_memory, get_memory)
    - bedrock-agentcore: data operations (create_event, retrieve_memory_records)
    """

    def __init__(
        self,
        memory_id: str,
        region: str = "eu-central-1",
        timeout: float = MEMORY_OPERATION_TIMEOUT,
    ):
        """Initialize with memory resource ID and configuration.

        Args:
            memory_id: The AgentCore Memory resource identifier.
            region: AWS region for the memory service.
            timeout: Maximum seconds allowed per API call.
        """
        self.memory_id = memory_id
        self.region = region
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker()

        # Control-plane client (provisioning)
        self._control_client = boto3.client(
            "bedrock-agentcore-control", region_name=region
        )
        # Data-plane client (read/write operations)
        self._data_client = boto3.client("bedrock-agentcore", region_name=region)

    # ------------------------------------------------------------------
    # Core methods
    # ------------------------------------------------------------------

    async def store_event(
        self,
        namespace: str,
        actor_id: str,
        session_id: str,
        content: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Store a memory event (conversation-style payload).

        Returns event ID on success, None on failure (graceful degradation).
        """
        if not self.circuit_breaker.allow_request():
            logger.warning(
                "Circuit breaker open — skipping store_event for namespace=%s",
                namespace,
            )
            return None

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._data_client.create_event,
                    memoryId=self.memory_id,
                    actorId=actor_id,
                    sessionId=session_id,
                    namespace=namespace,
                    content=content,
                ),
                timeout=self.timeout,
            )
            self.circuit_breaker.record_success()
            return response.get("eventId")
        except Exception as exc:
            self.circuit_breaker.record_failure()
            logger.warning(
                "Memory store_event failed (namespace=%s): %s", namespace, exc
            )
            return None

    async def retrieve_records(
        self,
        namespace: str,
        search_query: str,
        metadata_filters: Optional[List[Dict[str, Any]]] = None,
        max_results: int = 10,
    ) -> List[MemoryRecord]:
        """Retrieve memory records by namespace and search criteria.

        Returns empty list on failure (graceful degradation).
        """
        if not self.circuit_breaker.allow_request():
            logger.warning(
                "Circuit breaker open — skipping retrieve_records for namespace=%s",
                namespace,
            )
            return []

        try:
            kwargs: Dict[str, Any] = {
                "memoryId": self.memory_id,
                "namespace": namespace,
                "query": search_query,
                "maxResults": max_results,
            }
            if metadata_filters:
                kwargs["metadataFilters"] = metadata_filters

            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._data_client.retrieve_memory_records, **kwargs
                ),
                timeout=self.timeout,
            )
            self.circuit_breaker.record_success()
            return self._parse_records(response, namespace)
        except Exception as exc:
            self.circuit_breaker.record_failure()
            logger.warning(
                "Memory retrieve_records failed (namespace=%s): %s", namespace, exc
            )
            return []

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    async def store_device_fact(
        self, device_id: str, fact_type: str, content: Dict[str, Any]
    ) -> Optional[str]:
        """Convenience: store a fact in device-facts namespace."""
        namespace = f"device-facts/{device_id}/"
        payload = [{"type": "text", "text": json.dumps(content)}]
        return await self.store_event(
            namespace=namespace,
            actor_id=device_id,
            session_id=f"fact-{device_id}-{fact_type}",
            content=payload,
        )

    async def get_device_profile(
        self, device_id: str, max_entries: int = 10
    ) -> List[MemoryRecord]:
        """Convenience: retrieve device profile from device-facts namespace."""
        namespace = f"device-facts/{device_id}/"
        return await self.retrieve_records(
            namespace=namespace,
            search_query=f"device profile for {device_id}",
            max_results=max_entries,
        )

    async def store_diagnosis(
        self, device_id: str, diagnosis: DiagnosisEntry
    ) -> Optional[str]:
        """Convenience: store diagnosis in diagnosis-history namespace."""
        namespace = f"diagnosis-history/{device_id}/"
        payload = [{"type": "text", "text": diagnosis.model_dump_json()}]
        return await self.store_event(
            namespace=namespace,
            actor_id=device_id,
            session_id=f"diag-{device_id}-{diagnosis.timestamp}",
            content=payload,
        )

    async def get_diagnosis_history(
        self, device_id: str, limit: int = 10
    ) -> List[MemoryRecord]:
        """Convenience: retrieve past diagnoses for a device."""
        namespace = f"diagnosis-history/{device_id}/"
        return await self.retrieve_records(
            namespace=namespace,
            search_query=f"diagnosis history for {device_id}",
            max_results=limit,
        )

    async def store_work_order(
        self, device_id: str, work_order: WorkOrderEntry
    ) -> Optional[str]:
        """Convenience: store work order in maintenance-actions namespace."""
        namespace = f"maintenance-actions/{device_id}/"
        payload = [{"type": "text", "text": work_order.model_dump_json()}]
        return await self.store_event(
            namespace=namespace,
            actor_id=device_id,
            session_id=f"wo-{device_id}-{work_order.work_order_id}",
            content=payload,
        )

    async def check_recent_work_orders(
        self, device_id: str, hours: int = DEDUP_WINDOW_HOURS
    ) -> List[MemoryRecord]:
        """Convenience: check for duplicate work orders within time window."""
        namespace = f"maintenance-actions/{device_id}/"
        return await self.retrieve_records(
            namespace=namespace,
            search_query=f"work orders for {device_id} in last {hours} hours",
            max_results=10,
        )

    async def store_session_context(
        self, session_id: str, agent_name: str, content: Dict[str, Any]
    ) -> Optional[str]:
        """Convenience: store session-scoped context."""
        namespace = f"session-context/{session_id}/"
        payload = [{"type": "text", "text": json.dumps(content)}]
        return await self.store_event(
            namespace=namespace,
            actor_id=agent_name,
            session_id=session_id,
            content=payload,
        )

    async def get_session_context(
        self, session_id: str
    ) -> List[MemoryRecord]:
        """Convenience: retrieve all session context entries."""
        namespace = f"session-context/{session_id}/"
        return await self.retrieve_records(
            namespace=namespace,
            search_query=f"session context for {session_id}",
            max_results=10,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_records(response: Dict[str, Any], namespace: str) -> List[MemoryRecord]:
        """Parse raw API response into MemoryRecord models."""
        records: List[MemoryRecord] = []
        raw_records = response.get("memoryRecords", [])
        for raw in raw_records:
            try:
                record = MemoryRecord(
                    memory_record_id=raw.get("memoryRecordId", ""),
                    content_text=raw.get("contentText", ""),
                    namespace=namespace,
                    created_at=raw.get(
                        "createdAt", datetime.utcnow().isoformat()
                    ),
                    score=raw.get("score"),
                    metadata=raw.get("metadata", {}),
                )
                records.append(record)
            except Exception as parse_err:
                logger.warning("Failed to parse memory record: %s", parse_err)
        return records
