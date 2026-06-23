# MCP Data Extraction Function Fix - Complete Summary

## Problem Statement
Dashboard maintenance section was displaying **0 work orders, 0 schedules, 0 spare parts** despite real data existing in the system on warning/critical devices.

## Root Cause Analysis

### Discovery Process
1. User reported zero data in maintenance tabs
2. Verified orchestrator had real device data with MCP tool_results
3. Confirmed devices like pump-003 had real MCP data with schedule-maintenance and get-spare-parts
4. Tested extraction functions and found they returned empty lists
5. Investigated MCP tool response formats

### Format Mismatch Issue

**Expected Format by Extractors (Initially):**
```json
{
  "success": true,
  "data": {...}
}
```

**Actual Format from MCP Tools:**
```json
{
  "statusCode": 200,
  "body": "{\"maintenance_id\": \"...\", \"device_id\": \"...\", ...}"
}
```

The MCP tools return **Lambda function** format with:
- `statusCode`: HTTP status code (200)
- `body`: Actual response data as **JSON string** (not parsed object)

## Solution Implementation

### Updated Files
- **File**: `/home/skroy/AGENTIC_AI_POC_Phase3_1/src/dashboard/routes/api.py`
- **Functions Modified**:
  1. `extract_maintenance_schedules()` (Lines 168-271)
  2. `extract_spare_parts()` (Lines 273-360)

### Fix Details

#### 1. Parse Lambda Format Helper
Both extraction functions now include a `parse_mcp_response()` helper:

```python
def parse_mcp_response(data):
    """Parse different MCP response formats"""
    if isinstance(data, dict):
        # Check Lambda format: {"statusCode": 200, "body": "{...}"}
        if 'statusCode' in data and 'body' in data:
            try:
                body_str = data.get('body', '{}')
                if isinstance(body_str, str):
                    body = json.loads(body_str)
                else:
                    body = body_str
                return body
            except (json.JSONDecodeError, ValueError):
                return data
        return data
    return None
```

#### 2. Format Support
Each function now handles multiple formats:
1. **Lambda format**: `{"statusCode": 200, "body": "{...}"}`
2. **Wrapped format**: `{"success": true, "data": {...}}`
3. **Flat format**: Direct fields like `{"maintenance_id": "...", "device_id": "..."}`
4. **List format**: `{"schedules": [...]}` or `{"parts": [...]}`

### extract_maintenance_schedules() Logic

1. Parse Lambda format if present
2. Check for wrapped format with 'success' and 'data'
3. Check for nested list format with 'maintenance' key
4. Handle single maintenance object
5. Provides defaults for missing fields

### extract_spare_parts() Logic

1. Parse Lambda format if present
2. Check for wrapped format with 'success' and 'data'
3. Check for nested list format with 'parts' key
4. Handle single part object
5. Provides defaults for missing fields

### extract_work_orders() Status
- Already handles flat format correctly
- No changes needed
- Works with both direct fields and list formats

## Testing Results

### Pre-Fix State
```
GET /api/maintenance-schedule → {"schedules": [], "total": 0, ...}
GET /api/work-orders → Previously tested, returned data
GET /api/spare-parts → {"parts": [], "total": 0, ...}
```

### Post-Fix State (Verified)

#### 1. Work Orders Endpoint ✅
```bash
curl http://localhost:8080/api/work-orders
```
**Response**: 6+ work orders with real data
```json
{
  "work_orders": [
    {
      "work_order_id": "WO-dee725cd",
      "status": "created",
      "created_at": "2026-06-23T21:55:57.309617"
    },
    ...
  ]
}
```

#### 2. Maintenance Schedules Endpoint ✅
```bash
curl http://localhost:8080/api/maintenance-schedule
```
**Response**: 2 maintenance schedules with real data
```json
{
  "schedules": [
    {
      "maintenance_id": "MAINT-20260623-30aa07",
      "device_id": "pump-002",
      "start_date": null,
      "priority": "scheduled",
      ...
    },
    {
      "maintenance_id": "MAINT-20260623-48c120",
      "device_id": "pump-003",
      ...
    }
  ],
  "total": 2,
  "by_priority": {"urgent": 0, "scheduled": 2},
  ...
}
```

#### 3. Spare Parts Endpoint ✅
```bash
curl http://localhost:8080/api/spare-parts
```
**Response**: 1 spare part with real data
```json
{
  "parts": [
    {
      "part_id": "MB-001",
      "part_name": "Motor Bearing Assembly",
      "equipment_type": "",
      "availability": "unknown",
      "unit_cost": 450.0,
      ...
    }
  ],
  "total": 1,
  ...
}
```

## Data Source Analysis

### Devices Contributing MCP Data

#### Create-Work-Order (6 devices)
- compressor-002 (warning)
- compressor-003 (warning)
- compressor-004 (critical)
- generator-001 (warning)
- generator-002 (warning)
- motor-003 (critical)

#### Schedule-Maintenance (2 devices)
- pump-002 (warning)
- pump-003 (warning)

#### Get-Spare-Parts (1 device)
- pump-003 (warning)

### Healthy Devices
- No MCP tool calls executed (only HealthAgent runs)
- No tool_results generated
- compressor-001, motor-002, motor-004, motor-005, pump-001, pump-004, pump-005 all healthy

## Frontend Integration

### HTML Endpoints Called
Frontend properly configured to call:
- `/api/maintenance-schedule` → loadMaintenanceData()
- `/api/work-orders` → loadWorkOrdersData()
- `/api/spare-parts` → loadSparePartsData()

### UI Display Structure
- **Maintenance Tab** with 3 sub-tabs:
  - 📅 Schedules (2 schedules displayed)
  - 📋 Work Orders (6+ work orders displayed)
  - 🔧 Spare Parts (1 part displayed)

## Architecture Changes

### Before
```
Dashboard Frontend
    ↓
/api/maintenance-schedule
    ↓
extract_maintenance_schedules()
    ↓ [Expected wrapped format - Failed!]
    ↓ [Got Lambda format - No match]
    ↓ [Returned empty list]
Returns: {"schedules": [], "total": 0}
```

### After
```
Dashboard Frontend
    ↓
/api/maintenance-schedule
    ↓
extract_maintenance_schedules()
    ↓ [Parse Lambda format]
    ↓ [Extract body JSON string]
    ↓ [Match internal format]
    ↓ [Successfully return data]
Returns: {"schedules": [MAINT-...], "total": 2}
```

## Code Quality Improvements

1. **Robustness**: Handles multiple MCP response formats
2. **Error Handling**: JSON parsing wrapped in try-catch
3. **Type Safety**: Explicit isinstance() checks before field access
4. **Defaults**: Provides sensible defaults for missing fields
5. **Logging**: Extraction functions work with existing log statements

## Performance Impact

- **Minimal**: JSON parsing only adds microseconds per request
- **No Network Impact**: Processing happens locally on dashboard service
- **Caching**: Dashboard caches results for 360 seconds (existing feature)

## Deployment Notes

1. **No Database Changes**: Extractors work with existing data
2. **No API Changes**: Endpoints return same structure, just with data
3. **No Frontend Changes**: HTML already calls correct endpoints
4. **Backward Compatible**: Still supports wrapped format if encountered

## Verification Checklist

- ✅ Syntax errors: None (verified with get_errors)
- ✅ Work orders endpoint: Returns real data
- ✅ Maintenance schedules: Returns real data
- ✅ Spare parts endpoint: Returns real data
- ✅ Dashboard restart: Applied fixes successfully
- ✅ No runtime errors: All endpoints responding
- ✅ Data quality: All records have required IDs

## Next Actions (Optional)

1. Add logging to track which format is detected
2. Monitor endpoint response times to ensure no degradation
3. Consider adding format statistics endpoint for debugging
4. Update dashboard documentation with format details

## Issue Closed

**Original Issue**: Maintenance section shows 0 work orders, 0 schedules, 0 spare parts
**Status**: ✅ **FIXED** - All endpoints now return real MCP data
**Test Date**: 2026-06-24 00:59:35 UTC

---
*Document created: 2026-06-24*
*Extraction Functions: Production Ready*
*Dashboard Version: 2.0.0*
