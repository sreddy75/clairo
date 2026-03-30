/**
 * PWA Install Prompt Component
 *
 * Shows a prompt to install the PWA after the user has visited twice.
 * Uses the beforeinstallprompt event to trigger native install dialog.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { X, Download, Smartphone } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

interface InstallPromptProps {
  /** Minimum visits before showing prompt */
  minVisits?: number;
  /** Callback when user dismisses the prompt */
  onDismiss?: () => void;
  /** Callback when app is installed */
  onInstall?: () => void;
}

const STORAGE_KEY = 'pwa-install-prompt';
const VISIT_COUNT_KEY = 'pwa-visit-count';

export function InstallPrompt({
  minVisits = 2,
  onDismiss,
  onInstall,
}: InstallPromptProps) {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [isStandalone, setIsStandalone] = useState(false);

  useEffect(() => {
    // Check if already installed or dismissed
    const dismissed = localStorage.getItem(STORAGE_KEY) === 'dismissed';
    const isStandaloneMode =
      window.matchMedia('(display-mode: standalone)').matches ||
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Safari-specific standalone property
      (window.navigator as any).standalone === true;

    setIsStandalone(isStandaloneMode);

    if (dismissed || isStandaloneMode) {
      return;
    }

    // Track visit count
    const visitCount = parseInt(
      localStorage.getItem(VISIT_COUNT_KEY) || '0',
      10
    );
    const newCount = visitCount + 1;
    localStorage.setItem(VISIT_COUNT_KEY, String(newCount));

    // Detect iOS
    const iOS =
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- IE-specific MSStream property
      /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as any).MSStream;
    setIsIOS(iOS);

    // For iOS, show manual instructions after min visits
    if (iOS && newCount >= minVisits) {
      setShowPrompt(true);
      return;
    }

    // Listen for beforeinstallprompt event
    const handleBeforeInstall = (e: Event) => {
      e.preventDefault();
      const prompt = e as BeforeInstallPromptEvent;
      setDeferredPrompt(prompt);

      // Show prompt after min visits
      if (newCount >= minVisits) {
        setShowPrompt(true);
      }
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);

    // Listen for app installed event
    const handleAppInstalled = () => {
      setDeferredPrompt(null);
      setShowPrompt(false);
      localStorage.setItem(STORAGE_KEY, 'installed');
      onInstall?.();
    };

    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, [minVisits, onInstall]);

  const handleInstall = useCallback(async () => {
    if (!deferredPrompt) return;

    try {
      await deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;

      if (outcome === 'accepted') {
        localStorage.setItem(STORAGE_KEY, 'installed');
        onInstall?.();
      }
    } catch (error) {
      console.error('[PWA] Install prompt failed:', error);
    }

    setDeferredPrompt(null);
    setShowPrompt(false);
  }, [deferredPrompt, onInstall]);

  const handleDismiss = useCallback(() => {
    setShowPrompt(false);
    localStorage.setItem(STORAGE_KEY, 'dismissed');
    onDismiss?.();
  }, [onDismiss]);

  // Don't render if already installed or shouldn't show
  if (isStandalone || !showPrompt) {
    return null;
  }

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 md:left-auto md:right-4 md:max-w-sm animate-in slide-in-from-bottom-4">
      <Card className="border-primary/20 shadow-lg">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <div className="rounded-lg bg-primary/10 p-2">
                <Smartphone className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle className="text-base">Install Clairo</CardTitle>
                <CardDescription className="text-xs">
                  Quick access from your home screen
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
          {isIOS ? (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                Tap the share button{' '}
                <span className="inline-block align-middle">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="inline"
                  >
                    <path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8" />
                    <polyline points="16 6 12 2 8 6" />
                    <line x1="12" y1="2" x2="12" y2="15" />
                  </svg>
                </span>{' '}
                then &quot;Add to Home Screen&quot;
              </p>
            </div>
          ) : (
            <Button
              onClick={handleInstall}
              className="w-full"
              disabled={!deferredPrompt}
            >
              <Download className="mr-2 h-4 w-4" />
              Install App
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
