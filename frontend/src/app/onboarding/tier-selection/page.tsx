'use client';

import { useAuth } from '@clerk/nextjs';
import { Check } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useOnboarding } from '@/hooks/useOnboarding';
import { setAuthToken } from '@/lib/api/onboarding';

const FEATURES = [
  'Full platform access',
  'BAS preparation + tax planning',
  'AI-powered insights & analysis',
  'Client portal with magic link access',
  'Deep Xero integration',
  'ATO knowledge base with RAG',
  'Unlimited team members',
  'Priority support',
  'New modules as they ship',
];

export default function TierSelectionPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const { selectTierAndStartTrial, isLoading } = useOnboarding({
    skipInitialFetch: true,
  });
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const handleStart = async () => {
    setStarting(true);
    setError(null);

    try {
      const token = await getToken();
      if (token) {
        setAuthToken(token);
      }

      await selectTierAndStartTrial('starter', true);
      router.push('/onboarding/connect-xero');
    } catch (err) {
      console.error('Failed to start trial:', err);
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to start trial. Please try again.'
      );
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="space-y-8 max-w-lg mx-auto">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-foreground">
          Start your free trial
        </h1>
        <p className="mt-2 text-lg text-muted-foreground">
          14 days free. No credit card required.
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4 text-center">
          <p className="text-status-danger">{error}</p>
        </div>
      )}

      {/* Single plan card */}
      <Card className="border-2 border-primary">
        <CardContent className="pt-6 space-y-6">
          {/* Price */}
          <div className="text-center">
            <div className="flex items-baseline justify-center gap-1">
              <span className="text-4xl font-bold text-foreground">$299</span>
              <span className="text-muted-foreground">/month</span>
            </div>
            <p className="text-sm text-primary font-medium mt-1">
              Introductory pricing — locked in for early partners
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Unlimited clients. Unlimited team members.
            </p>
          </div>

          {/* Features */}
          <ul className="space-y-3">
            {FEATURES.map((feature) => (
              <li key={feature} className="flex items-start gap-2">
                <Check className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                <span className="text-sm text-muted-foreground">{feature}</span>
              </li>
            ))}
          </ul>

          {/* CTA */}
          <Button
            onClick={handleStart}
            disabled={isLoading || starting}
            className="w-full"
            size="lg"
          >
            {starting ? 'Starting trial...' : 'Start 14-Day Free Trial'}
          </Button>

          <p className="text-xs text-center text-muted-foreground">
            No credit card required. Cancel anytime.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
