'use client';

import { Badge } from '@/components/ui/badge';
import type { RequestStatus } from '@/lib/api/requests';
import { cn } from '@/lib/utils';

interface RequestStatusBadgeProps {
  status: RequestStatus;
  className?: string;
}

const statusConfig: Record<
  RequestStatus,
  { label: string; variant: 'default' | 'secondary' | 'outline' | 'destructive'; className: string }
> = {
  draft: {
    label: 'Draft',
    variant: 'secondary',
    className: 'bg-stone-100 text-stone-700 hover:bg-stone-100 dark:bg-stone-800 dark:text-stone-300',
  },
  pending: {
    label: 'Pending',
    variant: 'default',
    className: 'bg-amber-100 text-amber-800 hover:bg-amber-100 dark:bg-amber-500/10 dark:text-amber-400',
  },
  viewed: {
    label: 'Viewed',
    variant: 'default',
    className: 'bg-sky-100 text-sky-800 hover:bg-sky-100 dark:bg-sky-500/10 dark:text-sky-400',
  },
  in_progress: {
    label: 'In Progress',
    variant: 'default',
    className: 'bg-violet-100 text-violet-800 hover:bg-violet-100 dark:bg-violet-500/10 dark:text-violet-400',
  },
  complete: {
    label: 'Complete',
    variant: 'default',
    className: 'bg-emerald-100 text-emerald-800 hover:bg-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-400',
  },
  cancelled: {
    label: 'Cancelled',
    variant: 'secondary',
    className: 'bg-red-100 text-red-800 hover:bg-red-100 dark:bg-red-500/10 dark:text-red-400',
  },
};

export function RequestStatusBadge({ status, className }: RequestStatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.pending;

  return (
    <Badge
      variant={config.variant}
      className={cn(config.className, className)}
    >
      {config.label}
    </Badge>
  );
}

// Priority Badge
interface RequestPriorityBadgeProps {
  priority: 'low' | 'normal' | 'high' | 'urgent';
  className?: string;
}

const priorityConfig: Record<
  string,
  { label: string; className: string }
> = {
  low: {
    label: 'Low',
    className: 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400',
  },
  normal: {
    label: 'Normal',
    className: 'bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400',
  },
  high: {
    label: 'High',
    className: 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400',
  },
  urgent: {
    label: 'Urgent',
    className: 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400',
  },
};

export function RequestPriorityBadge({ priority, className }: RequestPriorityBadgeProps) {
  const config = priorityConfig[priority] ?? priorityConfig['normal'];
  const finalConfig = config ?? { label: 'Normal', className: 'bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400' };

  return (
    <Badge variant="outline" className={cn(finalConfig.className, className)}>
      {finalConfig.label}
    </Badge>
  );
}

// Overdue Badge
interface OverdueBadgeProps {
  daysOverdue: number;
  className?: string;
}

export function OverdueBadge({ daysOverdue, className }: OverdueBadgeProps) {
  return (
    <Badge
      variant="destructive"
      className={cn(className)}
    >
      {daysOverdue === 1 ? '1 day overdue' : `${daysOverdue} days overdue`}
    </Badge>
  );
}

// Due Soon Badge
interface DueSoonBadgeProps {
  daysUntilDue: number;
  className?: string;
}

export function DueSoonBadge({ daysUntilDue, className }: DueSoonBadgeProps) {
  if (daysUntilDue === 0) {
    return (
      <Badge
        variant="outline"
        className={cn('border-amber-500 text-amber-600 dark:text-amber-400', className)}
      >
        Due Today
      </Badge>
    );
  }

  if (daysUntilDue <= 3) {
    return (
      <Badge
        variant="outline"
        className={cn('border-amber-500 text-amber-600 dark:text-amber-400', className)}
      >
        Due in {daysUntilDue} {daysUntilDue === 1 ? 'day' : 'days'}
      </Badge>
    );
  }

  return null;
}

export default RequestStatusBadge;
