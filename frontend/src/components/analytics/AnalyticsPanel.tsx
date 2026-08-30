import React from 'react';
import { useFleetSummary, useAnalyticsOverview } from '../../queries';
import { Spinner, ErrorState, useAnnouncer } from '../common';
import { formatPercent1, numberOr0 } from '../../domain/format';
import { ANALYTICS_CACHE_MAX_AGE_MS } from '../../config/intervals';
import { useAnnounceOnLoad } from '../../hooks/useAnnounceOnLoad';
import { AgentDecisionOverview } from './AgentDecisionOverview';
import type { AnalyticsOverview, AnalyticsSnapshot } from '../../api/types';
import type { UseQueryResult } from '@tanstack/react-query';

// ---------------------------------------------------------------------------
// Source-selection hook
// ---------------------------------------------------------------------------

interface AnalyticsResult {
  data: AnalyticsSnapshot | AnalyticsOverview | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

/**
 * Prefers the embedded `_analytics` snapshot from the fleet-summary cache
 * while the data is fresh (within ANALYTICS_CACHE_MAX_AGE_MS). Falls back
 * to the dedicated analytics-overview endpoint otherwise.
 *
 * Replaces the legacy `window.lastFleetSummary` global approach.
 */
export function useAnalytics(): AnalyticsResult {
  const fleet = useFleetSummary();
  const fresh =
    fleet.data !== undefined &&
    Date.now() - (fleet.dataUpdatedAt ?? 0) < ANALYTICS_CACHE_MAX_AGE_MS;
  const embedded = fresh ? fleet.data?._analytics : undefined;
  const overview = useAnalyticsOverview({ enabled: !embedded });

  const data = embedded ?? overview.data;

  return {
    data,
    isLoading: !data && (fleet.isFetching || overview.isFetching),
    error: (overview.error as Error | null),
    refetch: () => {
      void fleet.refetch();
      void overview.refetch();
    },
  };
}

// ---------------------------------------------------------------------------
// Panel component
// ---------------------------------------------------------------------------

/** Analytics panel displaying confidence, degradation, total devices, and equipment distribution. */
export function AnalyticsPanel(): React.JSX.Element {
  const { data, isLoading, error, refetch } = useAnalytics();
  const fleet = useFleetSummary();
  const { announce } = useAnnouncer();

  // Announce on load using a minimal query-like object
  const pseudoQuery = { data } as UseQueryResult<unknown>;
  useAnnounceOnLoad(pseudoQuery, 'Analytics', announce);

  // Loading state
  if (!data && isLoading) {
    return <Spinner label="Loading analytics…" />;
  }

  // Error state (no data)
  if (!data && error) {
    return <ErrorState message={error.message} onRetry={refetch} />;
  }

  // No data available yet (neither loading nor error — unlikely but safe)
  if (!data) {
    return <Spinner label="Loading analytics…" />;
  }

  const devicesByType = data.devices_by_type;
  const hasDevicesByType =
    devicesByType != null && Object.keys(devicesByType).length > 0;

  return (
    <div className="analytics-panel card">
      <h3 className="analytics-panel__title">Analytics &amp; Insights</h3>

      <div className="summary-cards">
        <div className="summary-card summary-card--cyan">
          <div className="summary-card__label">Avg Remaining Health</div>
          <div className="summary-card__value">{formatPercent1(data.average_confidence)}</div>
        </div>
        <div className="summary-card summary-card--gold">
          <div className="summary-card__label">Avg Degradation</div>
          <div className="summary-card__value">{formatPercent1(data.average_degradation)}</div>
        </div>
        <div className="summary-card summary-card--blue">
          <div className="summary-card__label">Total Analyzed</div>
          <div className="summary-card__value">{numberOr0(data.total_devices_analyzed)}</div>
        </div>
      </div>

      {hasDevicesByType && (
        <section className="analytics-distribution">
          <h4 className="analytics-distribution__title">Equipment Distribution</h4>
          <div className="analytics-tiles">
            {Object.entries(devicesByType!).map(([type, count]) => (
              <div key={type} className="analytics-tile">
                <span className="analytics-tile__type">{type}</span>
                <span className="analytics-tile__count">{numberOr0(count)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {fleet.data && <AgentDecisionOverview fleet={fleet.data} />}
    </div>
  );
}
