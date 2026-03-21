'use client';

/**
 * Hook for fetching and managing trial status.
 *
 * Spec 021: Onboarding Flow - Free Trial Experience
 */

import { useCallback, useEffect, useState } from 'react';

import { getTrialStatus } from '@/lib/api/billing';
import type { SubscriptionTier, TrialStatusResponse } from '@/types/billing';

interface TrialState {
  isTrial: boolean;
  tier: SubscriptionTier | null;
  daysRemaining: number | null;
  trialEndDate: string | null;
  billingDate: string | null;
  priceMonthly: number;
  isLoading: boolean;
  error: string | null;
}

interface UseTrialStatusReturn extends TrialState {
  /**
   * Refresh trial status from the API.
   */
  refresh: () => Promise<void>;

  /**
   * Formatted billing date string (e.g., "January 15, 2025").
   */
  formattedBillingDate: string | null;

  /**
   * Whether the trial is ending soon (3 days or less).
   */
  isEndingSoon: boolean;

  /**
   * Whether the trial ends today or tomorrow.
   */
  isUrgent: boolean;
}

/**
 * Hook for fetching and managing trial status.
 * Used to display trial banners and billing information.
 *
 * @example
 * ```tsx
 * function Dashboard() {
 *   const { isTrial, daysRemaining, formattedBillingDate, tier, priceMonthly } = useTrialStatus();
 *
 *   if (isTrial && daysRemaining !== null) {
 *     return (
 *       <TrialBanner
 *         daysRemaining={daysRemaining}
 *         tier={tier}
 *         priceMonthly={priceMonthly}
 *         billingDate={formattedBillingDate}
 *       />
 *     );
 *   }
 *
 *   return <DashboardContent />;
 * }
 * ```
 */
export function useTrialStatus(): UseTrialStatusReturn {
  const [state, setState] = useState<TrialState>({
    isTrial: false,
    tier: null,
    daysRemaining: null,
    trialEndDate: null,
    billingDate: null,
    priceMonthly: 0,
    isLoading: true,
    error: null,
  });

  const fetchTrialStatus = useCallback(async () => {
    try {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      const response: TrialStatusResponse = await getTrialStatus();

      setState({
        isTrial: response.is_trial,
        tier: response.tier,
        daysRemaining: response.days_remaining,
        trialEndDate: response.trial_end_date,
        billingDate: response.billing_date,
        priceMonthly: response.price_monthly,
        isLoading: false,
        error: null,
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: 'Failed to load trial status',
      }));
      console.error('Failed to fetch trial status:', err);
    }
  }, []);

  useEffect(() => {
    fetchTrialStatus();
  }, [fetchTrialStatus]);

  // Format billing date for display
  const formattedBillingDate = state.billingDate
    ? new Date(state.billingDate).toLocaleDateString('en-AU', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null;

  // Check if trial is ending soon (3 days or less)
  const isEndingSoon =
    state.isTrial && state.daysRemaining !== null && state.daysRemaining <= 3;

  // Check if trial is urgent (today or tomorrow)
  const isUrgent =
    state.isTrial && state.daysRemaining !== null && state.daysRemaining <= 1;

  return {
    ...state,
    refresh: fetchTrialStatus,
    formattedBillingDate,
    isEndingSoon,
    isUrgent,
  };
}

export default useTrialStatus;
