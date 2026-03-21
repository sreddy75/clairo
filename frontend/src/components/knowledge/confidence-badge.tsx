'use client';

/**
 * ConfidenceBadge Component
 *
 * Displays a confidence tier (High / Medium / Low) as a small inline badge
 * with colour coding. Optionally shows the numeric score on hover via a
 * tooltip. Designed to sit alongside knowledge chat responses.
 */

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

type ConfidenceTier = 'high' | 'medium' | 'low';

interface ConfidenceBadgeProps {
  /** The confidence tier to display */
  confidence: ConfidenceTier;
  /** Optional numeric score (0-1) shown on hover */
  score?: number;
  /** Additional CSS classes */
  className?: string;
}

// =============================================================================
// Tier Configuration
// =============================================================================

const TIER_CONFIG: Record<
  ConfidenceTier,
  { label: string; badgeClasses: string }
> = {
  high: {
    label: 'High',
    badgeClasses:
      'bg-status-success/10 text-status-success border-status-success/30',
  },
  medium: {
    label: 'Medium',
    badgeClasses:
      'bg-status-warning/10 text-status-warning border-status-warning/30',
  },
  low: {
    label: 'Low',
    badgeClasses:
      'bg-status-danger/10 text-status-danger border-status-danger/30',
  },
};

// =============================================================================
// Component
// =============================================================================

export function ConfidenceBadge({ confidence, score, className }: ConfidenceBadgeProps) {
  const config = TIER_CONFIG[confidence];

  const badge = (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
        config.badgeClasses,
        className,
      )}
    >
      {config.label} confidence
    </span>
  );

  // If a numeric score is provided, wrap in a tooltip
  if (score !== undefined) {
    const pct = Math.round(score * 100);

    return (
      <TooltipProvider delayDuration={200}>
        <Tooltip>
          <TooltipTrigger asChild>
            {badge}
          </TooltipTrigger>
          <TooltipContent side="top" className="text-xs">
            Confidence score: {pct}%
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return badge;
}

export default ConfidenceBadge;
