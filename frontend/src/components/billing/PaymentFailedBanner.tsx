'use client';

import { AlertTriangle, CreditCard } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { openBillingPortal } from '@/lib/api/billing';

interface PaymentFailedBannerProps {
  currentPeriodEnd: string | null;
}

export function PaymentFailedBanner({ currentPeriodEnd }: PaymentFailedBannerProps) {
  const daysRemaining = currentPeriodEnd
    ? Math.max(0, Math.ceil((new Date(currentPeriodEnd).getTime() - Date.now()) / (1000 * 60 * 60 * 24)) + 7)
    : 7;

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-6 py-3">
      <div className="flex items-center justify-between max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
          <p className="text-sm text-amber-800">
            <span className="font-medium">Payment failed</span> — update your payment method within{' '}
            <span className="font-semibold">{daysRemaining} day{daysRemaining !== 1 ? 's' : ''}</span>{' '}
            to avoid service interruption.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0 border-amber-300 text-amber-800 hover:bg-amber-100"
          onClick={() => openBillingPortal()}
        >
          <CreditCard className="h-3.5 w-3.5 mr-1.5" />
          Update Payment
        </Button>
      </div>
    </div>
  );
}
