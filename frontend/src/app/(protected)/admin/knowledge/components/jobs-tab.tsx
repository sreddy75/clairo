'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Eye,
  Loader2,
  RefreshCw,
  RotateCcw,
  StopCircle,
  Trash2,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';

import { cancelAllJobs, deleteJob, restartJob } from '@/lib/api/knowledge';
import { JOB_STATUS_CONFIG, type JobStatus } from '@/types/knowledge';

import { useJobs } from '../hooks/use-jobs';

import { JobDetailModal } from './job-detail-modal';

const STATUS_OPTIONS: { value: JobStatus | ''; label: string }[] = [
  { value: '', label: 'All Statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
];

export function JobsTab() {
  const { getToken } = useAuth();
  const {
    jobs,
    isLoading,
    error,
    refresh,
    filter,
    setFilter,
    selectedJob,
    selectJob,
    clearSelectedJob,
    isLoadingJob,
  } = useJobs();

  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleRestart = async (jobId: string) => {
    setActionLoading(jobId);
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      await restartJob(token, jobId);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to restart job');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (jobId: string) => {
    if (!confirm('Are you sure you want to delete this job?')) return;

    setActionLoading(jobId);
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      await deleteJob(token, jobId);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete job');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancelAll = async () => {
    if (!confirm('Are you sure you want to cancel all pending and running jobs?')) return;

    setActionLoading('cancel-all');
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const result = await cancelAllJobs(token);
      await refresh();
      // Show success message briefly
      setActionError(null);
      alert(result.message);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to cancel jobs');
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusIcon = (status: JobStatus) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-status-success" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-status-danger" />;
      case 'running':
        return <Loader2 className="w-4 h-4 text-primary animate-spin" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-muted-foreground" />;
      case 'cancelled':
        return <XCircle className="w-4 h-4 text-status-warning" />;
    }
  };

  if (isLoading && jobs.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error && jobs.length === 0) {
    return (
      <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4">
        <div className="flex items-center gap-2 text-status-danger">
          <AlertCircle className="w-5 h-5" />
          <span className="font-medium">Error loading jobs</span>
        </div>
        <p className="text-status-danger text-sm mt-1">{error}</p>
        <button
          onClick={() => refresh()}
          className="mt-3 px-3 py-1.5 text-sm bg-status-danger/10 hover:bg-status-danger/20 text-status-danger rounded-md transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  const runningCount = jobs.filter((j) => j.status === 'running').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            Ingestion Jobs
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            {jobs.length} jobs{' '}
            {runningCount > 0 && (
              <span className="text-primary">
                ({runningCount} running - auto-refreshing)
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={filter.status || ''}
            onChange={(e) =>
              setFilter({
                ...filter,
                status: e.target.value as JobStatus | undefined,
              })
            }
            className="px-3 py-2 text-sm border border-border bg-card text-foreground rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            onClick={() => refresh()}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          {(jobs.some((j) => j.status === 'pending' || j.status === 'running')) && (
            <button
              onClick={handleCancelAll}
              disabled={actionLoading === 'cancel-all'}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-status-danger bg-status-danger/10 border border-status-danger/20 rounded-lg hover:bg-status-danger/20 disabled:opacity-50 transition-colors"
            >
              {actionLoading === 'cancel-all' ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <StopCircle className="w-4 h-4" />
              )}
              Cancel All
            </button>
          )}
        </div>
      </div>

      {/* Action Error Display */}
      {actionError && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-3">
          <div className="flex items-center gap-2 text-status-danger">
            <AlertCircle className="w-4 h-4" />
            <span className="text-sm">{actionError}</span>
            <button
              onClick={() => setActionError(null)}
              className="ml-auto text-status-danger hover:text-status-danger"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Jobs Table */}
      {jobs.length > 0 ? (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          <table className="w-full">
            <thead className="bg-muted border-b border-border">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Source
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Status
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Started
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Processed
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Added
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {jobs.map((job) => {
                const statusConfig = JOB_STATUS_CONFIG[job.status];
                return (
                  <tr key={job.id} className="hover:bg-muted">
                    <td className="px-4 py-3">
                      <div className="font-medium text-foreground">
                        {job.source_name}
                      </div>
                      <div className="text-xs text-muted-foreground font-mono">
                        {job.id.slice(0, 8)}...
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full ${statusConfig.bgColor} ${statusConfig.color}`}
                      >
                        {getStatusIcon(job.status)}
                        {statusConfig.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm text-muted-foreground">
                        {job.started_at
                          ? formatRelativeTime(job.started_at)
                          : 'Not started'}
                      </div>
                      {job.started_at && (
                        <div className="text-xs text-muted-foreground">
                          {formatDateTime(job.started_at)}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-medium text-foreground">
                        {job.items_processed.toLocaleString()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-medium text-status-success">
                        +{job.items_added.toLocaleString()}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => selectJob(job.id)}
                          className="p-1.5 text-muted-foreground hover:bg-muted rounded-md transition-colors"
                          title="View Details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {(job.status === 'failed' || job.status === 'completed' || job.status === 'cancelled') && (
                          <button
                            onClick={() => handleRestart(job.id)}
                            disabled={actionLoading === job.id}
                            className="p-1.5 text-primary hover:bg-primary/10 rounded-md transition-colors disabled:opacity-50"
                            title="Restart Job"
                          >
                            {actionLoading === job.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <RotateCcw className="w-4 h-4" />
                            )}
                          </button>
                        )}
                        {job.status !== 'running' && (
                          <button
                            onClick={() => handleDelete(job.id)}
                            disabled={actionLoading === job.id}
                            className="p-1.5 text-status-danger hover:bg-status-danger/10 rounded-md transition-colors disabled:opacity-50"
                            title="Delete Job"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-12 bg-muted rounded-lg border border-dashed border-border">
          <Clock className="w-12 h-12 text-muted-foreground mx-auto" />
          <h3 className="mt-4 text-lg font-medium text-foreground">
            No jobs found
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            {filter.status
              ? `No ${filter.status} jobs. Try changing the filter.`
              : 'Trigger an ingestion from the Sources tab to create a job.'}
          </p>
        </div>
      )}

      {/* Job Detail Modal */}
      <JobDetailModal
        job={selectedJob}
        isLoading={isLoadingJob}
        onClose={clearSelectedJob}
      />
    </div>
  );
}

function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleString('en-AU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDateTime(dateString);
}
