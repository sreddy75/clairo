'use client';

import { useAuth } from '@clerk/nextjs';
import { AlertCircle, CheckCircle2, Loader2, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import type { XeroSyncJob, XeroSyncStatus } from '@/lib/xero-sync';
import {
  cancelSync,
  getSyncStatus,
  getSyncTypeName,
} from '@/lib/xero-sync';

interface SyncProgressIndicatorProps {
  /** Connection ID */
  connectionId: string;
  /** Job ID to track */
  jobId: string;
  /** Callback when sync completes */
  onComplete?: (job: XeroSyncJob) => void;
  /** Callback when modal is closed */
  onClose?: () => void;
  /** Polling interval in milliseconds */
  pollInterval?: number;
}

/**
 * Shows sync progress in a modal with real-time updates.
 */
export function SyncProgressIndicator({
  connectionId,
  jobId,
  onComplete,
  onClose,
  pollInterval = 2000,
}: SyncProgressIndicatorProps) {
  const { getToken } = useAuth();
  const [job, setJob] = useState<XeroSyncJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  // Use refs to avoid stale closures
  const jobRef = useRef<XeroSyncJob | null>(null);
  const onCompleteRef = useRef(onComplete);
  const mountedRef = useRef(true);

  // Keep refs in sync
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    jobRef.current = job;
  }, [job]);

  useEffect(() => {
    mountedRef.current = true;
    let intervalId: NodeJS.Timeout | null = null;
    let retryCount = 0;
    const maxRetries = 3;

    const fetchStatus = async () => {
      try {
        const token = await getToken();
        if (!token || !mountedRef.current) return;

        const status = await getSyncStatus(token, connectionId, jobId);

        if (!mountedRef.current) return;

        setJob(status);
        setError(null);
        retryCount = 0; // Reset retry count on success

        // Check if sync is complete
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
          onCompleteRef.current?.(status);
          // Stop polling when complete
          if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
          }
        }
      } catch (err) {
        if (!mountedRef.current) return;

        // Only show error if we haven't loaded job data yet and exhausted retries
        if (!jobRef.current) {
          retryCount++;
          if (retryCount >= maxRetries) {
            setError(err instanceof Error ? err.message : 'Failed to fetch sync status');
            if (intervalId) {
              clearInterval(intervalId);
              intervalId = null;
            }
          }
          // Otherwise, will retry on next interval
        }
        // If we have job data, silently ignore polling errors
      }
    };

    // Initial fetch
    fetchStatus();

    // Set up polling
    intervalId = setInterval(fetchStatus, pollInterval);

    return () => {
      mountedRef.current = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [getToken, connectionId, jobId, pollInterval]);

  const handleCancel = async () => {
    setIsCancelling(true);
    try {
      const token = await getToken();
      if (!token) return;

      await cancelSync(token, connectionId, jobId);
      // Refresh status
      const status = await getSyncStatus(token, connectionId, jobId);
      setJob(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel sync');
    } finally {
      setIsCancelling(false);
    }
  };

  const isActive = job?.status === 'pending' || job?.status === 'in_progress';

  const getStatusIcon = (status: XeroSyncStatus) => {
    switch (status) {
      case 'pending':
      case 'in_progress':
        return <Loader2 className="w-6 h-6 animate-spin text-primary" />;
      case 'completed':
        return <CheckCircle2 className="w-6 h-6 text-status-success" />;
      case 'failed':
        return <AlertCircle className="w-6 h-6 text-status-danger" />;
      case 'cancelled':
        return <X className="w-6 h-6 text-muted-foreground" />;
    }
  };

  const getStatusText = (status: XeroSyncStatus) => {
    switch (status) {
      case 'pending':
        return 'Preparing sync...';
      case 'in_progress':
        return 'Syncing data...';
      case 'completed':
        return 'Sync completed!';
      case 'failed':
        return 'Sync failed';
      case 'cancelled':
        return 'Sync cancelled';
    }
  };

  // Calculate progress percentage (estimated)
  const progressPercent = job?.progress_details
    ? Math.min(
        100,
        Object.keys(job.progress_details).filter(
          (k) => (job.progress_details?.[k] as { status?: string })?.status === 'completed'
        ).length * 20 // 5 entity types now (accounts, contacts, invoices, bank_transactions, payroll)
      )
    : 0;

  // Handle backdrop click to close (only when sync is not active)
  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !isActive) {
      onClose?.();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className="bg-card rounded-xl shadow-xl max-w-md w-full mx-4 border border-border max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border flex-shrink-0">
          <h2 className="text-lg font-semibold text-foreground">
            {job ? getSyncTypeName(job.sync_type) : 'Sync Progress'}
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-muted-foreground hover:text-foreground rounded-lg transition-colors"
            title={isActive ? "Sync in progress" : "Close"}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content - Scrollable */}
        <div className="p-6 overflow-y-auto flex-1">
          {error ? (
            <div className="text-center">
              <AlertCircle className="w-12 h-12 text-status-danger mx-auto mb-3" />
              <p className="text-status-danger">{error}</p>
            </div>
          ) : job ? (
            <div className="space-y-4">
              {/* Status */}
              <div className="flex items-center gap-3">
                {getStatusIcon(job.status)}
                <span className="text-lg font-medium text-foreground">
                  {getStatusText(job.status)}
                </span>
              </div>

              {/* Progress bar */}
              {isActive && (
                <div className="w-full bg-muted rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              )}

              {/* Stats */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="bg-muted rounded-lg p-3">
                  <div className="text-muted-foreground">Processed</div>
                  <div className="text-xl font-semibold text-foreground">
                    {job.records_processed.toLocaleString()}
                  </div>
                </div>
                <div className="bg-muted rounded-lg p-3">
                  <div className="text-muted-foreground">Created</div>
                  <div className="text-xl font-semibold text-status-success">
                    {job.records_created.toLocaleString()}
                  </div>
                </div>
                <div className="bg-muted rounded-lg p-3">
                  <div className="text-muted-foreground">Updated</div>
                  <div className="text-xl font-semibold text-primary">
                    {job.records_updated.toLocaleString()}
                  </div>
                </div>
                <div className="bg-muted rounded-lg p-3">
                  <div className="text-muted-foreground">Failed</div>
                  <div className="text-xl font-semibold text-status-danger">
                    {job.records_failed.toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Error message */}
              {job.error_message && (
                <div className="bg-status-danger/10 text-status-danger p-3 rounded-lg text-sm border border-status-danger/20">
                  {job.error_message}
                </div>
              )}

              {/* Entity progress */}
              {job.progress_details && Object.keys(job.progress_details).length > 0 && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-foreground">Progress by type</div>
                  <div className="space-y-1">
                    {Object.entries(job.progress_details).map(([entity, details]) => {
                      const entityDetails = details as { status?: string; processed?: number };
                      return (
                        <div
                          key={entity}
                          className="flex items-center justify-between text-sm"
                        >
                          <span className="text-muted-foreground capitalize">{entity.replace('_', ' ')}</span>
                          <span
                            className={
                              entityDetails?.status === 'completed' || entityDetails?.status === 'complete'
                                ? 'text-status-success'
                                : entityDetails?.status === 'failed'
                                ? 'text-status-danger'
                                : 'text-primary'
                            }
                          >
                            {entityDetails?.status || 'pending'}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>

        {/* Footer - Always visible */}
        <div className="flex justify-end gap-3 p-4 border-t border-border flex-shrink-0">
          {isActive && (
            <button
              onClick={handleCancel}
              disabled={isCancelling}
              className="px-4 py-2 text-sm font-medium text-status-danger bg-status-danger/10 hover:bg-status-danger/20 rounded-lg transition-colors disabled:opacity-50"
            >
              {isCancelling ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                'Cancel Sync'
              )}
            </button>
          )}
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-foreground bg-muted hover:bg-muted/80 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default SyncProgressIndicator;
