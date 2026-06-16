#!/usr/bin/env python3
"""
DynamoDB Setup for Agentic AI POC Phase 1

Creates DynamoDB table for conversation memory:
- Stores conversation history
- Session management
- Query by session_id or user_id
"""

import boto3
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class DynamoDBSetup:
    """Manages DynamoDB table creation."""
    
    def __init__(self, region: str):
        self.dynamodb_client = boto3.client("dynamodb", region_name=region)
        self.region = region
    
    def create_conversation_table(self, table_name: str, billing_mode: str = "PAY_PER_REQUEST") -> str:
        """Create DynamoDB table for conversation memory."""
        try:
            # Check if table already exists
            try:
                response = self.dynamodb_client.describe_table(TableName=table_name)
                logger.warning(f"⚠ Table already exists: {table_name}")
                return response["Table"]["TableArn"]
            except self.dynamodb_client.exceptions.ResourceNotFoundException:
                pass
            
            # Create table
            if billing_mode == "PAY_PER_REQUEST":
                # For PAY_PER_REQUEST, don't include ProvisionedThroughput for GSI
                response = self.dynamodb_client.create_table(
                    TableName=table_name,
                    KeySchema=[
                        {"AttributeName": "session_id", "KeyType": "HASH"},  # Partition key
                        {"AttributeName": "timestamp", "KeyType": "RANGE"}   # Sort key
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "session_id", "AttributeType": "S"},
                        {"AttributeName": "timestamp", "AttributeType": "N"},
                        {"AttributeName": "user_id", "AttributeType": "S"},
                        {"AttributeName": "device_id", "AttributeType": "S"}
                    ],
                    BillingMode=billing_mode,
                    GlobalSecondaryIndexes=[
                        {
                            "IndexName": "user_id-timestamp-index",
                            "KeySchema": [
                                {"AttributeName": "user_id", "KeyType": "HASH"},
                                {"AttributeName": "timestamp", "KeyType": "RANGE"}
                            ],
                            "Projection": {"ProjectionType": "ALL"}
                        },
                        {
                            "IndexName": "device_id-timestamp-index",
                            "KeySchema": [
                                {"AttributeName": "device_id", "KeyType": "HASH"},
                                {"AttributeName": "timestamp", "KeyType": "RANGE"}
                            ],
                            "Projection": {"ProjectionType": "ALL"}
                        }
                    ],
                    StreamSpecification={
                        "StreamViewType": "NEW_AND_OLD_IMAGES",
                        "StreamEnabled": True
                    },
                    Tags=[
                        {"Key": "Project", "Value": "agentic-ai-poc"},
                        {"Key": "Phase", "Value": "phase-1"}
                    ]
                )
            else:
                # For PROVISIONED mode, include ProvisionedThroughput
                response = self.dynamodb_client.create_table(
                    TableName=table_name,
                    KeySchema=[
                        {"AttributeName": "session_id", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"}
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "session_id", "AttributeType": "S"},
                        {"AttributeName": "timestamp", "AttributeType": "N"},
                        {"AttributeName": "user_id", "AttributeType": "S"},
                        {"AttributeName": "device_id", "AttributeType": "S"}
                    ],
                    BillingMode=billing_mode,
                    ProvisionedThroughput={
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5
                    },
                    GlobalSecondaryIndexes=[
                        {
                            "IndexName": "user_id-timestamp-index",
                            "KeySchema": [
                                {"AttributeName": "user_id", "KeyType": "HASH"},
                                {"AttributeName": "timestamp", "KeyType": "RANGE"}
                            ],
                            "Projection": {"ProjectionType": "ALL"},
                            "ProvisionedThroughput": {
                                "ReadCapacityUnits": 5,
                                "WriteCapacityUnits": 5
                            }
                        },
                        {
                            "IndexName": "device_id-timestamp-index",
                            "KeySchema": [
                                {"AttributeName": "device_id", "KeyType": "HASH"},
                                {"AttributeName": "timestamp", "KeyType": "RANGE"}
                            ],
                            "Projection": {"ProjectionType": "ALL"},
                            "ProvisionedThroughput": {
                                "ReadCapacityUnits": 5,
                                "WriteCapacityUnits": 5
                            }
                        }
                    ],
                    StreamSpecification={
                        "StreamViewType": "NEW_AND_OLD_IMAGES",
                        "StreamEnabled": True
                    },
                    Tags=[
                        {"Key": "Project", "Value": "agentic-ai-poc"},
                        {"Key": "Phase", "Value": "phase-1"}
                    ]
                )
            
            table_arn = response["TableDescription"]["TableArn"]
            logger.info(f"✓ Created DynamoDB table: {table_name}")
            logger.info(f"  ARN: {table_arn}")
            logger.info(f"  Billing Mode: {billing_mode}")
            
            # Wait for table to be created
            waiter = self.dynamodb_client.get_waiter("table_exists")
            waiter.wait(TableName=table_name)
            logger.info(f"✓ Table is ready: {table_name}")
            
            return table_arn
        
        except Exception as e:
            logger.error(f"✗ Failed to create DynamoDB table: {e}")
            raise
    
    def add_ttl(self, table_name: str, ttl_attribute: str = "expiration_time", ttl_days: int = 30) -> None:
        """Add TTL (Time To Live) to table for automatic cleanup."""
        try:
            self.dynamodb_client.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    "AttributeName": ttl_attribute,
                    "Enabled": True
                }
            )
            logger.info(f"✓ Enabled TTL on {table_name} (attribute: {ttl_attribute})")
            logger.info(f"  Items will expire after {ttl_days} days of inactivity")
        
        except self.dynamodb_client.exceptions.ResourceInUseException:
            logger.warning(f"⚠ TTL already configured on {table_name}")
        
        except Exception as e:
            logger.error(f"✗ Failed to enable TTL: {e}")
            # Don't raise - TTL is optional
    
    def setup_dynamodb(self, table_name: str, billing_mode: str = "PAY_PER_REQUEST") -> Dict[str, str]:
        """Setup complete DynamoDB infrastructure."""
        logger.info("=" * 60)
        logger.info("Starting DynamoDB Setup")
        logger.info("=" * 60)
        
        try:
            # Create table
            table_arn = self.create_conversation_table(table_name, billing_mode)
            
            # Add TTL for cleanup
            self.add_ttl(table_name)
            
            logger.info("=" * 60)
            logger.info("✓ DynamoDB setup completed successfully")
            logger.info("=" * 60)
            
            return {
                "table_name": table_name,
                "table_arn": table_arn,
                "billing_mode": billing_mode
            }
        
        except Exception as e:
            logger.error(f"✗ DynamoDB setup failed: {e}")
            raise


def setup_dynamodb(region: str, table_name: str, billing_mode: str = "PAY_PER_REQUEST") -> Dict[str, str]:
    """Main function to setup DynamoDB."""
    dynamodb_setup = DynamoDBSetup(region)
    return dynamodb_setup.setup_dynamodb(table_name, billing_mode)


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    # Load environment variables
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.config import Config
    
    config = Config()
    dynamodb_info = setup_dynamodb(
        config.region,
        config.dynamodb_table_name,
        config.dynamodb_billing_mode
    )
    
    # Print results
    print("\n💾 DynamoDB Configuration:")
    for key, value in dynamodb_info.items():
        print(f"  {key}: {value}")
