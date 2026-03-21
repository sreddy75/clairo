'use client';

import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useRef, useState } from 'react';

import { getJob, getJobs } from '@/lib/api/knowledge';
import type {
  IngestionJob,
  IngestionJobSummary,
  JobsFilter,
  JobStatus,
} from '@/types/knowledge';

interface UseJobsResult {
  jobs: IngestionJobSummary[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  filter: JobsFilter;
  setFilter: (filter: JobsFilter) => void;
  selectedJob: IngestionJob | null;
  selectJob: (id: string) => Promise<void>;
  clearSelectedJob: () => void;
  isLoadingJob: boolean;
}

const POLL_INTERVAL = 3000; // 3 seconds

export function useJobs(): UseJobsResult {
  const { getToken } = useAuth();
  const [jobs, setJobs] = useState<IngestionJobSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingJob, setIsLoadingJob] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<JobsFilter>({});
  const [selectedJob, setSelectedJob] = useState<IngestionJob | null>(null);
  const pollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const fetchJobs = useCallback(async () => {
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const data = await getJobs(token, filter);
      setJobs(data);

      // Check if any jobs are running and set up polling
      const hasRunningJobs = data.some((job) => job.status === 'running');
      if (hasRunningJobs) {
        pollTimeoutRef.current = setTimeout(() => {
          fetchJobs();
        }, POLL_INTERVAL);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch jobs');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, filter]);

  const selectJob = useCallback(
    async (id: string) => {
      setIsLoadingJob(true);
      setError(null);
      try {
        const token = await getToken();
        if (!token) throw new Error('Not authenticated');
        const job = await getJob(token, id);
        setSelectedJob(job);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch job details');
      } finally {
        setIsLoadingJob(false);
      }
    },
    [getToken]
  );

  const clearSelectedJob = useCallback(() => {
    setSelectedJob(null);
  }, []);

  useEffect(() => {
    setIsLoading(true);
    fetchJobs();

    return () => {
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
      }
    };
  }, [fetchJobs]);

  return {
    jobs,
    isLoading,
    error,
    refresh: fetchJobs,
    filter,
    setFilter,
    selectedJob,
    selectJob,
    clearSelectedJob,
    isLoadingJob,
  };
}

// Helper to format job status with styling
export function getJobStatusConfig(status: JobStatus): {
  label: string;
  color: string;
  bgColor: string;
} {
  const config: Record<JobStatus, { label: string; color: string; bgColor: string }> = {
    pending: { label: 'Pending', color: 'text-slate-600', bgColor: 'bg-slate-100' },
    running: { label: 'Running', color: 'text-blue-600', bgColor: 'bg-blue-100' },
    completed: { label: 'Completed', color: 'text-green-600', bgColor: 'bg-green-100' },
    failed: { label: 'Failed', color: 'text-red-600', bgColor: 'bg-red-100' },
    cancelled: { label: 'Cancelled', color: 'text-amber-600', bgColor: 'bg-amber-100' },
  };
  return config[status];
}
