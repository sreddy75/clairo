'use client';

import { Mail, ArrowRight, CheckCircle2, AlertCircle, Fingerprint } from 'lucide-react';
import { useState, useEffect } from 'react';

import { BiometricPrompt } from '@/components/pwa/BiometricSetup';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { isPlatformAuthenticatorAvailable } from '@/hooks/useBiometricAuth';
import { portalApi, PortalApiError, portalTokenStorage } from '@/lib/api/portal';

/**
 * Portal Login Page
 *
 * Allows business owners to request a magic link to access their client portal.
 * The magic link is sent to their registered email address.
 */
export default function PortalLoginPage() {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [expiresInMinutes, setExpiresInMinutes] = useState(15);
  const [showBiometric, setShowBiometric] = useState(false);
  const [hasBiometric, setHasBiometric] = useState(false);

  // Check for biometric availability on mount
  useEffect(() => {
    let mounted = true;

    const checkBiometric = async () => {
      // Only show biometric if user has an existing session token
      const hasToken = portalTokenStorage.isAuthenticated();
      if (!hasToken) {
        return;
      }

      // Check if platform authenticator is available
      const available = await isPlatformAuthenticatorAvailable();
      if (!available || !mounted) {
        return;
      }

      // Check if user has registered credentials
      try {
        const status = await portalApi.push.getBiometricStatus();
        if (mounted && status.has_credentials) {
          setHasBiometric(true);
          setShowBiometric(true);
        }
      } catch {
        // Silently fail - biometric is optional
      }
    };

    checkBiometric();

    return () => {
      mounted = false;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const response = await portalApi.auth.requestMagicLink(email);
      setExpiresInMinutes(response.expires_in_minutes);
      setSuccess(true);
    } catch (err) {
      if (err instanceof PortalApiError) {
        // Don't reveal if email exists or not for security
        if (err.status === 404) {
          // Still show success to prevent email enumeration
          setSuccess(true);
        } else {
          setError(err.message || 'Failed to send magic link. Please try again.');
        }
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <Card className="shadow-xl border-0">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto w-12 h-12 bg-status-success/10 rounded-full flex items-center justify-center mb-4">
            <CheckCircle2 className="w-6 h-6 text-status-success" />
          </div>
          <CardTitle className="text-xl">Check your email</CardTitle>
          <CardDescription className="mt-2">
            We&apos;ve sent a magic link to <strong className="text-foreground">{email}</strong>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="bg-muted/50 rounded-lg p-4 text-sm text-muted-foreground">
            <p className="mb-2">Click the link in the email to sign in to your portal.</p>
            <p>The link will expire in {expiresInMinutes} minutes.</p>
          </div>

          <div className="text-center text-sm text-muted-foreground">
            <p>Didn&apos;t receive the email?</p>
            <Button
              variant="link"
              className="p-0 h-auto"
              onClick={() => {
                setSuccess(false);
                setEmail('');
              }}
            >
              Try again with a different email
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Biometric authentication view
  if (showBiometric && hasBiometric) {
    return (
      <Card className="shadow-xl border-0">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4">
            <Fingerprint className="w-6 h-6 text-primary" />
          </div>
          <CardTitle className="text-xl">Welcome back</CardTitle>
          <CardDescription className="mt-2">
            Use biometric authentication to sign in quickly
          </CardDescription>
        </CardHeader>
        <CardContent>
          <BiometricPrompt
            onSuccess={() => {
              // Redirect to dashboard on successful biometric auth
              window.location.href = '/portal/dashboard';
            }}
            onCancel={() => setShowBiometric(false)}
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="shadow-xl border-0">
      <CardHeader className="text-center pb-2">
        <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4">
          <Mail className="w-6 h-6 text-primary" />
        </div>
        <CardTitle className="text-xl">Sign in to your portal</CardTitle>
        <CardDescription className="mt-2">
          Enter your email address and we&apos;ll send you a magic link to sign in.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-2">
            <Input
              type="email"
              placeholder="your@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={isLoading}
              className="h-11"
              autoComplete="email"
              autoFocus
            />
          </div>

          <Button
            type="submit"
            className="w-full h-11"
            disabled={isLoading || !email}
          >
            {isLoading ? (
              <>
                <span className="animate-spin mr-2">&#9696;</span>
                Sending link...
              </>
            ) : (
              <>
                Send magic link
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </Button>

          {/* Biometric option */}
          {hasBiometric && !showBiometric && (
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-card px-2 text-muted-foreground">
                  or
                </span>
              </div>
            </div>
          )}

          {hasBiometric && !showBiometric && (
            <Button
              type="button"
              variant="outline"
              className="w-full h-11"
              onClick={() => setShowBiometric(true)}
            >
              <Fingerprint className="w-4 h-4 mr-2" />
              Use biometric
            </Button>
          )}

          <p className="text-xs text-center text-muted-foreground">
            By signing in, you agree to our Terms of Service and Privacy Policy.
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
