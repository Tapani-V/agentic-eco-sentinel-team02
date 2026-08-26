import { fetchJson } from './client';
import type {
  FleetSummary,
  DevicesResponse,
  DeviceQueryParams,
  AlertsResponse,
  MaintenanceScheduleResponse,
  WorkOrdersResponse,
  SparePartsResponse,
  AnalyticsOverview,
  HealthHistoryResponse,
  ServiceStatus,
} from './types';

export function getFleetSummary(): Promise<FleetSummary> {
  return fetchJson<FleetSummary>('/fleet-summary');
}

export function getDevices(params?: DeviceQueryParams): Promise<DevicesResponse> {
  return fetchJson<DevicesResponse>('/devices', params as Record<string, string | number | undefined>);
}

export function getAlerts(params?: { skip?: number; limit?: number }): Promise<AlertsResponse> {
  return fetchJson<AlertsResponse>('/alerts', params);
}

export function getMaintenanceSchedule(): Promise<MaintenanceScheduleResponse> {
  return fetchJson<MaintenanceScheduleResponse>('/maintenance-schedule');
}

export function getWorkOrders(params?: { skip?: number; limit?: number }): Promise<WorkOrdersResponse> {
  return fetchJson<WorkOrdersResponse>('/work-orders', params);
}

export function getSpareParts(params?: { skip?: number; limit?: number }): Promise<SparePartsResponse> {
  return fetchJson<SparePartsResponse>('/spare-parts', params);
}

export function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  return fetchJson<AnalyticsOverview>('/analytics/overview');
}

export function getHealthHistory(): Promise<HealthHistoryResponse> {
  return fetchJson<HealthHistoryResponse>('/analytics/health-history');
}

export function getStatus(): Promise<ServiceStatus> {
  return fetchJson<ServiceStatus>('/status');
}

export function getCacheClear(): Promise<FleetSummary> {
  return fetchJson<FleetSummary>('/cache-clear');
}
