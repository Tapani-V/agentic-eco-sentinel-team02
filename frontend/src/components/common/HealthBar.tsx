import React from 'react';
import { computeHealth } from '../../domain/health';
import { healthBarClass } from '../../domain/status';

export interface HealthBarProps {
  /** The degradation score (nominally 0–1). Passed to computeHealth. */
  score: unknown;
  /** The health_status value from the API. Determines the fill gradient class. */
  status: unknown;
}

/**
 * Health bar whose fill width comes exclusively from computeHealth
 * and whose fill gradient class comes from healthBarClass.
 */
export function HealthBar({ score, status }: HealthBarProps): React.JSX.Element {
  const health = computeHealth(score);
  const fillClass = healthBarClass(status);

  return (
    <div className="health-bar" role="meter" aria-valuenow={health.percent} aria-valuemin={0} aria-valuemax={100} aria-label={`Health: ${health.percent}%`}>
      <div
        className={`health-bar__fill health-bar__fill--${fillClass}`}
        style={{ width: health.barWidth }}
      />
    </div>
  );
}
