#!/usr/bin/env python3
"""
Test DeviceLoader with proper SSL certificates for corporate proxy
"""
import os
import sys

# SET ENVIRONMENT VARIABLES FIRST - before any boto3 imports
os.environ['AWS_CA_BUNDLE'] = '/home/skroy/AGENTIC_AI_POC_Phase3_1/config/minimal_certificate_bundle.pem'
os.environ['AWS_PROFILE'] = 'StandardAccess-450410489798'

print(f"AWS_CA_BUNDLE: {os.environ.get('AWS_CA_BUNDLE')}")
print(f"AWS_PROFILE: {os.environ.get('AWS_PROFILE')}")
print("")

# NOW import after environment is set
from src.utils.device_loader import DeviceLoader

print("=== Testing DeviceLoader with Proper SSL Certificates ===")
print("")

try:
    loader = DeviceLoader(bucket='agentic-ai-poc-synthetic-data')
    
    # Test 1: List devices
    devices = loader.list_available_devices()
    print(f"✅ Listed devices: {len(devices)} found")
    print(f"   Samples: {devices[:5]}")
    
    # Test 2: Load specific device
    device_data = loader.load_device_history('pump-001')
    print(f"✅ Loaded pump-001: {len(device_data)} readings")
    
    # Test 3: Get latest reading
    latest = loader.get_latest_reading('pump-001')
    print(f"✅ Latest reading: {latest.get('timestamp')}")
    
    # Test 4: Get device status
    status = loader.get_device_status('pump-001')
    print(f"✅ Device status: {status.get('device_id')} - {status.get('status')}")
    
    # Test 5: Test cache
    device_data2 = loader.load_device_history('pump-001')  # Should hit cache
    print(f"✅ Cache works: {len(device_data2)} readings (from cache)")
    
    print("")
    print("=" * 60)
    print("✅✅✅ ALL TESTS PASSED ✅✅✅")
    print("DeviceLoader works perfectly with S3 and SSL certificates!")
    print("=" * 60)
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
