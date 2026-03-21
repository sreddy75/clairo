'use client';

/**
 * A2UI LineChart Component
 * Interactive line chart using Recharts
 */

import { useMemo } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart as RechartsLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useA2UIData } from '@/lib/a2ui/context';
import type { LineChartProps, SeriesConfig } from '@/lib/a2ui/types';

// =============================================================================
// Types
// =============================================================================

interface A2UILineChartProps extends LineChartProps {
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

export function LineChart({
  id,
  title,
  xAxis,
  yAxis,
  series,
  interactive = true,
  dataBinding,
  data: propData,
}: A2UILineChartProps) {
  const boundData = useA2UIData<Record<string, unknown>[]>(dataBinding);

  // Normalize data to ensure numeric values are actual numbers
  const data = useMemo(() => {
    const rawData = (propData as Record<string, unknown>[]) || boundData || [];
    return normalizeChartData(rawData);
  }, [propData, boundData]);

  // Auto-detect series from data if not provided
  const detectedSeries: SeriesConfig[] = useMemo(() => {
    if (series) return series;
    const firstItem = data[0];
    if (!firstItem) return [];

    return Object.keys(firstItem)
      .filter((key) => key !== (xAxis?.dataKey || 'date') && typeof firstItem[key] === 'number')
      .map((key, index) => ({
        dataKey: key,
        name: key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' '),
        color: DEFAULT_COLORS[index % DEFAULT_COLORS.length],
      }));
  }, [series, data, xAxis?.dataKey]);

  if (!data.length) {
    return (
      <Card id={id}>
        <CardHeader>
          {title && <CardTitle className="text-sm font-medium">{title}</CardTitle>}
        </CardHeader>
        <CardContent>
          <div className="flex h-[200px] items-center justify-center text-muted-foreground">
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
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <RechartsLineChart
            data={data}
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey={xAxis?.dataKey || 'date'}
              className="text-xs"
              tick={{ fill: 'hsl(var(--muted-foreground))' }}
              tickLine={{ stroke: 'hsl(var(--muted))' }}
            />
            <YAxis
              className="text-xs"
              tick={{ fill: 'hsl(var(--muted-foreground))' }}
              tickLine={{ stroke: 'hsl(var(--muted))' }}
              tickFormatter={(value) =>
                yAxis?.format === 'currency'
                  ? `$${value.toLocaleString()}`
                  : yAxis?.format === 'percent'
                    ? `${value}%`
                    : value.toLocaleString()
              }
            />
            {interactive && (
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--popover))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                }}
                labelStyle={{ color: 'hsl(var(--popover-foreground))' }}
              />
            )}
            <Legend />
            {detectedSeries.map((s, index) => (
              <Line
                key={s.dataKey}
                type="monotone"
                dataKey={s.dataKey}
                name={s.name || s.dataKey}
                stroke={s.color || DEFAULT_COLORS[index % DEFAULT_COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={interactive ? { r: 5 } : undefined}
              />
            ))}
          </RechartsLineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
