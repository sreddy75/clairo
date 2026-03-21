'use client';

import { CheckCircle2, Loader2, Zap } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import type { TaxCodeSuggestionSummary } from '@/lib/bas';

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

  return (
    <div className="flex items-center justify-between gap-3 p-3 bg-muted/50 rounded-lg border">
      <div className="text-sm text-muted-foreground">
        <span className="font-medium text-foreground tabular-nums">{summary.unresolved_count}</span>
        {' '}pending
        {summary.high_confidence_pending > 0 && (
          <span className="text-status-success">
            {' '}({summary.high_confidence_pending} high confidence)
          </span>
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
            variant="outline"
            onClick={handleRecalculate}
            disabled={disabled || isRecalculating || isBulkApproving}
            className="h-8 text-xs border-status-success text-status-success hover:bg-status-success/10"
          >
            {isRecalculating ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
            ) : (
              <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
            )}
            Apply & Recalculate
          </Button>
        )}
      </div>
    </div>
  );
}
