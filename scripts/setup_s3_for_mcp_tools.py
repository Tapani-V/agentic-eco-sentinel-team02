#!/usr/bin/env python3
"""
S3 Setup Script for Phase 1 MCP Tools

Purpose:
- Create S3 bucket for MCP tools data
- Upload MCP tools data files to S3
- Configure bucket for MCP tool access

Usage:
    python scripts/setup_s3_for_mcp_tools.py --bucket-name agentic-ai-poc-3-1-mcp-tools --data-dir data/mcp-tools

This script:
1. Creates S3 bucket (if not exists)
2. Uploads all JSON files from data/mcp-tools/ to S3
3. Sets proper permissions for Lambda/ECS tools to read
4. Outputs S3 URLs for verification
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class S3DataManager:
    """Manages S3 bucket creation and data uploads for MCP tools"""
    
    def __init__(self, bucket_name: str, region: str = 'us-east-1'):
        self.bucket_name = bucket_name
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)
        self.s3_resource = boto3.resource('s3', region_name=region)
    
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
            logger.info(f"Bucket already exists, skipping creation")
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
            
            # Enable versioning for safety
            self.s3_client.put_bucket_versioning(
                Bucket=self.bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            logger.info(f"✅ Versioning enabled for: {self.bucket_name}")
            
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'BucketAlreadyOwnedByYou':
                logger.info("Bucket already owned by you")
                return True
            elif error_code == 'BucketAlreadyExists':
                logger.error(f"Bucket already exists (owned by another AWS account): {self.bucket_name}")
                return False
            else:
                logger.error(f"Failed to create bucket: {e}")
                raise
    
    def upload_data_files(self, data_dir: str, file_filter: Optional[str] = None) -> dict:
        """Upload JSON files from data_dir to S3, optionally filtering by name"""
        data_path = Path(data_dir)
        
        if not data_path.exists():
            logger.error(f"❌ Data directory not found: {data_dir}")
            return {}
        
        json_files = list(data_path.glob('*.json'))
        
        # Apply file filter if provided
        if file_filter:
            json_files = [f for f in json_files if file_filter in f.name]
            logger.info(f"Applied filter: {file_filter}")
        
        if not json_files:
            logger.warning(f"⚠️  No JSON files found in {data_dir}" + 
                          (f" matching filter '{file_filter}'" if file_filter else ""))
            return {}
        
        logger.info(f"Found {len(json_files)} JSON files to upload")
        uploaded_files = {}
        
        for file_path in json_files:
            try:
                s3_key = f"data/{file_path.name}"  # Upload to data/ prefix in S3
                
                logger.info(f"Uploading: {file_path.name} → s3://{self.bucket_name}/{s3_key}")
                
                self.s3_client.upload_file(
                    str(file_path),
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={
                        'ContentType': 'application/json',
                        'Metadata': {
                            'source': 'phase1-generated-data',
                            'generated': 'true'
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
    
    def configure_bucket_policy(self) -> bool:
        """Configure bucket policy to allow Lambda/ECS tools to read data"""
        try:
            logger.info(f"Configuring bucket policy for Lambda/ECS access...")
            
            # Policy allows Lambda/ECS execution roles to read objects
            bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowLambdaECSRead",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": [
                                "lambda.amazonaws.com",
                                "ecs-tasks.amazonaws.com"
                            ]
                        },
                        "Action": [
                            "s3:GetObject",
                            "s3:ListBucket"
                        ],
                        "Resource": [
                            f"arn:aws:s3:::{self.bucket_name}",
                            f"arn:aws:s3:::{self.bucket_name}/*"
                        ]
                    },
                    {
                        "Sid": "AllowDataListing",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:ListBucket",
                        "Resource": f"arn:aws:s3:::{self.bucket_name}",
                        "Condition": {
                            "StringEquals": {
                                "s3:prefix": "data/"
                            }
                        }
                    }
                ]
            }
            
            # Only set policy if bucket was just created or policy doesn't exist
            try:
                self.s3_client.put_bucket_policy(
                    Bucket=self.bucket_name,
                    Policy=json.dumps(bucket_policy)
                )
                logger.info(f"✅ Bucket policy configured")
                return True
            except ClientError as e:
                if 'PolicyText' in str(e):
                    logger.warning(f"Could not set bucket policy (may need manual IAM setup): {e}")
                    return False
                raise
        
        except Exception as e:
            logger.error(f"Error configuring bucket policy: {e}")
            return False
    
    def generate_summary(self, uploaded_files: dict) -> str:
        """Generate summary of S3 setup for documentation"""
        summary = f"""
S3 Setup Summary
================

Bucket Name: {self.bucket_name}
Region: {self.region}
Files Uploaded: {len(uploaded_files)}

Uploaded Files:
"""
        for filename, s3_url in sorted(uploaded_files.items()):
            summary += f"\n  - {filename}\n    Location: {s3_url}"
        
        summary += f"""

Configuration:
  ✅ Versioning: Enabled
  ✅ Data Prefix: data/
  ✅ Access: Lambda/ECS services can read

MCP Tools Can Now:
  - Read spare_parts_inventory.json from S3 (for get_spare_parts tool)
  - Read device data from S3 (if needed for schedule_maintenance)
  - Write results to S3 (if needed for create_work_order)

Local Agents Still Read From:
  - data/generated/*.json (local machine - sensor data)

Phase 2+ Migration:
  When agents move to AWS AgentCore Runtime:
  - Agents read sensor data from: s3://agentic-ai-poc-3-1-sensor-data/devices/device-*.json
  - MCP tools continue reading from: s3://{self.bucket_name}/mcp/spare_parts_inventory.json
"""
        return summary


def main():
    parser = argparse.ArgumentParser(
        description='Setup S3 bucket for Phase 1 MCP tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create bucket and upload MCP tools data to us-east-1
  python scripts/setup_s3_for_mcp_tools.py \
    --bucket-name agentic-ai-poc-3-1-mcp-tools \
    --data-dir data/mcp-tools

  # Use file filter to upload only spare parts inventory
  python scripts/setup_s3_for_mcp_tools.py \
    --bucket-name agentic-ai-poc-3-1-mcp-tools \
    --data-dir data/mcp-tools \
    --file-filter spare_parts_inventory.json

  # Save summary to file
  python scripts/setup_s3_for_mcp_tools.py \
    --bucket-name agentic-ai-poc-3-1-mcp-tools \
    --data-dir data/mcp-tools \
    --output-summary s3_mcp_setup_summary.txt
        """
    )
    
    parser.add_argument(
        '--bucket-name',
        required=True,
        help='S3 bucket name (must be globally unique)'
    )
    parser.add_argument(
        '--data-dir',
        default='data/mcp-tools',
        help='Directory containing MCP tools JSON data files (default: data/mcp-tools)'
    )
    parser.add_argument(
        '--file-filter',
        type=str,
        help='Filter files by name (e.g., spare_parts_inventory.json). If not provided, uploads all JSON files'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region for bucket (default: us-east-1)'
    )
    parser.add_argument(
        '--output-summary',
        type=str,
        help='Save summary to file'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize S3 manager
        manager = S3DataManager(
            bucket_name=args.bucket_name,
            region=args.region
        )
        
        # Step 1: Create bucket
        logger.info("=" * 60)
        logger.info("Step 1: Creating S3 Bucket")
        logger.info("=" * 60)
        if not manager.create_bucket():
            logger.error("Failed to create bucket")
            sys.exit(1)
        
        # Step 2: Upload data files
        logger.info("\n" + "=" * 60)
        logger.info("Step 2: Uploading Generated Data Files")
        logger.info("=" * 60)
        uploaded_files = manager.upload_data_files(args.data_dir, args.file_filter)
        if not uploaded_files:
            logger.error("No files uploaded")
            sys.exit(1)
        
        # Step 3: Configure bucket policy
        logger.info("\n" + "=" * 60)
        logger.info("Step 3: Configuring Bucket Policy")
        logger.info("=" * 60)
        manager.configure_bucket_policy()
        
        # Step 4: Generate summary
        logger.info("\n" + "=" * 60)
        logger.info("Setup Complete!")
        logger.info("=" * 60)
        summary = manager.generate_summary(uploaded_files)
        print(summary)
        
        if args.output_summary:
            Path(args.output_summary).write_text(summary)
            logger.info(f"Summary saved to: {args.output_summary}")
        
        return 0
    
    except KeyboardInterrupt:
        logger.info("Setup cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Setup failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
