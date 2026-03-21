'use client';

/**
 * DataFreshnessIndicator Component
 *
 * Shows "Data as of [date]" badge for AI-generated content.
 * Displays a stale warning when data is older than the threshold.
 */

import { AlertTriangle, Clock } from 'lucide-react';

interface DataFreshnessIndicatorProps {
  lastSyncDate: string | null | undefined;
  staleDaysThreshold?: number;
}

function daysBetween(date1: Date, date2: Date): number {
  const diffMs = Math.abs(date2.getTime() - date1.getTime());
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export function DataFreshnessIndicator({
  lastSyncDate,
  staleDaysThreshold = 7,
}: DataFreshnessIndicatorProps) {
  if (!lastSyncDate) {
    return (
      <div className="inline-flex items-center gap-1.5 px-2 py-1 text-xs text-muted-foreground bg-muted rounded-md">
        <Clock className="w-3 h-3" />
        <span>Data freshness unknown</span>
      </div>
    );
  }

  const syncDate = new Date(lastSyncDate);
  const daysAgo = daysBetween(syncDate, new Date());
  const isStale = daysAgo >= staleDaysThreshold;

  if (isStale) {
    return (
      <div className="inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-status-warning bg-status-warning/10 border border-status-warning/20 rounded-md">
        <AlertTriangle className="w-3 h-3" />
        <span>
          Data may be stale — last synced {daysAgo} day{daysAgo !== 1 ? 's' : ''} ago
        </span>
      </div>
    );
  }

  return (
    <div className="inline-flex items-center gap-1.5 px-2 py-1 text-xs text-muted-foreground bg-muted rounded-md">
      <Clock className="w-3 h-3" />
      <span>Data as of {formatDate(lastSyncDate)}</span>
    </div>
  );
}

export default DataFreshnessIndicator;
