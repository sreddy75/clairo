'use client';

/**
 * A2UI BarChart Component
 * Interactive bar chart using Recharts
 */

import { useMemo } from 'react';
import {
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useA2UIData } from '@/lib/a2ui/context';
import type { BarChartProps } from '@/lib/a2ui/types';

// =============================================================================
// Types
// =============================================================================

interface A2UIBarChartProps extends BarChartProps {
  id: string;
  dataBinding?: string;
  data?: unknown[];
}

// =============================================================================
// Default Colors
// =============================================================================

const DEFAULT_COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-5))',
];

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Parse a value that might be a formatted string (like "$46,341") to a number
 */
function parseNumericValue(value: unknown): number | null {
  if (typeof value === 'number') return value;
  if (typeof value !== 'string') return null;

  // Remove currency symbols, commas, percent signs, whitespace
  const cleaned = value.replace(/[$,\s%]/g, '');
  const num = parseFloat(cleaned);
  return isNaN(num) ? null : num;
}

/**
 * Normalize chart data by converting string values to numbers where possible
 */
function normalizeChartData(data: Record<string, unknown>[]): Record<string, unknown>[] {
  return data.map((item) => {
    const normalized: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(item)) {
      const parsed = parseNumericValue(value);
      normalized[key] = parsed !== null ? parsed : value;
    }
    return normalized;
  });
}

// =============================================================================
// Component
// =============================================================================

export function BarChart({
  id,
  title,
  orientation = 'vertical',
  stacked = false,
  dataBinding,
  data: propData,
}: A2UIBarChartProps) {
  const boundData = useA2UIData<Record<string, unknown>[]>(dataBinding);

  // Normalize data to ensure numeric values are actual numbers
  const data = useMemo(() => {
    const rawData = (propData as Record<string, unknown>[]) || boundData || [];
    return normalizeChartData(rawData);
  }, [propData, boundData]);

  // Auto-detect value keys from data
  const valueKeys = useMemo(() => {
    const firstItem = data[0];
    if (!firstItem) return [];
    return Object.keys(firstItem).filter(
      (key) => key !== 'name' && key !== 'label' && typeof firstItem[key] === 'number'
    );
  }, [data]);

  const nameKey = data[0] && 'name' in data[0] ? 'name' : 'label';

  if (!data.length) {
    return (
      <Card id={id}>
        <CardHeader>
          {title && <CardTitle className="text-sm font-medium">{title}</CardTitle>}
        </CardHeader>
        <CardContent className="p-3">
          <div className="flex h-[100px] items-center justify-center text-muted-foreground text-sm">
            No data available
          </div>
        </CardContent>
      </Card>
    );
  }

  const isHorizontal = orientation === 'horizontal';

  return (
    <Card id={id}>
      {title && (
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
        </CardHeader>
      )}
      <CardContent className="p-3">
        <ResponsiveContainer width="100%" height={150}>
          <RechartsBarChart
            data={data}
            layout={isHorizontal ? 'vertical' : 'horizontal'}
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            {isHorizontal ? (
              <>
                <XAxis
                  type="number"
                  className="text-xs"
                  tick={{ fill: 'hsl(var(--muted-foreground))' }}
                />
                <YAxis
                  type="category"
                  dataKey={nameKey}
                  className="text-xs"
                  tick={{ fill: 'hsl(var(--muted-foreground))' }}
                  width={100}
                />
              </>
            ) : (
              <>
                <XAxis
                  dataKey={nameKey}
                  className="text-xs"
                  tick={{ fill: 'hsl(var(--muted-foreground))' }}
                />
                <YAxis
                  className="text-xs"
                  tick={{ fill: 'hsl(var(--muted-foreground))' }}
                />
              </>
            )}
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--popover))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '6px',
              }}
              labelStyle={{ color: 'hsl(var(--popover-foreground))' }}
            />
            {valueKeys.length > 1 && <Legend />}
            {valueKeys.map((key, index) => (
              <Bar
                key={key}
                dataKey={key}
                stackId={stacked ? 'stack' : undefined}
                fill={DEFAULT_COLORS[index % DEFAULT_COLORS.length]}
                radius={stacked ? undefined : [4, 4, 0, 0]}
              >
                {/* Individual bar colors for single series */}
                {valueKeys.length === 1 &&
                  data.map((_, cellIndex) => (
                    <Cell
                      key={`cell-${cellIndex}`}
                      fill={DEFAULT_COLORS[cellIndex % DEFAULT_COLORS.length]}
                    />
                  ))}
              </Bar>
            ))}
          </RechartsBarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
