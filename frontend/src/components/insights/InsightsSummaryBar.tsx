'use client';

import { Badge } from '@/components/ui/badge';

import type { BucketCounts } from './insights-utils';

interface InsightsSummaryBarProps {
  counts: BucketCounts;
}

export function InsightsSummaryBar({ counts }: InsightsSummaryBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {/* Urgent pill */}
      <Badge
        className={
          counts.urgent > 0
            ? 'bg-status-danger/10 text-status-danger border-status-danger/20'
            : 'bg-muted text-muted-foreground border-border'
        }
      >
        {counts.urgent} urgent
        {counts.overdue > 0 && (
          <span className="ml-1 text-status-danger">
            ({counts.overdue} overdue)
          </span>
        )}
      </Badge>

      <span className="text-muted-foreground">&middot;</span>

      {/* New pill */}
      <Badge
        className={
          counts.newCount > 0
            ? 'bg-primary/10 text-primary border-primary/20'
            : 'bg-muted text-muted-foreground border-border'
        }
      >
        {counts.newCount} new
      </Badge>

      <span className="text-muted-foreground">&middot;</span>

      {/* Actioned pill */}
      <Badge className="bg-status-success/10 text-status-success border-status-success/20">
        {counts.actioned} actioned
      </Badge>

      <span className="text-muted-foreground">&middot;</span>

      {/* Total */}
      <span className="text-muted-foreground font-medium">
        {counts.total} total
      </span>
    </div>
  );
}
