/**
 * React hook for managing the product tour state.
 *
 * Spec 021: Onboarding Flow - Interactive Product Tour
 */

'use client';

import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useState } from 'react';

import { completeTour, skipTour, setAuthToken, getProgress } from '@/lib/api/onboarding';

interface UseTourResult {
  shouldShowTour: boolean;
  isTourRunning: boolean;
  startTour: () => void;
  handleTourEnd: (data: { action: string }) => void;
  isLoading: boolean;
  error: string | null;
}

const TOUR_STORAGE_KEY = 'clairo_tour_skipped';

export function useTour(): UseTourResult {
  const { getToken } = useAuth();
  const [shouldShowTour, setShouldShowTour] = useState(false);
  const [isTourRunning, setIsTourRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check if tour should run on mount
  useEffect(() => {
    async function checkTourStatus() {
      try {
        setIsLoading(true);
        setError(null);

        const token = await getToken();
        if (!token) {
          setIsLoading(false);
          return;
        }
        setAuthToken(token);

        // Check if user has completed or skipped the tour locally
        const locallySkipped = localStorage.getItem(TOUR_STORAGE_KEY) === 'true';
        if (locallySkipped) {
          setShouldShowTour(false);
          setIsLoading(false);
          return;
        }

        // Check onboarding progress
        const progress = await getProgress();

        // Tour should show if:
        // 1. Onboarding exists (user has started)
        // 2. Tour not completed
        // 3. Tour not skipped
        const shouldShow =
          progress &&
          !progress.tour_completed_at &&
          !progress.tour_skipped &&
          progress.payment_setup_at !== null; // Only after payment setup

        setShouldShowTour(shouldShow);
      } catch (err) {
        // Don't show error to user, just don't show tour
        console.error('Failed to check tour status:', err);
        setShouldShowTour(false);
      } finally {
        setIsLoading(false);
      }
    }

    checkTourStatus();
  }, [getToken]);

  // Start the tour
  const startTour = useCallback(() => {
    // Clear local skip flag if restarting
    localStorage.removeItem(TOUR_STORAGE_KEY);
    setIsTourRunning(true);
  }, []);

  // Handle tour completion or skip
  const handleTourEnd = useCallback(async (data: { action: string }) => {
    setIsTourRunning(false);

    try {
      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      if (data.action === 'skip' || data.action === 'close') {
        // User skipped or closed the tour
        await skipTour();
        localStorage.setItem(TOUR_STORAGE_KEY, 'true');
      } else if (data.action === 'reset' || data.action === 'next') {
        // This shouldn't trigger API call
        return;
      } else {
        // User completed the tour (last step)
        await completeTour();
      }

      setShouldShowTour(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save tour status');
      // Still hide the tour locally even if API fails
      localStorage.setItem(TOUR_STORAGE_KEY, 'true');
      setShouldShowTour(false);
    }
  }, [getToken]);

  return {
    shouldShowTour,
    isTourRunning,
    startTour,
    handleTourEnd,
    isLoading,
    error,
  };
}
