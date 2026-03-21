'use client';

import { Lightbulb, Bug, MessageSquare } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { formatRelativeTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { FeedbackSubmission, Severity } from '@/types/feedback';

interface FeedbackCardProps {
  submission: FeedbackSubmission;
  onClick: (submission: FeedbackSubmission) => void;
  dragAttributes?: Record<string, unknown>;
  dragListeners?: Record<string, unknown>;
  style?: React.CSSProperties;
}

const typeConfig = {
  feature_request: {
    label: 'Feature',
    icon: Lightbulb,
    className: 'bg-primary/15 text-primary border-primary/20',
  },
  bug_enhancement: {
    label: 'Bug',
    icon: Bug,
    className: 'bg-blue-500/15 text-blue-700 border-blue-500/20',
  },
} as const;

const severityConfig: Record<Severity, string> = {
  low: 'bg-stone-100 text-stone-700 border-stone-200',
  medium: 'bg-amber-100 text-amber-700 border-amber-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  critical: 'bg-red-100 text-red-700 border-red-200',
};

export function FeedbackCard({
  submission,
  onClick,
  dragAttributes,
  dragListeners,
  style,
}: FeedbackCardProps) {
  const type = typeConfig[submission.type];
  const TypeIcon = type.icon;

  return (
    <Card
      className={cn(
        'p-3 cursor-pointer hover:shadow-md transition-shadow border'
      )}
      style={style}
      onClick={() => onClick(submission)}
      {...dragAttributes}
      {...dragListeners}
    >
      <div className="space-y-2">
        {/* Title */}
        <p
          className={cn(
            'text-sm font-medium leading-tight',
            !submission.title && 'text-muted-foreground italic'
          )}
        >
          {submission.title ?? 'Untitled draft'}
        </p>

        {/* Badges row */}
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="outline" className={cn('gap-1 text-xs', type.className)}>
            <TypeIcon className="size-3" />
            {type.label}
          </Badge>
          {submission.severity && (
            <Badge
              variant="outline"
              className={cn('text-xs', severityConfig[submission.severity])}
            >
              {submission.severity}
            </Badge>
          )}
        </div>

        {/* Footer: submitter, time, conversation status */}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="truncate">{submission.submitter_name}</span>
          <span className="tabular-nums">
            {formatRelativeTime(submission.created_at)}
          </span>
        </div>

        {/* Conversation indicator */}
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <MessageSquare className="size-3" />
          <span>{submission.conversation_complete ? 'Complete' : 'Draft'}</span>
        </div>
      </div>
    </Card>
  );
}
