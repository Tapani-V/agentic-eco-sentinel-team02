#!/usr/bin/env python3
"""Debug DeviceLoader S3 initialization"""

import os
import sys

print("=" * 70)
print("DEBUG: DEVICELOADER INITIALIZATION")
print("=" * 70)
print(f"Current working directory: {os.getcwd()}")
print()

print("Environment variables:")
ca_bundle = os.getenv("AWS_CA_BUNDLE")
aws_profile = os.getenv("AWS_PROFILE")
print(f"  AWS_CA_BUNDLE = {ca_bundle}")
print(f"  AWS_PROFILE = {aws_profile}")
print()

from src.utils.device_loader import DeviceLoader

print("=" * 70)
print("Creating DeviceLoader...")
print("=" * 70)

loader = DeviceLoader(bucket='agentic-ai-poc-synthetic-data')
print(f"✅ DeviceLoader created")
print(f"  use_local: {loader.use_local}")
print(f"  bucket: {loader.bucket}")
print(f"  s3_client exists: {loader.s3_client is not None}")
print()

print("=" * 70)
print("Testing list_available_devices()...")
print("=" * 70)

try:
    devices = loader.list_available_devices()
    print(f"✅ SUCCESS: Found {len(devices)} devices")
    print(f"  Samples: {devices[:5]}")
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
