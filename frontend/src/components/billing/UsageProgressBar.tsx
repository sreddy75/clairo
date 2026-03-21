'use client';

import { cn } from '@/lib/utils';

interface UsageProgressBarProps {
  /**
   * Current value.
   */
  current: number;

  /**
   * Maximum allowed, null for unlimited/informational.
   */
  limit: number | null;

  /**
   * Label for the metric.
   */
  label: string;

  /**
   * Whether this is an informational metric (no limit enforcement).
   * Informational metrics always show green.
   */
  informational?: boolean;

  /**
   * Additional CSS classes.
   */
  className?: string;
}

/**
 * Get bar color based on percentage used.
 * green: <60%
 * yellow: 60-79%
 * orange: 80-89%
 * red: >=90%
 */
function getBarColor(percentage: number | null, informational: boolean): string {
  if (informational || percentage === null) {
    return 'bg-blue-500';
  }
  if (percentage >= 90) return 'bg-red-500';
  if (percentage >= 80) return 'bg-orange-500';
  if (percentage >= 60) return 'bg-yellow-500';
  return 'bg-green-500';
}

/**
 * Get text color based on percentage.
 */
function getTextColor(percentage: number | null, informational: boolean): string {
  if (informational || percentage === null) {
    return 'text-primary';
  }
  if (percentage >= 90) return 'text-red-600';
  if (percentage >= 80) return 'text-orange-600';
  if (percentage >= 60) return 'text-yellow-600';
  return 'text-green-600';
}

/**
 * Generic progress bar component for usage metrics.
 * Used in the usage dashboard for clients, AI queries, and documents.
 *
 * @example
 * ```tsx
 * <UsageProgressBar
 *   current={23}
 *   limit={25}
 *   label="Clients"
 * />
 * <UsageProgressBar
 *   current={150}
 *   limit={null}
 *   label="AI Queries"
 *   informational
 * />
 * ```
 */
export function UsageProgressBar({
  current,
  limit,
  label,
  informational = false,
  className,
}: UsageProgressBarProps) {
  const percentage = limit !== null ? Math.min((current / limit) * 100, 100) : null;
  const barColor = getBarColor(percentage, informational);
  const textColor = getTextColor(percentage, informational);

  return (
    <div className={cn('space-y-2', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span className={cn('text-sm font-semibold', textColor)}>
          {limit !== null ? `${current} / ${limit}` : current.toLocaleString()}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-muted rounded-full h-2">
        <div
          className={cn('h-2 rounded-full transition-all duration-300', barColor)}
          style={{
            width: percentage !== null
              ? `${percentage}%`
              : '100%', // Informational shows full bar
          }}
        />
      </div>

      {/* Percentage or description */}
      <div className="flex justify-between text-xs text-muted-foreground">
        {percentage !== null && limit !== null ? (
          <>
            <span>{Math.round(percentage)}% used</span>
            <span>{limit - current} remaining</span>
          </>
        ) : (
          <span>This billing period</span>
        )}
      </div>
    </div>
  );
}

export default UsageProgressBar;
