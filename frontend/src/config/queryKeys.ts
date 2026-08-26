import type { DeviceQueryParams } from '../api/types';

export type TabId = 'overview' | 'devices' | 'alerts' | 'maintenance' | 'analytics';

export const queryKeys = {
  fleetSummary: ['fleet-summary'] as const,
  devices: (p: DeviceQueryParams = {}) => ['devices', p] as const,
  alerts: ['alerts'] as const,
  maintenanceSchedule: ['maintenance-schedule'] as const,
  workOrders: ['work-orders'] as const,
  spareParts: ['spare-parts'] as const,
  analyticsOverview: ['analytics-overview'] as const,
  healthHistory: ['health-history'] as const,
  status: ['status'] as const,
};

export const ALL_QUERY_KEYS = [
  queryKeys.fleetSummary,
  queryKeys.alerts,
  queryKeys.maintenanceSchedule,
  queryKeys.workOrders,
  queryKeys.spareParts,
  queryKeys.analyticsOverview,
  queryKeys.healthHistory,
  queryKeys.status,
];

export const TAB_QUERY_KEYS: Record<TabId, readonly (readonly string[])[]> = {
  overview: [queryKeys.fleetSummary],
  devices: [['devices']],
  alerts: [queryKeys.alerts],
  maintenance: [queryKeys.maintenanceSchedule, queryKeys.workOrders, queryKeys.spareParts],
  analytics: [queryKeys.analyticsOverview, queryKeys.healthHistory, queryKeys.fleetSummary],
};
