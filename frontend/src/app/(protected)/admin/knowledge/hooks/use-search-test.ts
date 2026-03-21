'use client';

import { useAuth } from '@clerk/nextjs';
import { useCallback, useState } from 'react';

import { testSearch } from '@/lib/api/knowledge';
import type { SearchRequest, SearchResponse } from '@/types/knowledge';

interface UseSearchTestResult {
  results: SearchResponse | null;
  isSearching: boolean;
  error: string | null;
  search: (request: SearchRequest) => Promise<void>;
  clear: () => void;
}

export function useSearchTest(): UseSearchTestResult {
  const { getToken } = useAuth();
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(
    async (request: SearchRequest) => {
      setIsSearching(true);
      setError(null);
      try {
        const token = await getToken();
        if (!token) throw new Error('Not authenticated');
        const response = await testSearch(token, request);
        setResults(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Search failed');
        setResults(null);
      } finally {
        setIsSearching(false);
      }
    },
    [getToken]
  );

  const clear = useCallback(() => {
    setResults(null);
    setError(null);
  }, []);

  return {
    results,
    isSearching,
    error,
    search,
    clear,
  };
}
