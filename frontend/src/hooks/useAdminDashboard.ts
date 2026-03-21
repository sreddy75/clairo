'use client';

/**
 * Admin dashboard hooks using TanStack Query.
 *
 * Provides hooks for admin operations:
 * - useTenants: List tenants with filtering
 * - useTenant: Get tenant details
 * - useRevenueMetrics: Revenue analytics
 * - useTierChange: Tier change mutation
 * - useApplyCredit: Credit mutation
 * - useFeatureFlags: Feature flag operations
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import { useAuth } from '@clerk/nextjs';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import {
  applyCredit,
  changeTenantTier,
  deleteFeatureFlagOverride,
  getPlatformUsage,
  getRevenueMetrics,
  getRevenueTrends,
  getTenant,
  getTenantFeatureFlags,
  getTopUsers,
  listTenants,
  setAuthToken,
  setFeatureFlagOverride,
} from '@/lib/api/admin';
import type {
  CreditRequest,
  FeatureFlagOverrideRequest,
  FeatureKeyType,
  RevenueMetricsParams,
  RevenueTrendsParams,
  TenantListParams,
  TierChangeRequest,
} from '@/types/admin';

// =============================================================================
// Auth Token Hook
// =============================================================================

/**
 * Hook to sync Clerk auth token with admin API client.
 * Returns whether the token is ready for use.
 */
export function useAdminAuth() {
  const { getToken, isLoaded } = useAuth();
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    async function syncToken() {
      if (!isLoaded) return;
      try {
        const token = await getToken();
        setAuthToken(token);
        setIsReady(true);
      } catch {
        setAuthToken(null);
        setIsReady(true);
      }
    }
    syncToken();
  }, [getToken, isLoaded]);

  return isReady;
}

// =============================================================================
// Query Keys
// =============================================================================

export const adminQueryKeys = {
  all: ['admin'] as const,
  tenants: () => [...adminQueryKeys.all, 'tenants'] as const,
  tenantList: (params: TenantListParams) =>
    [...adminQueryKeys.tenants(), params] as const,
  tenant: (id: string) => [...adminQueryKeys.tenants(), id] as const,
  revenue: () => [...adminQueryKeys.all, 'revenue'] as const,
  revenueMetrics: (params: RevenueMetricsParams) =>
    [...adminQueryKeys.revenue(), 'metrics', params] as const,
  revenueTrends: (params: RevenueTrendsParams) =>
    [...adminQueryKeys.revenue(), 'trends', params] as const,
  featureFlags: (tenantId: string) =>
    [...adminQueryKeys.all, 'features', tenantId] as const,
  usage: () => [...adminQueryKeys.all, 'usage'] as const,
  topUsers: (metric: string) => [...adminQueryKeys.usage(), 'top', metric] as const,
};

// =============================================================================
// Tenant Queries
// =============================================================================

/**
 * Hook to list tenants with filtering, sorting, and pagination.
 */
export function useTenants(params: TenantListParams = {}) {
  const isAuthReady = useAdminAuth();
  return useQuery({
    queryKey: adminQueryKeys.tenantList(params),
    queryFn: () => listTenants(params),
    enabled: isAuthReady,
  });
}

/**
 * Hook to get detailed tenant information.
 */
export function useTenant(tenantId: string | null) {
  const isAuthReady = useAdminAuth();
  return useQuery({
    queryKey: adminQueryKeys.tenant(tenantId ?? ''),
    queryFn: () => getTenant(tenantId!),
    enabled: isAuthReady && !!tenantId,
  });
}

// =============================================================================
// Revenue Queries
// =============================================================================

/**
 * Hook to get revenue metrics.
 */
export function useRevenueMetrics(params: RevenueMetricsParams = {}) {
  const isAuthReady = useAdminAuth();
  return useQuery({
    queryKey: adminQueryKeys.revenueMetrics(params),
    queryFn: () => getRevenueMetrics(params),
    enabled: isAuthReady,
  });
}

/**
 * Hook to get revenue trends.
 */
export function useRevenueTrends(params: RevenueTrendsParams = {}) {
  const isAuthReady = useAdminAuth();
  return useQuery({
    queryKey: adminQueryKeys.revenueTrends(params),
    queryFn: () => getRevenueTrends(params),
    enabled: isAuthReady,
  });
}

// =============================================================================
// Usage Queries
// =============================================================================

/**
 * Hook to get platform usage metrics.
 */
export function usePlatformUsage() {
  const isAuthReady = useAdminAuth();
  return useQuery({
    queryKey: adminQueryKeys.usage(),
    queryFn: () => getPlatformUsage(),
    enabled: isAuthReady,
  });
}

/**
 * Hook to get top tenants by metric.
 */
export function useTopUsers(metric: string = 'clients', limit: number = 10) {
  const isAuthReady = useAdminAuth();
  return useQuery({
    queryKey: adminQueryKeys.topUsers(metric),
    queryFn: () => getTopUsers(metric, limit),
    enabled: isAuthReady,
  });
}

// =============================================================================
// Feature Flag Queries
// =============================================================================

/**
 * Hook to get feature flags for a tenant.
 */
export function useTenantFeatureFlags(tenantId: string | null) {
  const isAuthReady = useAdminAuth();
  return useQuery({
    queryKey: adminQueryKeys.featureFlags(tenantId ?? ''),
    queryFn: () => getTenantFeatureFlags(tenantId!),
    enabled: isAuthReady && !!tenantId,
  });
}

// =============================================================================
// Mutations
// =============================================================================

/**
 * Hook to change a tenant's subscription tier.
 */
export function useTierChange() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      tenantId,
      request,
    }: {
      tenantId: string;
      request: TierChangeRequest;
    }) => changeTenantTier(tenantId, request),
    onSuccess: (_data, variables) => {
      // Invalidate tenant and tenant list queries
      queryClient.invalidateQueries({
        queryKey: adminQueryKeys.tenant(variables.tenantId),
      });
      queryClient.invalidateQueries({
        queryKey: adminQueryKeys.tenants(),
      });
      // Also invalidate revenue metrics as tier changes affect MRR
      queryClient.invalidateQueries({
        queryKey: adminQueryKeys.revenue(),
      });
    },
  });
}

/**
 * Hook to apply credit to a tenant.
 */
export function useApplyCredit() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      tenantId,
      request,
    }: {
      tenantId: string;
      request: CreditRequest;
    }) => applyCredit(tenantId, request),
    onSuccess: (_data, variables) => {
      // Invalidate tenant query to refresh billing history
      queryClient.invalidateQueries({
        queryKey: adminQueryKeys.tenant(variables.tenantId),
      });
    },
  });
}

/**
 * Hook to set a feature flag override.
 */
export function useSetFeatureFlagOverride() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      tenantId,
      featureKey,
      request,
    }: {
      tenantId: string;
      featureKey: FeatureKeyType;
      request: FeatureFlagOverrideRequest;
    }) => setFeatureFlagOverride(tenantId, featureKey, request),
    onSuccess: (_data, variables) => {
      // Invalidate feature flags and tenant queries
      queryClient.invalidateQueries({
        queryKey: adminQueryKeys.featureFlags(variables.tenantId),
      });
      queryClient.invalidateQueries({
        queryKey: adminQueryKeys.tenant(variables.tenantId),
      });
    },
  });
}

/**
 * Hook to delete a feature flag override.
 */
export function useDeleteFeatureFlagOverride() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      tenantId,
      featureKey,
    }: {
      tenantId: string;
      featureKey: FeatureKeyType;
    }) => deleteFeatureFlagOverride(tenantId, featureKey),
    onSuccess: (_data, variables) => {
      // Invalidate feature flags and tenant queries
      queryClient.invalidateQueries({
        queryKey: adminQueryKeys.featureFlags(variables.tenantId),
      });
      queryClient.invalidateQueries({
        queryKey: adminQueryKeys.tenant(variables.tenantId),
      });
    },
  });
}

// =============================================================================
// Convenience Hooks
// =============================================================================

/**
 * Combined hook for common admin dashboard operations.
 *
 * @example
 * ```tsx
 * function AdminDashboard() {
 *   const { tenants, metrics, isLoading } = useAdminDashboard();
 *
 *   if (isLoading) return <Loading />;
 *
 *   return (
 *     <div>
 *       <MRRCard mrr={metrics.mrr} />
 *       <TenantTable tenants={tenants} />
 *     </div>
 *   );
 * }
 * ```
 */
export function useAdminDashboard(tenantParams: TenantListParams = {}) {
  // Auth is handled by individual hooks (useTenants, useRevenueMetrics)
  const tenantsQuery = useTenants(tenantParams);
  const metricsQuery = useRevenueMetrics();

  return {
    // Tenant data
    tenants: tenantsQuery.data?.tenants ?? [],
    totalTenants: tenantsQuery.data?.total ?? 0,
    hasMore: tenantsQuery.data?.has_more ?? false,

    // Revenue metrics
    metrics: metricsQuery.data ?? null,
    mrr: metricsQuery.data?.mrr?.current_cents ?? 0,
    mrrChange: metricsQuery.data?.mrr?.change_percentage ?? 0,
    churnRate: metricsQuery.data?.churn?.rate_percentage ?? 0,
    activeTenants: metricsQuery.data?.tenant_counts?.total_active ?? 0,

    // Loading states
    isLoading: tenantsQuery.isLoading || metricsQuery.isLoading,
    isTenantsLoading: tenantsQuery.isLoading,
    isMetricsLoading: metricsQuery.isLoading,

    // Error states
    error: tenantsQuery.error || metricsQuery.error,
    tenantsError: tenantsQuery.error,
    metricsError: metricsQuery.error,

    // Refresh functions
    refreshTenants: tenantsQuery.refetch,
    refreshMetrics: metricsQuery.refetch,
    refreshAll: () => {
      tenantsQuery.refetch();
      metricsQuery.refetch();
    },
  };
}

export default useAdminDashboard;
