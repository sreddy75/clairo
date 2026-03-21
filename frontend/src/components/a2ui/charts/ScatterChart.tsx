'use client';

/**
 * A2UI ScatterChart Component
 * Interactive scatter plot using Recharts
 */

import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart as RechartsScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useA2UIData } from '@/lib/a2ui/context';
import type { ScatterChartProps } from '@/lib/a2ui/types';


// =============================================================================
// Types
// =============================================================================

interface AxisConfigLocal {
  label?: string;
  dataKey?: string;
}

interface A2UIScatterChartProps extends ScatterChartProps {
  id: string;
  zAxis?: AxisConfigLocal;
  dataBinding?: string;
  data?: Record<string, unknown>[];
}

// =============================================================================
// Component
// =============================================================================

export function ScatterChart({
  id,
  title,
  xAxis,
  yAxis,
  zAxis,
  dataBinding,
  data: propData,
}: A2UIScatterChartProps) {
  const boundData = useA2UIData<Record<string, unknown>[]>(dataBinding);
  const data = (propData || boundData || []) as Array<{
    [key: string]: number | string;
  }>;

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
          <RechartsScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              type="number"
              dataKey={xAxis?.dataKey || 'x'}
              name={xAxis?.label || 'X'}
              className="text-xs"
              tick={{ fill: 'hsl(var(--muted-foreground))' }}
              tickLine={{ stroke: 'hsl(var(--muted))' }}
            />
            <YAxis
              type="number"
              dataKey={yAxis?.dataKey || 'y'}
              name={yAxis?.label || 'Y'}
              className="text-xs"
              tick={{ fill: 'hsl(var(--muted-foreground))' }}
              tickLine={{ stroke: 'hsl(var(--muted))' }}
            />
            {zAxis && (
              <ZAxis
                type="number"
                dataKey={zAxis.dataKey || 'z'}
                range={[50, 400]}
                name={zAxis.label || 'Size'}
              />
            )}
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              contentStyle={{
                backgroundColor: 'hsl(var(--popover))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '6px',
              }}
              labelStyle={{ color: 'hsl(var(--popover-foreground))' }}
            />
            <Scatter
              name={title || 'Data'}
              data={data}
              fill="hsl(var(--chart-1))"
            />
          </RechartsScatterChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
