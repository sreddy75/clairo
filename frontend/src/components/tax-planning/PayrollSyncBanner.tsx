'use client';

import { AlertCircle, Loader2 } from 'lucide-react';
import { useEffect, useRef } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

type PayrollSyncStatus = 'ready' | 'pending' | 'unavailable' | 'not_required' | null | undefined;

interface PayrollSyncBannerProps {
  status: PayrollSyncStatus;
  /**
   * Callback to re-fetch the tax plan. Invoked while status === "pending" on
   * a polling cadence that backs off after 30s (3s → 10s, capped at 2 min).
   */
  onPoll?: () => void;
}

const INITIAL_POLL_MS = 3000;
const BACKOFF_POLL_MS = 10_000;
const BACKOFF_AFTER_MS = 30_000;
const POLL_CAP_MS = 120_000;

/**
 * Spec 059 FR-006 — renders a persistent banner communicating payroll sync
 * state. `pending` polls the plan endpoint until status flips to `ready` or
 * the 2-minute cap is hit. `unavailable` asks the accountant to reconnect
 * Xero with payroll scope; `ready`/`not_required` render nothing.
 */
export function PayrollSyncBanner({ status, onPoll }: PayrollSyncBannerProps) {
  const startedAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (status !== 'pending' || !onPoll) {
      startedAtRef.current = null;
      return;
    }

    if (startedAtRef.current === null) {
      startedAtRef.current = Date.now();
    }

    const schedule = () => {
      const elapsed = Date.now() - (startedAtRef.current ?? Date.now());
      if (elapsed > POLL_CAP_MS) return null;
      const interval = elapsed < BACKOFF_AFTER_MS ? INITIAL_POLL_MS : BACKOFF_POLL_MS;
      return window.setTimeout(() => {
        onPoll();
        const next = schedule();
        if (next !== null) timerRef.current = next;
      }, interval);
    };

    const timerRef = { current: schedule() };
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, [status, onPoll]);

  if (status === 'pending') {
    return (
      <Alert className="border-amber-300 bg-amber-50 text-amber-900">
        <Loader2 className="h-4 w-4 animate-spin" />
        <AlertTitle className="text-amber-900">Payroll still syncing</AlertTitle>
        <AlertDescription className="text-amber-800">
          Figures will refresh automatically as soon as Xero responds. No need to reload.
        </AlertDescription>
      </Alert>
    );
  }

  if (status === 'unavailable') {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Payroll data unavailable</AlertTitle>
        <AlertDescription>
          Reconnect Xero with payroll scope to load Super YTD and PAYG Withheld. Super and
          PAYGW figures will remain blank until this is fixed.
        </AlertDescription>
      </Alert>
    );
  }

  return null;
}
