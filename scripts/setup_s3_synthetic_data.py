#!/usr/bin/env python3
"""
S3 Setup Script for Synthetic Device Data

Purpose:
- Create S3 bucket for synthetic device data
- Upload device JSON files for AgentCore runtime access
- Enable versioning for safety
- Document S3 location for agent configuration

Usage:
    python scripts/setup_s3_synthetic_data.py \
      --bucket-name team01-synthetic-data \
      --data-dir data/generated \
      --profile StandardAccess-450410489798

This script:
1. Creates S3 bucket (if not exists)
2. Uploads all device JSON files from data/generated/ to S3 devices/ prefix
3. Enables versioning
4. Outputs S3 paths and updates .agentcore.env with bucket name
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Dict

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SyntheticDataS3Manager:
    """Manages S3 bucket creation and synthetic device data uploads"""
    
    def __init__(self, bucket_name: str, region: str = 'eu-central-1', profile: Optional[str] = None):
        """Initialize S3 manager with boto3 session"""
        self.bucket_name = bucket_name
        self.region = region
        
        # Create session with profile if specified
        if profile:
            session = boto3.Session(profile_name=profile)
            self.s3_client = session.client('s3', region_name=region)
        else:
            self.s3_client = boto3.client('s3', region_name=region)
    
    def bucket_exists(self) -> bool:
        """Check if S3 bucket exists"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ Bucket exists: {self.bucket_name}")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.info(f"❌ Bucket does not exist: {self.bucket_name}")
                return False
            elif error_code == '403':
                logger.error(f"❌ Access denied to bucket: {self.bucket_name}")
                raise
            else:
                raise
    
    def create_bucket(self) -> bool:
        """Create S3 bucket with proper configuration"""
        if self.bucket_exists():
            logger.info("Bucket already exists, skipping creation")
            return True
        
        try:
            logger.info(f"Creating bucket: {self.bucket_name} in region {self.region}...")
            
            if self.region == 'us-east-1':
                # us-east-1 doesn't need LocationConstraint
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            
            logger.info(f"✅ Bucket created successfully: {self.bucket_name}")
            
            # Enable versioning for safety (can recover older versions)
            self.s3_client.put_bucket_versioning(
                Bucket=self.bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            logger.info("✅ Versioning enabled (can recover older versions)")
            
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'BucketAlreadyOwnedByYou':
                logger.info("Bucket already owned by you")
                return True
            elif error_code == 'BucketAlreadyExists':
                logger.error(f"❌ Bucket name exists globally (owned by another account)")
                return False
            else:
                logger.error(f"Failed to create bucket: {e}")
                raise
    
    def upload_device_files(self, data_dir: str, prefix: str = 'devices') -> Dict[str, str]:
        """
        Upload device JSON files to S3
        
        Args:
            data_dir: Local directory containing device JSON files
            prefix: S3 prefix (e.g., 'devices/' means files go to s3://bucket/devices/)
        
        Returns:
            Dictionary mapping filename to S3 URL
        """
        data_path = Path(data_dir)
        
        if not data_path.exists():
            logger.error(f"❌ Data directory not found: {data_dir}")
            return {}
        
        json_files = sorted(data_path.glob('*.json'))
        
        if not json_files:
            logger.warning(f"⚠️  No JSON files found in {data_dir}")
            return {}
        
        logger.info(f"Found {len(json_files)} device JSON files to upload")
        uploaded_files = {}
        
        for file_path in json_files:
            try:
                # Create S3 key: devices/compressor-001.json
                s3_key = f"{prefix}/{file_path.name}"
                
                logger.info(f"Uploading: {file_path.name} → s3://{self.bucket_name}/{s3_key}")
                
                # Upload with metadata
                self.s3_client.upload_file(
                    str(file_path),
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={
                        'ContentType': 'application/json',
                        'Metadata': {
                            'source': 'synthetic-device-data',
                            'device-type': file_path.stem.split('-')[0]  # Extract device type
                        }
                    }
                )
                
                s3_url = f"s3://{self.bucket_name}/{s3_key}"
                uploaded_files[file_path.name] = s3_url
                logger.info(f"✅ Uploaded: {file_path.name}")
                
            except ClientError as e:
                logger.error(f"Failed to upload {file_path.name}: {e}")
                raise
        
        logger.info(f"✅ All {len(uploaded_files)} files uploaded successfully")
        return uploaded_files
    
    def generate_summary(self, uploaded_files: Dict[str, str]) -> str:
        """Generate summary of S3 setup"""
        device_types = {}
        for filename in uploaded_files.keys():
            device_type = filename.split('-')[0]
            device_types[device_type] = device_types.get(device_type, 0) + 1
        
        summary = f"""
╔════════════════════════════════════════════════════════════╗
║          S3 SYNTHETIC DATA SETUP SUMMARY                  ║
╚════════════════════════════════════════════════════════════╝

Bucket Name:    {self.bucket_name}
Region:         {self.region}
Total Files:    {len(uploaded_files)}

Device Breakdown:
"""
        for device_type in sorted(device_types.keys()):
            summary += f"  - {device_type:12s}: {device_types[device_type]} files\n"
        
        summary += f"""
S3 Structure:
  Bucket: {self.bucket_name}
  ├── devices/
  │   ├── compressor-001.json
  │   ├── compressor-002.json
  │   ├── generator-001.json
  │   ├── motor-001.json
  │   └── pump-*.json

Configuration for .agentcore.env:
  SYNTHETIC_DATA_BUCKET=team01-synthetic-data
  SYNTHETIC_DATA_PREFIX=devices/

Access Pattern:
  Agents will load data via:
  s3://team01-synthetic-data/devices/device-id.json

Versioning:  ✅ Enabled (can recover previous versions)

Next Steps:
  1. Update .agentcore.env with bucket name
  2. Update agent code to load from S3 (Phase 2)
  3. Deploy agents to AgentCore (Phase 4)
"""
        return summary


def main():
    parser = argparse.ArgumentParser(
        description='Upload synthetic device data to S3 for AgentCore runtime'
    )
    parser.add_argument(
        '--bucket-name',
        default='team01-synthetic-data',
        help='S3 bucket name (default: team01-synthetic-data)'
    )
    parser.add_argument(
        '--data-dir',
        default='data/generated',
        help='Local directory with device JSON files (default: data/generated)'
    )
    parser.add_argument(
        '--region',
        default='eu-central-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--profile',
        help='AWS SSO profile name (optional)'
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("=" * 60)
        logger.info("SYNTHETIC DATA S3 SETUP")
        logger.info("=" * 60)
        
        # Initialize S3 manager
        manager = SyntheticDataS3Manager(
            bucket_name=args.bucket_name,
            region=args.region,
            profile=args.profile
        )
        
        # Step 1: Create bucket
        if not manager.create_bucket():
            logger.error("Failed to create bucket")
            return 1
        
        # Step 2: Upload files
        uploaded = manager.upload_device_files(args.data_dir, prefix='devices')
        
        if not uploaded:
            logger.error("No files were uploaded")
            return 1
        
        # Step 3: Print summary
        summary = manager.generate_summary(uploaded)
        print(summary)
        
        logger.info("=" * 60)
        logger.info("✅ SETUP COMPLETE - Synthetic data ready in S3")
        logger.info("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
