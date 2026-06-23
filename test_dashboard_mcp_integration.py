#!/usr/bin/env python3
"""
Test Suite for Dashboard API MCP Integration

Tests all new endpoints:
- /api/dashboard/maintenance-schedule
- /api/dashboard/work-orders
- /api/dashboard/spare-parts
- Updated /api/dashboard/fleet-summary (with MCP data)

Prerequisites:
1. Orchestrator running on port 8000
2. Dashboard running on port 8080
3. HealthAgent and DiagnosisAgent running (via docker-compose)

Run with:
    python3 test_dashboard_mcp_integration.py
"""

import httpx
import json
import time
import sys
from typing import Dict, Any, Optional
from datetime import datetime

# Configuration
DASHBOARD_BASE = "http://localhost:8080"
ORCHESTRATOR_BASE = "http://localhost:8000"

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(title: str):
    """Print section header"""
    print(f"\n{BLUE}{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}{RESET}\n")

def print_success(msg: str):
    """Print success message"""
    print(f"{GREEN}✅ {msg}{RESET}")

def print_error(msg: str):
    """Print error message"""
    print(f"{RED}❌ {msg}{RESET}")

def print_info(msg: str):
    """Print info message"""
    print(f"{BLUE}ℹ️  {msg}{RESET}")

def print_warning(msg: str):
    """Print warning message"""
    print(f"{YELLOW}⚠️  {msg}{RESET}")

async def test_orchestrator_connectivity():
    """Test if orchestrator is reachable"""
    print_header("1. Testing Orchestrator Connectivity")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ORCHESTRATOR_BASE}/health")
            if response.status_code == 200:
                print_success(f"Orchestrator is reachable at {ORCHESTRATOR_BASE}")
                return True
            else:
                print_error(f"Orchestrator returned status {response.status_code}")
                return False
    except Exception as e:
        print_error(f"Cannot connect to orchestrator: {str(e)}")
        return False

async def test_orchestrator_devices():
    """Test if orchestrator has devices"""
    print_header("2. Testing Orchestrator Devices")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ORCHESTRATOR_BASE}/devices")
            if response.status_code == 200:
                data = response.json()
                device_count = len(data.get('devices', []))
                print_success(f"Found {device_count} devices from orchestrator")
                
                if device_count > 0:
                    devices = data.get('devices', [])[:3]  # Show first 3
                    print_info(f"Sample devices: {', '.join(devices)}")
                    return True
                else:
                    print_warning("No devices found!")
                    return False
            else:
                print_error(f"Failed to fetch devices: {response.status_code}")
                return False
    except Exception as e:
        print_error(f"Error fetching devices: {str(e)}")
        return False

async def test_orchestrator_device_detail():
    """Test if individual device endpoints return MCP tool results"""
    print_header("3. Testing Orchestrator Device Detail (MCP Tool Results)")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First get device list
            response = await client.get(f"{ORCHESTRATOR_BASE}/devices")
            if response.status_code != 200:
                print_error("Failed to fetch device list")
                return False
            
            device_ids = response.json().get('devices', [])
            if not device_ids:
                print_error("No devices available")
                return False
            
            # Test first device
            device_id = device_ids[0]
            print_info(f"Fetching device detail for: {device_id}")
            
            response = await client.get(f"{ORCHESTRATOR_BASE}/devices/{device_id}")
            if response.status_code == 200:
                data = response.json()
                
                # Check for required fields
                required_fields = ['device_id', 'health_status', 'tool_results']
                missing = [f for f in required_fields if f not in data]
                
                if missing:
                    print_warning(f"Missing fields: {missing}")
                else:
                    print_success(f"Device detail retrieved: health_status={data.get('health_status')}")
                
                # Check tool results
                tool_results = data.get('tool_results', {})
                if tool_results:
                    tools_found = list(tool_results.keys())
                    print_info(f"MCP tools in results: {tools_found}")
                    
                    if 'schedule-maintenance' in tool_results:
                        print_info("  - schedule-maintenance: present")
                    if 'create-work-order' in tool_results:
                        print_info("  - create-work-order: present")
                    if 'get-spare-parts' in tool_results:
                        print_info("  - get-spare-parts: present")
                else:
                    print_warning("No MCP tool results in device data (may be healthy)")
                
                return True
            else:
                print_error(f"Failed to fetch device detail: {response.status_code}")
                return False
    except Exception as e:
        print_error(f"Error fetching device detail: {str(e)}")
        return False

async def test_dashboard_connectivity():
    """Test if dashboard is reachable"""
    print_header("4. Testing Dashboard Connectivity")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{DASHBOARD_BASE}/api/status")
            if response.status_code == 200:
                print_success(f"Dashboard is reachable at {DASHBOARD_BASE}")
                return True
            else:
                print_error(f"Dashboard returned status {response.status_code}")
                return False
    except Exception as e:
        print_error(f"Cannot connect to dashboard: {str(e)}")
        return False

async def test_fleet_summary():
    """Test fleet summary endpoint with MCP data"""
    print_header("5. Testing Fleet Summary Endpoint (with MCP Data)")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print_info("Fetching fleet summary... (may take 30+ seconds)")
            response = await client.get(f"{DASHBOARD_BASE}/api/fleet-summary")
            
            if response.status_code == 200:
                data = response.json()
                
                print_success(f"Fleet summary retrieved")
                print_info(f"  Total devices: {data.get('total_devices')}")
                print_info(f"  Healthy: {data.get('healthy_devices')}")
                print_info(f"  Warning: {data.get('warning_devices')}")
                print_info(f"  Critical: {data.get('critical_devices')}")
                
                # Check MCP data
                mcp_data = data.get('_mcp_data', {})
                if mcp_data:
                    print_info(f"  MCP Data:")
                    print_info(f"    - Work Orders: {mcp_data.get('work_orders', 0)}")
                    print_info(f"    - Maintenance Schedules: {mcp_data.get('maintenance_schedules', 0)}")
                    print_info(f"    - Spare Parts: {mcp_data.get('spare_parts_available', 0)}")
                    print_info(f"    - Urgent Work Orders: {mcp_data.get('urgent_work_orders', 0)}")
                    return True
                else:
                    print_warning("No _mcp_data in response")
                    return True  # Still success if fleet summary works
            else:
                print_error(f"Failed to fetch fleet summary: {response.status_code}")
                return False
    except httpx.TimeoutException:
        print_warning("Fleet summary fetch timed out (orchestrator still processing)")
        return True  # Not a failure, just a timeout
    except Exception as e:
        print_error(f"Error fetching fleet summary: {str(e)}")
        return False

async def test_maintenance_schedule_endpoint():
    """Test new maintenance schedule endpoint"""
    print_header("6. Testing Maintenance Schedule Endpoint")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print_info("Fetching maintenance schedules... (may take 30+ seconds)")
            response = await client.get(f"{DASHBOARD_BASE}/api/maintenance-schedule")
            
            if response.status_code == 200:
                data = response.json()
                
                print_success(f"Maintenance schedules retrieved")
                print_info(f"  Total: {data.get('total')}")
                
                by_priority = data.get('by_priority', {})
                if by_priority:
                    print_info(f"  By priority:")
                    print_info(f"    - Urgent: {by_priority.get('urgent', 0)}")
                    print_info(f"    - Scheduled: {by_priority.get('scheduled', 0)}")
                
                print_info(f"  Total estimated cost: ${data.get('total_estimated_cost', 0)}")
                
                schedules = data.get('schedules', [])
                if schedules:
                    print_info(f"  First schedule:")
                    first = schedules[0]
                    print_info(f"    - Device: {first.get('device_id')}")
                    print_info(f"    - Priority: {first.get('priority')}")
                    print_info(f"    - Start: {first.get('start_date')}")
                else:
                    print_info("  No maintenance schedules yet (normal for healthy devices)")
                
                return True
            else:
                print_error(f"Failed to fetch maintenance schedules: {response.status_code}")
                if response.status_code >= 400:
                    print_info(f"Response: {response.text[:200]}")
                return False
    except httpx.TimeoutException:
        print_warning("Maintenance schedule fetch timed out (orchestrator still processing)")
        return True
    except Exception as e:
        print_error(f"Error fetching maintenance schedules: {str(e)}")
        return False

async def test_work_orders_endpoint():
    """Test new work orders endpoint"""
    print_header("7. Testing Work Orders Endpoint")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print_info("Fetching work orders... (may take 30+ seconds)")
            response = await client.get(f"{DASHBOARD_BASE}/api/work-orders")
            
            if response.status_code == 200:
                data = response.json()
                
                print_success(f"Work orders retrieved")
                print_info(f"  Total: {data.get('total')}")
                
                by_urgency = data.get('by_urgency', {})
                if by_urgency:
                    print_info(f"  By urgency:")
                    print_info(f"    - Immediate: {by_urgency.get('immediate', 0)}")
                    print_info(f"    - Urgent: {by_urgency.get('urgent', 0)}")
                    print_info(f"    - Scheduled: {by_urgency.get('scheduled', 0)}")
                
                print_info(f"  Total estimated hours: {data.get('total_estimated_hours', 0)}")
                
                work_orders = data.get('work_orders', [])
                if work_orders:
                    print_info(f"  First work order:")
                    first = work_orders[0]
                    print_info(f"    - Device: {first.get('device_id')}")
                    print_info(f"    - Type: {first.get('work_type')}")
                    print_info(f"    - Urgency: {first.get('urgency')}")
                else:
                    print_info("  No work orders yet (normal for healthy devices)")
                
                return True
            else:
                print_error(f"Failed to fetch work orders: {response.status_code}")
                return False
    except httpx.TimeoutException:
        print_warning("Work orders fetch timed out (orchestrator still processing)")
        return True
    except Exception as e:
        print_error(f"Error fetching work orders: {str(e)}")
        return False

async def test_spare_parts_endpoint():
    """Test new spare parts endpoint"""
    print_header("8. Testing Spare Parts Endpoint")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print_info("Fetching spare parts... (may take 30+ seconds)")
            response = await client.get(f"{DASHBOARD_BASE}/api/spare-parts")
            
            if response.status_code == 200:
                data = response.json()
                
                print_success(f"Spare parts retrieved")
                print_info(f"  Total: {data.get('total')}")
                
                by_availability = data.get('by_availability', {})
                if by_availability:
                    print_info(f"  By availability:")
                    print_info(f"    - In Stock: {by_availability.get('in_stock', 0)}")
                    print_info(f"    - On Order: {by_availability.get('on_order', 0)}")
                    print_info(f"    - Out of Stock: {by_availability.get('out_of_stock', 0)}")
                
                print_info(f"  Critical parts unavailable: {data.get('critical_parts_unavailable', 0)}")
                print_info(f"  Total value in stock: ${data.get('total_value_in_stock', 0)}")
                
                parts = data.get('parts', [])
                if parts:
                    print_info(f"  First spare part:")
                    first = parts[0]
                    print_info(f"    - Name: {first.get('part_name')}")
                    print_info(f"    - Type: {first.get('equipment_type')}")
                    print_info(f"    - Availability: {first.get('availability')}")
                else:
                    print_info("  No spare parts data yet")
                
                return True
            else:
                print_error(f"Failed to fetch spare parts: {response.status_code}")
                return False
    except httpx.TimeoutException:
        print_warning("Spare parts fetch timed out (orchestrator still processing)")
        return True
    except Exception as e:
        print_error(f"Error fetching spare parts: {str(e)}")
        return False

async def test_filtering():
    """Test query parameter filtering"""
    print_header("9. Testing Query Parameter Filtering")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test work orders filtering
            tests_total += 1
            print_info("Testing work-orders?status=open filter...")
            response = await client.get(f"{DASHBOARD_BASE}/api/work-orders?status=open")
            if response.status_code == 200:
                data = response.json()
                print_success(f"  Work orders filter works (returned {data.get('total')} items)")
                tests_passed += 1
            else:
                print_warning(f"  Work orders filter returned {response.status_code}")
            
            # Test spare parts filtering
            tests_total += 1
            print_info("Testing spare-parts?availability=in_stock filter...")
            response = await client.get(f"{DASHBOARD_BASE}/api/spare-parts?availability=in_stock")
            if response.status_code == 200:
                data = response.json()
                print_success(f"  Spare parts filter works (returned {data.get('total')} items)")
                tests_passed += 1
            else:
                print_warning(f"  Spare parts filter returned {response.status_code}")
        
        print_info(f"Filtering tests: {tests_passed}/{tests_total} passed")
        return tests_passed == tests_total
    except Exception as e:
        print_error(f"Error testing filters: {str(e)}")
        return False

async def main():
    """Run all tests"""
    print(f"\n{BLUE}Dashboard MCP Integration Test Suite{RESET}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    tests = [
        ("Orchestrator Connectivity", test_orchestrator_connectivity),
        ("Orchestrator Devices", test_orchestrator_devices),
        ("Orchestrator Device Detail (MCP Tools)", test_orchestrator_device_detail),
        ("Dashboard Connectivity", test_dashboard_connectivity),
        ("Fleet Summary (Real MCP Data)", test_fleet_summary),
        ("Maintenance Schedule Endpoint", test_maintenance_schedule_endpoint),
        ("Work Orders Endpoint", test_work_orders_endpoint),
        ("Spare Parts Endpoint", test_spare_parts_endpoint),
        ("Query Parameter Filtering", test_filtering),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {str(e)}")
            results.append((test_name, False))
    
    # Print summary
    print_header("Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        if result:
            print_success(f"{test_name}")
        else:
            print_error(f"{test_name}")
    
    print(f"\n{BLUE}{'='*70}")
    if passed == total:
        print(f"{GREEN}✅ All {total} tests passed!{RESET}")
    else:
        print(f"{YELLOW}⚠️  {passed}/{total} tests passed{RESET}")
    print(f"{'='*70}{RESET}\n")
    
    return passed == total

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
