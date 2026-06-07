'use client';

import { AlertTriangle } from 'lucide-react';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { formatCurrency, formatDate } from '@/lib/formatters';

interface UnreconciledWarningProps {
  open: boolean;
  unreconciledCount: number;
  totalTransactions: number;
  balanceDiscrepancy: number;
  asOf: string | null;
  onProceed: () => void;
  onGoBack: () => void;
}

export function UnreconciledWarning({
  open,
  unreconciledCount,
  totalTransactions,
  balanceDiscrepancy,
  asOf,
  onProceed,
  onGoBack,
}: UnreconciledWarningProps) {
  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="w-5 h-5 text-status-warning" />
            <AlertDialogTitle>Xero data is not fully reconciled</AlertDialogTitle>
          </div>
          <AlertDialogDescription className="space-y-2">
            <span className="block">
              {unreconciledCount} of {totalTransactions} transaction
              {totalTransactions !== 1 ? 's' : ''} for this period are not reconciled in Xero —
              BAS figures may be incomplete or inaccurate.
            </span>
            {balanceDiscrepancy > 0 && (
              <span className="block">
                {formatCurrency(balanceDiscrepancy)} balance discrepancy from unreconciled transactions.
              </span>
            )}
            {asOf && (
              <span className="block text-xs text-muted-foreground">
                Reconciliation status as at {formatDate(asOf)}
              </span>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onGoBack}>
            Dismiss — I&apos;ll reconcile in Xero first
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onProceed}
            className="bg-status-warning text-white hover:bg-status-warning/90"
          >
            Proceed anyway
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
