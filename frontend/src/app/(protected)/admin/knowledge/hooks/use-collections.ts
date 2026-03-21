'use client';

import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useState } from 'react';

import {
  getCollections,
  initializeCollections,
} from '@/lib/api/knowledge';
import type { CollectionInfo } from '@/types/knowledge';

interface UseCollectionsResult {
  collections: CollectionInfo[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  initialize: () => Promise<void>;
  isInitializing: boolean;
}

export function useCollections(): UseCollectionsResult {
  const { getToken } = useAuth();
  const [collections, setCollections] = useState<CollectionInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isInitializing, setIsInitializing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCollections = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const data = await getCollections(token);
      setCollections(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch collections');
    } finally {
      setIsLoading(false);
    }
  }, [getToken]);

  const initialize = useCallback(async () => {
    setIsInitializing(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      await initializeCollections(token);
      await fetchCollections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initialize collections');
    } finally {
      setIsInitializing(false);
    }
  }, [getToken, fetchCollections]);

  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  return {
    collections,
    isLoading,
    error,
    refresh: fetchCollections,
    initialize,
    isInitializing,
  };
}
