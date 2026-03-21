'use client';

import { useAuth } from '@clerk/nextjs';
import { Loader2, RefreshCw, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import {
  startMultiClientSync,
  getMultiClientSyncStatus,
  type MultiClientSyncResponse,
  type MultiClientSyncStatusResponse,
} from '@/lib/xero-sync';

interface MultiClientSyncButtonProps {
  /** Optional callback when all syncs complete */
  onComplete?: () => void;
  /** Compact mode for toolbar placement */
  compact?: boolean;
}

/**
 * MultiClientSyncButton
 *
 * "Sync All Clients" button that triggers a batch sync across all connected
 * Xero clients. Shows a confirmation dialog before starting, displays
 * aggregate progress during sync, and handles partial failures gracefully.
 *
 * Spec 043: Phase 5 (US3 - Multi-Client Parallel Sync)
 */
export function MultiClientSyncButton({ onComplete, compact }: MultiClientSyncButtonProps) {
  const { getToken } = useAuth();
  const [isSyncing, setIsSyncing] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [batchResult, setBatchResult] = useState<MultiClientSyncResponse | null>(null);
  const [status, setStatus] = useState<MultiClientSyncStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Poll for status while syncing (skip when tab is hidden)
  useEffect(() => {
    if (!isSyncing) return;

    const pollStatus = async () => {
      try {
        const token = await getToken();
        if (!token) return;
        const currentStatus = await getMultiClientSyncStatus(token);
        setStatus(currentStatus);

        // Check if all syncs are done
        if (currentStatus.syncing === 0 && currentStatus.pending === 0) {
          setIsSyncing(false);
          onComplete?.();
        }
      } catch {
        // Silently ignore poll errors to avoid disrupting the user
      }
    };

    pollStatus();
    const interval = setInterval(() => {
      if (!document.hidden) pollStatus();
    }, 5000);
    return () => clearInterval(interval);
  }, [isSyncing, getToken, onComplete]);

  const handleSync = useCallback(async () => {
    setShowConfirm(false);
    setError(null);
    setIsSyncing(true);

    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const result = await startMultiClientSync(token);
      setBatchResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start sync');
      setIsSyncing(false);
    }
  }, [getToken]);

  const syncedCount = status ? status.completed + status.failed : 0;
  const totalCount = status?.total_connections ?? batchResult?.jobs_queued ?? 0;
  const progressPercent = totalCount > 0 ? Math.round((syncedCount / totalCount) * 100) : 0;

  return (
    <div className="relative">
      {/* Sync Button */}
      <button
        onClick={() => setShowConfirm(true)}
        disabled={isSyncing}
        className={`inline-flex items-center gap-2 rounded-lg border transition-colors
          ${compact ? 'px-3 py-1.5 text-sm' : 'px-4 py-2 text-sm'}
          ${isSyncing
            ? 'border-primary/20 bg-primary/10 text-primary cursor-not-allowed'
            : 'border-border bg-card text-foreground hover:bg-muted'
          }`}
      >
        {isSyncing ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <RefreshCw className="w-4 h-4" />
        )}
        {isSyncing ? (
          <span>
            Syncing {syncedCount}/{totalCount} clients
            {totalCount > 0 && ` (${progressPercent}%)`}
          </span>
        ) : (
          <span>Sync All Clients</span>
        )}
      </button>

      {/* Progress Bar (shown during sync) */}
      {isSyncing && totalCount > 0 && (
        <div className="absolute left-0 right-0 -bottom-1 h-0.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      )}

      {/* Confirmation Dialog (inline dropdown) */}
      {showConfirm && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-card border border-border rounded-lg shadow-lg z-50 p-4">
          <p className="text-sm font-medium text-foreground mb-2">
            Sync all clients?
          </p>
          <p className="text-xs text-muted-foreground mb-4">
            This will start a background sync for all connected Xero clients.
            Clients with active syncs will be skipped.
          </p>
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setShowConfirm(false)}
              className="px-3 py-1.5 text-xs rounded-md border border-border
                text-foreground hover:bg-muted"
            >
              Cancel
            </button>
            <button
              onClick={handleSync}
              className="px-3 py-1.5 text-xs rounded-md bg-primary text-primary-foreground hover:bg-primary/90"
            >
              Start Sync
            </button>
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-status-danger/10 border border-status-danger/20 rounded-lg p-3 z-50">
          <div className="flex items-center gap-2 text-sm text-status-danger">
            <XCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Batch result summary (shown when batch initiated and status available) */}
      {batchResult && isSyncing && status && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-card border border-border rounded-lg shadow-lg z-50 p-4">
          <p className="text-xs font-medium text-foreground mb-2">
            Sync Progress
          </p>

          {/* Per-status counts */}
          <div className="grid grid-cols-3 gap-2 mb-3">
            {status.completed > 0 && (
              <div className="flex items-center gap-1 text-xs text-status-success">
                <CheckCircle2 className="w-3 h-3" />
                <span>{status.completed} done</span>
              </div>
            )}
            {status.syncing > 0 && (
              <div className="flex items-center gap-1 text-xs text-primary">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>{status.syncing} syncing</span>
              </div>
            )}
            {status.failed > 0 && (
              <div className="flex items-center gap-1 text-xs text-status-danger">
                <AlertTriangle className="w-3 h-3" />
                <span>{status.failed} failed</span>
              </div>
            )}
          </div>

          {/* Skipped count */}
          {batchResult.jobs_skipped > 0 && (
            <p className="text-xs text-muted-foreground">
              {batchResult.jobs_skipped} client(s) skipped (already syncing)
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default MultiClientSyncButton;
