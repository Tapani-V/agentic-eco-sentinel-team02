import React from 'react';

export interface StaleNoticeProps {
  /** Optional custom message */
  message?: string;
}

/** Notice indicating that displayed data may be stale due to a failed refresh. */
export function StaleNotice({ message = 'Data may be stale — a recent update failed.' }: StaleNoticeProps): React.JSX.Element {
  return (
    <div className="stale-notice" role="status">
      <span className="stale-notice__icon" aria-hidden="true">⚠️</span>
      <span className="stale-notice__text">{message}</span>
    </div>
  );
}
