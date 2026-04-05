'use client';

import {
  Calendar,
  ChevronRight,
  CreditCard,
  Loader2,
  TrendingDown,
  TrendingUp,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';

import {
  cancelSubscription,
  openBillingPortal,
} from '@/lib/api/billing';
import { cn } from '@/lib/utils';
import type { SubscriptionResponse, SubscriptionTier } from '@/types/billing';

interface SubscriptionCardProps {
  subscription: SubscriptionResponse;
  onUpgrade?: (tier: SubscriptionTier) => void;
  onDowngrade?: (tier: SubscriptionTier) => void;
  onSubscribe?: (tier: SubscriptionTier) => void;
  onRefresh?: () => void;
  className?: string;
}

/**
 * Subscription card displaying current plan and management options.
 */
export function SubscriptionCard({
  subscription,
  onUpgrade,
  onDowngrade,
  onSubscribe,
  onRefresh,
  className,
}: SubscriptionCardProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const formatTier = (tier: string) => {
    return tier.charAt(0).toUpperCase() + tier.slice(1);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800';
      case 'grandfathered':
        return 'bg-purple-100 text-purple-800';
      case 'past_due':
        return 'bg-red-100 text-red-800';
      case 'suspended':
        return 'bg-red-100 text-red-800';
      case 'cancelled':
        return 'bg-muted text-foreground';
      default:
        return 'bg-muted text-foreground';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'active':
        return 'Active';
      case 'grandfathered':
        return 'Grandfathered';
      case 'past_due':
        return 'Past Due';
      case 'cancelled':
        return 'Cancelled';
      case 'suspended':
        return 'Suspended';
      case 'trial':
        return 'Trial';
      default:
        return status;
    }
  };

  const handleManageBilling = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await openBillingPortal();
    } catch (err) {
      setError('Failed to open billing portal');
      console.error(err);
      setIsLoading(false);
    }
  };

  const handleCancel = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await cancelSubscription({ reason: cancelReason || undefined });
      setShowCancelModal(false);
      onRefresh?.();
    } catch (err) {
      setError('Failed to cancel subscription');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const isGrandfathered = subscription.status === 'grandfathered';
  const isPastDue = subscription.status === 'past_due';
  const hasScheduledChange = subscription.scheduled_change !== null;

  return (
    <>
      <div className={cn('bg-card rounded-lg border shadow-sm', className)}>
        {/* Header */}
        <div className="px-6 py-4 border-b">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-foreground">
              Subscription
            </h3>
            <span
              className={cn(
                'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                getStatusColor(subscription.status)
              )}
            >
              {getStatusLabel(subscription.status)}
            </span>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          {/* Current Plan */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Current Plan</p>
              <p className="text-2xl font-bold text-foreground">
                {formatTier(subscription.tier)}
              </p>
            </div>
            {subscription.tier !== 'enterprise' && (
              <button
                onClick={() => onUpgrade?.(subscription.tier as SubscriptionTier)}
                className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800"
              >
                <TrendingUp className="h-4 w-4 mr-1" />
                Upgrade
              </button>
            )}
          </div>

          {/* Grandfathered notice */}
          {isGrandfathered && (
            <div className="mt-4 p-3 bg-purple-50 rounded-lg">
              <p className="text-sm text-purple-800">
                <strong>Grandfathered Account:</strong> You have full Professional
                tier access at no charge. Thank you for being an early adopter!
              </p>
            </div>
          )}

          {/* Past due warning */}
          {isPastDue && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-800">
                <strong>Payment Past Due:</strong> Please update your payment
                method to avoid service interruption.
              </p>
              <button
                onClick={handleManageBilling}
                disabled={isLoading}
                className="mt-2 text-sm font-medium text-red-600 hover:text-red-800"
              >
                Update Payment Method
              </button>
            </div>
          )}

          {/* Billing info */}
          {!isGrandfathered && subscription.current_period_end && (
            <div className="mt-4 flex items-center text-sm text-muted-foreground">
              <Calendar className="h-4 w-4 mr-2" />
              <span>
                {hasScheduledChange ? 'Changes take effect' : 'Next billing date'}:{' '}
                <strong>{formatDate(subscription.current_period_end)}</strong>
              </span>
            </div>
          )}

          {/* Scheduled change notice */}
          {hasScheduledChange && subscription.scheduled_change && (
            <div className={`mt-4 p-3 rounded-lg border ${
              subscription.scheduled_change.is_cancellation
                ? 'bg-red-50 border-red-200'
                : 'bg-yellow-50 border-yellow-200'
            }`}>
              <div className="flex items-start gap-2">
                {subscription.scheduled_change.is_cancellation ? (
                  <XCircle className="h-4 w-4 text-red-600 mt-0.5" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-yellow-600 mt-0.5" />
                )}
                <div>
                  <p className={`text-sm ${
                    subscription.scheduled_change.is_cancellation
                      ? 'text-red-800'
                      : 'text-yellow-800'
                  }`}>
                    {subscription.scheduled_change.is_cancellation ? (
                      <>
                        <strong>Cancellation Scheduled:</strong> Your subscription will end on{' '}
                        {formatDate(subscription.scheduled_change.effective_date)}. You&apos;ll
                        continue to have access until then.
                      </>
                    ) : (
                      <>
                        <strong>Scheduled Change:</strong> Your plan will change to{' '}
                        {subscription.scheduled_change.new_tier && formatTier(subscription.scheduled_change.new_tier)} on{' '}
                        {formatDate(subscription.scheduled_change.effective_date)}.
                      </>
                    )}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Usage info */}
          {subscription.usage && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Clients</span>
                <span className="font-medium text-foreground">
                  {subscription.usage.client_count}
                  {subscription.usage.client_limit
                    ? ` / ${subscription.usage.client_limit}`
                    : ' (unlimited)'}
                </span>
              </div>
              {subscription.usage.client_limit && (
                <div className="mt-2 w-full bg-muted rounded-full h-2">
                  <div
                    className={cn(
                      'h-2 rounded-full',
                      subscription.usage.is_at_limit
                        ? 'bg-red-500'
                        : subscription.usage.is_approaching_limit
                          ? 'bg-yellow-500'
                          : 'bg-green-500'
                    )}
                    style={{
                      width: `${Math.min(subscription.usage.percentage_used ?? 0, 100)}%`,
                    }}
                  />
                </div>
              )}
            </div>
          )}

          {/* Error message */}
          {error && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="px-6 py-4 bg-muted border-t rounded-b-lg">
          <div className="flex flex-wrap gap-3">
            {/* Subscribe button for trial users */}
            {subscription.status === 'trial' && (
              <button
                onClick={() => onSubscribe?.(subscription.tier as SubscriptionTier)}
                disabled={isLoading}
                className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <CreditCard className="h-4 w-4 mr-2" />
                )}
                Subscribe Now
              </button>
            )}

            {!isGrandfathered && (
              <button
                onClick={handleManageBilling}
                disabled={isLoading}
                className={cn(
                  'inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50',
                  subscription.status === 'suspended'
                    ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                    : 'border border-border text-muted-foreground bg-card hover:bg-muted'
                )}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <CreditCard className="h-4 w-4 mr-2" />
                )}
                {subscription.status === 'trial' ? 'Add Payment Method' : subscription.status === 'suspended' ? 'Reactivate' : 'Manage Billing'}
              </button>
            )}

            {subscription.tier !== 'starter' && !isGrandfathered && (
              <button
                onClick={() =>
                  onDowngrade?.(subscription.tier as SubscriptionTier)
                }
                className="inline-flex items-center px-4 py-2 border border-border rounded-lg text-sm font-medium text-muted-foreground bg-card hover:bg-muted"
              >
                <TrendingDown className="h-4 w-4 mr-2" />
                Downgrade
              </button>
            )}

            {!isGrandfathered &&
              subscription.status !== 'cancelled' && (
                <button
                  onClick={() => setShowCancelModal(true)}
                  className="inline-flex items-center px-4 py-2 border border-red-300 rounded-lg text-sm font-medium text-red-700 bg-card hover:bg-red-50"
                >
                  <XCircle className="h-4 w-4 mr-2" />
                  Cancel
                </button>
              )}
          </div>

          <div className="mt-4">
            <button
              onClick={() => document.getElementById('compare-plans')?.scrollIntoView({ behavior: 'smooth' })}
              className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
            >
              View all plans
              <ChevronRight className="h-4 w-4 ml-1" />
            </button>
          </div>
        </div>
      </div>

      {/* Cancel Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-card rounded-lg max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-foreground">
              Cancel Subscription
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Are you sure you want to cancel? You&apos;ll continue to have access
              until the end of your current billing period.
            </p>

            <div className="mt-4">
              <label className="block text-sm font-medium text-muted-foreground">
                Reason for canceling (optional)
              </label>
              <textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                rows={3}
                className="mt-1 block w-full rounded-lg border border-input px-3 py-2 text-sm focus:border-primary focus:ring-primary"
                placeholder="Tell us why you're leaving..."
              />
            </div>

            <div className="mt-6 flex gap-3 justify-end">
              <button
                onClick={() => setShowCancelModal(false)}
                className="px-4 py-2 border border-border rounded-lg text-sm font-medium text-foreground hover:bg-muted"
              >
                Keep Subscription
              </button>
              <button
                onClick={handleCancel}
                disabled={isLoading}
                className="px-4 py-2 bg-destructive text-destructive-foreground rounded-lg text-sm font-medium hover:bg-destructive/90 disabled:opacity-50"
              >
                {isLoading ? 'Canceling...' : 'Confirm Cancellation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default SubscriptionCard;
