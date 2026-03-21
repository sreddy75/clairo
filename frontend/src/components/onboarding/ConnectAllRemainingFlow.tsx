'use client';

/**
 * Modal for sequential connection of all remaining unconnected client Xero orgs.
 *
 * Shows:
 * - Progress: "Connecting 3 of 47 clients..."
 * - Current client being connected
 * - Skip button for individual clients
 * - Pause/Resume flow controls
 */

import { useEffect, useState } from 'react';

import type {
  XpmClient,
  XpmClientConnectionProgress,
} from '@/lib/api/onboarding';

interface ConnectAllRemainingFlowProps {
  isOpen: boolean;
  onClose: () => void;
  progress: XpmClientConnectionProgress | null;
  currentClient: XpmClient | null;
  isActive: boolean;
  connectAllProgress: {
    current: number;
    total: number;
    skipped: string[];
  };
  onStartConnectAll: () => Promise<void>;
  onConnectNext: () => Promise<unknown>;
  onSkipClient: (clientId: string) => void;
  onPause: () => void;
  error: string | null;
}

export function ConnectAllRemainingFlow({
  isOpen,
  onClose,
  progress,
  currentClient,
  isActive,
  connectAllProgress,
  onStartConnectAll,
  onConnectNext,
  onSkipClient,
  onPause,
  error,
}: ConnectAllRemainingFlowProps) {
  const [isStarting, setIsStarting] = useState(false);
  const [showComplete, setShowComplete] = useState(false);

  // Check if all clients are connected
  useEffect(() => {
    if (progress && progress.not_connected === 0 && !isActive) {
      setShowComplete(true);
    }
  }, [progress, isActive]);

  if (!isOpen) return null;

  const handleStart = async () => {
    setIsStarting(true);
    setShowComplete(false);
    try {
      await onStartConnectAll();
    } finally {
      setIsStarting(false);
    }
  };

  const handleSkip = () => {
    if (currentClient) {
      onSkipClient(currentClient.id);
      // Continue to next client after skipping
      onConnectNext();
    }
  };

  const handleClose = () => {
    onPause();
    onClose();
  };

  const remainingCount = progress?.not_connected ?? 0;
  const connectedCount = progress?.connected ?? 0;
  const totalCount = progress?.total_clients ?? 0;
  const progressPercent = totalCount > 0 ? (connectedCount / totalCount) * 100 : 0;

  // Complete state
  if (showComplete) {
    return (
      <div className="fixed inset-0 z-50 overflow-y-auto">
        <div
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={handleClose}
        />

        <div className="flex min-h-full items-center justify-center p-4">
          <div className="relative w-full max-w-md transform rounded-xl bg-card p-6 shadow-2xl transition-all">
            {/* Success icon */}
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
              <svg
                className="h-8 w-8 text-green-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>

            <h3 className="mt-4 text-center text-lg font-semibold text-foreground">
              All Clients Connected!
            </h3>

            <p className="mt-2 text-center text-sm text-muted-foreground">
              {connectedCount} of {totalCount} clients are now connected to their
              Xero organizations.
            </p>

            {connectAllProgress.skipped.length > 0 && (
              <p className="mt-2 text-center text-sm text-yellow-600">
                {connectAllProgress.skipped.length} client(s) were skipped.
              </p>
            )}

            <button
              onClick={handleClose}
              className="mt-6 w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Initial state - not started yet
  if (!isActive && remainingCount > 0) {
    return (
      <div className="fixed inset-0 z-50 overflow-y-auto">
        <div
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={handleClose}
        />

        <div className="flex min-h-full items-center justify-center p-4">
          <div className="relative w-full max-w-md transform rounded-xl bg-card p-6 shadow-2xl transition-all">
            {/* Close button */}
            <button
              onClick={handleClose}
              className="absolute right-4 top-4 text-muted-foreground hover:text-muted-foreground"
            >
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>

            {/* Icon */}
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <svg
                className="h-6 w-6 text-primary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>

            <h3 className="mt-4 text-center text-lg font-semibold text-foreground">
              Connect All Remaining Clients
            </h3>

            <p className="mt-2 text-center text-sm text-muted-foreground">
              Connect {remainingCount} unconnected client{remainingCount !== 1 ? 's' : ''} to
              their Xero organizations. You&apos;ll be redirected to Xero for each
              client to authorize access.
            </p>

            {/* Current progress */}
            <div className="mt-4 rounded-lg bg-muted p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Currently connected</span>
                <span className="font-medium text-foreground">
                  {connectedCount} of {totalCount}
                </span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-muted">
                <div
                  className="h-2 rounded-full bg-primary transition-all"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>

            <div className="mt-4 rounded-lg bg-amber-50 p-3">
              <p className="text-xs text-amber-700">
                <strong>Note:</strong> You can pause at any time and resume later.
                Clients will be connected one at a time.
              </p>
            </div>

            {error && (
              <div className="mt-4 rounded-lg bg-red-50 p-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <div className="mt-6 flex gap-3">
              <button
                onClick={handleClose}
                className="flex-1 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleStart}
                disabled={isStarting}
                className="flex-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isStarting ? (
                  <span className="flex items-center justify-center">
                    <svg
                      className="mr-2 h-4 w-4 animate-spin"
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
                    Starting...
                  </span>
                ) : (
                  `Connect ${remainingCount} Client${remainingCount !== 1 ? 's' : ''}`
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Active state - connecting clients
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="fixed inset-0 bg-black bg-opacity-50 transition-opacity" />

      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-md transform rounded-xl bg-card p-6 shadow-2xl transition-all">
          {/* Progress indicator */}
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <svg
              className="h-8 w-8 animate-spin text-primary"
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

          <h3 className="mt-4 text-center text-lg font-semibold text-foreground">
            Connecting Clients to Xero
          </h3>

          <p className="mt-2 text-center text-sm text-muted-foreground">
            Connecting {connectAllProgress.current + 1} of {connectAllProgress.total} clients...
          </p>

          {/* Progress bar */}
          <div className="mt-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Progress</span>
              <span className="font-medium text-foreground">
                {Math.round((connectAllProgress.current / connectAllProgress.total) * 100)}%
              </span>
            </div>
            <div className="mt-2 h-3 rounded-full bg-muted">
              <div
                className="h-3 rounded-full bg-primary transition-all"
                style={{
                  width: `${(connectAllProgress.current / connectAllProgress.total) * 100}%`,
                }}
              />
            </div>
          </div>

          {/* Current client */}
          {currentClient && (
            <div className="mt-4 rounded-lg bg-muted p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Current Client
              </p>
              <p className="mt-1 font-medium text-foreground">{currentClient.name}</p>
              {currentClient.email && (
                <p className="text-sm text-muted-foreground">{currentClient.email}</p>
              )}
            </div>
          )}

          {/* Skipped count */}
          {connectAllProgress.skipped.length > 0 && (
            <p className="mt-3 text-center text-sm text-yellow-600">
              {connectAllProgress.skipped.length} client(s) skipped
            </p>
          )}

          {error && (
            <div className="mt-4 rounded-lg bg-red-50 p-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Actions */}
          <div className="mt-6 flex gap-3">
            <button
              onClick={handleSkip}
              disabled={!currentClient}
              className="flex-1 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              Skip This Client
            </button>
            <button
              onClick={handleClose}
              className="flex-1 rounded-lg bg-muted-foreground px-4 py-2 text-sm font-medium text-white hover:bg-muted-foreground/80"
            >
              Pause
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
