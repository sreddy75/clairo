'use client';

import { AlertTriangle, Loader2, Zap } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import type { TaxCodeSuggestionSummary } from '@/lib/bas';
import { cn } from '@/lib/utils';

interface TaxCodeBulkActionsProps {
  summary: TaxCodeSuggestionSummary;
  onBulkApprove: () => Promise<void>;
  onRecalculate: () => Promise<void>;
  hasApprovedNotApplied: boolean;
  disabled?: boolean;
}

export function TaxCodeBulkActions({
  summary,
  onBulkApprove,
  onRecalculate,
  hasApprovedNotApplied,
  disabled = false,
}: TaxCodeBulkActionsProps) {
  const [isBulkApproving, setIsBulkApproving] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);

  async function handleBulkApprove() {
    setIsBulkApproving(true);
    try {
      await onBulkApprove();
    } finally {
      setIsBulkApproving(false);
    }
  }

  async function handleRecalculate() {
    setIsRecalculating(true);
    try {
      await onRecalculate();
    } finally {
      setIsRecalculating(false);
    }
  }

  const allResolved = summary.unresolved_count === 0;

  return (
    <div className={cn(
      'flex items-center justify-between gap-3 p-3 rounded-lg border',
      hasApprovedNotApplied ? 'bg-amber-50 border-amber-200' : 'bg-muted/50',
    )}>
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {hasApprovedNotApplied && (
          <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
        )}
        {allResolved && hasApprovedNotApplied ? (
          <span>All resolved — recalculate BAS figures before lodgement</span>
        ) : (
          <>
            <span className="font-medium text-foreground tabular-nums">{summary.unresolved_count}</span>
            {' '}uncoded
            {summary.high_confidence_pending > 0 && (
              <span className="text-status-success">
                {' '}({summary.high_confidence_pending} high confidence)
              </span>
            )}
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        {summary.can_bulk_approve && (
          <Button
            size="sm"
            onClick={handleBulkApprove}
            disabled={disabled || isBulkApproving || isRecalculating}
            className="h-8 text-xs"
          >
            {isBulkApproving ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
            ) : (
              <Zap className="w-3.5 h-3.5 mr-1.5" />
            )}
            Approve All High Confidence ({summary.high_confidence_pending})
          </Button>
        )}

        {hasApprovedNotApplied && (
          <Button
            size="sm"
            onClick={handleRecalculate}
            disabled={disabled || isRecalculating || isBulkApproving}
            className="h-8 text-xs bg-amber-500 hover:bg-amber-600 text-white border-transparent"
            title="Updates BAS figures (G1, 1A, G11, 1B) to reflect your approved tax codes. Run this before submitting the BAS to the ATO."
          >
            {isRecalculating ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
            ) : (
              <AlertTriangle className="w-3.5 h-3.5 mr-1.5" />
            )}
            Apply & Recalculate
          </Button>
        )}
      </div>
    </div>
  );
}
