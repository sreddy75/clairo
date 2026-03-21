import type { Insight, InsightPriority } from '@/types/insights';

export type Bucket = 'urgent' | 'review' | 'later' | 'handled';

export interface BucketCounts {
  total: number;
  urgent: number;
  newCount: number;
  actioned: number;
  overdue: number;
}

/**
 * Determine which triage bucket an insight belongs to.
 *
 * - **urgent**: deadline within 7 days (any priority), OR high priority + new/viewed
 * - **review**: status=new not already urgent, OR medium + viewed
 * - **later**: low priority viewed items
 * - **handled**: status=actioned
 * - Skip dismissed/resolved/expired entirely (caller should pre-filter)
 */
export function assignBucket(insight: Insight): Bucket | null {
  const { status, priority, action_deadline } = insight;

  // Skip non-active statuses
  if (status === 'dismissed' || status === 'resolved' || status === 'expired') {
    return null;
  }

  if (status === 'actioned') {
    return 'handled';
  }

  const deadlineUrgent = action_deadline ? isDeadlineUrgent(action_deadline) : false;

  // Urgent: deadline within 7 days OR high priority + active
  if (deadlineUrgent || (priority === 'high' && (status === 'new' || status === 'viewed'))) {
    return 'urgent';
  }

  // Review: new items (not already urgent) or medium + viewed
  if (status === 'new' || (priority === 'medium' && status === 'viewed')) {
    return 'review';
  }

  // Later: low priority viewed
  if (priority === 'low' && status === 'viewed') {
    return 'later';
  }

  // Fallback: anything viewed that didn't match above goes to review
  if (status === 'viewed') {
    return 'review';
  }

  return 'review';
}

const PRIORITY_ORDER: Record<InsightPriority, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

/**
 * Group insights into triage buckets with proper sorting within each bucket.
 */
export function groupIntoBuckets(insights: Insight[]): Map<Bucket, Insight[]> {
  const buckets = new Map<Bucket, Insight[]>([
    ['urgent', []],
    ['review', []],
    ['later', []],
    ['handled', []],
  ]);

  for (const insight of insights) {
    const bucket = assignBucket(insight);
    if (bucket) {
      buckets.get(bucket)!.push(insight);
    }
  }

  // Sort urgent: overdue first, then by days-to-deadline ascending
  buckets.get('urgent')!.sort((a, b) => {
    const aOverdue = a.action_deadline ? isDeadlineOverdue(a.action_deadline) : false;
    const bOverdue = b.action_deadline ? isDeadlineOverdue(b.action_deadline) : false;
    if (aOverdue !== bOverdue) return aOverdue ? -1 : 1;

    const aDays = a.action_deadline ? daysUntilDeadline(a.action_deadline) : Infinity;
    const bDays = b.action_deadline ? daysUntilDeadline(b.action_deadline) : Infinity;
    if (aDays !== bDays) return aDays - bDays;

    return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
  });

  // Sort review/later: high -> medium -> low, then newest first
  const sortByPriorityThenDate = (a: Insight, b: Insight) => {
    const pDiff = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
    if (pDiff !== 0) return pDiff;
    return new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime();
  };

  buckets.get('review')!.sort(sortByPriorityThenDate);
  buckets.get('later')!.sort(sortByPriorityThenDate);

  // Sort handled: most recently actioned first
  buckets.get('handled')!.sort((a, b) => {
    const aTime = a.actioned_at ? new Date(a.actioned_at).getTime() : 0;
    const bTime = b.actioned_at ? new Date(b.actioned_at).getTime() : 0;
    return bTime - aTime;
  });

  return buckets;
}

/**
 * Compute summary counts for the summary bar.
 */
export function computeCounts(insights: Insight[]): BucketCounts {
  const buckets = groupIntoBuckets(insights);
  const urgentItems = buckets.get('urgent') || [];

  return {
    total: insights.filter(i => !['dismissed', 'resolved', 'expired'].includes(i.status)).length,
    urgent: urgentItems.length,
    newCount: insights.filter(i => i.status === 'new').length,
    actioned: insights.filter(i => i.status === 'actioned').length,
    overdue: urgentItems.filter(i => i.action_deadline && isDeadlineOverdue(i.action_deadline)).length,
  };
}

function daysUntilDeadline(deadline: string): number {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const dl = new Date(deadline);
  dl.setHours(0, 0, 0, 0);
  return Math.ceil((dl.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

export function isDeadlineUrgent(deadline: string): boolean {
  return daysUntilDeadline(deadline) <= 7;
}

export function isDeadlineOverdue(deadline: string): boolean {
  return daysUntilDeadline(deadline) < 0;
}

/**
 * Human-friendly deadline string.
 * - "2d overdue" / "Due today" / "3 days left" / "28 Feb"
 */
export function formatDeadline(deadline: string): string {
  const days = daysUntilDeadline(deadline);

  if (days < -1) return `${Math.abs(days)}d overdue`;
  if (days === -1) return '1d overdue';
  if (days === 0) return 'Due today';
  if (days === 1) return '1 day left';
  if (days <= 7) return `${days} days left`;

  return new Date(deadline).toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
  });
}

/**
 * Relative time since a date (for "actioned 2d ago" labels).
 */
export function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return '1d ago';
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' });
}
