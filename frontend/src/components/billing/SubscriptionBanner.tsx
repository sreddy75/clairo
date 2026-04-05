'use client';

import { AlertTriangle, CreditCard } from 'lucide-react';
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface SubscriptionBannerProps {
  status: 'suspended' | 'past_due' | 'cancelled';
  currentPeriodEnd?: string | null;
}

export function SubscriptionBanner({ status, currentPeriodEnd }: SubscriptionBannerProps) {
  if (status === 'past_due') {
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
          <Button variant="outline" size="sm" className="shrink-0 border-amber-300 text-amber-800 hover:bg-amber-100" asChild>
            <Link href="/settings/billing">
              <CreditCard className="h-3.5 w-3.5 mr-1.5" />
              Update Payment
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      'border-b px-6 py-3',
      status === 'suspended'
        ? 'bg-red-50 border-red-200'
        : 'bg-stone-100 border-stone-200'
    )}>
      <div className="flex items-center justify-between max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <AlertTriangle className={cn(
            'h-4 w-4 shrink-0',
            status === 'suspended' ? 'text-red-600' : 'text-stone-600'
          )} />
          <p className={cn(
            'text-sm',
            status === 'suspended' ? 'text-red-800' : 'text-stone-800'
          )}>
            {status === 'suspended' ? (
              <>
                <span className="font-medium">Your subscription is suspended</span> — update your payment method to continue using Clairo.
              </>
            ) : (
              <>
                <span className="font-medium">Your subscription has ended</span> — resubscribe to regain full access.
              </>
            )}
          </p>
        </div>
        <Button
          size="sm"
          variant={status === 'suspended' ? 'default' : 'outline'}
          className="shrink-0"
          asChild
        >
          <Link href="/settings/billing">
            <CreditCard className="h-3.5 w-3.5 mr-1.5" />
            {status === 'suspended' ? 'Resolve' : 'Resubscribe'}
          </Link>
        </Button>
      </div>
    </div>
  );
}
