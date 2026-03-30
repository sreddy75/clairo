'use client';

/**
 * A2UI DataTable Component
 * Displays tabular data with sorting and pagination
 */

import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useA2UIData } from '@/lib/a2ui/context';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface TableColumnLocal {
  key: string;
  header?: string;
  label?: string;
  format?: 'text' | 'number' | 'currency' | 'date' | 'badge';
  sortable?: boolean;
  align?: 'left' | 'center' | 'right';
}

interface A2UIDataTableProps {
  id: string;
  title?: string;
  columns?: TableColumnLocal[];
  sortable?: boolean;
  paginated?: boolean;
  pageSize?: number;
  dataBinding?: string;
  data?: Record<string, unknown>[];
}

type SortDirection = 'asc' | 'desc' | null;

// =============================================================================
// Component
// =============================================================================

export function DataTable({
  id,
  title,
  columns,
  sortable = true,
  paginated = true,
  pageSize = 10,
  dataBinding,
  data: propData,
}: A2UIDataTableProps) {
  const boundData = useA2UIData<Record<string, unknown>[]>(dataBinding);
  const data = useMemo(() => propData || boundData || [], [propData, boundData]);

  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);
  const [currentPage, setCurrentPage] = useState(0);

  // Sort data
  const sortedData = useMemo(() => {
    if (!sortColumn || !sortDirection) return data;

    return [...data].sort((a, b) => {
      const aVal = a[sortColumn];
      const bVal = b[sortColumn];

      if (aVal === bVal) return 0;
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;

      const comparison = aVal < bVal ? -1 : 1;
      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [data, sortColumn, sortDirection]);

  // Paginate data
  const paginatedData = useMemo(() => {
    if (!paginated) return sortedData;
    const start = currentPage * pageSize;
    return sortedData.slice(start, start + pageSize);
  }, [sortedData, paginated, currentPage, pageSize]);

  const totalPages = Math.ceil(data.length / pageSize);

  const handleSort = useCallback(
    (columnKey: string) => {
      if (!sortable) return;

      if (sortColumn === columnKey) {
        setSortDirection((prev) =>
          prev === 'asc' ? 'desc' : prev === 'desc' ? null : 'asc'
        );
        if (sortDirection === 'desc') setSortColumn(null);
      } else {
        setSortColumn(columnKey);
        setSortDirection('asc');
      }
    },
    [sortable, sortColumn, sortDirection]
  );

  const formatCell = (value: unknown, format?: string): string => {
    if (value === null || value === undefined) return '-';

    switch (format) {
      case 'currency':
        return typeof value === 'number'
          ? value.toLocaleString('en-AU', { style: 'currency', currency: 'AUD' })
          : String(value);
      case 'percent':
        return typeof value === 'number' ? `${value.toFixed(1)}%` : String(value);
      case 'date':
        return value instanceof Date || typeof value === 'string'
          ? new Date(value as string).toLocaleDateString('en-AU')
          : String(value);
      case 'number':
        return typeof value === 'number' ? value.toLocaleString('en-AU') : String(value);
      default:
        return String(value);
    }
  };

  if (!data.length || !columns?.length) {
    return (
      <Card id={id}>
        {title && (
          <CardHeader>
            <CardTitle className="text-sm font-medium">{title}</CardTitle>
          </CardHeader>
        )}
        <CardContent>
          <div className="flex h-24 items-center justify-center text-muted-foreground">
            No data available
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
                {columns.map((col) => (
                  <TableHead
                    key={col.key}
                    className={cn(
                      sortable && 'cursor-pointer select-none hover:bg-muted/50',
                      col.align === 'right' && 'text-right',
                      col.align === 'center' && 'text-center'
                    )}
                    onClick={() => sortable && handleSort(col.key)}
                  >
                    <div className="flex items-center gap-1">
                      <span>{col.label}</span>
                      {sortable && (
                        <span className="text-muted-foreground">
                          {sortColumn === col.key ? (
                            sortDirection === 'asc' ? (
                              <ArrowUp className="h-3 w-3" />
                            ) : (
                              <ArrowDown className="h-3 w-3" />
                            )
                          ) : (
                            <ArrowUpDown className="h-3 w-3 opacity-50" />
                          )}
                        </span>
                      )}
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedData.map((row, rowIndex) => (
                <TableRow key={rowIndex}>
                  {columns.map((col) => (
                    <TableCell
                      key={col.key}
                      className={cn(
                        col.align === 'right' && 'text-right',
                        col.align === 'center' && 'text-center'
                      )}
                    >
                      {formatCell(row[col.key], col.format)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {paginated && totalPages > 1 && (
          <div className="flex items-center justify-between border-t px-4 py-3">
            <span className="text-sm text-muted-foreground">
              Showing {currentPage * pageSize + 1} to{' '}
              {Math.min((currentPage + 1) * pageSize, data.length)} of {data.length}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                disabled={currentPage === 0}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="px-2 text-sm">
                {currentPage + 1} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={currentPage >= totalPages - 1}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
