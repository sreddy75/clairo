'use client';

import {
  AlertTriangle,
  Building2,
  Calendar,
  CheckCircle2,
  Circle,
  Clock,
  MoreHorizontal,
  PlayCircle,
  Trash2,
  User,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';

import { cn } from '@/lib/utils';
import type { ActionItem, ActionItemStatus } from '@/types/action-items';
import { PRIORITY_CONFIG, STATUS_CONFIG } from '@/types/action-items';

interface ActionItemCardProps {
  item: ActionItem;
  onStart?: (id: string) => void;
  onComplete?: (id: string, notes?: string) => void;
  onCancel?: (id: string) => void;
  onDelete?: (id: string) => void;
  onClick?: (item: ActionItem) => void;
  compact?: boolean;
}

const statusIcons: Record<ActionItemStatus, React.ReactNode> = {
  pending: <Circle className="h-4 w-4" />,
  in_progress: <PlayCircle className="h-4 w-4" />,
  completed: <CheckCircle2 className="h-4 w-4" />,
  cancelled: <XCircle className="h-4 w-4" />,
};

function formatDate(dateString: string | null): string {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
  });
}

function getDaysUntilDue(dateString: string | null): number | null {
  if (!dateString) return null;
  const due = new Date(dateString);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  due.setHours(0, 0, 0, 0);
  return Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

export function ActionItemCard({
  item,
  onStart,
  onComplete,
  onCancel,
  onDelete,
  onClick,
  compact = false,
}: ActionItemCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const priorityConfig = PRIORITY_CONFIG[item.priority];
  const statusConfig = STATUS_CONFIG[item.status];
  const daysUntilDue = getDaysUntilDue(item.due_date);

  const isActive = item.status === 'pending' || item.status === 'in_progress';

  return (
    <div
      className={cn(
        'group relative rounded-lg border bg-card transition-all duration-200',
        'hover:shadow-md',
        item.is_overdue && isActive && 'border-status-danger/30 bg-status-danger/5',
        !item.is_overdue && 'border-border',
        item.status === 'completed' && 'opacity-75',
        item.status === 'cancelled' && 'opacity-60',
        onClick && 'cursor-pointer'
      )}
      onClick={() => onClick?.(item)}
    >
      <div className={cn('p-4', compact && 'p-3')}>
        {/* Header: Priority badge + Status + Menu */}
        <div className="mb-2 flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            {/* Priority badge */}
            <span
              className={cn(
                'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                priorityConfig.bgColor,
                priorityConfig.color
              )}
            >
              {priorityConfig.label}
            </span>

            {/* Overdue warning */}
            {item.is_overdue && isActive && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-status-danger">
                <AlertTriangle className="h-3 w-3" />
                Overdue
              </span>
            )}
          </div>

          {/* Status + Menu */}
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs',
                statusConfig.bgColor,
                statusConfig.color
              )}
            >
              {statusIcons[item.status]}
              {statusConfig.label}
            </span>

            {/* Actions menu */}
            {isActive && (onStart || onComplete || onCancel || onDelete) && (
              <div className="relative">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowMenu(!showMenu);
                  }}
                  className="rounded p-1 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100"
                >
                  <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
                </button>

                {showMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowMenu(false);
                      }}
                    />
                    <div className="absolute right-0 top-full z-20 mt-1 w-40 rounded-lg border border-border bg-card py-1 shadow-lg">
                      {item.status === 'pending' && onStart && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onStart(item.id);
                            setShowMenu(false);
                          }}
                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-foreground hover:bg-muted"
                        >
                          <PlayCircle className="h-4 w-4 text-primary" />
                          Start
                        </button>
                      )}
                      {isActive && onComplete && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onComplete(item.id);
                            setShowMenu(false);
                          }}
                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-foreground hover:bg-muted"
                        >
                          <CheckCircle2 className="h-4 w-4 text-status-success" />
                          Complete
                        </button>
                      )}
                      {isActive && onCancel && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onCancel(item.id);
                            setShowMenu(false);
                          }}
                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-foreground hover:bg-muted"
                        >
                          <XCircle className="h-4 w-4 text-muted-foreground" />
                          Cancel
                        </button>
                      )}
                      {onDelete && (
                        <>
                          <div className="my-1 border-t border-border" />
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onDelete(item.id);
                              setShowMenu(false);
                            }}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-status-danger hover:bg-status-danger/10"
                          >
                            <Trash2 className="h-4 w-4" />
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Title */}
        <h3
          className={cn(
            'font-medium text-foreground',
            compact ? 'text-sm' : 'text-base',
            item.status === 'completed' && 'line-through',
            item.status === 'cancelled' && 'line-through text-muted-foreground'
          )}
        >
          {item.title}
        </h3>

        {/* Description (if not compact) */}
        {!compact && item.description && (
          <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
            {item.description}
          </p>
        )}

        {/* Meta: Client, Assignee, Due date */}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {/* Client */}
          {item.client_name && (
            <span className="inline-flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              {item.client_name}
            </span>
          )}

          {/* Assignee */}
          {item.assigned_to_name && (
            <span className="inline-flex items-center gap-1">
              <User className="h-3 w-3" />
              {item.assigned_to_name}
            </span>
          )}

          {/* Due date */}
          {item.due_date && (
            <span
              className={cn(
                'inline-flex items-center gap-1',
                item.is_overdue && isActive && 'font-medium text-status-danger',
                daysUntilDue !== null &&
                  daysUntilDue <= 3 &&
                  daysUntilDue >= 0 &&
                  isActive &&
                  'font-medium text-status-warning'
              )}
            >
              {item.is_overdue && isActive ? (
                <Clock className="h-3 w-3" />
              ) : (
                <Calendar className="h-3 w-3" />
              )}
              {formatDate(item.due_date)}
              {daysUntilDue !== null && isActive && (
                <span className="text-muted-foreground">
                  {daysUntilDue === 0
                    ? '(today)'
                    : daysUntilDue === 1
                      ? '(tomorrow)'
                      : daysUntilDue < 0
                        ? `(${Math.abs(daysUntilDue)}d ago)`
                        : `(${daysUntilDue}d)`}
                </span>
              )}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
