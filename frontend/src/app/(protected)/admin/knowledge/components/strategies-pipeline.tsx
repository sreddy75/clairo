'use client';

/**
 * Kanban pipeline view for the Strategies admin tab (Spec 060 T055).
 *
 * Columns correspond to every lifecycle status except the terminal
 * superseded/archived (those clutter the board without adding value).
 * The `in_review` column is visually emphasised — it's the reviewer's
 * queue, and Acceptance Scenario 4 specifically calls it out.
 *
 * Card click defers to the parent (list Tab) so the same admin detail
 * Sheet drives actions in both views.
 */

import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import type {
  StrategyStatus,
  TaxStrategyListItem,
} from '@/lib/api/tax-strategies';
import { cn } from '@/lib/utils';

import { useStrategyList } from '../hooks/use-tax-strategies';

interface Props {
  onRowClick: (strategyId: string) => void;
}

// Columns kept in pipeline order so the reader's eye tracks work-in-flight
// left-to-right. Terminal states (superseded/archived) are elided.
const COLUMNS: Array<{
  status: StrategyStatus;
  label: string;
  accent?: 'in_review' | 'published';
}> = [
  { status: 'stub', label: 'Stub' },
  { status: 'researching', label: 'Researching' },
  { status: 'drafted', label: 'Drafted' },
  { status: 'enriched', label: 'Enriched' },
  { status: 'in_review', label: 'In review', accent: 'in_review' },
  { status: 'approved', label: 'Approved' },
  { status: 'published', label: 'Published', accent: 'published' },
];

const PER_COLUMN_LIMIT = 50;

export function StrategiesPipeline({ onRowClick }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-7">
      {COLUMNS.map((col) => (
        <Column
          key={col.status}
          status={col.status}
          label={col.label}
          accent={col.accent}
          onRowClick={onRowClick}
        />
      ))}
    </div>
  );
}

function Column({
  status,
  label,
  accent,
  onRowClick,
}: {
  status: StrategyStatus;
  label: string;
  accent?: 'in_review' | 'published';
  onRowClick: (strategyId: string) => void;
}) {
  const query = useStrategyList({ status, page: 1, page_size: PER_COLUMN_LIMIT });
  const rows = query.data?.data ?? [];
  const total = query.data?.meta.total ?? rows.length;

  return (
    <div
      className={cn(
        'flex flex-col rounded-md border bg-muted/30 p-2',
        accent === 'in_review' && 'border-amber-300 bg-amber-50/60 dark:bg-amber-950/20',
        accent === 'published' && 'border-emerald-300 bg-emerald-50/60 dark:bg-emerald-950/20',
      )}
    >
      <div className="flex items-baseline justify-between px-1 pb-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </h3>
        <span className="text-xs text-muted-foreground">{total}</span>
      </div>

      <div className="flex flex-col gap-2 overflow-y-auto">
        {query.isPending && (
          <>
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </>
        )}
        {query.isError && (
          <p className="text-xs text-destructive">Failed to load</p>
        )}
        {!query.isPending && rows.length === 0 && (
          <p className="px-1 text-xs text-muted-foreground">—</p>
        )}
        {rows.map((r) => (
          <StrategyCard key={r.strategy_id} row={r} onClick={onRowClick} />
        ))}
        {total > rows.length && (
          <p className="px-1 text-xs text-muted-foreground">
            +{total - rows.length} more…
          </p>
        )}
      </div>
    </div>
  );
}

function StrategyCard({
  row,
  onClick,
}: {
  row: TaxStrategyListItem;
  onClick: (strategyId: string) => void;
}) {
  return (
    <Card
      className="cursor-pointer transition-colors hover:bg-muted"
      onClick={() => onClick(row.strategy_id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick(row.strategy_id);
        }
      }}
    >
      <CardContent className="p-2">
        <p className="truncate text-xs font-mono text-muted-foreground">
          {row.strategy_id} · v{row.version}
        </p>
        <p className="line-clamp-2 text-xs font-medium text-foreground">
          {row.name}
        </p>
      </CardContent>
    </Card>
  );
}
