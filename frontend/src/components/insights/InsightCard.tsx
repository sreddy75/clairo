'use client';

import { CheckCircle2, Clock, ListPlus, XCircle } from 'lucide-react';

import type { Insight } from '@/types/insights';

import { formatDeadline, isDeadlineOverdue, isDeadlineUrgent, timeAgo } from './insights-utils';

interface InsightCardProps {
  insight: Insight;
  compact?: boolean;
  onSelect: (insight: Insight) => void;
  onAction: (insightId: string, action: 'view' | 'action' | 'dismiss') => void;
  onConvert: (insight: Insight) => void;
}

const PRIORITY_DOT: Record<string, string> = {
  high: 'bg-status-danger',
  medium: 'bg-status-warning',
  low: 'bg-primary',
};

export function InsightCard({
  insight,
  compact = false,
  onSelect,
  onAction,
  onConvert,
}: InsightCardProps) {
  const handleClick = () => {
    onSelect(insight);
    if (insight.status === 'new') {
      onAction(insight.id, 'view');
    }
  };

  // Compact mode: single-line card for "handled" section
  if (compact) {
    return (
      <div
        className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-card border border-border cursor-pointer hover:bg-muted transition-colors"
        onClick={handleClick}
      >
        <span className={`w-2 h-2 rounded-full shrink-0 ${PRIORITY_DOT[insight.priority] || 'bg-muted-foreground'}`} />
        <span className="text-sm text-foreground truncate flex-1">
          {insight.title}
        </span>
        {insight.actioned_at && (
          <span className="text-xs text-muted-foreground shrink-0">
            actioned {timeAgo(insight.actioned_at)}
          </span>
        )}
      </div>
    );
  }

  const hasDeadline = !!insight.action_deadline;
  const deadlineUrgent = hasDeadline && isDeadlineUrgent(insight.action_deadline!);
  const deadlineOverdue = hasDeadline && isDeadlineOverdue(insight.action_deadline!);
  const isNew = insight.status === 'new';
  const isActioned = insight.status === 'actioned';

  return (
    <div
      className="rounded-xl bg-card border border-border cursor-pointer hover:shadow-md transition-shadow overflow-hidden"
      onClick={handleClick}
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          {/* Left: content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              {/* Priority dot */}
              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${PRIORITY_DOT[insight.priority] || 'bg-muted-foreground'}`} />

              {/* Unread dot */}
              {isNew && (
                <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
              )}

              {/* Title */}
              <h4 className="font-medium text-foreground truncate">
                {insight.title}
              </h4>
            </div>

            {/* Summary - 1 line truncated */}
            <p className="text-sm text-muted-foreground truncate ml-[18px]">
              {insight.summary}
            </p>
          </div>

          {/* Right: inline actions */}
          <div className="flex items-center gap-1 shrink-0">
            {!isActioned && (
              <>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onAction(insight.id, 'action');
                  }}
                  className="p-1.5 rounded-md hover:bg-status-success/10 text-status-success"
                  title="Mark as done"
                >
                  <CheckCircle2 className="w-4 h-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onConvert(insight);
                  }}
                  className="p-1.5 rounded-md hover:bg-primary/10 text-primary"
                  title="Convert to task"
                >
                  <ListPlus className="w-4 h-4" />
                </button>
              </>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onAction(insight.id, 'dismiss');
              }}
              className="p-1.5 rounded-md hover:bg-muted text-muted-foreground"
              title="Dismiss"
            >
              <XCircle className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Deadline strip */}
      {deadlineUrgent && (
        <div
          className={`px-4 py-1.5 flex items-center gap-1.5 text-xs font-medium ${
            deadlineOverdue
              ? 'bg-status-danger/10 text-status-danger'
              : 'bg-status-warning/10 text-status-warning'
          }`}
        >
          <Clock className="w-3 h-3" />
          {formatDeadline(insight.action_deadline!)}
        </div>
      )}
    </div>
  );
}
