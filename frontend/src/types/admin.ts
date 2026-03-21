/**
 * Admin dashboard type definitions.
 *
 * Types for internal admin operations:
 * - Tenant management
 * - Revenue analytics
 * - Subscription management
 * - Feature flag overrides
 *
 * Spec 022: Admin Dashboard (Internal)
 */

// =============================================================================
// Enums and Literals
// =============================================================================

export type SubscriptionTierType = 'starter' | 'professional' | 'growth' | 'enterprise';

export type FeatureKeyType =
  | 'ai_insights'
  | 'client_portal'
  | 'custom_triggers'
  | 'api_access'
  | 'knowledge_base'
  | 'magic_zone';

export type CreditType = 'one_time' | 'recurring';

export type TenantStatusFilter = 'active' | 'inactive' | 'all';

export type TenantSortField = 'name' | 'created_at' | 'mrr' | 'client_count';

export type SortOrder = 'asc' | 'desc';

export type RevenuePeriod = 'daily' | 'weekly' | 'monthly';

// =============================================================================
// Tenant Types
// =============================================================================

export interface TenantSummary {
  id: string;
  name: string;
  owner_email: string | null;
  tier: SubscriptionTierType;
  client_count: number;
  client_limit: number | null;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  mrr_cents: number;
}

export interface TenantListResponse {
  tenants: TenantSummary[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

export interface BillingEventSummary {
  id: string;
  event_type: string;
  created_at: string;
  details: Record<string, unknown>;
}

export interface ActivityItem {
  type: string;
  description: string;
  timestamp: string;
  user: string | null;
}

export interface FeatureFlagStatus {
  feature_key: FeatureKeyType;
  tier_default: boolean;
  override_value: boolean | null;
  effective_value: boolean;
  is_overridden: boolean;
  override_reason: string | null;
  override_created_at: string | null;
  override_created_by: string | null;
}

export interface TenantDetailResponse {
  id: string;
  name: string;
  owner_email: string | null;
  tier: SubscriptionTierType;
  is_active: boolean;
  created_at: string;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  subscription_status: string;
  next_billing_date: string | null;
  mrr_cents: number;
  client_count: number;
  client_limit: number | null;
  ai_queries_month: number;
  documents_month: number;
  user_count: number;
  subscription_history: BillingEventSummary[];
  recent_activity: ActivityItem[];
  feature_flags: FeatureFlagStatus[];
}

// =============================================================================
// Revenue Analytics Types
// =============================================================================

export interface MRRMetrics {
  current_cents: number;
  previous_cents: number;
  change_percentage: number;
}

export interface ChurnMetrics {
  rate_percentage: number;
  lost_cents: number;
  tenant_count: number;
}

export interface ExpansionMetrics {
  amount_cents: number;
  upgrade_count: number;
  downgrade_count: number;
}

export interface TenantCounts {
  total_active: number;
  by_tier: Record<string, number>;
}

export interface PeriodRange {
  start_date: string;
  end_date: string;
}

export interface RevenueMetricsResponse {
  period: PeriodRange;
  mrr: MRRMetrics;
  churn: ChurnMetrics;
  expansion: ExpansionMetrics;
  tenant_counts: TenantCounts;
}

export interface RevenueTrendDataPoint {
  date: string;
  mrr_cents: number;
  tenant_count: number;
  new_subscriptions: number;
  churned_subscriptions: number;
}

export interface RevenueTrendsResponse {
  period: RevenuePeriod;
  data_points: RevenueTrendDataPoint[];
}

// =============================================================================
// Subscription Management Types
// =============================================================================

export interface TierChangeRequest {
  new_tier: SubscriptionTierType;
  reason: string;
  force_downgrade?: boolean;
}

export interface TierChangeResponse {
  success: boolean;
  tenant_id: string;
  old_tier: SubscriptionTierType;
  new_tier: SubscriptionTierType;
  effective_at: string;
  stripe_subscription_id: string | null;
  billing_event_id: string;
}

export interface TierChangeConflict {
  error: string;
  code: 'excess_clients' | 'pending_payment' | 'stripe_error';
  details: Record<string, unknown>;
}

export interface CreditRequest {
  amount_cents: number;
  credit_type: CreditType;
  reason: string;
}

export interface CreditResponse {
  success: boolean;
  tenant_id: string;
  amount_cents: number;
  credit_type: CreditType;
  effective_at: string;
  billing_event_id: string;
}

// =============================================================================
// Feature Flag Types
// =============================================================================

export interface FeatureFlagsResponse {
  tenant_id: string;
  tier: SubscriptionTierType;
  flags: FeatureFlagStatus[];
}

export interface FeatureFlagOverrideRequest {
  value: boolean;
  reason: string;
}

export interface FeatureFlagOverrideResponse {
  success: boolean;
  tenant_id: string;
  feature_key: FeatureKeyType;
  old_value: boolean | null;
  new_value: boolean;
  effective_at: string;
}

// =============================================================================
// Usage Analytics Types
// =============================================================================

export interface PlatformUsageMetrics {
  total_clients: number;
  total_syncs: number;
  total_ai_queries: number;
  by_tier: Record<string, Record<string, number>>;
}

export interface TopUserEntry {
  tenant_id: string;
  tenant_name: string;
  value: number;
}

export interface TopUsersResponse {
  metric: string;
  users: TopUserEntry[];
}

// =============================================================================
// Query Parameters
// =============================================================================

export interface TenantListParams {
  search?: string;
  tier?: SubscriptionTierType;
  status?: TenantStatusFilter;
  sort_by?: TenantSortField;
  sort_order?: SortOrder;
  page?: number;
  limit?: number;
}

export interface RevenueMetricsParams {
  period_days?: number;
}

export interface RevenueTrendsParams {
  period?: RevenuePeriod;
  lookback_days?: number;
}
