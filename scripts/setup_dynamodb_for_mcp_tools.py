#!/usr/bin/env python3
"""
DynamoDB Setup Script for Phase 1 MCP Tools

Purpose:
- Create DynamoDB tables for MCP tool operations
- Create maintenance_schedules table (for schedule_maintenance Lambda)
- Create work_orders table (for create_work_order ECS)
- Configure tables with proper attributes and billing

Usage:
    python scripts/setup_dynamodb_for_mcp_tools.py --region us-east-1

This script:
1. Creates maintenance_schedules table
2. Creates work_orders table
3. Waits for tables to become active
4. Outputs table configuration summary
"""

import argparse
import json
import logging
import sys
import time
from typing import Dict

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DynamoDBTableManager:
    """Manages DynamoDB table creation for MCP tools"""
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.dynamodb_client = boto3.client('dynamodb', region_name=region)
        self.dynamodb_resource = boto3.resource('dynamodb', region_name=region)
    
    def table_exists(self, table_name: str) -> bool:
        """Check if DynamoDB table exists"""
        try:
            self.dynamodb_client.describe_table(TableName=table_name)
            logger.info(f"✅ Table exists: {table_name}")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.info(f"❌ Table does not exist: {table_name}")
                return False
            else:
                raise
    
    def create_maintenance_schedules_table(self) -> bool:
        """Create maintenance_schedules table"""
        table_name = 'maintenance_schedules'
        
        if self.table_exists(table_name):
            logger.info(f"Table already exists, skipping creation")
            return True
        
        try:
            logger.info(f"Creating table: {table_name}...")
            
            self.dynamodb_client.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'maintenance_id', 'KeyType': 'HASH'},  # Partition key
                    {'AttributeName': 'device_id', 'KeyType': 'RANGE'}       # Sort key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'maintenance_id', 'AttributeType': 'S'},
                    {'AttributeName': 'device_id', 'AttributeType': 'S'},
                    {'AttributeName': 'scheduled_date', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST',
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'device_id-scheduled_date-index',
                        'KeySchema': [
                            {'AttributeName': 'device_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'scheduled_date', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                Tags=[
                    {'Key': 'Project', 'Value': 'AGENTIC_AI_POC_Phase3_1'},
                    {'Key': 'Purpose', 'Value': 'MCP_Tools_Maintenance'}
                ]
            )
            
            logger.info(f"✅ Table created: {table_name}")
            self._wait_for_table_active(table_name)
            return True
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceInUseException':
                logger.info(f"Table already exists: {table_name}")
                return True
            else:
                logger.error(f"Failed to create table: {e}")
                raise
    
    def create_work_orders_table(self) -> bool:
        """Create work_orders table"""
        table_name = 'work_orders'
        
        if self.table_exists(table_name):
            logger.info(f"Table already exists, skipping creation")
            return True
        
        try:
            logger.info(f"Creating table: {table_name}...")
            
            self.dynamodb_client.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'work_order_id', 'KeyType': 'HASH'},  # Partition key
                    {'AttributeName': 'created_at', 'KeyType': 'RANGE'}     # Sort key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'work_order_id', 'AttributeType': 'S'},
                    {'AttributeName': 'created_at', 'AttributeType': 'S'},
                    {'AttributeName': 'priority', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST',
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'priority-created_at-index',
                        'KeySchema': [
                            {'AttributeName': 'priority', 'KeyType': 'HASH'},
                            {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                Tags=[
                    {'Key': 'Project', 'Value': 'AGENTIC_AI_POC_Phase3_1'},
                    {'Key': 'Purpose', 'Value': 'MCP_Tools_WorkOrders'}
                ]
            )
            
            logger.info(f"✅ Table created: {table_name}")
            self._wait_for_table_active(table_name)
            return True
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceInUseException':
                logger.info(f"Table already exists: {table_name}")
                return True
            else:
                logger.error(f"Failed to create table: {e}")
                raise
    
    def _wait_for_table_active(self, table_name: str, max_wait: int = 60) -> bool:
        """Wait for table to become ACTIVE"""
        logger.info(f"Waiting for {table_name} to become ACTIVE...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = self.dynamodb_client.describe_table(TableName=table_name)
                status = response['Table']['TableStatus']
                
                if status == 'ACTIVE':
                    logger.info(f"✅ Table {table_name} is ACTIVE")
                    return True
                else:
                    logger.info(f"  Status: {status}... waiting")
                    time.sleep(2)
            except ClientError as e:
                logger.warning(f"Error checking table status: {e}")
                time.sleep(2)
        
        logger.error(f"Timeout waiting for {table_name} to become ACTIVE")
        return False
    
    def get_table_info(self, table_name: str) -> Dict:
        """Get table information"""
        try:
            response = self.dynamodb_client.describe_table(TableName=table_name)
            table = response['Table']
            return {
                'name': table['TableName'],
                'status': table['TableStatus'],
                'item_count': table.get('ItemCount', 0),
                'size_bytes': table.get('TableSizeBytes', 0),
                'billing_mode': table['BillingModeSummary'].get('BillingMode', 'UNKNOWN'),
                'arn': table['TableArn']
            }
        except ClientError as e:
            logger.error(f"Failed to get table info: {e}")
            return {}
    
    def generate_summary(self) -> str:
        """Generate summary of DynamoDB setup"""
        maintenance_info = self.get_table_info('maintenance_schedules')
        work_orders_info = self.get_table_info('work_orders')
        
        summary = f"""
DynamoDB Setup Summary
======================

Region: {self.region}

Table 1: maintenance_schedules
  Status: {maintenance_info.get('status', 'UNKNOWN')}
  Item Count: {maintenance_info.get('item_count', 0)}
  Size: {maintenance_info.get('size_bytes', 0)} bytes
  Billing: {maintenance_info.get('billing_mode', 'UNKNOWN')}
  ARN: {maintenance_info.get('arn', 'N/A')}
  
  Primary Key:
    - maintenance_id (HASH)
    - device_id (RANGE)
  
  Global Secondary Index:
    - device_id-scheduled_date-index (query by device and date)

Table 2: work_orders
  Status: {work_orders_info.get('status', 'UNKNOWN')}
  Item Count: {work_orders_info.get('item_count', 0)}
  Size: {work_orders_info.get('size_bytes', 0)} bytes
  Billing: {work_orders_info.get('billing_mode', 'UNKNOWN')}
  ARN: {work_orders_info.get('arn', 'N/A')}
  
  Primary Key:
    - work_order_id (HASH)
    - created_at (RANGE)
  
  Global Secondary Index:
    - priority-created_at-index (query by priority and creation time)

Lambda Functions Can Now:
  ✅ Write maintenance records to maintenance_schedules
  ✅ Write work orders to work_orders
  ✅ Query by device_id or priority

Phase 2+ Features:
  - Agents can query maintenance history per device
  - Agents can query open/critical work orders
  - Dashboard can display pending maintenance
"""
        return summary


def main():
    parser = argparse.ArgumentParser(
        description='Setup DynamoDB tables for Phase 1 MCP tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create tables in us-east-1
  python scripts/setup_dynamodb_for_mcp_tools.py

  # Use different region
  python scripts/setup_dynamodb_for_mcp_tools.py --region us-west-2

  # Save summary to file
  python scripts/setup_dynamodb_for_mcp_tools.py --output-summary dynamodb_setup_summary.txt

  # Verbose output
  python scripts/setup_dynamodb_for_mcp_tools.py --verbose
        """
    )
    
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region for tables (default: us-east-1)'
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
        # Initialize DynamoDB manager
        manager = DynamoDBTableManager(region=args.region)
        
        # Step 1: Create maintenance_schedules table
        logger.info("=" * 60)
        logger.info("Step 1: Creating maintenance_schedules Table")
        logger.info("=" * 60)
        if not manager.create_maintenance_schedules_table():
            logger.error("Failed to create maintenance_schedules table")
            sys.exit(1)
        
        # Step 2: Create work_orders table
        logger.info("\n" + "=" * 60)
        logger.info("Step 2: Creating work_orders Table")
        logger.info("=" * 60)
        if not manager.create_work_orders_table():
            logger.error("Failed to create work_orders table")
            sys.exit(1)
        
        # Step 3: Generate summary
        logger.info("\n" + "=" * 60)
        logger.info("Setup Complete!")
        logger.info("=" * 60)
        summary = manager.generate_summary()
        print(summary)
        
        if args.output_summary:
            with open(args.output_summary, 'w') as f:
                f.write(summary)
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
