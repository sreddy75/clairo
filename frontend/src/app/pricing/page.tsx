'use client';

import { ArrowRight, Zap } from 'lucide-react';
import Link from 'next/link';

/**
 * Public pricing page — outcome-based teaser while pricing is being finalised.
 */
export default function PricingPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <a href="/" className="text-2xl font-bold text-primary">
              Clairo
            </a>
            <div className="flex items-center gap-4">
              <a href="/sign-in" className="text-muted-foreground hover:text-foreground">
                Sign in
              </a>
              <a
                href="/sign-up"
                className="rounded-lg bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
              >
                Request Early Access
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-foreground">
            Pricing that reflects results, not seats.
          </h1>
          <p className="mt-4 text-xl text-muted-foreground max-w-2xl mx-auto">
            We don&apos;t think you should pay more because you have more logins.
            You should pay based on the clients you serve and the value Clairo delivers.
          </p>
        </div>

        <div className="bg-card rounded-2xl border border-border p-10 mb-12">
          <div className="grid sm:grid-cols-3 gap-8 mb-10">
            <div>
              <p className="text-sm font-semibold text-primary uppercase tracking-wider mb-3">What you get</p>
              <ul className="space-y-2.5 text-sm text-muted-foreground">
                <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Full platform access</li>
                <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> BAS + Tax Planning modules</li>
                <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Deep Xero integration</li>
                <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> ATO knowledge base</li>
                <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Client portal</li>
                <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> New modules as they ship</li>
              </ul>
            </div>
            <div>
              <p className="text-sm font-semibold text-primary uppercase tracking-wider mb-3">How we price</p>
              <ul className="space-y-2.5 text-sm text-muted-foreground">
                <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Based on clients managed</li>
                <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Not per seat or per login</li>
                <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> No lock-in contracts</li>
                <li className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-primary" /> Free onboarding support</li>
              </ul>
            </div>
            <div>
              <p className="text-sm font-semibold text-primary uppercase tracking-wider mb-3">Early access</p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                We&apos;re working with a small group of practices during EOFY 2026 to shape the product and the pricing.
                Early partners get founder-friendly terms and direct input into the roadmap.
              </p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-4 pt-8 border-t border-border">
            <Link
              href="/sign-up"
              className="group inline-flex items-center justify-center gap-3 px-8 py-4 bg-foreground hover:bg-foreground/90 text-background font-semibold rounded-full transition-all shadow-lg hover:shadow-xl"
            >
              Request Early Access
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
            <p className="text-sm text-muted-foreground">No credit card required. We&apos;ll reach out to discuss fit.</p>
          </div>
        </div>

        <div className="space-y-6">
          <h2 className="text-2xl font-bold text-foreground text-center">
            Questions
          </h2>
          <div className="max-w-3xl mx-auto space-y-6">
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="font-semibold text-foreground">What counts as a client?</h3>
              <p className="mt-2 text-muted-foreground">
                A client is a connected Xero organisation. You can run multiple BAS periods
                and tax plans per client without affecting your count.
              </p>
            </div>
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="font-semibold text-foreground">Why not per-seat pricing?</h3>
              <p className="mt-2 text-muted-foreground">
                A solo practitioner with 80 clients gets the same value from Clairo as a 5-person firm
                with 80 clients. We think pricing should reflect the value delivered, not how many
                people log in.
              </p>
            </div>
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="font-semibold text-foreground">What&apos;s included in early access?</h3>
              <p className="mt-2 text-muted-foreground">
                Full platform access, direct line to the founders, and input into the features
                and pricing we build. Early partners help shape the product and get the best terms.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
