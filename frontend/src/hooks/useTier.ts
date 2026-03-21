'use client';

import { useCallback, useEffect, useState } from 'react';

import { getFeatures } from '@/lib/api/billing';
import type { FeaturesResponse, SubscriptionTier } from '@/types/billing';
import { TIER_FEATURES } from '@/types/billing';

interface TierState {
  tier: SubscriptionTier | null;
  isLoading: boolean;
  error: string | null;
  features: FeaturesResponse | null;
}

interface UseTierReturn extends TierState {
  /**
   * Check if a specific feature is available.
   */
  canAccess: (feature: string) => boolean;

  /**
   * Get the client limit for the current tier.
   */
  clientLimit: number | null;

  /**
   * Get the current client count.
   */
  clientCount: number;

  /**
   * Check if the tenant is at or over client limit.
   */
  isAtLimit: boolean;

  /**
   * Check if the tenant is approaching client limit (>= 80%).
   */
  isApproachingLimit: boolean;

  /**
   * Refresh tier information.
   */
  refresh: () => Promise<void>;

  /**
   * Get the minimum tier required for a feature.
   */
  getMinimumTier: (feature: string) => SubscriptionTier;

  /**
   * Check if a tier is higher than current.
   */
  isUpgrade: (tier: SubscriptionTier) => boolean;
}

const TIER_ORDER: SubscriptionTier[] = ['starter', 'professional', 'growth', 'enterprise'];

const FEATURE_MINIMUM_TIER: Record<string, SubscriptionTier> = {
  ai_insights: 'starter',
  client_portal: 'professional',
  custom_triggers: 'professional',
  api_access: 'growth',
  knowledge_base: 'professional',
  magic_zone: 'professional',
};

/**
 * Hook for managing tier-based feature access.
 * Fetches and caches tier information for the current tenant.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { tier, canAccess, isAtLimit, clientLimit, clientCount } = useTier();
 *
 *   if (!canAccess('custom_triggers')) {
 *     return <UpgradePrompt feature="custom_triggers" />;
 *   }
 *
 *   return <TriggersList />;
 * }
 * ```
 */
export function useTier(): UseTierReturn {
  const [state, setState] = useState<TierState>({
    tier: null,
    isLoading: true,
    error: null,
    features: null,
  });

  const fetchFeatures = useCallback(async () => {
    try {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      const features = await getFeatures();
      setState({
        tier: features.tier,
        isLoading: false,
        error: null,
        features,
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: 'Failed to load tier information',
      }));
      console.error('Failed to fetch tier features:', err);
    }
  }, []);

  useEffect(() => {
    fetchFeatures();
  }, [fetchFeatures]);

  const canAccess = useCallback(
    (feature: string): boolean => {
      if (!state.features) return false;
      return state.features.can_access[feature] ?? false;
    },
    [state.features]
  );

  const getMinimumTier = useCallback(
    (feature: string): SubscriptionTier => {
      return FEATURE_MINIMUM_TIER[feature] ?? 'professional';
    },
    []
  );

  const isUpgrade = useCallback(
    (tier: SubscriptionTier): boolean => {
      if (!state.tier) return false;
      const currentIndex = TIER_ORDER.indexOf(state.tier);
      const newIndex = TIER_ORDER.indexOf(tier);
      return newIndex > currentIndex;
    },
    [state.tier]
  );

  // Derive client limit info
  const tierFeatures = state.tier ? TIER_FEATURES[state.tier] : null;
  const clientLimit = tierFeatures?.max_clients ?? null;
  const clientCount = state.features?.features?.max_clients
    ? 0 // Would need to get from subscription response
    : 0;

  const isAtLimit = clientLimit !== null && clientCount >= clientLimit;
  const isApproachingLimit =
    clientLimit !== null && clientCount >= clientLimit * 0.8;

  return {
    ...state,
    canAccess,
    clientLimit,
    clientCount,
    isAtLimit,
    isApproachingLimit,
    refresh: fetchFeatures,
    getMinimumTier,
    isUpgrade,
  };
}

export default useTier;
