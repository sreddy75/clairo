'use client';

/**
 * AgedPayablesReport Component
 *
 * Displays an Aged Payables (Creditors) report from Xero with aging buckets.
 *
 * Spec 023: Xero Reports API Integration
 */

import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  CreditCard,
  DollarSign,
  RefreshCw,
} from 'lucide-react';
import { useState } from 'react';

import type { AgedPayablesSummary, ReportResponse, ReportRow } from '@/lib/xero-reports';
import { formatCurrency } from '@/lib/xero-reports';

interface AgedPayablesReportProps {
  report: ReportResponse | null;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  className?: string;
}

function AgingBucketBar({
  current,
  overdue30,
  overdue60,
  overdue90,
  overdue90Plus,
  total,
}: {
  current: number;
  overdue30: number;
  overdue60: number;
  overdue90: number;
  overdue90Plus: number;
  total: number;
}) {
  if (total === 0) return null;

  const getWidth = (val: number) => ((val / total) * 100).toFixed(1);

  return (
    <div className="w-full h-6 rounded-lg overflow-hidden flex">
      <div
        className="bg-green-500 h-full"
        style={{ width: `${getWidth(current)}%` }}
        title={`Current: ${formatCurrency(current)}`}
      />
      <div
        className="bg-yellow-400 h-full"
        style={{ width: `${getWidth(overdue30)}%` }}
        title={`1-30 days: ${formatCurrency(overdue30)}`}
      />
      <div
        className="bg-orange-400 h-full"
        style={{ width: `${getWidth(overdue60)}%` }}
        title={`31-60 days: ${formatCurrency(overdue60)}`}
      />
      <div
        className="bg-red-400 h-full"
        style={{ width: `${getWidth(overdue90)}%` }}
        title={`61-90 days: ${formatCurrency(overdue90)}`}
      />
      <div
        className="bg-red-600 h-full"
        style={{ width: `${getWidth(overdue90Plus)}%` }}
        title={`90+ days: ${formatCurrency(overdue90Plus)}`}
      />
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

function ReportRowDisplay({ row }: { row: ReportRow }) {
  const isHeader = row.row_type === 'Header';
  const isSummary = row.row_type === 'SummaryRow';
  const cells = row.cells || [];

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
          className={`px-4 py-2 whitespace-nowrap ${idx === 0 ? 'text-left' : 'text-right'}`}
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
      <div className="h-6 w-full bg-muted rounded" />
    </div>
  );
}

export function AgedPayablesReport({
  report,
  isLoading = false,
  error = null,
  onRefresh,
  isRefreshing = false,
  className = '',
}: AgedPayablesReportProps) {
  const summary = report?.summary as AgedPayablesSummary | undefined;
  const allRows = report?.rows || [];

  if (isLoading) {
    return (
      <div className={`bg-card rounded-lg shadow-sm border p-6 ${className}`}>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-foreground">Aged Payables</h3>
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
            Aged Payables
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
          <h3 className="text-lg font-semibold text-foreground">Aged Payables</h3>
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
            {report.report_titles?.join(' • ') || 'Outstanding supplier bills'}
          </p>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-2 text-muted-foreground hover:text-foreground disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      <div className="p-6 space-y-6">
        {/* Summary Metrics */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6 p-4 bg-muted rounded-lg">
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Total Payables
              </span>
              <div className="flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-primary" />
                <span className="text-xl font-semibold text-primary">
                  {formatCurrency(summary.total)}
                </span>
              </div>
            </div>
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Current (Not Due)
              </span>
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-status-success" />
                <span className="text-xl font-semibold text-status-success">
                  {formatCurrency(summary.current)}
                </span>
              </div>
            </div>
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Total Overdue
              </span>
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-amber-600" />
                <span className="text-xl font-semibold text-amber-600">
                  {formatCurrency(summary.overdue_total)}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Aging Bar */}
        {summary && summary.total > 0 && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Aging Distribution</span>
              <span>Total: {formatCurrency(summary.total)}</span>
            </div>
            <AgingBucketBar
              current={summary.current}
              overdue30={summary.overdue_30}
              overdue60={summary.overdue_60}
              overdue90={summary.overdue_90}
              overdue90Plus={summary.overdue_90_plus}
              total={summary.total}
            />
            <div className="flex flex-wrap gap-4 text-xs">
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-green-500" />
                <span>Current: {formatCurrency(summary.current)}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-yellow-400" />
                <span>1-30 days: {formatCurrency(summary.overdue_30)}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-orange-400" />
                <span>31-60 days: {formatCurrency(summary.overdue_60)}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-red-400" />
                <span>61-90 days: {formatCurrency(summary.overdue_90)}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded bg-red-600" />
                <span>90+ days: {formatCurrency(summary.overdue_90_plus)}</span>
              </div>
            </div>
          </div>
        )}

        {/* Detailed Table */}
        {allRows.length > 0 && (
          <ReportSection
            title="All Suppliers"
            rows={allRows}
            defaultOpen={false}
          />
        )}

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

export default AgedPayablesReport;
