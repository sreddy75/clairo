'use client';

import { useAuth } from '@clerk/nextjs';
import { Bell } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { XeroSyncJob } from '@/lib/xero-sync';
import { getSyncHistory } from '@/lib/xero-sync';

/** Polling interval in milliseconds for checking active syncs. */
const POLL_INTERVAL_MS = 30_000;

interface SyncNotificationBadgeProps {
  /** If specified, tracks only syncs for this connection. */
  connectionId?: string;
  /** Additional CSS class names. */
  className?: string;
}

/**
 * Displays a bell icon with a badge showing the count of active (in-progress
 * or pending) Xero sync jobs. Polls for sync status and shows a sonner toast
 * notification when a sync job completes with a record count summary.
 *
 * When no syncs are active the badge is hidden and the icon appears muted.
 */
export function SyncNotificationBadge({
  connectionId,
  className,
}: SyncNotificationBadgeProps) {
  const { getToken } = useAuth();

  /** Count of currently active (pending + in_progress) sync jobs. */
  const [activeCount, setActiveCount] = useState(0);

  /**
   * Tracks job IDs that were active on the previous poll so we can detect
   * transitions from active to completed and fire a toast notification.
   */
  const previousActiveJobsRef = useRef<Map<string, XeroSyncJob>>(new Map());

  /**
   * Tracks job IDs for which we have already shown a completion toast so
   * we do not show duplicate notifications.
   */
  const notifiedJobsRef = useRef<Set<string>>(new Set());

  /**
   * Fetch recent sync jobs, update the active count, and fire toast
   * notifications for any jobs that transitioned to completed since the
   * last poll.
   */
  const pollSyncStatus = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      // If no connectionId is specified we cannot query sync history because
      // the API requires a connectionId. In that case the badge simply stays
      // hidden. A future enhancement (e.g. a tenant-wide active-syncs
      // endpoint from T019) would remove this limitation.
      if (!connectionId) return;

      const history = await getSyncHistory(token, connectionId, 20, 0);
      const jobs = history.jobs;

      // Partition jobs into active vs recently completed.
      const activeJobs = jobs.filter(
        (j) => j.status === 'pending' || j.status === 'in_progress'
      );

      const completedJobs = jobs.filter(
        (j) => j.status === 'completed' || j.status === 'failed'
      );

      setActiveCount(activeJobs.length);

      // Build a map of currently active job IDs for the next poll cycle.
      const currentActiveMap = new Map<string, XeroSyncJob>();
      for (const job of activeJobs) {
        currentActiveMap.set(job.id, job);
      }

      // Detect jobs that were active on the previous poll but are now
      // completed or failed -- these are transitions worth notifying about.
      const previousActive = previousActiveJobsRef.current;
      previousActive.forEach((_prevJob, jobId) => {
        // Skip if already notified.
        if (notifiedJobsRef.current.has(jobId)) return;

        // Still active -- no notification yet.
        if (currentActiveMap.has(jobId)) return;

        // Find the job in the completed list to get final record counts.
        const finishedJob = completedJobs.find((j) => j.id === jobId);
        if (!finishedJob) return;

        notifiedJobsRef.current.add(jobId);

        const totalRecords = finishedJob.records_processed ?? 0;
        const formattedCount = totalRecords.toLocaleString();

        if (finishedJob.status === 'completed') {
          toast.success(
            `Sync complete — ${formattedCount} records synced`,
            { duration: 6_000 }
          );
        } else if (finishedJob.status === 'failed') {
          toast.error(
            finishedJob.error_message ?? 'Sync failed',
            { duration: 8_000 }
          );
        }
      });

      previousActiveJobsRef.current = currentActiveMap;
    } catch {
      // Silently ignore polling errors to avoid spamming the user.
    }
  }, [connectionId, getToken]);

  // Set up the polling interval (skip when tab is hidden).
  useEffect(() => {
    if (!connectionId) return;

    // Run immediately on mount, then at the configured interval.
    pollSyncStatus();
    const interval = setInterval(() => {
      if (!document.hidden) pollSyncStatus();
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [connectionId, pollSyncStatus]);

  // Clean up notified jobs set when connectionId changes.
  useEffect(() => {
    notifiedJobsRef.current.clear();
    previousActiveJobsRef.current.clear();
  }, [connectionId]);

  const hasActiveSyncs = activeCount > 0;

  return (
    <Button
      variant="ghost"
      size="icon"
      className={cn('relative', className)}
      aria-label={
        hasActiveSyncs
          ? `${activeCount} sync${activeCount > 1 ? 's' : ''} in progress`
          : 'No active syncs'
      }
    >
      <Bell
        className={cn(
          'h-5 w-5 transition-colors',
          hasActiveSyncs ? 'text-blue-600' : 'text-muted-foreground'
        )}
      />

      {/* Animated badge showing active sync count */}
      {hasActiveSyncs && (
        <Badge
          className={cn(
            'absolute -top-1 -right-1 h-5 min-w-[1.25rem] px-1',
            'flex items-center justify-center',
            'bg-blue-600 text-white text-[10px] leading-none',
            'animate-in fade-in zoom-in-50 duration-200'
          )}
        >
          {activeCount}
        </Badge>
      )}
    </Button>
  );
}

export default SyncNotificationBadge;
