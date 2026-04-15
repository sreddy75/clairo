'use client';

/**
 * Invitation Landing Page
 *
 * Public page shown when a user clicks an invitation link.
 * Looks up the invitation, shows practice details, and directs
 * the user to sign up with the token preserved.
 */

import { Loader2, ShieldCheck, UserPlus, XCircle } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { apiClient } from '@/lib/api-client';

// ─── Types ──────────────────────────────────────────────────────────────────

interface InvitationPublic {
  email: string;
  role: string;
  status: string;
  expires_at: string;
  tenant_name: string;
}

// ─── Role Labels ────────────────────────────────────────────────────────────

const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  accountant: 'Accountant',
  staff: 'Staff',
};

// ─── Inner Component (needs useSearchParams inside Suspense) ────────────────

function InvitationContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [invitation, setInvitation] = useState<InvitationPublic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInvitation = useCallback(async () => {
    if (!token) {
      setError('No invitation token provided.');
      setLoading(false);
      return;
    }

    try {
      const response = await apiClient.get(
        `/api/v1/auth/invitations/token/${encodeURIComponent(token)}`
      );

      if (!response.ok) {
        if (response.status === 404) {
          setError('This invitation was not found or has been revoked.');
        } else if (response.status === 410) {
          setError('This invitation has expired. Please ask your practice admin to send a new one.');
        } else {
          setError('Unable to load invitation details.');
        }
        setLoading(false);
        return;
      }

      const data: InvitationPublic = await response.json();

      if (data.status === 'expired') {
        setError('This invitation has expired. Please ask your practice admin to send a new one.');
        setLoading(false);
        return;
      }

      if (data.status === 'revoked') {
        setError('This invitation has been revoked.');
        setLoading(false);
        return;
      }

      if (data.status === 'accepted') {
        setError('This invitation has already been accepted. You can sign in directly.');
        setLoading(false);
        return;
      }

      setInvitation(data);
    } catch {
      setError('Unable to load invitation details. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchInvitation();
  }, [fetchInvitation]);

  const handleAccept = () => {
    // Redirect to sign-up with the invitation token preserved
    // After Clerk sign-up, the onboarding flow will use this token
    const signUpUrl = `/sign-up#/?invitation_token=${encodeURIComponent(token!)}`;
    router.push(signUpUrl);
  };

  // ─── Loading ────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <Card className="w-full max-w-md">
        <CardContent className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  // ─── Error ──────────────────────────────────────────────────────────────

  if (error) {
    return (
      <Card className="w-full max-w-md">
        <CardHeader className="items-center pb-2">
          <XCircle className="h-12 w-12 text-red-400 mb-2" />
          <h2 className="text-lg font-semibold text-center">Invitation Unavailable</h2>
        </CardHeader>
        <CardContent className="text-center">
          <p className="text-sm text-muted-foreground">{error}</p>
        </CardContent>
        <CardFooter className="justify-center">
          <Button variant="outline" onClick={() => router.push('/sign-in')}>
            Go to Sign In
          </Button>
        </CardFooter>
      </Card>
    );
  }

  // ─── Invitation Details ─────────────────────────────────────────────────

  if (!invitation) return null;

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="items-center pb-2">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 mb-3">
          <UserPlus className="h-7 w-7 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-center">
          You&apos;re invited to join
        </h2>
        <p className="text-2xl font-bold text-center text-primary">
          {invitation.tenant_name}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg bg-muted/50 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Email</span>
            <span className="text-sm font-medium">{invitation.email}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Role</span>
            <Badge variant="secondary">
              <ShieldCheck className="mr-1 h-3 w-3" />
              {ROLE_LABELS[invitation.role] || invitation.role}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Expires</span>
            <span className="text-sm text-muted-foreground">
              {new Date(invitation.expires_at).toLocaleDateString('en-AU', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
              })}
            </span>
          </div>
        </div>
        <p className="text-xs text-muted-foreground text-center">
          Create your account to join the practice as {ROLE_LABELS[invitation.role]?.toLowerCase() || invitation.role}.
        </p>
      </CardContent>
      <CardFooter className="flex-col gap-2">
        <Button className="w-full" size="lg" onClick={handleAccept}>
          Accept & Create Account
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          onClick={() => router.push('/sign-in')}
        >
          Already have an account? Sign in
        </Button>
      </CardFooter>
    </Card>
  );
}

// ─── Page (with Suspense for useSearchParams) ───────────────────────────────

export default function InvitationPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Suspense
        fallback={
          <Card className="w-full max-w-md">
            <CardContent className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </CardContent>
          </Card>
        }
      >
        <InvitationContent />
      </Suspense>
    </div>
  );
}
