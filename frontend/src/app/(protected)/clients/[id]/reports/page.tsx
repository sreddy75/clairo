'use client';

/**
 * Client Reports Page
 *
 * Displays financial reports for a client/Xero connection.
 * Supports P&L, Balance Sheet, and other Xero Reports API data.
 *
 * Spec 023: Xero Reports API Integration
 */

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  ArrowLeft,
  BarChart3,
  FileText,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import {
  AgedPayablesReport,
  AgedReceivablesReport,
  BalanceSheetReport,
  BankSummaryReport,
  PeriodSelector,
  ProfitLossReport,
  ReportSelector,
  TrialBalanceReport,
} from '@/components/integrations/xero';
import type { ReportListResponse, ReportResponse, XeroReportType } from '@/lib/xero-reports';
import {
  getReport,
  listReports,
  RateLimitExceededError,
  refreshReport,
} from '@/lib/xero-reports';

// =============================================================================
// Types
// =============================================================================

interface ClientBasic {
  id: string;
  organization_name: string;
}

// =============================================================================
// Page Component
// =============================================================================

export default function ClientReportsPage() {
  const { getToken } = useAuth();
  const params = useParams();
  const clientId = params.id as string;

  // State
  const [client, setClient] = useState<ClientBasic | null>(null);
  const [reportList, setReportList] = useState<ReportListResponse | null>(null);
  const [selectedReportType, setSelectedReportType] = useState<XeroReportType | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState<string>('current');
  const [currentReport, setCurrentReport] = useState<ReportResponse | null>(null);

  // Loading states
  const [isLoadingClient, setIsLoadingClient] = useState(true);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Error states
  const [clientError, setClientError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  // Fetch client basic info
  const fetchClient = useCallback(async () => {
    try {
      setIsLoadingClient(true);
      setClientError(null);

      const token = await getToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/integrations/xero/connections/${clientId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to load client');
      }

      const data = await response.json();
      setClient({
        id: data.id,
        organization_name: data.organization_name,
      });
    } catch (err) {
      setClientError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoadingClient(false);
    }
  }, [clientId, getToken]);

  // Fetch report list
  const fetchReportList = useCallback(async () => {
    try {
      setIsLoadingList(true);
      setListError(null);

      const token = await getToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const data = await listReports(token, clientId);
      setReportList(data);

      // Auto-select first available report if none selected
      if (!selectedReportType && data.reports.length > 0) {
        const firstAvailable = data.reports.find((r) => r.is_available);
        if (firstAvailable) {
          setSelectedReportType(firstAvailable.report_type);
        }
      }
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoadingList(false);
    }
  }, [clientId, getToken, selectedReportType]);

  // Fetch a specific report
  const fetchReport = useCallback(async () => {
    if (!selectedReportType) return;

    try {
      setIsLoadingReport(true);
      setReportError(null);

      const token = await getToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const data = await getReport(token, clientId, selectedReportType, selectedPeriod);
      setCurrentReport(data);
    } catch (err) {
      if (err instanceof RateLimitExceededError) {
        setReportError(err.message);
      } else {
        setReportError(err instanceof Error ? err.message : 'Unknown error');
      }
    } finally {
      setIsLoadingReport(false);
    }
  }, [clientId, getToken, selectedReportType, selectedPeriod]);

  // Refresh report
  const handleRefresh = useCallback(async () => {
    if (!selectedReportType) return;

    try {
      setIsRefreshing(true);
      setReportError(null);

      const token = await getToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const data = await refreshReport(token, clientId, selectedReportType, selectedPeriod);
      setCurrentReport(data);

      // Also refresh the list to update sync statuses
      await fetchReportList();
    } catch (err) {
      if (err instanceof RateLimitExceededError) {
        setReportError(err.message);
      } else {
        setReportError(err instanceof Error ? err.message : 'Failed to refresh');
      }
    } finally {
      setIsRefreshing(false);
    }
  }, [clientId, getToken, selectedReportType, selectedPeriod, fetchReportList]);

  // Load client and report list on mount
  useEffect(() => {
    fetchClient();
    fetchReportList();
  }, [fetchClient, fetchReportList]);

  // Load report when selection changes
  useEffect(() => {
    if (selectedReportType) {
      fetchReport();
    }
  }, [selectedReportType, selectedPeriod, fetchReport]);

  // Note: We don't pass availablePeriods to PeriodSelector so users can select any period.
  // The backend will fetch from Xero on-demand if the period isn't cached.

  // =============================================================================
  // Render
  // =============================================================================

  if (isLoadingClient) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (clientError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <AlertCircle className="h-12 w-12 text-status-danger" />
        <p className="text-status-danger">{clientError}</p>
        <Link
          href="/clients"
          className="text-primary hover:underline flex items-center gap-1"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Clients
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background pb-12">
      {/* Header */}
      <div className="bg-card border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link
              href={`/clients/${clientId}`}
              className="text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Link href="/clients" className="hover:underline">
                  Clients
                </Link>
                <span>/</span>
                <Link href={`/clients/${clientId}`} className="hover:underline">
                  {client?.organization_name || 'Client'}
                </Link>
                <span>/</span>
                <span>Reports</span>
              </div>
              <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                <BarChart3 className="h-6 w-6" />
                Financial Reports
              </h1>
            </div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="bg-card rounded-lg shadow-sm border p-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Report:</span>
              <ReportSelector
                value={selectedReportType}
                onChange={setSelectedReportType}
                reportStatuses={reportList?.reports}
                disabled={isLoadingList}
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Period:</span>
              {selectedReportType && (
                <PeriodSelector
                  value={selectedPeriod}
                  onChange={setSelectedPeriod}
                  reportType={selectedReportType}
                  disabled={isLoadingReport}
                />
              )}
            </div>

            <button
              onClick={handleRefresh}
              disabled={isRefreshing || !selectedReportType}
              className="ml-auto inline-flex items-center px-3 py-2 border border-border rounded-md text-sm font-medium text-foreground bg-card hover:bg-muted disabled:opacity-50"
            >
              <RefreshCw
                className={`h-4 w-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`}
              />
              Refresh from Xero
            </button>
          </div>

          {listError && (
            <div className="mt-4 flex items-center gap-2 text-sm text-status-warning">
              <AlertCircle className="h-4 w-4" />
              {listError}
            </div>
          )}
        </div>
      </div>

      {/* Report Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {!selectedReportType ? (
          <div className="bg-card rounded-lg shadow-sm border p-8 text-center">
            <BarChart3 className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
            <p className="text-muted-foreground">Select a report type to view</p>
          </div>
        ) : selectedReportType === 'profit_and_loss' ? (
          <ProfitLossReport
            report={currentReport}
            isLoading={isLoadingReport}
            error={reportError}
            onRefresh={handleRefresh}
            isRefreshing={isRefreshing}
          />
        ) : selectedReportType === 'balance_sheet' ? (
          <BalanceSheetReport
            report={currentReport}
            isLoading={isLoadingReport}
            error={reportError}
            onRefresh={handleRefresh}
            isRefreshing={isRefreshing}
          />
        ) : selectedReportType === 'aged_receivables_by_contact' ? (
          <AgedReceivablesReport
            report={currentReport}
            isLoading={isLoadingReport}
            error={reportError}
            onRefresh={handleRefresh}
            isRefreshing={isRefreshing}
          />
        ) : selectedReportType === 'aged_payables_by_contact' ? (
          <AgedPayablesReport
            report={currentReport}
            isLoading={isLoadingReport}
            error={reportError}
            onRefresh={handleRefresh}
            isRefreshing={isRefreshing}
          />
        ) : selectedReportType === 'trial_balance' ? (
          <TrialBalanceReport
            report={currentReport}
            isLoading={isLoadingReport}
            error={reportError}
            onRefresh={handleRefresh}
            isRefreshing={isRefreshing}
          />
        ) : selectedReportType === 'bank_summary' ? (
          <BankSummaryReport
            report={currentReport}
            isLoading={isLoadingReport}
            error={reportError}
            onRefresh={handleRefresh}
            isRefreshing={isRefreshing}
          />
        ) : (
          // Fallback for budget_summary or unknown types
          <div className="bg-card rounded-lg shadow-sm border p-8">
            <div className="text-center">
              <FileText className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-2">
                {selectedReportType.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
              </h3>
              <p className="text-muted-foreground mb-4">
                Report viewer coming soon
              </p>
              {currentReport && (
                <div className="text-left max-w-2xl mx-auto">
                  <h4 className="text-sm font-medium text-foreground mb-2">Raw Data:</h4>
                  <pre className="bg-muted p-4 rounded text-xs overflow-auto max-h-96">
                    {JSON.stringify(currentReport.summary, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
