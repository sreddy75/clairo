'use client';

/**
 * CreditModal Component
 *
 * Modal for applying credits to a tenant's account.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import { DollarSign, Loader2, X } from 'lucide-react';
import { useState } from 'react';

import { useApplyCredit } from '@/hooks/useAdminDashboard';
import type { CreditType } from '@/types/admin';

interface CreditModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenantId: string;
  tenantName: string;
  onSuccess?: () => void;
}

/**
 * Format cents to currency display.
 */
function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

/**
 * Main CreditModal component.
 */
export function CreditModal({
  isOpen,
  onClose,
  tenantId,
  tenantName,
  onSuccess,
}: CreditModalProps) {
  const [amountDollars, setAmountDollars] = useState('');
  const [creditType, setCreditType] = useState<CreditType>('one_time');
  const [reason, setReason] = useState('');

  const applyCredit = useApplyCredit();

  if (!isOpen) return null;

  const amountCents = Math.round(parseFloat(amountDollars || '0') * 100);
  const isValidAmount = amountCents > 0 && amountCents <= 1000000; // Max $10,000
  const canSubmit = isValidAmount && reason.trim().length >= 5;

  const handleSubmit = async () => {
    if (!canSubmit) return;

    try {
      await applyCredit.mutateAsync({
        tenantId,
        request: {
          amount_cents: amountCents,
          credit_type: creditType,
          reason: reason.trim(),
        },
      });
      onSuccess?.();
      onClose();
    } catch (error) {
      console.error('Credit application failed:', error);
    }
  };

  const handleClose = () => {
    if (!applyCredit.isPending) {
      setAmountDollars('');
      setCreditType('one_time');
      setReason('');
      onClose();
    }
  };

  const handleAmountChange = (value: string) => {
    // Allow only valid currency input
    const cleaned = value.replace(/[^0-9.]/g, '');
    const parts = cleaned.split('.');
    if (parts.length > 2) return;
    if (parts[1] && parts[1].length > 2) return;
    setAmountDollars(cleaned);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-card rounded-xl max-w-md w-full mx-4 border border-border shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-status-success/10 rounded-lg">
              <DollarSign className="w-5 h-5 text-status-success" />
            </div>
            <h2 className="text-lg font-bold text-foreground">Apply Credit</h2>
          </div>
          <button
            onClick={handleClose}
            disabled={applyCredit.isPending}
            className="text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Tenant info */}
          <div className="bg-muted rounded-lg p-4">
            <p className="text-sm text-muted-foreground">Applying credit to</p>
            <p className="text-lg font-medium text-foreground">{tenantName}</p>
          </div>

          {/* Amount input */}
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">
              Credit Amount (AUD) <span className="text-status-danger">*</span>
            </label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground">
                $
              </span>
              <input
                type="text"
                value={amountDollars}
                onChange={(e) => handleAmountChange(e.target.value)}
                placeholder="0.00"
                className="w-full pl-8 pr-4 py-2 bg-card border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            {amountCents > 0 && (
              <p className="text-sm text-muted-foreground mt-1">
                {formatCurrency(amountCents)} will be credited
              </p>
            )}
            {amountCents > 1000000 && (
              <p className="text-sm text-status-danger mt-1">
                Maximum credit amount is $10,000
              </p>
            )}
          </div>

          {/* Credit type */}
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">
              Credit Type
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setCreditType('one_time')}
                className={`p-3 rounded-lg border transition-all ${
                  creditType === 'one_time'
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:border-border'
                }`}
              >
                <p className="text-sm font-medium text-foreground">One-Time</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Applied to next invoice
                </p>
              </button>
              <button
                onClick={() => setCreditType('recurring')}
                className={`p-3 rounded-lg border transition-all ${
                  creditType === 'recurring'
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:border-border'
                }`}
              >
                <p className="text-sm font-medium text-foreground">Recurring</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Monthly discount applied
                </p>
              </button>
            </div>
          </div>

          {/* Reason */}
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-2">
              Reason <span className="text-status-danger">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Enter the reason for this credit..."
              rows={3}
              className="w-full px-4 py-2 bg-card border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
            />
            <p className="text-xs text-muted-foreground mt-1">
              {reason.length}/5 characters minimum
            </p>
          </div>

          {/* Summary */}
          {canSubmit && (
            <div className="bg-status-success/10 border border-status-success/20 rounded-lg p-4">
              <p className="text-sm text-status-success">
                <strong>{formatCurrency(amountCents)}</strong>{' '}
                {creditType === 'one_time' ? 'one-time' : 'recurring'} credit
                will be applied to {tenantName}&apos;s account.
              </p>
            </div>
          )}

          {/* Error message */}
          {applyCredit.error && (
            <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-3">
              <p className="text-sm text-status-danger">
                {applyCredit.error instanceof Error
                  ? applyCredit.error.message
                  : 'Failed to apply credit. Please try again.'}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-border">
          <button
            onClick={handleClose}
            disabled={applyCredit.isPending}
            className="px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || applyCredit.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-status-success text-white rounded-lg hover:bg-status-success/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {applyCredit.isPending && (
              <Loader2 className="w-4 h-4 animate-spin" />
            )}
            Apply Credit
          </button>
        </div>
      </div>
    </div>
  );
}

export default CreditModal;
