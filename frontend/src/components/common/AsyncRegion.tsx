import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Spinner } from './Spinner';
import { ErrorState } from './ErrorState';
import { StaleNotice } from './StaleNotice';

export interface AsyncRegionProps<T> {
  /** The TanStack Query result to observe */
  query: UseQueryResult<T>;
  /** Accessible label shown alongside the spinner during initial load */
  loadingLabel: string;
  /** Predicate that returns true when data is considered empty */
  isEmpty?(data: T): boolean;
  /** Content rendered when isEmpty returns true */
  emptyMessage?: ReactNode;
  /** Render function called when data is available */
  children(data: T, meta: { isStale: boolean }): ReactNode;
}

/**
 * Encodes the async state table for any data-dependent region:
 * - No data + in flight → spinner + label
 * - No data + error → ErrorState with retry
 * - Data + isEmpty → emptyMessage
 * - Data + error → children + StaleNotice
 * - Data (no error) → children
 */
export function AsyncRegion<T>({ query, loadingLabel, isEmpty, emptyMessage, children }: AsyncRegionProps<T>) {
  const { data, error, isFetching } = query;

  // No data + in flight → spinner
  if (data === undefined && isFetching) {
    return (
      <div className="async-region-loading">
        <Spinner label={loadingLabel} />
      </div>
    );
  }

  // No data + error → error state
  if (data === undefined && error) {
    return (
      <div className="async-region-loading">
        <ErrorState message={error.message} onRetry={() => query.refetch()} />
      </div>
    );
  }

  // Data exists
  if (data !== undefined) {
    // Data + isEmpty → empty message
    if (isEmpty?.(data)) {
      return <>{emptyMessage}</>;
    }

    const isStale = !!error;
    return (
      <>
        {children(data, { isStale })}
        {isStale && <StaleNotice />}
      </>
    );
  }

  return null;
}
