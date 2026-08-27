#!/usr/bin/env python3
"""
Seed AgentCore Memory with synthetic historical data.

Populates the memory with realistic degradation scores, diagnosis history,
and maintenance actions for all 17 devices — simulating several weeks of
operation so the Fleet Health History chart and device memory indicators
display meaningful data immediately.

Usage:
    python scripts/seed_memory_data.py [--region REGION] [--memory-id MEMORY_ID]
"""

import json
import logging
import sys
import os
import random
import argparse
from pathlib import Path
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

# Load env
env_file = Path(__file__).parent.parent / ".agentcore.env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)-8s %(message)s")
logger = logging.getLogger("SEED_MEMORY")

# --- Device fleet definition (matches data/generated/) ---

DEVICES = [
    # Pumps
    {"device_id": "pump-001", "equipment_type": "PUMP", "profile": "healthy"},
    {"device_id": "pump-002", "equipment_type": "PUMP", "profile": "degrading"},
    {"device_id": "pump-003", "equipment_type": "PUMP", "profile": "critical"},
    {"device_id": "pump-004", "equipment_type": "PUMP", "profile": "intermittent"},
    {"device_id": "pump-005", "equipment_type": "PUMP", "profile": "degrading"},
    # Motors
    {"device_id": "motor-001", "equipment_type": "MOTOR", "profile": "healthy"},
    {"device_id": "motor-002", "equipment_type": "MOTOR", "profile": "degrading"},
    {"device_id": "motor-003", "equipment_type": "MOTOR", "profile": "critical"},
    {"device_id": "motor-004", "equipment_type": "MOTOR", "profile": "intermittent"},
    {"device_id": "motor-005", "equipment_type": "MOTOR", "profile": "healthy"},
    # Compressors
    {"device_id": "compressor-001", "equipment_type": "COMPRESSOR", "profile": "healthy"},
    {"device_id": "compressor-002", "equipment_type": "COMPRESSOR", "profile": "degrading"},
    {"device_id": "compressor-003", "equipment_type": "COMPRESSOR", "profile": "intermittent"},
    {"device_id": "compressor-004", "equipment_type": "COMPRESSOR", "profile": "critical"},
    # Generators
    {"device_id": "generator-001", "equipment_type": "GENERATOR", "profile": "healthy"},
    {"device_id": "generator-002", "equipment_type": "GENERATOR", "profile": "degrading"},
    {"device_id": "generator-003", "equipment_type": "GENERATOR", "profile": "critical"},
]

# --- Score generation profiles ---

def generate_scores(profile: str, num_points: int = 20) -> list:
    """Generate a sequence of degradation scores matching the device profile."""
    scores = []

    if profile == "healthy":
        # Low, stable scores (0.02 - 0.12)
        base = random.uniform(0.03, 0.08)
        for i in range(num_points):
            noise = random.uniform(-0.02, 0.02)
            scores.append(max(0.01, min(0.14, base + noise)))

    elif profile == "degrading":
        # Steadily increasing (0.10 → 0.45) — triggers trend detection
        start = random.uniform(0.10, 0.15)
        step = random.uniform(0.015, 0.025)
        for i in range(num_points):
            noise = random.uniform(-0.005, 0.01)
            scores.append(min(0.50, start + step * i + noise))

    elif profile == "critical":
        # High scores with slight increases (0.70 → 0.95)
        start = random.uniform(0.70, 0.80)
        step = random.uniform(0.005, 0.015)
        for i in range(num_points):
            noise = random.uniform(-0.01, 0.02)
            scores.append(min(0.99, start + step * i + noise))

    elif profile == "intermittent":
        # Fluctuating — some spikes, some drops
        base = random.uniform(0.20, 0.30)
        for i in range(num_points):
            if random.random() < 0.3:
                # Spike
                scores.append(min(0.60, base + random.uniform(0.10, 0.25)))
            else:
                scores.append(max(0.05, base + random.uniform(-0.08, 0.08)))

    return scores


def score_to_status(score: float) -> str:
    """Convert degradation score to health status."""
    if score < 0.15:
        return "healthy"
    elif score <= 0.50:
        return "warning"
    else:
        return "critical"


# --- Main seeding logic ---

def seed_memory(memory_id: str, region: str) -> None:
    """Write synthetic data into AgentCore Memory."""
    session = boto3.Session(region_name=region)
    client = session.client("bedrock-agentcore", region_name=region)

    now = datetime.utcnow()
    num_points = 20  # 20 data points per device (simulating ~20 days)
    total_events = 0
    failed_events = 0

    logger.info(f"🌱 Seeding memory: {memory_id}")
    logger.info(f"   Devices: {len(DEVICES)}")
    logger.info(f"   Points per device: {num_points}")
    logger.info(f"   Total events to write: ~{len(DEVICES) * num_points}")

    for device in DEVICES:
        device_id = device["device_id"]
        equipment_type = device["equipment_type"]
        profile = device["profile"]

        scores = generate_scores(profile, num_points)
        logger.info(f"   📊 {device_id} ({profile}): scores {scores[0]:.2f} → {scores[-1]:.2f}")

        for i, score in enumerate(scores):
            # Timestamp: spread over the last 20 days
            ts = now - timedelta(days=num_points - i, hours=random.randint(0, 12))
            timestamp_iso = ts.isoformat() + "Z"
            health_status = score_to_status(score)

            # Build content matching what HealthAgent writes
            content_payload = {
                "device_id": device_id,
                "equipment_type": equipment_type,
                "degradation_score": round(score, 4),
                "health_status": health_status,
                "anomaly_count": max(0, int((score - 0.15) * 10)) if score > 0.15 else 0,
                "anomalies": [],
                "timestamp": timestamp_iso,
            }

            # Add anomalies for non-healthy
            if health_status != "healthy":
                anomaly_options = {
                    "PUMP": ["high_vibration", "low_flow", "high_temperature", "seal_leakage"],
                    "MOTOR": ["high_current", "bearing_vibration", "overheating", "voltage_imbalance"],
                    "COMPRESSOR": ["high_discharge_temp", "low_inlet_pressure", "valve_degradation"],
                    "GENERATOR": ["frequency_drift", "voltage_sag", "overheating"],
                }
                options = anomaly_options.get(equipment_type, ["unknown_anomaly"])
                num_anomalies = min(len(options), max(1, int(score * 4)))
                content_payload["anomalies"] = random.sample(options, num_anomalies)
                content_payload["anomaly_count"] = len(content_payload["anomalies"])

            # Write event to memory
            try:
                client.create_event(
                    memoryId=memory_id,
                    actorId=device_id,
                    sessionId=f"seed-{device_id}-{int(ts.timestamp() * 1000)}".ljust(33, "0"),
                    eventTimestamp=ts,
                    payload=[
                        {
                            "conversational": {
                                "content": {"text": json.dumps(content_payload)},
                                "role": "ASSISTANT",
                            }
                        }
                    ],
                    metadata={
                        "namespace": {"stringValue": f"device-facts/{device_id}/"},
                        "device_id": {"stringValue": device_id},
                        "equipment_type": {"stringValue": equipment_type},
                        "fact_type": {"stringValue": "degradation"},
                    },
                )
                total_events += 1
            except ClientError as e:
                failed_events += 1
                if failed_events <= 3:
                    logger.warning(f"   ⚠️  Failed to write event: {e}")
                elif failed_events == 4:
                    logger.warning("   ... suppressing further warnings")

        # Also write a diagnosis entry for non-healthy devices
        if profile != "healthy":
            diagnosis_payload = {
                "device_id": device_id,
                "equipment_type": equipment_type,
                "anomalies_detected": content_payload.get("anomalies", []),
                "diagnosis_result": f"{profile}_wear_pattern",
                "confidence_score": round(random.uniform(0.75, 0.95), 2),
                "action_taken": "SCHEDULE_MAINTENANCE" if profile == "degrading" else "URGENT_REPAIR",
                "severity": "medium" if profile in ("degrading", "intermittent") else "critical",
                "llm_used": random.choice([True, False]),
                "timestamp": (now - timedelta(days=1)).isoformat() + "Z",
            }

            try:
                client.create_event(
                    memoryId=memory_id,
                    actorId=device_id,
                    sessionId=f"seed-diag-{device_id}-{int(now.timestamp())}".ljust(33, "0"),
                    eventTimestamp=now - timedelta(days=1),
                    payload=[
                        {
                            "conversational": {
                                "content": {"text": json.dumps(diagnosis_payload)},
                                "role": "ASSISTANT",
                            }
                        }
                    ],
                    metadata={
                        "namespace": {"stringValue": f"diagnosis-history/{device_id}/"},
                        "device_id": {"stringValue": device_id},
                        "equipment_type": {"stringValue": equipment_type},
                    },
                )
                total_events += 1
            except ClientError as e:
                failed_events += 1

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ SEEDING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"   Total events written: {total_events}")
    logger.info(f"   Failed: {failed_events}")
    logger.info(f"   Devices seeded: {len(DEVICES)}")
    logger.info(f"   Points per device: {num_points}")
    logger.info(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Seed AgentCore Memory with synthetic data")
    parser.add_argument("--region", default="eu-central-1", help="AWS region")
    parser.add_argument(
        "--memory-id",
        default=os.getenv("AGENTCORE_MEMORY_ID", "agentic_eco_sentinel_memory-b9oakkF6FK"),
        help="AgentCore Memory ID",
    )
    args = parser.parse_args()

    logger.info(f"Memory ID: {args.memory_id}")
    logger.info(f"Region: {args.region}")

    seed_memory(args.memory_id, args.region)


if __name__ == "__main__":
    main()
