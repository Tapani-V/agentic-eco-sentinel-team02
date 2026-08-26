import React from 'react';
import type { ProblematicDevice } from '../../api/types';
import { computeHealth } from '../../domain/health';
import { attentionLabel } from '../../domain/status';
import { textOr } from '../../domain/format';

export interface AttentionListProps {
  devices: ProblematicDevice[];
}

export function AttentionList({ devices }: AttentionListProps): React.JSX.Element {
  if (!devices || devices.length === 0) {
    return <p className="empty-state">✅ All devices operating normally</p>;
  }

  return (
    <div className="attention-list">
      {devices.map((device, index) => {
        const health = computeHealth(device.degradation_score);
        const statusClass = device.health_status === 'critical' ? 'attention-item--critical' : 'attention-item--warning';

        return (
          <div key={index} className={`attention-item ${statusClass}`}>
            <div className="attention-item__left">
              <span className="attention-item__id">{textOr(device.device_id, 'Unknown')}</span>
              <span className="attention-item__type">{textOr(device.equipment_type, 'UNKNOWN')}</span>
            </div>
            <div className="attention-item__right">
              <span className="attention-item__status">{attentionLabel(device.health_status)}</span>
              <span className="attention-item__health">Health: {health.percent}%</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
