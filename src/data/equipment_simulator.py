#!/usr/bin/env python3
"""
Equipment Simulator - Phase 1 Week 1 Day 3-4
Generates realistic 30-day sensor data with authentic degradation patterns.
Based on Phase 2.8 proven approach.

Features:
- 4 degradation scenarios (healthy, gradual, intermittent, catastrophic)
- Equipment-specific sensor physics
- Realistic sensor correlations
- 16 devices with mixed health states
- 30 days × 24 readings/day = 720 readings per device
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import logging
import argparse

logger = logging.getLogger(__name__)


class EquipmentSimulator:
    """Generates realistic sensor readings for a device with degradation"""
    
    # Equipment parameters (nominal values, ranges)
    EQUIPMENT_PARAMS = {
        "MOTOR": {
            "rpm": {"nominal": 3500, "min": 0, "max": 3600, "normal": [3450, 3550], "unit": "RPM"},
            "current": {"nominal": 70, "min": 0, "max": 100, "normal": [60, 80], "unit": "Amps"},
            "temperature": {"nominal": 85, "min": 32, "max": 302, "normal": [60, 120], "unit": "F"},
            "voltage": {"nominal": 380, "min": 0, "max": 500, "normal": [350, 410], "unit": "V"},
            "power_factor": {"nominal": 0.96, "min": 0.5, "max": 1.0, "normal": [0.90, 1.0], "unit": "PF"},
            "vibration": {"nominal": 0.5, "min": 0, "max": 15, "normal": [0, 2], "unit": "mm/s"}
        },
        "PUMP": {
            "flow": {"nominal": 600, "min": 0, "max": 1000, "normal": [500, 700], "unit": "GPM"},
            "pressure": {"nominal": 150, "min": 0, "max": 300, "normal": [140, 160], "unit": "PSI"},
            "temperature": {"nominal": 85, "min": 32, "max": 250, "normal": [70, 110], "unit": "F"},
            "vibration": {"nominal": 0.4, "min": 0, "max": 15, "normal": [0, 1.5], "unit": "mm/s"},
            "suction_pressure": {"nominal": 10, "min": -5, "max": 50, "normal": [5, 15], "unit": "PSI"}
        },
        "COMPRESSOR": {
            "discharge_pressure": {"nominal": 100, "min": 0, "max": 200, "normal": [90, 110], "unit": "PSI"},
            "discharge_temp": {"nominal": 150, "min": 50, "max": 250, "normal": [130, 170], "unit": "F"},
            "inlet_temp": {"nominal": 90, "min": 50, "max": 150, "normal": [80, 100], "unit": "F"},
            "motor_current": {"nominal": 100, "min": 0, "max": 200, "normal": [80, 120], "unit": "Amps"},
            "cooling_water_temp": {"nominal": 80, "min": 50, "max": 120, "normal": [70, 90], "unit": "F"}
        },
        "GENERATOR": {
            "voltage": {"nominal": 400, "min": 0, "max": 500, "normal": [380, 420], "unit": "V"},
            "current": {"nominal": 250, "min": 0, "max": 500, "normal": [150, 350], "unit": "Amps"},
            "frequency": {"nominal": 60.0, "min": 45, "max": 65, "normal": [59.9, 60.1], "unit": "Hz"},
            "temperature": {"nominal": 110, "min": 32, "max": 200, "normal": [90, 130], "unit": "F"},
            "power_factor": {"nominal": 0.95, "min": 0.5, "max": 1.0, "normal": [0.90, 1.0], "unit": "PF"}
        }
    }
    
    def __init__(self, device_id: str, equipment_type: str, scenario: str = "healthy"):
        """
        Initialize simulator for a device
        
        Args:
            device_id: Device identifier
            equipment_type: Type of equipment (MOTOR, PUMP, COMPRESSOR, GENERATOR)
            scenario: degradation scenario (healthy, gradual_degradation, intermittent, catastrophic)
        """
        self.device_id = device_id
        self.equipment_type = equipment_type
        self.scenario = scenario
        self.params = self.EQUIPMENT_PARAMS.get(equipment_type, {})
    
    def generate_30_days(self, start_date: datetime = None, readings_per_day: int = 24) -> List[Dict[str, Any]]:
        """
        Generate 30 days of sensor readings
        
        Args:
            start_date: Starting date (default: May 1, 2026)
            readings_per_day: Readings per day (default: 24 hourly)
        
        Returns:
            List of sensor readings
        """
        if start_date is None:
            start_date = datetime(2026, 5, 1)
        
        readings = []
        total_readings = 30 * readings_per_day
        
        for reading_num in range(total_readings):
            day = reading_num // readings_per_day + 1
            hour = (reading_num % readings_per_day)
            
            # Calculate degradation for this point in time
            degradation = self._calculate_degradation_for_day(day)
            
            # Generate timestamp
            timestamp = start_date + timedelta(days=day-1, hours=hour)
            
            # Generate reading with correlation
            reading = self._generate_correlated_reading(timestamp, degradation, day)
            readings.append(reading)
        
        return readings
    
    def _calculate_degradation_for_day(self, day: int) -> float:
        """
        Calculate degradation level for a specific day.
        Different scenarios have different degradation curves.
        
        Degradation scale:
        - 0.0-0.15: Healthy
        - 0.15-0.50: Warning (multiple anomalies detected)
        - 0.50+: Critical (severe anomalies requiring urgent attention)
        """
        if self.scenario == "healthy":
            # Stay healthy throughout (< 0.10)
            return 0.03 + random.uniform(-0.01, 0.01)
        
        elif self.scenario == "gradual_degradation":
            # Smooth increase from healthy to degrading (0.10-0.25)
            if day <= 15:
                degradation = 0.08 + day * 0.008 + random.uniform(-0.01, 0.01)
            else:
                degradation = 0.20 + (day - 15) * 0.005 + random.uniform(-0.02, 0.02)
            return min(0.30, max(0.08, degradation))
        
        elif self.scenario == "intermittent":
            # Warning level with occasional anomalies (0.28-0.35)
            baseline = 0.30 + day * 0.001
            
            # 30% chance of spike to mid-warning range
            if random.random() < 0.30:
                return 0.33 + random.uniform(0, 0.05)
            else:
                return baseline + random.uniform(-0.02, 0.02)
        
        elif self.scenario == "catastrophic":
            # Critical stage - very high degradation (>0.42)
            degradation = 0.80 + day * 0.008 + random.uniform(-0.02, 0.02)
            return min(0.99, max(0.80, degradation))
        
        else:
            return 0.1
    
    def _generate_correlated_reading(self, timestamp: datetime, degradation: float, day: int) -> Dict[str, Any]:
        """
        Generate sensor readings with realistic correlations.
        As degradation increases, sensors respond in equipment-specific ways.
        """
        reading = {
            "device_id": self.device_id,
            "equipment_type": self.equipment_type,
            "timestamp": timestamp.isoformat(),
            "degradation_score": round(degradation, 3),
            "health_state": self._get_health_state(degradation),
            "readings": {}
        }
        
        # Generate sensors based on equipment type
        if self.equipment_type == "MOTOR":
            reading["readings"] = self._generate_motor_sensors(degradation)
        elif self.equipment_type == "PUMP":
            reading["readings"] = self._generate_pump_sensors(degradation)
        elif self.equipment_type == "COMPRESSOR":
            reading["readings"] = self._generate_compressor_sensors(degradation)
        elif self.equipment_type == "GENERATOR":
            reading["readings"] = self._generate_generator_sensors(degradation)
        
        return reading
    
    def _get_health_state(self, degradation: float) -> str:
        """Map degradation score to health state (3-state system)"""
        if degradation < 0.15:
            return "healthy"
        elif degradation < 0.50:
            return "warning"
        else:
            return "critical"
    
    def _generate_motor_sensors(self, degradation: float) -> Dict[str, Any]:
        """Generate MOTOR sensor readings with realistic degradation"""
        p = self.params
        
        # Degradation effects on sensors
        rpm_effect = -150 * degradation
        current_effect = 120 * degradation
        temp_effect = 200 * degradation
        pf_effect = -0.40 * degradation
        vib_effect = 15 * degradation
        
        rpm = p["rpm"]["nominal"] + rpm_effect + random.gauss(0, 10)
        current = p["current"]["nominal"] + current_effect + random.gauss(0, 2)
        temperature = p["temperature"]["nominal"] + temp_effect + random.gauss(0, 3)
        voltage = p["voltage"]["nominal"] - 12 * degradation + random.gauss(0, 5)
        power_factor = p["power_factor"]["nominal"] + pf_effect + random.gauss(0, 0.01)
        vibration = p["vibration"]["nominal"] + vib_effect + random.gauss(0, 0.1)
        
        return {
            "rpm": {
                "value": round(max(p["rpm"]["min"], min(p["rpm"]["max"], rpm)), 2),
                "unit": p["rpm"]["unit"],
                "min": p["rpm"]["min"],
                "max": p["rpm"]["max"],
                "normal_range": p["rpm"]["normal"]
            },
            "current": {
                "value": round(max(p["current"]["min"], min(p["current"]["max"], current)), 2),
                "unit": p["current"]["unit"],
                "min": p["current"]["min"],
                "max": p["current"]["max"],
                "normal_range": p["current"]["normal"]
            },
            "temperature": {
                "value": round(max(p["temperature"]["min"], min(p["temperature"]["max"], temperature)), 2),
                "unit": p["temperature"]["unit"],
                "min": p["temperature"]["min"],
                "max": p["temperature"]["max"],
                "normal_range": p["temperature"]["normal"]
            },
            "voltage": {
                "value": round(max(p["voltage"]["min"], min(p["voltage"]["max"], voltage)), 2),
                "unit": p["voltage"]["unit"],
                "min": p["voltage"]["min"],
                "max": p["voltage"]["max"],
                "normal_range": p["voltage"]["normal"]
            },
            "power_factor": {
                "value": round(max(p["power_factor"]["min"], min(p["power_factor"]["max"], power_factor)), 4),
                "unit": p["power_factor"]["unit"],
                "min": p["power_factor"]["min"],
                "max": p["power_factor"]["max"],
                "normal_range": p["power_factor"]["normal"]
            },
            "vibration": {
                "value": round(max(p["vibration"]["min"], min(p["vibration"]["max"], vibration)), 2),
                "unit": p["vibration"]["unit"],
                "min": p["vibration"]["min"],
                "max": p["vibration"]["max"],
                "normal_range": p["vibration"]["normal"]
            }
        }
    
    def _generate_pump_sensors(self, degradation: float) -> Dict[str, Any]:
        """Generate PUMP sensor readings"""
        p = self.params
        
        flow_effect = -400 * (degradation ** 1.5)
        pressure_effect = -150 * degradation
        temp_effect = 180 * degradation
        vib_effect = 12 * degradation
        
        flow = p["flow"]["nominal"] + flow_effect + random.gauss(0, 20)
        pressure = p["pressure"]["nominal"] + pressure_effect + random.gauss(0, 5)
        temperature = p["temperature"]["nominal"] + temp_effect + random.gauss(0, 3)
        vibration = p["vibration"]["nominal"] + vib_effect + random.gauss(0, 0.1)
        suction_pressure = p["suction_pressure"]["nominal"] - 6 * degradation + random.gauss(0, 1)
        
        return {
            "flow": {
                "value": round(max(p["flow"]["min"], min(p["flow"]["max"], flow)), 2),
                "unit": p["flow"]["unit"],
                "min": p["flow"]["min"],
                "max": p["flow"]["max"],
                "normal_range": p["flow"]["normal"]
            },
            "pressure": {
                "value": round(max(p["pressure"]["min"], min(p["pressure"]["max"], pressure)), 2),
                "unit": p["pressure"]["unit"],
                "min": p["pressure"]["min"],
                "max": p["pressure"]["max"],
                "normal_range": p["pressure"]["normal"]
            },
            "temperature": {
                "value": round(max(p["temperature"]["min"], min(p["temperature"]["max"], temperature)), 2),
                "unit": p["temperature"]["unit"],
                "min": p["temperature"]["min"],
                "max": p["temperature"]["max"],
                "normal_range": p["temperature"]["normal"]
            },
            "vibration": {
                "value": round(max(p["vibration"]["min"], min(p["vibration"]["max"], vibration)), 2),
                "unit": p["vibration"]["unit"],
                "min": p["vibration"]["min"],
                "max": p["vibration"]["max"],
                "normal_range": p["vibration"]["normal"]
            },
            "suction_pressure": {
                "value": round(max(p["suction_pressure"]["min"], min(p["suction_pressure"]["max"], suction_pressure)), 2),
                "unit": p["suction_pressure"]["unit"],
                "min": p["suction_pressure"]["min"],
                "max": p["suction_pressure"]["max"],
                "normal_range": p["suction_pressure"]["normal"]
            }
        }
    
    def _generate_compressor_sensors(self, degradation: float) -> Dict[str, Any]:
        """Generate COMPRESSOR sensor readings"""
        p = self.params
        
        pressure_effect = -200 * degradation
        temp_effect = 250 * degradation
        current_effect = 140 * degradation
        
        discharge_pressure = p["discharge_pressure"]["nominal"] + pressure_effect + random.gauss(0, 5)
        discharge_temp = p["discharge_temp"]["nominal"] + temp_effect + random.gauss(0, 5)
        inlet_temp = p["inlet_temp"]["nominal"] + 25 * degradation + random.gauss(0, 2)
        motor_current = p["motor_current"]["nominal"] + current_effect + random.gauss(0, 5)
        cooling_water_temp = p["cooling_water_temp"]["nominal"] + 40 * degradation + random.gauss(0, 3)
        
        return {
            "discharge_pressure": {
                "value": round(max(p["discharge_pressure"]["min"], min(p["discharge_pressure"]["max"], discharge_pressure)), 2),
                "unit": p["discharge_pressure"]["unit"],
                "min": p["discharge_pressure"]["min"],
                "max": p["discharge_pressure"]["max"],
                "normal_range": p["discharge_pressure"]["normal"]
            },
            "discharge_temp": {
                "value": round(max(p["discharge_temp"]["min"], min(p["discharge_temp"]["max"], discharge_temp)), 2),
                "unit": p["discharge_temp"]["unit"],
                "min": p["discharge_temp"]["min"],
                "max": p["discharge_temp"]["max"],
                "normal_range": p["discharge_temp"]["normal"]
            },
            "inlet_temp": {
                "value": round(max(p["inlet_temp"]["min"], min(p["inlet_temp"]["max"], inlet_temp)), 2),
                "unit": p["inlet_temp"]["unit"],
                "min": p["inlet_temp"]["min"],
                "max": p["inlet_temp"]["max"],
                "normal_range": p["inlet_temp"]["normal"]
            },
            "motor_current": {
                "value": round(max(p["motor_current"]["min"], min(p["motor_current"]["max"], motor_current)), 2),
                "unit": p["motor_current"]["unit"],
                "min": p["motor_current"]["min"],
                "max": p["motor_current"]["max"],
                "normal_range": p["motor_current"]["normal"]
            },
            "cooling_water_temp": {
                "value": round(max(p["cooling_water_temp"]["min"], min(p["cooling_water_temp"]["max"], cooling_water_temp)), 2),
                "unit": p["cooling_water_temp"]["unit"],
                "min": p["cooling_water_temp"]["min"],
                "max": p["cooling_water_temp"]["max"],
                "normal_range": p["cooling_water_temp"]["normal"]
            }
        }
    
    def _generate_generator_sensors(self, degradation: float) -> Dict[str, Any]:
        """Generate GENERATOR sensor readings"""
        p = self.params
        
        voltage_effect = -100 * degradation
        current_effect = 200 * degradation
        temp_effect = 180 * degradation
        pf_effect = -0.40 * degradation
        
        voltage = p["voltage"]["nominal"] + voltage_effect + random.gauss(0, 5)
        current = p["current"]["nominal"] + current_effect + random.gauss(0, 10)
        frequency = p["frequency"]["nominal"] + random.gauss(0, 0.05)
        temperature = p["temperature"]["nominal"] + temp_effect + random.gauss(0, 3)
        power_factor = p["power_factor"]["nominal"] + pf_effect + random.gauss(0, 0.01)
        
        return {
            "voltage": {
                "value": round(max(p["voltage"]["min"], min(p["voltage"]["max"], voltage)), 2),
                "unit": p["voltage"]["unit"],
                "min": p["voltage"]["min"],
                "max": p["voltage"]["max"],
                "normal_range": p["voltage"]["normal"]
            },
            "current": {
                "value": round(max(p["current"]["min"], min(p["current"]["max"], current)), 2),
                "unit": p["current"]["unit"],
                "min": p["current"]["min"],
                "max": p["current"]["max"],
                "normal_range": p["current"]["normal"]
            },
            "frequency": {
                "value": round(frequency, 3),
                "unit": p["frequency"]["unit"],
                "min": p["frequency"]["min"],
                "max": p["frequency"]["max"],
                "normal_range": p["frequency"]["normal"]
            },
            "temperature": {
                "value": round(max(p["temperature"]["min"], min(p["temperature"]["max"], temperature)), 2),
                "unit": p["temperature"]["unit"],
                "min": p["temperature"]["min"],
                "max": p["temperature"]["max"],
                "normal_range": p["temperature"]["normal"]
            },
            "power_factor": {
                "value": round(max(p["power_factor"]["min"], min(p["power_factor"]["max"], power_factor)), 4),
                "unit": p["power_factor"]["unit"],
                "min": p["power_factor"]["min"],
                "max": p["power_factor"]["max"],
                "normal_range": p["power_factor"]["normal"]
            }
        }


class DataGenerator:
    """Generates 30-day data for all devices with mixed health states"""
    
    # Device scenarios: 16 devices across 4 health states
    DEVICE_SCENARIOS = {
        # Healthy devices (degradation < 0.10)
        "pump-001": {"type": "PUMP", "scenario": "healthy"},
        "motor-001": {"type": "MOTOR", "scenario": "healthy"},
        "compressor-001": {"type": "COMPRESSOR", "scenario": "healthy"},
        
        # Degrading devices (degradation 0.10-0.25)
        "pump-002": {"type": "PUMP", "scenario": "gradual_degradation"},
        "motor-002": {"type": "MOTOR", "scenario": "gradual_degradation"},
        "motor-003": {"type": "MOTOR", "scenario": "gradual_degradation"},
        "compressor-002": {"type": "COMPRESSOR", "scenario": "gradual_degradation"},
        "pump-003": {"type": "PUMP", "scenario": "gradual_degradation"},
        
        # Warning devices (degradation 0.25-0.42)
        "motor-004": {"type": "MOTOR", "scenario": "intermittent"},
        "compressor-003": {"type": "COMPRESSOR", "scenario": "intermittent"},
        "generator-001": {"type": "GENERATOR", "scenario": "intermittent"},
        
        # Critical devices (degradation > 0.42)
        "compressor-004": {"type": "COMPRESSOR", "scenario": "catastrophic"},
        "generator-002": {"type": "GENERATOR", "scenario": "catastrophic"},
        "generator-003": {"type": "GENERATOR", "scenario": "catastrophic"},
        "pump-004": {"type": "PUMP", "scenario": "catastrophic"},
        "pump-005": {"type": "PUMP", "scenario": "catastrophic"},
        "motor-005": {"type": "MOTOR", "scenario": "catastrophic"},
    }
    
    @staticmethod
    def generate_all_devices(output_dir: str = "data/generated"):
        """Generate 30-day data for all devices"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("=" * 70)
        logger.info("🚀 EQUIPMENT SIMULATOR - 30-Day Synthetic Data Generation")
        logger.info("=" * 70)
        logger.info(f"Generating data for {len(DataGenerator.DEVICE_SCENARIOS)} devices...\n")
        
        total_readings = 0
        
        for device_id, config in DataGenerator.DEVICE_SCENARIOS.items():
            logger.info(f"  Generating {device_id} ({config['scenario']})...")
            
            simulator = EquipmentSimulator(
                device_id=device_id,
                equipment_type=config['type'],
                scenario=config['scenario']
            )
            
            readings = simulator.generate_30_days(
                start_date=datetime(2026, 5, 1),
                readings_per_day=24
            )
            
            # Save to JSON
            file_path = output_path / f"{device_id}.json"
            with open(file_path, 'w') as f:
                json.dump(readings, f, indent=2)
            
            logger.info(f"    ✓ Saved {len(readings)} readings")
            total_readings += len(readings)
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ GENERATION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Total devices: {len(DataGenerator.DEVICE_SCENARIOS)}")
        logger.info(f"Total readings: {total_readings:,} ({total_readings // len(DataGenerator.DEVICE_SCENARIOS)} per device)")
        logger.info(f"Output directory: {output_path.resolve()}")
        logger.info("")


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Generate 30 days of synthetic equipment sensor data"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/generated",
        help="Output directory for JSON files (default: data/generated)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run generator
    DataGenerator.generate_all_devices(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
