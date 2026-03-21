'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Minus,
  XCircle,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import {
  useSyncProgress,
  type EntityProgressEvent,
  type PhaseCompleteEvent,
  type SyncCompleteEvent,
  type SyncEvent,
  type SyncFailedEvent,
  type SyncStartedEvent,
} from '@/hooks/useSyncProgress';
import { cn } from '@/lib/utils';
import type {
  EntityProgressResponse,
  EntityProgressStatus,
  SyncStatusResponse,
  XeroSyncJob,
} from '@/lib/xero-sync';
import { getEnhancedSyncStatus, getSyncStatus, type XeroSyncStatus } from '@/lib/xero-sync';

// =============================================================================
// Constants
// =============================================================================

/** Polling interval for sync status updates (fallback when SSE unavailable). */
const POLL_INTERVAL_MS = 2_000;

/** Maximum number of consecutive polling errors before giving up. */
const MAX_POLL_ERRORS = 5;

/** Human-readable labels for each sync phase. */
const PHASE_LABELS: Record<number, string> = {
  1: 'Essential Data',
  2: 'Recent History',
  3: 'Full History',
};

/** Human-readable labels for entity types. */
const ENTITY_TYPE_LABELS: Record<string, string> = {
  accounts: 'Chart of Accounts',
  contacts: 'Contacts',
  invoices: 'Invoices',
  bank_transactions: 'Bank Transactions',
  payments: 'Payments',
  credit_notes: 'Credit Notes',
  overpayments: 'Overpayments',
  prepayments: 'Prepayments',
  journals: 'Journals',
  manual_journals: 'Manual Journals',
  purchase_orders: 'Purchase Orders',
  repeating_invoices: 'Repeating Invoices',
  tracking_categories: 'Tracking Categories',
  quotes: 'Quotes',
  payroll: 'Payroll',
  assets: 'Assets',
  org_profile: 'Organisation Profile',
};

// =============================================================================
// Props
// =============================================================================

interface SyncProgressDialogProps {
  /** Whether the dialog is open. Controlled by the parent. */
  open: boolean;
  /** Called when the user closes the dialog. Does NOT cancel the sync. */
  onOpenChange: (open: boolean) => void;
  /** The Xero connection ID for the active sync. */
  connectionId: string;
  /** The sync job ID to track. */
  jobId: string;
  /** Optional callback when the sync reaches a terminal state. */
  onComplete?: (job: XeroSyncJob) => void;
  /** Polling interval in milliseconds. Defaults to 2000. */
  pollInterval?: number;
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Returns the appropriate status icon for an entity sync status.
 */
function EntityStatusIcon({ status }: { status: EntityProgressStatus }) {
  switch (status) {
    case 'in_progress':
      return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
    case 'completed':
      return <CheckCircle2 className="h-4 w-4 text-status-success" />;
    case 'failed':
      return <XCircle className="h-4 w-4 text-status-danger" />;
    case 'skipped':
      return <Minus className="h-4 w-4 text-muted-foreground" />;
    case 'pending':
    default:
      return <Minus className="h-4 w-4 text-muted-foreground/50" />;
  }
}

/**
 * Returns the human-readable label for an entity type, falling back to a
 * formatted version of the raw string if no label is defined.
 */
function getEntityLabel(entityType: string): string {
  if (ENTITY_TYPE_LABELS[entityType]) {
    return ENTITY_TYPE_LABELS[entityType];
  }
  // Fallback: replace underscores and capitalise each word
  return entityType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Calculates an overall progress percentage from a list of entity progress
 * records. Each entity contributes equally.
 */
function calculateOverallProgress(entities: EntityProgressResponse[]): number {
  if (entities.length === 0) return 0;

  const completedOrFailed = entities.filter(
    (e) => e.status === 'completed' || e.status === 'failed' || e.status === 'skipped'
  ).length;

  const inProgress = entities.filter((e) => e.status === 'in_progress').length;

  // In-progress entities count as 50% done for the progress bar
  const effectiveComplete = completedOrFailed + inProgress * 0.5;

  return Math.round((effectiveComplete / entities.length) * 100);
}

/**
 * Merges an SSE entity_progress event into the existing entity progress list.
 * If an entity with the same entity_type exists, updates it in place;
 * otherwise appends a new entry.
 */
function mergeEntityProgress(
  entities: EntityProgressResponse[],
  event: EntityProgressEvent
): EntityProgressResponse[] {
  const existingIndex = entities.findIndex(
    (e) => e.entity_type === event.entity_type
  );

  const updated: EntityProgressResponse = {
    entity_type: event.entity_type,
    status: event.status as EntityProgressStatus,
    records_processed: event.records_processed ?? 0,
    records_created: event.records_created ?? 0,
    records_updated: event.records_updated ?? 0,
    records_failed: event.records_failed ?? 0,
    error_message: null,
    duration_ms: null,
  };

  if (existingIndex >= 0) {
    const next = [...entities];
    next[existingIndex] = { ...next[existingIndex], ...updated };
    return next;
  }

  return [...entities, updated];
}

// =============================================================================
// Component
// =============================================================================

/**
 * Non-blocking dialog that displays real-time sync progress for a Xero
 * connection. Closing the dialog does NOT cancel the sync -- the sync
 * continues in the background and can be monitored via the
 * SyncNotificationBadge component.
 *
 * Uses Server-Sent Events (SSE) via the useSyncProgress hook for real-time
 * updates. Falls back to polling the enhanced sync status endpoint when
 * SSE is unavailable or encounters errors.
 */
export function SyncProgressDialog({
  open,
  onOpenChange,
  connectionId,
  jobId,
  onComplete,
  pollInterval = POLL_INTERVAL_MS,
}: SyncProgressDialogProps) {
  const { getToken } = useAuth();

  const [syncStatus, setSyncStatus] = useState<SyncStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Whether we should fall back to polling (SSE failed or disconnected)
  const [usePollingFallback, setUsePollingFallback] = useState(false);

  // Refs to avoid stale closures in the polling interval callback
  const onCompleteRef = useRef(onComplete);
  const errorCountRef = useRef(0);
  const hasNotifiedCompleteRef = useRef(false);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  // Reset the completion notification flag when the jobId changes
  useEffect(() => {
    hasNotifiedCompleteRef.current = false;
    setUsePollingFallback(false);
  }, [jobId]);

  // ---------------------------------------------------------------------------
  // SSE via useSyncProgress hook
  // ---------------------------------------------------------------------------

  const handleSSEEvent = useCallback(
    (event: SyncEvent) => {
      setSyncStatus((prev) => {
        // Build updated status from SSE events
        const current = prev ?? {
          job: {
            id: jobId,
            connection_id: connectionId,
            status: 'in_progress',
            sync_type: 'full',
            sync_phase: 1,
            triggered_by: 'user',
            records_processed: 0,
            records_created: 0,
            records_updated: 0,
            records_failed: 0,
            error_message: null,
            started_at: new Date().toISOString(),
            completed_at: null,
            created_at: new Date().toISOString(),
          } as XeroSyncJob,
          entities: [],
          phase: 1,
          total_phases: 3,
          records_processed: 0,
          records_created: 0,
          records_updated: 0,
          records_failed: 0,
          post_sync_tasks: [],
        };

        switch (event.type) {
          case 'sync_started': {
            const started = event as SyncStartedEvent;
            return {
              ...current,
              phase: started.phase,
              job: {
                ...current.job,
                status: 'in_progress',
                sync_phase: started.phase,
              },
            };
          }

          case 'entity_progress': {
            const ep = event as EntityProgressEvent;
            const entities = mergeEntityProgress(current.entities, ep);
            // Recalculate aggregate counts from entity list
            const processed = entities.reduce((s, e) => s + e.records_processed, 0);
            const created = entities.reduce((s, e) => s + e.records_created, 0);
            const updated = entities.reduce((s, e) => s + e.records_updated, 0);
            const failed = entities.reduce((s, e) => s + e.records_failed, 0);
            return {
              ...current,
              entities,
              records_processed: processed,
              records_created: created,
              records_updated: updated,
              records_failed: failed,
            };
          }

          case 'phase_complete': {
            const pc = event as PhaseCompleteEvent;
            return {
              ...current,
              phase: pc.next_phase ?? pc.phase,
              job: {
                ...current.job,
                sync_phase: pc.next_phase ?? pc.phase,
              },
            };
          }

          case 'sync_complete': {
            const sc = event as SyncCompleteEvent;
            const completedJob: XeroSyncJob = {
              ...current.job,
              status: (sc.status as XeroSyncStatus) || 'completed',
              records_processed: sc.records_processed,
              records_created: sc.records_created,
              records_updated: sc.records_updated,
              records_failed: sc.records_failed,
              completed_at: new Date().toISOString(),
            };
            // Notify parent of completion
            if (!hasNotifiedCompleteRef.current) {
              hasNotifiedCompleteRef.current = true;
              onCompleteRef.current?.(completedJob);
            }
            return {
              ...current,
              job: completedJob,
              records_processed: sc.records_processed,
              records_created: sc.records_created,
              records_updated: sc.records_updated,
              records_failed: sc.records_failed,
            };
          }

          case 'sync_failed': {
            const sf = event as SyncFailedEvent;
            const failedJob: XeroSyncJob = {
              ...current.job,
              status: 'failed',
              error_message: sf.error,
              completed_at: new Date().toISOString(),
            };
            if (!hasNotifiedCompleteRef.current) {
              hasNotifiedCompleteRef.current = true;
              onCompleteRef.current?.(failedJob);
            }
            return {
              ...current,
              job: failedJob,
            };
          }

          case 'post_sync_progress':
            // Post-sync tasks are informational; no state merge needed here
            return current;

          default:
            return current;
        }
      });

      setError(null);
    },
    [connectionId, jobId]
  );

  const {
    status: sseStatus,
  } = useSyncProgress({
    connectionId,
    jobId,
    enabled: open && !usePollingFallback,
    onEvent: handleSSEEvent,
    onComplete: () => {
      // Handled in handleSSEEvent via sync_complete / sync_failed
    },
    onError: () => {
      // SSE error event -- will trigger fallback below
    },
  });

  // If SSE enters a persistent error state, activate polling fallback
  useEffect(() => {
    if (sseStatus === 'error' && !usePollingFallback) {
      setUsePollingFallback(true);
    }
  }, [sseStatus, usePollingFallback]);

  // ---------------------------------------------------------------------------
  // Polling fallback (used when SSE is unavailable or has failed)
  // ---------------------------------------------------------------------------

  /**
   * Fetches the latest enhanced sync status. Falls back to the basic
   * getSyncStatus endpoint if the enhanced endpoint is unavailable.
   */
  const fetchStatus = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      try {
        const status = await getEnhancedSyncStatus(token, connectionId, jobId);
        setSyncStatus(status);
        setError(null);
        errorCountRef.current = 0;

        // Notify parent when the sync reaches a terminal state
        const terminalStatuses = ['completed', 'failed', 'cancelled'];
        if (
          terminalStatuses.includes(status.job.status) &&
          !hasNotifiedCompleteRef.current
        ) {
          hasNotifiedCompleteRef.current = true;
          onCompleteRef.current?.(status.job);
        }
      } catch {
        // Fallback: try the basic sync status endpoint and wrap it
        const basicJob = await getSyncStatus(token, connectionId, jobId);
        const fallbackStatus: SyncStatusResponse = {
          job: basicJob,
          entities: [],
          phase: basicJob.sync_phase,
          total_phases: 3,
          records_processed: basicJob.records_processed,
          records_created: basicJob.records_created,
          records_updated: basicJob.records_updated,
          records_failed: basicJob.records_failed,
          post_sync_tasks: [],
        };
        setSyncStatus(fallbackStatus);
        setError(null);
        errorCountRef.current = 0;

        const terminalStatuses = ['completed', 'failed', 'cancelled'];
        if (
          terminalStatuses.includes(basicJob.status) &&
          !hasNotifiedCompleteRef.current
        ) {
          hasNotifiedCompleteRef.current = true;
          onCompleteRef.current?.(basicJob);
        }
      }
    } catch (err) {
      errorCountRef.current++;
      if (errorCountRef.current >= MAX_POLL_ERRORS) {
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to fetch sync status'
        );
      }
    }
  }, [getToken, connectionId, jobId]);

  // Poll for status while the dialog is open AND SSE is unavailable
  useEffect(() => {
    if (!open || !usePollingFallback) return;

    // Fetch immediately on activation
    fetchStatus();

    const intervalId = setInterval(() => {
      // Stop polling if the sync is in a terminal state
      if (
        syncStatus?.job.status === 'completed' ||
        syncStatus?.job.status === 'failed' ||
        syncStatus?.job.status === 'cancelled'
      ) {
        return;
      }
      fetchStatus();
    }, pollInterval);

    return () => clearInterval(intervalId);
  }, [open, usePollingFallback, fetchStatus, pollInterval, syncStatus?.job.status]);

  // Also do an initial fetch to populate the dialog regardless of SSE status
  useEffect(() => {
    if (open && !syncStatus) {
      fetchStatus();
    }
    // Only run on open/syncStatus change, not on every fetchStatus recreation
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------

  const job = syncStatus?.job ?? null;
  const entities = syncStatus?.entities ?? [];
  const currentPhase = syncStatus?.phase ?? job?.sync_phase ?? null;
  const totalPhases = syncStatus?.total_phases ?? 3;
  const isActive = job?.status === 'pending' || job?.status === 'in_progress';
  const overallProgress = isActive ? calculateOverallProgress(entities) : 100;

  const phaseLabel =
    currentPhase != null && PHASE_LABELS[currentPhase]
      ? `Phase ${currentPhase} of ${totalPhases}: ${PHASE_LABELS[currentPhase]}`
      : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Sync Progress</DialogTitle>
          <DialogDescription>
            {isActive
              ? 'Sync is running in the background. You can close this dialog safely.'
              : job?.status === 'completed'
                ? 'Sync completed successfully.'
                : job?.status === 'failed'
                  ? 'Sync encountered an error.'
                  : job?.status === 'cancelled'
                    ? 'Sync was cancelled.'
                    : 'Loading sync status...'}
          </DialogDescription>
        </DialogHeader>

        {/* Main content area -- scrollable */}
        <div className="flex-1 overflow-y-auto space-y-4 py-2">
          {/* Error state */}
          {error && !syncStatus && (
            <div className="flex flex-col items-center gap-2 py-6">
              <AlertCircle className="h-10 w-10 text-status-danger" />
              <p className="text-sm text-status-danger text-center">{error}</p>
            </div>
          )}

          {/* Loading state */}
          {!syncStatus && !error && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          )}

          {/* Sync status content */}
          {syncStatus && (
            <>
              {/* Phase indicator */}
              {phaseLabel && (
                <div
                  className={cn(
                    'rounded-md px-3 py-2 text-sm font-medium',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'bg-status-success/10 text-status-success'
                  )}
                >
                  {phaseLabel}
                </div>
              )}

              {/* Overall progress bar */}
              {isActive && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Overall progress</span>
                    <span>{overallProgress}%</span>
                  </div>
                  <Progress value={overallProgress} className="h-2" />
                </div>
              )}

              {/* Aggregate record counts */}
              <div className="grid grid-cols-4 gap-2 text-center">
                <div className="rounded-md bg-muted/50 p-2">
                  <div className="text-lg font-semibold">
                    {syncStatus.records_processed.toLocaleString()}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Processed
                  </div>
                </div>
                <div className="rounded-md bg-muted/50 p-2">
                  <div className="text-lg font-semibold text-status-success">
                    {syncStatus.records_created.toLocaleString()}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Created
                  </div>
                </div>
                <div className="rounded-md bg-muted/50 p-2">
                  <div className="text-lg font-semibold text-primary">
                    {syncStatus.records_updated.toLocaleString()}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Updated
                  </div>
                </div>
                <div className="rounded-md bg-muted/50 p-2">
                  <div className="text-lg font-semibold text-status-danger">
                    {syncStatus.records_failed.toLocaleString()}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Failed
                  </div>
                </div>
              </div>

              {/* Job-level error message */}
              {job?.error_message && (
                <div className="rounded-md border border-status-danger/20 bg-status-danger/10 p-3 text-sm text-status-danger">
                  {job.error_message}
                </div>
              )}

              {/* Per-entity progress list */}
              {entities.length > 0 && (
                <div className="space-y-1.5">
                  <h4 className="text-sm font-medium text-foreground">
                    Entity progress
                  </h4>
                  <div className="rounded-md border divide-y">
                    {entities.map((entity) => (
                      <div
                        key={entity.entity_type}
                        className="flex items-center justify-between px-3 py-2 text-sm"
                      >
                        <div className="flex items-center gap-2">
                          <EntityStatusIcon status={entity.status} />
                          <span className="text-foreground">
                            {getEntityLabel(entity.entity_type)}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground">
                          {/* Record count -- only show when meaningful */}
                          {(entity.status === 'completed' ||
                            entity.status === 'in_progress') &&
                            entity.records_processed > 0 && (
                              <span>
                                {entity.records_processed.toLocaleString()}{' '}
                                records
                              </span>
                            )}
                          {/* Duration -- only show when completed */}
                          {entity.status === 'completed' &&
                            entity.duration_ms != null && (
                              <span>
                                {entity.duration_ms < 1000
                                  ? `${entity.duration_ms}ms`
                                  : `${(entity.duration_ms / 1000).toFixed(1)}s`}
                              </span>
                            )}
                          {/* Error message */}
                          {entity.status === 'failed' &&
                            entity.error_message && (
                              <span
                                className="max-w-[150px] truncate text-status-danger"
                                title={entity.error_message}
                              >
                                {entity.error_message}
                              </span>
                            )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <DialogFooter className="flex-shrink-0 gap-2 sm:gap-0">
          {isActive && (
            <p className="mr-auto text-xs text-muted-foreground self-center">
              Sync will continue in the background
            </p>
          )}
          <Button
            variant="secondary"
            onClick={() => onOpenChange(false)}
          >
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default SyncProgressDialog;
