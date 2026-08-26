import React from 'react';

export interface EmptyStateProps {
  /** The empty-state message to display */
  message: string;
}

/** Renders an empty-state message in a styled container. */
export function EmptyState({ message }: EmptyStateProps): React.JSX.Element {
  return (
    <div className="empty-state">
      <p>{message}</p>
    </div>
  );
}
