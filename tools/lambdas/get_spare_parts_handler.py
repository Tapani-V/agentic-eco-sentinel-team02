"""
Lambda Handler: get_spare_parts

Purpose:
- MCP Tool for querying spare parts inventory
- Reads from S3: s3://agentic-ai-poc-3-1-mcp-tools/data/spare_parts_inventory.json
- Filters by part_type and optional category
- Returns matching spare parts to agent

Used by: Diagnosis agent when it needs to find available spare parts
"""

import json
import logging
import os
from typing import Any, Dict, List

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for get_spare_parts MCP tool
    
    Input:
    {
        "part_type": "bearing",        # Required: type of spare part
        "category": "mechanical"        # Optional: category filter
    }
    
    Output:
    {
        "parts": [
            {
                "part_id": "PART-001",
                "part_name": "Ball Bearing 6205",
                "category": "mechanical",
                "stock_quantity": 15,
                "unit_cost": 45.50
            },
            ...
        ],
        "count": 2
    }
    """
    
    try:
        logger.info(f"Received request: {json.dumps(event)}")
        
        # Extract parameters
        part_type = event.get('part_type')
        category = event.get('category')
        
        # Validate required parameters
        if not part_type:
            return error_response(400, "part_type is required")
        
        # Read inventory from S3
        bucket_name = os.environ.get('MCP_TOOLS_BUCKET', 'agentic-ai-poc-3-1-mcp-tools')
        inventory_key = 'data/spare_parts_inventory.json'
        
        logger.info(f"Reading inventory from s3://{bucket_name}/{inventory_key}")
        
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=inventory_key)
            inventory_data = json.loads(response['Body'].read().decode('utf-8'))
        except s3_client.exceptions.NoSuchBucket:
            return error_response(500, f"Bucket not found: {bucket_name}")
        except s3_client.exceptions.NoSuchKey:
            return error_response(500, f"Inventory file not found: {inventory_key}")
        
        # Filter spare parts
        matching_parts = filter_spare_parts(
            inventory_data,
            part_type=part_type,
            category=category
        )
        
        if not matching_parts:
            logger.info(f"No spare parts found matching: part_type={part_type}, category={category}")
            return success_response({
                "parts": [],
                "count": 0,
                "message": f"No spare parts found matching part_type='{part_type}'"
            })
        
        logger.info(f"Found {len(matching_parts)} matching spare parts")
        return success_response({
            "parts": matching_parts,
            "count": len(matching_parts)
        })
    
    except Exception as e:
        logger.error(f"Error in get_spare_parts: {str(e)}", exc_info=True)
        return error_response(500, f"Internal error: {str(e)}")


def filter_spare_parts(inventory: Dict, part_type: str, category: str = None) -> List[Dict]:
    """
    Filter spare parts from inventory
    
    Args:
        inventory: Full inventory data from S3
        part_type: Type to filter by (required)
        category: Category to filter by (optional)
    
    Returns:
        List of matching spare parts
    """
    spare_parts = inventory.get('spare_parts', [])
    
    matching_parts = []
    for part in spare_parts:
        # Match part_type (case-insensitive)
        if part.get('part_type', '').lower() != part_type.lower():
            continue
        
        # If category filter provided, check it
        if category and part.get('category', '').lower() != category.lower():
            continue
        
        # This part matches all filters
        matching_parts.append({
            'part_id': part.get('part_id'),
            'part_name': part.get('part_name'),
            'category': part.get('category'),
            'stock_quantity': part.get('stock_quantity', 0),
            'unit_cost': part.get('unit_cost', 0.0)
        })
    
    return matching_parts


def success_response(data: Dict) -> Dict[str, Any]:
    """Format success response"""
    return {
        'statusCode': 200,
        'body': json.dumps(data),
        'headers': {
            'Content-Type': 'application/json'
        }
    }


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Format error response"""
    logger.error(f"Error {status_code}: {message}")
    return {
        'statusCode': status_code,
        'body': json.dumps({'error': message}),
        'headers': {
            'Content-Type': 'application/json'
        }
    }
