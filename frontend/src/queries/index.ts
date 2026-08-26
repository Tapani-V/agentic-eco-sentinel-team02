import { useQuery } from '@tanstack/react-query';
import {
  getFleetSummary,
  getDevices,
  getAlerts,
  getMaintenanceSchedule,
  getWorkOrders,
  getSpareParts,
  getAnalyticsOverview,
  getHealthHistory,
  getStatus,
} from '../api/endpoints';
import type { DeviceQueryParams } from '../api/types';
import { queryKeys } from '../config/queryKeys';
import { REFRESH_INTERVALS_MS } from '../config/intervals';

export function useFleetSummary() {
  return useQuery({
    queryKey: queryKeys.fleetSummary,
    queryFn: getFleetSummary,
    refetchInterval: REFRESH_INTERVALS_MS.fleetSummary,
  });
}

export function useDevices(params?: DeviceQueryParams) {
  return useQuery({
    queryKey: queryKeys.devices(params),
    queryFn: () => getDevices(params),
    refetchInterval: REFRESH_INTERVALS_MS.devices,
  });
}

export function useAlerts() {
  return useQuery({
    queryKey: queryKeys.alerts,
    queryFn: () => getAlerts(),
    refetchInterval: REFRESH_INTERVALS_MS.alerts,
  });
}

export function useMaintenanceSchedule() {
  return useQuery({
    queryKey: queryKeys.maintenanceSchedule,
    queryFn: getMaintenanceSchedule,
    refetchInterval: REFRESH_INTERVALS_MS.maintenance,
  });
}

export function useWorkOrders() {
  return useQuery({
    queryKey: queryKeys.workOrders,
    queryFn: () => getWorkOrders(),
    refetchInterval: REFRESH_INTERVALS_MS.maintenance,
  });
}

export function useSpareParts() {
  return useQuery({
    queryKey: queryKeys.spareParts,
    queryFn: () => getSpareParts(),
    refetchInterval: REFRESH_INTERVALS_MS.maintenance,
  });
}

export function useAnalyticsOverview(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.analyticsOverview,
    queryFn: getAnalyticsOverview,
    refetchInterval: REFRESH_INTERVALS_MS.analytics,
    enabled: options?.enabled ?? true,
  });
}

export function useHealthHistory() {
  return useQuery({
    queryKey: queryKeys.healthHistory,
    queryFn: getHealthHistory,
    refetchInterval: REFRESH_INTERVALS_MS.healthHistory,
  });
}

export function useStatus() {
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: getStatus,
    refetchInterval: REFRESH_INTERVALS_MS.status,
  });
}
