'use client';

/**
 * TopUsersTable Component
 *
 * Displays top tenants by various metrics.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import { Crown, MessageSquare, RefreshCw, Users } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { useTopUsers } from '@/hooks/useAdminDashboard';

type MetricType = 'clients' | 'syncs' | 'ai_queries';

interface TopUsersTableProps {
  limit?: number;
}

/**
 * Metric selector tabs.
 */
function MetricSelector({
  selected,
  onChange,
}: {
  selected: MetricType;
  onChange: (metric: MetricType) => void;
}) {
  const metrics: { value: MetricType; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { value: 'clients', label: 'Clients', icon: Users },
    { value: 'syncs', label: 'Syncs', icon: RefreshCw },
    { value: 'ai_queries', label: 'AI Queries', icon: MessageSquare },
  ];

  return (
    <div className="flex bg-muted rounded-lg p-1">
      {metrics.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          onClick={() => onChange(value)}
          className={`flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
            selected === value
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          <Icon className="w-4 h-4" />
          {label}
        </button>
      ))}
    </div>
  );
}

/**
 * Format metric value for display.
 */
function formatMetricValue(value: number, _metric: MetricType): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return value.toLocaleString();
}

/**
 * Main TopUsersTable component.
 */
export function TopUsersTable({ limit = 10 }: TopUsersTableProps) {
  const [metric, setMetric] = useState<MetricType>('clients');
  const { data, isLoading, error, refetch } = useTopUsers(metric, limit);

  return (
    <div className="bg-card rounded-xl border border-border">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Crown className="w-5 h-5 text-status-warning" />
            Top Tenants
          </h3>
          <MetricSelector selected={metric} onChange={setMetric} />
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {error ? (
          <div className="text-center py-4">
            <p className="text-status-danger mb-2">Failed to load top users</p>
            <button
              onClick={() => refetch()}
              className="text-sm text-primary hover:text-primary"
            >
              Try again
            </button>
          </div>
        ) : isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between animate-pulse">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-muted rounded-full" />
                  <div className="h-4 bg-muted rounded w-32" />
                </div>
                <div className="h-4 bg-muted rounded w-16" />
              </div>
            ))}
          </div>
        ) : data?.users.length === 0 ? (
          <p className="text-muted-foreground text-center py-4">No data available</p>
        ) : (
          <div className="space-y-3">
            {data?.users.map((user, index) => (
              <div
                key={user.tenant_id}
                className="flex items-center justify-between py-2 border-b border-border last:border-0"
              >
                <div className="flex items-center gap-3">
                  {/* Rank badge */}
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                      index === 0
                        ? 'bg-status-warning/10 text-status-warning'
                        : index === 1
                          ? 'bg-muted text-foreground'
                          : index === 2
                            ? 'bg-status-warning/10 text-status-warning'
                            : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {index + 1}
                  </div>

                  {/* Tenant name */}
                  <Link
                    href={`/internal/admin/customers/${user.tenant_id}`}
                    className="text-sm font-medium text-foreground hover:text-primary transition-colors"
                  >
                    {user.tenant_name}
                  </Link>
                </div>

                {/* Metric value */}
                <span className="text-sm font-medium text-foreground">
                  {formatMetricValue(user.value, metric)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default TopUsersTable;
