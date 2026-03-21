'use client';

import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  X,
  XCircle,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { JOB_STATUS_CONFIG, type IngestionJob } from '@/types/knowledge';

interface JobDetailModalProps {
  job: IngestionJob | null;
  isLoading: boolean;
  onClose: () => void;
}

export function JobDetailModal({ job, isLoading, onClose }: JobDetailModalProps) {
  if (!job && !isLoading) return null;

  const statusConfig = job ? JOB_STATUS_CONFIG[job.status] : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative bg-card rounded-2xl shadow-lg w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden border border-border">
        {/* Header */}
        <div className="px-6 py-4 bg-muted border-b border-border">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">
              Job Details
            </h2>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
              <X className="w-5 h-5" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          ) : job ? (
            <div className="space-y-6">
              {/* Status and ID */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {job.status === 'completed' && (
                    <CheckCircle2 className="w-6 h-6 text-status-success" />
                  )}
                  {job.status === 'failed' && (
                    <XCircle className="w-6 h-6 text-status-danger" />
                  )}
                  {job.status === 'running' && (
                    <Loader2 className="w-6 h-6 text-status-info animate-spin" />
                  )}
                  {job.status === 'pending' && (
                    <Clock className="w-6 h-6 text-status-neutral" />
                  )}
                  <span
                    className={cn('px-3 py-1 text-sm font-medium rounded-full', statusConfig?.bgColor, statusConfig?.color)}
                  >
                    {statusConfig?.label}
                  </span>
                </div>
                <span className="text-sm text-muted-foreground font-mono">
                  {job.id.slice(0, 8)}...
                </span>
              </div>

              {/* Timestamps */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-muted rounded-lg p-4">
                  <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">
                    Started At
                  </div>
                  <div className="text-sm text-foreground">
                    {job.started_at
                      ? formatDateTime(job.started_at)
                      : 'Not started'}
                  </div>
                </div>
                <div className="bg-muted rounded-lg p-4">
                  <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1">
                    Completed At
                  </div>
                  <div className="text-sm text-foreground">
                    {job.completed_at
                      ? formatDateTime(job.completed_at)
                      : 'In progress'}
                  </div>
                </div>
              </div>

              {/* Duration */}
              {job.duration_seconds !== null && (
                <div className="bg-primary/5 rounded-lg p-4">
                  <div className="text-xs font-medium uppercase tracking-wide text-primary mb-1">
                    Duration
                  </div>
                  <div className="text-lg font-semibold text-foreground tabular-nums">
                    {formatDuration(job.duration_seconds)}
                  </div>
                </div>
              )}

              {/* Statistics */}
              <div>
                <h3 className="text-sm font-semibold text-foreground mb-3">
                  Processing Statistics
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <StatCard label="Processed" value={job.items_processed} color="neutral" />
                  <StatCard label="Added" value={job.items_added} color="success" />
                  <StatCard label="Updated" value={job.items_updated} color="info" />
                  <StatCard label="Skipped" value={job.items_skipped} color="warning" />
                  <StatCard label="Failed" value={job.items_failed} color="danger" />
                  <StatCard label="Tokens Used" value={job.tokens_used.toLocaleString()} color="neutral" />
                </div>
              </div>

              {/* Success Rate */}
              {job.items_processed > 0 && (
                <div className="bg-muted rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-muted-foreground">
                      Success Rate
                    </span>
                    <span className="text-sm font-semibold text-foreground tabular-nums">
                      {(job.success_rate * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-border rounded-full h-2">
                    <div
                      className={cn(
                        'h-2 rounded-full transition-all',
                        job.success_rate >= 0.9
                          ? 'bg-status-success'
                          : job.success_rate >= 0.7
                          ? 'bg-status-warning'
                          : 'bg-status-danger'
                      )}
                      style={{ width: `${job.success_rate * 100}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Errors */}
              {job.errors.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-status-danger" />
                    Errors ({job.errors.length})
                  </h3>
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {job.errors.map((error, index) => (
                      <div
                        key={index}
                        className="bg-destructive/5 border border-destructive/20 rounded-lg p-3"
                      >
                        {error.url && (
                          <div className="text-xs text-destructive font-mono mb-1 truncate">
                            {error.url}
                          </div>
                        )}
                        <div className="text-sm text-destructive">{error.error}</div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {formatDateTime(error.timestamp)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Metadata */}
              <div className="text-xs text-muted-foreground pt-4 border-t border-border">
                <div>Triggered by: {job.triggered_by}</div>
                <div>Created: {formatDateTime(job.created_at)}</div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-muted border-t border-border flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number | string;
  color: 'success' | 'info' | 'warning' | 'danger' | 'neutral';
}) {
  const colorClasses = {
    success: 'bg-status-success/10 text-status-success',
    info: 'bg-status-info/10 text-status-info',
    warning: 'bg-status-warning/10 text-status-warning',
    danger: 'bg-status-danger/10 text-status-danger',
    neutral: 'bg-muted text-foreground',
  };

  return (
    <div className={cn('rounded-lg p-3', colorClasses[color])}>
      <div className="text-xs font-medium opacity-70">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  if (minutes < 60) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}
