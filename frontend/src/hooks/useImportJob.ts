/**
 * React hook for polling import job status.
 *
 * Polls the import job endpoint every 2 seconds while the job is in progress.
 *
 * Spec 021: Onboarding Flow - Bulk Import
 */

'use client';

import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useRef, useState } from 'react';

import { getImportJob, setAuthToken, type BulkImportJob } from '@/lib/api/onboarding';

interface UseImportJobResult {
  job: BulkImportJob | null;
  isLoading: boolean;
  error: string | null;
  startPolling: (jobId: string) => void;
  stopPolling: () => void;
  isPolling: boolean;
}

const POLL_INTERVAL = 2000; // 2 seconds

export function useImportJob(): UseImportJobResult {
  const { getToken } = useAuth();
  const [job, setJob] = useState<BulkImportJob | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const jobIdRef = useRef<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch job status
  const fetchJobStatus = useCallback(async (jobId: string) => {
    try {
      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      const jobData = await getImportJob(jobId);
      setJob(jobData);

      // Stop polling if job is complete or failed
      if (
        jobData.status === 'completed' ||
        jobData.status === 'partial_failure' ||
        jobData.status === 'failed' ||
        jobData.status === 'cancelled'
      ) {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
          setIsPolling(false);
        }
      }

      return jobData;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch job status');
      return null;
    }
  }, [getToken]);

  // Start polling
  const startPolling = useCallback((jobId: string) => {
    // Stop any existing polling
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    jobIdRef.current = jobId;
    setIsPolling(true);
    setError(null);
    setIsLoading(true);

    // Initial fetch
    fetchJobStatus(jobId).finally(() => setIsLoading(false));

    // Start polling
    intervalRef.current = setInterval(() => {
      if (jobIdRef.current) {
        fetchJobStatus(jobIdRef.current);
      }
    }, POLL_INTERVAL);
  }, [fetchJobStatus]);

  // Stop polling
  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
    jobIdRef.current = null;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return {
    job,
    isLoading,
    error,
    startPolling,
    stopPolling,
    isPolling,
  };
}
