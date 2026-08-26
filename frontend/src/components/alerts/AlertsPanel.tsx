import React from 'react';
import { useAlerts } from '../../queries';
import { AsyncRegion, useAnnouncer } from '../common';
import { AlertItem } from './AlertItem';
import { useAnnounceOnLoad } from '../../hooks/useAnnounceOnLoad';
import type { AlertsResponse } from '../../api/types';

/** Vertical list panel rendering one AlertItem per active alert. */
export function AlertsPanel(): React.JSX.Element {
  const query = useAlerts();
  const { announce } = useAnnouncer();
  useAnnounceOnLoad(query, 'Alerts', announce);

  return (
    <AsyncRegion<AlertsResponse>
      query={query}
      loadingLabel="Loading alerts…"
      isEmpty={(data) => data.alerts.length === 0}
      emptyMessage={<p className="empty-state">✅ No active alerts</p>}
    >
      {(data) => (
        <div className="alert-list">
          {data.alerts.map((alert, index) => (
            <AlertItem key={`${alert.device_id ?? ''}-${index}`} alert={alert} />
          ))}
        </div>
      )}
    </AsyncRegion>
  );
}
