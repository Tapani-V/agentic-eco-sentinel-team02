# Dashboard API - Quick Reference Card

## ⭐ MCP Tool Integration (June 24, 2026 - Updated)

All dashboard endpoints now return **real data from MCP tools** executed by DiagnosisAgent.

**Data Pipeline**:
```
Orchestrator → HealthAgent → DiagnosisAgent → MCP Tools
                                  ↓
                         Returns tool_results:
                         • schedule-maintenance (Lambda format)
                         • create-work-order (Lambda format)
                         • get-spare-parts (Lambda format)
                                  ↓
                         Dashboard API extracts & aggregates
                         (Now handles Lambda format parsing!)
                                  ↓
                         Returns real operational data
```

**Key Extraction Functions** (in `src/dashboard/routes/api.py`):
- `extract_maintenance_schedules()` - Parses Lambda format + JSON strings → Returns 2 real schedules
- `extract_work_orders()` - Parses Lambda format + flat format → Returns 12 work orders
- `extract_spare_parts()` - Parses Lambda format + JSON strings → Returns 1 spare part

**Format Handling** (Updated June 24):
All extractors now support:
1. **Lambda format**: `{"statusCode": 200, "body": "{...JSON...}"}`
2. **Wrapped format**: `{"success": true, "data": {...}}`
3. **Flat format**: `{field1: ..., field2: ...}`
4. **List format**: `{parts: [...]}` or `{schedules: [...]}`

**No More Mock Data**: 100% real data from agent pipeline ✅ VERIFIED

---

## Current Data Status (June 24, 2026)

| Endpoint | Data Source | Count | Example |
|----------|-------------|-------|---------|
| `/api/work-orders` | 6 warning/critical devices | **12 orders** | WO-dee0b7ae, WO-07d871a1, ... |
| `/api/maintenance-schedule` | 2 pump devices | **2 schedules** | MAINT-20260623-30aa07, MAINT-20260623-48c120 |
| `/api/spare-parts` | pump-003 device | **1 part** | Motor Bearing Assembly ($450) |

---

## New Endpoints

### 1. Fleet Summary (Updated)
```bash
GET /api/dashboard/fleet-summary
```

**Returns**: Device health metrics + real MCP data

**Response**:
```json
{
  "total_devices": 17,
  "healthy_devices": 8,
  "warning_devices": 6,
  "critical_devices": 3,
  "fleet_health_percent": 47,
  "_mcp_data": {
    "work_orders": 4,
    "maintenance_schedules": 3,
    "spare_parts_available": 12,
    "urgent_work_orders": 2
  }
}
```

**Time**: 30-60 seconds (sequential fetching of all devices)  
**Caching**: 6 minutes (auto-refresh or hard refresh)

---

### 2. Maintenance Schedules (NEW)
```bash
GET /api/dashboard/maintenance-schedule
```

**Returns**: Real maintenance schedules from MCP tool

**Response**:
```json
{
  "schedules": [
    {
      "maintenance_id": "maint-001",
      "device_id": "pump-001",
      "start_date": "2026-06-25T10:00:00",
      "duration_hours": 4,
      "priority": "urgent",
      "parts_needed": ["seal-kit-001"],
      "estimated_cost": 250.00,
      "reason": "Bearing degradation"
    }
  ],
  "total": 5,
  "by_priority": {"urgent": 2, "scheduled": 3},
  "total_estimated_cost": 1250.00
}
```

**Time**: 30-60 seconds  
**Sorted by**: Priority (urgent first), then by start_date

---

### 3. Work Orders (NEW)
```bash
GET /api/dashboard/work-orders
GET /api/dashboard/work-orders?status=open
GET /api/dashboard/work-orders?status=in_progress
GET /api/dashboard/work-orders?status=completed
```

**Returns**: Real work orders from MCP tool

**Query Parameters**:
- `status`: open, in_progress, completed (optional)

**Response**:
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
  "total_estimated_hours": 8
}
```

**Time**: 30-60 seconds  
**Sorted by**: Urgency (immediate → urgent → scheduled), then by created_at

---

### 4. Spare Parts (NEW)
```bash
GET /api/dashboard/spare-parts
GET /api/dashboard/spare-parts?availability=in_stock
GET /api/dashboard/spare-parts?availability=on_order
GET /api/dashboard/spare-parts?availability=out_of_stock
```

**Returns**: Real spare parts from MCP tool

**Query Parameters**:
- `availability`: in_stock, on_order, out_of_stock (optional)

**Response**:
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
  "total_value_in_stock": 3500.00
}
```

**Time**: 30-60 seconds  
**Sorted by**: Criticality (critical first), then availability  
**Deduplication**: By part_id (multiple devices requesting same part)

---

## Key Features

✅ **Real Data**: All from DiagnosisAgent MCP tools  
✅ **Sequential Fetching**: One device at a time (prevents overload)  
✅ **Aggregation**: All devices combined into single response  
✅ **Filtering**: Query parameters for status/availability/priority  
✅ **Statistics**: Counts, totals, breakdowns  
✅ **Caching**: 6-minute TTL on fleet summary  
✅ **Hard Refresh**: `/api/cache-clear` bypasses cache  

---

## Error Responses

### 503 Service Unavailable
```json
{
  "detail": "Orchestrator unavailable"
}
```
**Cause**: Cannot reach orchestrator (port 8000)  
**Fix**: Start orchestrator service

### 404 Not Found
```json
{
  "detail": "Device {device_id} not found"
}
```
**Cause**: Device doesn't exist in data/generated/  
**Fix**: Load test devices first

---

## Performance Notes

| Endpoint | Time | Notes |
|----------|------|-------|
| `/api/dashboard/fleet-summary` | 30-60s | Sequential fetch all devices, cached 6min |
| `/api/dashboard/maintenance-schedule` | 30-60s | Sequential fetch all devices, no cache |
| `/api/dashboard/work-orders` | 30-60s | Sequential fetch all devices, no cache |
| `/api/dashboard/spare-parts` | 30-60s | Sequential fetch all devices, deduplicated |

**Why Sequential?**
- Prevents overwhelming DiagnosisAgent
- MCP tools need proper sequencing
- More reliable than parallel requests

**Why No Cache on New Endpoints?**
- MCP tools should return fresh data each time
- Maintenance/work orders change frequently
- 30-60 seconds is acceptable for operational tools

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Dashboard UI                       │
└──────────────────────┬──────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────┐
│              Dashboard API (port 8080)               │
│                                                      │
│  /api/dashboard/fleet-summary      (cached)          │
│  /api/dashboard/maintenance-schedule                │
│  /api/dashboard/work-orders                         │
│  /api/dashboard/spare-parts                         │
│  /api/cache-clear                  (hard refresh)    │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ↓                             ↓
┌──────────────────┐        ┌──────────────────┐
│  Orchestrator    │        │  Orchestrator    │
│  /devices        │        │  /devices/{id}   │
│  (list IDs)      │        │  (analyze device)│
└────────┬─────────┘        └────────┬─────────┘
         │                           │
         └──────────────┬────────────┘
                        ↓
        ┌───────────────────────────────────┐
        │      HealthAgent (port 8001)      │
        │     Classify: healthy/warning/    │
        │     critical                      │
        └────────────┬──────────────────────┘
                     │
                     ↓
        ┌───────────────────────────────────┐
        │    DiagnosisAgent (port 8002)     │
        │  Root cause + MCP tool calls:     │
        │  - schedule-maintenance           │
        │  - create-work-order              │
        │  - get-spare-parts                │
        └───────────────────────────────────┘
```

---

## Usage Examples

### Fetch critical devices with open work orders
```bash
# Get fleet summary
FLEET=$(curl -s http://localhost:8080/api/fleet-summary)

# Get open work orders
WOS=$(curl -s http://localhost:8080/api/work-orders?status=open)

# Parse and filter in your UI
```

### Monitor spare parts availability
```bash
# Get all spare parts
PARTS=$(curl -s http://localhost:8080/api/spare-parts)

# Filter critical parts out of stock
CRITICAL=$(echo $PARTS | jq '.parts[] | select(.criticality=="critical" and .availability=="out_of_stock")')

# Alert if any critical parts unavailable
if [ $(echo $CRITICAL | jq length) -gt 0 ]; then
  echo "ALERT: Critical parts unavailable!"
fi
```

### Schedule maintenance window
```bash
# Get maintenance schedules
SCHEDULES=$(curl -s http://localhost:8080/api/maintenance-schedule)

# Get urgent schedules (start planning)
URGENT=$(echo $SCHEDULES | jq '.schedules[] | select(.priority=="urgent")')
```

---

## Testing

```bash
# Run full test suite
python3 test_dashboard_mcp_integration.py

# Individual endpoint tests
curl http://localhost:8080/api/fleet-summary | jq '.'
curl http://localhost:8080/api/maintenance-schedule | jq '.total'
curl http://localhost:8080/api/work-orders | jq '.by_urgency'
curl http://localhost:8080/api/spare-parts | jq '.critical_parts_unavailable'

# With filtering
curl http://localhost:8080/api/work-orders?status=open | jq '.total'
curl http://localhost:8080/api/spare-parts?availability=in_stock | jq '.total'
```

---

## Developer Notes

### MCP Tool Result Format
Each device returns `tool_results` dict:
```python
{
  'schedule-maintenance': {'success': bool, 'data': {...}},
  'create-work-order': {'success': bool, 'data': {...}},
  'get-spare-parts': {'success': bool, 'data': [...]}
}
```

### Extractor Functions
Located in `/src/dashboard/routes/api.py` (lines 168-333):
- `extract_maintenance_schedules(tool_results)` → List[Dict]
- `extract_work_orders(tool_results)` → List[Dict]
- `extract_spare_parts(tool_results)` → List[Dict]

### Adding a New Tool
1. Receive tool output in `device_data['tool_results']['{tool-name}']`
2. Create extractor function: `def extract_{tool_name}(tool_results)`
3. Create dashboard endpoint: `@router.get("/api/dashboard/{endpoint-name}")`
4. Use same pattern: sequential fetch + extract + aggregate

---

## Troubleshooting

**Q: Endpoints timing out (>60s)?**
A: Orchestrator might be slow. Check if DiagnosisAgent is responding.

**Q: No MCP data in fleet-summary?**
A: Check if devices are triggering DiagnosisAgent. Healthy devices skip diagnosis.

**Q: Work orders empty?**
A: Create a critical device in test data to trigger work order creation.

**Q: Parts deduplication not working?**
A: Check if parts have unique `part_id` field.
