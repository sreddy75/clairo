'use client';

/**
 * A2UI PieChart Component
 * Interactive pie/donut chart using Recharts
 */

import {
  Cell,
  Legend,
  Pie,
  PieChart as RechartsPieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useA2UIData } from '@/lib/a2ui/context';
import type { PieChartProps } from '@/lib/a2ui/types';


// =============================================================================
// Types
// =============================================================================

interface A2UIPieChartProps extends PieChartProps {
  id: string;
  showLabels?: boolean;
  dataBinding?: string;
  data?: Array<{ name: string; value: number; color?: string }>;
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
// Component
// =============================================================================

export function PieChart({
  id,
  title,
  donut = false,
  showLabels = true,
  showLegend = true,
  dataBinding,
  data: propData,
}: A2UIPieChartProps) {
  const boundData = useA2UIData<Array<{ name: string; value: number; color?: string }>>(
    dataBinding
  );
  const data = propData || boundData || [];

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

  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <Card id={id}>
      {title && (
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
        </CardHeader>
      )}
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <RechartsPieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={donut ? 60 : 0}
              outerRadius={100}
              paddingAngle={2}
              label={
                showLabels
                  ? ({ name, percent }) =>
                      `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`
                  : undefined
              }
              labelLine={showLabels}
            >
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.color || DEFAULT_COLORS[index % DEFAULT_COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number | undefined) => [
                `${(value ?? 0).toLocaleString('en-AU')} (${(((value ?? 0) / total) * 100).toFixed(1)}%)`,
                'Value',
              ]}
              contentStyle={{
                backgroundColor: 'hsl(var(--popover))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '6px',
              }}
              labelStyle={{ color: 'hsl(var(--popover-foreground))' }}
            />
            {showLegend && (
              <Legend
                layout="horizontal"
                verticalAlign="bottom"
                align="center"
              />
            )}
          </RechartsPieChart>
        </ResponsiveContainer>
        {donut && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="text-center">
              <p className="text-2xl font-bold">{total.toLocaleString('en-AU')}</p>
              <p className="text-sm text-muted-foreground">Total</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
