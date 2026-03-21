/**
 * React hook for onboarding state management.
 *
 * Provides access to onboarding progress and actions.
 */

'use client';

import { useCallback, useEffect, useState } from 'react';

import {
  type BulkImportJob,
  type OnboardingProgress,
  type SubscriptionTier,
  completeTour,
  dismissChecklist,
  getProgress,
  initiateXeroConnect,
  selectTier,
  skipTour,
  skipXero,
  startBulkImport,
  startOnboarding,
} from '@/lib/api/onboarding';

interface UseOnboardingOptions {
  /** Skip the initial fetch on mount (useful when auth token isn't ready yet) */
  skipInitialFetch?: boolean;
}

interface UseOnboardingResult {
  // State
  progress: OnboardingProgress | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  start: () => Promise<OnboardingProgress>;
  selectTierAndStartTrial: (
    tier: SubscriptionTier,
    withTrial?: boolean
  ) => Promise<OnboardingProgress>;
  connectXero: () => Promise<string>;
  skipXeroStep: () => Promise<OnboardingProgress>;
  importClients: (
    clientIds: string[],
    sourceType?: 'xpm' | 'xero_accounting'
  ) => Promise<BulkImportJob>;
  completeProductTour: () => Promise<OnboardingProgress>;
  skipProductTour: () => Promise<OnboardingProgress>;
  dismissOnboardingChecklist: () => Promise<OnboardingProgress>;

  // Utilities
  refresh: () => Promise<void>;
  getChecklistProgress: () => { completed: number; total: number };
  isComplete: boolean;
}

export function useOnboarding(options: UseOnboardingOptions = {}): UseOnboardingResult {
  const { skipInitialFetch = false } = options;
  const [progress, setProgress] = useState<OnboardingProgress | null>(null);
  const [isLoading, setIsLoading] = useState(!skipInitialFetch);
  const [error, setError] = useState<string | null>(null);

  // Fetch initial progress
  const fetchProgress = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await getProgress();
      setProgress(data);
    } catch (err) {
      // If 404, user hasn't started onboarding yet
      if (err instanceof Error && err.message.includes('404')) {
        setProgress(null);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load progress');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!skipInitialFetch) {
      fetchProgress();
    }
  }, [fetchProgress, skipInitialFetch]);

  // Start onboarding
  const start = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await startOnboarding();
      setProgress(data);
      return data;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Select tier and start trial (no Stripe redirect)
  const selectTierAndStartTrial = useCallback(
    async (tier: SubscriptionTier, withTrial: boolean = true) => {
      setIsLoading(true);
      try {
        const data = await selectTier({
          tier,
          with_trial: withTrial,
        });
        setProgress(data);
        return data;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // Initiate Xero connection
  const connectXero = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await initiateXeroConnect();
      return response.authorization_url;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Skip Xero step
  const skipXeroStep = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await skipXero();
      setProgress(data);
      return data;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Import clients
  const importClients = useCallback(
    async (
      clientIds: string[],
      sourceType: 'xpm' | 'xero_accounting' = 'xpm'
    ) => {
      setIsLoading(true);
      try {
        const job = await startBulkImport(clientIds, sourceType);
        // Refresh progress after import starts
        await fetchProgress();
        return job;
      } finally {
        setIsLoading(false);
      }
    },
    [fetchProgress]
  );

  // Complete product tour
  const completeProductTour = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await completeTour();
      setProgress(data);
      return data;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Skip product tour
  const skipProductTour = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await skipTour();
      setProgress(data);
      return data;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Dismiss checklist
  const dismissOnboardingChecklist = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await dismissChecklist();
      setProgress(data);
      return data;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Get checklist progress
  const getChecklistProgress = useCallback(() => {
    if (!progress?.checklist) {
      return { completed: 0, total: 0 };
    }
    return {
      completed: progress.checklist.completed_count,
      total: progress.checklist.total_count,
    };
  }, [progress?.checklist]);

  return {
    progress,
    isLoading,
    error,
    start,
    selectTierAndStartTrial,
    connectXero,
    skipXeroStep,
    importClients,
    completeProductTour,
    skipProductTour,
    dismissOnboardingChecklist,
    refresh: fetchProgress,
    getChecklistProgress,
    isComplete: progress?.status === 'completed',
  };
}
