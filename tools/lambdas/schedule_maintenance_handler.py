"""
Lambda Handler: schedule_maintenance

Purpose:
- MCP Tool for scheduling maintenance
- Writes to DynamoDB: maintenance_schedules table
- Generates unique maintenance_id
- Stores maintenance record for future reference
- Called by diagnosis agent when maintenance is needed

Used by: Diagnosis agent to schedule preventive/corrective maintenance
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for schedule_maintenance MCP tool
    
    Input:
    {
        "device_id": "motor-001",              # Required: device to maintain
        "maintenance_type": "preventive",      # Required: preventive/corrective/inspection
        "scheduled_date": "2026-06-15"         # Required: YYYY-MM-DD format
    }
    
    Output:
    {
        "maintenance_id": "MAINT-20260528-abc123",
        "device_id": "motor-001",
        "maintenance_type": "preventive",
        "scheduled_date": "2026-06-15",
        "status": "scheduled",
        "created_at": "2026-05-28T10:30:00Z"
    }
    """
    
    try:
        logger.info(f"Received request: {json.dumps(event)}")
        
        # Extract parameters
        device_id = event.get('device_id')
        maintenance_type = event.get('maintenance_type')
        scheduled_date = event.get('scheduled_date')
        
        # Validate required parameters
        if not device_id:
            return error_response(400, "device_id is required")
        if not maintenance_type:
            return error_response(400, "maintenance_type is required")
        if not scheduled_date:
            return error_response(400, "scheduled_date is required")
        
        # Validate maintenance_type
        valid_types = ['preventive', 'corrective', 'inspection']
        if maintenance_type.lower() not in valid_types:
            return error_response(
                400,
                f"maintenance_type must be one of: {', '.join(valid_types)}"
            )
        
        # Validate date format (YYYY-MM-DD)
        try:
            scheduled_dt = datetime.strptime(scheduled_date, '%Y-%m-%d')
        except ValueError:
            return error_response(400, "scheduled_date must be in YYYY-MM-DD format")
        
        # Generate unique maintenance_id
        maintenance_id = generate_maintenance_id()
        
        # Get current timestamp
        now = datetime.utcnow().isoformat() + 'Z'
        
        # Write to DynamoDB
        table_name = os.environ.get('MAINTENANCE_TABLE', 'maintenance_schedules')
        table = dynamodb.Table(table_name)
        
        logger.info(f"Writing to DynamoDB table: {table_name}")
        
        try:
            table.put_item(
                Item={
                    'maintenance_id': maintenance_id,
                    'device_id': device_id,
                    'maintenance_type': maintenance_type,
                    'scheduled_date': scheduled_date,
                    'status': 'scheduled',
                    'created_at': now,
                    'updated_at': now,
                    'metadata': {
                        'source': 'diagnosis-agent',
                        'phase': 'phase-1'
                    }
                }
            )
            logger.info(f"Successfully wrote maintenance record: {maintenance_id}")
        except Exception as db_error:
            logger.error(f"DynamoDB write failed: {str(db_error)}", exc_info=True)
            return error_response(500, f"Failed to store maintenance record: {str(db_error)}")
        
        # Return success with maintenance record
        result = {
            'maintenance_id': maintenance_id,
            'device_id': device_id,
            'maintenance_type': maintenance_type,
            'scheduled_date': scheduled_date,
            'status': 'scheduled',
            'created_at': now,
            'message': f'Maintenance scheduled for {device_id} on {scheduled_date}'
        }
        
        logger.info(f"Success: {json.dumps(result)}")
        return success_response(result)
    
    except Exception as e:
        logger.error(f"Error in schedule_maintenance: {str(e)}", exc_info=True)
        return error_response(500, f"Internal error: {str(e)}")


def generate_maintenance_id() -> str:
    """
    Generate unique maintenance ID
    
    Format: MAINT-YYYYMMDD-XXXXXX
    Example: MAINT-20260528-abc123
    """
    now = datetime.utcnow()
    date_str = now.strftime('%Y%m%d')
    unique_suffix = str(uuid.uuid4())[:6]
    return f"MAINT-{date_str}-{unique_suffix}"


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
