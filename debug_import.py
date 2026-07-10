#!/usr/bin/env python3
"""Debug what happens during DeviceLoader import"""

import os
import sys

print("BEFORE IMPORT:", flush=True)
print(f"  AWS_CA_BUNDLE = {os.getenv('AWS_CA_BUNDLE')}", flush=True)
print(f"  AWS_PROFILE = {os.getenv('AWS_PROFILE')}", flush=True)
print(flush=True)

print("IMPORTING DeviceLoader...", flush=True)
sys.stdout.flush()

from src.utils.device_loader import DeviceLoader

print("AFTER IMPORT - SUCCESS", flush=True)
