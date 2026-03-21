'use client';

import { useCallback, useEffect, useState } from 'react';

import { getUsage } from '@/lib/api/billing';
import type { UsageMetrics, SubscriptionTier } from '@/types/billing';

interface UsageState {
  data: UsageMetrics | null;
  isLoading: boolean;
  error: string | null;
}

interface UseUsageReturn extends UsageState {
  /**
   * Refresh usage data.
   */
  refresh: () => Promise<void>;

  /**
   * Client count.
   */
  clientCount: number;

  /**
   * Client limit (null if unlimited).
   */
  clientLimit: number | null;

  /**
   * Usage percentage (null if unlimited).
   */
  percentage: number | null;

  /**
   * Whether at client limit.
   */
  isAtLimit: boolean;

  /**
   * Whether approaching limit (>= 80%).
   */
  isApproachingLimit: boolean;

  /**
   * Current tier.
   */
  tier: SubscriptionTier | null;

  /**
   * Next available tier for upgrade.
   */
  nextTier: SubscriptionTier | null;

  /**
   * Threshold warning level if any.
   */
  thresholdWarning: '80%' | '90%' | '100%' | null;

  /**
   * AI queries this billing period.
   */
  aiQueriesMonth: number;

  /**
   * Documents processed this billing period.
   */
  documentsMonth: number;
}

/**
 * Hook for fetching and managing usage metrics.
 *
 * @example
 * ```tsx
 * function UsageDashboard() {
 *   const {
 *     clientCount,
 *     clientLimit,
 *     percentage,
 *     isApproachingLimit,
 *     thresholdWarning,
 *     isLoading,
 *   } = useUsage();
 *
 *   if (isLoading) return <Skeleton />;
 *
 *   return (
 *     <div>
 *       <UsageProgressBar current={clientCount} limit={clientLimit} />
 *       {isApproachingLimit && <UpgradePrompt />}
 *     </div>
 *   );
 * }
 * ```
 */
export function useUsage(): UseUsageReturn {
  const [state, setState] = useState<UsageState>({
    data: null,
    isLoading: true,
    error: null,
  });

  const fetchUsage = useCallback(async () => {
    try {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      const data = await getUsage();
      setState({
        data,
        isLoading: false,
        error: null,
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: 'Failed to load usage data',
      }));
      console.error('Failed to fetch usage:', err);
    }
  }, []);

  useEffect(() => {
    fetchUsage();
  }, [fetchUsage]);

  // Derive values from data
  const { data } = state;

  return {
    ...state,
    refresh: fetchUsage,
    clientCount: data?.client_count ?? 0,
    clientLimit: data?.client_limit ?? null,
    percentage: data?.client_percentage ?? null,
    isAtLimit: data?.is_at_limit ?? false,
    isApproachingLimit: data?.is_approaching_limit ?? false,
    tier: data?.tier ?? null,
    nextTier: data?.next_tier ?? null,
    thresholdWarning: data?.threshold_warning ?? null,
    aiQueriesMonth: data?.ai_queries_month ?? 0,
    documentsMonth: data?.documents_month ?? 0,
  };
}

export default useUsage;
