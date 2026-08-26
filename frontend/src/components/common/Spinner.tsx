import React from 'react';

export interface SpinnerProps {
  /** Size variant: sm (16px), md (24px), lg (32px) */
  size?: 'sm' | 'md' | 'lg';
  /** Accessible label describing what is loading */
  label?: string;
}

/**
 * Loading spinner with an accessible label.
 * Renders a 16px/24px/32px spinning element with a 0.8s rotation and 2px border.
 * When used with a label, wraps in a loading-state container.
 * When used inline (no label), renders just the spinner element.
 */
export function Spinner({ size = 'sm', label }: SpinnerProps): React.JSX.Element {
  if (label) {
    return (
      <div className="loading-state">
        <span className={`spinner spinner--${size}`} role="status" aria-label={label} />
        <span>{label}</span>
      </div>
    );
  }
  return (
    <span className={`spinner spinner--${size}`} role="status" aria-label="Loading" />
  );
}
