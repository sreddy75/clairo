'use client';

/**
 * Inline citation chip for a `[CLR-XXX: Name]` reference (Spec 060 T038).
 *
 * Rendered mid-prose by the markdown tokenizer (T041). Three colour states
 * mirror the backend's name-drift classification:
 *   - verified            → green
 *   - partially_verified  → amber (identifier matched, cited name drifted)
 *   - unverified          → red (no matching retrieved strategy — hallucinated
 *     or not currently published)
 *
 * Click opens `StrategyDetailSheet` with the full strategy content.
 */

import { badgeVariants } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { StrategyCitationStatus } from '@/types/tax-planning';

interface StrategyChipProps {
  strategyId: string;
  citedName: string;
  status: StrategyCitationStatus;
  onClick?: (strategyId: string) => void;
}

const STATUS_CLASSES: Record<StrategyCitationStatus, string> = {
  verified:
    'bg-emerald-100 text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-900 dark:text-emerald-300 dark:hover:bg-emerald-800',
  partially_verified:
    'bg-amber-100 text-amber-700 hover:bg-amber-200 dark:bg-amber-900 dark:text-amber-300 dark:hover:bg-amber-800',
  unverified:
    'bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900 dark:text-red-300 dark:hover:bg-red-800',
};

const STATUS_TITLES: Record<StrategyCitationStatus, string> = {
  verified: 'Verified against the strategy knowledge base',
  partially_verified:
    'Strategy id matches but the cited name has drifted — review before relying',
  unverified: 'No matching published strategy — verify before relying',
};

export function StrategyChip({
  strategyId,
  citedName,
  status,
  onClick,
}: StrategyChipProps) {
  const handleClick = () => onClick?.(strategyId);
  const handleKeyDown = (e: React.KeyboardEvent<HTMLSpanElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick?.(strategyId);
    }
  };

  return (
    <span
      role="button"
      tabIndex={0}
      title={STATUS_TITLES[status]}
      aria-label={`${strategyId}: ${citedName} (${status.replace('_', ' ')})`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={cn(
        badgeVariants({ variant: 'secondary' }),
        'mx-0.5 cursor-pointer align-baseline font-medium',
        STATUS_CLASSES[status],
      )}
    >
      [{strategyId}: {citedName}]
    </span>
  );
}
