import React from 'react';

export type KpiVariant = 'healthy' | 'warning' | 'critical' | 'default';

export interface KpiCardProps {
  /** The card's heading label */
  label: string;
  /** The displayed value — can be a string or a ReactNode (e.g. Spinner) */
  value: string | React.ReactNode;
  /** Descriptive subtext below the value */
  subtext: string;
  /** Left-border colour variant mapped to state tokens */
  variant: KpiVariant;
}

/**
 * A single KPI summary card with a coloured left border,
 * a label, a prominent value, and a subtext line.
 */
export function KpiCard({ label, value, subtext, variant }: KpiCardProps): React.JSX.Element {
  return (
    <div className={`kpi-card kpi-card--${variant}`}>
      <div className="kpi-card__label">{label}</div>
      <div className="kpi-card__value">{value}</div>
      <div className="kpi-card__subtext">{subtext}</div>
    </div>
  );
}
