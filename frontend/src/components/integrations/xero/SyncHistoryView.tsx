'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Loader2,
  XCircle,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import type { XeroSyncJob, XeroSyncStatus } from '@/lib/xero-sync';
import {
  formatRelativeTime,
  getStatusColor,
  getSyncHistory,
  getSyncTypeName,
} from '@/lib/xero-sync';

interface SyncHistoryViewProps {
  connectionId: string;
  pageSize?: number;
}

export function SyncHistoryView({
  connectionId,
  pageSize = 10,
}: SyncHistoryViewProps) {
  const { getToken } = useAuth();
  const [jobs, setJobs] = useState<XeroSyncJob[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) return;

      const response = await getSyncHistory(
        token,
        connectionId,
        pageSize,
        page * pageSize
      );

      setJobs(response.jobs);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sync history');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, connectionId, pageSize, page]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const totalPages = Math.ceil(total / pageSize);

  const getStatusIcon = (status: XeroSyncStatus) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4" />;
      case 'in_progress':
        return <Loader2 className="w-4 h-4 animate-spin" />;
      case 'completed':
        return <CheckCircle2 className="w-4 h-4" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4" />;
      case 'cancelled':
        return <XCircle className="w-4 h-4" />;
    }
  };

  const formatDuration = (startedAt: string | null, completedAt: string | null) => {
    if (!startedAt) return '-';
    if (!completedAt) return 'In progress';

    const start = new Date(startedAt);
    const end = new Date(completedAt);
    const durationMs = end.getTime() - start.getTime();
    const seconds = Math.floor(durationMs / 1000);

    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  if (isLoading && jobs.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <AlertCircle className="w-8 h-8 text-status-danger mx-auto mb-2" />
        <p className="text-destructive">{error}</p>
        <Button
          variant="link"
          onClick={fetchHistory}
          className="mt-3 text-sm text-primary"
        >
          Try again
        </Button>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="text-center py-8">
        <Clock className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
        <p className="text-foreground">No sync history yet</p>
        <p className="text-sm text-muted-foreground">
          Sync your data to see history here
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="overflow-hidden bg-card border border-border rounded-lg">
        <table className="min-w-full divide-y divide-border">
          <thead className="bg-muted">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">
                Type
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">
                Started
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">
                Duration
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase">
                Records
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {jobs.map((job) => (
              <tr key={job.id} className="hover:bg-muted/50">
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className="text-sm font-medium text-foreground">
                    {getSyncTypeName(job.sync_type)}
                  </span>
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span
                    className={`inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(
                      job.status
                    )}`}
                  >
                    {getStatusIcon(job.status)}
                    <span className="capitalize">{job.status.replace('_', ' ')}</span>
                  </span>
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground">
                  {formatRelativeTime(job.started_at || job.created_at)}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground tabular-nums">
                  {formatDuration(job.started_at, job.completed_at)}
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-right">
                  <div className="text-sm">
                    <span className="text-foreground tabular-nums">{job.records_processed}</span>
                    {job.records_failed > 0 && (
                      <span className="text-destructive ml-1 tabular-nums">
                        ({job.records_failed} failed)
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground tabular-nums">
                    {job.records_created} new, {job.records_updated} updated
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {page * pageSize + 1} to{' '}
            {Math.min((page + 1) * pageSize, total)} of {total} syncs
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="w-5 h-5" />
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page + 1} of {totalPages}
            </span>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
            >
              <ChevronRight className="w-5 h-5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default SyncHistoryView;
