"""
Dashboard API Routes - Agentic-Eco-Sentinel

All endpoints fetch REAL DATA from the Orchestrator service (port 8000).
Dashboard acts as a client-focused visualization layer.

Integration with Multi-Agent System:
- Fleet summary aggregates device data from HealthAgent + DiagnosisAgent
- MCP tool results from DiagnosisAgent are extracted and displayed
- Sequential fetching prevents overwhelming DiagnosisAgent
- Real work orders, maintenance schedules, and spare parts from tool_results

Data Flow:
    Dashboard API ←→ Orchestrator API (port 8000)
         ↓                    ↓
    Real Device Data    HealthAgent (classify)
    Real Agent Analysis DiagnosisAgent (diagnose + MCP tools)
    Real Tool Results   MCP Tools: schedule-maintenance, create-work-order, get-spare-parts
"""

import logging
import httpx
import ssl
import asyncio
import json
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from ..config import settings

logger = logging.getLogger('DASHBOARD.API')
router = APIRouter()


# ============================================================================
# SHARED DATA CACHE (prevents duplicate fetches)
# ============================================================================

class DataCache:
    """Cache for device data to ensure consistency across endpoints"""
    def __init__(self):
        self.data = None
        self.timestamp = None
        self.ttl = 360  # Cache valid for 360 seconds (6 minutes) - PRODUCTION GRADE
    
    def get(self):
        """Get cached data if still valid"""
        if not self.data:
            return None
        
        elapsed = (datetime.now() - self.timestamp).total_seconds()
        if elapsed > self.ttl:
            self.data = None
            return None
        
        return self.data
    
    def set(self, data):
        """Set cache data"""
        self.data = data
        self.timestamp = datetime.now()
    
    def invalidate(self):
        """Clear cache"""
        self.data = None
        self.timestamp = None

data_cache = DataCache()


def build_agent_decisions(devices: List[Dict[str, Any]], total_devices: int, healthy_devices: int) -> Dict[str, Any]:
    """Summarize live DiagnosisAgent actions and MCP tool usage for the dashboard."""
    actions_by_equipment: Dict[str, Dict[str, int]] = {}
    tool_counts = {
        'get-spare-parts': 0,
        'schedule-maintenance': 0,
        'create-work-order': 0,
    }
    urgent_repairs = 0
    scheduled_maintenance = 0

    for device in devices:
        equipment_type = device.get('equipment_type', 'UNKNOWN')
        action = device.get('action')
        equipment_actions = actions_by_equipment.setdefault(
            equipment_type,
            {'urgent_repair': 0, 'scheduled_maintenance': 0},
        )
        if action == 'URGENT_REPAIR':
            urgent_repairs += 1
            equipment_actions['urgent_repair'] += 1
        elif action == 'SCHEDULE_MAINTENANCE':
            scheduled_maintenance += 1
            equipment_actions['scheduled_maintenance'] += 1

        for tool_name in device.get('mcp_tools_used', []):
            if tool_name in tool_counts:
                tool_counts[tool_name] += 1

    return {
        'health_agent_analyses': total_devices,
        'diagnosis_agent_analyses': max(0, total_devices - healthy_devices),
        'urgent_repairs': urgent_repairs,
        'scheduled_maintenance': scheduled_maintenance,
        'tool_counts': tool_counts,
        'actions_by_equipment': actions_by_equipment,
    }


# ============================================================================
# REQUEST QUEUE - Prevent overlapping fetches (PRODUCTION GRADE)
# ============================================================================

class FetchQueue:
    """Manages fetch requests to prevent concurrent device fetches"""
    def __init__(self):
        self.fetching = False
        self.fetch_type = None  # 'auto' or 'manual'
        self.start_time = None
    
    def is_fetching(self):
        return self.fetching
    
    def start_fetch(self, fetch_type='auto'):
        self.fetching = True
        self.fetch_type = fetch_type
        self.start_time = datetime.now()
        logger.info(f"🚀 Starting {fetch_type} fetch at {self.start_time}")
    
    def end_fetch(self):
        if self.fetching:
            duration = (datetime.now() - self.start_time).total_seconds()
            logger.info(f"✅ {self.fetch_type} fetch complete in {duration:.1f}s")
        self.fetching = False
        self.fetch_type = None
    
    def cancel_fetch(self):
        if self.fetching:
            logger.warning(f"⏹️  Cancelling {self.fetch_type} fetch")
        self.fetching = False
        self.fetch_type = None

fetch_queue = FetchQueue()


# ============================================================================
# ORCHESTRATOR API CLIENT
# ============================================================================

class OrchestratorClient:
    """Client for communicating with Orchestrator service"""
    
    def __init__(self, base_url: str, timeout: int = 300):  # 5 minutes for sequential requests
        self.base_url = base_url.rstrip('/') if base_url else ''
        self.timeout = timeout
        self.logger = logging.getLogger('ORCHESTRATOR_CLIENT')
    
    async def get(self, endpoint: str, retries: int = 2, **kwargs) -> Optional[Dict[str, Any]]:
        """Make GET request to orchestrator, retrying transient connection/timeout errors"""
        last_error = None
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    url = f"{self.base_url}{endpoint}"
                    self.logger.debug(f"🔗 GET {endpoint} (attempt {attempt + 1}/{retries + 1})")
                    response = await client.get(url, **kwargs)
                    
                    if response.status_code == 200:
                        self.logger.debug(f"✅ {endpoint} - 200 OK")
                        return response.json()
                    else:
                        self.logger.error(f"❌ {endpoint} - {response.status_code}")
                        return None
            except httpx.ConnectError:
                last_error = 'connect'
            except httpx.TimeoutException:
                last_error = 'timeout'
            except ssl.SSLError:
                # Observed intermittently (self-resolving TLS handshake
                # failures) - retry like a transient connect error instead
                # of permanently skipping this device for the cache TTL.
                last_error = 'connect'
            except Exception as e:
                self.logger.error(f"❌ Error calling {endpoint}: {str(e)}")
                return None
            
            if attempt < retries:
                await asyncio.sleep(0.5 * (attempt + 1))  # 0.5s, 1s backoff
        
        if last_error == 'connect':
            self.logger.error(f"🚫 Cannot connect to orchestrator: {self.base_url} (after {retries + 1} attempts)")
        elif last_error == 'timeout':
            self.logger.error(f"⏱️  Timeout calling {endpoint} (after {retries + 1} attempts)")
        return None
    
    async def post(self, endpoint: str, data: Dict[str, Any], **kwargs) -> Optional[Dict[str, Any]]:
        """Make POST request to orchestrator"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}{endpoint}"
                self.logger.debug(f"🔗 POST {endpoint}")
                response = await client.post(url, json=data, **kwargs)
                
                if response.status_code in [200, 201]:
                    self.logger.debug(f"✅ {endpoint} - {response.status_code}")
                    return response.json()
                else:
                    self.logger.error(f"❌ {endpoint} - {response.status_code}")
                    return None
        except Exception as e:
            self.logger.error(f"❌ Error calling POST {endpoint}: {str(e)}")
            return None


# Initialize orchestrator client
orchestrator = OrchestratorClient(settings.ORCHESTRATOR_URL, timeout=60)  # Reduced timeout from 300s to 60s


# ============================================================================
# MCP TOOL RESULT EXTRACTORS - Extract real data from tool_results
# ============================================================================

def extract_maintenance_schedules(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract maintenance schedule data from MCP tool_results['schedule-maintenance']
    
    Handles multiple formats:
    1. Lambda format: {"statusCode": 200, "body": "{...}"}
    2. Wrapped format: {"success": true, "data": {...}}
    3. Flat format: direct fields
    """
    import json
    maintenance_schedules = []
    
    if not tool_results or 'schedule-maintenance' not in tool_results:
        return maintenance_schedules
    
    schedule_data = tool_results.get('schedule-maintenance')
    
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
            # Otherwise return as-is (wrapped or flat format)
            return data
        return None
    
    # Parse the response
    parsed_data = parse_mcp_response(schedule_data)
    
    if isinstance(parsed_data, dict):
        # Check if it's wrapped format (has 'success' and 'data' fields)
        if 'success' in parsed_data and 'data' in parsed_data:
            if parsed_data.get('success'):
                items = parsed_data.get('data', [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get('maintenance_id'):
                            maintenance_schedules.append({
                                'maintenance_id': item.get('maintenance_id'),
                                'device_id': item.get('device_id', ''),
                                'start_date': item.get('start_date'),
                                'duration_hours': item.get('duration_hours', 0),
                                'priority': item.get('priority', 'scheduled'),
                                'parts_needed': item.get('parts_needed', []),
                                'estimated_cost': item.get('estimated_cost', 0),
                                'reason': item.get('reason', ''),
                                'status': 'scheduled',
                            })
                else:
                    # data is a single object
                    item = items
                    if item.get('maintenance_id'):
                        maintenance_schedules.append({
                            'maintenance_id': item.get('maintenance_id'),
                            'device_id': item.get('device_id', ''),
                            'start_date': item.get('start_date'),
                            'duration_hours': item.get('duration_hours', 0),
                            'priority': item.get('priority', 'scheduled'),
                            'parts_needed': item.get('parts_needed', []),
                            'estimated_cost': item.get('estimated_cost', 0),
                            'reason': item.get('reason', ''),
                            'status': 'scheduled',
                        })
        # Otherwise treat as flat format or list
        elif isinstance(parsed_data.get('maintenance'), list):
            # Format: {"maintenance": [...]}
            for item in parsed_data.get('maintenance', []):
                if isinstance(item, dict) and item.get('maintenance_id'):
                    maintenance_schedules.append({
                        'maintenance_id': item.get('maintenance_id'),
                        'device_id': item.get('device_id', ''),
                        'start_date': item.get('start_date'),
                        'duration_hours': item.get('duration_hours', 0),
                        'priority': item.get('priority', 'scheduled'),
                        'parts_needed': item.get('parts_needed', []),
                        'estimated_cost': item.get('estimated_cost', 0),
                        'reason': item.get('reason', ''),
                        'status': 'scheduled',
                    })
        elif parsed_data.get('maintenance_id'):
            # Single maintenance object
            maintenance_schedules.append({
                'maintenance_id': parsed_data.get('maintenance_id'),
                'device_id': parsed_data.get('device_id', ''),
                'start_date': parsed_data.get('start_date'),
                'duration_hours': parsed_data.get('duration_hours', 0),
                'priority': parsed_data.get('priority', 'scheduled'),
                'parts_needed': parsed_data.get('parts_needed', []),
                'estimated_cost': parsed_data.get('estimated_cost', 0),
                'reason': parsed_data.get('reason', ''),
                'status': 'scheduled',
                    })
    
    return maintenance_schedules


def extract_work_orders(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract work order data from MCP tool_results['create-work-order']
    
    Handles both wrapped format (with 'success' and 'data') and flat format (direct fields)
    """
    work_orders = []
    
    if not tool_results or 'create-work-order' not in tool_results:
        return work_orders
    
    work_order_data = tool_results.get('create-work-order')
    
    if isinstance(work_order_data, dict):
        # Check if it's wrapped format (has 'success' and 'data' fields)
        if 'success' in work_order_data and 'data' in work_order_data:
            if work_order_data.get('success'):
                work_order_item = work_order_data.get('data', {})
                if work_order_item.get('work_order_id'):  # Only add if has ID
                    work_orders.append({
                        'work_order_id': work_order_item.get('work_order_id'),
                        'device_id': work_order_item.get('device_id'),
                        'work_type': work_order_item.get('work_type', 'Maintenance'),
                        'urgency': work_order_item.get('urgency', 'scheduled'),
                        'assigned_to': work_order_item.get('assigned_to', 'Unassigned'),
                        'estimated_hours': work_order_item.get('estimated_hours', 0),
                        'description': work_order_item.get('description', ''),
                        'created_at': work_order_item.get('created_at'),
                        'status': 'open',
                    })
        # Otherwise treat as flat format (direct fields)
        elif work_order_data.get('work_order_id'):
            work_orders.append({
                'work_order_id': work_order_data.get('work_order_id'),
                'device_id': work_order_data.get('device_id', ''),
                'work_type': work_order_data.get('work_type', 'Maintenance'),
                'urgency': work_order_data.get('urgency', 'scheduled'),
                'assigned_to': work_order_data.get('assigned_to', 'Unassigned'),
                'estimated_hours': work_order_data.get('estimated_hours', 0),
                'description': work_order_data.get('description', ''),
                'created_at': work_order_data.get('created_at'),
                'status': work_order_data.get('status', 'open'),
            })
    elif isinstance(work_order_data, list):
        for item in work_order_data:
            if isinstance(item, dict):
                # Check if it's wrapped format
                if 'success' in item and 'data' in item:
                    if item.get('success'):
                        work_order_item = item.get('data', {})
                        if work_order_item.get('work_order_id'):
                            work_orders.append({
                                'work_order_id': work_order_item.get('work_order_id'),
                                'device_id': work_order_item.get('device_id'),
                                'work_type': work_order_item.get('work_type', 'Maintenance'),
                                'urgency': work_order_item.get('urgency', 'scheduled'),
                                'assigned_to': work_order_item.get('assigned_to', 'Unassigned'),
                                'estimated_hours': work_order_item.get('estimated_hours', 0),
                                'description': work_order_item.get('description', ''),
                                'created_at': work_order_item.get('created_at'),
                                'status': 'open',
                            })
                # Otherwise treat as flat format
                elif item.get('work_order_id'):
                    work_orders.append({
                        'work_order_id': item.get('work_order_id'),
                        'device_id': item.get('device_id', ''),
                        'work_type': item.get('work_type', 'Maintenance'),
                        'urgency': item.get('urgency', 'scheduled'),
                        'assigned_to': item.get('assigned_to', 'Unassigned'),
                        'estimated_hours': item.get('estimated_hours', 0),
                        'description': item.get('description', ''),
                        'created_at': item.get('created_at'),
                        'status': item.get('status', 'open'),
                    })
    
    return work_orders


def extract_spare_parts(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract spare parts data from MCP tool_results['get-spare-parts']
    
    Handles multiple formats:
    1. Lambda format: {"statusCode": 200, "body": "{...}"}
    2. Wrapped format: {"success": true, "data": [...]}
    3. Flat format: list or direct dict
    
    Maps different field names:
    - stock_quantity or quantity_available → quantity_available
    - category or equipment_type → equipment_type
    - Derives availability from quantity
    """
    import json
    spare_parts = []
    
    if not tool_results or 'get-spare-parts' not in tool_results:
        return spare_parts
    
    parts_data = tool_results.get('get-spare-parts')
    
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
            # Otherwise return as-is (wrapped or flat format)
            return data
        return None
    
    def normalize_part(p):
        """Normalize part fields from different MCP response formats"""
        if not isinstance(p, dict) or not p.get('part_id'):
            return None
        
        # Map quantity field (could be stock_quantity or quantity_available)
        qty = p.get('quantity_available') or p.get('stock_quantity') or 0
        
        # Determine availability from quantity or explicit field
        if 'availability' in p:
            availability = p.get('availability')
        else:
            # Calculate from quantity
            availability = 'in_stock' if qty > 0 else 'out_of_stock'
        
        # Map equipment type (could be equipment_type or category)
        equipment_type = p.get('equipment_type') or p.get('category', '')
        
        # Determine criticality (default to medium-high for parts)
        criticality = p.get('criticality', 'high')
        
        return {
            'part_id': p.get('part_id'),
            'part_name': p.get('part_name', ''),
            'equipment_type': equipment_type,
            'availability': availability,
            'quantity_available': qty,
            'lead_time_days': p.get('lead_time_days', 0),
            'unit_cost': p.get('unit_cost', 0),
            'criticality': criticality,
        }
    
    # Parse the response
    parsed_data = parse_mcp_response(parts_data)
    
    if isinstance(parsed_data, dict):
        # Check if it's wrapped format (has 'success' and 'data' fields)
        if 'success' in parsed_data and 'data' in parsed_data:
            if parsed_data.get('success'):
                parts_list = parsed_data.get('data', [])
                if isinstance(parts_list, list):
                    for p in parts_list:
                        normalized = normalize_part(p)
                        if normalized:
                            spare_parts.append(normalized)
        # Check for parts list in parsed data
        elif isinstance(parsed_data.get('parts'), list):
            # Format: {"parts": [...]}
            for p in parsed_data.get('parts', []):
                normalized = normalize_part(p)
                if normalized:
                    spare_parts.append(normalized)
        # Single part object
        elif parsed_data.get('part_id'):
            normalized = normalize_part(parsed_data)
            if normalized:
                spare_parts.append(normalized)
    elif isinstance(parts_data, list):
        for p in parts_data:
            normalized = normalize_part(p)
            if normalized:
                spare_parts.append(normalized)
    
    return spare_parts


# ============================================================================
# API ENDPOINTS - Client-Focused Data
# ============================================================================

@router.get("/fleet-summary")
async def fleet_summary():
    """
    Fleet Summary KPIs - PRODUCTION GRADE WITH REAL MCP DATA
    
    Returns aggregated device health metrics from orchestrator, including:
    - Device health distribution (healthy, warning, critical)
    - Real work orders from MCP tool results
    - Real maintenance schedules from MCP tool results
    - Spare parts availability
    
    - Caches for 5-6 minutes (360s)
    - Option 2: Detects new devices via device list check (< 100ms)
    - Prevents concurrent fetches with request queue
    - Extracts real data from DiagnosisAgent MCP tool results (sequential fetching)
    """
    logger.info("📊 Fleet summary requested")
    
    # Check cache first
    cached = data_cache.get()
    if cached:
        logger.debug("📦 Cache valid, checking device count for new devices...")
        
        # Option 2: Fast device count check (< 100ms) for new device detection
        try:
            devices_list_data = await orchestrator.get("/devices")
            if devices_list_data:
                new_device_count = len(devices_list_data.get('devices', []))
                cached_device_count = cached.get('total_devices')
                
                if new_device_count != cached_device_count:
                    logger.warning(f"🆕 Device count changed: {cached_device_count} → {new_device_count}")
                    logger.info("Invalidating cache and fetching fresh data...")
                    data_cache.invalidate()
                    # Continue to fetch fresh data below
                else:
                    logger.debug(f"✓ Device count unchanged: {cached_device_count}")
                    return cached
        except Exception as e:
            logger.debug(f"⚠️  Device list check failed: {str(e)}, using cache")
            return cached
    
    # Check if fetch already in progress (prevent overlapping requests)
    if fetch_queue.is_fetching():
        logger.debug(f"⏳ Fetch already in progress ({fetch_queue.fetch_type}), returning cache or error")
        if cached:
            return cached
        # If no cache and fetch in progress, return 503 with Retry-After header
        # Frontend will automatically retry with exponential backoff
        logger.info(f"📊 Device fetch in progress, client should retry in 2-3 seconds")
        raise HTTPException(
            status_code=503,
            detail="Loading fleet data... Please wait and retry. Dashboard fetches all devices sequentially (40-50 seconds on first load)."
        )
    
    # Start protected fetch with queue
    fetch_queue.start_fetch('auto')
    
    try:
        # Get device IDs from orchestrator
        devices_list_data = await orchestrator.get("/devices")
        
        if not devices_list_data:
            logger.error("Failed to fetch devices from orchestrator")
            raise HTTPException(status_code=503, detail="Orchestrator unavailable")
        
        device_ids = devices_list_data.get('devices', [])
        logger.debug(f"📋 Fetching {len(device_ids)} devices sequentially")
        
        # Fetch health status and MCP tool results for each device SEQUENTIALLY
        # (Parallel requests overwhelm the diagnosis agent)
        health_statuses = {}
        device_details = {}  # Store full device details for problematic devices
        degradation_scores = []
        equipment_counts = {}
        
        # Aggregate MCP tool results
        all_work_orders = []
        all_maintenance_schedules = []
        all_spare_parts = {}  # Deduplicated by part_id
        all_devices = []  # Full per-device summaries, for /devices to reuse
        
        for device_id in device_ids:
            device_data = await orchestrator.get(f"/devices/{device_id}")
            if device_data:
                status = device_data.get('health_status', 'unknown')
                health_statuses[device_id] = status
                confidence = device_data.get('confidence', 0)
                degradation_scores.append(device_data.get('degradation_score', 0))
                
                equipment_type = device_id.split('-')[0].upper()
                equipment_counts[equipment_type] = equipment_counts.get(equipment_type, 0) + 1
                
                all_devices.append({
                    "device_id": device_id,
                    "equipment_type": equipment_type,
                    "health_status": status,
                    # NOTE: holds raw confidence, not actual degradation - matches
                    # the shape list_devices()'s own fetch loop produces, since
                    # both are passed through the same filter/format code below,
                    # which inverts this into a real degradation_score.
                    "degradation_score": confidence,
                    "timestamp": device_data.get('timestamp', ''),
                    "diagnosis": device_data.get('diagnosis', ''),
                })
                
                # Store details for critical and warning devices
                if status in ['critical', 'warning']:
                    device_details[device_id] = {
                        'device_id': device_id,
                        'health_status': status,
                        'equipment_type': equipment_type,
                        'confidence': confidence,
                        'degradation_score': round(1 - confidence, 3),
                        'diagnosis': device_data.get('diagnosis', ''),
                        'recommendation': device_data.get('recommendation_details', ''),
                        'action': device_data.get('action'),
                        'mcp_tools_used': device_data.get('mcp_tools_used', []),
                    }
                
                # Extract MCP tool results for this device
                tool_results = device_data.get('tool_results', {})
                
                # Extract work orders
                work_orders = extract_work_orders(tool_results)
                for wo in work_orders:
                    all_work_orders.append(wo)
                
                # Extract maintenance schedules
                maintenance_schedules = extract_maintenance_schedules(tool_results)
                for ms in maintenance_schedules:
                    all_maintenance_schedules.append(ms)
                
                # Extract spare parts (deduplicate by part_id)
                spare_parts = extract_spare_parts(tool_results)
                for part in spare_parts:
                    part_id = part.get('part_id')
                    if part_id and part_id not in all_spare_parts:
                        all_spare_parts[part_id] = part
            # Don't mark as unknown - just skip if timeout
        
        # Calculate metrics
        total = len(device_ids)
        responded = len(health_statuses)
        healthy = sum(1 for status in health_statuses.values() if status == 'healthy')
        warning = sum(1 for status in health_statuses.values() if status == 'warning')
        critical = sum(1 for status in health_statuses.values() if status == 'critical')
        
        # Calculate analytics metrics
        avg_degradation = sum(degradation_scores) / len(degradation_scores) if degradation_scores else 0
        avg_remaining_health = 1 - avg_degradation
        
        # If some devices didn't respond, log it. Percentage is based on devices
        # that actually responded, not the full fleet count - otherwise transient
        # per-device fetch failures make fleet health look artificially low.
        if responded < total:
            logger.warning(f"⚠️  Only {responded}/{total} devices responded ({total - responded} timeouts)")
        
        health_percent = round((healthy / responded * 100)) if responded > 0 else 0
        
        logger.info(f"✅ Fleet: {healthy}/{total} healthy, {warning} warning, {critical} critical")
        logger.info(f"📋 Work Orders: {len(all_work_orders)} | Maintenance: {len(all_maintenance_schedules)} | Spare Parts: {len(all_spare_parts)}")
        logger.debug(f"📊 Analytics: {avg_remaining_health:.2%} avg remaining health, {list(equipment_counts.keys())} equipment types")
        
        # Sort problematic devices by criticality (critical first, then warning)
        sorted_problematic = sorted(
            device_details.values(),
            key=lambda d: (0 if d['health_status'] == 'critical' else 1, d['device_id'])
        )
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "total_devices": total,
            "healthy_devices": healthy,
            "warning_devices": warning,
            "critical_devices": critical,
            "fleet_health_percent": health_percent,
            "degradation_trend": "stable",
            "_problematic_devices": sorted_problematic,  # All problematic devices
            # Raw MCP result lists - consumed directly by /work-orders,
            # /maintenance-schedule, /spare-parts (via data_cache.get()) so
            # they don't each independently re-fetch all devices.
            "work_orders": all_work_orders,
            "maintenance_schedules": all_maintenance_schedules,
            "spare_parts": list(all_spare_parts.values()),
            "devices_list": all_devices,
            "_mcp_data": {
                "work_orders": len(all_work_orders),
                "maintenance_schedules": len(all_maintenance_schedules),
                "spare_parts_available": len(all_spare_parts),
                "urgent_work_orders": sum(1 for wo in all_work_orders if wo.get('urgency') in ['immediate', 'urgent']),
            },
            "_analytics": {
                "average_degradation": round(avg_degradation, 3),
                "average_remaining_health": round(avg_remaining_health, 3),
                "total_devices_analyzed": len(device_ids),
                "devices_by_type": equipment_counts,
            },
            "_agent_decisions": build_agent_decisions(
                sorted_problematic,
                total,
                healthy,
            ),
        }
        
        # Cache the result
        data_cache.set(result)
        logger.info(f"💾 Cached fleet data (TTL: 360s, devices: {total}, WOs: {len(all_work_orders)})")
        
        return result
        
    finally:
        fetch_queue.end_fetch()


@router.get("/devices")
async def list_devices(
    equipment_type: Optional[str] = Query(None),
    health_status: Optional[str] = Query(None),
    skip: int = Query(0),
    limit: int = Query(50)
):
    """
    List all devices from orchestrator with real data
    
    Query Parameters:
        - equipment_type: Filter by PUMP, MOTOR, COMPRESSOR, GENERATOR
        - health_status: Filter by healthy, warning, critical
        - skip: Pagination offset
        - limit: Pagination limit (max 100)
    """
    logger.info(f"📋 Devices list requested (skip={skip}, limit={limit})")
    
    # Reuse fleet-summary's cache if available (avoids an independent,
    # uncoordinated full-fleet re-scan on every /devices call).
    cached = data_cache.get()
    if cached and 'devices_list' in cached:
        logger.debug("📦 Using cached devices list")
        devices = list(cached['devices_list'])
    else:
        # Avoid starting a second full-fleet scan while /fleet-summary's is
        # already in progress - wait for it instead.
        if fetch_queue.is_fetching():
            raise HTTPException(
                status_code=503,
                detail="Loading fleet data... Please wait and retry."
            )
        
        # Get device IDs from orchestrator
        devices_list_data = await orchestrator.get("/devices")
        
        if not devices_list_data:
            logger.error("Failed to fetch device list")
            raise HTTPException(status_code=503, detail="Orchestrator unavailable")
        
        device_ids = devices_list_data.get('devices', [])
        
        # Fetch full device data for each device ID
        devices = []
        for device_id in device_ids:
            device_data = await orchestrator.get(f"/devices/{device_id}")
            if device_data:
                # Extract equipment type from device_id (pump-001 → PUMP)
                equipment_type_detected = device_id.split('-')[0].upper()
                
                devices.append({
                    "device_id": device_id,
                    "equipment_type": equipment_type_detected,
                    "health_status": device_data.get('health_status', 'unknown'),
                    "degradation_score": device_data.get('confidence', 0),  # Use confidence as degradation proxy
                    "timestamp": device_data.get('timestamp', ''),
                    "diagnosis": device_data.get('diagnosis', ''),
                })
        
        logger.debug(f"✅ Fetched {len(devices)} full device records")
    
    # Apply filters
    if equipment_type:
        devices = [d for d in devices if d['equipment_type'].upper() == equipment_type.upper()]
        logger.debug(f"Filtered by type: {len(devices)} devices")
    
    if health_status:
        devices = [d for d in devices if d['health_status'] == health_status]
        logger.debug(f"Filtered by status: {len(devices)} devices")
    
    # Apply pagination
    total = len(devices)
    paginated = devices[skip:skip + limit]
    
    # Format for dashboard (client-focused)
    formatted_devices = [
        {
            "device_id": d['device_id'],
            "equipment_type": d['equipment_type'],
            "health_status": d['health_status'],
            "degradation_score": round(1 - d['degradation_score'], 3),  # Invert confidence to degradation
            "last_timestamp": d['timestamp'],
            "location": f"Equipment {d['device_id']}",
            "diagnosis": d['diagnosis'],
        }
        for d in paginated
    ]
    
    logger.info(f"✅ Returning {len(formatted_devices)} devices (total: {total})")
    
    return {
        "devices": formatted_devices,
        "total": total,
        "skip": skip,
        "limit": limit,
        "returned": len(formatted_devices),
    }


@router.get("/devices/{device_id}")
async def device_detail(device_id: str):
    """
    Get detailed information for a specific device
    
    Includes:
    - Current sensor readings
    - Health status and degradation
    - Agent analysis & insights
    - Maintenance recommendations
    """
    logger.info(f"🔍 Device detail requested: {device_id}")
    
    # Get device from orchestrator
    device_data = await orchestrator.get(f"/devices/{device_id}")
    
    if not device_data:
        logger.error(f"Device {device_id} not found")
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    # Get device summary with history
    device_summary = await orchestrator.get(f"/devices/{device_id}/summary")
    
    logger.info(f"✅ Device detail retrieved: {device_id}")
    
    return {
        "device_id": device_id,
        "current": device_data,
        "summary": device_summary or {},
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/cache-clear")
async def hard_refresh_cache():
    """
    Hard refresh endpoint - clears cache and returns fresh data
    
    Used by the Hard Refresh button to force immediate data fetch
    bypassing the auto-refresh mechanism and request queue.
    Returns fresh data directly with real MCP tool results aggregated.
    """
    logger.info("🔄 Hard refresh requested - clearing cache")
    
    # Cancel any in-progress auto-fetch if possible
    if fetch_queue.is_fetching() and fetch_queue.fetch_type == 'auto':
        fetch_queue.cancel_fetch()
        logger.info("Cancelled in-progress auto-fetch")
    
    # Clear cache
    data_cache.invalidate()
    logger.info("✓ Cache cleared")
    
    # Start manual (hard) fetch with queue protection
    fetch_queue.start_fetch('manual')
    
    try:
        devices_list_data = await orchestrator.get("/devices")
        if not devices_list_data:
            raise HTTPException(status_code=503, detail="Orchestrator unavailable")
        
        device_ids = devices_list_data.get('devices', [])
        logger.info(f"🔄 Hard refresh: fetching {len(device_ids)} devices")
        
        health_statuses = {}
        degradation_scores = []
        equipment_counts = {}
        
        # Aggregate MCP tool results
        all_work_orders = []
        all_maintenance_schedules = []
        all_spare_parts = {}
        
        for device_id in device_ids:
            device_data = await orchestrator.get(f"/devices/{device_id}")
            if device_data:
                health_statuses[device_id] = device_data.get('health_status', 'unknown')
                degradation_scores.append(device_data.get('degradation_score', 0))
                equipment_type = device_id.split('-')[0].upper()
                equipment_counts[equipment_type] = equipment_counts.get(equipment_type, 0) + 1
                
                # Extract MCP tool results
                tool_results = device_data.get('tool_results', {})
                
                # Extract and aggregate all tool results
                work_orders = extract_work_orders(tool_results)
                all_work_orders.extend(work_orders)
                
                maintenance_schedules = extract_maintenance_schedules(tool_results)
                all_maintenance_schedules.extend(maintenance_schedules)
                
                spare_parts = extract_spare_parts(tool_results)
                for part in spare_parts:
                    part_id = part.get('part_id')
                    if part_id and part_id not in all_spare_parts:
                        all_spare_parts[part_id] = part
        
        total = len(device_ids)
        responded = len(health_statuses)
        healthy = sum(1 for status in health_statuses.values() if status == 'healthy')
        warning = sum(1 for status in health_statuses.values() if status == 'warning')
        critical = sum(1 for status in health_statuses.values() if status == 'critical')
        
        if responded < total:
            logger.warning(f"⚠️  Only {responded}/{total} devices responded ({total - responded} timeouts)")
        
        avg_degradation = sum(degradation_scores) / len(degradation_scores) if degradation_scores else 0
        avg_remaining_health = 1 - avg_degradation
        health_percent = round((healthy / responded * 100)) if responded > 0 else 0
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "total_devices": total,
            "healthy_devices": healthy,
            "warning_devices": warning,
            "critical_devices": critical,
            "fleet_health_percent": health_percent,
            "degradation_trend": "stable",
            "_mcp_data": {
                "work_orders": len(all_work_orders),
                "maintenance_schedules": len(all_maintenance_schedules),
                "spare_parts_available": len(all_spare_parts),
                "urgent_work_orders": sum(1 for wo in all_work_orders if wo.get('urgency') in ['immediate', 'urgent']),
            },
            "_analytics": {
                "average_degradation": round(avg_degradation, 3),
                "average_remaining_health": round(avg_remaining_health, 3),
                "total_devices_analyzed": len(device_ids),
                "devices_by_type": equipment_counts,
            },
            "_source": "fresh"
        }
        
        data_cache.set(result)
        logger.info(f"✅ Hard refresh complete: {healthy}/{total} healthy, {warning} warning, {critical} critical (WOs: {len(all_work_orders)})")
        
        return result
        
    finally:
        fetch_queue.end_fetch()


@router.get("/alerts")
async def get_alerts(severity: Optional[str] = Query(None)):
    """
    Get active alerts and critical items
    
    Query Parameters:
        - severity: Filter by critical, high, medium, low
    
    Alert data derived from:
    - Devices with health_status = 'critical' or 'warning'
    - Agent analysis from orchestrator
    """
    logger.info("🚨 Alerts requested")
    
    # Get all device IDs
    devices_list_data = await orchestrator.get("/devices")
    
    if not devices_list_data:
        raise HTTPException(status_code=503, detail="Orchestrator unavailable")
    
    device_ids = devices_list_data.get('devices', [])
    
    # Fetch health status and generate alerts
    alerts = []
    
    for device_id in device_ids:
        device_data = await orchestrator.get(f"/devices/{device_id}")
        
        if not device_data:
            continue
        
        state = device_data.get('health_status', 'unknown')
        
        if state == 'critical':
            alerts.append({
                "id": f"alert-{device_id}-critical",
                "device_id": device_id,
                "severity": "critical",
                "title": f"Critical: {device_id} requires immediate attention",
                "description": device_data.get('diagnosis', 'Device in critical state'),
                "timestamp": device_data.get('timestamp'),
                "action_required": True,
            })
        elif state == 'warning':
            alerts.append({
                "id": f"alert-{device_id}-warning",
                "device_id": device_id,
                "severity": "high",
                "title": f"Warning: {device_id} anomaly detected",
                "description": device_data.get('diagnosis', 'Device showing warning signs'),
                "timestamp": device_data.get('timestamp'),
                "action_required": False,
            })
    
    # Apply severity filter
    if severity:
        severity_map = {'critical': 'critical', 'high': 'high', 'medium': 'medium', 'low': 'low'}
        target_severity = severity_map.get(severity.lower())
        if target_severity:
            alerts = [a for a in alerts if a['severity'] == target_severity]
            logger.debug(f"Filtered alerts by severity: {len(alerts)}")
    
    logger.info(f"✅ {len(alerts)} alerts returned")
    
    return {
        "alerts": alerts,
        "total": len(alerts),
        "critical_count": sum(1 for a in alerts if a['severity'] == 'critical'),
        "high_count": sum(1 for a in alerts if a['severity'] == 'high'),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/maintenance/schedule")
async def maintenance_schedule():
    """
    Maintenance schedule and work orders
    
    Derived from device health states and agent recommendations.
    Shows predicted maintenance needs based on agent analysis.
    
    DEPRECATED: Use /maintenance-schedule endpoint instead for real MCP data.
    """
    logger.info("🔧 Maintenance schedule requested (legacy endpoint)")
    
    # Get all device IDs
    devices_list_data = await orchestrator.get("/devices")
    
    if not devices_list_data:
        raise HTTPException(status_code=503, detail="Orchestrator unavailable")
    
    device_ids = devices_list_data.get('devices', [])
    
    # Generate maintenance items based on health status
    maintenance_items = []
    
    for device_id in device_ids:
        device_data = await orchestrator.get(f"/devices/{device_id}")
        
        if not device_data:
            continue
        
        health_status = device_data.get('health_status', 'healthy')
        
        # Schedule maintenance for warning or critical devices
        if health_status in ['warning', 'critical']:
            priority = 'urgent' if health_status == 'critical' else 'scheduled'
            maintenance_items.append({
                "device_id": device_id,
                "equipment_type": device_id.split('-')[0].upper(),
                "priority": priority,
                "health_status": health_status,
                "recommended_action": device_data.get('action', 'MONITOR_ONLY'),
                "diagnosis": device_data.get('diagnosis', ''),
                "estimated_duration": "2-4 hours",
                "last_analysis": device_data.get('timestamp'),
            })
    
    logger.info(f"✅ {len(maintenance_items)} maintenance items identified")
    
    return {
        "work_orders": len([m for m in maintenance_items if m['priority'] == 'urgent']),
        "scheduled_maintenance": len([m for m in maintenance_items if m['priority'] == 'scheduled']),
        "items": maintenance_items,
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# NEW ENDPOINTS - Real MCP Tool Data
# ============================================================================

@router.get("/maintenance-schedule")
async def get_maintenance_schedules():
    """
    Real maintenance schedules from MCP tool results
    
    Fetches data from DiagnosisAgent's schedule-maintenance tool
    Uses cached data from fleet-summary for performance (360s TTL)
    
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
    
    # Check if we have cached fleet data with maintenance schedules already extracted
    cached = data_cache.get()
    if cached and 'maintenance_schedules' in cached:
        all_schedules = cached.get('maintenance_schedules', [])
        logger.debug(f"📦 Using cached maintenance schedules: {len(all_schedules)} schedules from cache")
    else:
        # If no cache, fetch from orchestrator
        logger.debug("💾 No cache available, fetching fresh data...")
        
        # Avoid starting a second full-fleet scan while /fleet-summary's is
        # already in progress - wait for it instead (it populates this same
        # cache with maintenance_schedules on completion).
        if fetch_queue.is_fetching():
            raise HTTPException(
                status_code=503,
                detail="Loading fleet data... Please wait and retry."
            )
        
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


@router.get("/work-orders")
async def get_work_orders(status: Optional[str] = Query(None)):
    """
    Real work orders from MCP tool results
    
    Fetches data from DiagnosisAgent's create-work-order tool
    Uses cached data from fleet-summary for performance (360s TTL)
    
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
    
    # Check if we have cached fleet data with work orders already extracted
    cached = data_cache.get()
    if cached and 'work_orders' in cached:
        all_work_orders = cached.get('work_orders', [])
        logger.debug(f"📦 Using cached work orders: {len(all_work_orders)} orders from cache")
    else:
        # If no cache, fetch from orchestrator
        logger.debug("💾 No cache available, fetching fresh data...")
        
        # Avoid starting a second full-fleet scan while /fleet-summary's is
        # already in progress - wait for it instead (it populates this same
        # cache with work_orders on completion).
        if fetch_queue.is_fetching():
            raise HTTPException(
                status_code=503,
                detail="Loading fleet data... Please wait and retry."
            )
        
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


@router.get("/spare-parts")
async def get_spare_parts(availability: Optional[str] = Query(None)):
    """
    Spare parts availability from MCP tool results
    
    Fetches data from DiagnosisAgent's get-spare-parts tool
    Uses cached data from fleet-summary for performance (360s TTL)
    Deduplicates parts (if same part requested across multiple devices)
    
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
    
    # Check if we have cached fleet data with spare parts already extracted
    cached = data_cache.get()
    if cached and 'spare_parts' in cached:
        all_parts = cached.get('spare_parts', [])
        logger.debug(f"📦 Using cached spare parts: {len(all_parts)} parts from cache")
    else:
        # If no cache, fetch from orchestrator
        logger.debug("💾 No cache available, fetching fresh data...")
        
        # Avoid starting a second full-fleet scan while /fleet-summary's is
        # already in progress - wait for it instead (it populates this same
        # cache with spare_parts on completion).
        if fetch_queue.is_fetching():
            raise HTTPException(
                status_code=503,
                detail="Loading fleet data... Please wait and retry."
            )
        
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


@router.get("/analytics/overview")
async def analytics_overview():
    """
    Analytics overview with trends and metrics
    Uses cached data from fleet-summary to ensure consistency
    """
    logger.info("📈 Analytics overview requested")
    
    # Try to use cached fleet data first
    cached = data_cache.get()
    if cached and "_analytics" in cached:
        logger.debug("📦 Using cached analytics data")
        # Return only the analytics portion
        return {
            "average_degradation": cached["_analytics"]["average_degradation"],
            "average_remaining_health": cached["_analytics"]["average_remaining_health"],
            "total_devices_analyzed": cached["_analytics"]["total_devices_analyzed"],
            "devices_by_type": cached["_analytics"]["devices_by_type"],
            "trend": "stable",
            "timestamp": cached["timestamp"],
        }
    
    # Fallback: fetch fresh data if cache not available
    logger.debug("⚠️  No cached analytics, fetching fresh data")
    
    # Avoid starting a second full-fleet scan while /fleet-summary's is
    # already in progress - wait for it instead (it populates this same
    # cache with _analytics on completion).
    if fetch_queue.is_fetching():
        raise HTTPException(
            status_code=503,
            detail="Loading fleet data... Please wait and retry."
        )
    
    # Get all device IDs
    devices_list_data = await orchestrator.get("/devices")
    
    if not devices_list_data:
        raise HTTPException(status_code=503, detail="Orchestrator unavailable")
    
    device_ids = devices_list_data.get('devices', [])
    
    # Fetch HealthAgent degradation scores for analytics
    degradation_scores = []
    equipment_counts = {}
    
    for device_id in device_ids:
        device_data = await orchestrator.get(f"/devices/{device_id}")
        
        if device_data:
            degradation_scores.append(device_data.get('degradation_score', 0))
            
            equipment_type = device_id.split('-')[0].upper()
            equipment_counts[equipment_type] = equipment_counts.get(equipment_type, 0) + 1
    
    avg_degradation = sum(degradation_scores) / len(degradation_scores) if degradation_scores else 0
    avg_remaining_health = 1 - avg_degradation
    
    logger.info(f"✅ Analytics: avg remaining health {avg_remaining_health:.2%}, equipment types: {equipment_counts}")
    
    return {
        "average_degradation": round(avg_degradation, 3),
        "average_remaining_health": round(avg_remaining_health, 3),
        "total_devices_analyzed": len(device_ids),
        "devices_by_type": equipment_counts,
        "trend": "stable",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/analytics/trends")
async def analytics_trends(period: str = Query("7d")):
    """
    Detailed trends over time
    
    Query Parameters:
        - period: 1d, 7d, 30d, 90d
    """
    logger.info(f"📊 Trends requested for period: {period}")
    
    return {
        "period": period,
        "data_points": [
            {"date": (datetime.now() - timedelta(days=i)).isoformat(), "value": 85 - i*2}
            for i in range(7)
        ],
        "trend": "declining",  # Device health trending down
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/status")
async def service_status():
    """
    Dashboard service status including orchestrator connectivity
    """
    logger.info("🏥 Status check requested")
    
    # Check orchestrator connectivity
    health_check = await orchestrator.get("/health")
    orchestrator_ok = health_check is not None
    
    status_msg = "✅ All systems operational" if orchestrator_ok else "⚠️  Orchestrator unavailable"
    logger.info(status_msg)
    
    return {
        "status": "healthy" if orchestrator_ok else "degraded",
        "dashboard": {
            "version": "2.0.0",
            "port": settings.DASHBOARD_PORT,
        },
        "orchestrator": {
            "url": settings.ORCHESTRATOR_URL,
            "connected": orchestrator_ok,
            "response": health_check or {}
        },
        "timestamp": datetime.now().isoformat(),
    }

# ============================================================================
# SUSTAINABILITY - append this block to the END of src/dashboard/routes/api.py
# ============================================================================

def extract_sustainability(device_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pull SustainabilityAgent fields out of an orchestrator device payload.

    Returns None when the agent did not run for this device (healthy devices,
    and critical devices where the agent is deliberately bypassed).
    """
    if not device_data:
        return None
    if not device_data.get('sust_recommendation'):
        return None

    return {
        'recommendation': device_data.get('sust_recommendation'),
        'explanation': device_data.get('sust_explanation', ''),
        'co2_reason': device_data.get('sust_co2', ''),
        'cost_reason': device_data.get('sust_cost', ''),
        'risk_level': device_data.get('sust_risk_level', 'Unknown'),
        'scheduled_date': device_data.get('sust_scheduled_date'),
        'options': device_data.get('sust_options', []),
        'grid': device_data.get('sust_grid') or {},
        'breakeven': device_data.get('sust_breakeven') or {},
    }


def _co2_savings_from_options(options: List[Dict[str, Any]]) -> Dict[str, float]:
    """CO2 and cost avoided versus the worst eligible alternative.

    The agent already reports savings in prose. This recomputes them as numbers
    so the dashboard can total them across the fleet.
    """
    eligible = [o for o in options if o.get('status') == 'eligible']
    if len(eligible) < 2:
        return {'co2_avoided_kg': 0.0, 'cost_avoided_eur': 0.0}

    chosen = eligible[0]  # agent returns them sorted, best first
    worst = max(eligible, key=lambda o: o.get('total_co2_kg', 0))
    return {
        'co2_avoided_kg': round(
            worst.get('total_co2_kg', 0) - chosen.get('total_co2_kg', 0), 1
        ),
        'cost_avoided_eur': round(
            worst.get('total_cost_eur', 0) - chosen.get('total_cost_eur', 0), 0
        ),
    }


@router.get("/sustainability")
async def sustainability_overview():
    """
    Sustainability Agent results across the fleet.

    Returns per-device recommendations, fleet totals, and pie-chart-ready
    breakdowns of recommendation mix and risk level.

    Devices where the agent did not run (healthy, or critical/urgent where it
    is deliberately bypassed) are counted separately rather than hidden -- the
    bypass count is evidence the safety guardrail is working.
    """
    logger.info("Sustainability overview requested")

    devices_list_data = await orchestrator.get("/devices")
    if not devices_list_data:
        raise HTTPException(status_code=503, detail="Orchestrator unavailable")

    device_ids = devices_list_data.get('devices', [])

    per_device = []
    bypassed = []
    total_co2_avoided = 0.0
    total_cost_avoided = 0.0
    grid_readings = []

    recommendation_counts: Dict[str, int] = {}
    risk_counts: Dict[str, int] = {}

    for device_id in device_ids:
        device_data = await orchestrator.get(f"/devices/{device_id}")
        if not device_data:
            continue

        sust = extract_sustainability(device_data)

        if sust is None:
            bypassed.append({
                'device_id': device_id,
                'health_status': device_data.get('health_status', 'unknown'),
                'action': device_data.get('action'),
                'reason': (
                    'Critical device - sustainability optimisation bypassed'
                    if device_data.get('health_status') == 'critical'
                    else 'Healthy device - no maintenance decision required'
                ),
            })
            continue

        savings = _co2_savings_from_options(sust['options'])
        total_co2_avoided += savings['co2_avoided_kg']
        total_cost_avoided += savings['cost_avoided_eur']

        rec = sust['recommendation']
        recommendation_counts[rec] = recommendation_counts.get(rec, 0) + 1
        risk = sust['risk_level']
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

        if sust['grid'].get('g_per_kwh'):
            grid_readings.append(sust['grid'])

        per_device.append({
            'device_id': device_id,
            'equipment_type': device_id.split('-')[0].upper(),
            'health_status': device_data.get('health_status'),
            'diagnosis': device_data.get('diagnosis', ''),
            **sust,
            **savings,
        })

    # Sort: highest carbon saving first -- the headline devices lead the table
    per_device.sort(key=lambda d: d.get('co2_avoided_kg', 0), reverse=True)

    grid = grid_readings[0] if grid_readings else {}

    logger.info(
        f"Sustainability: {len(per_device)} optimised, {len(bypassed)} bypassed, "
        f"{total_co2_avoided:.1f} kg CO2e avoided"
    )

    return {
        'devices': per_device,
        'bypassed': bypassed,
        'totals': {
            'devices_optimised': len(per_device),
            'devices_bypassed': len(bypassed),
            'co2_avoided_kg': round(total_co2_avoided, 1),
            'cost_avoided_eur': round(total_cost_avoided, 0),
            'equivalent_van_km_avoided': round(total_co2_avoided / 0.24, 0),
        },
        # Pie-chart ready
        'recommendation_mix': [
            {'label': k.replace('_', ' ').title(), 'value': v}
            for k, v in sorted(recommendation_counts.items())
        ],
        'risk_mix': [
            {'label': k, 'value': v}
            for k, v in sorted(risk_counts.items())
        ],
        'grid': {
            'zone': grid.get('zone', 'FI'),
            'g_per_kwh': grid.get('g_per_kwh'),
            'is_live': grid.get('is_live', False),
            'source': grid.get('source', ''),
            'label': (
                f"{grid.get('g_per_kwh')} gCO2/kWh "
                f"({'live' if grid.get('is_live') else 'annual average'})"
                if grid.get('g_per_kwh') else 'unavailable'
            ),
        },
        'timestamp': datetime.now().isoformat(),
    }


@router.get("/sustainability/{device_id}")
async def sustainability_detail(device_id: str):
    """Full option comparison for one device, including rejected options.

    The rejected options are the point: showing what the agent refused to do,
    and why, is most of the explainability story.
    """
    device_data = await orchestrator.get(f"/devices/{device_id}")
    if not device_data:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

    sust = extract_sustainability(device_data)
    if sust is None:
        return {
            'device_id': device_id,
            'optimised': False,
            'reason': (
                'Critical device - sustainability optimisation bypassed; '
                'urgent repair proceeds unchanged'
                if device_data.get('health_status') == 'critical'
                else 'Device healthy - no maintenance decision required'
            ),
            'health_status': device_data.get('health_status'),
            'action': device_data.get('action'),
        }

    return {
        'device_id': device_id,
        'optimised': True,
        'diagnosis': device_data.get('diagnosis', ''),
        **sust,
        **_co2_savings_from_options(sust['options']),
        'timestamp': datetime.now().isoformat(),
    }
