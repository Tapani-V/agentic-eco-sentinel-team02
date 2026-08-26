import { useEffect, useRef } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';

/**
 * Pushes "{label} loaded" into a live-region announce function
 * on each absent→present transition of query data.
 */
export function useAnnounceOnLoad(
  query: UseQueryResult<unknown>,
  label: string,
  announce: (msg: string) => void,
): void {
  const prevHadData = useRef(false);

  useEffect(() => {
    const hasData = query.data !== undefined;
    if (hasData && !prevHadData.current) {
      announce(`${label} loaded`);
    }
    prevHadData.current = hasData;
  }, [query.data, label, announce]);
}
