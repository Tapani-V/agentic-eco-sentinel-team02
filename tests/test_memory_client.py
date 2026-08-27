"""Unit tests for MemoryClient class."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.memory.client import MemoryClient
from src.memory.schemas import DiagnosisEntry, WorkOrderEntry


@pytest.fixture
def mock_boto3_clients():
    """Patch boto3.client to return mock clients."""
    with patch("src.memory.client.boto3.client") as mock_client:
        control_client = MagicMock()
        data_client = MagicMock()

        def side_effect(service, **kwargs):
            if service == "bedrock-agentcore-control":
                return control_client
            elif service == "bedrock-agentcore":
                return data_client
            return MagicMock()

        mock_client.side_effect = side_effect
        yield control_client, data_client


@pytest.fixture
def memory_client(mock_boto3_clients):
    """Create a MemoryClient with mocked boto3 clients."""
    return MemoryClient(memory_id="test-memory-id", region="us-east-1")


class TestMemoryClientInit:
    def test_initializes_with_correct_attributes(self, memory_client):
        assert memory_client.memory_id == "test-memory-id"
        assert memory_client.region == "us-east-1"
        assert memory_client.timeout == 2.0

    def test_circuit_breaker_starts_closed(self, memory_client):
        assert memory_client.circuit_breaker.allow_request() is True
        assert memory_client.circuit_breaker.is_open is False


class TestStoreEvent:
    def test_returns_event_id_on_success(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.create_event.return_value = {"eventId": "evt-123"}

        result = asyncio.run(
            memory_client.store_event(
                namespace="device-facts/pump-001/",
                actor_id="pump-001",
                session_id="sess-pump-001-1234567890000000000",
                content=[{"type": "text", "text": "test content"}],
            )
        )
        assert result == "evt-123"

    def test_returns_none_on_failure(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.create_event.side_effect = Exception("Service unavailable")

        result = asyncio.run(
            memory_client.store_event(
                namespace="device-facts/pump-001/",
                actor_id="pump-001",
                session_id="sess-pump-001-1234567890000000000",
                content=[{"type": "text", "text": "test content"}],
            )
        )
        assert result is None

    def test_records_failure_on_circuit_breaker(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.create_event.side_effect = Exception("Failure")

        for _ in range(3):
            asyncio.run(
                memory_client.store_event(
                    namespace="ns", actor_id="a", session_id="s", content=[]
                )
            )

        assert memory_client.circuit_breaker.is_open is True

    def test_skips_when_circuit_breaker_open(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        memory_client.circuit_breaker.is_open = True

        result = asyncio.run(
            memory_client.store_event(
                namespace="ns", actor_id="a", session_id="s", content=[]
            )
        )
        assert result is None
        data_client.create_event.assert_not_called()


class TestRetrieveRecords:
    def test_returns_parsed_records_on_success(
        self, memory_client, mock_boto3_clients
    ):
        _, data_client = mock_boto3_clients
        data_client.retrieve_memory_records.return_value = {
            "memoryRecords": [
                {
                    "memoryRecordId": "rec-001",
                    "contentText": '{"device_id": "pump-001"}',
                    "createdAt": "2024-01-15T10:30:00Z",
                    "score": 0.95,
                    "metadata": {"key": "value"},
                }
            ]
        }

        result = asyncio.run(
            memory_client.retrieve_records(
                namespace="device-facts/pump-001/",
                search_query="device profile",
            )
        )

        assert len(result) == 1
        assert result[0].memory_record_id == "rec-001"
        assert result[0].content_text == '{"device_id": "pump-001"}'
        assert result[0].score == 0.95

    def test_returns_empty_list_on_failure(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.retrieve_memory_records.side_effect = Exception("Timeout")

        result = asyncio.run(
            memory_client.retrieve_records(
                namespace="device-facts/pump-001/",
                search_query="profile",
            )
        )
        assert result == []

    def test_skips_when_circuit_breaker_open(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        memory_client.circuit_breaker.is_open = True

        result = asyncio.run(
            memory_client.retrieve_records(namespace="ns", search_query="q")
        )
        assert result == []
        data_client.retrieve_memory_records.assert_not_called()


class TestConvenienceMethods:
    def test_store_device_fact(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.create_event.return_value = {"eventId": "evt-fact"}

        result = asyncio.run(
            memory_client.store_device_fact(
                device_id="pump-001",
                fact_type="degradation",
                content={"score": 0.75},
            )
        )
        assert result == "evt-fact"

    def test_get_device_profile(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.retrieve_memory_records.return_value = {"memoryRecords": []}

        result = asyncio.run(memory_client.get_device_profile("pump-001"))
        assert result == []

    def test_store_diagnosis(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.create_event.return_value = {"eventId": "evt-diag"}

        diagnosis = DiagnosisEntry(
            device_id="pump-001",
            equipment_type="PUMP",
            anomalies_detected=["high_vibration"],
            diagnosis_result="bearing_wear",
            confidence_score=0.85,
            action_taken="SCHEDULE_MAINTENANCE",
            severity="medium",
            llm_used=True,
            timestamp="2024-01-15T10:30:00Z",
        )
        result = asyncio.run(
            memory_client.store_diagnosis("pump-001", diagnosis)
        )
        assert result == "evt-diag"

    def test_store_work_order(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.create_event.return_value = {"eventId": "evt-wo"}

        work_order = WorkOrderEntry(
            device_id="pump-001",
            work_order_id="WO-12345",
            diagnosis_category="bearing_wear",
            severity="high",
            action_type="URGENT_REPAIR",
            creation_timestamp="2024-01-15T10:30:00Z",
        )
        result = asyncio.run(
            memory_client.store_work_order("pump-001", work_order)
        )
        assert result == "evt-wo"

    def test_check_recent_work_orders(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.retrieve_memory_records.return_value = {"memoryRecords": []}

        result = asyncio.run(
            memory_client.check_recent_work_orders("pump-001")
        )
        assert result == []

    def test_store_session_context(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.create_event.return_value = {"eventId": "evt-sess"}

        result = asyncio.run(
            memory_client.store_session_context(
                session_id="sess-pump-001-1234567890000000000",
                agent_name="HealthAgent",
                content={"health_status": "warning"},
            )
        )
        assert result == "evt-sess"

    def test_get_session_context(self, memory_client, mock_boto3_clients):
        _, data_client = mock_boto3_clients
        data_client.retrieve_memory_records.return_value = {"memoryRecords": []}

        result = asyncio.run(
            memory_client.get_session_context(
                "sess-pump-001-1234567890000000000"
            )
        )
        assert result == []


class TestTimeoutEnforcement:
    def test_store_event_timeout(self, memory_client, mock_boto3_clients):
        """Write operations that exceed timeout return None."""
        _, data_client = mock_boto3_clients

        def slow_call(**kwargs):
            import time
            time.sleep(5)
            return {"eventId": "should-not-arrive"}

        data_client.create_event.side_effect = slow_call
        # Use a very short timeout for testing
        memory_client.timeout = 0.1

        result = asyncio.run(
            memory_client.store_event(
                namespace="ns", actor_id="a", session_id="s", content=[]
            )
        )
        assert result is None
        assert memory_client.circuit_breaker.consecutive_failures == 1

    def test_retrieve_records_timeout(self, memory_client, mock_boto3_clients):
        """Read operations that exceed timeout return empty list."""
        _, data_client = mock_boto3_clients

        def slow_call(**kwargs):
            import time
            time.sleep(5)
            return {"memoryRecords": []}

        data_client.retrieve_memory_records.side_effect = slow_call
        memory_client.timeout = 0.1

        result = asyncio.run(
            memory_client.retrieve_records(namespace="ns", search_query="q")
        )
        assert result == []
        assert memory_client.circuit_breaker.consecutive_failures == 1
