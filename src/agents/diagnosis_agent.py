#!/usr/bin/env python3
"""
DiagnosisAgent - Root cause analysis with 4-step decision process
Week 2 Day 5-7: Pattern matching → Confidence check → LLM judgment (if needed) → Execute actions

THIS AGENT CALLS MCP TOOLS VIA GATEWAYCLIENT
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json

from src.agents.base_agent import BaseAgent
from src.gateway.client import GatewayClient
from src.llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


class DiagnosisAgent(BaseAgent):
    """
    DiagnosisAgent: 4-Step Root Cause Analysis & Action Execution
    
    Week 2 Day 5-7 Design:
    
    Step 1: Pattern Matching (equipment-specific rules)
            → Try to match sensor anomalies against known patterns
            → Calculate confidence score (0.0-1.0)
    
    Step 2: Confidence Check
            → If confidence >= 0.85: TRUST THE RULE (use recommended action)
            → If confidence < 0.85: UNCERTAIN (call LLM for judgment)
    
    Step 3: LLM Enhancement (if confidence < 0.85)
            → Call LLM with sensor data + rule suggestion
            → Get AI judgment + final confidence + recommended action
    
    Step 4: Execute Action
            → Determines action type: URGENT_REPAIR | SCHEDULE_MAINTENANCE | MONITOR_ONLY
            → Calls MCP tools via GatewayClient if action requires tools
            → Returns results to Orchestrator
    
    MCP Tools Used:
    - get-spare-parts: Check spare parts availability
    - schedule-maintenance: Schedule maintenance in DynamoDB
    - create-work-order: Create emergency work order
    """
    
    def __init__(self):
        """Initialize DiagnosisAgent"""
        super().__init__("DiagnosisAgent", "diagnosis_analysis")
        
        # Initialize clients
        self.gateway_client = None  # Will be set by FastAPI wrapper when needed
        self.llm_client = LLMClient()  # Initialize LLM client for diagnosis verification
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform 4-step diagnosis and action execution
        
        Input from Orchestrator (via HealthAgent analysis):
        {
            'device_id': str,
            'equipment_type': str,  # PUMP, MOTOR, COMPRESSOR, GENERATOR
            'health_status': str,   # healthy | warning | critical
            'degradation_score': float,
            'anomalies': [str],     # From HealthAgent
            'current_reading': {
                'readings': {
                    'sensor_name': {'value': float, 'normal_range': [...], ...},
                    ...
                }
            }
        }
        
        Output to Orchestrator:
        {
            'device_id': str,
            'diagnosis': str,
            'confidence': float,
            'severity': str,        # low | medium | high
            'action': str,          # URGENT_REPAIR | SCHEDULE_MAINTENANCE | MONITOR_ONLY
            'action_taken': str,    # Description of what was done
            'tool_results': {...},  # Results from MCP tool calls (if any)
            'llm_used': bool,
            'analysis_timestamp': str,
            'status': 'completed' or 'error'
        }
        """
        try:
            device_id = input_data.get('device_id')
            equipment_type = input_data.get('equipment_type', 'UNKNOWN')
            health_status = input_data.get('health_status', 'unknown')
            anomalies = input_data.get('anomalies', [])
            current_reading = input_data.get('current_reading', {})
            
            if not device_id:
                raise ValueError("Missing required field: device_id")
            
            logger.info(f"[DiagnosisAgent] Starting diagnosis for {device_id} ({equipment_type})")
            logger.info(f"  Health status: {health_status}, Anomalies: {len(anomalies)}")
            
            # STEP 1: Pattern matching
            logger.info(f"[DiagnosisAgent] STEP 1: Pattern matching")
            rule_match = self._match_patterns(equipment_type, anomalies, current_reading)
            diagnosis = rule_match['diagnosis']
            confidence = rule_match['confidence']
            rule_confidence = confidence  # Track initial rule confidence
            recommended_action = rule_match['action']
            severity = rule_match['severity']
            
            logger.info(f"  Rule match: {diagnosis} (confidence: {confidence:.2f})")
            
            # STEP 2: Health Status Escalation (Business Rule)
            # If health_status = critical, ANY action must be escalated to URGENT_REPAIR
            # Critical status means device failure is imminent - requires immediate work order
            logger.info(f"[DiagnosisAgent] STEP 2: Health status escalation check")
            if health_status == 'critical':
                logger.info(f"  Health Status = CRITICAL → Escalating to URGENT_REPAIR (work order required)")
                recommended_action = 'URGENT_REPAIR'
                confidence = min(confidence + 0.05, 1.0)  # Slight confidence boost due to severity
            else:
                logger.info(f"  Health Status = {health_status} → Using rule recommendation: {recommended_action}")
            
            # STEP 3: Confidence check (for non-critical devices)
            logger.info(f"[DiagnosisAgent] STEP 3: Confidence check (threshold: 0.85)")
            llm_used = False
            if confidence < 0.85 and health_status != 'critical':
                logger.info(f"  Confidence {confidence:.2f} < 0.85 → CALLING LLM for verification")
                llm_used = True
                
                # Call LLM to verify diagnosis and get recommendation
                llm_response = self.llm_client.verify_diagnosis(
                    device_id=device_id,
                    equipment_type=equipment_type,
                    anomalies=anomalies,
                    rule_diagnosis=diagnosis,
                    rule_action=recommended_action,
                    rule_confidence=confidence,
                    current_reading=current_reading
                )
                
                # Update diagnosis and action based on LLM response
                diagnosis = llm_response['diagnosis']
                recommended_action = llm_response['action']
                confidence = llm_response['confidence']
                llm_used = llm_response['llm_used']
                
                logger.info(f"  LLM Recommendation: {diagnosis} ({recommended_action}, confidence: {confidence:.2f})")
            else:
                logger.info(f"  Confidence {confidence:.2f} >= 0.85 → TRUST RULE (no LLM needed)")
            
            # STEP 4: Execute action
            logger.info(f"[DiagnosisAgent] STEP 4: Execute action ({recommended_action})")
            action_result = await self._execute_action(
                device_id,
                equipment_type,
                recommended_action,
                anomalies,
                current_reading
            )
            
            # Build recommendation fields for dashboard
            recommendations = self._build_recommendations(
                device_id,
                equipment_type,
                recommended_action,
                diagnosis,
                anomalies,
                severity,
                llm_used
            )
            
            result = {
                'device_id': device_id,
                'diagnosis': diagnosis,
                'confidence': round(confidence, 2),
                'confidence_rule_based': round(rule_confidence, 2),  # Initial confidence from pattern matching
                'llm_used': llm_used,
                'severity': severity,
                'action': recommended_action,
                'action_taken': action_result.get('description', ''),
                'tool_results': action_result.get('tools', {}),
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'status': 'completed',
                # New recommendation fields for dashboard
                'insights': recommendations.get('insights', ''),
                'immediate_actions': recommendations.get('immediate_actions', []),
                'predicted_failure_date': recommendations.get('predicted_failure_date', None),
                'recommendation_details': recommendations.get('recommendation_details', '')
            }
            
            self._log_execution(
                device_id,
                'completed',
                f"Diagnosis: {diagnosis} | Confidence: {confidence:.2f} | Action: {recommended_action}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[DiagnosisAgent] Error diagnosing {device_id}: {str(e)}", exc_info=True)
            return {
                'device_id': input_data.get('device_id', 'unknown'),
                'status': 'error',
                'error': str(e)
            }
    
    def _build_recommendations(
        self,
        device_id: str,
        equipment_type: str,
        action: str,
        diagnosis: str,
        anomalies: List[str],
        severity: str,
        llm_used: bool = False
    ) -> Dict[str, Any]:
        """
        Build rich recommendation fields for dashboard display
        
        Returns: {
            'insights': str,  # Analysis reasoning explaining the action
            'immediate_actions': List[str],  # Steps to take now
            'predicted_failure_date': str,  # ISO date when failure expected
            'recommendation_details': str  # Detailed explanation
        }
        """
        from datetime import datetime, timedelta
        
        immediate_actions = []
        predicted_failure_date = None
        insights = ""
        recommendation_details = ""
        
        # Determine analysis source prefix
        analysis_source = "LLM-based Analysis" if llm_used else "Rule-Based Analysis"
        
        if action == 'URGENT_REPAIR':
            immediate_actions = [
                f"Stop {equipment_type} operations immediately",
                "Isolate equipment from production line",
                "Inspect for visible damage or wear",
                f"Replace critical components (bearings/seals/valves)",
                "Run full diagnostics before restart"
            ]
            predicted_failure_date = datetime.utcnow().isoformat()  # Imminent failure
            insights = f"{analysis_source}: Device is in critical condition. {diagnosis}. Continued operation poses safety/reliability risks."
            recommendation_details = f"URGENT: {diagnosis}. Equipment failure is imminent. Immediate emergency repair required to prevent catastrophic failure and production loss."
        
        elif action == 'SCHEDULE_MAINTENANCE':
            immediate_actions = [
                "Schedule preventive maintenance window (1-2 weeks)",
                f"Order necessary replacement parts ({self._get_parts_for_anomaly(anomalies)})",
                "Notify operations of planned downtime",
                "Prepare maintenance crew and tools",
                "Monitor equipment closely until maintenance window"
            ]
            predicted_failure_date = (datetime.utcnow() + timedelta(days=14)).isoformat()
            insights = f"{analysis_source}: Device showing degradation patterns. {diagnosis}. Proactive maintenance can prevent failure."
            recommendation_details = f"PREVENTIVE: {diagnosis}. Schedule maintenance within 2 weeks to address degradation. Parts and labor should be budgeted."
        
        else:  # MONITOR_ONLY
            immediate_actions = [
                "Continue normal operations",
                "Perform routine inspections per schedule",
                "Monitor sensor readings for changes",
                "Log equipment status in maintenance tracking system"
            ]
            predicted_failure_date = None
            insights = f"{analysis_source}: Equipment operating within normal parameters."
            recommendation_details = f"MONITOR: {diagnosis}. No action required at this time. Continue regular monitoring schedule."
        
        return {
            'insights': insights,
            'immediate_actions': immediate_actions,
            'predicted_failure_date': predicted_failure_date,
            'recommendation_details': recommendation_details
        }
    
    def _get_parts_for_anomaly(self, anomalies: List[str]) -> str:
        """Extract part types from anomalies"""
        if not anomalies:
            return "standard parts"
        
        parts = []
        for anomaly in anomalies:
            if "vibration" in str(anomaly).lower():
                parts.append("bearings")
            elif "temperature" in str(anomaly).lower():
                parts.append("seals")
            elif "pressure" in str(anomaly).lower():
                parts.append("valves")
        
        return " / ".join(parts) if parts else "standard parts"
    
    def _match_patterns(
        self,
        equipment_type: str,
        anomalies: List[str],
        current_reading: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STEP 1: Match sensor anomalies against equipment-specific rules
        
        Returns: {
            'diagnosis': str,
            'confidence': float (0.0-1.0),
            'action': str (URGENT_REPAIR | SCHEDULE_MAINTENANCE | MONITOR_ONLY),
            'severity': str (low | medium | high)
        }
        """
        
        if equipment_type == "PUMP":
            return self._match_pump_patterns(anomalies, current_reading)
        elif equipment_type == "MOTOR":
            return self._match_motor_patterns(anomalies, current_reading)
        elif equipment_type == "COMPRESSOR":
            return self._match_compressor_patterns(anomalies, current_reading)
        elif equipment_type == "GENERATOR":
            return self._match_generator_patterns(anomalies, current_reading)
        else:
            return {
                'diagnosis': 'Unknown equipment type',
                'confidence': 0.0,
                'action': 'MONITOR_ONLY',
                'severity': 'low'
            }
    
    def _match_pump_patterns(self, anomalies: List[str], reading: Dict[str, Any]) -> Dict[str, Any]:
        """Match PUMP failure patterns"""
        
        # Story 4: Critical - temp 98°C + vibration critical
        if any('temperature_high' in a and '98' in a for a in anomalies):
            if any('vibration' in a for a in anomalies):
                return {
                    'diagnosis': 'Pump cavitation with bearing failure - CRITICAL',
                    'confidence': 0.96,
                    'action': 'URGENT_REPAIR',
                    'severity': 'high'
                }
        
        # Story 2: pressure fluctuation + high vibration = valve wear
        has_pressure_anomaly = any('pressure' in a for a in anomalies)
        has_high_vibration = any('vibration_high' in a for a in anomalies)
        
        if has_pressure_anomaly and has_high_vibration:
            return {
                'diagnosis': 'Pump valve wear - pressure unstable with high vibration',
                'confidence': 0.88,
                'action': 'SCHEDULE_MAINTENANCE',
                'severity': 'high'
            }
        
        # Bearing wear pattern
        if any('vibration_high' in a for a in anomalies) and any('temperature' in a for a in anomalies):
            return {
                'diagnosis': 'Bearing degradation',
                'confidence': 0.85,
                'action': 'SCHEDULE_MAINTENANCE',
                'severity': 'high'
            }
        
        # Generic issues
        if any('vibration' in a for a in anomalies):
            return {
                'diagnosis': 'Elevated vibration levels - possible mechanical wear',
                'confidence': 0.72,
                'action': 'SCHEDULE_MAINTENANCE',
                'severity': 'medium'
            }
        
        return {
            'diagnosis': 'Minor anomalies detected',
            'confidence': 0.60,
            'action': 'MONITOR_ONLY',
            'severity': 'low'
        }
    
    def _match_motor_patterns(self, anomalies: List[str], reading: Dict[str, Any]) -> Dict[str, Any]:
        """Match MOTOR failure patterns"""
        
        has_temp = any('temperature' in a for a in anomalies)
        has_vibration = any('vibration' in a for a in anomalies)
        
        # Story 3: temperature elevated + medium vibration (ambiguous)
        if has_temp and any('medium' in a or ('vibration' in a and 'high' not in a) for a in anomalies):
            return {
                'diagnosis': 'Motor condition ambiguous - possible bearing degradation or sensor calibration issue',
                'confidence': 0.72,
                'action': 'SCHEDULE_MAINTENANCE',
                'severity': 'medium'
            }
        
        # Critical bearing failure
        if has_temp and has_vibration and any('high' in a for a in anomalies):
            return {
                'diagnosis': 'Motor bearing degradation - CRITICAL',
                'confidence': 0.90,
                'action': 'URGENT_REPAIR',
                'severity': 'high'
            }
        
        if has_temp:
            return {
                'diagnosis': 'Motor elevated temperature',
                'confidence': 0.75,
                'action': 'MONITOR_ONLY',
                'severity': 'medium'
            }
        
        return {
            'diagnosis': 'Motor operating normally',
            'confidence': 0.90,
            'action': 'MONITOR_ONLY',
            'severity': 'low'
        }
    
    def _match_compressor_patterns(self, anomalies: List[str], reading: Dict[str, Any]) -> Dict[str, Any]:
        """Match COMPRESSOR failure patterns"""
        
        if any('temperature' in a or 'discharge_temp' in a for a in anomalies):
            return {
                'diagnosis': 'Compressor thermal stress - possible valve issue',
                'confidence': 0.82,
                'action': 'SCHEDULE_MAINTENANCE',
                'severity': 'high'
            }
        
        return {
            'diagnosis': 'Compressor operating normally',
            'confidence': 0.90,
            'action': 'MONITOR_ONLY',
            'severity': 'low'
        }
    
    def _match_generator_patterns(self, anomalies: List[str], reading: Dict[str, Any]) -> Dict[str, Any]:
        """Match GENERATOR failure patterns"""
        
        if any('voltage' in a for a in anomalies):
            return {
                'diagnosis': 'Generator voltage regulation issue',
                'confidence': 0.80,
                'action': 'SCHEDULE_MAINTENANCE',
                'severity': 'medium'
            }
        
        return {
            'diagnosis': 'Generator operating normally',
            'confidence': 0.95,
            'action': 'MONITOR_ONLY',
            'severity': 'low'
        }
    
    async def _execute_action(
        self,
        device_id: str,
        equipment_type: str,
        action: str,
        anomalies: List[str],
        current_reading: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        STEP 4: Execute the recommended action via MCP tools
        
        Actions:
        - URGENT_REPAIR: Create emergency work order (MCP: create-work-order)
        - SCHEDULE_MAINTENANCE: Schedule maintenance with automatic spare parts validation (MCP: get-spare-parts, schedule-maintenance, create-work-order)
        - MONITOR_ONLY: No action, just log and recommend re-check
        """
        
        try:
            # Initialize GatewayClient if not already done
            if not self.gateway_client:
                self.gateway_client = GatewayClient()
            
            if action == 'URGENT_REPAIR':
                logger.info(f"[_execute_action] URGENT_REPAIR: Calling create-work-order for {device_id}")
                
                # Use sync call (wrapped in async context)
                tool_result = self.gateway_client.call_tool(
                    tool_name="create-work-order",
                    arguments={
                        "work_order_type": "repair",
                        "priority": "critical",
                        "description": f"CRITICAL: {equipment_type} ({device_id}) failure detected. Anomalies: {', '.join(anomalies) if anomalies else 'Multiple critical parameters exceeded'}. Immediate repair required."
                    }
                )
                
                logger.info(f"[_execute_action] Work order result: {tool_result}")
                
                return {
                    'description': f'Emergency work order created for {device_id}',
                    'tools': {
                        'create-work-order': tool_result
                    }
                }
            
            elif action == 'SCHEDULE_MAINTENANCE':
                logger.info(f"[_execute_action] SCHEDULE_MAINTENANCE: MANDATORY spare parts validation before scheduling")
                
                # IMPORTANT: Before scheduling ANY maintenance, validate spare parts availability
                # This reduces risk of scheduling work that cannot proceed due to missing parts
                
                # Step 1: Determine what parts are needed from anomalies
                part_type = "bearing"  # Default
                if anomalies:
                    if any("vibration" in str(a).lower() for a in anomalies):
                        part_type = "bearing"
                    elif any("temperature" in str(a).lower() for a in anomalies):
                        part_type = "seal"
                    elif any("pressure" in str(a).lower() for a in anomalies):
                        part_type = "valve"
                
                logger.info(f"[_execute_action] Checking spare parts availability (part_type: {part_type})")
                
                # Step 2: Check spare parts availability
                parts_result = self.gateway_client.call_tool(
                    tool_name="get-spare-parts",
                    arguments={
                        "part_type": part_type,
                        "category": "mechanical"
                    }
                )
                
                logger.info(f"[_execute_action] Spare parts check result: {parts_result}")
                
                # Step 3: Parse response body if it's a JSON string
                parts_data = parts_result
                if isinstance(parts_result.get("body"), str):
                    try:
                        parts_data = json.loads(parts_result.get("body"))
                        logger.info(f"[_execute_action] Parsed body: {parts_data}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"[_execute_action] Failed to parse body as JSON: {e}")
                        parts_data = {}
                
                # Step 4: Decide next action based on parts availability
                from datetime import datetime, timedelta
                scheduled_date = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
                
                if parts_data.get("parts") and len(parts_data.get("parts", [])) > 0:
                    # Parts available - proceed with maintenance scheduling
                    logger.info(f"[_execute_action] Parts available, proceeding with maintenance scheduling")
                    
                    maintenance_result = self.gateway_client.call_tool(
                        tool_name="schedule-maintenance",
                        arguments={
                            "device_id": device_id,
                            "maintenance_type": "preventive",
                            "scheduled_date": scheduled_date
                        }
                    )
                    
                    logger.info(f"[_execute_action] Maintenance scheduled: {maintenance_result}")
                    
                    return {
                        'description': f'Spare parts validated and available. Preventive maintenance scheduled for {device_id}',
                        'tools': {
                            'get-spare-parts': parts_result,
                            'schedule-maintenance': maintenance_result
                        }
                    }
                else:
                    # Parts NOT available - escalate to work order for procurement
                    logger.warning(f"[_execute_action] Spare parts NOT available. Escalating to procurement work order")
                    
                    work_order_result = self.gateway_client.call_tool(
                        tool_name="create-work-order",
                        arguments={
                            "work_order_type": "procurement",
                            "priority": "high",
                            "description": f"PROCUREMENT REQUIRED: {equipment_type} ({device_id}) requires {part_type} for maintenance. Parts not currently in stock. Please procure and contact scheduling team."
                        }
                    )
                    
                    logger.info(f"[_execute_action] Procurement work order created: {work_order_result}")
                    
                    return {
                        'description': f'Spare parts unavailable. Procurement work order created for {device_id}',
                        'tools': {
                            'get-spare-parts': parts_result,
                            'create-work-order': work_order_result
                        }
                    }
            
            else:  # MONITOR_ONLY
                logger.info(f"[_execute_action] MONITOR_ONLY: No action required for {device_id}")
                return {
                    'description': 'No action required. Continue monitoring.',
                    'tools': {}
                }
        
        except Exception as e:
            logger.error(f"[_execute_action] Error executing action: {str(e)}", exc_info=True)
            return {
                'description': f'Error executing action: {str(e)}',
                'tools': {
                    'error': str(e)
                }
            }
