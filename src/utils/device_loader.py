"""
Device Data Loader

Loads real sensor data from data/generated/ JSON files.
Returns the latest reading for a device along with metadata.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class DeviceLoader:
    """Load and manage device data from JSON files."""
    
    def __init__(self, data_dir: str = "data/generated"):
        """Initialize device loader with data directory."""
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")
    
    def list_available_devices(self) -> List[str]:
        """List all available devices (without .json extension)."""
        json_files = self.data_dir.glob("*.json")
        return sorted([f.stem for f in json_files])
    
    def load_device_history(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load complete history for a device."""
        file_path = self.data_dir / f"{device_id}.json"
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {device_id}.json: {e}")
    
    def get_latest_reading(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest sensor reading for a device."""
        history = self.load_device_history(device_id)
        if not history or len(history) == 0:
            return None
        
        # Return the last entry (most recent)
        return history[-1]
    
    def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get device status with latest reading formatted for agent processing.
        
        Returns:
        {
            "device_id": str,
            "equipment_type": str,
            "timestamp": str,
            "health_state": str,
            "degradation_score": float,
            "current_reading": {
                "readings": {...}  # Sensor readings in agent format
            }
        }
        """
        latest = self.get_latest_reading(device_id)
        if not latest:
            return None
        
        # Transform to agent format
        return {
            "device_id": latest.get("device_id"),
            "equipment_type": latest.get("equipment_type"),
            "timestamp": latest.get("timestamp"),
            "health_state": latest.get("health_state"),
            "degradation_score": latest.get("degradation_score"),
            "current_reading": {
                "readings": latest.get("readings", {})
            }
        }
    
    def get_device_summary(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get device summary with history stats.
        
        Returns info about device plus statistics from history.
        """
        latest = self.get_latest_reading(device_id)
        if not latest:
            return None
        
        history = self.load_device_history(device_id)
        
        # Calculate degradation trend
        if len(history) > 1:
            scores = [h.get("degradation_score", 0) for h in history[-10:]]  # Last 10 readings
            avg_score = sum(scores) / len(scores)
            trend = "improving" if scores[-1] < scores[0] else "degrading" if scores[-1] > scores[0] else "stable"
        else:
            avg_score = latest.get("degradation_score", 0)
            trend = "no_history"
        
        return {
            "device_id": latest.get("device_id"),
            "equipment_type": latest.get("equipment_type"),
            "last_reading_timestamp": latest.get("timestamp"),
            "current_health": latest.get("health_state"),
            "degradation_score": latest.get("degradation_score"),
            "average_degradation_score": avg_score,
            "trend": trend,
            "history_count": len(history),
            "readings_available": list(latest.get("readings", {}).keys())
        }
