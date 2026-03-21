'use client';

import { useAuth } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { useEffect, useRef } from 'react';

import { getProgress, setAuthToken, type OnboardingStatus } from '@/lib/api/onboarding';
import { apiClient } from '@/lib/api-client';

/**
 * Maps onboarding status to the correct route.
 */
function getRouteForStatus(status: OnboardingStatus): string {
  switch (status) {
    case 'started':
      return '/onboarding/tier-selection';
    case 'tier_selected':
    case 'payment_setup':
      return '/onboarding/connect-xero';
    case 'xero_connected':
    case 'skipped_xero':
      return '/onboarding/import-clients';
    case 'clients_imported':
    case 'tour_completed':
    case 'completed':
      return '/dashboard';
    default:
      return '/onboarding/tier-selection';
  }
}

/**
 * Onboarding entry point - redirects to the appropriate step
 * based on the user's current onboarding progress.
 *
 * For brand new users (no backend account yet), redirects to
 * /onboarding/create-account to collect organization name.
 */
export default function OnboardingPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const hasRedirected = useRef(false);

  useEffect(() => {
    async function redirectToCurrentStep() {
      if (hasRedirected.current) return;

      try {
        const token = await getToken();
        if (!token) {
          hasRedirected.current = true;
          router.replace('/sign-up');
          return;
        }

        // Check if user has a backend account
        const meResponse = await apiClient.get('/api/v1/auth/me', {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!meResponse.ok) {
          // No backend account — send to account creation
          hasRedirected.current = true;
          router.replace('/onboarding/create-account');
          return;
        }

        // User has an account — check onboarding progress
        setAuthToken(token);
        const progress = await getProgress();
        hasRedirected.current = true;
        router.replace(getRouteForStatus(progress.status));
      } catch {
        // Error fetching progress — could be new account with no progress yet
        // Send to tier selection (onboarding start)
        hasRedirected.current = true;
        router.replace('/onboarding/tier-selection');
      }
    }

    redirectToCurrentStep();
  }, [router, getToken]);

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-muted-foreground">Loading your onboarding progress...</p>
      </div>
    </div>
  );
}
