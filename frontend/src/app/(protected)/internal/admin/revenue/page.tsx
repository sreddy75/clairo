'use client';

/**
 * Admin Revenue Analytics Page
 *
 * Displays comprehensive revenue metrics and trends.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import { AlertTriangle, DollarSign, RefreshCw } from 'lucide-react';
import { useState } from 'react';

import { useRevenueMetrics } from '@/hooks/useAdminDashboard';

import { RevenueMetrics } from '../components/RevenueMetrics';
import { RevenueTrendsChart } from '../components/RevenueTrendsChart';

/**
 * Revenue analytics page.
 */
export default function RevenuePage() {
  const [periodDays, setPeriodDays] = useState(30);
  const { data, isLoading, error, refetch, isFetching } = useRevenueMetrics({
    period_days: periodDays,
  });

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
            <DollarSign className="w-7 h-7 text-status-success" />
            Revenue Analytics
          </h1>
          <p className="text-muted-foreground mt-1">
            Monitor MRR, churn, expansion, and revenue trends
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Period selector */}
          <select
            value={periodDays}
            onChange={(e) => setPeriodDays(Number(e.target.value))}
            className="px-4 py-2 bg-card border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={180}>Last 6 months</option>
            <option value={365}>Last year</option>
          </select>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted/80 transition-colors disabled:opacity-50"
          >
            <RefreshCw
              className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`}
            />
            Refresh
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-status-danger" />
          <div>
            <p className="text-status-danger font-medium">Failed to load revenue data</p>
            <p className="text-sm text-status-danger/80">
              {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="ml-auto px-3 py-1 text-sm bg-status-danger/10 text-status-danger rounded hover:bg-status-danger/20 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Revenue metrics cards */}
      <RevenueMetrics data={data ?? null} isLoading={isLoading} />

      {/* Revenue trends chart */}
      <RevenueTrendsChart />

      {/* Additional insights */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Health indicators */}
        <div className="bg-card rounded-xl p-6 border border-border">
          <h3 className="text-lg font-semibold text-foreground mb-4">Health Indicators</h3>
          <div className="space-y-4">
            <HealthIndicator
              label="Net Revenue Retention"
              value={calculateNRR(data)}
              target={100}
              format="percentage"
              isLoading={isLoading}
            />
            <HealthIndicator
              label="Gross Revenue Retention"
              value={calculateGRR(data)}
              target={90}
              format="percentage"
              isLoading={isLoading}
            />
            <HealthIndicator
              label="Quick Ratio"
              value={calculateQuickRatio(data)}
              target={4}
              format="number"
              isLoading={isLoading}
            />
          </div>
        </div>

        {/* Revenue breakdown */}
        <div className="bg-card rounded-xl p-6 border border-border">
          <h3 className="text-lg font-semibold text-foreground mb-4">Revenue Breakdown</h3>
          <div className="space-y-3">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="animate-pulse">
                  <div className="h-4 bg-muted rounded w-full mb-1" />
                  <div className="h-2 bg-muted rounded w-3/4" />
                </div>
              ))
            ) : (
              <>
                <RevenueBreakdownRow
                  label="Base MRR"
                  value={data?.mrr?.current_cents ?? 0}
                  total={data?.mrr?.current_cents ?? 0}
                  color="bg-primary"
                />
                <RevenueBreakdownRow
                  label="Expansion Revenue"
                  value={data?.expansion?.amount_cents ?? 0}
                  total={data?.mrr?.current_cents ?? 1}
                  color="bg-status-success"
                />
                <RevenueBreakdownRow
                  label="Lost to Churn"
                  value={data?.churn?.lost_cents ?? 0}
                  total={data?.mrr?.current_cents ?? 1}
                  color="bg-status-danger"
                  isNegative
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Health indicator component.
 */
function HealthIndicator({
  label,
  value,
  target,
  format,
  isLoading,
}: {
  label: string;
  value: number;
  target: number;
  format: 'percentage' | 'number';
  isLoading: boolean;
}) {
  const isHealthy = value >= target;
  const percentage = Math.min((value / target) * 100, 100);

  if (isLoading) {
    return (
      <div className="animate-pulse">
        <div className="h-4 bg-muted rounded w-32 mb-2" />
        <div className="h-2 bg-muted rounded w-full" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span
          className={`text-sm font-medium ${
            isHealthy ? 'text-status-success' : 'text-status-warning'
          }`}
        >
          {format === 'percentage' ? `${value.toFixed(1)}%` : value.toFixed(1)}
          <span className="text-muted-foreground ml-1">(target: {target}{format === 'percentage' ? '%' : ''})</span>
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            isHealthy ? 'bg-status-success' : 'bg-status-warning'
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Revenue breakdown row.
 */
function RevenueBreakdownRow({
  label,
  value,
  total,
  color,
  isNegative = false,
}: {
  label: string;
  value: number;
  total: number;
  color: string;
  isNegative?: boolean;
}) {
  const percentage = total > 0 ? (value / total) * 100 : 0;
  const formattedValue = new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value / 100);

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className={`text-sm font-medium ${isNegative ? 'text-status-danger' : 'text-foreground'}`}>
          {isNegative ? '-' : ''}{formattedValue}
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-500`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Calculate Net Revenue Retention.
 * NRR = (Starting MRR + Expansion - Churn - Contraction) / Starting MRR * 100
 */
function calculateNRR(data: { mrr?: { previous_cents: number; current_cents: number }; expansion?: { amount_cents: number }; churn?: { lost_cents: number } } | null | undefined): number {
  if (!data?.mrr?.previous_cents) return 100;
  const startingMRR = data.mrr.previous_cents;
  const expansion = data.expansion?.amount_cents ?? 0;
  const churn = data.churn?.lost_cents ?? 0;
  return ((startingMRR + expansion - churn) / startingMRR) * 100;
}

/**
 * Calculate Gross Revenue Retention.
 * GRR = (Starting MRR - Churn - Contraction) / Starting MRR * 100
 */
function calculateGRR(data: { mrr?: { previous_cents: number }; churn?: { lost_cents: number } } | null | undefined): number {
  if (!data?.mrr?.previous_cents) return 100;
  const startingMRR = data.mrr.previous_cents;
  const churn = data.churn?.lost_cents ?? 0;
  return ((startingMRR - churn) / startingMRR) * 100;
}

/**
 * Calculate Quick Ratio.
 * Quick Ratio = (New MRR + Expansion MRR) / (Churned MRR + Contraction MRR)
 * A ratio > 4 is considered healthy for SaaS.
 */
function calculateQuickRatio(data: { expansion?: { amount_cents: number; upgrade_count: number }; churn?: { lost_cents: number } } | null | undefined): number {
  const expansion = data?.expansion?.amount_cents ?? 0;
  const churn = data?.churn?.lost_cents ?? 0;
  if (churn === 0) return expansion > 0 ? 10 : 0; // Cap at 10 if no churn
  return expansion / churn;
}
