'use client';

/**
 * UsageAnalytics Component
 *
 * Displays aggregate platform usage metrics.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import { BarChart3, FileText, MessageSquare, Users } from 'lucide-react';

import { usePlatformUsage } from '@/hooks/useAdminDashboard';

/**
 * Usage metric card.
 */
function MetricCard({
  title,
  value,
  icon: Icon,
  iconColor,
  isLoading,
}: {
  title: string;
  value: number | string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
  isLoading: boolean;
}) {
  return (
    <div className="bg-card rounded-xl p-6 border border-border">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          {isLoading ? (
            <div className="h-8 w-24 bg-muted rounded animate-pulse mt-2" />
          ) : (
            <p className="text-2xl font-bold text-foreground mt-1">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
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
 * Tier breakdown bar chart.
 */
function TierBreakdown({
  data,
  isLoading,
}: {
  data: Record<string, Record<string, number>> | null;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="bg-card rounded-xl p-6 border border-border">
        <div className="h-5 bg-muted rounded w-40 mb-4 animate-pulse" />
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="animate-pulse">
              <div className="h-4 bg-muted rounded w-24 mb-2" />
              <div className="h-6 bg-muted rounded w-full" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const tiers = ['starter', 'professional', 'growth', 'enterprise'];
  const colors: Record<string, string> = {
    starter: 'bg-muted-foreground',
    professional: 'bg-primary',
    growth: 'bg-purple-500',
    enterprise: 'bg-status-warning',
  };

  // Calculate totals per tier
  const tierTotals = tiers.map((tier) => {
    const tierData = data?.[tier] ?? {};
    return {
      tier,
      clients: tierData.clients ?? 0,
      syncs: tierData.syncs ?? 0,
      aiQueries: tierData.ai_queries ?? 0,
    };
  });

  const maxClients = Math.max(...tierTotals.map((t) => t.clients), 1);

  return (
    <div className="bg-card rounded-xl p-6 border border-border">
      <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
        <BarChart3 className="w-5 h-5 text-primary" />
        Usage by Tier
      </h3>
      <div className="space-y-4">
        {tierTotals.map(({ tier, clients, syncs, aiQueries }) => (
          <div key={tier}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-foreground capitalize">
                {tier}
              </span>
              <span className="text-sm text-muted-foreground">
                {clients} clients | {syncs} syncs | {aiQueries} AI queries
              </span>
            </div>
            <div className="h-4 bg-muted rounded-full overflow-hidden">
              <div
                className={`h-full ${colors[tier]} rounded-full transition-all duration-500`}
                style={{ width: `${(clients / maxClients) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Main UsageAnalytics component.
 */
export function UsageAnalytics() {
  const { data, isLoading, error } = usePlatformUsage();

  if (error) {
    return (
      <div className="bg-card rounded-xl p-6 border border-border">
        <p className="text-status-danger">Failed to load usage analytics</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard
          title="Total Clients"
          value={data?.total_clients ?? 0}
          icon={Users}
          iconColor="bg-primary"
          isLoading={isLoading}
        />
        <MetricCard
          title="Total Syncs"
          value={data?.total_syncs ?? 0}
          icon={FileText}
          iconColor="bg-status-success"
          isLoading={isLoading}
        />
        <MetricCard
          title="AI Queries"
          value={data?.total_ai_queries ?? 0}
          icon={MessageSquare}
          iconColor="bg-purple-500"
          isLoading={isLoading}
        />
      </div>

      {/* Tier breakdown */}
      <TierBreakdown data={data?.by_tier ?? null} isLoading={isLoading} />
    </div>
  );
}

export default UsageAnalytics;
