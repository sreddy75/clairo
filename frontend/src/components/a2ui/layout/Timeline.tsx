'use client';

/**
 * A2UI Timeline Component
 * Displays a vertical timeline of events
 */

import { Check, Circle, Clock } from 'lucide-react';

import type { TimelineItem, TimelineProps } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

interface A2UITimelineProps extends TimelineProps {
  id: string;
  dataBinding?: string;
}

// =============================================================================
// Helpers
// =============================================================================

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffHours < 1) {
    return 'Just now';
  } else if (diffHours < 24) {
    return `${diffHours}h ago`;
  } else if (diffDays < 7) {
    return `${diffDays}d ago`;
  } else {
    return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' });
  }
}

function getStatusIcon(status?: TimelineItem['status']) {
  switch (status) {
    case 'completed':
      return Check;
    case 'current':
      return Circle;
    case 'upcoming':
    default:
      return Clock;
  }
}

function getStatusStyles(status?: TimelineItem['status']) {
  switch (status) {
    case 'completed':
      return {
        icon: 'bg-status-success text-white',
        line: 'bg-status-success',
        text: 'text-muted-foreground',
      };
    case 'current':
      return {
        icon: 'bg-primary text-white ring-4 ring-primary/20',
        line: 'bg-border',
        text: 'text-foreground font-medium',
      };
    case 'upcoming':
    default:
      return {
        icon: 'bg-muted text-muted-foreground',
        line: 'bg-border',
        text: 'text-muted-foreground',
      };
  }
}

// =============================================================================
// Component
// =============================================================================

export function Timeline({ id, items }: A2UITimelineProps) {
  if (!items?.length) {
    return null;
  }

  return (
    <div id={id} className="relative space-y-0" role="list">
      {items.map((item, index) => {
        const Icon = getStatusIcon(item.status);
        const styles = getStatusStyles(item.status);
        const isLast = index === items.length - 1;

        return (
          <div
            key={item.id}
            className="relative flex gap-4 pb-8"
            role="listitem"
          >
            {/* Vertical line */}
            {!isLast && (
              <div
                className={cn(
                  'absolute left-[17px] top-10 h-[calc(100%-32px)] w-0.5',
                  styles.line
                )}
                aria-hidden="true"
              />
            )}

            {/* Icon */}
            <div
              className={cn(
                'relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full',
                styles.icon
              )}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
            </div>

            {/* Content */}
            <div className="flex-1 pt-1.5">
              <div className="flex items-center justify-between gap-2">
                <h4 className={cn('text-sm', styles.text)}>{item.title}</h4>
                <time
                  className="text-xs text-muted-foreground"
                  dateTime={item.timestamp}
                >
                  {formatTimestamp(item.timestamp)}
                </time>
              </div>
              {item.description && (
                <p className="mt-1 text-sm text-muted-foreground">
                  {item.description}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
