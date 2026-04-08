'use client';

import { AlertTriangle, CheckCircle2, RotateCcw, XCircle } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { retryWritebackJob, type WritebackJobDetailResponse } from '@/lib/bas';

const SKIP_LABELS: Record<string, string> = {
  voided: 'Voided in Xero',
  deleted: 'Deleted in Xero',
  period_locked: 'Period locked',
  reconciled: 'Already reconciled',
  authorised_locked: 'Invoice locked (has payments)',
  conflict_changed: 'Modified in Xero since last sync',
  credit_note_applied: 'Credit note applied',
  invalid_tax_type: 'Invalid tax code',
};

interface WritebackResultsSummaryProps {
  connectionId: string;
  sessionId: string;
  job: WritebackJobDetailResponse;
  getToken: () => Promise<string | null>;
  onRetryJobCreated: (jobId: string) => void;
}

export function WritebackResultsSummary({
  connectionId,
  sessionId,
  job,
  getToken,
  onRetryJobCreated,
}: WritebackResultsSummaryProps) {
  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      const token = await getToken();
      if (!token) return;
      const newJob = await retryWritebackJob(token, connectionId, sessionId, job.id);
      onRetryJobCreated(newJob.id);
    } finally {
      setRetrying(false);
    }
  };

  const duration = job.duration_seconds ? `${job.duration_seconds.toFixed(1)}s` : null;

  return (
    <div className="flex items-center gap-4 text-sm flex-wrap">
      <span className="font-medium text-foreground">
        {job.status === 'completed' ? 'Sync complete' : job.status === 'partial' ? 'Sync partial' : 'Sync failed'}
      </span>
      {duration && <span className="text-muted-foreground">{duration}</span>}

      <div className="flex items-center gap-1.5 text-emerald-700">
        <CheckCircle2 className="h-3.5 w-3.5" />
        <span>{job.succeeded_count} synced</span>
      </div>

      {job.skipped_count > 0 && (() => {
        const reasons = job.items
          .filter(i => i.status === 'skipped' && i.skip_reason)
          .map(i => SKIP_LABELS[i.skip_reason!] ?? i.skip_reason!);
        const unique = Array.from(new Set(reasons));
        const tooltip = unique.length > 0 ? unique.join(', ') : undefined;
        return (
          <div className="flex items-center gap-1.5 text-amber-700" title={tooltip}>
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>{job.skipped_count} skipped{tooltip ? ` — ${unique.join('; ')}` : ''}</span>
          </div>
        );
      })()}

      {job.failed_count > 0 && (() => {
        const errors = job.items
          .filter(i => i.status === 'failed')
          .map(i => (i.error_detail ?? '').trim())
          .filter(Boolean);
        const unique = Array.from(new Set(errors));
        const tooltip = unique.join('; ') || undefined;
        return (
          <div className="flex items-center gap-1.5 text-red-700" title={tooltip}>
            <XCircle className="h-3.5 w-3.5" />
            <span>{job.failed_count} failed{tooltip ? ` — ${unique.join('; ')}` : ''}</span>
          </div>
        );
      })()}

      {job.failed_count > 0 && (
        <Button
          variant="outline"
          size="sm"
          onClick={handleRetry}
          disabled={retrying}
          className="h-7 gap-1.5 text-xs ml-auto"
        >
          <RotateCcw className="h-3 w-3" />
          {retrying ? 'Retrying…' : `Retry ${job.failed_count} failed`}
        </Button>
      )}
    </div>
  );
}
