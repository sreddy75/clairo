'use client';

import { TrendingUp, History, AlertCircle } from 'lucide-react';
import Link from 'next/link';

import { useUsage } from '@/hooks/useUsage';
import { cn } from '@/lib/utils';

import { UsageProgressBar } from './UsageProgressBar';

interface UsageDashboardProps {
  /**
   * Additional CSS classes.
   */
  className?: string;
}

/**
 * Usage dashboard component showing all usage metrics.
 * Displays client count, AI queries, and documents processed.
 *
 * @example
 * ```tsx
 * <UsageDashboard />
 * ```
 */
export function UsageDashboard({ className }: UsageDashboardProps) {
  const {
    clientCount,
    clientLimit,
    aiQueriesMonth,
    documentsMonth,
    isLoading,
    error,
    isApproachingLimit,
    isAtLimit,
    thresholdWarning,
    tier,
    nextTier,
  } = useUsage();

  if (isLoading) {
    return (
      <div className={cn('rounded-lg border bg-card p-6', className)}>
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-muted rounded w-1/3" />
          <div className="space-y-3">
            <div className="h-2 bg-muted rounded" />
            <div className="h-2 bg-muted rounded" />
            <div className="h-2 bg-muted rounded" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('rounded-lg border bg-card p-6', className)}>
        <div className="flex items-center gap-2 text-red-600">
          <AlertCircle className="h-5 w-5" />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('rounded-lg border bg-card', className)}>
      {/* Header */}
      <div className="px-6 py-4 border-b">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-foreground">Usage</h3>
            <p className="text-sm text-muted-foreground">
              Current billing period
            </p>
          </div>
          {tier && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 capitalize">
              {tier} Plan
            </span>
          )}
        </div>
      </div>

      {/* Usage Metrics */}
      <div className="p-6 space-y-6">
        {/* Clients - Enforced limit */}
        <UsageProgressBar
          current={clientCount}
          limit={clientLimit}
          label="Clients"
        />

        {/* AI Queries - Informational */}
        <UsageProgressBar
          current={aiQueriesMonth}
          limit={null}
          label="AI Queries"
          informational
        />

        {/* Documents - Informational */}
        <UsageProgressBar
          current={documentsMonth}
          limit={null}
          label="Documents Processed"
          informational
        />
      </div>

      {/* Warning Messages */}
      {thresholdWarning && (
        <div className="px-6 pb-4">
          {isAtLimit ? (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-red-800">
                    Client limit reached
                  </p>
                  <p className="text-sm text-red-700 mt-1">
                    You cannot add new clients until you upgrade your plan.
                  </p>
                </div>
              </div>
            </div>
          ) : isApproachingLimit ? (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-5 w-5 text-yellow-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-yellow-800">
                    Approaching client limit ({thresholdWarning})
                  </p>
                  <p className="text-sm text-yellow-700 mt-1">
                    Consider upgrading to continue growing your practice.
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* Actions */}
      <div className="px-6 py-4 border-t bg-muted flex items-center justify-between rounded-b-lg">
        <Link
          href="/settings/billing/history"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <History className="h-4 w-4" />
          View History
        </Link>

        {nextTier && (isApproachingLimit || isAtLimit) && (
          <Link
            href="/pricing"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-lg transition-colors"
          >
            <TrendingUp className="h-4 w-4" />
            Upgrade to {nextTier.charAt(0).toUpperCase() + nextTier.slice(1)}
          </Link>
        )}
      </div>
    </div>
  );
}

export default UsageDashboard;
