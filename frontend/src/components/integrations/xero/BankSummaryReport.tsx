'use client';

/**
 * BankSummaryReport Component
 *
 * Displays a Bank Summary report from Xero showing cash flow
 * across all bank accounts.
 *
 * Spec 023: Xero Reports API Integration
 */

import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  Building2,
  ChevronDown,
  ChevronRight,
  Clock,
  DollarSign,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { useState } from 'react';

import type { BankSummarySummary, ReportResponse, ReportRow } from '@/lib/xero-reports';
import { formatCurrency } from '@/lib/xero-reports';

interface BankSummaryReportProps {
  report: ReportResponse | null;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  className?: string;
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
    </div>
  );
}

export function BankSummaryReport({
  report,
  isLoading = false,
  error = null,
  onRefresh,
  isRefreshing = false,
  className = '',
}: BankSummaryReportProps) {
  const summary = report?.summary as BankSummarySummary | undefined;
  const allRows = report?.rows || [];

  const netMovementTrend = summary?.net_movement
    ? summary.net_movement >= 0
      ? 'positive'
      : 'negative'
    : 'neutral';

  if (isLoading) {
    return (
      <div className={`bg-card rounded-lg shadow-sm border p-6 ${className}`}>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-foreground">Bank Summary</h3>
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
            Bank Summary
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
          <h3 className="text-lg font-semibold text-foreground">Bank Summary</h3>
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
            {report.report_titles?.join(' • ') || 'Bank account cash flow'}
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
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 p-4 bg-muted rounded-lg">
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Opening Balance
              </span>
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-muted-foreground" />
                <span className="text-lg font-semibold text-foreground">
                  {formatCurrency(summary.total_opening)}
                </span>
              </div>
            </div>
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Received
              </span>
              <div className="flex items-center gap-2">
                <ArrowDownRight className="h-4 w-4 text-status-success" />
                <span className="text-lg font-semibold text-status-success">
                  {formatCurrency(summary.total_received)}
                </span>
              </div>
            </div>
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Spent
              </span>
              <div className="flex items-center gap-2">
                <ArrowUpRight className="h-4 w-4 text-status-danger" />
                <span className="text-lg font-semibold text-status-danger">
                  {formatCurrency(summary.total_spent)}
                </span>
              </div>
            </div>
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Net Movement
              </span>
              <div className="flex items-center gap-2">
                {netMovementTrend === 'positive' ? (
                  <TrendingUp className="h-4 w-4 text-status-success" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-status-danger" />
                )}
                <span className={`text-lg font-semibold ${netMovementTrend === 'positive' ? 'text-status-success' : 'text-status-danger'}`}>
                  {formatCurrency(summary.net_movement)}
                </span>
              </div>
            </div>
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Closing Balance
              </span>
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-primary" />
                <span className="text-lg font-semibold text-primary">
                  {formatCurrency(summary.total_closing)}
                </span>
              </div>
            </div>
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Bank Accounts
              </span>
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-muted-foreground" />
                <span className="text-lg font-semibold text-muted-foreground">
                  {summary.account_count}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Cash Flow Summary */}
        {summary && (
          <div className="flex items-center justify-center gap-8 p-4 border rounded-lg">
            <div className="text-center">
              <div className="text-sm text-muted-foreground">Opening</div>
              <div className="text-xl font-semibold">{formatCurrency(summary.total_opening)}</div>
            </div>
            <div className="text-2xl text-muted-foreground">+</div>
            <div className="text-center">
              <div className="text-sm text-status-success">Received</div>
              <div className="text-xl font-semibold text-status-success">{formatCurrency(summary.total_received)}</div>
            </div>
            <div className="text-2xl text-muted-foreground">-</div>
            <div className="text-center">
              <div className="text-sm text-status-danger">Spent</div>
              <div className="text-xl font-semibold text-status-danger">{formatCurrency(summary.total_spent)}</div>
            </div>
            <div className="text-2xl text-muted-foreground">=</div>
            <div className="text-center">
              <div className="text-sm text-primary">Closing</div>
              <div className="text-xl font-semibold text-primary">{formatCurrency(summary.total_closing)}</div>
            </div>
          </div>
        )}

        {/* Detailed Table */}
        {allRows.length > 0 && (
          <ReportSection
            title="All Bank Accounts"
            rows={allRows}
            defaultOpen={true}
          />
        )}

        {/* Report Metadata */}
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-4 border-t">
          <span>
            Fetched: {new Date(report.fetched_at).toLocaleString('en-AU')}
          </span>
          <span>
            Period: {report.period_key}
          </span>
        </div>
      </div>
    </div>
  );
}

export default BankSummaryReport;
