'use client';

import { CheckCircle2, XCircle } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';

import { PricingTable } from '@/components/billing/PricingTable';

/**
 * Public pricing page displaying all subscription tiers.
 * Handles success/cancel states from Stripe checkout redirect.
 */
function PricingContent() {
  const searchParams = useSearchParams();
  const [message, setMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  useEffect(() => {
    // Handle checkout result
    const canceled = searchParams.get('canceled');
    if (canceled === 'true') {
      setMessage({
        type: 'error',
        text: 'Checkout was canceled. You can try again when ready.',
      });
    }
  }, [searchParams]);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <a href="/" className="text-2xl font-bold text-primary">
              Clairo
            </a>
            <div className="flex items-center gap-4">
              <a
                href="/sign-in"
                className="text-muted-foreground hover:text-foreground"
              >
                Sign in
              </a>
              <a
                href="/sign-up"
                className="rounded-lg bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
              >
                Get Started
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Status message */}
        {message && (
          <div
            className={`mb-8 p-4 rounded-lg flex items-start gap-3 ${
              message.type === 'success'
                ? 'bg-status-success/10 border border-status-success/20'
                : 'bg-status-danger/10 border border-status-danger/20'
            }`}
          >
            {message.type === 'success' ? (
              <CheckCircle2 className="h-5 w-5 text-status-success flex-shrink-0 mt-0.5" />
            ) : (
              <XCircle className="h-5 w-5 text-status-danger flex-shrink-0 mt-0.5" />
            )}
            <p
              className={
                message.type === 'success' ? 'text-status-success' : 'text-status-danger'
              }
            >
              {message.text}
            </p>
          </div>
        )}

        {/* Page header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-foreground">
            Simple, Transparent Pricing
          </h1>
          <p className="mt-4 text-xl text-muted-foreground max-w-2xl mx-auto">
            Choose the plan that fits your practice. All plans include core BAS
            preparation features.
          </p>
        </div>

        {/* Pricing table */}
        <PricingTable />

        {/* FAQ Section */}
        <div id="faq" className="mt-16">
          <h2 className="text-2xl font-bold text-foreground text-center mb-8">
            Frequently Asked Questions
          </h2>
          <div className="max-w-3xl mx-auto space-y-6">
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="font-semibold text-foreground">
                Can I change plans later?
              </h3>
              <p className="mt-2 text-muted-foreground">
                Yes! You can upgrade or downgrade at any time. Upgrades are
                immediate with prorated billing. Downgrades take effect at your
                next billing cycle.
              </p>
            </div>
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="font-semibold text-foreground">
                What counts as a client?
              </h3>
              <p className="mt-2 text-muted-foreground">
                A client is defined as a connected Xero organisation. You can
                have multiple BAS periods per client without affecting your
                client count.
              </p>
            </div>
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="font-semibold text-foreground">
                Is there a free trial?
              </h3>
              <p className="mt-2 text-muted-foreground">
                New accounts start with full access during onboarding. After
                setup, you&apos;ll choose a plan that fits your needs.
              </p>
            </div>
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="font-semibold text-foreground">
                What payment methods do you accept?
              </h3>
              <p className="mt-2 text-muted-foreground">
                We accept all major credit cards (Visa, Mastercard, American
                Express) through our secure payment partner Stripe.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PricingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background flex items-center justify-center">Loading...</div>}>
      <PricingContent />
    </Suspense>
  );
}
