#!/usr/bin/env python3
"""
Inventory Data Generator - Phase 1 Week 2
Generates spare parts inventory knowledge base for agent tools.

This is separate from equipment simulator to distinguish between:
- Equipment Simulator: Replicates real sensor data (physics-based)
- Inventory Generator: Creates reference/knowledge base data (configuration-based)

Features:
- Spare parts catalog mapped by issue type
- Equipment type associations
- Availability, lead times, and costs
- Ready for Lambda function `get_spare_parts` tool
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class InventoryDataGenerator:
    """Generates spare parts inventory reference data"""

    # Spare parts inventory mapped by issue type
    # This is a knowledge base that agents will query
    SPARE_PARTS_CATALOG = {
        "motor_bearing_failure": {
            "available": True,
            "part_name": "Motor Bearing Assembly",
            "part_id": "MB-001",
            "quantity_in_stock": 5,
            "lead_time_days": 2,
            "cost": 450,
            "equipment_types": ["MOTOR"],
            "description": "Standard ball bearing assembly for industrial motors"
        },
        "pump_seal_failure": {
            "available": True,
            "part_name": "Pump Seal Kit",
            "part_id": "PS-002",
            "quantity_in_stock": 12,
            "lead_time_days": 1,
            "cost": 120,
            "equipment_types": ["PUMP"],
            "description": "Mechanical seal replacement for centrifugal pumps"
        },
        "compressor_valve_failure": {
            "available": True,
            "part_name": "Discharge Valve Assembly",
            "part_id": "CV-003",
            "quantity_in_stock": 8,
            "lead_time_days": 3,
            "cost": 680,
            "equipment_types": ["COMPRESSOR"],
            "description": "High-pressure discharge valve for rotary compressors"
        },
        "component_degradation": {
            "available": False,
            "part_name": "Custom Component Assembly",
            "part_id": "CC-004",
            "quantity_in_stock": 0,
            "lead_time_days": 14,
            "cost": 850,
            "equipment_types": ["MOTOR", "PUMP", "COMPRESSOR"],
            "description": "OEM-specific custom component",
            "backorder_note": "On order from OEM supplier, expected 2026-06-10"
        },
        "electrical_failure": {
            "available": True,
            "part_name": "Motor Stator Coil Assembly",
            "part_id": "SC-005",
            "quantity_in_stock": 3,
            "lead_time_days": 5,
            "cost": 1200,
            "equipment_types": ["MOTOR", "GENERATOR"],
            "description": "3-phase stator winding replacement"
        },
        "cooling_system_failure": {
            "available": True,
            "part_name": "Cooling Fan Motor Assembly",
            "part_id": "CF-006",
            "quantity_in_stock": 7,
            "lead_time_days": 2,
            "cost": 380,
            "equipment_types": ["COMPRESSOR", "GENERATOR"],
            "description": "AC motor-driven cooling fan unit"
        },
        "generator_voltage_regulator_failure": {
            "available": True,
            "part_name": "Automatic Voltage Regulator (AVR)",
            "part_id": "AVR-007",
            "quantity_in_stock": 4,
            "lead_time_days": 4,
            "cost": 520,
            "equipment_types": ["GENERATOR"],
            "description": "Electronic AVR module for alternators"
        },
        "pump_cavitation": {
            "available": True,
            "part_name": "Pump Impeller Assembly",
            "part_id": "PI-008",
            "quantity_in_stock": 6,
            "lead_time_days": 3,
            "cost": 420,
            "equipment_types": ["PUMP"],
            "description": "Replacement impeller for centrifugal pump"
        }
    }

    @staticmethod
    def generate_inventory(output_dir: str = "data/generated") -> None:
        """
        Generate spare parts inventory file

        Args:
            output_dir: Output directory for JSON file (default: data/generated)
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info("=" * 70)
        logger.info("🔧 INVENTORY DATA GENERATOR - Spare Parts Knowledge Base")
        logger.info("=" * 70)
        logger.info(
            f"Generating {len(InventoryDataGenerator.SPARE_PARTS_CATALOG)} part types...\n"
        )

        # Save inventory to JSON
        inventory_file = output_path / "spare_parts_inventory.json"
        with open(inventory_file, "w") as f:
            json.dump(
                InventoryDataGenerator.SPARE_PARTS_CATALOG, f, indent=2
            )

        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ INVENTORY GENERATION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Part types: {len(InventoryDataGenerator.SPARE_PARTS_CATALOG)}")
        logger.info(f"Output file: {inventory_file.resolve()}")
        logger.info("")

        # Print summary
        available_count = sum(
            1
            for part in InventoryDataGenerator.SPARE_PARTS_CATALOG.values()
            if part.get("available")
        )
        backorder_count = (
            len(InventoryDataGenerator.SPARE_PARTS_CATALOG) - available_count
        )

        logger.info("Summary:")
        logger.info(f"  - Parts in stock: {available_count}")
        logger.info(f"  - Parts on backorder: {backorder_count}")
        logger.info("")


def main():
    """Command-line interface"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate spare parts inventory knowledge base"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/generated",
        help="Output directory for JSON file (default: data/generated)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run generator
    InventoryDataGenerator.generate_inventory(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
