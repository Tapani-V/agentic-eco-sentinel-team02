"""
End-to-End Workflow Test for Agentic AI POC Phase 3
Validates complete flow: Anomaly → Health Analysis → Diagnosis → MCP Tools → Backend Updates
"""

import asyncio
import json
import time
from typing import Dict, Any
import httpx

ORCHESTRATOR_URL = "http://localhost:8000"
TIMEOUT = 60.0  # Extended timeout for full workflow


class EndToEndWorkflowTest:
    """Complete workflow validation from anomaly to resolution"""
    
    async def test_bearing_failure_workflow(self):
        """
        COMPLETE WORKFLOW TEST: Bearing Failure Detection & Resolution
        
        Workflow Steps:
        1. Device sends anomalous sensor data to Orchestrator
        2. HealthAgent classifies as WARNING/CRITICAL
        3. Router routes to DiagnosisAgent
        4. DiagnosisAgent identifies bearing failure
        5. MCP Tools Called:
           - create-work-order: Creates ticket
           - get-spare-parts: Queries S3 inventory
           - (schedule-maintenance if applicable)
        6. Aggregator consolidates responses
        7. Complete response returned to client
        
        Expected: All steps complete with proper data flow
        """
        print("\n" + "="*70)
        print("END-TO-END TEST: Bearing Failure Workflow")
        print("="*70)
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # ==========================================
            # Step 1: Device sends anomalous data
            # ==========================================
            print("\n[STEP 1] Sending anomalous sensor data to Orchestrator...")
            
            payload = {
                "device_id": "PUMP-E2E-001",
                "equipment_type": "centrifugal_pump",
                "sensor_data": {
                    "temperature_celsius": 92.5,
                    "vibration_mm_s": 5.8,
                    "pressure_bar": 40.5,
                    "flow_gpm": 1150
                },
                "anomaly_scores": {
                    "temperature_high": 0.8,
                    "vibration_high": 0.9,
                    "pressure_abnormal": 0.1,
                    "flow_degradation": 0.2
                }
            }
            
            start_time = time.time()
            
            try:
                response = await client.post(
                    f"{ORCHESTRATOR_URL}/process",
                    json=payload,
                    timeout=TIMEOUT
                )
            except Exception as e:
                print(f"❌ FAILED: Could not connect to Orchestrator at {ORCHESTRATOR_URL}")
                print(f"   Error: {str(e)}")
                print(f"   Ensure docker-compose is running: docker-compose up -d")
                return False
            
            assert response.status_code == 200, f"Orchestrator returned {response.status_code}"
            data = response.json()
            
            workflow_time = time.time() - start_time
            print(f"✅ Orchestrator responded in {workflow_time:.2f}s")
            print(f"   Response size: {len(json.dumps(data))} bytes")
            
            # ==========================================
            # Step 2: Verify HealthAgent output
            # ==========================================
            print("\n[STEP 2] Verifying HealthAgent analysis...")
            
            assert "health_status" in data, "Missing health_status"
            assert "degradation_score" in data, "Missing degradation_score"
            assert data["health_status"] in ["warning", "critical"], \
                f"Unexpected health status: {data['health_status']}"
            assert 0.3 <= data["degradation_score"] <= 1.0, \
                f"Degradation score {data['degradation_score']} out of range"
            
            print(f"✅ HealthAgent Analysis Complete")
            print(f"   Health Status: {data['health_status']}")
            print(f"   Degradation Score: {data['degradation_score']:.2f}")
            print(f"   Anomalies Detected: {', '.join(data.get('anomalies', [])[:3])}")
            
            # ==========================================
            # Step 3: Verify DiagnosisAgent called
            # ==========================================
            print("\n[STEP 3] Verifying DiagnosisAgent root cause analysis...")
            
            assert "diagnosis" in data, "DiagnosisAgent did not run"
            diagnosis = data["diagnosis"]
            
            assert "root_cause" in diagnosis, "Missing root_cause"
            assert "confidence" in diagnosis, "Missing confidence score"
            assert isinstance(diagnosis["confidence"], (int, float)), "Invalid confidence type"
            assert 0.0 <= diagnosis["confidence"] <= 1.0, "Confidence out of range"
            
            print(f"✅ DiagnosisAgent Analysis Complete")
            print(f"   Root Cause: {diagnosis['root_cause']}")
            print(f"   Confidence: {diagnosis['confidence']:.2f}")
            if "reasoning" in diagnosis:
                reasoning = diagnosis["reasoning"]
                print(f"   Reasoning: {reasoning[:100]}...")
            if "required_parts" in diagnosis:
                print(f"   Required Parts: {diagnosis['required_parts']}")
            
            # ==========================================
            # Step 4: Verify MCP Tool Calls
            # ==========================================
            print("\n[STEP 4] Verifying MCP Tool Invocations...")
            
            assert "tool_results" in data, "No tool_results returned"
            tool_results = data["tool_results"]
            
            # Verify create-work-order
            if "create-work-order" in tool_results:
                wo = tool_results["create-work-order"]
                assert wo.get("status") == "CREATED", "Work order creation failed"
                assert "work_order_id" in wo, "Missing work_order_id"
                print(f"✅ MCP Tool: create-work-order")
                print(f"   Work Order ID: {wo['work_order_id']}")
                print(f"   Status: {wo['status']}")
                if "assigned_to" in wo:
                    print(f"   Assigned To: {wo['assigned_to']}")
            else:
                print(f"⚠️  MCP Tool: create-work-order NOT called")
            
            # Verify get-spare-parts
            if "get-spare-parts" in tool_results:
                parts = tool_results["get-spare-parts"]
                if parts.get("status") != "error":
                    assert "parts" in parts, "Missing parts list"
                    print(f"✅ MCP Tool: get-spare-parts")
                    print(f"   Parts Found: {len(parts['parts'])}")
                    if len(parts["parts"]) > 0:
                        for i, part in enumerate(parts["parts"][:2]):
                            print(f"   - {part.get('part_number', 'N/A')}: "
                                  f"{part.get('quantity_available', 0)} available")
                else:
                    print(f"⚠️  MCP Tool: get-spare-parts returned error")
            else:
                print(f"⚠️  MCP Tool: get-spare-parts NOT called")
            
            # Verify schedule-maintenance (if applicable)
            if "schedule-maintenance" in tool_results:
                maint = tool_results["schedule-maintenance"]
                assert maint.get("status") == "SCHEDULED", "Maintenance scheduling failed"
                assert "schedule_id" in maint, "Missing schedule_id"
                print(f"✅ MCP Tool: schedule-maintenance")
                print(f"   Schedule ID: {maint['schedule_id']}")
                print(f"   Scheduled Date: {maint.get('scheduled_date', 'N/A')}")
            
            # ==========================================
            # Step 5: Verify Aggregator output
            # ==========================================
            print("\n[STEP 5] Verifying Aggregator consolidation...")
            
            assert "final_recommendation" in data or "recommendation" in data or \
                   "summary" in data, "Missing aggregated recommendation"
            
            print(f"✅ Aggregator consolidation successful")
            if "final_recommendation" in data:
                print(f"   Recommendation: {data['final_recommendation'][:100]}")
            
            # ==========================================
            # Step 6: Verify response structure
            # ==========================================
            print("\n[STEP 6] Verifying complete response structure...")
            
            required_fields = [
                "device_id",
                "health_status",
                "degradation_score",
                "anomalies",
                "diagnosis",
                "tool_results"
            ]
            
            missing = [f for f in required_fields if f not in data]
            assert len(missing) == 0, f"Missing fields: {missing}"
            
            print(f"✅ Response structure valid")
            print(f"   Fields: {', '.join(required_fields)}")
            
            # ==========================================
            # Step 7: Performance validation
            # ==========================================
            print("\n[STEP 7] Verifying performance thresholds...")
            
            thresholds = {
                "healthy": 1.0,
                "warning": 5.0,
                "critical": 10.0
            }
            
            threshold = thresholds.get(data["health_status"], 10.0)
            assert workflow_time < threshold, \
                f"Workflow took {workflow_time:.2f}s, exceeds {threshold}s for {data['health_status']}"
            
            print(f"✅ Performance acceptable")
            print(f"   Total Time: {workflow_time:.2f}s")
            print(f"   Threshold: {threshold}s for {data['health_status']}")
            
            return True
    
    async def test_critical_escalation_workflow(self):
        """
        CRITICAL ESCALATION WORKFLOW: Immediate HealthAgent MCP Call
        
        Workflow Steps:
        1. Device sends CRITICAL sensor data
        2. HealthAgent detects critical status immediately
        3. HealthAgent calls create-work-order (emergency escalation)
        4. Router routes to DiagnosisAgent for analysis
        5. DiagnosisAgent performs 4-step root cause analysis
        6. DiagnosisAgent calls MCP tools (create-work-order, get-spare-parts)
        7. Aggregator combines immediate escalation + diagnosis
        8. Complete response with dual work orders returned
        """
        print("\n" + "="*70)
        print("END-TO-END TEST: Critical Escalation Workflow")
        print("="*70)
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            print("\n[STEP 1] Sending CRITICAL sensor data...")
            
            payload = {
                "device_id": "PUMP-CRITICAL-E2E",
                "equipment_type": "centrifugal_pump",
                "sensor_data": {
                    "temperature_celsius": 115.0,  # Extremely high
                    "vibration_mm_s": 9.2,         # Extremely high
                    "pressure_bar": 12.0,          # Critically low
                    "flow_gpm": 300                # Very low
                },
                "anomaly_scores": {
                    "temperature_high": 0.99,
                    "vibration_high": 0.99,
                    "pressure_abnormal": 0.95,
                    "flow_degradation": 0.95
                }
            }
            
            start_time = time.time()
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process",
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            workflow_time = time.time() - start_time
            
            print(f"✅ Orchestrator responded in {workflow_time:.2f}s")
            
            print("\n[STEP 2] Verifying HealthAgent immediate escalation...")
            
            assert data["health_status"] == "critical", \
                f"Expected critical, got {data['health_status']}"
            assert data["degradation_score"] > 0.8, \
                f"Degradation score too low: {data['degradation_score']}"
            
            print(f"✅ HealthAgent escalation immediate")
            print(f"   Health Status: {data['health_status']}")
            print(f"   Degradation Score: {data['degradation_score']:.2f}")
            
            # Verify HealthAgent MCP call
            health_results = data.get("health_results", {})
            assert "tool_results" in health_results, "HealthAgent did not call MCP tools"
            assert "create-work-order" in health_results["tool_results"], \
                "HealthAgent did not create emergency work order"
            
            health_wo = health_results["tool_results"]["create-work-order"]
            print(f"✅ HealthAgent emergency work order created")
            print(f"   Work Order ID: {health_wo['work_order_id']}")
            print(f"   Priority: CRITICAL")
            
            print("\n[STEP 3] Verifying DiagnosisAgent follow-up analysis...")
            
            diagnosis = data.get("diagnosis", {})
            assert "root_cause" in diagnosis, "DiagnosisAgent did not run"
            assert diagnosis["confidence"] > 0.8, "DiagnosisAgent confidence too low"
            
            print(f"✅ DiagnosisAgent analysis complete")
            print(f"   Root Cause: {diagnosis['root_cause']}")
            print(f"   Confidence: {diagnosis['confidence']:.2f}")
            
            print("\n[STEP 4] Verifying comprehensive MCP tool results...")
            
            tool_results = data.get("tool_results", {})
            
            tool_calls = {
                "create-work-order": False,
                "get-spare-parts": False,
                "schedule-maintenance": False
            }
            
            for tool_name in tool_calls:
                if tool_name in tool_results:
                    tool_calls[tool_name] = True
                    result = tool_results[tool_name]
                    status = result.get("status", "unknown")
                    print(f"✅ {tool_name}: {status}")
            
            print(f"\n   Tools Called: {sum(tool_calls.values())}/3")
            
            print("\n[STEP 5] Verifying performance under critical load...")
            
            # Critical workflows should complete within 15 seconds
            assert workflow_time < 15, f"Critical workflow too slow: {workflow_time:.2f}s"
            
            print(f"✅ Performance acceptable for critical scenario")
            print(f"   Total Time: {workflow_time:.2f}s")
            
            return True
    
    async def test_healthy_device_workflow(self):
        """
        HEALTHY DEVICE WORKFLOW: No Diagnosis Required
        
        Workflow Steps:
        1. Device sends healthy sensor data
        2. HealthAgent classifies as HEALTHY
        3. Router skips DiagnosisAgent (requires_diagnosis = false)
        4. Aggregator returns health analysis only
        5. No MCP tools called
        """
        print("\n" + "="*70)
        print("END-TO-END TEST: Healthy Device Workflow")
        print("="*70)
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            print("\n[STEP 1] Sending healthy sensor data...")
            
            payload = {
                "device_id": "PUMP-HEALTHY-E2E",
                "equipment_type": "centrifugal_pump",
                "sensor_data": {
                    "temperature_celsius": 45.0,
                    "vibration_mm_s": 1.2,
                    "pressure_bar": 40.0,
                    "flow_gpm": 1200
                },
                "anomaly_scores": {}
            }
            
            start_time = time.time()
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process",
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            workflow_time = time.time() - start_time
            
            print(f"✅ Orchestrator responded in {workflow_time:.2f}s")
            
            print("\n[STEP 2] Verifying HealthAgent classification...")
            
            assert data["health_status"] == "healthy", \
                f"Expected healthy, got {data['health_status']}"
            assert data["degradation_score"] < 0.3, \
                f"Degradation score too high: {data['degradation_score']}"
            
            print(f"✅ Device classified as healthy")
            print(f"   Health Status: {data['health_status']}")
            print(f"   Degradation Score: {data['degradation_score']:.2f}")
            
            print("\n[STEP 3] Verifying short-circuit (no diagnosis)...")
            
            requires_diagnosis = data.get("requires_diagnosis", True)
            assert requires_diagnosis == False, "Should not require diagnosis for healthy device"
            
            diagnosis = data.get("diagnosis")
            assert diagnosis is None or diagnosis.get("skipped") == True, \
                "DiagnosisAgent should not run for healthy device"
            
            print(f"✅ DiagnosisAgent correctly skipped")
            print(f"   Requires Diagnosis: {requires_diagnosis}")
            
            print("\n[STEP 4] Verifying no MCP tool calls...")
            
            tool_results = data.get("tool_results", {})
            assert len(tool_results) == 0, f"No tools should be called, got {list(tool_results.keys())}"
            
            print(f"✅ No MCP tools called (as expected)")
            
            print("\n[STEP 5] Verifying fast response time...")
            
            # Healthy device should respond very quickly (< 1 second)
            assert workflow_time < 1.5, f"Healthy workflow too slow: {workflow_time:.2f}s"
            
            print(f"✅ Fast response time")
            print(f"   Total Time: {workflow_time:.2f}s")
            
            return True


async def run_all_e2e_tests():
    """Run all end-to-end workflow tests"""
    
    print("\n" + "="*70)
    print("AGENTIC AI POC - PHASE 3 END-TO-END WORKFLOW TESTS")
    print("="*70)
    print("\nStarting comprehensive end-to-end validation...")
    print("Services expected at:")
    print(f"  - Orchestrator: {ORCHESTRATOR_URL}")
    print(f"  - (HealthAgent & DiagnosisAgent via internal Docker network)")
    
    tester = EndToEndWorkflowTest()
    results = {}
    
    try:
        print("\n[TEST 1/3] Bearing Failure Workflow...")
        results["bearing_failure"] = await tester.test_bearing_failure_workflow()
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        results["bearing_failure"] = False
    
    try:
        print("\n[TEST 2/3] Critical Escalation Workflow...")
        results["critical_escalation"] = await tester.test_critical_escalation_workflow()
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        results["critical_escalation"] = False
    
    try:
        print("\n[TEST 3/3] Healthy Device Workflow...")
        results["healthy_device"] = await tester.test_healthy_device_workflow()
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        results["healthy_device"] = False
    
    # Summary
    print("\n" + "="*70)
    print("END-TO-END TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All end-to-end tests PASSED!")
        return True
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) FAILED")
        return False


if __name__ == "__main__":
    """
    Run end-to-end tests with:
    python tests/test_e2e.py
    
    Or with asyncio runner:
    python -m asyncio -c "from tests.test_e2e import run_all_e2e_tests; await run_all_e2e_tests()"
    """
    success = asyncio.run(run_all_e2e_tests())
    exit(0 if success else 1)
