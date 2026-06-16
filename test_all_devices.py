#!/usr/bin/env python3
"""
Test 3: Batch Processing - Run Workflow on All 16 Devices and Generate Reports
Processes all devices and saves JSON reports
"""

import json
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from src.graph.workflow import AgentWorkflow


def generate_reports_all_devices():
    """Generate and save reports for all 16 devices"""
    
    print("\n" + "="*70)
    print("BATCH TEST: Generate Reports for All 16 Devices")
    print("="*70)
    
    workflow = AgentWorkflow()
    data_dir = Path('data/generated')
    output_dir = Path('output/reports')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_reports = []
    summary = {
        'generated_at': datetime.utcnow().isoformat(),
        'total_devices': 0,
        'devices_by_health': {
            'healthy': [],
            'warning': [],
            'alert': [],
            'critical': []
        },
        'devices_by_equipment_type': {
            'PUMP': [],
            'MOTOR': [],
            'COMPRESSOR': [],
            'GENERATOR': []
        },
        'critical_actions_required': []
    }
    
    print(f"\n► Processing devices...\n")
    
    for json_file in sorted(data_dir.glob('*.json')):
        device_id = json_file.stem
        equipment_type = device_id.split('-')[0].upper()
        
        print(f"  Processing {device_id}...")
        
        with open(json_file) as f:
            readings = json.load(f)
        
        # Use latest reading (day 30)
        latest_reading = readings[-1]
        
        # Run workflow
        report = workflow.run(
            device_id=device_id,
            equipment_type=equipment_type,
            current_reading=latest_reading
        )
        
        all_reports.append(report)
        
        # Categorize in summary
        health_state = report['health']['health_state']
        summary['devices_by_health'][health_state].append(device_id)
        summary['devices_by_equipment_type'][equipment_type].append(device_id)
        
        # Flag critical devices
        if health_state == 'critical':
            summary['critical_actions_required'].append({
                'device_id': device_id,
                'equipment_type': equipment_type,
                'degradation_score': report['health']['degradation_score'],
                'diagnosis': report.get('diagnosis', {}).get('primary_diagnosis', 'N/A'),
                'recommended_actions': report.get('diagnosis', {}).get('recommended_actions', [])
            })
        
        # Save individual report
        report_file = output_dir / f"{device_id}_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"    ✓ Saved: {report_file}")
    
    summary['total_devices'] = len(all_reports)
    
    # Save summary report
    summary_file = output_dir / 'fleet_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n  ✓ Saved summary: {summary_file}")
    
    # Print summary to console
    print(f"\n" + "="*70)
    print("FLEET SUMMARY")
    print("="*70)
    print(f"\nTotal Devices: {summary['total_devices']}")
    print(f"\nHealth Distribution:")
    print(f"  ✓ Healthy:  {len(summary['devices_by_health']['healthy']):2d} - {summary['devices_by_health']['healthy']}")
    print(f"  ⚠ Warning:  {len(summary['devices_by_health']['warning']):2d} - {summary['devices_by_health']['warning']}")
    print(f"  ⚡ Alert:    {len(summary['devices_by_health']['alert']):2d} - {summary['devices_by_health']['alert']}")
    print(f"  🔴 Critical: {len(summary['devices_by_health']['critical']):2d} - {summary['devices_by_health']['critical']}")
    
    print(f"\nEquipment Type Distribution:")
    for eq_type, devices in summary['devices_by_equipment_type'].items():
        print(f"  {eq_type:12} - {len(devices):2d} devices: {devices}")
    
    if summary['critical_actions_required']:
        print(f"\n⚠️  CRITICAL DEVICES REQUIRING IMMEDIATE ACTION:")
        for critical_device in summary['critical_actions_required']:
            print(f"\n  Device: {critical_device['device_id']} ({critical_device['equipment_type']})")
            print(f"  Degradation: {critical_device['degradation_score']:.3f}")
            print(f"  Diagnosis: {critical_device['diagnosis']}")
            print(f"  Actions:")
            for action in critical_device['recommended_actions']:
                print(f"    • {action}")
    
    print(f"\n" + "="*70)
    print(f"✓ All reports saved to: {output_dir.resolve()}")
    print(f"  • Individual reports: {device_id}_report.json (×16)")
    print(f"  • Fleet summary: fleet_summary.json")
    print("="*70 + "\n")
    
    return summary


def print_detailed_report(device_id: str, report: dict):
    """Print detailed report for a single device"""
    
    print(f"\n{'='*70}")
    print(f"DETAILED REPORT: {device_id}")
    print(f"{'='*70}\n")
    
    # Header
    print(f"Device ID: {report['device_id']}")
    print(f"Equipment Type: {report['equipment_type']}")
    print(f"Analysis Timestamp: {report['analysis_timestamp']}")
    
    # Health Section
    print(f"\n[HEALTH ANALYSIS]")
    health = report['health']
    print(f"  State: {health['health_state']}")
    print(f"  Degradation Score: {health['degradation_score']:.3f}")
    print(f"  Trend: {health['trend']}")
    if health.get('anomalies'):
        print(f"  Anomalies:")
        for anomaly in health['anomalies']:
            print(f"    • {anomaly}")
    
    # Diagnosis Section (if performed)
    if report.get('diagnosis'):
        print(f"\n[DIAGNOSIS]")
        diagnosis = report['diagnosis']
        print(f"  Primary Diagnosis: {diagnosis['primary_diagnosis']}")
        print(f"  Confidence: {diagnosis['confidence']:.2f}")
        print(f"  Severity: {diagnosis['severity']}")
        if diagnosis.get('sensor_correlations'):
            print(f"  Sensor Correlations:")
            for correlation in diagnosis['sensor_correlations']:
                print(f"    • {correlation}")
        if diagnosis.get('recommended_actions'):
            print(f"  Recommended Actions:")
            for action in diagnosis['recommended_actions']:
                print(f"    • {action}")
    
    # Overall Recommendation
    print(f"\n[RECOMMENDATION]")
    print(f"  {report['overall_recommendation']}")
    
    print(f"\n{'='*70}\n")


def main():
    """Run batch processing"""
    try:
        summary = generate_reports_all_devices()
        
        # Print detailed report for a critical device
        critical_devices = summary['devices_by_health']['critical']
        if critical_devices:
            report_file = Path('output/reports') / f"{critical_devices[0]}_report.json"
            if report_file.exists():
                with open(report_file) as f:
                    report = json.load(f)
                print_detailed_report(critical_devices[0], report)
        
        print("🎉 "*35)
        print("✓ BATCH PROCESSING COMPLETE")
        print("🎉 "*35 + "\n")
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
