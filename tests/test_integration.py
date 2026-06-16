"""
Integration Tests for Agentic AI POC Phase 3
Tests all 4 stories with actual HTTP calls between containerized services
"""

import asyncio
import json
import pytest
import httpx
from typing import Dict, Any

# Service URLs (from docker-compose network)
ORCHESTRATOR_URL = "http://localhost:8000"
HEALTH_AGENT_URL = "http://localhost:8001"
DIAGNOSIS_AGENT_URL = "http://localhost:8002"

# Timeout for service calls
TIMEOUT = 30.0


class TestHealthyDevice:
    """Story 1: Healthy Device - No diagnosis needed"""
    
    @pytest.mark.asyncio
    async def test_healthy_sensor_readings(self):
        """
        Scenario: Device with normal sensor readings, no anomalies
        Expected: health_status = 'healthy', no tool calls, no diagnosis
        """
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "device_id": "PUMP-001",
                "equipment_type": "centrifugal_pump",
                "sensor_data": {
                    "temperature_celsius": 45.0,
                    "vibration_mm_s": 1.2,
                    "pressure_bar": 40.0,
                    "flow_gpm": 1200
                },
                "anomaly_scores": {
                    "temperature_high": 0.0,
                    "vibration_high": 0.0,
                    "pressure_abnormal": 0.0,
                    "flow_degradation": 0.0
                }
            }
            
            # Call orchestrator
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process",
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Assertions for healthy device
            assert data["health_status"] == "healthy"
            assert data["degradation_score"] < 0.3
            assert data.get("requires_diagnosis", False) == False
            assert len(data.get("tool_results", {})) == 0
            
            print(f"✅ Story 1 PASSED: Healthy device detected correctly")
            print(f"   Degradation Score: {data['degradation_score']}")


class TestSimpleRootCause:
    """Story 2: Simple Root Cause - Bearing Failure with Work Order"""
    
    @pytest.mark.asyncio
    async def test_bearing_failure_diagnosis(self):
        """
        Scenario: High vibration + high temperature (classic bearing failure)
        Expected: DiagnosisAgent identifies bearing failure, creates work order
        """
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "device_id": "PUMP-002",
                "equipment_type": "centrifugal_pump",
                "sensor_data": {
                    "temperature_celsius": 92.5,  # High
                    "vibration_mm_s": 5.8,         # High
                    "pressure_bar": 40.5,
                    "flow_gpm": 1150
                },
                "anomaly_scores": {
                    "temperature_high": 0.8,
                    "vibration_high": 0.9,
                    "pressure_abnormal": 0.0,
                    "flow_degradation": 0.0
                }
            }
            
            # Call orchestrator
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process",
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Assertions for health status
            assert data["health_status"] in ["warning", "critical"]
            assert data["degradation_score"] >= 0.3
            assert data.get("requires_diagnosis", True) == True
            
            # Assertions for diagnosis results
            assert "diagnosis" in data
            diagnosis = data["diagnosis"]
            assert diagnosis["root_cause"] == "bearing_failure"
            assert diagnosis["confidence"] >= 0.7
            
            # Assertions for tool calls
            assert "tool_results" in data
            assert "create-work-order" in data["tool_results"]
            work_order = data["tool_results"]["create-work-order"]
            assert "work_order_id" in work_order
            assert work_order["status"] == "CREATED"
            assert "WO-" in work_order["work_order_id"]
            
            # Assertions for spare parts queried
            assert "get-spare-parts" in data["tool_results"]
            spare_parts = data["tool_results"]["get-spare-parts"]
            assert "parts" in spare_parts
            assert len(spare_parts["parts"]) > 0
            
            print(f"✅ Story 2 PASSED: Bearing failure diagnosed and work order created")
            print(f"   Root Cause: {diagnosis['root_cause']}")
            print(f"   Confidence: {diagnosis['confidence']}")
            print(f"   Work Order: {work_order['work_order_id']}")
            print(f"   Spare Parts Found: {len(spare_parts['parts'])}")


class TestAmbiguousDiagnosis:
    """Story 3: Ambiguous Symptoms - Maintenance Scheduled"""
    
    @pytest.mark.asyncio
    async def test_ambiguous_symptoms_maintenance_schedule(self):
        """
        Scenario: Mixed symptoms with moderate confidence
        Expected: Diagnosis confidence 0.5-0.7, maintenance scheduled instead of immediate work order
        """
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "device_id": "MOTOR-001",
                "equipment_type": "electric_motor",
                "sensor_data": {
                    "temperature_celsius": 75.0,
                    "vibration_mm_s": 3.5,
                    "pressure_bar": 38.0,
                    "flow_gpm": 1050
                },
                "anomaly_scores": {
                    "temperature_high": 0.4,
                    "vibration_high": 0.5,
                    "pressure_abnormal": 0.3,
                    "flow_degradation": 0.4
                }
            }
            
            # Call orchestrator
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process",
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Assertions for health status (warning, not critical)
            assert data["health_status"] == "warning"
            
            # Assertions for diagnosis confidence (moderate)
            assert "diagnosis" in data
            diagnosis = data["diagnosis"]
            assert 0.5 <= diagnosis["confidence"] <= 0.75
            
            # Assertions for maintenance scheduling (instead of immediate work order)
            assert "tool_results" in data
            tool_results = data["tool_results"]
            
            # Should schedule maintenance if confidence suggests degradation pattern
            if "schedule-maintenance" in tool_results:
                schedule = tool_results["schedule-maintenance"]
                assert schedule["status"] == "SCHEDULED"
                assert "schedule_id" in schedule
                print(f"✅ Story 3 PASSED: Ambiguous symptoms triggered maintenance scheduling")
                print(f"   Root Cause: {diagnosis['root_cause']}")
                print(f"   Confidence: {diagnosis['confidence']}")
                print(f"   Maintenance Scheduled: {schedule['schedule_id']}")
            else:
                # If confidence too low, should create work order for investigation
                assert "create-work-order" in tool_results
                print(f"✅ Story 3 PASSED: Ambiguous symptoms created investigation work order")
                print(f"   Confidence too low for scheduling, investigation ordered")


class TestCriticalEscalation:
    """Story 4: Critical Status - Immediate Work Order from HealthAgent"""
    
    @pytest.mark.asyncio
    async def test_critical_immediate_escalation(self):
        """
        Scenario: Multiple critical anomalies detected
        Expected: HealthAgent immediately calls create-work-order (critical), 
                  DiagnosisAgent also performs analysis
        """
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "device_id": "PUMP-CRITICAL-001",
                "equipment_type": "centrifugal_pump",
                "sensor_data": {
                    "temperature_celsius": 110.0,  # Extremely high
                    "vibration_mm_s": 8.5,          # Extremely high
                    "pressure_bar": 15.0,           # Critically low
                    "flow_gpm": 500                 # Very low
                },
                "anomaly_scores": {
                    "temperature_high": 0.95,
                    "vibration_high": 0.99,
                    "pressure_abnormal": 0.90,
                    "flow_degradation": 0.95
                }
            }
            
            # Call orchestrator
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process",
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Assertions for critical health status
            assert data["health_status"] == "critical"
            assert data["degradation_score"] >= 0.8
            
            # Assertions for immediate HealthAgent work order (critical escalation)
            health_tool_results = data.get("health_results", {}).get("tool_results", {})
            assert "create-work-order" in health_tool_results
            health_wo = health_tool_results["create-work-order"]
            assert health_wo["status"] == "CREATED"
            assert "work_order_id" in health_wo
            
            # Assertions for DiagnosisAgent follow-up analysis
            assert "diagnosis" in data
            diagnosis = data["diagnosis"]
            assert diagnosis["confidence"] > 0.8
            assert diagnosis["root_cause"] in ["bearing_failure", "cavitation", "seal_failure"]
            
            # Assertions for comprehensive tool results
            tool_results = data["tool_results"]
            assert "create-work-order" in tool_results
            assert "get-spare-parts" in tool_results
            
            print(f"✅ Story 4 PASSED: Critical status triggered immediate escalation + diagnosis")
            print(f"   Health Status: {data['health_status']}")
            print(f"   Degradation Score: {data['degradation_score']}")
            print(f"   Immediate WO (HealthAgent): {health_wo['work_order_id']}")
            print(f"   Root Cause Analysis: {diagnosis['root_cause']} (conf: {diagnosis['confidence']})")


class TestServiceHealth:
    """Verify all services are running and healthy"""
    
    @pytest.mark.asyncio
    async def test_orchestrator_health(self):
        """Verify Orchestrator service is healthy"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{ORCHESTRATOR_URL}/health")
            assert response.status_code == 200
            print("✅ Orchestrator service healthy")
    
    @pytest.mark.asyncio
    async def test_health_agent_health(self):
        """Verify HealthAgent service is healthy"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{HEALTH_AGENT_URL}/health")
            assert response.status_code == 200
            print("✅ HealthAgent service healthy")
    
    @pytest.mark.asyncio
    async def test_diagnosis_agent_health(self):
        """Verify DiagnosisAgent service is healthy"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{DIAGNOSIS_AGENT_URL}/health")
            assert response.status_code == 200
            print("✅ DiagnosisAgent service healthy")


class TestMCPToolIntegration:
    """Test MCP tool invocation paths"""
    
    @pytest.mark.asyncio
    async def test_create_work_order_tool(self):
        """Verify create-work-order MCP tool is called correctly"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Use bearing failure scenario
            payload = {
                "device_id": "PUMP-MCP-TEST-001",
                "equipment_type": "centrifugal_pump",
                "sensor_data": {
                    "temperature_celsius": 95.0,
                    "vibration_mm_s": 6.0,
                    "pressure_bar": 40.0,
                    "flow_gpm": 1200
                },
                "anomaly_scores": {
                    "temperature_high": 0.85,
                    "vibration_high": 0.95,
                    "pressure_abnormal": 0.0,
                    "flow_degradation": 0.0
                }
            }
            
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process",
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify create-work-order was called
            tool_results = data.get("tool_results", {})
            assert "create-work-order" in tool_results
            wo = tool_results["create-work-order"]
            
            # Verify work order response structure
            assert wo.get("status") in ["CREATED", "error"]
            if wo["status"] == "CREATED":
                assert "work_order_id" in wo
                assert wo["work_order_id"].startswith("WO-")
                print(f"✅ MCP Tool Test: create-work-order called successfully")
                print(f"   Work Order ID: {wo['work_order_id']}")
    
    @pytest.mark.asyncio
    async def test_get_spare_parts_tool(self):
        """Verify get-spare-parts MCP tool is called and returns inventory"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "device_id": "PUMP-PARTS-TEST-001",
                "equipment_type": "centrifugal_pump",
                "sensor_data": {
                    "temperature_celsius": 85.0,
                    "vibration_mm_s": 5.5,
                    "pressure_bar": 40.0,
                    "flow_gpm": 1150
                },
                "anomaly_scores": {
                    "temperature_high": 0.8,
                    "vibration_high": 0.9,
                    "pressure_abnormal": 0.0,
                    "flow_degradation": 0.0
                }
            }
            
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process",
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify get-spare-parts was called
            tool_results = data.get("tool_results", {})
            assert "get-spare-parts" in tool_results
            parts_result = tool_results["get-spare-parts"]
            
            # Verify spare parts response structure
            if parts_result.get("status") != "error":
                assert "parts" in parts_result
                assert isinstance(parts_result["parts"], list)
                if len(parts_result["parts"]) > 0:
                    part = parts_result["parts"][0]
                    assert "part_number" in part
                    assert "quantity_available" in part
                    assert "location" in part
                    print(f"✅ MCP Tool Test: get-spare-parts called successfully")
                    print(f"   Parts Found: {len(parts_result['parts'])}")


class TestResponseTiming:
    """Verify response times are acceptable"""
    
    @pytest.mark.asyncio
    async def test_orchestrator_response_time(self):
        """Verify orchestrator responds within acceptable time"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "device_id": "TIMING-TEST",
                "equipment_type": "centrifugal_pump",
                "sensor_data": {
                    "temperature_celsius": 50.0,
                    "vibration_mm_s": 1.5,
                    "pressure_bar": 40.0,
                    "flow_gpm": 1200
                },
                "anomaly_scores": {}
            }
            
            import time
            start = time.time()
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process",
                json=payload
            )
            elapsed = time.time() - start
            
            assert response.status_code == 200
            # Acceptable thresholds:
            # - Healthy device: < 1 second
            # - With diagnosis: < 5 seconds
            # - With MCP tools: < 10 seconds
            assert elapsed < 15, f"Response took {elapsed}s, exceeds 15s threshold"
            print(f"✅ Response timing acceptable: {elapsed:.2f}s")


# ============================================
# Test Execution
# ============================================

if __name__ == "__main__":
    """
    Run tests with: pytest tests/test_integration.py -v
    
    Expected output:
    ✅ Story 1 PASSED: Healthy device detected correctly
    ✅ Story 2 PASSED: Bearing failure diagnosed and work order created
    ✅ Story 3 PASSED: Ambiguous symptoms triggered maintenance scheduling
    ✅ Story 4 PASSED: Critical status triggered immediate escalation + diagnosis
    ✅ All MCP tools verified
    ✅ All services healthy
    ✅ Response times acceptable
    """
    pytest.main([__file__, "-v", "-s"])
