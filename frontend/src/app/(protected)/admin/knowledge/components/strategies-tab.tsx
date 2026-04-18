'use client';

/**
 * Admin Strategies tab — paginated list with status filter (Spec 060 T043).
 *
 * Row click opens the StrategyAdminDetailSheet (T044). Full filter set
 * (category, tenant, search) is scheduled for T053; Phase 1 ships with
 * status-only filtering per task description.
 */

import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { StrategyStatus } from '@/lib/api/tax-strategies';
import { cn } from '@/lib/utils';

import { useStrategyList } from '../hooks/use-tax-strategies';

import { StrategyAdminDetailSheet } from './strategy-detail-sheet';

const STATUS_FILTERS: Array<{ value: StrategyStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'stub', label: 'Stub' },
  { value: 'researching', label: 'Researching' },
  { value: 'drafted', label: 'Drafted' },
  { value: 'enriched', label: 'Enriched' },
  { value: 'in_review', label: 'In review' },
  { value: 'approved', label: 'Approved' },
  { value: 'published', label: 'Published' },
  { value: 'superseded', label: 'Superseded' },
  { value: 'archived', label: 'Archived' },
];

// Colour follows design-system semantics: green=good, amber=attention,
// neutral stone for in-progress/inactive. Colours only carry meaning
// — never decorative.
const STATUS_BADGE_CLASSES: Record<StrategyStatus, string> = {
  stub: 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
  researching:
    'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
  drafted:
    'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
  enriched:
    'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
  in_review:
    'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  approved:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
  published:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
  superseded:
    'bg-stone-100 text-stone-500 line-through dark:bg-stone-800 dark:text-stone-500',
  archived:
    'bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-500',
};

const PAGE_SIZE = 50;

function formatDate(value: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString('en-AU', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return '—';
  }
}

export function StrategiesTab() {
  const [statusFilter, setStatusFilter] = useState<StrategyStatus | 'all'>(
    'all',
  );
  const [page, setPage] = useState(1);
  const [openStrategyId, setOpenStrategyId] = useState<string | null>(null);

  const query = useStrategyList({
    status: statusFilter === 'all' ? null : statusFilter,
    page,
    page_size: PAGE_SIZE,
  });

  const total = query.data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => {
          const active = statusFilter === f.value;
          return (
            <Button
              key={f.value}
              size="sm"
              variant={active ? 'default' : 'outline'}
              onClick={() => {
                setStatusFilter(f.value);
                setPage(1);
              }}
            >
              {f.label}
            </Button>
          );
        })}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[110px]">ID</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Categories</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last reviewed</TableHead>
                <TableHead>Reviewer</TableHead>
                <TableHead className="text-right">v</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.isPending && (
                <SkeletonRows rows={8} />
              )}
              {query.isError && (
                <TableRow>
                  <TableCell colSpan={7} className="text-sm text-destructive">
                    Failed to load strategies: {query.error.message}
                  </TableCell>
                </TableRow>
              )}
              {query.data?.data.length === 0 && !query.isPending && (
                <TableRow>
                  <TableCell colSpan={7} className="text-sm text-muted-foreground">
                    No strategies match this filter.
                  </TableCell>
                </TableRow>
              )}
              {query.data?.data.map((row) => (
                <TableRow
                  key={row.strategy_id}
                  className="cursor-pointer"
                  onClick={() => setOpenStrategyId(row.strategy_id)}
                >
                  <TableCell className="font-mono text-xs">
                    {row.strategy_id}
                  </TableCell>
                  <TableCell>{row.name}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {row.categories.map((c) => (
                        <Badge
                          key={c}
                          variant="secondary"
                          className="text-[10px] font-normal"
                        >
                          {c.replace(/_/g, ' ')}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium',
                        STATUS_BADGE_CLASSES[row.status],
                      )}
                    >
                      {row.status.replace('_', ' ')}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(row.last_reviewed_at)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {row.reviewer_display_name ?? '—'}
                  </TableCell>
                  <TableCell className="text-right text-sm text-muted-foreground">
                    {row.version}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {total > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {total === 0
              ? '0 results'
              : `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} of ${total}`}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      <StrategyAdminDetailSheet
        strategyId={openStrategyId}
        open={openStrategyId !== null}
        onOpenChange={(next) => {
          if (!next) setOpenStrategyId(null);
        }}
      />
    </div>
  );
}

function SkeletonRows({ rows }: { rows: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <TableRow key={`sk-${i}`}>
          <TableCell><Skeleton className="h-4 w-16" /></TableCell>
          <TableCell><Skeleton className="h-4 w-64" /></TableCell>
          <TableCell><Skeleton className="h-4 w-32" /></TableCell>
          <TableCell><Skeleton className="h-4 w-20" /></TableCell>
          <TableCell><Skeleton className="h-4 w-20" /></TableCell>
          <TableCell><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell><Skeleton className="h-4 w-6" /></TableCell>
        </TableRow>
      ))}
    </>
  );
}
