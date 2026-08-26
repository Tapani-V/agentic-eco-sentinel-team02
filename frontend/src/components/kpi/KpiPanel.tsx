import React from 'react';
import { useFleetSummary } from '../../queries';
import { numberOr0 } from '../../domain/format';
import { Spinner } from '../common/Spinner';
import { KpiCard } from './KpiCard';

/**
 * Four KPI cards showing fleet health summary metrics.
 * While data is unavailable, each value slot renders a spinner.
 */
export function KpiPanel(): React.JSX.Element {
  const { data } = useFleetSummary();

  const loading = <Spinner size="sm" label="Loading KPI data…" />;

  return (
    <div className="kpi-grid">
      <KpiCard
        label="Fleet Health"
        value={data ? `${numberOr0(data.healthy_devices)} (${numberOr0(data.fleet_health_percent)}%)` : loading}
        subtext="Devices Healthy"
        variant="healthy"
      />
      <KpiCard
        label="Warning Devices"
        value={data ? String(numberOr0(data.warning_devices)) : loading}
        subtext="Needs Attention"
        variant="warning"
      />
      <KpiCard
        label="Critical Devices"
        value={data ? String(numberOr0(data.critical_devices)) : loading}
        subtext="Urgent Action"
        variant="critical"
      />
      <KpiCard
        label="Total Devices"
        value={data ? String(numberOr0(data.total_devices)) : loading}
        subtext="In Fleet"
        variant="default"
      />
    </div>
  );
}
