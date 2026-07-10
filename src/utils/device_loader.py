"""
Device Data Loader

Phase 2 Migration: Loads sensor data from S3 bucket instead of local files.
Provides fallback to local files for development/testing.
Returns the latest reading for a device along with metadata.

Configuration via environment variables:
  AWS_PROFILE: AWS SSO profile name (required for S3 access)
  SYNTHETIC_DATA_BUCKET: S3 bucket name (e.g., 'agentic-ai-poc-synthetic-data')
  SYNTHETIC_DATA_PREFIX: S3 prefix for device files (e.g., 'devices/')
  USE_LOCAL_DATA: Set to 'true' to use local data instead of S3 (dev only)
  AWS_CA_BUNDLE: Path to CA certificate bundle (for corporate proxies)

Authentication:
  Uses AWS SSO profile or IAM role - no static credentials needed.
  Supports custom CA certificates via AWS_CA_BUNDLE for corporate environments.

SSL Certificate Issues (Corporate Networks):
  For corporate proxy/firewall SSL issues:
  1. AWS_CA_BUNDLE is automatically loaded from .agentcore.env
  2. Example in .agentcore.env: AWS_CA_BUNDLE=config/minimal_certificate_bundle.pem
  3. See AGENTCORE_MIGRATION_PHASE2_SSL_CERTIFICATE_SOLUTION.md for details
  
  DO NOT disable SSL verification (verify=False) - it's a security risk!
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DeviceLoader:
    """Load and manage device data from S3 (or local files as fallback)."""
    
    def __init__(
        self,
        data_dir: str = "data/generated",
        bucket: Optional[str] = None,
        prefix: str = "devices/",
        cache_ttl: int = 300,
        max_retries: int = 3
    ):
        """
        Initialize device loader with S3 configuration.
        
        Args:
            data_dir: Local directory for fallback (dev/testing)
            bucket: S3 bucket name (reads from env if not provided)
            prefix: S3 prefix for device files
            cache_ttl: Cache time-to-live in seconds (default 5 min)
            max_retries: Max retry attempts for S3 failures
        """
        # Load bucket from env or use provided value
        if bucket is None:
            bucket = os.getenv("SYNTHETIC_DATA_BUCKET")
        
        self.bucket = bucket
        self.prefix = prefix
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        
        # Local fallback configuration
        self.data_dir = Path(data_dir)
        self.use_local = os.getenv("USE_LOCAL_DATA", "false").lower() == "true"
        
        # Initialize S3 client (only if not using local data)
        self.s3_client = None
        if not self.use_local and self.bucket:
            try:
                # Try to use AWS SSO profile if configured
                profile = os.getenv("AWS_PROFILE")
                session = boto3.Session(profile_name=profile) if profile else boto3.Session()
                
                # NOTE: boto3 automatically uses AWS_CA_BUNDLE environment variable
                # for SSL certificate verification. No code changes needed.
                self.s3_client = session.client('s3')
                logger.info(f"✅ DeviceLoader initialized with S3 bucket: {self.bucket}")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                logger.warning("Falling back to local data")
                self.use_local = True
        
        # In-memory cache: {device_id: (data, timestamp)}
        self._cache: Dict[str, tuple] = {}
        
        logger.info(f"DeviceLoader configured: use_local={self.use_local}, bucket={self.bucket}")
    
    def _is_cache_valid(self, device_id: str) -> bool:
        """Check if cached data is still valid."""
        if device_id not in self._cache:
            return False
        
        cached_data, cached_time = self._cache[device_id]
        elapsed = (datetime.now() - cached_time).total_seconds()
        return elapsed < self.cache_ttl
    
    def _get_from_cache(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve data from cache if valid."""
        if self._is_cache_valid(device_id):
            logger.debug(f"Cache hit for {device_id}")
            return self._cache[device_id][0]
        return None
    
    def _set_cache(self, device_id: str, data: List[Dict[str, Any]]):
        """Store data in cache with timestamp."""
        self._cache[device_id] = (data, datetime.now())
        logger.debug(f"Cached {device_id} (TTL: {self.cache_ttl}s)")
    
    def _load_from_s3(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load device data from S3 with retry logic."""
        if not self.s3_client or not self.bucket:
            return None
        
        s3_key = f"{self.prefix}{device_id}.json"
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Loading from S3: s3://{self.bucket}/{s3_key}")
                response = self.s3_client.get_object(Bucket=self.bucket, Key=s3_key)
                data = json.loads(response['Body'].read().decode('utf-8'))
                self._set_cache(device_id, data)
                return data
            
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NoSuchKey':
                    logger.warning(f"Device not found in S3: {device_id}")
                    return None
                elif error_code == 'NoSuchBucket':
                    logger.error(f"S3 bucket not found: {self.bucket}")
                    return None
                elif error_code in ['ServiceUnavailable', 'SlowDown']:
                    if attempt < self.max_retries - 1:
                        logger.warning(f"S3 error (attempt {attempt + 1}/{self.max_retries}): {error_code}")
                        continue
                    else:
                        logger.error(f"S3 failed after {self.max_retries} retries")
                        return None
                else:
                    logger.error(f"S3 error: {e}")
                    return None
            
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in S3 file {device_id}: {e}")
                return None
            
            except Exception as e:
                logger.error(f"Unexpected error loading from S3: {e}")
                return None
        
        return None
    
    def _load_from_local(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load device data from local files (dev/testing)."""
        file_path = self.data_dir / f"{device_id}.json"
        if not file_path.exists():
            logger.warning(f"Local file not found: {file_path}")
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            self._set_cache(device_id, data)
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            return None
    
    def list_available_devices(self) -> List[str]:
        """List all available devices (without .json extension)."""
        if self.use_local:
            # Local mode: list from filesystem
            json_files = self.data_dir.glob("*.json")
            return sorted([f.stem for f in json_files])
        else:
            # S3 mode: list from S3
            if not self.s3_client or not self.bucket:
                logger.error("S3 client not configured for list_available_devices")
                return []
            
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=self.prefix
                )
                
                if 'Contents' not in response:
                    return []
                
                devices = [
                    obj['Key'].replace(self.prefix, '').replace('.json', '')
                    for obj in response['Contents']
                    if obj['Key'].endswith('.json')
                ]
                return sorted(devices)
            
            except ClientError as e:
                logger.error(f"Failed to list devices from S3: {e}")
                return []
    
    def load_device_history(self, device_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load complete history for a device.
        
        First checks cache, then loads from S3 or local files.
        """
        # Try cache first
        cached = self._get_from_cache(device_id)
        if cached:
            return cached
        
        # Try S3 or local based on configuration
        if self.use_local:
            return self._load_from_local(device_id)
        else:
            return self._load_from_s3(device_id)
    
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
