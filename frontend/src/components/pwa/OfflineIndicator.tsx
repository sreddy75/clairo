/**
 * Offline Indicator Component
 *
 * Shows a banner when the user is offline, with last sync time.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { WifiOff, RefreshCw, Clock } from 'lucide-react';
import { useEffect, useState } from 'react';

import { useNetworkStatus } from '@/hooks/useNetworkStatus';
import { cn } from '@/lib/utils';

interface OfflineIndicatorProps {
  /** Custom class name */
  className?: string;
  /** Show as a toast instead of banner */
  variant?: 'banner' | 'toast';
}

const LAST_SYNC_KEY = 'pwa-last-sync';

export function OfflineIndicator({
  className,
  variant = 'banner',
}: OfflineIndicatorProps) {
  const { isOnline, isSlow, effectiveType } = useNetworkStatus();
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [show, setShow] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Mount guard to prevent hydration issues
  useEffect(() => {
    setMounted(true);
  }, []);

  // Load last sync time (only after mounted)
  useEffect(() => {
    if (!mounted) return;
    const stored = localStorage.getItem(LAST_SYNC_KEY);
    if (stored) {
      setLastSync(new Date(stored));
    }
  }, [mounted]);

  // Update last sync when coming back online
  useEffect(() => {
    if (!mounted) return;
    if (isOnline && !show) {
      const now = new Date();
      localStorage.setItem(LAST_SYNC_KEY, now.toISOString());
      setLastSync(now);
    }
  }, [isOnline, show, mounted]);

  // Show/hide animation
  useEffect(() => {
    if (!mounted) return;
    if (!isOnline) {
      setShow(true);
      return;
    }
    // Delay hiding to show "Back online" message
    const timer = setTimeout(() => setShow(false), 2000);
    return () => clearTimeout(timer);
  }, [isOnline, mounted]);

  // Don't render until mounted to prevent hydration mismatch
  if (!mounted) {
    return null;
  }

  // Format relative time
  const formatLastSync = (date: Date): string => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  if (!show && isOnline) {
    return null;
  }

  if (variant === 'toast') {
    return (
      <div
        className={cn(
          'fixed bottom-20 left-4 right-4 z-50 md:left-auto md:right-4 md:max-w-sm',
          'animate-in slide-in-from-bottom-4',
          className
        )}
      >
        <div
          className={cn(
            'rounded-lg px-4 py-3 shadow-lg flex items-center gap-3',
            isOnline
              ? 'bg-green-500 text-white'
              : 'bg-yellow-500 text-yellow-950'
          )}
        >
          {isOnline ? (
            <>
              <RefreshCw className="h-5 w-5" />
              <span className="font-medium">Back online</span>
            </>
          ) : (
            <>
              <WifiOff className="h-5 w-5" />
              <div className="flex-1">
                <p className="font-medium">You&apos;re offline</p>
                {lastSync && (
                  <p className="text-xs opacity-80">
                    Last sync: {formatLastSync(lastSync)}
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  // Banner variant
  return (
    <div
      className={cn(
        'w-full px-4 py-2 flex items-center justify-center gap-2 text-sm',
        isOnline
          ? 'bg-green-500 text-white'
          : isSlow
            ? 'bg-orange-500 text-white'
            : 'bg-yellow-500 text-yellow-950',
        'animate-in slide-in-from-top-2',
        className
      )}
    >
      {isOnline ? (
        <>
          <RefreshCw className="h-4 w-4" />
          <span>Back online - syncing...</span>
        </>
      ) : (
        <>
          <WifiOff className="h-4 w-4" />
          <span>
            {isSlow ? 'Slow connection' : "You're offline"}
            {effectiveType && ` (${effectiveType})`}
          </span>
          {lastSync && (
            <>
              <span className="opacity-60">•</span>
              <Clock className="h-3 w-3 opacity-60" />
              <span className="opacity-60">{formatLastSync(lastSync)}</span>
            </>
          )}
        </>
      )}
    </div>
  );
}

/**
 * Hook to update last sync time.
 * Call this after successful API requests.
 */
export function updateLastSync(): void {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(LAST_SYNC_KEY, new Date().toISOString());
  }
}
