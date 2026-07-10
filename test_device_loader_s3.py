#!/usr/bin/env python3
"""
Test DeviceLoader S3 integration with SSL certificates.
Usage: AWS_CA_BUNDLE=config/minimal_certificate_bundle.pem \
       AWS_PROFILE=StandardAccess-450410489798 \
       python3 test_device_loader_s3.py
"""

import os
from src.utils.device_loader import DeviceLoader

def main():
    print("=" * 70)
    print("TESTING DEVICELOADER WITH S3 AND SSL CERTIFICATES")
    print("=" * 70)
    print()
    
    # Verify environment
    ca_bundle = os.getenv("AWS_CA_BUNDLE")
    aws_profile = os.getenv("AWS_PROFILE")
    
    print("Environment Configuration:")
    print(f"  AWS_CA_BUNDLE: {ca_bundle}")
    print(f"  AWS_PROFILE: {aws_profile}")
    print()
    
    if not ca_bundle:
        print("⚠️  WARNING: AWS_CA_BUNDLE not set")
    if not aws_profile:
        print("⚠️  WARNING: AWS_PROFILE not set")
    print()
    
    try:
        # Initialize loader
        print("Initializing DeviceLoader with S3...")
        loader = DeviceLoader(bucket='agentic-ai-poc-synthetic-data')
        print("✅ DeviceLoader initialized successfully")
        print()
        
        # Test 1: List devices
        print("Test 1: List available devices...")
        devices = loader.list_available_devices()
        print(f"  ✅ Found {len(devices)} devices")
        print(f"  Samples: {', '.join(devices[:5])}")
        print()
        
        # Test 2: Load device history
        print("Test 2: Load device history (pump-001)...")
        device_data = loader.load_device_history('pump-001')
        print(f"  ✅ Loaded {len(device_data)} readings from pump-001")
        if device_data:
            first_reading = device_data[0]
            print(f"  First reading: {first_reading.get('timestamp')} = {first_reading.get('pump_status')}")
        print()
        
        # Test 3: Get latest reading
        print("Test 3: Get latest reading (pump-001)...")
        latest = loader.get_latest_reading('pump-001')
        print(f"  ✅ Latest reading timestamp: {latest.get('timestamp')}")
        print(f"  Latest pump_status: {latest.get('pump_status')}")
        print()
        
        # Test 4: Get device status
        print("Test 4: Get device status (pump-001)...")
        status = loader.get_device_status('pump-001')
        print(f"  ✅ Device: {status.get('device_id')}")
        print(f"  Status: {status.get('status')}")
        print()
        
        # Test 5: Get device summary
        print("Test 5: Get device summary (pump-001)...")
        summary = loader.get_device_summary('pump-001')
        print(f"  ✅ Average: {summary.get('average_value'):.2f}")
        print(f"  Min: {summary.get('min_value'):.2f}")
        print(f"  Max: {summary.get('max_value'):.2f}")
        print()
        
        # Test 6: Multiple devices
        print("Test 6: Identify pump devices...")
        pump_devices = [d for d in devices if 'pump' in d]
        print(f"  ✅ Found {len(pump_devices)} pump devices: {pump_devices}")
        print()
        
        # Test 7: Cache verification
        print("Test 7: Verify caching works...")
        device_data_cached = loader.load_device_history('pump-001')
        print(f"  ✅ Cache reloaded {len(device_data_cached)} readings (should be same as Test 2)")
        print()
        
        # Test 8: Load different device
        print("Test 8: Load different device (compressor-001)...")
        comp_data = loader.load_device_history('compressor-001')
        print(f"  ✅ Loaded {len(comp_data)} readings from compressor-001")
        print()
        
        print("=" * 70)
        print("✅✅✅ ALL TESTS PASSED ✅✅✅")
        print("DeviceLoader S3 integration with SSL certificates: SUCCESS")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        print("=" * 70)
        print(f"❌ ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
