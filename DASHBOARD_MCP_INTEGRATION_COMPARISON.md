# Dashboard API - Before & After Code Comparison

## Before: Mock Data Implementation

### Old Fleet Summary Response
```json
{
  "total_devices": 17,
  "healthy_devices": 3,  // ← MOCK DATA
  "warning_devices": 8,  // ← MOCK DATA
  "critical_devices": 6, // ← MOCK DATA
  "fleet_health_percent": 18,
  "degradation_trend": "stable"
}
```

### Old Maintenance Endpoint
```python
@router.get("/maintenance/schedule")
async def maintenance_schedule():
    """Derived from device health states and agent recommendations."""
    # Generated synthetic maintenance items based on health status
    maintenance_items.append({
        "device_id": device_id,
        "priority": priority,
        "health_status": health_status,
        "recommended_action": device_data.get('action', 'MONITOR_ONLY'),
        "diagnosis": device_data.get('diagnosis', ''),
        "estimated_duration": "2-4 hours",  # ← HARDCODED
    })
```

### Missing Endpoints
- ❌ No `/api/dashboard/work-orders` endpoint
- ❌ No `/api/dashboard/spare-parts` endpoint
- ❌ No MCP tool result extraction

---

## After: Real MCP Tool Integration

### New Fleet Summary Response
```json
{
  "total_devices": 17,
  "healthy_devices": 8,   // ← REAL DATA (from HealthAgent)
  "warning_devices": 6,   // ← REAL DATA (from HealthAgent)
  "critical_devices": 3,  // ← REAL DATA (from HealthAgent)
  "fleet_health_percent": 47,
  "degradation_trend": "stable",
  "_mcp_data": {          // ← NEW: Real MCP tool results
    "work_orders": 4,     // ← From create-work-order tool
    "maintenance_schedules": 3,  // ← From schedule-maintenance tool
    "spare_parts_available": 12, // ← From get-spare-parts tool
    "urgent_work_orders": 2
  },
  "_analytics": { ... },
  "_problematic_devices": [ ... ]
}
```

### New MCP Tool Result Extractors

```python
# ============================================================================
# MCP TOOL RESULT EXTRACTORS - Extract real data from tool_results
# ============================================================================

def extract_maintenance_schedules(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract maintenance schedule data from MCP tool_results['schedule-maintenance']
    
    Tool result format:
    {
        'success': bool,
        'data': {
            'maintenance_id': '...',
            'device_id': '...',
            'start_date': '...',
            'duration_hours': int,
            'priority': 'urgent|scheduled',
            'parts_needed': [...],
            'estimated_cost': float,
            'reason': '...'
        }
    }
    """
    # Safely extract data from nested dictionaries
    # Handle both dict and list responses
    # Return structured maintenance schedule data


def extract_work_orders(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract work order data from MCP tool_results['create-work-order']
    
    Returns structured work order data with:
    - work_order_id, device_id, work_type, urgency, assigned_to
    - estimated_hours, description, created_at
    """
    # Safely extract and structure work order data


def extract_spare_parts(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract spare parts data from MCP tool_results['get-spare-parts']
    
    Returns structured spare parts data with:
    - part_id, part_name, equipment_type, availability
    - quantity_available, lead_time_days, unit_cost, criticality
    """
    # Safely extract and structure spare parts data
```

### New Maintenance Schedule Endpoint

```python
@router.get("/maintenance-schedule")
async def get_maintenance_schedules():
    """
    ✨ NEW ENDPOINT - Real maintenance schedules from MCP tool results
    
    Fetches data from DiagnosisAgent's schedule-maintenance tool
    Sequential fetching prevents overwhelming DiagnosisAgent
    """
    # Get all device IDs
    device_ids = await orchestrator.get("/devices")
    
    # Aggregate all maintenance schedules from all devices (sequential)
    all_schedules = []
    
    for device_id in device_ids:
        device_data = await orchestrator.get(f"/devices/{device_id}")
        
        # Extract maintenance schedules from MCP tool results
        tool_results = device_data.get('tool_results', {})
        schedules = extract_maintenance_schedules(tool_results)
        all_schedules.extend(schedules)
    
    # Return organized by priority (urgent first)
    return {
        "schedules": all_schedules,
        "total": len(all_schedules),
        "by_priority": {"urgent": ..., "scheduled": ...},
        "total_estimated_cost": ...,
        "timestamp": ...
    }
```

### New Work Orders Endpoint

```python
@router.get("/work-orders")
async def get_work_orders(status: Optional[str] = Query(None)):
    """
    ✨ NEW ENDPOINT - Real work orders from MCP tool results
    
    Fetches data from DiagnosisAgent's create-work-order tool
    Optional filtering by status: open|in_progress|completed
    """
    # Get all device IDs
    device_ids = await orchestrator.get("/devices")
    
    # Aggregate all work orders from all devices (sequential)
    all_work_orders = []
    
    for device_id in device_ids:
        device_data = await orchestrator.get(f"/devices/{device_id}")
        
        # Extract work orders from MCP tool results
        tool_results = device_data.get('tool_results', {})
        work_orders = extract_work_orders(tool_results)
        all_work_orders.extend(work_orders)
    
    # Apply filters and return organized by urgency
    return {
        "work_orders": all_work_orders,
        "total": len(all_work_orders),
        "by_urgency": {"immediate": ..., "urgent": ..., "scheduled": ...},
        "total_estimated_hours": ...,
        "timestamp": ...
    }
```

### New Spare Parts Endpoint

```python
@router.get("/spare-parts")
async def get_spare_parts(availability: Optional[str] = Query(None)):
    """
    ✨ NEW ENDPOINT - Real spare parts availability from MCP tool results
    
    Fetches data from DiagnosisAgent's get-spare-parts tool
    Deduplicates parts by part_id (handles multiple device requests)
    Optional filtering by availability: in_stock|on_order|out_of_stock
    """
    # Get all device IDs
    device_ids = await orchestrator.get("/devices")
    
    # Aggregate all spare parts from all devices, deduplicating by part_id
    all_parts_dict = {}  # {part_id: part_data}
    
    for device_id in device_ids:
        device_data = await orchestrator.get(f"/devices/{device_id}")
        
        # Extract spare parts from MCP tool results
        tool_results = device_data.get('tool_results', {})
        spare_parts = extract_spare_parts(tool_results)
        
        # Deduplicate by part_id
        for part in spare_parts:
            part_id = part.get('part_id')
            if part_id and part_id not in all_parts_dict:
                all_parts_dict[part_id] = part
    
    # Return organized by criticality and availability
    return {
        "parts": list(all_parts_dict.values()),
        "total": len(all_parts_dict),
        "by_availability": {"in_stock": ..., "on_order": ..., "out_of_stock": ...},
        "critical_parts_unavailable": ...,
        "total_value_in_stock": ...,
        "timestamp": ...
    }
```

### Updated Hard Refresh Endpoint

```python
@router.get("/cache-clear")
async def hard_refresh_cache():
    """
    ✨ UPDATED - Now aggregates REAL MCP tool results
    
    Before: Only returned device health metrics
    After: Also includes work orders, maintenance schedules, spare parts
    """
    # Start protected fetch
    fetch_queue.start_fetch('manual')
    
    try:
        # Get devices and fetch each one (sequential)
        device_ids = await orchestrator.get("/devices")
        
        # Aggregate MCP tool results
        all_work_orders = []
        all_maintenance_schedules = []
        all_spare_parts = {}
        
        for device_id in device_ids:
            device_data = await orchestrator.get(f"/devices/{device_id}")
            
            # Extract ALL MCP tools from this device
            tool_results = device_data.get('tool_results', {})
            
            all_work_orders.extend(extract_work_orders(tool_results))
            all_maintenance_schedules.extend(extract_maintenance_schedules(tool_results))
            
            spare_parts = extract_spare_parts(tool_results)
            for part in spare_parts:
                part_id = part.get('part_id')
                if part_id and part_id not in all_spare_parts:
                    all_spare_parts[part_id] = part
        
        # Return including MCP data
        return {
            "total_devices": total,
            "healthy_devices": healthy,
            "warning_devices": warning,
            "critical_devices": critical,
            "_mcp_data": {
                "work_orders": len(all_work_orders),
                "maintenance_schedules": len(all_maintenance_schedules),
                "spare_parts_available": len(all_spare_parts),
            },
            ...
        }
```

---

## Data Flow Comparison

### BEFORE
```
Dashboard UI
    ↓
Dashboard API (MOCK DATA)
    └─ /api/dashboard/fleet-summary
       └─ Returns hardcoded: 3 healthy, 8 warning, 6 critical
```

### AFTER
```
Dashboard UI
    ↓
Dashboard API (REAL DATA)
    ├─ /api/dashboard/fleet-summary (device health + MCP counts)
    ├─ /api/dashboard/maintenance-schedule (real from MCP)
    ├─ /api/dashboard/work-orders (real from MCP)
    └─ /api/dashboard/spare-parts (real from MCP)
        ↓
    Orchestrator API (port 8000)
        ├─ GET /devices          (list device IDs)
        └─ GET /devices/{id}     (get device analysis + MCP tool results)
            ↓
        HealthAgent (classify device health)
            ↓
        DiagnosisAgent (diagnose + invoke MCP tools)
            ├─ MCP Tool: schedule-maintenance
            ├─ MCP Tool: create-work-order
            └─ MCP Tool: get-spare-parts
```

---

## Key Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **Data Source** | Hardcoded mock data | Real device data from agents |
| **Device Health** | 3/8/6 (mock) | Actual counts from HealthAgent |
| **Work Orders** | ❌ None | ✅ From create-work-order MCP tool |
| **Maintenance** | Synthetic based on health | ✅ Real from schedule-maintenance MCP tool |
| **Spare Parts** | ❌ None | ✅ From get-spare-parts MCP tool |
| **Endpoints** | 1 legacy endpoint | 4 production endpoints |
| **Fetching** | Sequential (data only) | Sequential (prevents overload) |
| **Caching** | 6-minute TTL | 6-minute TTL (consistent) |
| **Filtering** | ❌ None | ✅ status, availability, priority |
| **Statistics** | Basic counts | ✅ Detailed: by_priority, by_urgency, critical_unavailable |
| **Deduplication** | ❌ N/A | ✅ Spare parts by part_id |

---

## Response Data Structure Examples

### OLD Maintenance Endpoint
```json
{
  "work_orders": 2,
  "scheduled_maintenance": 3,
  "items": [
    {
      "device_id": "pump-001",
      "priority": "urgent",
      "recommended_action": "MONITOR_ONLY",
      "estimated_duration": "2-4 hours"  // ← HARDCODED
    }
  ]
}
```

### NEW Maintenance Schedule Endpoint
```json
{
  "schedules": [
    {
      "maintenance_id": "maint-001",
      "device_id": "pump-001",
      "start_date": "2026-06-25T10:00:00",  // ← REAL from MCP tool
      "duration_hours": 4,                   // ← REAL from MCP tool
      "priority": "urgent",                  // ← REAL from MCP tool
      "parts_needed": ["seal-kit-001"],      // ← REAL from MCP tool
      "estimated_cost": 250.00,              // ← REAL from MCP tool
      "reason": "Bearing degradation"        // ← REAL from MCP tool
    }
  ],
  "total": 5,
  "by_priority": {"urgent": 2, "scheduled": 3},
  "total_estimated_cost": 1250.00
}
```

---

## Testing the Changes

### Run the test suite:
```bash
python3 test_dashboard_mcp_integration.py
```

### Manual curl tests:
```bash
# Test fleet summary with MCP data
curl http://localhost:8080/api/fleet-summary | jq '._mcp_data'

# Test maintenance schedules (real MCP data)
curl http://localhost:8080/api/maintenance-schedule | jq '.schedules[0]'

# Test work orders
curl http://localhost:8080/api/work-orders | jq '.work_orders[0]'

# Test spare parts with filtering
curl http://localhost:8080/api/spare-parts?availability=in_stock | jq '.parts[0]'
```

---

## Files Changed

**Single File Modified:**
- `/src/dashboard/routes/api.py`
  - Added 3 helper functions (170+ lines)
  - Updated 1 endpoint (fleet_summary)
  - Updated 1 endpoint (hard_refresh_cache)
  - Added 3 new endpoints (450+ lines)
  - Total: ~620 lines of new/modified code

**New Test File:**
- `test_dashboard_mcp_integration.py` (comprehensive test suite)

**Documentation:**
- `DASHBOARD_MCP_INTEGRATION_GUIDE.md` (this guide)
- `DASHBOARD_MCP_INTEGRATION_COMPARISON.md` (before/after)
