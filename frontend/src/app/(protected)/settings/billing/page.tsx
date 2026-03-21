'use client';

import { useAuth } from '@clerk/nextjs';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { SubscriptionCard } from '@/components/billing/SubscriptionCard';
import { UsageDashboard } from '@/components/billing/UsageDashboard';
import {
  getSubscription,
  upgradeSubscription,
  downgradeSubscription,
  getTiers,
  setAuthToken,
  redirectToCheckout,
} from '@/lib/api/billing';
import { cn } from '@/lib/utils';
import type { SubscriptionResponse, TierInfo, SubscriptionTier } from '@/types/billing';

/**
 * Billing settings page for managing subscription.
 */
export default function BillingSettingsPage() {
  const router = useRouter();
  const { getToken, isLoaded } = useAuth();
  const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
  const [tiers, setTiers] = useState<TierInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [showDowngradeModal, setShowDowngradeModal] = useState(false);
  const [selectedTier, setSelectedTier] = useState<SubscriptionTier | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const fetchData = async () => {
    try {
      // Get and set auth token before making requests
      const token = await getToken();
      setAuthToken(token);

      const [subResponse, tiersResponse] = await Promise.all([
        getSubscription(),
        getTiers(),
      ]);
      setSubscription(subResponse);
      setTiers(tiersResponse.tiers);
    } catch (err) {
      setError('Failed to load subscription data');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isLoaded) {
      fetchData();
    }
  }, [isLoaded]);

  const handleUpgrade = async (currentTier: SubscriptionTier) => {
    // If on trial, redirect to Stripe Checkout instead of upgrade API
    if (subscription?.status === 'trial') {
      // Find next tier up
      const tierOrder = ['starter', 'professional', 'growth', 'enterprise'];
      const currentIndex = tierOrder.indexOf(currentTier);
      const nextTier = tierOrder[currentIndex + 1];
      if (nextTier && nextTier !== 'enterprise') {
        setIsProcessing(true);
        setError(null);
        try {
          await redirectToCheckout(nextTier);
        } catch (err) {
          setError('Failed to start checkout');
          console.error(err);
          setIsProcessing(false);
        }
      }
      return;
    }

    // For active subscriptions, use the upgrade modal
    const tierOrder = ['starter', 'professional', 'growth', 'enterprise'];
    const currentIndex = tierOrder.indexOf(currentTier);
    const availableTiers = tiers.filter(
      (t) => tierOrder.indexOf(t.name) > currentIndex && t.name !== 'enterprise'
    );
    const firstTier = availableTiers[0];
    if (firstTier) {
      setSelectedTier(firstTier.name);
      setShowUpgradeModal(true);
    }
  };

  const handleSubscribe = async (tier: SubscriptionTier) => {
    // Redirect to Stripe Checkout for the selected tier
    setIsProcessing(true);
    setError(null);
    try {
      await redirectToCheckout(tier);
    } catch (err) {
      setError('Failed to start checkout');
      console.error(err);
      setIsProcessing(false);
    }
  };

  const handleDowngrade = (currentTier: SubscriptionTier) => {
    // Find tiers lower than current
    const tierOrder = ['starter', 'professional', 'growth', 'enterprise'];
    const currentIndex = tierOrder.indexOf(currentTier);
    const availableTiers = tiers.filter(
      (t) => tierOrder.indexOf(t.name) < currentIndex
    );
    const lastTier = availableTiers[availableTiers.length - 1];
    if (lastTier) {
      setSelectedTier(lastTier.name);
      setShowDowngradeModal(true);
    }
  };

  const confirmUpgrade = async () => {
    if (!selectedTier) return;

    setIsProcessing(true);
    setError(null);
    try {
      const updated = await upgradeSubscription({ new_tier: selectedTier });
      setSubscription(updated);
      setShowUpgradeModal(false);
    } catch (err) {
      setError('Failed to upgrade subscription');
      console.error(err);
    } finally {
      setIsProcessing(false);
    }
  };

  const confirmDowngrade = async () => {
    if (!selectedTier) return;

    setIsProcessing(true);
    setError(null);
    try {
      const updated = await downgradeSubscription({ new_tier: selectedTier });
      setSubscription(updated);
      setShowDowngradeModal(false);
    } catch (err) {
      setError('Failed to schedule downgrade');
      console.error(err);
    } finally {
      setIsProcessing(false);
    }
  };

  const formatPrice = (priceCents: number) => {
    return `$${(priceCents / 100).toFixed(0)}`;
  };

  const formatTier = (tier: string) => {
    return tier.charAt(0).toUpperCase() + tier.slice(1);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Settings
        </button>
        <h1 className="text-xl font-bold text-foreground">Billing & Subscription</h1>
        <p className="mt-1 text-muted-foreground">
          Manage your subscription plan and billing preferences.
        </p>
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-6 p-4 bg-status-danger/10 border border-status-danger/20 rounded-lg text-status-danger">
          {error}
        </div>
      )}

      {/* Subscription card */}
      {subscription && (
        <SubscriptionCard
          subscription={subscription}
          onUpgrade={handleUpgrade}
          onDowngrade={handleDowngrade}
          onSubscribe={handleSubscribe}
          onRefresh={fetchData}
          className="mb-8"
        />
      )}

      {/* Usage Dashboard - Spec 020 */}
      <UsageDashboard className="mb-8" />

      {/* Feature comparison */}
      <div id="compare-plans" className="bg-card rounded-lg border shadow-sm scroll-mt-8">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-foreground">
            Compare Plans
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-muted">
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Feature
                </th>
                {tiers.map((tier) => (
                  <th
                    key={tier.name}
                    className={cn(
                      'px-6 py-3 text-center text-xs font-medium uppercase tracking-wider',
                      tier.name === subscription?.tier
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-foreground'
                    )}
                  >
                    {tier.display_name}
                    {tier.name === subscription?.tier && (
                      <span className="block text-xs font-normal normal-case">
                        (Current)
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <tr>
                <td className="px-6 py-4 text-sm text-foreground">Price</td>
                {tiers.map((tier) => (
                  <td
                    key={tier.name}
                    className={cn(
                      'px-6 py-4 text-center text-sm',
                      tier.name === subscription?.tier ? 'bg-primary/10' : ''
                    )}
                  >
                    {tier.price_monthly > 0
                      ? `${formatPrice(tier.price_monthly)}/mo`
                      : 'Custom'}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-6 py-4 text-sm text-foreground">Clients</td>
                {tiers.map((tier) => (
                  <td
                    key={tier.name}
                    className={cn(
                      'px-6 py-4 text-center text-sm',
                      tier.name === subscription?.tier ? 'bg-primary/10' : ''
                    )}
                  >
                    {tier.features.max_clients ?? 'Unlimited'}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-6 py-4 text-sm text-foreground">AI Insights</td>
                {tiers.map((tier) => (
                  <td
                    key={tier.name}
                    className={cn(
                      'px-6 py-4 text-center text-sm',
                      tier.name === subscription?.tier ? 'bg-primary/10' : ''
                    )}
                  >
                    {tier.features.ai_insights === 'full' ? 'Full' : 'Basic'}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-6 py-4 text-sm text-foreground">Client Portal</td>
                {tiers.map((tier) => (
                  <td
                    key={tier.name}
                    className={cn(
                      'px-6 py-4 text-center text-sm',
                      tier.name === subscription?.tier ? 'bg-primary/10' : ''
                    )}
                  >
                    {tier.features.client_portal ? '✓' : '—'}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-6 py-4 text-sm text-foreground">Custom Triggers</td>
                {tiers.map((tier) => (
                  <td
                    key={tier.name}
                    className={cn(
                      'px-6 py-4 text-center text-sm',
                      tier.name === subscription?.tier ? 'bg-primary/10' : ''
                    )}
                  >
                    {tier.features.custom_triggers ? '✓' : '—'}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-6 py-4 text-sm text-foreground">Magic Zone</td>
                {tiers.map((tier) => (
                  <td
                    key={tier.name}
                    className={cn(
                      'px-6 py-4 text-center text-sm',
                      tier.name === subscription?.tier ? 'bg-primary/10' : ''
                    )}
                  >
                    {tier.features.magic_zone ? '✓' : '—'}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-6 py-4 text-sm text-foreground">API Access</td>
                {tiers.map((tier) => (
                  <td
                    key={tier.name}
                    className={cn(
                      'px-6 py-4 text-center text-sm',
                      tier.name === subscription?.tier ? 'bg-primary/10' : ''
                    )}
                  >
                    {tier.features.api_access ? '✓' : '—'}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Upgrade Modal */}
      {showUpgradeModal && selectedTier && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-card rounded-lg max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-foreground">
              Upgrade to {formatTier(selectedTier)}
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Your subscription will be upgraded immediately. You&apos;ll be charged
              a prorated amount for the remainder of your billing period.
            </p>

            <div className="mt-6 flex gap-3 justify-end">
              <button
                onClick={() => setShowUpgradeModal(false)}
                disabled={isProcessing}
                className="px-4 py-2 border border-border rounded-lg text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmUpgrade}
                disabled={isProcessing}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                {isProcessing ? 'Processing...' : 'Confirm Upgrade'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Downgrade Modal */}
      {showDowngradeModal && selectedTier && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-card rounded-lg max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-foreground">
              Downgrade to {formatTier(selectedTier)}
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Your downgrade will take effect at the end of your current billing
              period. You&apos;ll continue to have access to your current features
              until then.
            </p>

            {subscription?.usage && subscription.usage.client_limit && (
              <div className="mt-4 p-3 bg-status-warning/10 border border-status-warning/20 rounded-lg">
                <p className="text-sm text-status-warning">
                  <strong>Note:</strong> The {formatTier(selectedTier)} plan has a
                  lower client limit. You currently have{' '}
                  {subscription.usage.client_count} clients. You won&apos;t be able to
                  add more clients after downgrading.
                </p>
              </div>
            )}

            <div className="mt-6 flex gap-3 justify-end">
              <button
                onClick={() => setShowDowngradeModal(false)}
                disabled={isProcessing}
                className="px-4 py-2 border border-border rounded-lg text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDowngrade}
                disabled={isProcessing}
                className="px-4 py-2 bg-status-warning text-white rounded-lg text-sm font-medium hover:bg-status-warning/90 disabled:opacity-50"
              >
                {isProcessing ? 'Processing...' : 'Schedule Downgrade'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
