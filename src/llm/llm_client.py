#!/usr/bin/env python3
"""
LLM Client for diagnosis verification

Uses Amazon Bedrock (Nova Lite) for diagnosis verification when rule
confidence < 0.85. Fully managed model - no deployment needed, just
bedrock-runtime:InvokeModel permission (already granted to the shared
AgentCoreExecutionRole via its BedrockModelAccess inline policy).
"""

import os
import json
import logging
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM client using Amazon Bedrock (Nova Lite) for diagnosis verification.

    Used in DiagnosisAgent Step 3 when rule confidence < 0.85.
    Calls Amazon Nova Lite via the Bedrock Converse API.
    """

    MODEL_ID = "amazon.nova-lite-v1:0"

    def __init__(self):
        """Initialize Bedrock client from environment/profile."""
        self.region = os.getenv("AWS_REGION", "us-east-1")
        profile = os.getenv("AWS_PROFILE")

        try:
            session = boto3.Session(profile_name=profile, region_name=self.region)
            self.client = session.client("bedrock-runtime")
            logger.info(f"LLM client initialized (model: {self.MODEL_ID}, region: {self.region})")
        except Exception as e:
            logger.warning(f"Failed to initialize Bedrock client: {e}. LLM verification disabled.")
            self.client = None

    def verify_diagnosis(
        self,
        device_id: str,
        equipment_type: str,
        anomalies: list,
        rule_diagnosis: str,
        rule_action: str,
        rule_confidence: float,
        current_reading: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify diagnosis using LLM when rule confidence is low (<0.85)
        
        Args:
            device_id: Device identifier
            equipment_type: PUMP, MOTOR, COMPRESSOR, GENERATOR
            anomalies: List of detected anomalies
            rule_diagnosis: Diagnosis from pattern matching rules
            rule_action: Action from pattern matching rules
            rule_confidence: Confidence score from rules
            current_reading: Sensor readings
        
        Returns:
            {
                'diagnosis': str,
                'action': str,  # URGENT_REPAIR | SCHEDULE_MAINTENANCE | MONITOR_ONLY
                'confidence': float,
                'reasoning': str,
                'llm_used': True
            }
        """
        
        if not self.client:
            logger.warning("LLM client not available. Returning rule-based decision.")
            return {
                'diagnosis': rule_diagnosis,
                'action': rule_action,
                'confidence': rule_confidence,
                'reasoning': 'Rule-based (LLM unavailable)',
                'llm_used': False
            }
        
        try:
            # Build context for LLM
            sensor_summary = self._summarize_sensors(current_reading)
            anomalies_text = "\n".join([f"  - {a}" for a in anomalies]) if anomalies else "  None detected"
            
            prompt = f"""You are an expert equipment maintenance engineer analyzing industrial equipment diagnostics.

DEVICE INFORMATION:
- Device ID: {device_id}
- Equipment Type: {equipment_type}

SENSOR ANOMALIES DETECTED:
{anomalies_text}

SENSOR READINGS SUMMARY:
{sensor_summary}

RULE-BASED ANALYSIS (Low Confidence):
- Diagnosis: {rule_diagnosis}
- Recommended Action: {rule_action}
- Rule Confidence: {rule_confidence:.2f} (below 0.85 threshold)

TASK: Verify the rule-based diagnosis. Based on the sensor data and anomalies:
1. Do you agree with the diagnosis? Why or why not?
2. What is the correct action to take? (URGENT_REPAIR | SCHEDULE_MAINTENANCE | MONITOR_ONLY)
3. What is your confidence level? (0.0-1.0)

Respond ONLY in JSON format:
{{
    "diagnosis": "Your verified diagnosis",
    "action": "URGENT_REPAIR|SCHEDULE_MAINTENANCE|MONITOR_ONLY",
    "confidence": 0.85,
    "reasoning": "Brief explanation of why you chose this action"
}}"""
            
            logger.info(f"[LLM] Calling Amazon Nova Lite for {device_id} verification")
            
            response = self.client.converse(
                modelId=self.MODEL_ID,
                messages=[
                    {"role": "user", "content": [{"text": prompt}]}
                ],
                system=[
                    {"text": "You are an expert industrial equipment diagnostician. Always respond in valid JSON format only, with no extra text."}
                ],
                inferenceConfig={
                    "temperature": 0.5,
                    "maxTokens": 500,
                },
            )
            
            # Parse LLM response
            response_text = response["output"]["message"]["content"][0]["text"].strip()
            
            # Extract JSON from response (in case LLM adds extra text)
            try:
                # Try to find JSON object in response
                import re
                json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    response_json = json.loads(json_match.group())
                else:
                    response_json = json.loads(response_text)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON: {response_text}")
                # Fallback to rule-based
                return {
                    'diagnosis': rule_diagnosis,
                    'action': rule_action,
                    'confidence': rule_confidence,
                    'reasoning': 'LLM response parsing failed',
                    'llm_used': False
                }
            
            # Validate and extract fields
            llm_diagnosis = response_json.get('diagnosis', rule_diagnosis)
            llm_action = response_json.get('action', rule_action)
            llm_confidence = float(response_json.get('confidence', rule_confidence))
            llm_reasoning = response_json.get('reasoning', 'No reasoning provided')
            
            # Validate action
            if llm_action not in ['URGENT_REPAIR', 'SCHEDULE_MAINTENANCE', 'MONITOR_ONLY']:
                logger.warning(f"Invalid action from LLM: {llm_action}. Using rule action instead.")
                llm_action = rule_action
            
            logger.info(f"[LLM] Verification complete for {device_id}")
            logger.info(f"  Rule: {rule_diagnosis} ({rule_action})")
            logger.info(f"  LLM:  {llm_diagnosis} ({llm_action})")
            
            return {
                'diagnosis': llm_diagnosis,
                'action': llm_action,
                'confidence': llm_confidence,
                'reasoning': llm_reasoning,
                'llm_used': True
            }
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"[LLM] Bedrock error for {device_id}: {error_code} - {e}")
            return {
                'diagnosis': rule_diagnosis,
                'action': rule_action,
                'confidence': rule_confidence,
                'reasoning': f'Bedrock error: {error_code}',
                'llm_used': False
            }
        except Exception as e:
            logger.error(f"[LLM] Error during verification for {device_id}: {e}")
            # Fallback to rule-based
            return {
                'diagnosis': rule_diagnosis,
                'action': rule_action,
                'confidence': rule_confidence,
                'reasoning': f'LLM error: {str(e)}',
                'llm_used': False
            }
    
    def _summarize_sensors(self, current_reading: Dict[str, Any]) -> str:
        """Create a human-readable summary of sensor readings"""
        readings = current_reading.get('readings', {})
        
        if not readings:
            return "No sensor data available"
        
        lines = []
        for sensor_name, sensor_data in readings.items():
            if isinstance(sensor_data, dict):
                value = sensor_data.get('value', 'N/A')
                unit = sensor_data.get('unit', '')
                normal_range = sensor_data.get('normal_range', [])
                
                if normal_range:
                    min_val, max_val = normal_range[0], normal_range[1]
                    status = "✓ Normal" if min_val <= value <= max_val else "⚠ Out of range"
                    lines.append(f"  {sensor_name}: {value} {unit} (normal: {min_val}-{max_val}) {status}")
                else:
                    lines.append(f"  {sensor_name}: {value} {unit}")
        
        return "\n".join(lines) if lines else "No sensor readings"
