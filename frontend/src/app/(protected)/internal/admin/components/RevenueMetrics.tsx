'use client';

/**
 * RevenueMetrics Component
 *
 * Displays MRR, churn, and expansion metrics cards.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import {
  ArrowDownIcon,
  ArrowUpIcon,
  DollarSign,
  TrendingDown,
  TrendingUp,
  Users,
} from 'lucide-react';

import type { RevenueMetricsResponse } from '@/types/admin';

interface RevenueMetricsProps {
  data: RevenueMetricsResponse | null;
  isLoading: boolean;
}

/**
 * Format cents to currency string.
 */
function formatCents(cents: number): string {
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

/**
 * Metric card component.
 */
function MetricCard({
  title,
  value,
  subtitle,
  change,
  changeLabel,
  icon: Icon,
  iconColor,
  isPositiveGood = true,
}: {
  title: string;
  value: string;
  subtitle?: string;
  change?: number;
  changeLabel?: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
  isPositiveGood?: boolean;
}) {
  const hasChange = change !== undefined && change !== null;
  const isPositive = (change ?? 0) >= 0;
  const isGood = isPositiveGood ? isPositive : !isPositive;

  return (
    <div className="bg-card rounded-xl p-4 border border-border">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold tabular-nums text-foreground mt-2">{value}</p>
          {subtitle && (
            <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
          )}
          {hasChange && (
            <div className="flex items-center gap-1 mt-3">
              {isPositive ? (
                <ArrowUpIcon
                  className={`w-4 h-4 ${isGood ? 'text-status-success' : 'text-status-danger'}`}
                />
              ) : (
                <ArrowDownIcon
                  className={`w-4 h-4 ${isGood ? 'text-status-success' : 'text-status-danger'}`}
                />
              )}
              <span
                className={`text-sm font-medium ${
                  isGood ? 'text-status-success' : 'text-status-danger'
                }`}
              >
                {Math.abs(change).toFixed(1)}%
              </span>
              {changeLabel && (
                <span className="text-sm text-muted-foreground">{changeLabel}</span>
              )}
            </div>
          )}
        </div>
        <div className={`p-3 rounded-lg ${iconColor}`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  );
}

/**
 * Loading skeleton for metric card.
 */
function MetricCardSkeleton() {
  return (
    <div className="bg-card rounded-xl p-4 border border-border animate-pulse">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="h-4 bg-muted rounded w-24 mb-3" />
          <div className="h-8 bg-muted rounded w-32 mb-2" />
          <div className="h-4 bg-muted rounded w-20" />
        </div>
        <div className="w-12 h-12 bg-muted rounded-lg" />
      </div>
    </div>
  );
}

/**
 * Tier breakdown component.
 */
function TierBreakdown({
  tenantCounts,
  isLoading,
}: {
  tenantCounts: Record<string, number> | null;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="bg-card rounded-xl p-4 border border-border">
        <div className="h-5 bg-muted rounded w-32 mb-4 animate-pulse" />
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="animate-pulse">
              <div className="h-3 bg-muted rounded w-full mb-1" />
              <div className="h-2 bg-muted rounded w-full" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const total = Object.values(tenantCounts || {}).reduce((a, b) => a + b, 0);
  const tiers = ['starter', 'professional', 'growth', 'enterprise'];
  const colors: Record<string, string> = {
    starter: 'bg-muted-foreground',
    professional: 'bg-primary',
    growth: 'bg-purple-500',
    enterprise: 'bg-status-warning',
  };

  return (
    <div className="bg-card rounded-xl p-4 border border-border">
      <h3 className="text-lg font-semibold text-foreground mb-4">
        Customers by Tier
      </h3>
      <div className="space-y-4">
        {tiers.map((tier) => {
          const count = tenantCounts?.[tier] ?? 0;
          const percentage = total > 0 ? (count / total) * 100 : 0;

          return (
            <div key={tier}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-foreground capitalize">
                  {tier}
                </span>
                <span className="text-sm text-muted-foreground">
                  {count} ({percentage.toFixed(0)}%)
                </span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full ${colors[tier]} rounded-full transition-all duration-500`}
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 pt-4 border-t border-border">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-muted-foreground">Total Active</span>
          <span className="text-lg font-bold text-foreground">{total}</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Main RevenueMetrics component.
 */
export function RevenueMetrics({ data, isLoading }: RevenueMetricsProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <MetricCardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Main metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Monthly Recurring Revenue"
          value={formatCents(data?.mrr?.current_cents ?? 0)}
          subtitle={`Previous: ${formatCents(data?.mrr?.previous_cents ?? 0)}`}
          change={data?.mrr?.change_percentage}
          changeLabel="vs last period"
          icon={DollarSign}
          iconColor="bg-status-success"
        />

        <MetricCard
          title="Active Customers"
          value={String(data?.tenant_counts?.total_active ?? 0)}
          icon={Users}
          iconColor="bg-primary"
        />

        <MetricCard
          title="Churn Rate"
          value={`${(data?.churn?.rate_percentage ?? 0).toFixed(1)}%`}
          subtitle={`${data?.churn?.tenant_count ?? 0} churned (${formatCents(data?.churn?.lost_cents ?? 0)} lost)`}
          icon={TrendingDown}
          iconColor="bg-status-danger"
          isPositiveGood={false}
        />

        <MetricCard
          title="Expansion Revenue"
          value={formatCents(data?.expansion?.amount_cents ?? 0)}
          subtitle={`${data?.expansion?.upgrade_count ?? 0} upgrades, ${data?.expansion?.downgrade_count ?? 0} downgrades`}
          icon={TrendingUp}
          iconColor="bg-purple-500"
        />
      </div>

      {/* Secondary info */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <div className="bg-card rounded-xl p-4 border border-border">
            <h3 className="text-lg font-semibold text-foreground mb-4">
              Period Summary
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Period Start</p>
                <p className="text-foreground font-medium">
                  {data?.period?.start_date
                    ? new Date(data.period.start_date).toLocaleDateString('en-AU', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })
                    : '-'}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Period End</p>
                <p className="text-foreground font-medium">
                  {data?.period?.end_date
                    ? new Date(data.period.end_date).toLocaleDateString('en-AU', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })
                    : '-'}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Net MRR Change</p>
                <p
                  className={`font-medium ${
                    (data?.mrr?.current_cents ?? 0) >= (data?.mrr?.previous_cents ?? 0)
                      ? 'text-status-success'
                      : 'text-status-danger'
                  }`}
                >
                  {formatCents(
                    (data?.mrr?.current_cents ?? 0) - (data?.mrr?.previous_cents ?? 0)
                  )}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Net Expansion</p>
                <p className="text-foreground font-medium">
                  {(data?.expansion?.upgrade_count ?? 0) -
                    (data?.expansion?.downgrade_count ?? 0)}{' '}
                  net upgrades
                </p>
              </div>
            </div>
          </div>
        </div>

        <TierBreakdown
          tenantCounts={data?.tenant_counts?.by_tier ?? null}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}

export default RevenueMetrics;
