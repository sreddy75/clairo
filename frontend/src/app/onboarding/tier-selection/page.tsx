'use client';

import { useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { TierCard } from '@/components/onboarding/TierCard';
import { useOnboarding } from '@/hooks/useOnboarding';
import { setAuthToken, type SubscriptionTier } from '@/lib/api/onboarding';

interface Tier {
  id: SubscriptionTier;
  name: string;
  price: number;
  clientLimit: number;
  features: string[];
  recommended?: boolean;
}

const tiers: Tier[] = [
  {
    id: 'starter',
    name: 'Starter',
    price: 99,
    clientLimit: 25,
    features: [
      'Up to 25 clients',
      'Core BAS preparation',
      'Basic AI insights',
      'Email support',
    ],
  },
  {
    id: 'professional',
    name: 'Professional',
    price: 299,
    clientLimit: 100,
    recommended: true,
    features: [
      'Up to 100 clients',
      'Full AI-powered insights',
      'Client portal access',
      'Smart triggers & alerts',
      'Priority support',
    ],
  },
  {
    id: 'growth',
    name: 'Growth',
    price: 599,
    clientLimit: 250,
    features: [
      'Up to 250 clients',
      'Everything in Professional',
      'API access',
      'Custom integrations',
      'Dedicated account manager',
    ],
  },
];

export default function TierSelectionPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  // Skip initial fetch since we need to set auth token first
  const { selectTierAndStartTrial, isLoading } = useOnboarding({
    skipInitialFetch: true,
  });
  const [selectedTier, setSelectedTier] = useState<SubscriptionTier | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);

  const handleSelectTier = async (tierId: SubscriptionTier) => {
    setSelectedTier(tierId);
    setError(null);

    try {
      // Refresh auth token before API call
      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      await selectTierAndStartTrial(tierId, true);
      // Navigate to connect-xero (no Stripe redirect)
      router.push('/onboarding/connect-xero');
    } catch (err) {
      console.error('Failed to select tier:', err);
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to start trial. Please try again.'
      );
      setSelectedTier(null);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-foreground">Choose your plan</h1>
        <p className="mt-2 text-lg text-muted-foreground">
          Start your 14-day free trial. No credit card required.
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4 text-center">
          <p className="text-status-danger">{error}</p>
        </div>
      )}

      {/* Trial badge */}
      <div className="flex justify-center">
        <span className="inline-flex items-center px-4 py-2 rounded-full text-sm font-medium bg-status-success/10 text-status-success">
          <svg
            className="w-5 h-5 mr-2"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
              clipRule="evenodd"
            />
          </svg>
          14-Day Free Trial — No Credit Card Required
        </span>
      </div>

      {/* Tier cards */}
      <div className="grid gap-6 md:grid-cols-3">
        {tiers.map((tier) => (
          <TierCard
            key={tier.id}
            name={tier.name}
            price={tier.price}
            clientLimit={tier.clientLimit}
            features={tier.features}
            recommended={tier.recommended}
            selected={selectedTier === tier.id}
            isLoading={isLoading && selectedTier === tier.id}
            onSelect={() => handleSelectTier(tier.id)}
          />
        ))}
      </div>

      {/* Enterprise CTA */}
      <div className="text-center pt-4">
        <p className="text-muted-foreground">
          Need more than 250 clients?{' '}
          <a href="/contact" className="text-primary hover:underline">
            Contact us for Enterprise pricing
          </a>
        </p>
      </div>
    </div>
  );
}
