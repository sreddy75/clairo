'use client';

import { useEffect, useRef, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { getWritebackJob, type WritebackJobDetailResponse } from '@/lib/bas';

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

interface WritebackProgressPanelProps {
  connectionId: string;
  sessionId: string;
  jobId: string;
  getToken: () => Promise<string | null>;
  onJobComplete: (job: WritebackJobDetailResponse) => void;
}

export function WritebackProgressPanel({
  connectionId,
  sessionId,
  jobId,
  getToken,
  onJobComplete,
}: WritebackProgressPanelProps) {
  const [job, setJob] = useState<WritebackJobDetailResponse | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    let active = true;

    async function poll() {
      const token = await getToken();
      if (!token || !active) return;
      try {
        const data = await getWritebackJob(token, connectionId, sessionId, jobId);
        if (!active) return;
        setJob(data);
        if (data.status !== 'in_progress' && data.status !== 'pending') {
          if (intervalRef.current) clearInterval(intervalRef.current);
          onJobComplete(data);
        }
      } catch {
        // silently ignore transient errors
      }
    }

    poll();
    intervalRef.current = setInterval(poll, 2000);

    return () => {
      active = false;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [connectionId, sessionId, jobId, getToken, onJobComplete]);

  if (!job) {
    return (
      <Card>
        <CardContent className="p-4 flex items-center gap-3">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span className="text-sm text-muted-foreground">Starting Xero sync…</span>
        </CardContent>
      </Card>
    );
  }

  const processed = job.succeeded_count + job.skipped_count + job.failed_count;
  const progressPercent = job.total_count > 0 ? Math.round((processed / job.total_count) * 100) : 0;

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">Syncing to Xero…</span>
          <span className="text-muted-foreground tabular-nums">
            {processed} of {job.total_count}
          </span>
        </div>
        <Progress value={progressPercent} className="h-2" />
        {job.items.length > 0 && (
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {job.items.map((item) => (
              <div key={item.id} className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground truncate max-w-[200px]">
                  {item.source_type} · {item.xero_document_id.slice(0, 8)}…
                </span>
                {item.status === 'pending' && (
                  <Badge variant="outline" className="text-xs">pending</Badge>
                )}
                {item.status === 'success' && (
                  <Badge className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200">synced</Badge>
                )}
                {item.status === 'skipped' && (
                  <Badge className="text-xs bg-amber-100 text-amber-700 border-amber-200" title={SKIP_LABELS[item.skip_reason ?? ''] ?? item.skip_reason ?? 'skipped'}>
                    {SKIP_LABELS[item.skip_reason ?? ''] ?? 'skipped'}
                  </Badge>
                )}
                {item.status === 'failed' && (
                  <Badge className="text-xs bg-red-100 text-red-700 border-red-200" title={item.error_detail ?? 'failed'}>
                    {item.error_detail ? item.error_detail.slice(0, 60) : 'failed'}
                  </Badge>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
