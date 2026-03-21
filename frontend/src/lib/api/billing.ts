/**
 * Billing API client.
 *
 * Functions for interacting with subscription and billing endpoints.
 */

import type {
  AdminTenantUsageResponse,
  AdminUsageStats,
  BillingEventsResponse,
  CancelRequest,
  CheckoutRequest,
  CheckoutResponse,
  DowngradeRequest,
  FeaturesResponse,
  PortalResponse,
  SubscriptionResponse,
  SubscriptionTier,
  TiersResponse,
  TrialStatusResponse,
  UpgradeRequest,
  UpsellOpportunitiesResponse,
  UsageHistoryResponse,
  UsageMetrics,
} from '@/types/billing';

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
  options: RequestInit = {},
  requireAuth: boolean = true
): Promise<T> {
  const url = `${API_BASE}/api/v1${endpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  // Add auth token if required and available
  if (requireAuth && authToken) {
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

// =============================================================================
// Subscription Endpoints
// =============================================================================

/**
 * Get current subscription status.
 */
export async function getSubscription(): Promise<SubscriptionResponse> {
  return apiFetch<SubscriptionResponse>('/subscription');
}

/**
 * Get trial status for the current tenant.
 * Returns trial info including days remaining and billing date.
 */
export async function getTrialStatus(): Promise<TrialStatusResponse> {
  return apiFetch<TrialStatusResponse>('/trial-status');
}

/**
 * Create a Stripe Checkout session for subscription.
 */
export async function createCheckoutSession(
  request: CheckoutRequest
): Promise<CheckoutResponse> {
  return apiFetch<CheckoutResponse>('/subscription/checkout', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Create a Stripe Customer Portal session.
 */
export async function createPortalSession(): Promise<PortalResponse> {
  return apiFetch<PortalResponse>('/subscription/portal', {
    method: 'POST',
  });
}

/**
 * Upgrade subscription to a higher tier.
 */
export async function upgradeSubscription(
  request: UpgradeRequest
): Promise<SubscriptionResponse> {
  return apiFetch<SubscriptionResponse>('/subscription/upgrade', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Schedule a downgrade for the next billing cycle.
 */
export async function downgradeSubscription(
  request: DowngradeRequest
): Promise<SubscriptionResponse> {
  return apiFetch<SubscriptionResponse>('/subscription/downgrade', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Cancel subscription at end of current period.
 */
export async function cancelSubscription(
  request: CancelRequest = {}
): Promise<SubscriptionResponse> {
  return apiFetch<SubscriptionResponse>('/subscription/cancel', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// =============================================================================
// Features Endpoints
// =============================================================================

/**
 * Get feature access status for current tenant.
 */
export async function getFeatures(): Promise<FeaturesResponse> {
  return apiFetch<FeaturesResponse>('/features');
}

/**
 * List all available subscription tiers.
 * This endpoint is public (no auth required).
 */
export async function getTiers(): Promise<TiersResponse> {
  return apiFetch<TiersResponse>('/features/tiers', {}, false);
}

// =============================================================================
// Billing Events Endpoints
// =============================================================================

/**
 * List billing events for current tenant.
 */
export async function getBillingEvents(
  limit: number = 20,
  offset: number = 0
): Promise<BillingEventsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return apiFetch<BillingEventsResponse>(`/billing/events?${params}`);
}

// =============================================================================
// Usage Endpoints (Spec 020)
// =============================================================================

/**
 * Get current usage metrics for the tenant's billing dashboard.
 */
export async function getUsage(): Promise<UsageMetrics> {
  return apiFetch<UsageMetrics>('/billing/usage');
}

/**
 * Get usage history for the tenant.
 * Returns daily usage snapshots for trend analysis and charting.
 */
export async function getUsageHistory(months: number = 3): Promise<UsageHistoryResponse> {
  const params = new URLSearchParams({ months: String(months) });
  return apiFetch<UsageHistoryResponse>(`/billing/usage/history?${params}`);
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Redirect to Stripe Checkout.
 */
export async function redirectToCheckout(tier: string): Promise<void> {
  const { checkout_url } = await createCheckoutSession({
    tier: tier as SubscriptionTier,
  });
  window.location.href = checkout_url;
}

/**
 * Open Stripe Customer Portal.
 */
export async function openBillingPortal(): Promise<void> {
  const { portal_url } = await createPortalSession();
  window.location.href = portal_url;
}

// =============================================================================
// Admin Usage Analytics Endpoints (Spec 020)
// =============================================================================

/**
 * Get aggregate usage statistics for all tenants.
 * Admin only endpoint.
 */
export async function getAdminUsageStats(): Promise<AdminUsageStats> {
  return apiFetch<AdminUsageStats>('/admin/usage/stats');
}

/**
 * Get upsell opportunities - tenants approaching their limits.
 * Admin only endpoint.
 */
export async function getUpsellOpportunities(
  threshold: number = 80,
  tier?: SubscriptionTier,
  limit: number = 50
): Promise<UpsellOpportunitiesResponse> {
  const params = new URLSearchParams({
    threshold: String(threshold),
    limit: String(limit),
  });
  if (tier) {
    params.append('tier', tier);
  }
  return apiFetch<UpsellOpportunitiesResponse>(`/admin/usage/opportunities?${params}`);
}

/**
 * Get detailed usage for a specific tenant.
 * Admin only endpoint.
 */
export async function getAdminTenantUsage(tenantId: string): Promise<AdminTenantUsageResponse> {
  return apiFetch<AdminTenantUsageResponse>(`/admin/usage/tenant/${tenantId}`);
}
