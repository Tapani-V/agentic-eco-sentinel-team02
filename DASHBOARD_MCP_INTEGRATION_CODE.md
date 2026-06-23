# Dashboard API - Code Implementation Reference

This document shows the exact code added to `/src/dashboard/routes/api.py` for MCP tool integration.

## Helper Functions - MCP Tool Result Extraction

### Extract Maintenance Schedules
```python
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
        },
        'message': '...'
    }
    """
    maintenance_schedules = []
    
    if not tool_results or 'schedule-maintenance' not in tool_results:
        return maintenance_schedules
    
    schedule_data = tool_results.get('schedule-maintenance')
    
    if isinstance(schedule_data, dict):
        if schedule_data.get('success'):
            maintenance_item = schedule_data.get('data', {})
            maintenance_schedules.append({
                'maintenance_id': maintenance_item.get('maintenance_id'),
                'device_id': maintenance_item.get('device_id'),
                'start_date': maintenance_item.get('start_date'),
                'duration_hours': maintenance_item.get('duration_hours'),
                'priority': maintenance_item.get('priority'),
                'parts_needed': maintenance_item.get('parts_needed', []),
                'estimated_cost': maintenance_item.get('estimated_cost'),
                'reason': maintenance_item.get('reason'),
                'status': 'scheduled',
            })
    elif isinstance(schedule_data, list):
        for item in schedule_data:
            if item.get('success'):
                maintenance_item = item.get('data', {})
                maintenance_schedules.append({
                    'maintenance_id': maintenance_item.get('maintenance_id'),
                    'device_id': maintenance_item.get('device_id'),
                    'start_date': maintenance_item.get('start_date'),
                    'duration_hours': maintenance_item.get('duration_hours'),
                    'priority': maintenance_item.get('priority'),
                    'parts_needed': maintenance_item.get('parts_needed', []),
                    'estimated_cost': maintenance_item.get('estimated_cost'),
                    'reason': maintenance_item.get('reason'),
                    'status': 'scheduled',
                })
    
    return maintenance_schedules
```

### Extract Work Orders
```python
def extract_work_orders(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract work order data from MCP tool_results['create-work-order']
    
    Tool result format:
    {
        'success': bool,
        'data': {
            'work_order_id': '...',
            'device_id': '...',
            'work_type': '...',
            'urgency': 'immediate|urgent|scheduled',
            'assigned_to': '...',
            'estimated_hours': int,
            'description': '...',
            'created_at': '...'
        },
        'message': '...'
    }
    """
    work_orders = []
    
    if not tool_results or 'create-work-order' not in tool_results:
        return work_orders
    
    work_order_data = tool_results.get('create-work-order')
    
    if isinstance(work_order_data, dict):
        if work_order_data.get('success'):
            work_order_item = work_order_data.get('data', {})
            work_orders.append({
                'work_order_id': work_order_item.get('work_order_id'),
                'device_id': work_order_item.get('device_id'),
                'work_type': work_order_item.get('work_type'),
                'urgency': work_order_item.get('urgency'),
                'assigned_to': work_order_item.get('assigned_to'),
                'estimated_hours': work_order_item.get('estimated_hours'),
                'description': work_order_item.get('description'),
                'created_at': work_order_item.get('created_at'),
                'status': 'open',
            })
    elif isinstance(work_order_data, list):
        for item in work_order_data:
            if item.get('success'):
                work_order_item = item.get('data', {})
                work_orders.append({
                    'work_order_id': work_order_item.get('work_order_id'),
                    'device_id': work_order_item.get('device_id'),
                    'work_type': work_order_item.get('work_type'),
                    'urgency': work_order_item.get('urgency'),
                    'assigned_to': work_order_item.get('assigned_to'),
                    'estimated_hours': work_order_item.get('estimated_hours'),
                    'description': work_order_item.get('description'),
                    'created_at': work_order_item.get('created_at'),
                    'status': 'open',
                })
    
    return work_orders
```

### Extract Spare Parts
```python
def extract_spare_parts(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract spare parts data from MCP tool_results['get-spare-parts']
    
    Tool result format:
    {
        'success': bool,
        'data': [
            {
                'part_id': '...',
                'part_name': '...',
                'equipment_type': '...',
                'availability': 'in_stock|on_order|out_of_stock',
                'quantity_available': int,
                'lead_time_days': int,
                'unit_cost': float,
                'criticality': 'critical|high|medium|low'
            },
            ...
        ],
        'message': '...'
    }
    """
    spare_parts = []
    
    if not tool_results or 'get-spare-parts' not in tool_results:
        return spare_parts
    
    parts_data = tool_results.get('get-spare-parts')
    
    if isinstance(parts_data, dict):
        if parts_data.get('success'):
            parts_list = parts_data.get('data', [])
            if isinstance(parts_list, list):
                spare_parts.extend(parts_list)
    elif isinstance(parts_data, list):
        spare_parts.extend(parts_data)
    
    return spare_parts
```

## New Endpoint: GET /api/dashboard/maintenance-schedule

```python
@router.get("/maintenance-schedule")
async def get_maintenance_schedules():
    """
    Real maintenance schedules from MCP tool results
    
    Fetches data from DiagnosisAgent's schedule-maintenance tool
    Sequential fetching prevents overwhelming DiagnosisAgent
    
    Returns:
    {
        'schedules': [
            {
                'maintenance_id': '...',
                'device_id': '...',
                'start_date': '...',
                'duration_hours': int,
                'priority': 'urgent|scheduled',
                'parts_needed': [...],
                'estimated_cost': float,
                'reason': '...',
                'status': 'scheduled'
            }
        ],
        'total': int,
        'by_priority': {'urgent': int, 'scheduled': int},
        'total_estimated_cost': float
    }
    """
    logger.info("📅 Maintenance schedule endpoint (real MCP data)")
    
    # Get all device IDs
    devices_list_data = await orchestrator.get("/devices")
    
    if not devices_list_data:
        logger.error("Failed to fetch device list")
        raise HTTPException(status_code=503, detail="Orchestrator unavailable")
    
    device_ids = devices_list_data.get('devices', [])
    
    # Aggregate all maintenance schedules from all devices (sequential)
    all_schedules = []
    
    for device_id in device_ids:
        device_data = await orchestrator.get(f"/devices/{device_id}")
        
        if not device_data:
            continue
        
        # Extract maintenance schedules from MCP tool results
        tool_results = device_data.get('tool_results', {})
        schedules = extract_maintenance_schedules(tool_results)
        
        all_schedules.extend(schedules)
    
    # Calculate statistics
    urgent_count = sum(1 for s in all_schedules if s.get('priority') == 'urgent')
    scheduled_count = sum(1 for s in all_schedules if s.get('priority') == 'scheduled')
    total_cost = sum(s.get('estimated_cost', 0) for s in all_schedules)
    
    # Sort by priority (urgent first) then by start_date
    all_schedules.sort(
        key=lambda s: (0 if s.get('priority') == 'urgent' else 1, s.get('start_date', ''))
    )
    
    logger.info(f"✅ {len(all_schedules)} maintenance schedules retrieved ({urgent_count} urgent)")
    
    return {
        "schedules": all_schedules,
        "total": len(all_schedules),
        "by_priority": {
            "urgent": urgent_count,
            "scheduled": scheduled_count,
        },
        "total_estimated_cost": round(total_cost, 2),
        "timestamp": datetime.now().isoformat(),
    }
```

## New Endpoint: GET /api/dashboard/work-orders

```python
@router.get("/work-orders")
async def get_work_orders(status: Optional[str] = Query(None)):
    """
    Real work orders from MCP tool results
    
    Fetches data from DiagnosisAgent's create-work-order tool
    Sequential fetching prevents overwhelming DiagnosisAgent
    
    Query Parameters:
        - status: Filter by 'open', 'in_progress', 'completed' (optional)
    
    Returns:
    {
        'work_orders': [
            {
                'work_order_id': '...',
                'device_id': '...',
                'work_type': '...',
                'urgency': 'immediate|urgent|scheduled',
                'assigned_to': '...',
                'estimated_hours': int,
                'description': '...',
                'created_at': '...',
                'status': 'open|in_progress|completed'
            }
        ],
        'total': int,
        'by_urgency': {'immediate': int, 'urgent': int, 'scheduled': int},
        'total_estimated_hours': int
    }
    """
    logger.info(f"📋 Work orders endpoint (status filter: {status})")
    
    # Get all device IDs
    devices_list_data = await orchestrator.get("/devices")
    
    if not devices_list_data:
        logger.error("Failed to fetch device list")
        raise HTTPException(status_code=503, detail="Orchestrator unavailable")
    
    device_ids = devices_list_data.get('devices', [])
    
    # Aggregate all work orders from all devices (sequential)
    all_work_orders = []
    
    for device_id in device_ids:
        device_data = await orchestrator.get(f"/devices/{device_id}")
        
        if not device_data:
            continue
        
        # Extract work orders from MCP tool results
        tool_results = device_data.get('tool_results', {})
        work_orders = extract_work_orders(tool_results)
        
        all_work_orders.extend(work_orders)
    
    # Apply status filter if provided
    if status:
        all_work_orders = [wo for wo in all_work_orders if wo.get('status') == status]
        logger.debug(f"Filtered work orders by status '{status}': {len(all_work_orders)} remaining")
    
    # Calculate statistics
    immediate_count = sum(1 for wo in all_work_orders if wo.get('urgency') == 'immediate')
    urgent_count = sum(1 for wo in all_work_orders if wo.get('urgency') == 'urgent')
    scheduled_count = sum(1 for wo in all_work_orders if wo.get('urgency') == 'scheduled')
    total_hours = sum(wo.get('estimated_hours', 0) for wo in all_work_orders)
    
    # Sort by urgency (immediate → urgent → scheduled)
    urgency_order = {'immediate': 0, 'urgent': 1, 'scheduled': 2}
    all_work_orders.sort(
        key=lambda wo: (urgency_order.get(wo.get('urgency'), 3), wo.get('created_at', ''))
    )
    
    logger.info(f"✅ {len(all_work_orders)} work orders retrieved ({immediate_count} immediate, {urgent_count} urgent)")
    
    return {
        "work_orders": all_work_orders,
        "total": len(all_work_orders),
        "by_urgency": {
            "immediate": immediate_count,
            "urgent": urgent_count,
            "scheduled": scheduled_count,
        },
        "total_estimated_hours": total_hours,
        "timestamp": datetime.now().isoformat(),
    }
```

## New Endpoint: GET /api/dashboard/spare-parts

```python
@router.get("/spare-parts")
async def get_spare_parts(availability: Optional[str] = Query(None)):
    """
    Spare parts availability from MCP tool results
    
    Fetches data from DiagnosisAgent's get-spare-parts tool
    Deduplicates parts (if same part requested across multiple devices)
    Sequential fetching prevents overwhelming DiagnosisAgent
    
    Query Parameters:
        - availability: Filter by 'in_stock', 'on_order', 'out_of_stock' (optional)
    
    Returns:
    {
        'parts': [
            {
                'part_id': '...',
                'part_name': '...',
                'equipment_type': '...',
                'availability': 'in_stock|on_order|out_of_stock',
                'quantity_available': int,
                'lead_time_days': int,
                'unit_cost': float,
                'criticality': 'critical|high|medium|low'
            }
        ],
        'total': int,
        'by_availability': {'in_stock': int, 'on_order': int, 'out_of_stock': int},
        'critical_parts_unavailable': int,
        'total_value': float
    }
    """
    logger.info(f"🔧 Spare parts endpoint (availability filter: {availability})")
    
    # Get all device IDs
    devices_list_data = await orchestrator.get("/devices")
    
    if not devices_list_data:
        logger.error("Failed to fetch device list")
        raise HTTPException(status_code=503, detail="Orchestrator unavailable")
    
    device_ids = devices_list_data.get('devices', [])
    
    # Aggregate all spare parts from all devices, deduplicating by part_id (sequential)
    all_parts_dict = {}  # {part_id: part_data}
    
    for device_id in device_ids:
        device_data = await orchestrator.get(f"/devices/{device_id}")
        
        if not device_data:
            continue
        
        # Extract spare parts from MCP tool results
        tool_results = device_data.get('tool_results', {})
        spare_parts = extract_spare_parts(tool_results)
        
        # Deduplicate by part_id (keep first occurrence or merge if needed)
        for part in spare_parts:
            part_id = part.get('part_id')
            if part_id and part_id not in all_parts_dict:
                all_parts_dict[part_id] = part
    
    # Convert to list
    all_parts = list(all_parts_dict.values())
    
    # Apply availability filter if provided
    if availability:
        all_parts = [p for p in all_parts if p.get('availability') == availability]
        logger.debug(f"Filtered spare parts by availability '{availability}': {len(all_parts)} remaining")
    
    # Calculate statistics
    in_stock_count = sum(1 for p in all_parts if p.get('availability') == 'in_stock')
    on_order_count = sum(1 for p in all_parts if p.get('availability') == 'on_order')
    out_of_stock_count = sum(1 for p in all_parts if p.get('availability') == 'out_of_stock')
    critical_unavailable = sum(
        1 for p in all_parts 
        if p.get('criticality') == 'critical' and p.get('availability') != 'in_stock'
    )
    total_value = sum(
        p.get('unit_cost', 0) * p.get('quantity_available', 0) 
        for p in all_parts 
        if p.get('availability') == 'in_stock'
    )
    
    # Sort by criticality (critical first) then availability (out_of_stock first)
    availability_order = {'out_of_stock': 0, 'on_order': 1, 'in_stock': 2}
    criticality_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    all_parts.sort(
        key=lambda p: (
            criticality_order.get(p.get('criticality'), 4),
            availability_order.get(p.get('availability'), 3)
        )
    )
    
    logger.info(f"✅ {len(all_parts)} spare parts retrieved ({critical_unavailable} critical parts unavailable)")
    
    return {
        "parts": all_parts,
        "total": len(all_parts),
        "by_availability": {
            "in_stock": in_stock_count,
            "on_order": on_order_count,
            "out_of_stock": out_of_stock_count,
        },
        "critical_parts_unavailable": critical_unavailable,
        "total_value_in_stock": round(total_value, 2),
        "timestamp": datetime.now().isoformat(),
    }
```

## Key Implementation Patterns

### 1. Sequential Fetching (Prevent Overload)
```python
for device_id in device_ids:
    device_data = await orchestrator.get(f"/devices/{device_id}")
    # Process one device at a time
```

### 2. Safe Tool Result Extraction
```python
tool_results = device_data.get('tool_results', {})
schedules = extract_maintenance_schedules(tool_results)
# Extract function handles missing/malformed data
```

### 3. Aggregation Pattern
```python
all_schedules = []
for device_id in device_ids:
    # ... fetch and extract ...
    all_schedules.extend(schedules)
# All results combined into single response
```

### 4. Deduplication (Spare Parts)
```python
all_parts_dict = {}  # {part_id: part_data}
for device_id in device_ids:
    for part in spare_parts:
        part_id = part.get('part_id')
        if part_id and part_id not in all_parts_dict:
            all_parts_dict[part_id] = part
all_parts = list(all_parts_dict.values())
```

### 5. Sorting and Statistics
```python
# Sort by priority
all_schedules.sort(key=lambda s: (
    0 if s.get('priority') == 'urgent' else 1,
    s.get('start_date', '')
))

# Calculate statistics
urgent_count = sum(1 for s in all_schedules if s.get('priority') == 'urgent')
total_cost = sum(s.get('estimated_cost', 0) for s in all_schedules)
```

## File Location

All code is in: `/src/dashboard/routes/api.py`

- MCP extractors: Lines 168-333
- New endpoints: Lines 867-1134
- Updated fleet_summary: Lines 370-550
- Updated hard_refresh: Lines 1136-1220
