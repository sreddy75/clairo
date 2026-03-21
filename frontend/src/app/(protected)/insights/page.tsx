'use client';

/**
 * Insights Page - Redirects to AI Assistant
 *
 * The insights functionality has been consolidated into the
 * AI Knowledge Assistant for a unified experience.
 */

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function InsightsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/assistant');
  }, [router]);

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="text-muted-foreground text-sm">Redirecting to AI Assistant...</div>
    </div>
  );
}
