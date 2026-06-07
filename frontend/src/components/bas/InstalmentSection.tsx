'use client';

import { useState } from 'react';

import { type BASCalculation, type InstalmentUpdateRequest, updateInstalments } from '@/lib/bas';
import { formatCurrency } from '@/lib/formatters';
import { cn } from '@/lib/utils';

interface InstalmentSectionProps {
  calculation: BASCalculation;
  getToken: () => Promise<string | null>;
  onUpdated: (updated: BASCalculation) => void;
}

/**
 * Always-visible PAYG Instalment section within the PAYG tab.
 * T1 = instalment income, T2 = instalment rate.
 * T_instalment_payable = T1 × T2 (computed server-side, displayed read-only).
 * Saves to PATCH /bas/calculations/{id}/instalments on blur.
 */
export function InstalmentSection({ calculation, getToken, onUpdated }: InstalmentSectionProps) {
  const [t1, setT1] = useState<string>(
    calculation.t1_instalment_income != null ? String(parseFloat(calculation.t1_instalment_income)) : ''
  );
  const [t2, setT2] = useState<string>(
    calculation.t2_instalment_rate != null ? String(parseFloat(calculation.t2_instalment_rate) * 100) : ''
  );
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const payable = calculation.t_instalment_payable;

  const handleBlur = async () => {
    setSaveError(null);
    const t1Val = t1 !== '' ? parseFloat(t1) : null;
    // t2 is entered as a percentage (e.g. "8.5") → convert to rate (0.085)
    const t2Val = t2 !== '' ? parseFloat(t2) / 100 : null;

    // Skip save if nothing changed
    const existingT1 = calculation.t1_instalment_income != null ? parseFloat(calculation.t1_instalment_income) : null;
    const existingT2 = calculation.t2_instalment_rate != null ? parseFloat(calculation.t2_instalment_rate) * 100 : null;
    const newT2Display = t2 !== '' ? parseFloat(t2) : null;
    if (t1Val === existingT1 && newT2Display === existingT2) return;

    setIsSaving(true);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const payload: InstalmentUpdateRequest = {
        t1_instalment_income: isNaN(t1Val as number) ? null : t1Val,
        t2_instalment_rate: isNaN(t2Val as number) ? null : t2Val,
      };
      const updated = await updateInstalments(token, calculation.id, payload);
      onUpdated(updated);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save instalment values');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-muted/30 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-foreground uppercase tracking-wider">PAYG Instalment</p>
        {isSaving && (
          <span className="text-[10px] text-muted-foreground animate-pulse">Saving…</span>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* T1 — Instalment income */}
        <div className="space-y-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            Instalment income (T1)
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm select-none">$</span>
            <input
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              value={t1}
              onChange={(e) => setT1(e.target.value)}
              onBlur={handleBlur}
              className={cn(
                'w-full pl-7 pr-3 py-2 text-sm font-mono rounded-lg border border-border bg-background',
                'focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary',
              )}
            />
          </div>
          <p className="text-[10px] text-muted-foreground tabular-nums">
            {t1 !== '' && !isNaN(parseFloat(t1)) ? formatCurrency(parseFloat(t1), { fractionDigits: 2 }) : '$0.00'}
          </p>
        </div>

        {/* T2 — Instalment rate */}
        <div className="space-y-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            Instalment rate (T2)
          </label>
          <div className="relative">
            <input
              type="number"
              min="0"
              max="100"
              step="0.001"
              placeholder="0.000"
              value={t2}
              onChange={(e) => setT2(e.target.value)}
              onBlur={handleBlur}
              className={cn(
                'w-full pl-3 pr-8 py-2 text-sm font-mono rounded-lg border border-border bg-background',
                'focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary',
              )}
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm select-none">%</span>
          </div>
          <p className="text-[10px] text-muted-foreground tabular-nums">
            {t2 !== '' && !isNaN(parseFloat(t2)) ? `${parseFloat(t2).toFixed(3)}%` : '0.000%'}
          </p>
        </div>

        {/* T — Instalment payable (read-only) */}
        <div className="space-y-1">
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            Instalment payable (T)
          </label>
          <div className="px-3 py-2 rounded-lg border border-border bg-muted/50 min-h-[38px] flex items-center">
            <p className="text-sm font-mono font-semibold text-foreground tabular-nums">
              {payable != null ? formatCurrency(parseFloat(payable), { fractionDigits: 2 }) : '$0.00'}
            </p>
          </div>
          <p className="text-[10px] text-muted-foreground">T1 × T2 (computed)</p>
        </div>
      </div>

      {saveError && (
        <p className="text-xs text-status-danger">{saveError}</p>
      )}
    </div>
  );
}
