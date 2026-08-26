import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';

const LastUpdatedContext = createContext<number | null>(null);

export function LastUpdatedProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);

  useEffect(() => {
    const unsubscribe = queryClient.getQueryCache().subscribe((event) => {
      if (event.type === 'updated' && event.query.state.status === 'success') {
        setLastUpdatedAt(event.query.state.dataUpdatedAt);
      }
    });
    return unsubscribe;
  }, [queryClient]);

  return (
    <LastUpdatedContext.Provider value={lastUpdatedAt}>
      {children}
    </LastUpdatedContext.Provider>
  );
}

export function useLastUpdated(): number | null {
  return useContext(LastUpdatedContext);
}
