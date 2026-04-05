'use client';

import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { useCookieConsent } from '@/hooks/useCookieConsent';

export function CookieConsentBanner() {
  const { consent, loaded, accept, decline } = useCookieConsent();

  // Don't render until we've checked localStorage, or if already decided
  if (!loaded || consent !== null) return null;

  return (
    <div className="fixed bottom-0 inset-x-0 z-50 p-4">
      <div className="mx-auto max-w-2xl rounded-lg border bg-card p-4 shadow-lg">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
            We use cookies to improve your experience and analyse site usage.{' '}
            <Link href="/privacy" className="underline hover:text-foreground">
              Learn more
            </Link>
          </p>
          <div className="flex gap-2 shrink-0">
            <Button variant="outline" size="sm" onClick={decline}>
              Decline
            </Button>
            <Button size="sm" onClick={accept}>
              Accept
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
