'use client';

/**
 * BalanceSheetReport Component
 *
 * Displays a Balance Sheet report from Xero with summary metrics
 * and detailed row breakdown.
 *
 * Spec 023: Xero Reports API Integration
 */

import {
  AlertCircle,
  Building2,
  ChevronDown,
  ChevronRight,
  Clock,
  CreditCard,
  DollarSign,
  RefreshCw,
  Scale,
} from 'lucide-react';
import { useState } from 'react';

import { ThresholdTooltip } from '@/components/insights/ThresholdTooltip';
import type { BalanceSheetSummary, ReportResponse, ReportRow } from '@/lib/xero-reports';
import { formatCurrency } from '@/lib/xero-reports';

interface BalanceSheetReportProps {
  report: ReportResponse | null;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  className?: string;
}

function MetricCard({
  label,
  value,
  icon: Icon,
  variant = 'default',
}: {
  label: string;
  value: number | null | undefined;
  icon?: React.ComponentType<{ className?: string }>;
  variant?: 'default' | 'success' | 'warning' | 'danger';
}) {
  const colorClasses = {
    default: 'text-muted-foreground',
    success: 'text-status-success',
    warning: 'text-amber-600',
    danger: 'text-status-danger',
  };

  return (
    <div className="flex flex-col space-y-1">
      <span className="text-xs text-muted-foreground uppercase tracking-wide">
        {label}
      </span>
      <div className="flex items-center gap-2">
        {Icon && <Icon className={`h-4 w-4 ${colorClasses[variant]}`} />}
        <span className={`text-xl font-semibold ${colorClasses[variant]}`}>
          {formatCurrency(value)}
        </span>
      </div>
    </div>
  );
}

function ReportSection({
  title,
  rows,
  defaultOpen = false,
}: {
  title: string;
  rows: ReportRow[];
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (!rows || rows.length === 0) return null;

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full py-3 px-4 bg-muted hover:bg-muted text-left transition-colors"
      >
        <span className="font-medium text-foreground">{title}</span>
        {isOpen ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {isOpen && (
        <div className="border-t overflow-x-auto">
          <table className="w-full text-sm">
            <tbody>
              {rows.map((row, idx) => (
                <ReportRowDisplay key={idx} row={row} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ReportRowDisplay({ row, depth = 0 }: { row: ReportRow; depth?: number }) {
  const isHeader = row.row_type === 'Header';
  const isSummary = row.row_type === 'SummaryRow';
  const isSection = row.row_type === 'Section';
  const cells = row.cells || [];

  if (isSection && row.title) {
    return (
      <>
        <tr className="bg-muted">
          <td
            colSpan={cells.length || 2}
            className="px-4 py-2 font-medium text-foreground"
            style={{ paddingLeft: `${depth * 16 + 16}px` }}
          >
            {row.title}
          </td>
        </tr>
        {row.rows?.map((childRow, idx) => (
          <ReportRowDisplay key={idx} row={childRow} depth={depth + 1} />
        ))}
      </>
    );
  }

  if (cells.length === 0) return null;

  const rowClasses = `
    border-b border-border last:border-0
    ${isHeader ? 'bg-muted font-medium' : ''}
    ${isSummary ? 'bg-muted font-medium' : ''}
  `;

  return (
    <tr className={rowClasses}>
      {cells.map((cell, idx) => (
        <td
          key={idx}
          className={`px-4 py-2 ${idx === 0 ? 'text-left' : 'text-right'}`}
          style={idx === 0 ? { paddingLeft: `${depth * 16 + 16}px` } : undefined}
        >
          {cell?.value || ''}
        </td>
      ))}
    </tr>
  );
}

function ReportSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="space-y-2">
            <div className="h-4 w-24 bg-muted rounded" />
            <div className="h-8 w-32 bg-muted rounded" />
          </div>
        ))}
      </div>
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-2">
            <div className="h-12 w-full bg-muted rounded" />
            <div className="h-32 w-full bg-muted rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function BalanceSheetReport({
  report,
  isLoading = false,
  error = null,
  onRefresh,
  isRefreshing = false,
  className = '',
}: BalanceSheetReportProps) {
  const summary = report?.summary as BalanceSheetSummary | undefined;
  const sections = report?.rows?.filter((row) => row.row_type === 'Section') || [];

  // Determine health indicators
  const currentRatioHealth = summary?.current_ratio
    ? summary.current_ratio >= 1.5
      ? 'success'
      : summary.current_ratio >= 1
        ? 'warning'
        : 'danger'
    : 'default';

  const debtToEquityHealth = summary?.debt_to_equity
    ? summary.debt_to_equity <= 1
      ? 'success'
      : summary.debt_to_equity <= 2
        ? 'warning'
        : 'danger'
    : 'default';

  if (isLoading) {
    return (
      <div className={`bg-card rounded-lg shadow-sm border p-6 ${className}`}>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-foreground">Balance Sheet</h3>
          <p className="text-sm text-muted-foreground">Loading report...</p>
        </div>
        <ReportSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className={`bg-card rounded-lg shadow-sm border p-6 ${className}`}>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-status-danger" />
            Balance Sheet
          </h3>
          <p className="text-sm text-status-danger">{error}</p>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="inline-flex items-center px-3 py-2 border border-border rounded-md text-sm font-medium text-foreground bg-card hover:bg-muted disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
            Retry
          </button>
        )}
      </div>
    );
  }

  if (!report) {
    return (
      <div className={`bg-card rounded-lg shadow-sm border p-6 ${className}`}>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-foreground">Balance Sheet</h3>
          <p className="text-sm text-muted-foreground">No report data available</p>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="inline-flex items-center px-3 py-2 border border-border rounded-md text-sm font-medium text-foreground bg-card hover:bg-muted"
          >
            Load Report
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={`bg-card rounded-lg shadow-sm border ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between p-6 border-b">
        <div>
          <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
            {report.report_name}
            {report.is_stale && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700">
                <Clock className="h-3 w-3 mr-1" />
                Stale
              </span>
            )}
          </h3>
          <p className="text-sm text-muted-foreground">
            {report.report_titles?.join(' • ') || 'Financial position'}
          </p>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-2 text-muted-foreground hover:text-muted-foreground disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      <div className="p-6 space-y-6">
        {/* Summary Metrics */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 p-4 bg-muted rounded-lg">
            <MetricCard
              label="Total Assets"
              value={summary.total_assets}
              icon={Building2}
              variant="success"
            />
            <MetricCard
              label="Total Liabilities"
              value={summary.total_liabilities}
              icon={CreditCard}
              variant="danger"
            />
            <MetricCard
              label="Net Assets / Equity"
              value={summary.equity}
              icon={DollarSign}
              variant={summary.equity >= 0 ? 'success' : 'danger'}
            />
            <ThresholdTooltip metricKey="balance_sheet_current_ratio">
              <MetricCard
                label="Current Ratio"
                value={summary.current_ratio}
                icon={Scale}
                variant={currentRatioHealth as 'default' | 'success' | 'warning' | 'danger'}
              />
            </ThresholdTooltip>
          </div>
        )}

        {/* Asset/Liability Breakdown */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div className="text-center p-3 border rounded-lg bg-card">
              <div className="text-muted-foreground text-xs">Current Assets</div>
              <div className="font-medium text-foreground">{formatCurrency(summary.current_assets)}</div>
            </div>
            <div className="text-center p-3 border rounded-lg bg-card">
              <div className="text-muted-foreground text-xs">Non-Current Assets</div>
              <div className="font-medium text-foreground">{formatCurrency(summary.non_current_assets)}</div>
            </div>
            <div className="text-center p-3 border rounded-lg bg-card">
              <div className="text-muted-foreground text-xs">Current Liabilities</div>
              <div className="font-medium text-foreground">{formatCurrency(summary.current_liabilities)}</div>
            </div>
            <ThresholdTooltip metricKey="balance_sheet_debt_equity">
              <div className="text-center p-3 border rounded-lg bg-card">
                <div className="text-muted-foreground text-xs">Debt/Equity</div>
                <div className={`font-medium ${debtToEquityHealth === 'success' ? 'text-status-success' : debtToEquityHealth === 'danger' ? 'text-status-danger' : 'text-foreground'}`}>
                  {summary.debt_to_equity?.toFixed(2) || '-'}
                </div>
              </div>
            </ThresholdTooltip>
          </div>
        )}

        {/* Detailed Sections */}
        <div className="space-y-3">
          {sections.map((section, idx) => (
            <ReportSection
              key={idx}
              title={section.title || `Section ${idx + 1}`}
              rows={section.rows}
              defaultOpen={idx === 0}
            />
          ))}
        </div>

        {/* Report Metadata */}
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-4 border-t">
          <span>
            Fetched: {new Date(report.fetched_at).toLocaleString('en-AU')}
          </span>
          <span>
            As of: {report.period_key}
          </span>
        </div>
      </div>
    </div>
  );
}

export default BalanceSheetReport;
