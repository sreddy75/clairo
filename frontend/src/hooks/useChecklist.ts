/**
 * React hook for managing onboarding checklist state.
 *
 * Spec 021: Onboarding Flow - Onboarding Checklist Widget
 */

'use client';

import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useState } from 'react';

import {
  getProgress,
  dismissChecklist,
  setAuthToken,
  type OnboardingProgress,
  type OnboardingChecklist,
} from '@/lib/api/onboarding';

interface UseChecklistResult {
  checklist: OnboardingChecklist | null;
  isLoading: boolean;
  error: string | null;
  dismiss: () => Promise<void>;
  refresh: () => Promise<void>;
  shouldShow: boolean;
}

// Don't show checklist if all items are complete for more than 3 days
const HIDE_AFTER_COMPLETE_DAYS = 3;

export function useChecklist(): UseChecklistResult {
  const { getToken } = useAuth();
  const [checklist, setChecklist] = useState<OnboardingChecklist | null>(null);
  const [progress, setProgress] = useState<OnboardingProgress | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch checklist data
  const fetchChecklist = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const token = await getToken();
      if (!token) {
        setIsLoading(false);
        return;
      }
      setAuthToken(token);

      const progressData = await getProgress();
      setProgress(progressData);
      setChecklist(progressData.checklist);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load checklist');
    } finally {
      setIsLoading(false);
    }
  }, [getToken]);

  // Dismiss checklist
  const dismiss = useCallback(async () => {
    try {
      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      const updatedProgress = await dismissChecklist();
      setProgress(updatedProgress);
      setChecklist(updatedProgress.checklist);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to dismiss checklist');
    }
  }, [getToken]);

  // Refresh checklist data
  const refresh = useCallback(async () => {
    await fetchChecklist();
  }, [fetchChecklist]);

  // Initial load
  useEffect(() => {
    fetchChecklist();
  }, [fetchChecklist]);

  // Determine if checklist should be shown
  const shouldShow = (() => {
    if (!checklist || !progress) return false;

    // Don't show if dismissed
    if (checklist.dismissed) return false;

    // Don't show if no items (shouldn't happen, but be safe)
    if (checklist.total_count === 0) return false;

    // Always show if not all items complete
    if (checklist.completed_count < checklist.total_count) return true;

    // If all items complete, check if completed recently
    if (progress.completed_at) {
      const completedDate = new Date(progress.completed_at);
      const now = new Date();
      const daysSinceComplete = Math.floor(
        (now.getTime() - completedDate.getTime()) / (1000 * 60 * 60 * 24)
      );
      return daysSinceComplete < HIDE_AFTER_COMPLETE_DAYS;
    }

    return true;
  })();

  return {
    checklist,
    isLoading,
    error,
    dismiss,
    refresh,
    shouldShow,
  };
}
