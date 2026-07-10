#!/usr/bin/env python3
"""Debug DeviceLoader S3 path resolution"""

import os
import sys

print("=" * 70)
print("DEBUG: PATH RESOLUTION")
print("=" * 70)
print(f"Current working directory: {os.getcwd()}")
print(f"Script location: {os.path.abspath(__file__)}")
print()

print("Environment variables:")
ca_bundle = os.getenv("AWS_CA_BUNDLE")
aws_profile = os.getenv("AWS_PROFILE")
print(f"  AWS_CA_BUNDLE = {ca_bundle}")
print(f"  AWS_PROFILE = {aws_profile}")
print()

if ca_bundle:
    print(f"CA Bundle path resolution:")
    print(f"  Raw: {ca_bundle}")
    print(f"  Exists: {os.path.exists(ca_bundle)}")
    print(f"  Absolute: {os.path.abspath(ca_bundle)}")
    print(f"  Is file: {os.path.isfile(ca_bundle) if os.path.exists(ca_bundle) else 'N/A'}")
    if os.path.exists(ca_bundle):
        size = os.path.getsize(ca_bundle)
        print(f"  Size: {size} bytes")
    print()

print("Python paths:")
for i, path in enumerate(sys.path):
    print(f"  [{i}] {path}")
print()

print("=" * 70)
print("Testing boto3 initialization...")
print("=" * 70)

import boto3

session = boto3.Session(profile_name=aws_profile) if aws_profile else boto3.Session()
print(f"✅ Session created with profile: {aws_profile}")

s3_kwargs = {}
if ca_bundle and os.path.exists(ca_bundle):
    s3_kwargs['verify'] = ca_bundle
    print(f"✅ Using custom CA bundle: {ca_bundle}")
else:
    print(f"⚠️  CA bundle not found or not set")

print(f"S3 client kwargs: {s3_kwargs}")

s3_client = session.client('s3', **s3_kwargs)
print(f"✅ S3 client created")

print()
print("Testing S3 API call...")
try:
    response = s3_client.list_objects_v2(
        Bucket='agentic-ai-poc-synthetic-data',
        Prefix='devices/',
        MaxKeys=1
    )
    print(f"✅ S3 call succeeded: Found {response.get('KeyCount')} objects")
except Exception as e:
    print(f"❌ S3 call failed: {e}")
    import traceback
    traceback.print_exc()
