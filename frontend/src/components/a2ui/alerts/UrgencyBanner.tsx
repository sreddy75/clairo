'use client';

/**
 * A2UI UrgencyBanner Component
 * Displays time-sensitive urgency notifications
 */

import { AlertTriangle, Clock } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import type { UrgencyBannerProps } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UIUrgencyBannerProps extends UrgencyBannerProps {
  id: string;
  dataBinding?: string;
}

// =============================================================================
// Helpers
// =============================================================================

function formatDeadline(deadline: string): string {
  const date = new Date(deadline);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    return `Overdue by ${Math.abs(diffDays)} days`;
  } else if (diffDays === 0) {
    return 'Due today';
  } else if (diffDays === 1) {
    return 'Due tomorrow';
  } else if (diffDays <= 7) {
    return `Due in ${diffDays} days`;
  } else {
    return `Due ${date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })}`;
  }
}

function getVariantStyles(variant: string, deadline: string) {
  const date = new Date(deadline);
  const now = new Date();
  const isOverdue = date < now;

  if (variant === 'critical' || isOverdue) {
    return {
      container: 'border-status-danger/50 bg-status-danger/10 text-foreground',
      icon: 'text-status-danger',
      badge: 'bg-status-danger text-white',
    };
  }

  return {
    container: 'border-status-warning/50 bg-status-warning/10 text-foreground',
    icon: 'text-status-warning',
    badge: 'bg-status-warning text-white',
  };
}

// =============================================================================
// Component
// =============================================================================

export function UrgencyBanner({
  id,
  deadline,
  message,
  variant = 'warning',
}: A2UIUrgencyBannerProps) {
  const styles = getVariantStyles(variant, deadline);
  const formattedDeadline = formatDeadline(deadline);
  const Icon = variant === 'critical' ? AlertTriangle : Clock;

  return (
    <Alert
      id={id}
      className={cn('relative', styles.container)}
      role="alert"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <Icon className={cn('h-5 w-5 mt-0.5', styles.icon)} aria-hidden="true" />
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <AlertTitle className="font-semibold m-0">{message}</AlertTitle>
            <span
              className={cn(
                'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
                styles.badge
              )}
            >
              {formattedDeadline}
            </span>
          </div>
          <AlertDescription className="text-sm opacity-80">
            {new Date(deadline).toLocaleDateString('en-AU', {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
          </AlertDescription>
        </div>
      </div>
    </Alert>
  );
}
