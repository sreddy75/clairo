'use client';

import { AlertTriangle, Clock, RefreshCw, XCircle } from 'lucide-react';

import type { SyncFreshness, XeroSyncStatus } from '@/lib/xero-sync';
import {
  formatRelativeTime,
  getSyncFreshness,
} from '@/lib/xero-sync';

interface SyncStatusDisplayProps {
  /** Current sync status (null if no sync in progress) */
  status: XeroSyncStatus | null;
  /** Last successful sync timestamp */
  lastSyncAt: string | null | undefined;
  /** Whether sync is currently in progress */
  isSyncing: boolean;
  /** Error message if sync failed */
  errorMessage?: string | null;
  /** Show compact version */
  compact?: boolean;
}

/** Map freshness levels to Tailwind color classes and indicator dot colors. */
const FRESHNESS_STYLES: Record<
  SyncFreshness,
  { textClass: string; dotClass: string; label: string }
> = {
  fresh: {
    textClass: 'text-status-success',
    dotClass: 'bg-green-500',
    label: 'Data is up to date',
  },
  recent: {
    textClass: 'text-muted-foreground',
    dotClass: 'bg-status-neutral',
    label: 'Data is recent',
  },
  stale: {
    textClass: 'text-amber-600',
    dotClass: 'bg-amber-500',
    label: 'Data may be stale',
  },
  very_stale: {
    textClass: 'text-status-danger',
    dotClass: 'bg-red-500',
    label: 'Data is outdated',
  },
};

/**
 * Displays the current sync status for a Xero connection.
 * Shows last sync time with a freshness indicator (colored dot),
 * stale data warnings, and current sync progress.
 */
export function SyncStatusDisplay({
  status,
  lastSyncAt,
  isSyncing,
  errorMessage,
  compact = false,
}: SyncStatusDisplayProps) {
  const relativeTime = formatRelativeTime(lastSyncAt);
  const freshness = getSyncFreshness(lastSyncAt);

  // Currently syncing
  if (isSyncing || status === 'in_progress') {
    return (
      <div className={`flex items-center gap-2 ${compact ? 'text-sm' : ''}`}>
        <RefreshCw className="w-4 h-4 animate-spin text-primary" />
        <span className="text-blue-700">Syncing...</span>
      </div>
    );
  }

  // Pending sync
  if (status === 'pending') {
    return (
      <div className={`flex items-center gap-2 ${compact ? 'text-sm' : ''}`}>
        <Clock className="w-4 h-4 text-yellow-500" />
        <span className="text-yellow-700">Sync pending</span>
      </div>
    );
  }

  // Failed sync
  if (status === 'failed' && errorMessage) {
    return (
      <div className={`flex flex-col gap-1 ${compact ? 'text-sm' : ''}`}>
        <div className="flex items-center gap-2">
          <XCircle className="w-4 h-4 text-status-danger" />
          <span className="text-red-700">Sync failed</span>
        </div>
        {!compact && (
          <p className="text-xs text-status-danger ml-6">{errorMessage}</p>
        )}
      </div>
    );
  }

  // Never synced
  if (!lastSyncAt) {
    return (
      <div className={`flex items-center gap-2 ${compact ? 'text-sm' : ''}`}>
        <AlertTriangle className="w-4 h-4 text-amber-500" />
        <span className="text-amber-700">Never synced</span>
      </div>
    );
  }

  // Data freshness display with colored dot indicator
  const style = FRESHNESS_STYLES[freshness];

  // Very stale (>48h) -- show a prominent warning
  if (freshness === 'very_stale') {
    return (
      <div className={`flex flex-col gap-1 ${compact ? 'text-sm' : ''}`}>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block w-2.5 h-2.5 rounded-full ${style.dotClass} flex-shrink-0`}
            aria-hidden="true"
          />
          <span className={style.textClass}>{style.label}</span>
        </div>
        <p className="text-xs text-muted-foreground ml-[1.125rem]">
          Last synced {relativeTime}
        </p>
      </div>
    );
  }

  // Stale (24-48h) -- amber warning
  if (freshness === 'stale') {
    return (
      <div className={`flex flex-col gap-1 ${compact ? 'text-sm' : ''}`}>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block w-2.5 h-2.5 rounded-full ${style.dotClass} flex-shrink-0`}
            aria-hidden="true"
          />
          <span className={style.textClass}>{style.label}</span>
        </div>
        <p className="text-xs text-muted-foreground ml-[1.125rem]">
          Last synced {relativeTime}
        </p>
      </div>
    );
  }

  // Fresh (<1h) or recent (1-24h) -- single line with dot
  return (
    <div className={`flex items-center gap-2 ${compact ? 'text-sm' : ''}`}>
      <span
        className={`inline-block w-2.5 h-2.5 rounded-full ${style.dotClass} flex-shrink-0`}
        aria-hidden="true"
      />
      <span className={style.textClass}>
        Last synced {relativeTime}
      </span>
    </div>
  );
}

export default SyncStatusDisplay;
