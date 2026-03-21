'use client';

import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useState } from 'react';

import {
  createSource,
  deleteSource,
  getSources,
  triggerIngestion,
  updateSource,
} from '@/lib/api/knowledge';
import type {
  KnowledgeSource,
  KnowledgeSourceCreate,
  KnowledgeSourceUpdate,
} from '@/types/knowledge';

interface UseSourcesResult {
  sources: KnowledgeSource[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  create: (data: KnowledgeSourceCreate) => Promise<KnowledgeSource>;
  update: (id: string, data: KnowledgeSourceUpdate) => Promise<KnowledgeSource>;
  remove: (id: string) => Promise<void>;
  ingest: (id: string) => Promise<void>;
  isOperating: boolean;
}

export function useSources(): UseSourcesResult {
  const { getToken } = useAuth();
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isOperating, setIsOperating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSources = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const data = await getSources(token);
      setSources(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch sources');
    } finally {
      setIsLoading(false);
    }
  }, [getToken]);

  const create = useCallback(
    async (data: KnowledgeSourceCreate): Promise<KnowledgeSource> => {
      setIsOperating(true);
      setError(null);
      try {
        const token = await getToken();
        if (!token) throw new Error('Not authenticated');
        const source = await createSource(token, data);
        await fetchSources();
        return source;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to create source';
        setError(message);
        throw err;
      } finally {
        setIsOperating(false);
      }
    },
    [getToken, fetchSources]
  );

  const update = useCallback(
    async (id: string, data: KnowledgeSourceUpdate): Promise<KnowledgeSource> => {
      setIsOperating(true);
      setError(null);
      try {
        const token = await getToken();
        if (!token) throw new Error('Not authenticated');
        const source = await updateSource(token, id, data);
        await fetchSources();
        return source;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to update source';
        setError(message);
        throw err;
      } finally {
        setIsOperating(false);
      }
    },
    [getToken, fetchSources]
  );

  const remove = useCallback(
    async (id: string): Promise<void> => {
      setIsOperating(true);
      setError(null);
      try {
        const token = await getToken();
        if (!token) throw new Error('Not authenticated');
        await deleteSource(token, id);
        await fetchSources();
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to delete source';
        setError(message);
        throw err;
      } finally {
        setIsOperating(false);
      }
    },
    [getToken, fetchSources]
  );

  const ingest = useCallback(
    async (id: string): Promise<void> => {
      setIsOperating(true);
      setError(null);
      try {
        const token = await getToken();
        if (!token) throw new Error('Not authenticated');
        await triggerIngestion(token, id);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to trigger ingestion';
        setError(message);
        throw err;
      } finally {
        setIsOperating(false);
      }
    },
    [getToken]
  );

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  return {
    sources,
    isLoading,
    error,
    refresh: fetchSources,
    create,
    update,
    remove,
    ingest,
    isOperating,
  };
}
