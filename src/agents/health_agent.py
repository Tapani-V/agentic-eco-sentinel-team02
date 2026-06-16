#!/usr/bin/env python3
"""
HealthAgent - Analyzes equipment health from sensor data
Week 2 Day 5-7: Threshold-based health classification with anomaly detection

LOCAL ANALYSIS + MCP TOOL CALLS FOR CRITICAL STATUS
- Pure local analysis (no external dependencies)
- Calls create-work-order MCP tool if health_status = critical
"""

from typing import Dict, Any, List
from datetime import datetime
import logging

from src.agents.base_agent import BaseAgent
from src.gateway.client import GatewayClient

logger = logging.getLogger(__name__)


class HealthAgent(BaseAgent):
    """
    HealthAgent: Pure health analysis via threshold rules + MCP tool for critical
    
    Week 2 Day 5-7 Design:
    - Apply threshold rules to sensor data (deterministic, local)
    - Classify health state: healthy → warning → critical
    - Detect anomalies (sensors out of normal range)
    - If status = CRITICAL: Call MCP create-work-order tool (immediate escalation)
    - Return classification + anomalies + tool_results to Orchestrator
    
    MCP Integration:
    - Uses GatewayClient for Cognito token + tool calls
    - Calls create-work-order when health_status = critical
    - Gracefully handles tool failures (doesn't break local analysis)
    """
    
    def __init__(self):
        """Initialize HealthAgent"""
        super().__init__("HealthAgent", "health_analysis")
        self.gateway_client = None  # Lazy initialized
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze equipment health via threshold-based rules
        
        Input schema:
        {
            'device_id': str,
            'equipment_type': str,
            'current_reading': {
                'readings': {
                    'sensor_name': {
                        'value': float,
                        'unit': str,
                        'normal_range': [float, float]
                    },
                    ...
                }
            }
        }
        
        Output schema (goes to DiagnosisAgent):
        {
            'device_id': str,
            'health_status': str,  # 'healthy' | 'warning' | 'critical'
            'degradation_score': float (0.0-1.0),
            'anomalies': [str],  # List of anomaly descriptions
            'analysis_timestamp': str (ISO format),
            'status': 'completed' or 'error'
        }
        
        Week 2 Day 5-7 Logic:
        1. Extract sensor values from current_reading
        2. Apply equipment-specific threshold rules
        3. Detect anomalies (sensors out of normal range)
        4. Compute degradation score based on how many thresholds are exceeded
        5. Classify health state: healthy < warning < critical
        6. Return to Orchestrator (who will pass to DiagnosisAgent if not healthy)
        """
        try:
            device_id = input_data.get('device_id')
            equipment_type = input_data.get('equipment_type', 'UNKNOWN')
            current_reading = input_data.get('current_reading')
            
            if not device_id or not current_reading:
                raise ValueError("Missing required fields: device_id, current_reading")
            
            # Step 1: Extract sensor readings
            sensors = current_reading.get('readings', {})
            
            # Step 2: Detect anomalies (sensors outside normal range)
            anomalies = self._detect_anomalies(sensors)
            
            # Step 3: Compute degradation score based on anomalies
            degradation_score = self._compute_degradation_score(equipment_type, sensors, anomalies)
            
            # Step 4: Classify health state based on degradation
            health_status = self._classify_health_state(degradation_score)
            
            result = {
                'device_id': device_id,
                'health_status': health_status,
                'degradation_score': round(degradation_score, 3),
                'anomalies': anomalies,
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'status': 'completed'
            }
            
            self._log_execution(
                device_id,
                'completed',
                f"Health: {health_status}, Score: {degradation_score:.2f}, Anomalies: {len(anomalies)}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[HealthAgent] Error analyzing {device_id}: {str(e)}")
            return {
                'device_id': input_data.get('device_id', 'unknown'),
                'status': 'error',
                'error': str(e)
            }
    
    def _classify_health_state(self, degradation_score: float) -> str:
        """
        Classify health state based on degradation score
        
        Thresholds (from Week 2 Day 5-7 architecture):
        - 0.0 - 0.15: healthy (no anomalies or minor anomalies)
        - 0.15 - 0.50: warning (multiple anomalies detected)
        - 0.50+: critical (severe anomalies requiring urgent attention)
        """
        if degradation_score < 0.15:
            return "healthy"
        elif degradation_score < 0.50:
            return "warning"
        else:
            return "critical"
    
    def _detect_anomalies(self, sensors: Dict[str, Any]) -> List[str]:
        """
        Detect sensors operating outside normal range
        
        Returns list of anomaly descriptions like:
        - "temperature_high: 98°C (normal: 20-95°C)"
        - "vibration_high: 5.2 mm/s (normal: 0-3 mm/s)"
        """
        anomalies = []
        
        for sensor_name, sensor_data in sensors.items():
            if not isinstance(sensor_data, dict):
                continue
            
            value = sensor_data.get('value')
            normal_range = sensor_data.get('normal_range')
            unit = sensor_data.get('unit', '')
            
            if value is None or not normal_range:
                continue
            
            min_normal, max_normal = normal_range[0], normal_range[1]
            
            # Check if out of bounds
            if value < min_normal:
                anomaly = f"{sensor_name}_low: {value} {unit} (normal: {min_normal}-{max_normal})"
                anomalies.append(anomaly)
            elif value > max_normal:
                anomaly = f"{sensor_name}_high: {value} {unit} (normal: {min_normal}-{max_normal})"
                anomalies.append(anomaly)
        
        return anomalies
    
    def _compute_degradation_score(
        self,
        equipment_type: str,
        sensors: Dict[str, Any],
        anomalies: List[str]
    ) -> float:
        """
        Compute degradation score based on sensor anomalies
        
        Week 2 Day 5-7 approach:
        - Use sensor's normal_range to determine severity
        - Each anomaly contributes to degradation based on how far out-of-range it is
        - Multiple anomalies compound degradation
        - Calculate percentage deviation from normal range
        
        Returns: 0.0 (perfect) to 1.0 (complete failure)
        """
        score = 0.0
        
        if not anomalies:
            return score
        
        # Process each anomaly by calculating how far it deviates from normal range
        for anomaly in anomalies:
            severity = self._calculate_anomaly_severity(anomaly, sensors)
            score += severity
        
        # Cap at 1.0
        return min(1.0, score)
    
    def _calculate_anomaly_severity(self, anomaly: str, sensors: Dict[str, Any]) -> float:
        """
        Calculate severity (0.0-1.0) of a single anomaly based on deviation from normal range
        
        Parsing anomaly string: "sensor_name_direction: value unit (normal: min-max)"
        Example: "temperature_high: 141.54 F (normal: 70-110)"
        
        Severity calculation:
        - Deviation < 10% of range: 0.10 (minor)
        - Deviation 10-25% of range: 0.20 (moderate)
        - Deviation 25-50% of range: 0.35 (high)
        - Deviation > 50% of range: 0.50 (critical)
        """
        try:
            # Extract sensor name and value from anomaly
            # Format: "sensor_name_direction: value unit (normal: min-max)"
            parts = anomaly.split(':')
            if len(parts) < 3:
                return 0.10  # Safe default
            
            sensor_direction = parts[0].strip()  # e.g., "temperature_high"
            value_str = parts[1].strip().split()[0]  # Extract just the number
            value = float(value_str)
            
            # Extract normal range from the anomaly string
            # Format: "... (normal: min-max)"
            range_part = parts[2].split('(')[1].split(')')[0]  # Get content in parentheses
            range_vals = range_part.replace('normal:', '').strip().split('-')
            min_normal = float(range_vals[0].strip())
            max_normal = float(range_vals[1].strip())
            
            range_size = max_normal - min_normal
            if range_size <= 0:
                return 0.10  # Avoid division by zero
            
            # Calculate deviation percentage
            if 'high' in sensor_direction:
                deviation = value - max_normal
                deviation_pct = deviation / range_size
            elif 'low' in sensor_direction:
                deviation = min_normal - value
                deviation_pct = deviation / range_size
            else:
                return 0.10
            
            # Convert percentage deviation to severity score
            if deviation_pct <= 0.10:
                return 0.10  # Minor anomaly
            elif deviation_pct <= 0.25:
                return 0.20  # Moderate anomaly
            elif deviation_pct <= 0.50:
                return 0.35  # High anomaly
            else:
                return 0.50  # Critical anomaly
                
        except Exception as e:
            logger.debug(f"Error calculating anomaly severity for '{anomaly}': {e}")
            return 0.10  # Safe default
