'use client';

/**
 * TenantDetailCard Component
 *
 * Displays comprehensive tenant information in organized sections.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import {
  Building,
  Calendar,
  CreditCard,
  FileText,
  Mail,
  MessageSquare,
  Users,
} from 'lucide-react';

import type { TenantDetailResponse, SubscriptionTierType } from '@/types/admin';

interface TenantDetailCardProps {
  tenant: TenantDetailResponse | null;
  isLoading: boolean;
}

/**
 * Format cents to currency string.
 */
function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

/**
 * Format date to readable string.
 */
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('en-AU', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/**
 * Tier badge component.
 */
function TierBadge({ tier }: { tier: SubscriptionTierType }) {
  const colors: Record<SubscriptionTierType, string> = {
    starter: 'bg-muted text-foreground',
    professional: 'bg-primary/10 text-primary',
    growth: 'bg-purple-500/10 text-purple-700',
    enterprise: 'bg-status-warning/10 text-status-warning',
  };

  return (
    <span className={`text-sm font-medium px-3 py-1 rounded-full ${colors[tier]}`}>
      {tier.charAt(0).toUpperCase() + tier.slice(1)}
    </span>
  );
}

/**
 * Status badge component.
 */
function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <span
      className={`flex items-center gap-2 text-sm font-medium px-3 py-1 rounded-full ${
        isActive
          ? 'bg-status-success/10 text-status-success'
          : 'bg-status-danger/10 text-status-danger'
      }`}
    >
      <span
        className={`w-2 h-2 rounded-full ${
          isActive ? 'bg-status-success' : 'bg-status-danger'
        }`}
      />
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

/**
 * Info row component for consistent layout.
 */
function InfoRow({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {Icon && <Icon className="w-4 h-4" />}
        {label}
      </div>
      <div className="text-sm text-foreground font-medium">{value}</div>
    </div>
  );
}

/**
 * Section component for grouping info.
 */
function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-card rounded-xl border border-border">
      <div className="px-6 py-4 border-b border-border">
        <h3 className="text-lg font-semibold text-foreground">{title}</h3>
      </div>
      <div className="p-6 divide-y divide-border">{children}</div>
    </div>
  );
}

/**
 * Loading skeleton.
 */
function TenantDetailCardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="bg-card rounded-xl p-6 border border-border animate-pulse">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-muted rounded-full" />
          <div className="flex-1">
            <div className="h-6 bg-muted rounded w-48 mb-2" />
            <div className="h-4 bg-muted rounded w-32" />
          </div>
          <div className="flex gap-2">
            <div className="h-8 bg-muted rounded w-24" />
            <div className="h-8 bg-muted rounded w-20" />
          </div>
        </div>
      </div>

      {/* Sections skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="bg-card rounded-xl border border-border animate-pulse"
          >
            <div className="px-6 py-4 border-b border-border">
              <div className="h-5 bg-muted rounded w-32" />
            </div>
            <div className="p-6 space-y-4">
              {[1, 2, 3].map((j) => (
                <div key={j} className="flex justify-between">
                  <div className="h-4 bg-muted rounded w-24" />
                  <div className="h-4 bg-muted rounded w-32" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Main TenantDetailCard component.
 */
export function TenantDetailCard({ tenant, isLoading }: TenantDetailCardProps) {
  if (isLoading) {
    return <TenantDetailCardSkeleton />;
  }

  if (!tenant) {
    return (
      <div className="bg-card rounded-xl p-6 border border-border text-center">
        <p className="text-muted-foreground">No tenant data available</p>
      </div>
    );
  }

  const subscriptionStatusColors: Record<string, string> = {
    active: 'text-status-success',
    past_due: 'text-status-warning',
    canceled: 'text-status-danger',
    incomplete: 'text-status-warning',
    trialing: 'text-primary',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-card rounded-xl p-6 border border-border">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          {/* Avatar */}
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
            <span className="text-2xl font-bold text-white">
              {tenant.name.substring(0, 2).toUpperCase()}
            </span>
          </div>

          {/* Name and email */}
          <div className="flex-1">
            <h2 className="text-xl font-bold text-foreground">{tenant.name}</h2>
            {tenant.owner_email && (
              <p className="text-muted-foreground flex items-center gap-2 mt-1">
                <Mail className="w-4 h-4" />
                {tenant.owner_email}
              </p>
            )}
          </div>

          {/* Badges */}
          <div className="flex items-center gap-3">
            <TierBadge tier={tenant.tier} />
            <StatusBadge isActive={tenant.is_active} />
          </div>
        </div>
      </div>

      {/* Info sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Account Info */}
        <Section title="Account Information">
          <InfoRow
            label="Tenant ID"
            value={
              <code className="text-xs bg-muted px-2 py-1 rounded">
                {tenant.id}
              </code>
            }
            icon={Building}
          />
          <InfoRow
            label="Created"
            value={formatDate(tenant.created_at)}
            icon={Calendar}
          />
          <InfoRow
            label="User Count"
            value={tenant.user_count}
            icon={Users}
          />
        </Section>

        {/* Billing Info */}
        <Section title="Billing Information">
          <InfoRow
            label="Monthly Recurring Revenue"
            value={formatCurrency(tenant.mrr_cents)}
            icon={CreditCard}
          />
          <InfoRow
            label="Subscription Status"
            value={
              <span
                className={
                  subscriptionStatusColors[tenant.subscription_status] ||
                  'text-muted-foreground'
                }
              >
                {tenant.subscription_status.charAt(0).toUpperCase() +
                  tenant.subscription_status.slice(1).replace('_', ' ')}
              </span>
            }
          />
          <InfoRow
            label="Next Billing Date"
            value={formatDate(tenant.next_billing_date)}
            icon={Calendar}
          />
          {tenant.stripe_customer_id && (
            <InfoRow
              label="Stripe Customer"
              value={
                <code className="text-xs bg-muted px-2 py-1 rounded">
                  {tenant.stripe_customer_id}
                </code>
              }
            />
          )}
        </Section>

        {/* Usage Stats */}
        <Section title="Usage Statistics">
          <InfoRow
            label="Active Clients"
            value={
              <>
                {tenant.client_count}
                {tenant.client_limit && (
                  <span className="text-muted-foreground ml-1">
                    / {tenant.client_limit}
                  </span>
                )}
              </>
            }
            icon={Users}
          />
          <InfoRow
            label="AI Queries (This Month)"
            value={tenant.ai_queries_month}
            icon={MessageSquare}
          />
          <InfoRow
            label="Documents (This Month)"
            value={tenant.documents_month}
            icon={FileText}
          />
        </Section>

        {/* Feature Flags Summary */}
        <Section title="Feature Flags">
          <div className="space-y-2">
            {tenant.feature_flags.map((flag) => (
              <div
                key={flag.feature_key}
                className="flex items-center justify-between py-2"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground capitalize">
                    {flag.feature_key.replace(/_/g, ' ')}
                  </span>
                  {flag.is_overridden && (
                    <span className="text-xs bg-status-warning/10 text-status-warning px-2 py-0.5 rounded">
                      Overridden
                    </span>
                  )}
                </div>
                <span
                  className={`text-sm font-medium ${
                    flag.effective_value ? 'text-status-success' : 'text-muted-foreground'
                  }`}
                >
                  {flag.effective_value ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}

export default TenantDetailCard;
