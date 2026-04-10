'use client';

/**
 * Bulk Import Progress Page (Phase 035 - T023)
 *
 * Real-time progress dashboard showing:
 * - Overall progress bar
 * - Per-organization sync status
 * - Retry for failed orgs
 * - Estimated time remaining
 */

import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Loader2,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import { useBulkImportApi } from '@/lib/api/bulk-import';
import type {
  BulkImportJobDetailResponse,
  BulkImportOrgStatusType,
} from '@/types/bulk-import';

const STATUS_CONFIG: Record<
  BulkImportOrgStatusType,
  { label: string; color: string; icon: React.ElementType }
> = {
  pending: {
    label: 'Pending',
    color: 'bg-muted text-muted-foreground',
    icon: Clock,
  },
  importing: {
    label: 'Importing',
    color: 'bg-primary/10 text-primary',
    icon: Loader2,
  },
  syncing: {
    label: 'Syncing',
    color: 'bg-accent text-accent-foreground',
    icon: Loader2,
  },
  completed: {
    label: 'Completed',
    color: 'bg-status-success/10 text-status-success',
    icon: CheckCircle2,
  },
  failed: {
    label: 'Failed',
    color: 'bg-status-danger/10 text-status-danger',
    icon: XCircle,
  },
  skipped: {
    label: 'Skipped',
    color: 'bg-muted text-muted-foreground/70',
    icon: Clock,
  },
};

export default function BulkImportProgressPage() {
  const params = useParams();
  const jobId = params.jobId as string;
  const bulkImportApi = useBulkImportApi();

  const [job, setJob] = useState<BulkImportJobDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRetrying, setIsRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const isTerminal =
    job &&
    ['completed', 'partial_failure', 'failed', 'cancelled'].includes(
      job.status
    );

  const fetchStatus = useCallback(async () => {
    try {
      const result = await bulkImportApi.getBulkImportStatus(jobId);
      setJob(result);
      setIsLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch status');
      setIsLoading(false);
    }
  }, [jobId, bulkImportApi]);

  // Start polling
  useEffect(() => {
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 2000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchStatus]);

  // Stop polling when terminal
  useEffect(() => {
    if (isTerminal && intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, [isTerminal]);

  const handleRetry = async () => {
    setIsRetrying(true);
    setError(null);
    try {
      await bulkImportApi.retryFailedOrgs(jobId);
      // Restart polling
      if (!intervalRef.current) {
        intervalRef.current = setInterval(fetchStatus, 2000);
      }
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry');
    } finally {
      setIsRetrying(false);
    }
  };

  // Estimate remaining time
  const estimatedRemaining = (() => {
    if (!job) return null;
    const completed = job.imported_count + job.failed_count + job.skipped_count;
    const remaining = job.total_organizations - completed;
    if (remaining <= 0 || !job.started_at) return null;

    const startTime = new Date(job.started_at).getTime();
    const elapsed = Date.now() - startTime;
    if (completed === 0) return null;

    const avgPerOrg = elapsed / completed;
    const remainingMs = avgPerOrg * remaining;
    const minutes = Math.ceil(remainingMs / 60000);
    return minutes <= 1 ? 'Less than a minute' : `~${minutes} minutes`;
  })();

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
        <p className="text-muted-foreground">Loading import status...</p>
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="max-w-xl mx-auto py-12">
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-xl p-6 text-center">
          <XCircle className="w-12 h-12 text-status-danger mx-auto mb-4" />
          <p className="text-status-danger mb-4">{error}</p>
          <Link
            href="/clients"
            className="text-status-danger hover:text-status-danger/80 underline"
          >
            Return to Clients
          </Link>
        </div>
      </div>
    );
  }

  if (!job) return null;

  const progressPercent = job.progress_percent;
  const statusLabel =
    job.status === 'in_progress'
      ? 'In Progress'
      : job.status === 'partial_failure'
        ? 'Completed with Errors'
        : job.status.charAt(0).toUpperCase() + job.status.slice(1);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Link
          href="/clients"
          className="flex items-center gap-1 text-muted-foreground hover:text-foreground mb-4 text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Clients
        </Link>
        <h1 className="text-2xl font-bold text-foreground">
          Bulk Import Progress
        </h1>
        <p className="text-muted-foreground mt-1">
          {isTerminal
            ? `Import ${statusLabel.toLowerCase()}.`
            : 'Importing organizations from Xero...'}
        </p>
      </div>

      {/* Progress Card */}
      <div className="bg-card rounded-xl border border-border p-6 space-y-4">
        {/* Progress Bar */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-foreground">
              {statusLabel}
            </span>
            <span className="text-sm text-muted-foreground">
              {progressPercent}%
            </span>
          </div>
          <div className="w-full bg-muted rounded-full h-3">
            <div
              className={`h-3 rounded-full transition-all duration-500 ${
                job.status === 'failed'
                  ? 'bg-status-danger'
                  : job.status === 'partial_failure'
                    ? 'bg-status-warning'
                    : job.status === 'completed'
                      ? 'bg-status-success'
                      : 'bg-primary'
              }`}
              style={{ width: `${Math.max(progressPercent, 2)}%` }}
            />
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              Total
            </p>
            <p className="text-xl font-bold text-foreground">
              {job.total_organizations}
            </p>
          </div>
          <div>
            <p className="text-xs text-status-success uppercase tracking-wider">
              Imported
            </p>
            <p className="text-xl font-bold text-status-success">
              {job.imported_count}
            </p>
          </div>
          <div>
            <p className="text-xs text-status-danger uppercase tracking-wider">
              Failed
            </p>
            <p className="text-xl font-bold text-status-danger">
              {job.failed_count}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              Skipped
            </p>
            <p className="text-xl font-bold text-muted-foreground">
              {job.skipped_count}
            </p>
          </div>
        </div>

        {/* Estimated Time & Actions */}
        <div className="flex items-center justify-between pt-2 border-t border-border">
          <div className="text-sm text-muted-foreground">
            {!isTerminal && estimatedRemaining && (
              <span>Estimated remaining: {estimatedRemaining}</span>
            )}
            {isTerminal && job.completed_at && (
              <span>
                Completed: {new Date(job.completed_at).toLocaleString()}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {job.failed_count > 0 && (
              <button
                onClick={handleRetry}
                disabled={isRetrying}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-status-danger border border-status-danger/20 rounded-lg hover:bg-status-danger/10 disabled:opacity-50 transition-colors"
              >
                {isRetrying ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4" />
                )}
                Retry Failed
              </button>
            )}
            {isTerminal && (
              <Link
                href="/clients"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary-foreground bg-primary hover:bg-primary/90 rounded-lg transition-colors"
              >
                View Clients
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-xl p-4">
          <p className="text-status-danger">{error}</p>
        </div>
      )}

      {/* Per-Organization Details */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <div className="px-6 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">
            Organization Details
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted border-b border-border">
              <tr>
                <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">
                  Organization
                </th>
                <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">
                  Status
                </th>
                <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">
                  Type
                </th>
                <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">
                  Details
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {job.organizations.map((org) => {
                const config = STATUS_CONFIG[org.status] ?? STATUS_CONFIG.pending;
                const StatusIcon = config.icon;
                const isAnimating =
                  org.status === 'importing' || org.status === 'syncing';

                return (
                  <tr key={org.xero_tenant_id}>
                    <td className="px-6 py-4">
                      <p className="font-medium text-foreground">
                        {org.organization_name}
                      </p>
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}
                      >
                        <StatusIcon
                          className={`w-3.5 h-3.5 ${isAnimating ? 'animate-spin' : ''}`}
                        />
                        {config.label}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm text-muted-foreground">
                      {org.connection_type}
                    </td>
                    <td className="px-4 py-4">
                      {org.error_message && (
                        <div className="flex items-start gap-1.5">
                          <AlertCircle className="w-4 h-4 text-status-danger mt-0.5 shrink-0" />
                          <p className="text-sm text-status-danger">
                            {org.error_message}
                          </p>
                        </div>
                      )}
                      {org.sync_completed_at && (
                        <p className="text-sm text-muted-foreground">
                          {new Date(org.sync_completed_at).toLocaleTimeString()}
                        </p>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
