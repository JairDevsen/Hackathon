import { keepPreviousData, QueryClient, useQuery } from '@tanstack/react-query'
import { api, type Opts } from './api'

export const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: (n, e: any) => n < 2 && !(e?.status >= 400 && e?.status < 500), refetchOnWindowFocus: false } } })

export function useGet<T = any>(path: string | null, query?: Opts['query'], options: { refetchInterval?: number; keep?: boolean } = {}) {
  return useQuery<T>({
    queryKey: [path, query],
    queryFn: ({ signal }) => api<T>(path!, { query, signal }),
    enabled: !!path,
    refetchInterval: options.refetchInterval,
    placeholderData: options.keep ? keepPreviousData : undefined,
  })
}
