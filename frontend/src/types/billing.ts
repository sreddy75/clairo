/**
 * Billing module TypeScript types.
 *
 * Matches the backend Pydantic schemas for subscription management.
 */

// =============================================================================
// Enums
// =============================================================================

export type SubscriptionTier = 'starter' | 'professional' | 'growth' | 'enterprise';

export type SubscriptionStatus =
  | 'trial'
  | 'active'
  | 'past_due'
  | 'cancelled'
  | 'suspended'
  | 'grandfathered';

export type AIInsightsLevel = 'basic' | 'full';

// =============================================================================
// Feature & Tier Info
// =============================================================================

export interface TierFeatures {
  max_clients: number | null;
  ai_insights: AIInsightsLevel;
  client_portal: boolean;
  custom_triggers: boolean;
  api_access: boolean;
  knowledge_base: boolean;
  magic_zone: boolean;
}

export interface UsageInfo {
  client_count: number;
  client_limit: number | null;
  is_at_limit: boolean;
  is_approaching_limit: boolean;
  percentage_used: number | null;
}

export interface TierInfo {
  name: SubscriptionTier;
  display_name: string;
  price_monthly: number;
  price_id: string | null;
  features: TierFeatures;
  highlights: string[];
}

export interface ScheduledChange {
  new_tier: SubscriptionTier | null;
  effective_date: string;
  is_cancellation?: boolean;
}

// =============================================================================
// Subscription Responses
// =============================================================================

export interface SubscriptionResponse {
  tier: SubscriptionTier;
  status: SubscriptionStatus;
  stripe_customer_id: string | null;
  current_period_end: string | null;
  scheduled_change: ScheduledChange | null;
  features: TierFeatures;
  usage: UsageInfo;
}

export interface FeaturesResponse {
  tier: SubscriptionTier;
  features: TierFeatures;
  can_access: Record<string, boolean>;
}

export interface TiersResponse {
  tiers: TierInfo[];
}

// =============================================================================
// Checkout
// =============================================================================

export interface CheckoutRequest {
  tier: SubscriptionTier;
  success_url?: string;
  cancel_url?: string;
}

export interface CheckoutResponse {
  checkout_url: string;
  session_id: string;
}

export interface PortalResponse {
  portal_url: string;
}

// =============================================================================
// Subscription Management
// =============================================================================

export interface UpgradeRequest {
  new_tier: SubscriptionTier;
}

export interface DowngradeRequest {
  new_tier: SubscriptionTier;
}

export interface CancelRequest {
  reason?: string;
  feedback?: string;
}

// =============================================================================
// Trial Status (Spec 021)
// =============================================================================

export interface TrialStatusResponse {
  is_trial: boolean;
  tier: SubscriptionTier;
  trial_end_date: string | null;
  days_remaining: number | null;
  price_monthly: number;
  billing_date: string | null;
}

// =============================================================================
// Billing Events
// =============================================================================

export interface BillingEvent {
  id: string;
  event_type: string;
  amount_cents: number | null;
  currency: string;
  status: string;
  created_at: string;
}

export interface BillingEventsResponse {
  events: BillingEvent[];
  total: number;
  limit: number;
  offset: number;
}

// =============================================================================
// Usage Tracking (Spec 020)
// =============================================================================

export type ThresholdWarning = '80%' | '90%' | '100%';

export type UsageAlertType = 'threshold_80' | 'threshold_90' | 'limit_reached';

export interface UsageMetrics {
  client_count: number;
  client_limit: number | null;
  client_percentage: number | null;
  ai_queries_month: number;
  documents_month: number;
  is_at_limit: boolean;
  is_approaching_limit: boolean;
  threshold_warning: ThresholdWarning | null;
  tier: SubscriptionTier;
  next_tier: SubscriptionTier | null;
}

export interface UsageSnapshot {
  id: string;
  captured_at: string;
  client_count: number;
  ai_queries_count: number;
  documents_count: number;
  tier: string;
  client_limit: number | null;
}

export interface UsageHistoryResponse {
  snapshots: UsageSnapshot[];
  period_start: string;
  period_end: string;
}

export interface UsageAlert {
  id: string;
  alert_type: UsageAlertType;
  billing_period: string;
  threshold_percentage: number;
  client_count_at_alert: number;
  client_limit_at_alert: number;
  sent_at: string;
}

export interface UsageAlertsResponse {
  alerts: UsageAlert[];
  total: number;
}

// =============================================================================
// Error Responses
// =============================================================================

export interface FeatureGatedError {
  error: string;
  code: string;
  feature: string;
  required_tier: SubscriptionTier;
  current_tier: SubscriptionTier;
}

export interface ClientLimitError {
  error: string;
  code: string;
  current_count: number;
  limit: number;
  required_tier: SubscriptionTier;
}

// =============================================================================
// Feature Names (for type-safe feature checks)
// =============================================================================

export type FeatureName =
  | 'ai_insights'
  | 'client_portal'
  | 'custom_triggers'
  | 'api_access'
  | 'knowledge_base'
  | 'magic_zone';

// =============================================================================
// Tier Order (for comparison)
// =============================================================================

export const TIER_ORDER: SubscriptionTier[] = [
  'starter',
  'professional',
  'growth',
  'enterprise',
];

export function compareTiers(a: SubscriptionTier, b: SubscriptionTier): number {
  return TIER_ORDER.indexOf(a) - TIER_ORDER.indexOf(b);
}

export function isHigherTier(a: SubscriptionTier, b: SubscriptionTier): boolean {
  return compareTiers(a, b) > 0;
}

// =============================================================================
// Default Features by Tier (client-side reference)
// =============================================================================

export const TIER_FEATURES: Record<SubscriptionTier, TierFeatures> = {
  starter: {
    max_clients: 25,
    ai_insights: 'basic',
    client_portal: false,
    custom_triggers: false,
    api_access: false,
    knowledge_base: false,
    magic_zone: false,
  },
  professional: {
    max_clients: 100,
    ai_insights: 'full',
    client_portal: true,
    custom_triggers: true,
    api_access: false,
    knowledge_base: true,
    magic_zone: true,
  },
  growth: {
    max_clients: 250,
    ai_insights: 'full',
    client_portal: true,
    custom_triggers: true,
    api_access: true,
    knowledge_base: true,
    magic_zone: true,
  },
  enterprise: {
    max_clients: null,
    ai_insights: 'full',
    client_portal: true,
    custom_triggers: true,
    api_access: true,
    knowledge_base: true,
    magic_zone: true,
  },
};

// =============================================================================
// Pricing (in cents AUD)
// =============================================================================

export const TIER_PRICING: Record<SubscriptionTier, number | null> = {
  starter: 9900,       // $99
  professional: 29900, // $299
  growth: 59900,       // $599
  enterprise: null,    // Custom
};

export function formatPrice(cents: number | null): string {
  if (cents === null) return 'Custom';
  return `$${(cents / 100).toFixed(0)}`;
}

// =============================================================================
// Admin Usage Analytics (Spec 020 - User Story 4)
// =============================================================================

export interface AdminUsageStats {
  total_tenants: number;
  total_clients: number;
  average_clients_per_tenant: number;
  tenants_at_limit: number;
  tenants_approaching_limit: number;
  tenants_by_tier: Record<SubscriptionTier, number>;
}

export interface UpsellOpportunity {
  tenant_id: string;
  tenant_name: string;
  owner_email: string;
  current_tier: SubscriptionTier;
  client_count: number;
  client_limit: number;
  percentage_used: number;
}

export interface UpsellOpportunitiesResponse {
  opportunities: UpsellOpportunity[];
  total: number;
}

export interface AdminTenantUsageResponse {
  tenant_id: string;
  tenant_name: string;
  tier: SubscriptionTier;
  usage: UsageMetrics;
  history: UsageSnapshot[];
  alerts: UsageAlert[];
}
