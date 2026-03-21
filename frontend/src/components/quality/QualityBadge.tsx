'use client';

import { getQualityTier } from '@/lib/quality';
import { cn } from '@/lib/utils';

interface QualityBadgeProps {
  score: number | null | undefined;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

/**
 * Quality score badge component.
 * Displays the overall quality score with color-coded tier.
 */
export function QualityBadge({
  score,
  size = 'md',
  showLabel = false,
  className,
}: QualityBadgeProps) {
  // Handle null/undefined score
  if (score === null || score === undefined) {
    return (
      <span
        className={cn(
          'inline-flex items-center rounded-full font-medium',
          'bg-muted text-muted-foreground',
          size === 'sm' && 'px-2 py-0.5 text-xs',
          size === 'md' && 'px-2.5 py-1 text-sm',
          size === 'lg' && 'px-3 py-1.5 text-base',
          className
        )}
      >
        {showLabel ? 'No Score' : '--'}
      </span>
    );
  }

  const tier = getQualityTier(score);
  const tierStyles = {
    good: 'bg-status-success/10 text-status-success border-status-success/20',
    fair: 'bg-status-warning/10 text-status-warning border-status-warning/20',
    poor: 'bg-status-danger/10 text-status-danger border-status-danger/20',
  };

  const tierLabels = {
    good: 'Good',
    fair: 'Fair',
    poor: 'Needs Work',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full font-medium border',
        tierStyles[tier],
        size === 'sm' && 'px-2 py-0.5 text-xs',
        size === 'md' && 'px-2.5 py-1 text-sm',
        size === 'lg' && 'px-3 py-1.5 text-base',
        className
      )}
    >
      <span className="font-semibold">{Math.round(score)}%</span>
      {showLabel && (
        <span className="ml-1.5 opacity-80">{tierLabels[tier]}</span>
      )}
    </span>
  );
}

export default QualityBadge;
