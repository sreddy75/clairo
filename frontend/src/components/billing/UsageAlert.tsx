'use client';

import { AlertTriangle, TrendingUp, X } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { cn } from '@/lib/utils';
import type { SubscriptionTier, ThresholdWarning } from '@/types/billing';

interface UsageAlertProps {
  /**
   * Usage percentage (0-100).
   */
  percentage: number;

  /**
   * Current subscription tier.
   */
  tier: SubscriptionTier;

  /**
   * Threshold warning level.
   */
  thresholdWarning: ThresholdWarning | null;

  /**
   * Next tier for upgrade.
   */
  nextTier: SubscriptionTier | null;

  /**
   * Whether the alert can be dismissed.
   */
  dismissible?: boolean;

  /**
   * Additional CSS classes.
   */
  className?: string;
}

/**
 * In-app banner alert for usage warnings.
 * Displayed when usage is at 80%, 90%, or 100% of limit.
 *
 * @example
 * ```tsx
 * <UsageAlert
 *   percentage={85}
 *   tier="starter"
 *   thresholdWarning="80%"
 *   nextTier="professional"
 * />
 * ```
 */
export function UsageAlert({
  percentage,
  tier,
  thresholdWarning,
  nextTier,
  dismissible = true,
  className,
}: UsageAlertProps) {
  const [isDismissed, setIsDismissed] = useState(false);

  // Don't show if no warning or dismissed
  if (!thresholdWarning || isDismissed) {
    return null;
  }

  const isAtLimit = thresholdWarning === '100%';

  const getAlertStyles = () => {
    if (isAtLimit) {
      return {
        container: 'bg-red-50 border-red-200',
        icon: 'text-red-500',
        title: 'text-red-800',
        message: 'text-red-700',
        button: 'bg-red-600 hover:bg-red-700 text-white',
      };
    }
    if (thresholdWarning === '90%') {
      return {
        container: 'bg-orange-50 border-orange-200',
        icon: 'text-orange-500',
        title: 'text-orange-800',
        message: 'text-orange-700',
        button: 'bg-orange-600 hover:bg-orange-700 text-white',
      };
    }
    return {
      container: 'bg-yellow-50 border-yellow-200',
      icon: 'text-yellow-500',
      title: 'text-yellow-800',
      message: 'text-yellow-700',
      button: 'bg-yellow-600 hover:bg-yellow-700 text-white',
    };
  };

  const styles = getAlertStyles();

  const getMessage = () => {
    if (isAtLimit) {
      return "You've reached your client limit. You cannot add new clients until you upgrade.";
    }
    if (thresholdWarning === '90%') {
      return `You're at ${Math.round(percentage)}% of your client limit. Upgrade soon to avoid interruptions.`;
    }
    return `You're approaching your client limit (${Math.round(percentage)}% used). Consider upgrading.`;
  };

  const getTitle = () => {
    if (isAtLimit) return 'Client Limit Reached';
    return 'Approaching Client Limit';
  };

  return (
    <div
      className={cn(
        'relative border rounded-lg p-4',
        styles.container,
        className
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className={cn('h-5 w-5 mt-0.5 flex-shrink-0', styles.icon)} />

        <div className="flex-1 min-w-0">
          <h4 className={cn('text-sm font-semibold', styles.title)}>
            {getTitle()}
          </h4>
          <p className={cn('mt-1 text-sm', styles.message)}>
            {getMessage()}
          </p>

          {nextTier && (
            <div className="mt-3 flex items-center gap-3">
              <Link
                href="/pricing"
                className={cn(
                  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                  styles.button
                )}
              >
                <TrendingUp className="h-4 w-4" />
                Upgrade to {nextTier.charAt(0).toUpperCase() + nextTier.slice(1)}
              </Link>

              <span className="text-sm text-muted-foreground">
                Current plan: {tier.charAt(0).toUpperCase() + tier.slice(1)}
              </span>
            </div>
          )}
        </div>

        {dismissible && !isAtLimit && (
          <button
            onClick={() => setIsDismissed(true)}
            className="flex-shrink-0 p-1 rounded hover:bg-black/5 transition-colors"
            aria-label="Dismiss alert"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        )}
      </div>
    </div>
  );
}

export default UsageAlert;
