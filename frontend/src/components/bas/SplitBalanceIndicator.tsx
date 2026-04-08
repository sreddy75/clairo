'use client';

import { AlertTriangle, CheckCircle2 } from 'lucide-react';

import type { TaxCodeOverrideWithSplit, XeroLineItemView } from '@/lib/bas';
import { cn } from '@/lib/utils';

interface SplitBalanceIndicatorProps {
  splits: TaxCodeOverrideWithSplit[];
  /** Original Xero line items — used to derive the total when transactionTotal is unavailable */
  originalLineItems?: XeroLineItemView[];
  transactionTotal: number | null;
  className?: string;
}

/**
 * Shows whether the active splits on a bank transaction sum to the transaction total.
 *
 * - Green checkmark: splits are balanced (sum equals total).
 * - Amber warning: split amounts do not equal the transaction total.
 * - Hidden: no overrides present and no transaction total available.
 */
export function SplitBalanceIndicator({
  splits,
  originalLineItems = [],
  transactionTotal,
  className,
}: SplitBalanceIndicatorProps) {
  const splitsWithAmount = splits.filter((s) => s.line_amount !== null);

  // Derive total from original line items if not provided via props
  const effectiveTotal =
    transactionTotal !== null
      ? transactionTotal
      : originalLineItems.length > 0
        ? Math.abs(originalLineItems.reduce((sum, li) => sum + Number(li.line_amount ?? 0), 0))
        : null;

  if (splitsWithAmount.length === 0 || effectiveTotal === null) return null;

  const splitSum = splitsWithAmount.reduce((acc, s) => acc + Number(s.line_amount), 0);
  const total = Number(effectiveTotal);
  if (!isFinite(total) || total === 0) return null;
  const diff = Math.abs(Math.abs(splitSum) - total);
  const isBalanced = diff < 0.005; // allow ½ cent float tolerance

  return (
    <div className={cn('flex items-center gap-1 text-[10px]', className)}>
      {isBalanced ? (
        <>
          <CheckCircle2 className="w-3 h-3 text-emerald-600 flex-shrink-0" />
          <span className="text-emerald-700">Splits balanced</span>
        </>
      ) : (
        <>
          <AlertTriangle className="w-3 h-3 text-amber-500 flex-shrink-0" />
          <span className="text-amber-700">
            Splits unbalanced — ${Math.abs(splitSum).toFixed(2)} of ${total.toFixed(2)}
          </span>
        </>
      )}
    </div>
  );
}
