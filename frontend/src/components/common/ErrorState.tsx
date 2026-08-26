import React from 'react';

export interface ErrorStateProps {
  /** Error message to display */
  message: string;
  /** Callback invoked when the retry control is activated */
  onRetry?: () => void;
}

/** Renders an error message with an optional retry button. */
export function ErrorState({ message, onRetry }: ErrorStateProps): React.JSX.Element {
  return (
    <div className="error-state" role="alert">
      <p className="error-state__message">{message}</p>
      {onRetry && (
        <button className="error-state__retry" type="button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
