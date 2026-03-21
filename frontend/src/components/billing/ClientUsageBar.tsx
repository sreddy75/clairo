'use client';

import { TrendingUp, Users } from 'lucide-react';
import Link from 'next/link';

import { cn } from '@/lib/utils';
import type { SubscriptionTier } from '@/types/billing';

interface ClientUsageBarProps {
  /**
   * Current number of clients.
   */
  clientCount: number;

  /**
   * Maximum clients allowed, null for unlimited.
   */
  clientLimit: number | null;

  /**
   * Current subscription tier.
   */
  tier: SubscriptionTier;

  /**
   * Compact mode for sidebar/header usage.
   */
  compact?: boolean;

  /**
   * Additional CSS classes.
   */
  className?: string;
}

/**
 * Progress bar showing client usage relative to tier limit.
 * Shows different states: normal, warning (>80%), at limit (100%).
 *
 * @example
 * ```tsx
 * <ClientUsageBar
 *   clientCount={23}
 *   clientLimit={25}
 *   tier="starter"
 * />
 * ```
 */
export function ClientUsageBar({
  clientCount,
  clientLimit,
  tier: _tier,
  compact = false,
  className,
}: ClientUsageBarProps) {
  // Unlimited tiers
  if (clientLimit === null) {
    return compact ? null : (
      <div className={cn('flex items-center gap-2 text-sm text-muted-foreground', className)}>
        <Users className="h-4 w-4" />
        <span>{clientCount} clients (unlimited)</span>
      </div>
    );
  }

  const percentage = Math.min((clientCount / clientLimit) * 100, 100);
  const isAtLimit = clientCount >= clientLimit;
  const isApproachingLimit = percentage >= 80 && !isAtLimit;

  const getBarColor = () => {
    if (isAtLimit) return 'bg-red-500';
    if (isApproachingLimit) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const getStatusText = () => {
    if (isAtLimit) return 'At limit';
    if (isApproachingLimit) return 'Approaching limit';
    return 'Good';
  };

  const getStatusColor = () => {
    if (isAtLimit) return 'text-red-600';
    if (isApproachingLimit) return 'text-yellow-600';
    return 'text-green-600';
  };

  if (compact) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <div className="w-16 bg-muted rounded-full h-1.5">
          <div
            className={cn('h-1.5 rounded-full', getBarColor())}
            style={{ width: `${percentage}%` }}
          />
        </div>
        <span className={cn('text-xs', getStatusColor())}>
          {clientCount}/{clientLimit}
        </span>
      </div>
    );
  }

  return (
    <div className={cn('rounded-lg border bg-card p-4', className)}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">Client Usage</span>
        </div>
        <span className={cn('text-sm font-medium', getStatusColor())}>
          {getStatusText()}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-muted rounded-full h-2.5 mb-2">
        <div
          className={cn('h-2.5 rounded-full transition-all', getBarColor())}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Count */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {clientCount} of {clientLimit} clients
        </span>
        <span className="text-sm text-muted-foreground">
          {Math.round(percentage)}% used
        </span>
      </div>

      {/* Warning message and upgrade CTA */}
      {isApproachingLimit && (
        <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-sm text-yellow-800">
            You&apos;re approaching your client limit.
          </p>
          <Link
            href="/pricing"
            className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            <TrendingUp className="h-3.5 w-3.5" />
            Upgrade for more clients
          </Link>
        </div>
      )}

      {isAtLimit && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-800">
            You&apos;ve reached your client limit. Upgrade to add more clients.
          </p>
          <Link
            href="/pricing"
            className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            <TrendingUp className="h-3.5 w-3.5" />
            Upgrade now
          </Link>
        </div>
      )}
    </div>
  );
}

export default ClientUsageBar;
