'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  ArrowDownCircle,
  ArrowUpCircle,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Repeat,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import type {
  RepeatingInvoice,
  RepeatingInvoiceStatus,
  RecurringSummary,
  ScheduleUnit} from '@/lib/api/assets';
import {
  formatCurrency,
  formatDate,
  getRepeatingInvoices,
  getRecurringSummary,
  getScheduleDisplayText,
  syncRepeatingInvoices,
} from '@/lib/api/assets';

interface RepeatingInvoicesListProps {
  /** Connection ID for the Xero connection */
  connectionId: string;
  /** Number of items per page */
  pageSize?: number;
  /** Optional filter by type (ACCPAY = bills, ACCREC = sales) */
  invoiceType?: 'ACCPAY' | 'ACCREC';
  /** Optional filter by status */
  statusFilter?: RepeatingInvoiceStatus;
  /** Show summary card */
  showSummary?: boolean;
}

/**
 * Displays a paginated list of repeating invoices with recurring revenue/expense summary.
 */
export function RepeatingInvoicesList({
  connectionId,
  pageSize = 25,
  invoiceType,
  statusFilter,
  showSummary = true,
}: RepeatingInvoicesListProps) {
  const { getToken } = useAuth();
  const [invoices, setInvoices] = useState<RepeatingInvoice[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<RecurringSummary | null>(null);

  const fetchInvoices = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) return;

      const [invoicesResponse, summaryResponse] = await Promise.all([
        getRepeatingInvoices(token, connectionId, {
          limit: pageSize,
          offset: page * pageSize,
          invoice_type: invoiceType,
          status: statusFilter,
        }),
        showSummary ? getRecurringSummary(token, connectionId) : Promise.resolve(null),
      ]);

      setInvoices(invoicesResponse.invoices);
      setTotal(invoicesResponse.total);
      if (summaryResponse) {
        setSummary(summaryResponse);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load repeating invoices');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, connectionId, pageSize, page, invoiceType, statusFilter, showSummary]);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const token = await getToken();
      if (!token) return;

      await syncRepeatingInvoices(token, connectionId);
      await fetchInvoices();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync repeating invoices');
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  const totalPages = Math.ceil(total / pageSize);

  // Loading state
  if (isLoading && invoices.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-10 h-10 text-status-danger mx-auto mb-3" />
        <p className="text-status-danger mb-2">{error}</p>
        <button
          onClick={fetchInvoices}
          className="text-sm text-primary hover:text-blue-800 font-medium"
        >
          Try again
        </button>
      </div>
    );
  }

  // Empty state
  if (invoices.length === 0) {
    return (
      <div className="text-center py-12">
        <Repeat className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium text-foreground mb-2">No repeating invoices</h3>
        <p className="text-muted-foreground mb-4">
          {invoiceType === 'ACCREC'
            ? 'No recurring sales invoices found.'
            : invoiceType === 'ACCPAY'
            ? 'No recurring bills found.'
            : 'No repeating invoices have been synced yet.'}
        </p>
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50"
        >
          {isSyncing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          Sync Repeating Invoices from Xero
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      {showSummary && summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <TrendingUp className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Monthly Revenue</p>
                <p className="text-xl font-semibold text-green-600">
                  {formatCurrency(summary.monthly_receivables)}
                </p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-100 rounded-lg">
                <TrendingDown className="w-5 h-5 text-status-danger" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Monthly Expenses</p>
                <p className="text-xl font-semibold text-status-danger">
                  {formatCurrency(summary.monthly_payables)}
                </p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <ArrowUpCircle className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Annual Revenue</p>
                <p className="text-xl font-semibold text-foreground">
                  {formatCurrency(summary.annual_receivables)}
                </p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-border rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-100 rounded-lg">
                <ArrowDownCircle className="w-5 h-5 text-status-danger" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Annual Expenses</p>
                <p className="text-xl font-semibold text-foreground">
                  {formatCurrency(summary.annual_payables)}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Header with sync button */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-foreground">
          Repeating Invoices ({total})
        </h3>
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-muted disabled:opacity-50"
        >
          {isSyncing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          Sync
        </button>
      </div>

      {/* Repeating Invoices table */}
      <div className="overflow-hidden bg-white border border-border rounded-lg">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Contact
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Schedule
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Next Date
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Amount
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {invoices.map((invoice) => (
                <tr key={invoice.id} className="hover:bg-muted">
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      <Repeat className="w-5 h-5 text-muted-foreground" />
                      <div>
                        <div className="text-sm font-medium text-foreground">
                          {invoice.contact_name || 'Unknown'}
                        </div>
                        {invoice.reference && (
                          <div className="text-xs text-muted-foreground">
                            {invoice.reference}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                        invoice.invoice_type === 'ACCREC'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-orange-100 text-orange-800'
                      }`}
                    >
                      {invoice.invoice_type === 'ACCREC' ? 'Sales' : 'Bill'}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="flex items-center gap-2 text-sm text-foreground">
                      <Calendar className="w-4 h-4 text-muted-foreground" />
                      {getScheduleDisplayText(
                        invoice.schedule_unit as ScheduleUnit,
                        invoice.schedule_period
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground">
                    {formatDate(invoice.next_scheduled_date)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-right font-medium">
                    <span
                      className={
                        invoice.invoice_type === 'ACCREC'
                          ? 'text-green-600'
                          : 'text-status-danger'
                      }
                    >
                      {formatCurrency(invoice.total)}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                        invoice.status === 'AUTHORISED'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-muted text-foreground'
                      }`}
                    >
                      {invoice.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {page * pageSize + 1} to{' '}
            {Math.min((page + 1) * pageSize, total)} of {total} invoices
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="text-sm text-muted-foreground">
              Page {page + 1} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default RepeatingInvoicesList;
