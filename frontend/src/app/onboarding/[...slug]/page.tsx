'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

/**
 * Catch-all route for invalid onboarding subpaths (e.g. /onboarding/undefined).
 * Redirects to the main onboarding entry point which handles routing
 * based on the user's actual onboarding status.
 */
export default function OnboardingCatchAll() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/onboarding');
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-muted-foreground">Redirecting...</p>
      </div>
    </div>
  );
}
