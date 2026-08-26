/**
 * API response types for the Dashboard_Service endpoints.
 *
 * Nullable/optional fields use `T | null | undefined` to force call sites
 * through `numberOr0` / `textOr` before rendering.
 *
 * Status-like fields are typed as `HealthStatus | string` (or similar unions)
 * so the domain layer can narrow them safely while accepting unknown values
 * from the API without a runtime crash.
 */

// ---------------------------------------------------------------------------
// Status unions
// ---------------------------------------------------------------------------

export type HealthStatus = 'healthy' | 'warning' | 'critical';
export type AlertSeverity = 'critical' | 'high';
export type Priority = 'urgent' | 'scheduled';
export type Urgency = 'immediate' | 'urgent' | 'scheduled';
export type Availability = 'in_stock' | 'on_order' | 'out_of_stock';
export type Criticality = 'critical' | 'high' | 'medium' | 'low';

// ---------------------------------------------------------------------------
// Fleet Summary
// ---------------------------------------------------------------------------

export interface AnalyticsSnapshot {
  average_confidence: number | null | undefined;
  average_degradation: number | null | undefined;
  total_devices_analyzed: number | null | undefined;
  devices_by_type: Record<string, number> | null | undefined;
}

export interface ProblematicDevice {
  device_id: string | null | undefined;
  equipment_type: string | null | undefined;
  health_status: HealthStatus | string;
  degradation_score: number | null | undefined;
}

export interface FleetSummary {
  healthy_devices: number | null | undefined;
  warning_devices: number | null | undefined;
  critical_devices: number | null | undefined;
  total_devices: number | null | undefined;
  fleet_health_percent: number | null | undefined;
  _problematic_devices: ProblematicDevice[];
  _analytics?: AnalyticsSnapshot;
}

// ---------------------------------------------------------------------------
// Devices
// ---------------------------------------------------------------------------

export interface Device {
  device_id: string | null | undefined;
  equipment_type: string | null | undefined;
  health_status: HealthStatus | string;
  degradation_score: number | null | undefined;
  memory_context?: DeviceMemoryContext;
}

// ---------------------------------------------------------------------------
// Memory Context (for device memory indicators)
// ---------------------------------------------------------------------------

export interface DeviceMemoryContext {
  history_count: number;
  trend: 'improving' | 'stable' | 'worsening' | null;
  is_recurring: boolean;
}

export interface DevicesResponse {
  devices: Device[];
}

export interface DeviceQueryParams {
  equipment_type?: string;
  health_status?: string;
  skip?: number;
  limit?: number;
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export interface Alert {
  title: string | null | undefined;
  severity: AlertSeverity | string;
  description: string | null | undefined;
  device_id: string | null | undefined;
}

export interface AlertsResponse {
  alerts: Alert[];
}

// ---------------------------------------------------------------------------
// Maintenance Schedule
// ---------------------------------------------------------------------------

export interface MaintenanceSchedule {
  device_id: string | null | undefined;
  priority: Priority | string;
  reason: string | null | undefined;
  start_date: string | null | undefined;
  duration_hours: number | null | undefined;
  estimated_cost: number | null | undefined;
  parts_needed: string[] | null | undefined;
}

export interface MaintenanceScheduleResponse {
  schedules: MaintenanceSchedule[];
  by_priority: {
    urgent: number | null | undefined;
    scheduled: number | null | undefined;
  };
  total_estimated_cost: number | null | undefined;
}

// ---------------------------------------------------------------------------
// Work Orders
// ---------------------------------------------------------------------------

export interface WorkOrder {
  work_order_id: string | null | undefined;
  device_id: string | null | undefined;
  urgency: Urgency | string;
  description: string | null | undefined;
  assigned_to: string | null | undefined;
  estimated_hours: number | null | undefined;
  created_at: string | null | undefined;
}

export interface WorkOrdersResponse {
  work_orders: WorkOrder[];
  total: number | null | undefined;
  by_urgency: {
    immediate: number | null | undefined;
    urgent: number | null | undefined;
  };
  total_estimated_hours: number | null | undefined;
}

// ---------------------------------------------------------------------------
// Spare Parts
// ---------------------------------------------------------------------------

export interface SparePart {
  part_name: string | null | undefined;
  availability: Availability | string;
  equipment_type: string | null | undefined;
  quantity_available: number | null | undefined;
  lead_time_days: number | null | undefined;
  unit_cost: number | null | undefined;
  criticality: Criticality | string;
}

export interface SparePartsResponse {
  parts: SparePart[];
  total: number | null | undefined;
  by_availability: {
    in_stock: number | null | undefined;
    on_order: number | null | undefined;
  };
  critical_parts_unavailable: number | null | undefined;
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export interface AnalyticsOverview {
  average_confidence: number | null | undefined;
  average_degradation: number | null | undefined;
  total_devices_analyzed: number | null | undefined;
  devices_by_type: Record<string, number> | null | undefined;
}

// ---------------------------------------------------------------------------
// Health History (for analytics chart)
// ---------------------------------------------------------------------------

export interface HealthHistoryDataPoint {
  timestamp: string;
  health_percent: number;
}

export interface HealthHistoryDevice {
  device_id: string;
  equipment_type: string;
  data_points: HealthHistoryDataPoint[];
}

export interface HealthHistoryResponse {
  devices: HealthHistoryDevice[];
  total_devices: number;
}

// ---------------------------------------------------------------------------
// Service Status
// ---------------------------------------------------------------------------

export interface ServiceStatus {
  dashboard: {
    version: string | null | undefined;
  };
}
