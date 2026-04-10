'use client';

import { formatDistanceToNow } from 'date-fns';
import {
  AlertTriangle,
  Calendar,
  ChevronRight,
  Clock,
  FileText,
  MessageSquare,
} from 'lucide-react';
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { TrackingRequestItem } from '@/lib/api/requests';
import { cn } from '@/lib/utils';

import {
  DueSoonBadge,
  OverdueBadge,
  RequestPriorityBadge,
  RequestStatusBadge,
} from './RequestStatusBadge';

interface RequestTrackingTableProps {
  requests: TrackingRequestItem[];
  className?: string;
  emptyMessage?: string;
}

export function RequestTrackingTable({
  requests,
  className,
  emptyMessage = 'No requests found',
}: RequestTrackingTableProps) {
  if (requests.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={cn('rounded-md border', className)}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Request</TableHead>
            <TableHead>Client</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Priority</TableHead>
            <TableHead>Due Date</TableHead>
            <TableHead className="text-right">Responses</TableHead>
            <TableHead className="w-[50px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {requests.map((request) => (
            <RequestRow key={request.id} request={request} />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

interface RequestRowProps {
  request: TrackingRequestItem;
}

function RequestRow({ request }: RequestRowProps) {
  const daysOverdue = request.is_overdue && request.days_until_due
    ? Math.abs(request.days_until_due)
    : 0;

  return (
    <TableRow
      className={cn(
        request.is_overdue && 'bg-red-50/50',
        request.days_until_due !== null &&
          request.days_until_due === 0 &&
          !request.is_overdue &&
          'bg-orange-50/50'
      )}
    >
      <TableCell>
        <div className="flex flex-col">
          <span className="font-medium">{request.title}</span>
          {request.sent_at && (
            <span className="text-xs text-muted-foreground">
              Sent {formatDistanceToNow(new Date(request.sent_at), { addSuffix: true })}
            </span>
          )}
        </div>
      </TableCell>
      <TableCell>
        <Link
          href={`/clients/${request.connection_id}`}
          className="text-primary hover:underline"
        >
          {request.organization_name}
        </Link>
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <RequestStatusBadge status={request.status} />
          {request.is_overdue && <OverdueBadge daysOverdue={daysOverdue} />}
          {!request.is_overdue && request.days_until_due !== null && (
            <DueSoonBadge daysUntilDue={request.days_until_due} />
          )}
        </div>
      </TableCell>
      <TableCell>
        <RequestPriorityBadge priority={request.priority} />
      </TableCell>
      <TableCell>
        {request.due_date ? (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-1 text-sm">
                  <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                  {new Date(request.due_date).toLocaleDateString()}
                </div>
              </TooltipTrigger>
              <TooltipContent>
                {request.days_until_due !== null && (
                  <span>
                    {request.is_overdue
                      ? `${daysOverdue} days overdue`
                      : request.days_until_due === 0
                        ? 'Due today'
                        : `Due in ${request.days_until_due} days`}
                  </span>
                )}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : (
          <span className="text-muted-foreground">No due date</span>
        )}
      </TableCell>
      <TableCell className="text-right">
        {request.response_count > 0 ? (
          <div className="flex items-center justify-end gap-1">
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            <span>{request.response_count}</span>
          </div>
        ) : (
          <span className="text-muted-foreground">-</span>
        )}
      </TableCell>
      <TableCell>
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/requests/${request.id}`}>
            <ChevronRight className="h-4 w-4" />
          </Link>
        </Button>
      </TableCell>
    </TableRow>
  );
}

// Summary Stats Component
interface TrackingStatsProps {
  summary: {
    total: number;
    pending: number;
    viewed: number;
    in_progress: number;
    completed: number;
    overdue: number;
    due_today: number;
    due_this_week: number;
  };
  className?: string;
}

export function TrackingStats({ summary, className }: TrackingStatsProps) {
  const stats = [
    {
      label: 'Total',
      value: summary.total,
      className: 'bg-muted',
    },
    {
      label: 'Pending',
      value: summary.pending,
      className: 'bg-amber-100 text-amber-800',
    },
    {
      label: 'Viewed',
      value: summary.viewed,
      className: 'bg-status-info/10 text-status-info',
    },
    {
      label: 'In Progress',
      value: summary.in_progress,
      className: 'bg-purple-100 text-purple-800',
    },
    {
      label: 'Completed',
      value: summary.completed,
      className: 'bg-green-100 text-green-800',
    },
  ];

  const alerts = [
    {
      label: 'Overdue',
      value: summary.overdue,
      icon: AlertTriangle,
      className: 'text-red-600',
    },
    {
      label: 'Due Today',
      value: summary.due_today,
      icon: Clock,
      className: 'text-orange-600',
    },
    {
      label: 'Due This Week',
      value: summary.due_this_week,
      icon: Calendar,
      className: 'text-amber-600',
    },
  ];

  return (
    <div className={cn('space-y-4', className)}>
      {/* Status Counts */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className={cn(
              'rounded-lg p-3 text-center',
              stat.className
            )}
          >
            <div className="text-2xl font-bold">{stat.value}</div>
            <div className="text-sm text-muted-foreground">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Alert Stats */}
      {(summary.overdue > 0 || summary.due_today > 0 || summary.due_this_week > 0) && (
        <div className="flex items-center gap-6 p-3 bg-muted/50 rounded-lg">
          {alerts.map(
            (alert) =>
              alert.value > 0 && (
                <div key={alert.label} className="flex items-center gap-2">
                  <alert.icon className={cn('h-4 w-4', alert.className)} />
                  <span className={cn('font-medium', alert.className)}>
                    {alert.value}
                  </span>
                  <span className="text-muted-foreground">{alert.label}</span>
                </div>
              )
          )}
        </div>
      )}
    </div>
  );
}

export default RequestTrackingTable;
