import { useEffect, useRef, useState } from 'react';
import { useHardRefresh } from '../../queries/useHardRefresh';
import { HARD_REFRESH_LABEL_RESET_MS } from '../../config/intervals';

type HardRefreshState = 'idle' | 'pending' | 'done' | 'failed';

const LABELS: Record<HardRefreshState, string> = {
  idle: '⚡ Hard Refresh',
  pending: '⏳ Fetching fresh data (3-5 min)...',
  done: '✅ Done!',
  failed: '❌ Failed',
};

export function HardRefreshButton() {
  const [state, setState] = useState<HardRefreshState>('idle');
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mutation = useHardRefresh();

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  const handleClick = () => {
    if (state === 'pending') return;
    setState('pending');
    mutation.mutate(undefined, {
      onSuccess: () => {
        setState('done');
        timerRef.current = setTimeout(() => {
          setState('idle');
          timerRef.current = null;
        }, HARD_REFRESH_LABEL_RESET_MS);
      },
      onError: () => {
        setState('failed');
        timerRef.current = setTimeout(() => {
          setState('idle');
          timerRef.current = null;
        }, HARD_REFRESH_LABEL_RESET_MS);
      },
    });
  };

  return (
    <button
      className="btn-hard-refresh"
      onClick={handleClick}
      disabled={state === 'pending'}
      aria-busy={state === 'pending'}
    >
      {LABELS[state]}
    </button>
  );
}
