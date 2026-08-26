import React from 'react';
import type { Alert } from '../../api/types';
import { textOr } from '../../domain/format';
import { alertSeverityClass } from '../../domain/status';

export interface AlertItemProps {
  alert: Alert;
}

/** Renders a single alert item with severity badge and device info. */
export function AlertItem({ alert }: AlertItemProps): React.JSX.Element {
  const severityClass = alertSeverityClass(alert.severity);

  return (
    <div className={`alert-item alert-item--${severityClass}`}>
      <div className="alert-item__content">
        <div className="alert-item__title">{textOr(alert.title, 'Untitled Alert')}</div>
        <div className="alert-item__description">{textOr(alert.description, 'No description')}</div>
        <div className="alert-item__device">Device: {textOr(alert.device_id, 'Unknown')}</div>
      </div>
      <span className="alert-item__badge">
        {textOr(alert.severity, 'unknown').toUpperCase()}
      </span>
    </div>
  );
}
