/**
 * Admin API client.
 *
 * Functions for admin dashboard operations:
 * - Tenant management
 * - Revenue analytics
 * - Subscription management
 * - Feature flag overrides
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import type {
  CreditRequest,
  CreditResponse,
  FeatureFlagOverrideRequest,
  FeatureFlagOverrideResponse,
  FeatureFlagsResponse,
  FeatureKeyType,
  PlatformUsageMetrics,
  RevenueMetricsParams,
  RevenueMetricsResponse,
  RevenueTrendsParams,
  RevenueTrendsResponse,
  TenantDetailResponse,
  TenantListParams,
  TenantListResponse,
  TierChangeRequest,
  TierChangeResponse,
  TopUsersResponse,
} from '@/types/admin';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Token storage for authenticated requests
let authToken: string | null = null;

/**
 * Set the auth token for API requests.
 * Call this with the Clerk token when the app initializes.
 */
export function setAuthToken(token: string | null): void {
  authToken = token;
}

// =============================================================================
// Helper Functions
// =============================================================================

async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}/api/v1${endpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  // Add auth token if available
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.error || error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

function buildQueryString(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value));
    }
  });

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}

// =============================================================================
// Tenant Management
// =============================================================================

/**
 * List all tenants with filtering, sorting, and pagination.
 */
export async function listTenants(
  params: TenantListParams = {}
): Promise<TenantListResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiFetch<TenantListResponse>(`/admin/tenants${queryString}`);
}

/**
 * Get detailed tenant information.
 */
export async function getTenant(tenantId: string): Promise<TenantDetailResponse> {
  return apiFetch<TenantDetailResponse>(`/admin/tenants/${tenantId}`);
}

// =============================================================================
// Revenue Analytics
// =============================================================================

/**
 * Get aggregate revenue metrics (MRR, churn, expansion).
 */
export async function getRevenueMetrics(
  params: RevenueMetricsParams = {}
): Promise<RevenueMetricsResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiFetch<RevenueMetricsResponse>(`/admin/revenue/metrics${queryString}`);
}

/**
 * Get revenue trends over time.
 */
export async function getRevenueTrends(
  params: RevenueTrendsParams = {}
): Promise<RevenueTrendsResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiFetch<RevenueTrendsResponse>(`/admin/revenue/trends${queryString}`);
}

// =============================================================================
// Subscription Management
// =============================================================================

/**
 * Change a tenant's subscription tier.
 */
export async function changeTenantTier(
  tenantId: string,
  request: TierChangeRequest
): Promise<TierChangeResponse> {
  return apiFetch<TierChangeResponse>(`/admin/tenants/${tenantId}/tier`, {
    method: 'PUT',
    body: JSON.stringify(request),
  });
}

/**
 * Apply a credit to a tenant's account.
 */
export async function applyCredit(
  tenantId: string,
  request: CreditRequest
): Promise<CreditResponse> {
  return apiFetch<CreditResponse>(`/admin/tenants/${tenantId}/credit`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// =============================================================================
// Feature Flags
// =============================================================================

/**
 * Get all feature flags for a tenant.
 */
export async function getTenantFeatureFlags(
  tenantId: string
): Promise<FeatureFlagsResponse> {
  return apiFetch<FeatureFlagsResponse>(`/admin/tenants/${tenantId}/features`);
}

/**
 * Set a feature flag override for a tenant.
 */
export async function setFeatureFlagOverride(
  tenantId: string,
  featureKey: FeatureKeyType,
  request: FeatureFlagOverrideRequest
): Promise<FeatureFlagOverrideResponse> {
  return apiFetch<FeatureFlagOverrideResponse>(
    `/admin/tenants/${tenantId}/features/${featureKey}`,
    {
      method: 'PUT',
      body: JSON.stringify(request),
    }
  );
}

/**
 * Delete a feature flag override (revert to tier default).
 */
export async function deleteFeatureFlagOverride(
  tenantId: string,
  featureKey: FeatureKeyType
): Promise<FeatureFlagOverrideResponse> {
  return apiFetch<FeatureFlagOverrideResponse>(
    `/admin/tenants/${tenantId}/features/${featureKey}`,
    {
      method: 'DELETE',
    }
  );
}

// =============================================================================
// Usage Analytics
// =============================================================================

/**
 * Get aggregate platform usage metrics.
 */
export async function getPlatformUsage(): Promise<PlatformUsageMetrics> {
  return apiFetch<PlatformUsageMetrics>('/admin/usage');
}

/**
 * Get top tenants by a specific metric.
 */
export async function getTopUsers(
  metric: string = 'clients',
  limit: number = 10
): Promise<TopUsersResponse> {
  const queryString = buildQueryString({ metric, limit });
  return apiFetch<TopUsersResponse>(`/admin/usage/top${queryString}`);
}
