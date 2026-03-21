'use client';

/**
 * TrialBalanceReport Component
 *
 * Displays a Trial Balance report from Xero showing all accounts
 * with debit and credit balances.
 *
 * Spec 023: Xero Reports API Integration
 */

import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  DollarSign,
  RefreshCw,
  Scale,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';

import type { ReportResponse, ReportRow, TrialBalanceSummary } from '@/lib/xero-reports';
import { formatCurrency } from '@/lib/xero-reports';

interface TrialBalanceReportProps {
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

export function TrialBalanceReport({
  report,
  isLoading = false,
  error = null,
  onRefresh,
  isRefreshing = false,
  className = '',
}: TrialBalanceReportProps) {
  const summary = report?.summary as TrialBalanceSummary | undefined;
  const allRows = report?.rows || [];

  if (isLoading) {
    return (
      <div className={`bg-card rounded-lg shadow-sm border p-6 ${className}`}>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-foreground">Trial Balance</h3>
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
            Trial Balance
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
          <h3 className="text-lg font-semibold text-foreground">Trial Balance</h3>
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
            {report.report_titles?.join(' • ') || 'Account balances summary'}
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
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Total Debits
              </span>
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-primary" />
                <span className="text-xl font-semibold text-primary">
                  {formatCurrency(summary.total_debits)}
                </span>
              </div>
            </div>
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Total Credits
              </span>
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-purple-600" />
                <span className="text-xl font-semibold text-purple-600">
                  {formatCurrency(summary.total_credits)}
                </span>
              </div>
            </div>
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Balance Status
              </span>
              <div className="flex items-center gap-2">
                {summary.is_balanced ? (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-status-success" />
                    <span className="text-xl font-semibold text-status-success">
                      Balanced
                    </span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 text-status-danger" />
                    <span className="text-xl font-semibold text-status-danger">
                      Unbalanced
                    </span>
                  </>
                )}
              </div>
            </div>
            <div className="flex flex-col space-y-1">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Accounts
              </span>
              <div className="flex items-center gap-2">
                <Scale className="h-4 w-4 text-muted-foreground" />
                <span className="text-xl font-semibold text-muted-foreground">
                  {summary.account_count}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Balance Check Alert */}
        {summary && !summary.is_balanced && (
          <div className="border border-red-200 rounded-lg p-4 bg-red-50">
            <div className="flex items-center gap-2 text-red-800">
              <AlertCircle className="h-5 w-5" />
              <span className="font-medium">Trial Balance is out of balance!</span>
            </div>
            <p className="mt-1 text-sm text-red-700">
              Total debits ({formatCurrency(summary.total_debits)}) do not equal
              total credits ({formatCurrency(summary.total_credits)}).
              Difference: {formatCurrency(Math.abs(summary.total_debits - summary.total_credits))}
            </p>
          </div>
        )}

        {/* Detailed Table */}
        {allRows.length > 0 && (
          <ReportSection
            title="All Accounts"
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
            As of: {report.period_key}
          </span>
        </div>
      </div>
    </div>
  );
}

export default TrialBalanceReport;
