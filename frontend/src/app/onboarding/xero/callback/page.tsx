'use client';

import { useAuth } from '@clerk/nextjs';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function XeroCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { getToken } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const processedRef = useRef(false);

  useEffect(() => {
    // Prevent double execution in React Strict Mode
    if (processedRef.current) {
      return;
    }
    processedRef.current = true;

    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setError('Xero connection was cancelled or failed. Please try again.');
      return;
    }

    if (!code || !state) {
      setError('Invalid callback parameters. Please try connecting again.');
      return;
    }

    // Handle the OAuth callback
    const handleCallback = async () => {
      try {
        const token = await getToken();

        // Call backend to complete OAuth
        const response = await fetch(
          `${API_BASE}/api/v1/onboarding/xero/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
          {
            headers: {
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Failed to complete Xero connection');
        }

        // Success - redirect to import clients
        router.push('/onboarding/import-clients');
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to complete Xero connection. Please try again.'
        );
      }
    };

    handleCallback();
  }, [searchParams, router, getToken]);

  if (error) {
    return (
      <div className="max-w-md mx-auto text-center space-y-6 py-12">
        <div className="mx-auto w-16 h-16 bg-status-danger/10 rounded-full flex items-center justify-center">
          <svg
            className="w-8 h-8 text-status-danger"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-foreground">
          Connection Failed
        </h2>
        <p className="text-muted-foreground">{error}</p>
        <button
          onClick={() => router.push('/onboarding/connect-xero')}
          className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto text-center space-y-6 py-12">
      <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center">
        <svg
          className="w-8 h-8 text-primary animate-spin"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      </div>
      <h2 className="text-xl font-semibold text-foreground">
        Connecting to Xero...
      </h2>
      <p className="text-muted-foreground">
        Please wait while we complete the connection.
      </p>
    </div>
  );
}

export default function XeroCallbackPage() {
  return (
    <Suspense fallback={<div className="max-w-md mx-auto text-center py-12">Loading...</div>}>
      <XeroCallbackContent />
    </Suspense>
  );
}
