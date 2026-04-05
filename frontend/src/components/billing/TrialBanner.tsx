'use client';

import { Clock, CreditCard, Settings, X } from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { openBillingPortal } from '@/lib/api/billing';
import { cn } from '@/lib/utils';
import type { SubscriptionTier } from '@/types/billing';

interface TrialBannerProps {
  /**
   * Days remaining in trial.
   */
  daysRemaining: number;

  /**
   * Current subscription tier.
   */
  tier: SubscriptionTier;

  /**
   * Monthly price in cents.
   */
  priceMonthly: number;

  /**
   * Trial end date (billing date).
   */
  billingDate: string;

  /**
   * Whether the banner can be dismissed (session-only).
   */
  dismissible?: boolean;

  /**
   * Additional CSS classes.
   */
  className?: string;
}

/**
 * Trial banner displayed at the top of the dashboard for users in trial.
 * Shows days remaining, billing date, and provides quick access to billing settings.
 *
 * Spec 021: Onboarding Flow - Free Trial Experience
 *
 * @example
 * ```tsx
 * <TrialBanner
 *   daysRemaining={12}
 *   tier="professional"
 *   priceMonthly={29900}
 *   billingDate="January 15, 2025"
 * />
 * ```
 */
export function TrialBanner({
  daysRemaining,
  tier,
  priceMonthly,
  billingDate,
  dismissible = true,
  className,
}: TrialBannerProps) {
  const [isDismissed, setIsDismissed] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Hydration safety
  useEffect(() => {
    setMounted(true);
  }, []);

  const handleDismiss = useCallback(() => {
    setIsDismissed(true);
    // Session-only dismiss (resets on refresh)
    try {
      sessionStorage.setItem('trialBannerDismissed', 'true');
    } catch {
      // Ignore if sessionStorage is not available
    }
  }, []);

  // Check if already dismissed this session
  useEffect(() => {
    if (mounted) {
      try {
        const dismissed = sessionStorage.getItem('trialBannerDismissed');
        if (dismissed === 'true') {
          setIsDismissed(true);
        }
      } catch {
        // Ignore if sessionStorage is not available
      }
    }
  }, [mounted]);

  // Don't render until mounted (hydration safety)
  if (!mounted || isDismissed) {
    return null;
  }

  // Format price
  const priceDisplay = `$${(priceMonthly / 100).toFixed(0)}`;
  const tierDisplay = tier.charAt(0).toUpperCase() + tier.slice(1);

  // Urgency-based styling
  const getStyles = () => {
    if (daysRemaining <= 1) {
      return {
        container: 'bg-status-danger/10 border-status-danger/20',
        icon: 'text-status-danger',
        text: 'text-status-danger',
        badge: 'bg-status-danger/20 text-status-danger',
      };
    }
    if (daysRemaining <= 3) {
      return {
        container: 'bg-status-warning/10 border-status-warning/20',
        icon: 'text-status-warning',
        text: 'text-status-warning',
        badge: 'bg-status-warning/20 text-status-warning',
      };
    }
    return {
      container: 'bg-primary/10 border-primary/20',
      icon: 'text-primary',
      text: 'text-primary',
      badge: 'bg-primary/20 text-primary',
    };
  };

  const styles = getStyles();

  const getDaysText = () => {
    if (daysRemaining === 0) return 'Trial ends today';
    if (daysRemaining === 1) return 'Trial ends tomorrow';
    return `${daysRemaining} days left in trial`;
  };

  return (
    <div
      className={cn(
        'relative border rounded-lg px-4 py-3',
        styles.container,
        className
      )}
      role="status"
      aria-label="Trial status"
    >
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Clock className={cn('h-5 w-5 flex-shrink-0', styles.icon)} />

          <div className="flex items-center gap-3 flex-wrap">
            <span
              className={cn(
                'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                styles.badge
              )}
            >
              {getDaysText()}
            </span>

            <span className={cn('text-sm', styles.text)}>
              Your {tierDisplay} plan ({priceDisplay}/mo) starts on {billingDate}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {daysRemaining <= 3 && (
            <button
              onClick={() => openBillingPortal()}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                'bg-primary text-primary-foreground hover:bg-primary/90'
              )}
            >
              <CreditCard className="h-4 w-4" />
              Add Payment Method
            </button>
          )}
          <Link
            href="/settings/billing"
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
              'bg-card border border-border hover:bg-muted text-foreground'
            )}
          >
            <Settings className="h-4 w-4" />
            Billing Settings
          </Link>

          {dismissible && (
            <button
              onClick={handleDismiss}
              className="p-1.5 rounded hover:bg-muted transition-colors"
              aria-label="Dismiss trial banner"
            >
              <X className="h-4 w-4 text-muted-foreground" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default TrialBanner;
