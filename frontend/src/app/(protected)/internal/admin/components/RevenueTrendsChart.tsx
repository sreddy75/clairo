'use client';

/**
 * RevenueTrendsChart Component
 *
 * Line chart showing MRR trends over time with period selector.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import { TrendingUp } from 'lucide-react';
import { useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { useRevenueTrends } from '@/hooks/useAdminDashboard';
import type { RevenuePeriod, RevenueTrendDataPoint } from '@/types/admin';

interface RevenueTrendsChartProps {
  className?: string;
}

/**
 * Format cents to currency string.
 */
function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

/**
 * Format date for chart axis.
 */
function formatDate(dateStr: string, period: RevenuePeriod): string {
  const date = new Date(dateStr);
  switch (period) {
    case 'daily':
      return date.toLocaleDateString('en-AU', { month: 'short', day: 'numeric' });
    case 'weekly':
      return `Week ${getWeekNumber(date)}`;
    case 'monthly':
      return date.toLocaleDateString('en-AU', { month: 'short', year: '2-digit' });
    default:
      return dateStr;
  }
}

/**
 * Get ISO week number.
 */
function getWeekNumber(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
}

/**
 * Period selector tabs.
 */
function PeriodSelector({
  period,
  onChange,
}: {
  period: RevenuePeriod;
  onChange: (period: RevenuePeriod) => void;
}) {
  const options: { value: RevenuePeriod; label: string }[] = [
    { value: 'daily', label: 'Daily' },
    { value: 'weekly', label: 'Weekly' },
    { value: 'monthly', label: 'Monthly' },
  ];

  return (
    <div className="flex bg-muted rounded-lg p-1">
      {options.map((option) => (
        <button
          key={option.value}
          onClick={() => onChange(option.value)}
          className={`px-3 py-1 text-sm font-medium rounded-md transition-colors ${
            period === option.value
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Custom tooltip for the chart.
 */
function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{
    value: number;
    dataKey: string;
    color: string;
    name: string;
  }>;
  label?: string;
}) {
  if (!active || !payload || !payload.length) {
    return null;
  }

  return (
    <div className="bg-card border border-border rounded-lg p-3 shadow-lg">
      <p className="text-sm text-muted-foreground mb-2">{label}</p>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-sm text-muted-foreground">{entry.name}:</span>
          <span className="text-sm font-medium text-foreground">
            {entry.dataKey === 'mrr_cents'
              ? formatCurrency(entry.value)
              : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * Loading skeleton for chart.
 */
function ChartSkeleton() {
  return (
    <div className="bg-card rounded-xl p-6 border border-border">
      <div className="flex items-center justify-between mb-6">
        <div className="h-6 bg-muted rounded w-40 animate-pulse" />
        <div className="h-8 bg-muted rounded w-32 animate-pulse" />
      </div>
      <div className="h-64 bg-muted rounded animate-pulse flex items-center justify-center">
        <div className="text-muted-foreground">Loading chart...</div>
      </div>
    </div>
  );
}

/**
 * Main RevenueTrendsChart component.
 */
export function RevenueTrendsChart({ className = '' }: RevenueTrendsChartProps) {
  const [period, setPeriod] = useState<RevenuePeriod>('daily');
  const [lookbackDays, setLookbackDays] = useState(30);

  const { data, isLoading, error } = useRevenueTrends({ period, lookback_days: lookbackDays });

  if (isLoading) {
    return <ChartSkeleton />;
  }

  if (error) {
    return (
      <div className={`bg-card rounded-xl p-6 border border-border ${className}`}>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary" />
            Revenue Trends
          </h3>
        </div>
        <div className="h-64 flex items-center justify-center text-status-danger">
          Failed to load revenue trends
        </div>
      </div>
    );
  }

  const chartData = (data?.data_points ?? []).map((point: RevenueTrendDataPoint) => ({
    ...point,
    formattedDate: formatDate(point.date, period),
  }));

  // Calculate MRR growth
  const firstMRR = chartData[0]?.mrr_cents ?? 0;
  const lastMRR = chartData[chartData.length - 1]?.mrr_cents ?? 0;
  const mrrGrowth = firstMRR > 0 ? ((lastMRR - firstMRR) / firstMRR) * 100 : 0;

  // Calculate total new and churned
  const totalNew = chartData.reduce(
    (sum: number, point: RevenueTrendDataPoint) => sum + point.new_subscriptions,
    0
  );
  const totalChurned = chartData.reduce(
    (sum: number, point: RevenueTrendDataPoint) => sum + point.churned_subscriptions,
    0
  );

  return (
    <div className={`bg-card rounded-xl p-6 border border-border ${className}`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary" />
            Revenue Trends
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            MRR over the last {lookbackDays} days
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Lookback selector */}
          <select
            value={lookbackDays}
            onChange={(e) => setLookbackDays(Number(e.target.value))}
            className="px-3 py-1.5 bg-card border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
          >
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
            <option value={180}>6 months</option>
            <option value={365}>1 year</option>
          </select>
          <PeriodSelector period={period} onChange={setPeriod} />
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-muted rounded-lg p-3">
          <p className="text-xs text-muted-foreground">MRR Growth</p>
          <p
            className={`text-lg font-bold ${
              mrrGrowth >= 0 ? 'text-status-success' : 'text-status-danger'
            }`}
          >
            {mrrGrowth >= 0 ? '+' : ''}
            {mrrGrowth.toFixed(1)}%
          </p>
        </div>
        <div className="bg-muted rounded-lg p-3">
          <p className="text-xs text-muted-foreground">New Subscriptions</p>
          <p className="text-lg font-bold text-primary">{totalNew}</p>
        </div>
        <div className="bg-muted rounded-lg p-3">
          <p className="text-xs text-muted-foreground">Churned</p>
          <p className="text-lg font-bold text-status-warning">{totalChurned}</p>
        </div>
      </div>

      {/* Chart */}
      {chartData.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-muted-foreground">
          No data available for this period
        </div>
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="formattedDate"
                stroke="#9CA3AF"
                fontSize={12}
                tickLine={false}
                axisLine={{ stroke: '#E5E7EB' }}
              />
              <YAxis
                stroke="#9CA3AF"
                fontSize={12}
                tickLine={false}
                axisLine={{ stroke: '#E5E7EB' }}
                tickFormatter={(value) => formatCurrency(value)}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ stroke: '#D1D5DB', strokeDasharray: '5 5' }}
              />
              <Line
                type="monotone"
                dataKey="mrr_cents"
                name="MRR"
                stroke="#3B82F6"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6, stroke: '#3B82F6', strokeWidth: 2, fill: '#DBEAFE' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-4 pt-4 border-t border-border">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-primary" />
          <span className="text-sm text-muted-foreground">Monthly Recurring Revenue</span>
        </div>
      </div>
    </div>
  );
}

export default RevenueTrendsChart;
