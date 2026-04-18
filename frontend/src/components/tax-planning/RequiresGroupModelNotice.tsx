'use client';

import { Info } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface RequiresGroupModelNoticeProps {
  className?: string;
  compact?: boolean;
}

/**
 * Spec 059 FR-017..FR-020 — disabled-state notice for scenarios whose benefit
 * cannot be computed honestly on a single entity (director salary, trust
 * distribution, dividend timing, spouse contribution, multi-entity
 * restructure). Rather than synthesising a misleading "single-entity net
 * benefit" figure, we surface the scenario as a placeholder and point to the
 * upcoming group tax model.
 */
export function RequiresGroupModelNotice({
  className,
  compact = false,
}: RequiresGroupModelNoticeProps) {
  if (compact) {
    return (
      <Badge
        variant="outline"
        className={cn(
          'gap-1 border-stone-300 text-stone-600 bg-stone-50 text-[10px]',
          className,
        )}
      >
        <Info className="h-3 w-3" />
        Needs group tax model
      </Badge>
    );
  }

  return (
    <div
      className={cn(
        'rounded-md border border-dashed border-stone-300 bg-stone-50 p-3',
        'text-xs text-stone-600',
        className,
      )}
    >
      <div className="flex items-center gap-1.5 font-medium text-stone-700">
        <Info className="h-3.5 w-3.5" />
        Multi-entity strategy
      </div>
      <p className="mt-1">
        Precise benefit requires the group tax model (coming soon). Excluded
        from combined totals so the headline number is not misleading.
      </p>
    </div>
  );
}
