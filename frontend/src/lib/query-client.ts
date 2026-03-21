import { QueryClient } from '@tanstack/react-query';

/**
 * Create and configure the TanStack Query client.
 *
 * Configuration:
 * - staleTime: 5 minutes - data considered fresh for this duration
 * - gcTime: 30 minutes - unused data garbage collected after this duration
 * - retry: 3 times with exponential backoff
 * - refetchOnWindowFocus: disabled for better UX
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Data stays fresh for 5 minutes
      staleTime: 5 * 60 * 1000,

      // Garbage collect after 30 minutes
      gcTime: 30 * 60 * 1000,

      // Retry 3 times with exponential backoff
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

      // Don't refetch on window focus (can be annoying)
      refetchOnWindowFocus: false,

      // Refetch on reconnect
      refetchOnReconnect: true,
    },
    mutations: {
      // Retry mutations once
      retry: 1,
    },
  },
});
