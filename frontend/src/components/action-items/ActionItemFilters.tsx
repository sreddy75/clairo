'use client';

import { Check, ChevronDown, Filter, X } from 'lucide-react';
import { useState } from 'react';

import { cn } from '@/lib/utils';
import type { ActionItemPriority, ActionItemStatus } from '@/types/action-items';
import { PRIORITY_CONFIG, STATUS_CONFIG } from '@/types/action-items';

export interface ActionItemFilters {
  status: ActionItemStatus[];
  priority: ActionItemPriority[];
  includeCompleted: boolean;
}

interface ActionItemFiltersProps {
  filters: ActionItemFilters;
  onChange: (filters: ActionItemFilters) => void;
}

const priorities: ActionItemPriority[] = ['urgent', 'high', 'medium', 'low'];
const statuses: ActionItemStatus[] = ['pending', 'in_progress', 'completed', 'cancelled'];

export function ActionItemFiltersBar({ filters, onChange }: ActionItemFiltersProps) {
  const [openDropdown, setOpenDropdown] = useState<'status' | 'priority' | null>(null);

  const hasActiveFilters =
    filters.status.length > 0 ||
    filters.priority.length > 0 ||
    filters.includeCompleted;

  const toggleStatus = (status: ActionItemStatus) => {
    const newStatuses = filters.status.includes(status)
      ? filters.status.filter((s) => s !== status)
      : [...filters.status, status];
    onChange({ ...filters, status: newStatuses });
  };

  const togglePriority = (priority: ActionItemPriority) => {
    const newPriorities = filters.priority.includes(priority)
      ? filters.priority.filter((p) => p !== priority)
      : [...filters.priority, priority];
    onChange({ ...filters, priority: newPriorities });
  };

  const clearFilters = () => {
    onChange({ status: [], priority: [], includeCompleted: false });
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Filter className="h-4 w-4 text-muted-foreground" />

      {/* Status filter */}
      <div className="relative">
        <button
          onClick={() => setOpenDropdown(openDropdown === 'status' ? null : 'status')}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition-colors',
            filters.status.length > 0
              ? 'border-primary/30 bg-primary/10 text-primary'
              : 'border-border bg-card text-foreground hover:bg-muted'
          )}
        >
          Status
          {filters.status.length > 0 && (
            <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground">
              {filters.status.length}
            </span>
          )}
          <ChevronDown className="h-3.5 w-3.5" />
        </button>

        {openDropdown === 'status' && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setOpenDropdown(null)}
            />
            <div className="absolute left-0 top-full z-20 mt-1 w-48 rounded-lg border border-border bg-card py-1 shadow-lg">
              {statuses.map((status) => {
                const config = STATUS_CONFIG[status];
                const isSelected = filters.status.includes(status);
                return (
                  <button
                    key={status}
                    onClick={() => toggleStatus(status)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-foreground hover:bg-muted"
                  >
                    <span
                      className={cn(
                        'flex h-4 w-4 items-center justify-center rounded border',
                        isSelected
                          ? 'border-primary bg-primary'
                          : 'border-border'
                      )}
                    >
                      {isSelected && <Check className="h-3 w-3 text-white" />}
                    </span>
                    <span
                      className={cn(
                        'rounded-full px-2 py-0.5 text-xs',
                        config.bgColor,
                        config.color
                      )}
                    >
                      {config.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Priority filter */}
      <div className="relative">
        <button
          onClick={() => setOpenDropdown(openDropdown === 'priority' ? null : 'priority')}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition-colors',
            filters.priority.length > 0
              ? 'border-primary/30 bg-primary/10 text-primary'
              : 'border-border bg-card text-foreground hover:bg-muted'
          )}
        >
          Priority
          {filters.priority.length > 0 && (
            <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground">
              {filters.priority.length}
            </span>
          )}
          <ChevronDown className="h-3.5 w-3.5" />
        </button>

        {openDropdown === 'priority' && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setOpenDropdown(null)}
            />
            <div className="absolute left-0 top-full z-20 mt-1 w-48 rounded-lg border border-border bg-card py-1 shadow-lg">
              {priorities.map((priority) => {
                const config = PRIORITY_CONFIG[priority];
                const isSelected = filters.priority.includes(priority);
                return (
                  <button
                    key={priority}
                    onClick={() => togglePriority(priority)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-foreground hover:bg-muted"
                  >
                    <span
                      className={cn(
                        'flex h-4 w-4 items-center justify-center rounded border',
                        isSelected
                          ? 'border-primary bg-primary'
                          : 'border-border'
                      )}
                    >
                      {isSelected && <Check className="h-3 w-3 text-white" />}
                    </span>
                    <span
                      className={cn(
                        'rounded-full px-2 py-0.5 text-xs',
                        config.bgColor,
                        config.color
                      )}
                    >
                      {config.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Include completed toggle */}
      <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-foreground">
        <input
          type="checkbox"
          checked={filters.includeCompleted}
          onChange={(e) => onChange({ ...filters, includeCompleted: e.target.checked })}
          className="h-4 w-4 rounded border-border text-primary focus:ring-primary/20 bg-card"
        />
        Show completed
      </label>

      {/* Clear filters */}
      {hasActiveFilters && (
        <button
          onClick={clearFilters}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <X className="h-3.5 w-3.5" />
          Clear
        </button>
      )}
    </div>
  );
}

// Quick filter tabs component
interface QuickFilterTabsProps {
  activeTab: 'all' | 'urgent' | 'overdue' | 'mine';
  onChange: (tab: 'all' | 'urgent' | 'overdue' | 'mine') => void;
  counts?: {
    all?: number;
    urgent?: number;
    overdue?: number;
    mine?: number;
  };
}

export function QuickFilterTabs({ activeTab, onChange, counts }: QuickFilterTabsProps) {
  const tabs = [
    { id: 'all' as const, label: 'All Tasks', count: counts?.all },
    { id: 'urgent' as const, label: 'Urgent', count: counts?.urgent },
    { id: 'overdue' as const, label: 'Overdue', count: counts?.overdue },
    { id: 'mine' as const, label: 'Assigned to Me', count: counts?.mine },
  ];

  return (
    <div className="flex gap-1 rounded-lg bg-muted p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
            activeTab === tab.id
              ? 'bg-card text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          {tab.label}
          {tab.count !== undefined && tab.count > 0 && (
            <span
              className={cn(
                'rounded-full px-1.5 text-xs',
                activeTab === tab.id
                  ? 'bg-muted text-foreground'
                  : 'bg-muted/70 text-muted-foreground'
              )}
            >
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
