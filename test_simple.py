#!/usr/bin/env python3
"""Minimal DeviceLoader S3 test"""
from src.utils.device_loader import DeviceLoader
loader = DeviceLoader(bucket='agentic-ai-poc-synthetic-data')
devices = loader.list_available_devices()
print(f'✅ Found {len(devices)} devices')
for d in devices[:5]:
    print(f'  - {d}')
