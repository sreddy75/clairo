'use client';

/**
 * useA2UIRenderer Hook
 * Manages A2UI message fetching and rendering state
 */

import { useState, useCallback, useEffect } from 'react';

import type { A2UIMessage, A2UIActionHandlers } from '@/lib/a2ui/types';

// =============================================================================
// Types
// =============================================================================

export interface UseA2UIRendererOptions {
  /** URL to fetch A2UI message from */
  url?: string;
  /** Initial A2UI message (if not fetching) */
  initialMessage?: A2UIMessage;
  /** Action handlers */
  actionHandlers?: A2UIActionHandlers;
  /** Whether to fetch immediately on mount */
  fetchOnMount?: boolean;
  /** Poll interval in ms (0 = no polling) */
  pollInterval?: number;
  /** Custom fetch options */
  fetchOptions?: RequestInit;
}

export interface UseA2UIRendererResult {
  /** Current A2UI message */
  message: A2UIMessage | null;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: Error | null;
  /** Refetch the A2UI message */
  refetch: () => Promise<void>;
  /** Clear the current message */
  clear: () => void;
  /** Set a new message directly */
  setMessage: (message: A2UIMessage) => void;
}

// =============================================================================
// Hook Implementation
// =============================================================================

export function useA2UIRenderer(
  options: UseA2UIRendererOptions = {}
): UseA2UIRendererResult {
  const {
    url,
    initialMessage,
    fetchOnMount = true,
    pollInterval = 0,
    fetchOptions,
  } = options;

  const [message, setMessage] = useState<A2UIMessage | null>(initialMessage || null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Fetch A2UI message from URL
  const fetchMessage = useCallback(async () => {
    if (!url) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        ...fetchOptions,
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch A2UI: ${response.status} ${response.statusText}`);
      }

      const data: A2UIMessage = await response.json();

      // Validate basic structure
      if (!data.surfaceUpdate || !data.meta) {
        throw new Error('Invalid A2UI message structure');
      }

      setMessage(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setIsLoading(false);
    }
  }, [url, fetchOptions]);

  // Refetch function
  const refetch = useCallback(async () => {
    await fetchMessage();
  }, [fetchMessage]);

  // Clear message
  const clear = useCallback(() => {
    setMessage(null);
    setError(null);
  }, []);

  // Fetch on mount
  useEffect(() => {
    if (fetchOnMount && url) {
      fetchMessage();
    }
  }, [fetchOnMount, url, fetchMessage]);

  // Polling
  useEffect(() => {
    if (!pollInterval || !url) return;

    const interval = setInterval(() => {
      fetchMessage();
    }, pollInterval);

    return () => clearInterval(interval);
  }, [pollInterval, url, fetchMessage]);

  return {
    message,
    isLoading,
    error,
    refetch,
    clear,
    setMessage,
  };
}

// =============================================================================
// POST Hook (for queries)
// =============================================================================

export interface UseA2UIQueryOptions {
  /** URL to POST query to */
  url: string;
  /** Action handlers */
  actionHandlers?: A2UIActionHandlers;
  /** Custom fetch options */
  fetchOptions?: RequestInit;
}

export interface UseA2UIQueryResult extends UseA2UIRendererResult {
  /** Execute a query */
  query: (queryText: string) => Promise<void>;
}

export function useA2UIQuery(options: UseA2UIQueryOptions): UseA2UIQueryResult {
  const { url, fetchOptions } = options;

  const [message, setMessage] = useState<A2UIMessage | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const query = useCallback(
    async (queryText: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: JSON.stringify({ query: queryText }),
          ...fetchOptions,
        });

        if (!response.ok) {
          throw new Error(`Query failed: ${response.status} ${response.statusText}`);
        }

        const data: A2UIMessage = await response.json();
        setMessage(data);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Unknown error'));
      } finally {
        setIsLoading(false);
      }
    },
    [url, fetchOptions]
  );

  const refetch = useCallback(async () => {
    // No-op for query hook - use query() instead
  }, []);

  const clear = useCallback(() => {
    setMessage(null);
    setError(null);
  }, []);

  return {
    message,
    isLoading,
    error,
    refetch,
    clear,
    setMessage,
    query,
  };
}
