'use client';

import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState, Suspense } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { portalApi, portalTokenStorage, PortalApiError } from '@/lib/api/portal';

type VerificationState = 'verifying' | 'success' | 'error' | 'expired' | 'invalid';

/**
 * Magic Link Verification Page
 *
 * Handles the magic link token from email and authenticates the user.
 * URL format: /portal/verify?token=<magic_link_token>
 */
function VerifyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const redirectTo = searchParams.get('redirect');

  const [state, setState] = useState<VerificationState>('verifying');
  const [error, setError] = useState<string | null>(null);
  const [businessName, setBusinessName] = useState<string | null>(null);

  useEffect(() => {
    const verifyToken = async () => {
      if (!token) {
        setState('invalid');
        setError('No verification token provided. Please check your email link.');
        return;
      }

      try {
        const response = await portalApi.auth.verifyMagicLink(token);

        // Store tokens
        portalTokenStorage.setTokens(
          response.access_token,
          response.refresh_token,
          response.business_name
        );

        setBusinessName(response.business_name);
        setState('success');

        // Redirect after a brief delay — to classification page if redirect param exists, otherwise dashboard
        const destination = redirectTo && redirectTo.startsWith('/portal/') ? redirectTo : '/portal/dashboard';
        setTimeout(() => {
          router.push(destination);
        }, 2000);
      } catch (err) {
        if (err instanceof PortalApiError) {
          if (err.status === 400 || err.code === 'INVALID_TOKEN') {
            setState('invalid');
            setError('This link is invalid. Please request a new magic link.');
          } else if (err.status === 410 || err.code === 'TOKEN_EXPIRED') {
            setState('expired');
            setError('This link has expired. Please request a new magic link.');
          } else if (err.status === 404) {
            setState('invalid');
            setError('This link is no longer valid. Please request a new magic link.');
          } else {
            setState('error');
            setError(err.message || 'Verification failed. Please try again.');
          }
        } else {
          setState('error');
          setError('An unexpected error occurred. Please try again.');
        }
      }
    };

    verifyToken();
  }, [token, router]);

  // Verifying state
  if (state === 'verifying') {
    return (
      <Card className="shadow-xl border-0">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4">
            <Loader2 className="w-6 h-6 text-primary animate-spin" />
          </div>
          <CardTitle className="text-xl">Verifying your link</CardTitle>
          <CardDescription className="mt-2">
            Please wait while we sign you in...
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex justify-center py-4">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Success state
  if (state === 'success') {
    return (
      <Card className="shadow-xl border-0">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto w-12 h-12 bg-status-success/10 rounded-full flex items-center justify-center mb-4">
            <CheckCircle2 className="w-6 h-6 text-status-success" />
          </div>
          <CardTitle className="text-xl">Welcome back!</CardTitle>
          {businessName && (
            <CardDescription className="mt-2 text-base">
              Signed in as <strong className="text-foreground">{businessName}</strong>
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          <Alert className="bg-status-success/10 border-status-success/20">
            <CheckCircle2 className="h-4 w-4 text-status-success" />
            <AlertTitle className="text-status-success">Success</AlertTitle>
            <AlertDescription className="text-status-success">
              You&apos;re being redirected to your portal...
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  // Error states (invalid, expired, error)
  return (
    <Card className="shadow-xl border-0">
      <CardHeader className="text-center pb-2">
        <div className="mx-auto w-12 h-12 bg-status-danger/10 rounded-full flex items-center justify-center mb-4">
          <XCircle className="w-6 h-6 text-status-danger" />
        </div>
        <CardTitle className="text-xl">
          {state === 'expired' ? 'Link expired' : 'Verification failed'}
        </CardTitle>
        <CardDescription className="mt-2">
          {error}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button
          className="w-full"
          onClick={() => router.push('/portal/login')}
        >
          Request a new magic link
        </Button>

        {state === 'expired' && (
          <p className="text-xs text-center text-muted-foreground">
            Magic links expire after 15 minutes for security reasons.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Wrapper with Suspense for useSearchParams
 */
export default function PortalVerifyPage() {
  return (
    <Suspense
      fallback={
        <Card className="shadow-xl border-0">
          <CardHeader className="text-center pb-2">
            <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4">
              <Loader2 className="w-6 h-6 text-primary animate-spin" />
            </div>
            <CardTitle className="text-xl">Loading...</CardTitle>
          </CardHeader>
        </Card>
      }
    >
      <VerifyContent />
    </Suspense>
  );
}
