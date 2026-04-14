'use client';

import { useAuth } from '@clerk/nextjs';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState, Suspense, useRef } from 'react';
import { toast } from 'sonner';

import { apiClient } from '@/lib/api-client';

type CallbackStatus = 'processing' | 'success' | 'error';

interface XeroCallbackResponse {
  connection_id: string;
  organization_name: string;
  status: string;
  message: string;
}

function XeroCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { getToken } = useAuth();
  const [status, setStatus] = useState<CallbackStatus>('processing');
  const [error, setError] = useState<string | null>(null);
  const [organizationName, setOrganizationName] = useState<string | null>(null);
  const processedRef = useRef(false);

  useEffect(() => {
    async function handleCallback() {
      // Prevent double execution in React Strict Mode
      if (processedRef.current) {
        return;
      }
      processedRef.current = true;
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const errorParam = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');

      // Handle OAuth errors from Xero
      if (errorParam) {
        setStatus('error');
        setError(errorDescription || 'Authorization was denied');
        return;
      }

      // Validate required parameters
      if (!code || !state) {
        setStatus('error');
        setError('Missing authorization code or state');
        return;
      }

      // Optional: Client-side state validation
      const storedState = sessionStorage.getItem('xero_oauth_state');
      if (storedState && storedState !== state) {
        setStatus('error');
        setError('State mismatch - possible CSRF attack');
        return;
      }

      // Clear stored state
      sessionStorage.removeItem('xero_oauth_state');

      try {
        const token = await getToken();
        if (!token) {
          throw new Error('Authentication required');
        }

        // Complete the OAuth callback
        const response = await apiClient.get(
          `/api/v1/integrations/xero/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData?.error?.message || errorData?.detail || 'Failed to complete Xero connection');
        }

        const data: XeroCallbackResponse = await response.json();
        setOrganizationName(data.organization_name);
        setStatus('success');
        toast.success(`Connected to ${data.organization_name}`);

        // Check if we should return to a specific page (e.g., Tax Plan after re-auth)
        const returnTo = sessionStorage.getItem('xero_reauth_return_to');
        sessionStorage.removeItem('xero_reauth_return_to');

        setTimeout(() => {
          if (returnTo) {
            router.push(returnTo);
          } else {
            router.push('/settings/integrations');
          }
        }, 2000);
      } catch (err) {
        setStatus('error');
        setError(err instanceof Error ? err.message : 'Failed to complete Xero connection');
      }
    }

    handleCallback();
  }, [searchParams, getToken, router]);

  if (status === 'processing') {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-foreground mb-2">
            Connecting to Xero...
          </h1>
          <p className="text-muted-foreground">
            Please wait while we complete the connection.
          </p>
        </div>
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 bg-status-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-8 h-8 text-status-success" />
          </div>
          <h1 className="text-xl font-semibold text-foreground mb-2">
            Successfully Connected!
          </h1>
          <p className="text-muted-foreground mb-4">
            Your Xero organization <strong>{organizationName}</strong> is now connected.
          </p>
          <p className="text-sm text-muted-foreground">
            Redirecting...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 bg-status-danger/10 rounded-full flex items-center justify-center mx-auto mb-4">
          <XCircle className="w-8 h-8 text-status-danger" />
        </div>
        <h1 className="text-xl font-semibold text-foreground mb-2">
          Connection Failed
        </h1>
        <p className="text-muted-foreground mb-6">{error}</p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => router.push('/settings/integrations')}
            className="px-4 py-2 text-foreground bg-muted hover:bg-muted/80 rounded-lg transition-colors"
          >
            Back to Integrations
          </button>
          <button
            onClick={() => router.push('/settings/integrations')}
            className="px-4 py-2 text-primary-foreground bg-primary hover:bg-primary/90 rounded-lg transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Xero OAuth Callback Page
 *
 * Handles the OAuth callback from Xero after user authorization.
 * Extracts code/state from URL params and sends to backend.
 */
export default function XeroCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[60vh] flex items-center justify-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary" />
        </div>
      }
    >
      <XeroCallbackContent />
    </Suspense>
  );
}
