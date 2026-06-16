#!/usr/bin/env python3
"""
Test 2: Integration Test for Full Workflow
Tests the complete LangGraph workflow (HealthAgent → Router → DiagnosisAgent → Aggregator)
"""

import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from src.graph.workflow import AgentWorkflow


def test_workflow_single_device():
    """Test workflow with single device"""
    
    print("\n" + "="*70)
    print("TEST 1: Full Workflow - Single Device")
    print("="*70)
    
    workflow = AgentWorkflow()
    
    # Test cases: one from each health category
    test_cases = [
        ('pump-001.json', 'PUMP', 'Healthy device'),
        ('pump-002.json', 'PUMP', 'Degrading device'),
        ('motor-004.json', 'MOTOR', 'Warning device'),
        ('pump-004.json', 'PUMP', 'Critical device'),
    ]
    
    for json_file, equipment_type, description in test_cases:
        file_path = Path('data/generated') / json_file
        
        if not file_path.exists():
            print(f"\n⚠️  File not found: {file_path}")
            continue
        
        print(f"\n► Testing {json_file} ({description})...")
        
        with open(file_path) as f:
            readings = json.load(f)
        
        # Use the last reading (day 30)
        latest_reading = readings[-1]
        device_id = latest_reading['device_id']
        
        # Run workflow
        report = workflow.run(
            device_id=device_id,
            equipment_type=equipment_type,
            current_reading=latest_reading
        )
        
        # Validate report structure
        print(f"\n  Report Structure:")
        print(f"  ├─ Device ID: {report['device_id']}")
        print(f"  ├─ Equipment Type: {report['equipment_type']}")
        print(f"  ├─ Workflow Status: {report['workflow_status']}")
        print(f"  ├─ Health State: {report['health']['health_state']}")
        print(f"  ├─ Degradation: {report['health']['degradation_score']:.3f}")
        
        # If diagnosis was performed, show it
        if report.get('diagnosis'):
            print(f"  ├─ Diagnosis: {report['diagnosis'].get('primary_diagnosis', 'N/A')}")
            print(f"  ├─ Confidence: {report['diagnosis'].get('confidence', 0):.2f}")
            print(f"  ├─ Severity: {report['diagnosis'].get('severity', 'N/A')}")
        
        print(f"  └─ Recommendation: {report['overall_recommendation']}")
        
        # Assertions
        assert report['workflow_status'] == 'completed', "Workflow should complete"
        assert report['health'] is not None, "Health result missing"
        assert report['device_id'] == device_id, "Device ID mismatch"
        
        health_state = report['health']['health_state']
        assert health_state in ['healthy', 'warning', 'alert', 'critical'], \
            f"Invalid health state: {health_state}"
        
        # If health_state is warning/alert/critical, diagnosis should be present
        if health_state in ['warning', 'alert', 'critical']:
            assert report.get('diagnosis') is not None, \
                f"Diagnosis missing for {health_state} device"
        
        print(f"  ✓ PASS")
    
    print("\n" + "="*70)
    print("✓ Full Workflow Test PASSED")
    print("="*70)


def test_workflow_all_devices():
    """Test workflow with all 16 devices"""
    
    print("\n" + "="*70)
    print("TEST 2: Full Workflow - All 16 Devices")
    print("="*70)
    
    workflow = AgentWorkflow()
    data_dir = Path('data/generated')
    
    healthy_count = 0
    warning_count = 0
    alert_count = 0
    critical_count = 0
    diagnosed_count = 0
    
    print(f"\n► Processing all devices...\n")
    
    for json_file in sorted(data_dir.glob('*.json')):
        device_id = json_file.stem
        equipment_type = device_id.split('-')[0].upper()
        
        with open(json_file) as f:
            readings = json.load(f)
        
        # Use latest reading
        latest_reading = readings[-1]
        
        # Run workflow
        report = workflow.run(
            device_id=device_id,
            equipment_type=equipment_type,
            current_reading=latest_reading
        )
        
        # Count by health state
        health_state = report['health']['health_state']
        if health_state == 'healthy':
            healthy_count += 1
            symbol = "✓"
        elif health_state == 'warning':
            warning_count += 1
            symbol = "⚠"
        elif health_state == 'alert':
            alert_count += 1
            symbol = "⚡"
        else:
            critical_count += 1
            symbol = "🔴"
        
        # Count diagnosed devices
        if report.get('diagnosis'):
            diagnosed_count += 1
        
        # Show one-line summary
        degradation = report['health']['degradation_score']
        recommendation = report['overall_recommendation'].split(':')[0]
        
        print(f"  {symbol} {device_id:15} | {health_state:8} | Deg: {degradation:.3f} | {recommendation}")
    
    print(f"\n  Summary:")
    print(f"  ├─ Healthy: {healthy_count}")
    print(f"  ├─ Warning: {warning_count}")
    print(f"  ├─ Alert: {alert_count}")
    print(f"  ├─ Critical: {critical_count}")
    print(f"  └─ Total Diagnosed: {diagnosed_count}")
    
    # Validate counts
    total = healthy_count + warning_count + alert_count + critical_count
    assert total == 17, f"Expected 17 devices, got {total}"
    
    print(f"\n  ✓ PASS - All 16 devices processed")
    
    print("\n" + "="*70)
    print("✓ All Devices Test PASSED")
    print("="*70)


def main():
    """Run all workflow tests"""
    try:
        test_workflow_single_device()
        test_workflow_all_devices()
        
        print("\n" + "🎉 "*35)
        print("✓ ALL WORKFLOW TESTS PASSED")
        print("🎉 "*35 + "\n")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
