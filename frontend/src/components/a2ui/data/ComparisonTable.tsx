'use client';

/**
 * A2UI ComparisonTable Component
 * Displays side-by-side comparison of values with variance highlighting
 */

import { ArrowDown, ArrowUp, Minus } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface ComparisonColumn {
  key: string;
  label: string;
  format?: string;
}

interface ComparisonRowLocal {
  label: string;
  values: Record<string, number | string | undefined>;
  format?: string;
  variance?: number;
  isAnomaly?: boolean;
}

interface A2UIComparisonTableProps {
  id: string;
  title?: string;
  rows?: ComparisonRowLocal[];
  columns?: ComparisonColumn[];
  highlightVariance?: boolean;
  varianceThreshold?: number;
  dataBinding?: string;
}

// =============================================================================
// Helpers
// =============================================================================

function formatValue(value: number | string | undefined, format?: string): string {
  if (value === undefined) return '-';
  if (typeof value === 'string') return value;

  switch (format) {
    case 'currency':
      return value.toLocaleString('en-AU', { style: 'currency', currency: 'AUD' });
    case 'percent':
      return `${value.toFixed(1)}%`;
    case 'number':
      return value.toLocaleString('en-AU');
    default:
      return String(value);
  }
}

function getVarianceIcon(variance: number) {
  if (variance > 0) return <ArrowUp className="h-3 w-3" />;
  if (variance < 0) return <ArrowDown className="h-3 w-3" />;
  return <Minus className="h-3 w-3" />;
}

function getVarianceClass(variance: number, isAnomaly: boolean) {
  if (isAnomaly) return 'text-destructive bg-destructive/10';
  if (Math.abs(variance) <= 5) return 'text-muted-foreground';
  if (variance > 0) return 'text-status-success';
  return 'text-status-danger';
}

// =============================================================================
// Component
// =============================================================================

export function ComparisonTable({
  id,
  title,
  rows,
  columns,
  highlightVariance = true,
  varianceThreshold = 10,
}: A2UIComparisonTableProps) {
  if (!rows?.length || !columns?.length) {
    return (
      <Card id={id}>
        {title && (
          <CardHeader>
            <CardTitle className="text-sm font-medium">{title}</CardTitle>
          </CardHeader>
        )}
        <CardContent>
          <div className="flex h-24 items-center justify-center text-muted-foreground">
            No data to compare
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card id={id}>
      {title && (
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
        </CardHeader>
      )}
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[200px]">Field</TableHead>
                {columns.map((col) => (
                  <TableHead key={col.key} className="text-right">
                    {col.label}
                  </TableHead>
                ))}
                {highlightVariance && <TableHead className="text-right">Variance</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const isAnomaly =
                  row.variance !== undefined &&
                  Math.abs(row.variance) > varianceThreshold;

                return (
                  <TableRow
                    key={row.label}
                    className={cn(isAnomaly && 'bg-destructive/5')}
                  >
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        {isAnomaly && (
                          <span className="h-2 w-2 rounded-full bg-destructive" />
                        )}
                        {row.label}
                      </div>
                    </TableCell>
                    {columns.map((col) => (
                      <TableCell key={col.key} className="text-right font-mono">
                        {formatValue(row.values[col.key], row.format)}
                      </TableCell>
                    ))}
                    {highlightVariance && row.variance !== undefined && (
                      <TableCell className="text-right">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
                            getVarianceClass(row.variance, isAnomaly)
                          )}
                        >
                          {getVarianceIcon(row.variance)}
                          {row.variance > 0 ? '+' : ''}
                          {row.variance.toFixed(1)}%
                        </span>
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
