# Dashboard API - MCP Tool Integration Guide

## Overview

The dashboard API has been updated to properly integrate with the multi-agent system and MCP tools, replacing mock data with real data from:
- **HealthAgent**: Device health classification (healthy/warning/critical)
- **DiagnosisAgent**: Root cause analysis + MCP tool invocations
- **MCP Tools**: Schedule maintenance, create work orders, get spare parts

## What Changed

### 1. **MCP Tool Result Extractors** (Lines 168-333)

Added three helper functions to safely extract data from DiagnosisAgent's `tool_results` dictionary:

#### `extract_maintenance_schedules(tool_results: Dict)`
- Extracts data from `tool_results['schedule-maintenance']`
- Returns list of maintenance schedules with: maintenance_id, device_id, start_date, duration_hours, priority, parts_needed, estimated_cost, reason

#### `extract_work_orders(tool_results: Dict)`
- Extracts data from `tool_results['create-work-order']`
- Returns list of work orders with: work_order_id, device_id, work_type, urgency, assigned_to, estimated_hours, description, created_at

#### `extract_spare_parts(tool_results: Dict)`
- Extracts data from `tool_results['get-spare-parts']`
- Deduplicates parts by part_id (handles multiple devices requesting same part)
- Returns list of spare parts with: part_id, part_name, equipment_type, availability, quantity_available, lead_time_days, unit_cost, criticality

### 2. **Updated Fleet Summary Endpoint** (`/api/dashboard/fleet-summary`)

**Before**: Returned mock data (3/8/6 device distribution)

**After**: Returns real aggregated data:
- Device health metrics (healthy/warning/critical counts) - from real device data
- Work orders count and breakdown - from MCP tool results
- Maintenance schedules count and breakdown - from MCP tool results
- Spare parts availability - from MCP tool results
- Problematic devices list with recommendations

```json
{
  "total_devices": 17,
  "healthy_devices": 8,
  "warning_devices": 6,
  "critical_devices": 3,
  "fleet_health_percent": 47,
  "degradation_trend": "stable",
  "_mcp_data": {
    "work_orders": 4,
    "maintenance_schedules": 3,
    "spare_parts_available": 12,
    "urgent_work_orders": 2
  },
  "_analytics": { ... },
  "_problematic_devices": [ ... ]
}
```

### 3. **Three New Endpoints - Real MCP Data**

#### **GET `/api/dashboard/maintenance-schedule`**
- Fetches all maintenance schedules from DiagnosisAgent's MCP tool
- Sequential fetching (one device at a time)
- Returns organized by priority (urgent first)
- Includes statistics: total, by_priority, total_estimated_cost

**Response Example**:
```json
{
  "schedules": [
    {
      "maintenance_id": "maint-001",
      "device_id": "pump-001",
      "start_date": "2026-06-25T10:00:00",
      "duration_hours": 4,
      "priority": "urgent",
      "parts_needed": ["seal-kit-001", "bearing-020"],
      "estimated_cost": 250.00,
      "reason": "Bearing degradation detected",
      "status": "scheduled"
    }
  ],
  "total": 5,
  "by_priority": {
    "urgent": 2,
    "scheduled": 3
  },
  "total_estimated_cost": 1250.00,
  "timestamp": "2026-06-24T12:00:00"
}
```

#### **GET `/api/dashboard/work-orders`** (Optional: `?status=open|in_progress|completed`)
- Fetches all work orders from DiagnosisAgent's MCP tool
- Sequential fetching (one device at a time)
- Returns organized by urgency (immediate → urgent → scheduled)
- Includes statistics: total, by_urgency, total_estimated_hours

**Response Example**:
```json
{
  "work_orders": [
    {
      "work_order_id": "wo-001",
      "device_id": "motor-005",
      "work_type": "Preventive Maintenance",
      "urgency": "immediate",
      "assigned_to": "John Smith",
      "estimated_hours": 2,
      "description": "Replace worn bearings",
      "created_at": "2026-06-24T11:30:00",
      "status": "open"
    }
  ],
  "total": 4,
  "by_urgency": {
    "immediate": 1,
    "urgent": 2,
    "scheduled": 1
  },
  "total_estimated_hours": 8,
  "timestamp": "2026-06-24T12:00:00"
}
```

#### **GET `/api/dashboard/spare-parts`** (Optional: `?availability=in_stock|on_order|out_of_stock`)
- Fetches all spare parts from DiagnosisAgent's MCP tool
- Deduplicates parts by part_id across all devices
- Sequential fetching (one device at a time)
- Returns organized by criticality and availability
- Highlights critical parts unavailable

**Response Example**:
```json
{
  "parts": [
    {
      "part_id": "pump-seal-001",
      "part_name": "Hydraulic Seal Kit",
      "equipment_type": "PUMP",
      "availability": "in_stock",
      "quantity_available": 5,
      "lead_time_days": 0,
      "unit_cost": 150.00,
      "criticality": "critical"
    }
  ],
  "total": 12,
  "by_availability": {
    "in_stock": 8,
    "on_order": 2,
    "out_of_stock": 2
  },
  "critical_parts_unavailable": 1,
  "total_value_in_stock": 3500.00,
  "timestamp": "2026-06-24T12:00:00"
}
```

## Data Flow Architecture

```
Dashboard UI
    ↓
Dashboard API (port 8080)
    ├─ /api/dashboard/fleet-summary
    ├─ /api/dashboard/maintenance-schedule
    ├─ /api/dashboard/work-orders
    └─ /api/dashboard/spare-parts
        ↓
    Orchestrator API (port 8000)
        ├─ GET /devices          (list device IDs)
        └─ GET /devices/{id}     (get device analysis + MCP tool results)
            ↓
        HealthAgent (classify device health)
        ↓
        DiagnosisAgent (diagnose + invoke MCP tools)
            ├─ MCP: schedule-maintenance
            ├─ MCP: create-work-order
            └─ MCP: get-spare-parts
```

## Sequential Fetching (Important!)

All new endpoints fetch devices sequentially (one device at a time) to **prevent overwhelming the DiagnosisAgent**:

```python
for device_id in device_ids:
    device_data = await orchestrator.get(f"/devices/{device_id}")
    # Process tool_results
```

This ensures:
- DiagnosisAgent receives time to process each device
- MCP tools are invoked with proper sequencing
- No concurrent request overload

## Backward Compatibility

- Old endpoint `/api/dashboard/maintenance/schedule` still works (marked as DEPRECATED)
- New endpoints use cleaner naming: `/api/dashboard/maintenance-schedule` (no double slash)
- All existing endpoints continue to work

## Features

✅ Real data from HealthAgent + DiagnosisAgent  
✅ MCP tool results properly extracted and aggregated  
✅ Sequential fetching to prevent agent overload  
✅ Deduplication (spare parts by part_id)  
✅ Filtering by status/availability/priority  
✅ Comprehensive statistics and breakdowns  
✅ Caching for performance (6-minute TTL)  
✅ Hard refresh support (bypass cache)  
✅ Detailed logging for debugging  

## Testing

See **DASHBOARD_MCP_INTEGRATION_TEST.md** for comprehensive test suite.

Quick start:
```bash
# Terminal 1: Start orchestrator
cd /home/skroy/AGENTIC_AI_POC_Phase3_1
python3 -m uvicorn src.services.orchestrator.app:app --host 0.0.0.0 --port 8000

# Terminal 2: Start dashboard
cd /home/skroy/AGENTIC_AI_POC_Phase3_1
python3 -m uvicorn src.dashboard.app:app --host 0.0.0.0 --port 8080

# Terminal 3: Run tests
python3 test_dashboard_mcp_integration.py
```

## Files Modified

- `/src/dashboard/routes/api.py`
  - Added: `extract_maintenance_schedules()` helper
  - Added: `extract_work_orders()` helper
  - Added: `extract_spare_parts()` helper
  - Updated: `/api/dashboard/fleet-summary` endpoint (now aggregates real MCP data)
  - Updated: `/api/cache-clear` endpoint (now includes MCP data)
  - Added: `/api/dashboard/maintenance-schedule` endpoint
  - Added: `/api/dashboard/work-orders` endpoint
  - Added: `/api/dashboard/spare-parts` endpoint

## Key Design Decisions

1. **Sequential Fetching**: Prevents overwhelming DiagnosisAgent (chose sequential over parallel)
2. **Deduplication**: Spare parts deduplicated by part_id (keep first occurrence)
3. **Caching**: 6-minute TTL for fleet summary (balances freshness with performance)
4. **Safe Extraction**: Tool result extractors handle missing/malformed data gracefully
5. **Statistics**: All endpoints include aggregated statistics (counts, totals, breakdowns)
