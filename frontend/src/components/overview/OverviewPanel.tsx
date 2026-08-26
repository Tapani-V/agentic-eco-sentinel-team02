import React from 'react';
import { useFleetSummary } from '../../queries';
import { AsyncRegion, Card, useAnnouncer } from '../common';
import { StatusChart } from './StatusChart';
import { AttentionList } from './AttentionList';
import { numberOr0 } from '../../domain/format';
import { useAnnounceOnLoad } from '../../hooks/useAnnounceOnLoad';

/** Overview panel showing device status distribution chart and attention list. */
export function OverviewPanel(): React.JSX.Element {
  const fleetQuery = useFleetSummary();
  const { announce } = useAnnouncer();
  useAnnounceOnLoad(fleetQuery, 'Overview', announce);

  return (
    <AsyncRegion query={fleetQuery} loadingLabel="Loading overview…">
      {(data) => (
        <div className="overview-grid">
          <Card title="Device Status Distribution">
            <StatusChart
              healthy={numberOr0(data.healthy_devices)}
              warning={numberOr0(data.warning_devices)}
              critical={numberOr0(data.critical_devices)}
            />
          </Card>
          <Card title="Devices Needing Attention">
            <AttentionList devices={data._problematic_devices} />
          </Card>
        </div>
      )}
    </AsyncRegion>
  );
}
