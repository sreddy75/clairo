'use client';

import { Check, Loader2, Sparkles } from 'lucide-react';
import { useState } from 'react';

import { getTiers, redirectToCheckout } from '@/lib/api/billing';
import { cn } from '@/lib/utils';
import type { TierInfo, SubscriptionTier } from '@/types/billing';

interface PricingTableProps {
  currentTier?: SubscriptionTier | null;
  onSelectTier?: (tier: SubscriptionTier) => void;
  className?: string;
}

/**
 * Pricing table displaying all subscription tiers with features.
 * Highlights the recommended tier and handles checkout redirect.
 */
export function PricingTable({
  currentTier = null,
  onSelectTier,
  className,
}: PricingTableProps) {
  const [tiers, setTiers] = useState<TierInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [processingTier, setProcessingTier] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch tiers on mount
  useState(() => {
    const fetchTiers = async () => {
      try {
        const response = await getTiers();
        setTiers(response.tiers);
      } catch (err) {
        setError('Failed to load pricing. Please try again.');
        console.error('Failed to fetch tiers:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchTiers();
  });

  const handleSelectTier = async (tier: SubscriptionTier) => {
    if (tier === 'enterprise') {
      // For enterprise, redirect to contact page
      window.location.href = '/contact?plan=enterprise';
      return;
    }

    setProcessingTier(tier);
    setError(null);

    try {
      if (onSelectTier) {
        onSelectTier(tier);
      } else {
        await redirectToCheckout(tier);
      }
    } catch (err) {
      setError('Failed to start checkout. Please try again.');
      console.error('Checkout error:', err);
    } finally {
      setProcessingTier(null);
    }
  };

  const formatPrice = (priceCents: number) => {
    return `$${(priceCents / 100).toFixed(0)}`;
  };

  const isRecommended = (tierName: string) => tierName === 'professional';
  const isCurrent = (tierName: string) => tierName === currentTier;

  if (isLoading) {
    return (
      <div className={cn('py-12', className)}>
        <div className="flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-3 text-muted-foreground">Loading pricing...</span>
        </div>
      </div>
    );
  }

  if (error && tiers.length === 0) {
    return (
      <div className={cn('py-12 text-center', className)}>
        <p className="text-destructive">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 text-sm text-primary hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className={cn('py-8', className)}>
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
        {tiers.map((tier) => (
          <div
            key={tier.name}
            className={cn(
              'relative rounded-2xl border bg-card p-6 shadow-sm transition-all hover:shadow-md',
              isRecommended(tier.name)
                ? 'border-primary ring-2 ring-primary'
                : 'border-border',
              isCurrent(tier.name) && 'bg-muted'
            )}
          >
            {/* Recommended badge */}
            {isRecommended(tier.name) && (
              <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                <span className="inline-flex items-center gap-1 rounded-full bg-primary px-4 py-1 text-sm font-semibold text-white">
                  <Sparkles className="h-4 w-4" />
                  Recommended
                </span>
              </div>
            )}

            {/* Current plan badge */}
            {isCurrent(tier.name) && (
              <div className="absolute -top-4 right-4">
                <span className="inline-flex items-center rounded-full bg-muted-foreground px-3 py-1 text-xs font-medium text-white">
                  Current Plan
                </span>
              </div>
            )}

            {/* Tier header */}
            <div className="text-center">
              <h3 className="text-lg font-semibold text-foreground">
                {tier.display_name}
              </h3>
              <div className="mt-4">
                {tier.price_monthly > 0 ? (
                  <>
                    <span className="text-4xl font-bold text-foreground">
                      {formatPrice(tier.price_monthly)}
                    </span>
                    <span className="text-muted-foreground">/month</span>
                  </>
                ) : (
                  <span className="text-2xl font-bold text-foreground">
                    Contact Sales
                  </span>
                )}
              </div>
            </div>

            {/* Client limit */}
            <div className="mt-4 text-center text-sm text-muted-foreground">
              {tier.features.max_clients ? (
                <span>Up to {tier.features.max_clients} clients</span>
              ) : (
                <span>Unlimited clients</span>
              )}
            </div>

            {/* CTA Button */}
            <button
              onClick={() => handleSelectTier(tier.name)}
              disabled={
                processingTier !== null ||
                isCurrent(tier.name)
              }
              className={cn(
                'mt-6 w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors',
                isRecommended(tier.name)
                  ? 'bg-primary text-white hover:bg-primary/90 disabled:bg-primary/40'
                  : 'bg-foreground text-background hover:bg-foreground/90 disabled:bg-muted-foreground',
                isCurrent(tier.name) && 'bg-muted text-muted-foreground cursor-not-allowed'
              )}
            >
              {processingTier === tier.name ? (
                <span className="inline-flex items-center">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </span>
              ) : isCurrent(tier.name) ? (
                'Current Plan'
              ) : tier.name === 'enterprise' ? (
                'Contact Sales'
              ) : currentTier ? (
                'Switch Plan'
              ) : (
                'Get Started'
              )}
            </button>

            {/* Highlights */}
            <ul className="mt-6 space-y-3">
              {tier.highlights.map((highlight, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <Check className="h-5 w-5 flex-shrink-0 text-status-success" />
                  <span className="text-sm text-muted-foreground">{highlight}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Feature comparison link */}
      <div className="mt-8 text-center">
        <a
          href="#features"
          className="text-sm text-primary hover:underline"
        >
          Compare all features
        </a>
      </div>
    </div>
  );
}

export default PricingTable;
