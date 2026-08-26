import React from 'react';
import type { Device } from '../../api/types';
import { computeHealth } from '../../domain/health';
import { textOr } from '../../domain/format';
import { healthBarClass } from '../../domain/status';
import { HealthBar } from '../common';
import { MemoryIndicators } from './MemoryIndicators';

export interface DeviceCardProps {
  device: Device;
}

/** Renders a single device card with health bar and status information. */
export function DeviceCard({ device }: DeviceCardProps): React.JSX.Element {
  const health = computeHealth(device.degradation_score);
  const statusClass = healthBarClass(device.health_status);

  return (
    <div className={`device-card device-card--${statusClass}`}>
      <div className="device-card__id">{textOr(device.device_id, 'Unknown Device')}</div>
      <span className="device-card__type">{textOr(device.equipment_type, 'Unknown')}</span>
      <HealthBar score={device.degradation_score} status={device.health_status} />
      <MemoryIndicators context={device.memory_context} />
      <div className="device-card__footer">
        <span className="device-card__status">{textOr(device.health_status, 'unknown')}</span>
        <span className="device-card__health">Health: {health.percent}%</span>
      </div>
    </div>
  );
}
