import { useMutation, useQueryClient } from '@tanstack/react-query';
import { getCacheClear } from '../api/endpoints';

export function useHardRefresh() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: getCacheClear,
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });
}
