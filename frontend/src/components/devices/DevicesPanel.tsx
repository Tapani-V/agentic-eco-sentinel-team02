import React from 'react';
import { useDevices } from '../../queries';
import { AsyncRegion, useAnnouncer } from '../common';
import { DeviceCard } from './DeviceCard';
import { useAnnounceOnLoad } from '../../hooks/useAnnounceOnLoad';
import type { DevicesResponse } from '../../api/types';

/** Grid panel rendering one DeviceCard per device. */
export function DevicesPanel(): React.JSX.Element {
  const query = useDevices();
  const { announce } = useAnnouncer();
  useAnnounceOnLoad(query, 'Devices', announce);

  return (
    <AsyncRegion<DevicesResponse>
      query={query}
      loadingLabel="Loading devices…"
      isEmpty={(data) => data.devices.length === 0}
      emptyMessage={<p className="empty-state">No devices found</p>}
    >
      {(data) => (
        <div className="devices-grid">
          {data.devices.map((device) => (
            <DeviceCard key={device.device_id ?? Math.random()} device={device} />
          ))}
        </div>
      )}
    </AsyncRegion>
  );
}
