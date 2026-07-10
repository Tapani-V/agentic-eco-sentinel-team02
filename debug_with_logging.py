#!/usr/bin/env python3
"""Debug with logging enabled"""

import os
import logging
import sys

# Enable all logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

print("=" * 70)
print("IMPORTING DEVICELOADER WITH LOGGING ENABLED")
print("=" * 70)
print()

from src.utils.device_loader import DeviceLoader

print()
print("=" * 70)
print("CREATING DEVICELOADER INSTANCE")
print("=" * 70)
print()

loader = DeviceLoader(bucket='agentic-ai-poc-synthetic-data')

print()
print("=" * 70)
print(f"DEVICELOADER CREATED: use_local={loader.use_local}, s3_client={'✅' if loader.s3_client else '❌'}")
print("=" * 70)
print()

if loader.s3_client:
    print("S3 client is active, testing list_available_devices()...")
    try:
        devices = loader.list_available_devices()
        print(f"✅ SUCCESS: {len(devices)} devices found")
    except Exception as e:
        print(f"❌ FAILED: {e}")
else:
    print("❌ No S3 client created, using local data")
