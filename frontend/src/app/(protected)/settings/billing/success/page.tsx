'use client';

import { CheckCircle2, Loader2 } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';

import { getSubscription } from '@/lib/api/billing';
import type { SubscriptionResponse } from '@/types/billing';

/**
 * Checkout success page.
 * Polls subscription status and redirects to dashboard when confirmed.
 */
export default function CheckoutSuccessPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(5);

  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    if (!sessionId) {
      router.push('/settings/billing');
      return;
    }

    let pollCount = 0;
    const maxPolls = 10;
    const pollInterval = 2000;

    const pollSubscription = async () => {
      try {
        const sub = await getSubscription();
        setSubscription(sub);

        // Check if subscription is active
        if (sub.status === 'active' || sub.status === 'grandfathered') {
          setIsPolling(false);
          return true;
        }

        pollCount++;
        if (pollCount >= maxPolls) {
          setIsPolling(false);
          setError(
            'Subscription confirmation is taking longer than expected. ' +
            'Your subscription should be active shortly.'
          );
          return false;
        }

        return false;
      } catch (err) {
        console.error('Failed to fetch subscription:', err);
        pollCount++;
        if (pollCount >= maxPolls) {
          setIsPolling(false);
          setError('Failed to confirm subscription. Please check your billing settings.');
          return false;
        }
        return false;
      }
    };

    // Initial poll
    pollSubscription();

    // Continue polling
    const interval = setInterval(async () => {
      const confirmed = await pollSubscription();
      if (confirmed) {
        clearInterval(interval);
      }
    }, pollInterval);

    return () => clearInterval(interval);
  }, [sessionId, router]);

  // Countdown and redirect
  useEffect(() => {
    if (!isPolling && subscription && !error) {
      const countdownInterval = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(countdownInterval);
            router.push('/dashboard');
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

      return () => clearInterval(countdownInterval);
    }
    return undefined;
  }, [isPolling, subscription, error, router]);

  const formatTier = (tier: string) => {
    return tier.charAt(0).toUpperCase() + tier.slice(1);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="bg-card rounded-2xl shadow-lg p-8 text-center">
          {isPolling ? (
            <>
              <Loader2 className="h-16 w-16 animate-spin text-primary mx-auto" />
              <h1 className="mt-6 text-xl font-bold text-foreground">
                Confirming Your Subscription
              </h1>
              <p className="mt-3 text-muted-foreground">
                Please wait while we confirm your payment...
              </p>
            </>
          ) : error ? (
            <>
              <div className="h-16 w-16 rounded-full bg-status-warning/10 flex items-center justify-center mx-auto">
                <span className="text-2xl">!</span>
              </div>
              <h1 className="mt-6 text-xl font-bold text-foreground">
                Processing Payment
              </h1>
              <p className="mt-3 text-muted-foreground">{error}</p>
              <div className="mt-6 space-y-3">
                <button
                  onClick={() => router.push('/settings/billing')}
                  className="w-full rounded-lg bg-primary px-4 py-2.5 text-primary-foreground font-semibold hover:bg-primary/90"
                >
                  Go to Billing Settings
                </button>
                <button
                  onClick={() => router.push('/dashboard')}
                  className="w-full rounded-lg border border-border px-4 py-2.5 text-foreground font-semibold hover:bg-muted"
                >
                  Go to Dashboard
                </button>
              </div>
            </>
          ) : subscription ? (
            <>
              <div className="h-16 w-16 rounded-full bg-status-success/10 flex items-center justify-center mx-auto">
                <CheckCircle2 className="h-10 w-10 text-status-success" />
              </div>
              <h1 className="mt-6 text-xl font-bold text-foreground">
                Welcome to {formatTier(subscription.tier)}!
              </h1>
              <p className="mt-3 text-muted-foreground">
                Your subscription is now active. You have full access to all{' '}
                {formatTier(subscription.tier)} features.
              </p>

              {/* Features summary */}
              <div className="mt-6 p-4 bg-muted rounded-lg text-left">
                <h3 className="text-sm font-semibold text-foreground mb-2">
                  Your Plan Includes:
                </h3>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li>
                    {subscription.usage?.client_limit ?? 'Unlimited'} clients
                  </li>
                  {subscription.features.ai_insights === 'full' && (
                    <li>Full AI insights & Magic Zone</li>
                  )}
                  {subscription.features.client_portal && <li>Client portal access</li>}
                  {subscription.features.custom_triggers && <li>Custom triggers</li>}
                  {subscription.features.api_access && <li>API access</li>}
                </ul>
              </div>

              <p className="mt-6 text-sm text-muted-foreground">
                Redirecting to dashboard in {countdown} seconds...
              </p>

              <button
                onClick={() => router.push('/dashboard')}
                className="mt-4 w-full rounded-lg bg-primary px-4 py-2.5 text-primary-foreground font-semibold hover:bg-primary/90"
              >
                Go to Dashboard Now
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
