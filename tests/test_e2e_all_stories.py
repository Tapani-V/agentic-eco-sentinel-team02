#!/usr/bin/env python3
"""
End-to-End Integration Tests for Week 2 Days 5-7

Tests all 4 stories:
1. Happy Path - Device is healthy
2. Simple Issue - Compressor with high vibration + pressure fluctuation
3. Ambiguous - Motor with mixed signals (requires LLM)
4. Emergency - Critical pump failure
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime
from typing import Dict, Any

# Configure test parameters
ORCHESTRATOR_URL = "http://localhost:8000"
HEALTH_AGENT_URL = "http://localhost:8001"
DIAGNOSIS_AGENT_URL = "http://localhost:8002"
TIMEOUT = 30.0

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{text:^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")


def print_success(text: str):
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    print(f"{RED}✗ {text}{RESET}")


def print_info(text: str):
    print(f"{YELLOW}→ {text}{RESET}")


async def check_service_health(url: str, service_name: str) -> bool:
    """Check if a service is healthy."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{url}/health")
            if response.status_code == 200:
                print_success(f"{service_name} is healthy")
                return True
            else:
                print_error(f"{service_name} returned status {response.status_code}")
                return False
    except Exception as e:
        print_error(f"{service_name} health check failed: {e}")
        return False


async def test_services_health() -> bool:
    """Test all services are running."""
    print_header("Checking Service Health")
    
    services = [
        (ORCHESTRATOR_URL, "Orchestrator"),
        (HEALTH_AGENT_URL, "HealthAgent"),
        (DIAGNOSIS_AGENT_URL, "DiagnosisAgent"),
    ]
    
    results = []
    for url, name in services:
        result = await check_service_health(url, name)
        results.append(result)
    
    if all(results):
        print_success("All services are healthy!")
        return True
    else:
        print_error("Some services are not healthy")
        return False


async def story_1_happy_path(client: httpx.AsyncClient) -> Dict[str, Any]:
    """
    Story 1: Happy Path - Device is healthy
    
    Device: Water pump at factory
    - Temperature: 72°C (normal)
    - Flow rate: 850 L/min (normal)
    - Vibration: 2.1 mm/s (normal)
    - Pressure: 4.2 bar (normal)
    
    Expected:
    - health_status: "healthy"
    - action_taken: "none"
    - path: "health_only" (Router skips DiagnosisAgent)
    - No tools called
    """
    print_header("Story 1: Happy Path (Device is Fine)")
    print_info("Device: Water pump, all metrics normal")
    
    request_data = {
        "device_metrics": {
            "device_id": "pump-001",
            "equipment_type": "pump",
            "temperature": 72.0,
            "vibration_level": "normal",
            "pressure": 4.2,
            "flow_rate": 850.0,
            "degradation_score": 0.05,
            "anomalies": []
        }
    }
    
    try:
        response = await client.post(
            f"{ORCHESTRATOR_URL}/process",
            json=request_data,
            timeout=TIMEOUT
        )
        result = response.json()
        
        print(f"\nResponse:")
        print(json.dumps(result, indent=2))
        
        # Validate results
        assert result['health_status'] == 'healthy', "Should be healthy"
        assert result['action_taken'] == 'none', "No action should be taken"
        assert result['path'] == 'health_only', "Should skip DiagnosisAgent"
        
        print_success("Story 1 PASSED: Healthy device correctly identified")
        return result
        
    except Exception as e:
        print_error(f"Story 1 FAILED: {e}")
        return None


async def story_2_simple_issue(client: httpx.AsyncClient) -> Dict[str, Any]:
    """
    Story 2: Simple Issue - Compressor with rule match
    
    Device: Compressor
    - Temperature: 87°C (slightly high)
    - Pressure: fluctuating between 5.5-6.2 bar (unstable)
    - Vibration: 4.2 mm/s (HIGH)
    - Flow: normal
    
    Expected:
    - health_status: "warning"
    - Rule match: "Valve wear" (confidence 0.88 >= 0.85)
    - recommended_action: "SCHEDULE_MAINTENANCE"
    - path: "full_diagnosis"
    - Tool called: schedule-maintenance
    - LLM NOT used (confidence >= 0.85)
    """
    print_header("Story 2: Simple Issue (Compressor Valve Wear)")
    print_info("Device: Compressor with pressure fluctuation + high vibration")
    print_info("Expected: Rule match (0.88 confidence), schedule maintenance")
    
    request_data = {
        "device_metrics": {
            "device_id": "comp-001",
            "equipment_type": "compressor",
            "temperature": 87.0,
            "vibration_level": "high",
            "pressure": 5.8,
            "flow_rate": 95.0,
            "degradation_score": 0.35,
            "anomalies": [
                {"type": "pressure_fluctuation", "value": 5.8},
                {"type": "temperature_elevated", "value": 87}
            ]
        }
    }
    
    try:
        response = await client.post(
            f"{ORCHESTRATOR_URL}/process",
            json=request_data,
            timeout=TIMEOUT
        )
        result = response.json()
        
        print(f"\nResponse:")
        print(json.dumps(result, indent=2))
        
        # Validate results
        assert result['health_status'] == 'warning', "Should be warning"
        assert result['path'] == 'full_diagnosis', "Should call DiagnosisAgent"
        assert result['action_taken'] == 'maintenance_scheduled', "Should schedule maintenance"
        assert result['confidence'] >= 0.85, "Should have high confidence"
        assert not result['llm_used'], "Should NOT use LLM (high confidence)"
        
        print_success("Story 2 PASSED: Compressor valve wear detected with rule match")
        return result
        
    except AssertionError as e:
        print_error(f"Story 2 FAILED: {e}")
        return None
    except Exception as e:
        print_error(f"Story 2 FAILED: {e}")
        return None


async def story_3_ambiguous(client: httpx.AsyncClient) -> Dict[str, Any]:
    """
    Story 3: Ambiguous Path - Motor with mixed signals (LLM needed)
    
    Device: Motor
    - Temperature: 84°C (slightly elevated)
    - Vibration: 2.8 mm/s (borderline)
    - Current draw: normal
    - Sound: slightly higher than baseline
    
    Expected:
    - health_status: "warning"
    - Rule match: "Bearing wear" (confidence 0.72 < 0.85)
    - LLM IS used (confidence < 0.85)
    - LLM returns: "CHECK_PARTS_FIRST"
    - Tools called: get-spare-parts + schedule-maintenance
    - action_taken: "maintenance_scheduled_with_parts"
    """
    print_header("Story 3: Ambiguous Path (LLM Enhanced)")
    print_info("Device: Motor with mixed signals")
    print_info("Expected: Rule confidence 0.72 < 0.85, LLM called, parts checked")
    
    request_data = {
        "device_metrics": {
            "device_id": "motor-005",
            "equipment_type": "motor",
            "temperature": 84.0,
            "vibration_level": "high",
            "pressure": 1.0,
            "flow_rate": 100.0,
            "degradation_score": 0.42,
            "anomalies": [
                {"type": "temperature_elevated", "value": 84},
                {"type": "vibration_high", "value": "medium"}
            ]
        }
    }
    
    try:
        response = await client.post(
            f"{ORCHESTRATOR_URL}/process",
            json=request_data,
            timeout=TIMEOUT
        )
        result = response.json()
        
        print(f"\nResponse:")
        print(json.dumps(result, indent=2))
        
        # Validate results
        assert result['health_status'] == 'warning', "Should be warning"
        assert result['path'] == 'full_diagnosis', "Should call DiagnosisAgent"
        assert result['llm_used'], "LLM should be used (low confidence)"
        assert 'CHECK_PARTS_FIRST' in result['recommended_action'] or \
               'maintenance_scheduled' in result['action_taken'], \
               "Should check parts or schedule"
        
        print_success("Story 3 PASSED: Ambiguous case handled with LLM")
        return result
        
    except AssertionError as e:
        print_error(f"Story 3 FAILED: {e}")
        return None
    except Exception as e:
        print_error(f"Story 3 FAILED: {e}")
        return None


async def story_4_emergency(client: httpx.AsyncClient) -> Dict[str, Any]:
    """
    Story 4: Emergency Path - Critical pump failure
    
    Device: Pump
    - Temperature: 98°C (WAY TOO HIGH!)
    - Vibration: critical level
    - Pressure: fluctuating wildly
    - Pump sounds abnormal
    
    Expected:
    - health_status: "critical"
    - Rule match: "Pump cavitation" (confidence 0.96 >= 0.85)
    - recommended_action: "URGENT_REPAIR"
    - path: "full_diagnosis"
    - Tool called: create-work-order
    - action_taken: "work_order_created"
    - LLM NOT used (confidence >= 0.85)
    """
    print_header("Story 4: Emergency Path (Critical Failure)")
    print_info("Device: Pump with critical temperature and vibration")
    print_info("Expected: High confidence rule, urgent work order")
    
    request_data = {
        "device_metrics": {
            "device_id": "pump-002",
            "equipment_type": "pump",
            "temperature": 98.0,
            "vibration_level": "critical",
            "pressure": 7.2,
            "flow_rate": 45.0,
            "degradation_score": 0.92,
            "anomalies": [
                {"type": "temperature_elevated", "value": 98},
                {"type": "vibration_high", "value": "critical"}
            ]
        }
    }
    
    try:
        response = await client.post(
            f"{ORCHESTRATOR_URL}/process",
            json=request_data,
            timeout=TIMEOUT
        )
        result = response.json()
        
        print(f"\nResponse:")
        print(json.dumps(result, indent=2))
        
        # Validate results
        assert result['health_status'] == 'critical', "Should be critical"
        assert result['path'] == 'full_diagnosis', "Should call DiagnosisAgent"
        assert result['action_taken'] == 'work_order_created', "Should create work order"
        assert result['confidence'] >= 0.85, "Should have high confidence"
        assert not result['llm_used'], "Should NOT use LLM (high confidence)"
        
        print_success("Story 4 PASSED: Emergency case correctly escalated")
        return result
        
    except AssertionError as e:
        print_error(f"Story 4 FAILED: {e}")
        return None
    except Exception as e:
        print_error(f"Story 4 FAILED: {e}")
        return None


async def run_all_tests():
    """Run all end-to-end tests."""
    print(f"\n{BLUE}{'*'*70}{RESET}")
    print(f"{BLUE}* Week 2 Days 5-7: Agent Integration End-to-End Tests *{RESET}")
    print(f"{BLUE}{'*'*70}{RESET}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Orchestrator: {ORCHESTRATOR_URL}")
    print(f"HealthAgent: {HEALTH_AGENT_URL}")
    print(f"DiagnosisAgent: {DIAGNOSIS_AGENT_URL}")
    
    # Check health first
    if not await test_services_health():
        print_error("Services not available. Start with: docker-compose up -d")
        return False
    
    # Run tests
    async with httpx.AsyncClient() as client:
        results = {
            "story_1_happy_path": await story_1_happy_path(client),
            "story_2_simple_issue": await story_2_simple_issue(client),
            "story_3_ambiguous": await story_3_ambiguous(client),
            "story_4_emergency": await story_4_emergency(client),
        }
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for r in results.values() if r is not None)
    total = len(results)
    
    for name, result in results.items():
        if result is not None:
            print_success(f"{name}: PASSED")
        else:
            print_error(f"{name}: FAILED")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print_success("All end-to-end tests PASSED! ✓")
        return True
    else:
        print_error(f"{total - passed} test(s) FAILED")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_error("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
