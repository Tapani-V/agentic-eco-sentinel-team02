#!/usr/bin/env python3
"""
Test 1: Unit Test for HealthAgent
Tests HealthAgent in isolation
"""

import json
import asyncio
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from src.agents.health_agent import HealthAgent


async def test_health_agent_single_reading():
    """Test HealthAgent with a single reading"""
    
    print("\n" + "="*70)
    print("TEST 1: HealthAgent - Single Reading")
    print("="*70)
    
    agent = HealthAgent()
    
    # Load sample readings
    data_dir = Path('data/generated')
    
    test_cases = [
        'pump-001.json',      # healthy
        'pump-004.json',      # catastrophic
        'motor-001.json',     # healthy
        'motor-004.json',     # intermittent
    ]
    
    for json_file in test_cases:
        file_path = data_dir / json_file
        
        if not file_path.exists():
            print(f"\n⚠️  File not found: {file_path}")
            continue
        
        print(f"\n► Testing {json_file}...")
        
        with open(file_path) as f:
            readings = json.load(f)
        
        if not readings:
            print("  ✗ No readings found")
            continue
        
        # Test with first reading
        first_reading = readings[0]
        device_id = first_reading['device_id']
        
        # Execute HealthAgent
        result = await agent.execute({
            'device_id': device_id,
            'current_reading': first_reading
        })
        
        # Validate result
        print(f"  Device ID: {result.get('device_id')}")
        print(f"  Health State: {result.get('health_state')}")
        print(f"  Degradation Score: {result.get('degradation_score'):.3f}")
        print(f"  Trend: {result.get('trend')}")
        print(f"  Status: {result.get('status')}")
        
        # Assertions
        assert result['status'] == 'completed', f"Expected 'completed', got {result['status']}"
        assert result['device_id'] == device_id, f"Device ID mismatch"
        assert result['health_state'] in ['healthy', 'warning', 'alert', 'critical'], \
            f"Invalid health state: {result['health_state']}"
        assert 0 <= result['degradation_score'] <= 1, \
            f"Degradation score out of range: {result['degradation_score']}"
        
        if result.get('anomalies'):
            print(f"  Anomalies: {result['anomalies']}")
        
        print(f"  ✓ PASS")
    
    print("\n" + "="*70)
    print("✓ HealthAgent Unit Test PASSED")
    print("="*70)


async def test_health_agent_with_history():
    """Test HealthAgent with historical data for trend calculation"""
    
    print("\n" + "="*70)
    print("TEST 2: HealthAgent - With Historical Data (Trend Calculation)")
    print("="*70)
    
    agent = HealthAgent()
    
    # Load readings from a critical device
    with open('data/generated/pump-004.json') as f:
        all_readings = json.load(f)
    
    # Test with multiple readings to see trend
    print(f"\n► Testing trend calculation with {len(all_readings)} readings from pump-004...")
    
    # Test with last 30 readings (showing trends from hour 690-720)
    recent_readings = all_readings[-30:]
    
    result = await agent.execute({
        'device_id': 'pump-004',
        'current_reading': recent_readings[-1],  # Latest reading
        'historical_readings': recent_readings[:-1]  # All except latest
    })
    
    print(f"  Health State: {result.get('health_state')}")
    print(f"  Degradation Score: {result.get('degradation_score'):.3f}")
    print(f"  Trend: {result.get('trend')}")
    
    assert result['trend'] in ['improving', 'stable', 'degrading'], \
        f"Invalid trend: {result['trend']}"
    
    print(f"  ✓ PASS")
    
    print("\n" + "="*70)
    print("✓ HealthAgent Trend Test PASSED")
    print("="*70)


async def main():
    """Run all HealthAgent tests"""
    try:
        await test_health_agent_single_reading()
        await test_health_agent_with_history()
        
        print("\n" + "🎉 "*35)
        print("✓ ALL HEALTHAGENT TESTS PASSED")
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
    asyncio.run(main())
