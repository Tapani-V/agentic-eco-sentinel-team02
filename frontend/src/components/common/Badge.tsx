import React from 'react';

export interface BadgeProps {
  /** Display text */
  children: React.ReactNode;
  /** Visual variant modifier for styling */
  variant?: string;
}

/** Inline badge with a variant modifier class. */
export function Badge({ children, variant }: BadgeProps): React.JSX.Element {
  return (
    <span className={`badge${variant ? ` badge--${variant}` : ''}`}>
      {children}
    </span>
  );
}
