/**
 * Biometric Setup Component
 *
 * Allows users to register and manage biometric credentials (Face ID, Touch ID).
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import {
  Fingerprint,
  Smartphone,
  Shield,
  Trash2,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Plus,
} from 'lucide-react';
import { useState } from 'react';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { useBiometricAuth } from '@/hooks/useBiometricAuth';
import { cn } from '@/lib/utils';

interface BiometricSetupProps {
  /** Compact mode - just show enable button */
  compact?: boolean;
  /** Custom class name */
  className?: string;
}

export function BiometricSetup({ compact = false, className }: BiometricSetupProps) {
  const {
    status,
    isLoading,
    credentials,
    error,
    register,
    deleteCredential,
  } = useBiometricAuth();
  const [isRegistering, setIsRegistering] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Handle registration
  const handleRegister = async () => {
    setIsRegistering(true);
    try {
      // Detect device type for naming
      const userAgent = navigator.userAgent.toLowerCase();
      let deviceName = 'Biometric';
      if (userAgent.includes('iphone') || userAgent.includes('ipad')) {
        deviceName = 'Face ID / Touch ID';
      } else if (userAgent.includes('android')) {
        deviceName = 'Fingerprint';
      } else if (userAgent.includes('mac')) {
        deviceName = 'Touch ID';
      } else if (userAgent.includes('windows')) {
        deviceName = 'Windows Hello';
      }

      await register(deviceName);
    } catch (err) {
      // Error is handled by the hook
      console.error('[BiometricSetup] Registration failed:', err);
    } finally {
      setIsRegistering(false);
    }
  };

  // Handle deletion
  const handleDelete = async (credentialId: string) => {
    setDeletingId(credentialId);
    try {
      await deleteCredential(credentialId);
    } catch (err) {
      console.error('[BiometricSetup] Delete failed:', err);
    } finally {
      setDeletingId(null);
    }
  };

  // Format date
  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // Loading state
  if (isLoading) {
    return (
      <div className={cn('flex items-center justify-center p-4', className)}>
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Not supported
  if (!status.isSupported) {
    if (compact) {
      return null;
    }

    return (
      <Card className={cn('border-muted', className)}>
        <CardContent className="flex items-center gap-3 py-4">
          <div className="p-2 rounded-full bg-muted">
            <Fingerprint className="h-5 w-5 text-muted-foreground" />
          </div>
          <div>
            <p className="font-medium text-muted-foreground">
              Biometric login not available
            </p>
            <p className="text-sm text-muted-foreground">
              Your device doesn&apos;t support biometric authentication
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Compact mode - just show a setup button
  if (compact) {
    if (status.hasCredentials) {
      return (
        <Badge variant="secondary" className={cn('gap-1', className)}>
          <Shield className="h-3 w-3" />
          Biometric enabled
        </Badge>
      );
    }

    return (
      <Button
        variant="outline"
        size="sm"
        onClick={handleRegister}
        disabled={isRegistering}
        className={className}
      >
        {isRegistering ? (
          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
        ) : (
          <Fingerprint className="h-4 w-4 mr-2" />
        )}
        Enable biometric login
      </Button>
    );
  }

  // Full card
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Fingerprint className="h-5 w-5" />
          Biometric Login
        </CardTitle>
        <CardDescription>
          Use Face ID, Touch ID, or fingerprint for quick access
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Error message */}
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <p className="text-sm">{error}</p>
          </div>
        )}

        {/* No credentials - show setup prompt */}
        {!status.hasCredentials && (
          <div className="text-center py-6 space-y-4">
            <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
              <Fingerprint className="h-8 w-8 text-primary" />
            </div>
            <div>
              <p className="font-medium">Quick & Secure Access</p>
              <p className="text-sm text-muted-foreground mt-1">
                Sign in instantly using your device&apos;s biometric authentication
              </p>
            </div>
            <Button
              onClick={handleRegister}
              disabled={isRegistering}
              className="w-full"
            >
              {isRegistering ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Setting up...
                </>
              ) : (
                <>
                  <Shield className="h-4 w-4 mr-2" />
                  Enable Biometric Login
                </>
              )}
            </Button>
          </div>
        )}

        {/* Credentials list */}
        {status.hasCredentials && (
          <div className="space-y-3">
            {credentials.map((credential) => (
              <div
                key={credential.id}
                className="flex items-center justify-between p-3 rounded-lg border bg-muted/30"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-full bg-status-success/10">
                    <CheckCircle2 className="h-4 w-4 text-status-success" />
                  </div>
                  <div>
                    <p className="font-medium text-sm">
                      {credential.device_name || 'Biometric credential'}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Added {formatDate(credential.created_at)}
                      {credential.last_used_at && (
                        <> · Last used {formatDate(credential.last_used_at)}</>
                      )}
                    </p>
                  </div>
                </div>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      disabled={deletingId === credential.id}
                    >
                      {deletingId === credential.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Remove biometric access?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will remove the biometric credential from this device.
                        You can set it up again later if needed.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => handleDelete(credential.id)}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        Remove
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            ))}

            {/* Add another device button */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleRegister}
              disabled={isRegistering}
              className="w-full"
            >
              {isRegistering ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Plus className="h-4 w-4 mr-2" />
              )}
              Add another device
            </Button>
          </div>
        )}

        {/* Security note */}
        <div className="flex items-start gap-2 p-3 rounded-lg bg-muted/50 text-sm text-muted-foreground">
          <Smartphone className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <p>
            Your biometric data never leaves your device. We only store a secure
            key that verifies your identity.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Biometric prompt for quick re-authentication.
 */
interface BiometricPromptProps {
  /** Called when authentication succeeds */
  onSuccess: () => void;
  /** Called when user dismisses or fails */
  onCancel: () => void;
  /** Custom class name */
  className?: string;
}

export function BiometricPrompt({
  onSuccess,
  onCancel,
  className,
}: BiometricPromptProps) {
  const { status, authenticate, error } = useBiometricAuth();
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const handleAuthenticate = async () => {
    setIsAuthenticating(true);
    try {
      const success = await authenticate();
      if (success) {
        onSuccess();
      }
    } catch {
      // Error handled by hook
    } finally {
      setIsAuthenticating(false);
    }
  };

  if (!status.isSupported || !status.hasCredentials) {
    return null;
  }

  return (
    <div className={cn('text-center space-y-4', className)}>
      <button
        onClick={handleAuthenticate}
        disabled={isAuthenticating}
        className="mx-auto p-6 rounded-full bg-primary/10 hover:bg-primary/20 transition-colors disabled:opacity-50"
      >
        {isAuthenticating ? (
          <Loader2 className="h-12 w-12 text-primary animate-spin" />
        ) : (
          <Fingerprint className="h-12 w-12 text-primary" />
        )}
      </button>

      <div>
        <p className="font-medium">
          {isAuthenticating ? 'Authenticating...' : 'Tap to use biometric'}
        </p>
        {error && (
          <p className="text-sm text-destructive mt-1">{error}</p>
        )}
      </div>

      <Button variant="ghost" onClick={onCancel} disabled={isAuthenticating}>
        Use another method
      </Button>
    </div>
  );
}
