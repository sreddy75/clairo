/**
 * Notification Permission Component
 *
 * Prompts users to enable push notifications.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { Bell, BellOff, X, Check, Loader2 } from 'lucide-react';
import { useState, useEffect } from 'react';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { usePushNotifications } from '@/hooks/usePushNotifications';
import { cn } from '@/lib/utils';

interface NotificationPermissionProps {
  /** When to show the prompt */
  trigger?: 'immediate' | 'after-first-request' | 'manual';
  /** Custom class name */
  className?: string;
  /** Callback when permission is granted */
  onGranted?: () => void;
  /** Callback when permission is denied */
  onDenied?: () => void;
  /** Callback when prompt is dismissed */
  onDismiss?: () => void;
}

const DISMISSED_KEY = 'pwa-notification-prompt-dismissed';

export function NotificationPermission({
  trigger = 'after-first-request',
  className,
  onGranted,
  onDenied,
  onDismiss,
}: NotificationPermissionProps) {
  const {
    isSupported,
    permission,
    isSubscribed,
    isLoading,
    error,
    subscribe,
  } = usePushNotifications();

  const [show, setShow] = useState(false);

  // Check if we should show based on trigger type
  useEffect(() => {
    // Check if previously dismissed
    const dismissed = localStorage.getItem(DISMISSED_KEY);
    if (dismissed) {
      return;
    }

    // Don't show if already subscribed or not supported
    if (!isSupported || isSubscribed || permission === 'denied') {
      return;
    }

    if (trigger === 'immediate') {
      setShow(true);
    } else if (trigger === 'after-first-request') {
      // Check if user has viewed at least one request
      const hasViewedRequest = localStorage.getItem('pwa-has-viewed-request');
      if (hasViewedRequest) {
        setShow(true);
      }
    }
    // For 'manual', parent component controls visibility
  }, [trigger, isSupported, isSubscribed, permission]);

  const handleEnable = async () => {
    const success = await subscribe();
    if (success) {
      setShow(false);
      onGranted?.();
    } else if (permission === 'denied') {
      onDenied?.();
    }
  };

  const handleDismiss = () => {
    setShow(false);
    localStorage.setItem(DISMISSED_KEY, 'true');
    onDismiss?.();
  };

  // Don't render if not showing
  if (!show) {
    return null;
  }

  return (
    <div
      className={cn(
        'fixed bottom-4 left-4 right-4 z-50 md:left-auto md:right-4 md:max-w-sm',
        'animate-in slide-in-from-bottom-4',
        className
      )}
    >
      <Card className="border-primary/20 shadow-lg">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <div className="rounded-lg bg-primary/10 p-2">
                <Bell className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle className="text-base">Stay Updated</CardTitle>
                <CardDescription className="text-xs">
                  Get notified about new document requests
                </CardDescription>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 -mr-2 -mt-2"
              onClick={handleDismiss}
            >
              <X className="h-4 w-4" />
              <span className="sr-only">Dismiss</span>
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {error && (
            <p className="text-sm text-destructive mb-3">{error}</p>
          )}
          <div className="flex gap-2">
            <Button
              onClick={handleEnable}
              disabled={isLoading}
              className="flex-1"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Enabling...
                </>
              ) : (
                <>
                  <Check className="mr-2 h-4 w-4" />
                  Enable
                </>
              )}
            </Button>
            <Button
              variant="outline"
              onClick={handleDismiss}
              disabled={isLoading}
            >
              Not now
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            You can change this anytime in settings
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

/**
 * Settings component for managing notification preferences.
 */
export function NotificationSettings({ className }: { className?: string }) {
  const {
    isSupported,
    permission,
    isSubscribed,
    isLoading,
    error,
    subscribe,
    unsubscribe,
  } = usePushNotifications();

  if (!isSupported) {
    return (
      <div className={cn('flex items-center gap-3 text-muted-foreground', className)}>
        <BellOff className="h-5 w-5" />
        <div>
          <p className="font-medium">Notifications not supported</p>
          <p className="text-sm">
            Your browser doesn&apos;t support push notifications
          </p>
        </div>
      </div>
    );
  }

  if (permission === 'denied') {
    return (
      <div className={cn('flex items-center gap-3 text-destructive', className)}>
        <BellOff className="h-5 w-5" />
        <div>
          <p className="font-medium">Notifications blocked</p>
          <p className="text-sm text-muted-foreground">
            Enable notifications in your browser settings
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex items-center justify-between', className)}>
      <div className="flex items-center gap-3">
        {isSubscribed ? (
          <Bell className="h-5 w-5 text-primary" />
        ) : (
          <BellOff className="h-5 w-5 text-muted-foreground" />
        )}
        <div>
          <p className="font-medium">Push notifications</p>
          <p className="text-sm text-muted-foreground">
            {isSubscribed
              ? 'Get notified about new requests'
              : 'Stay updated on document requests'}
          </p>
        </div>
      </div>
      <Button
        variant={isSubscribed ? 'outline' : 'default'}
        size="sm"
        onClick={isSubscribed ? unsubscribe : subscribe}
        disabled={isLoading}
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : isSubscribed ? (
          'Disable'
        ) : (
          'Enable'
        )}
      </Button>
      {error && (
        <p className="text-xs text-destructive mt-1">{error}</p>
      )}
    </div>
  );
}
