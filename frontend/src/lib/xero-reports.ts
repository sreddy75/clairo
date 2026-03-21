/**
 * Xero Reports API Client
 *
 * Provides types and API functions for Xero financial reports.
 * Spec 023: Xero Reports API Integration
 */

import { apiClient } from './api-client';

// =============================================================================
// Types
// =============================================================================

export type XeroReportType =
  | 'profit_and_loss'
  | 'balance_sheet'
  | 'aged_receivables_by_contact'
  | 'aged_payables_by_contact'
  | 'trial_balance'
  | 'bank_summary'
  | 'budget_summary';

export const REPORT_TYPE_DISPLAY_NAMES: Record<XeroReportType, string> = {
  profit_and_loss: 'Profit & Loss',
  balance_sheet: 'Balance Sheet',
  aged_receivables_by_contact: 'Aged Receivables',
  aged_payables_by_contact: 'Aged Payables',
  trial_balance: 'Trial Balance',
  bank_summary: 'Bank Summary',
  budget_summary: 'Budget Summary',
};

export interface ReportCell {
  value: string | null;
  attributes: Array<{ [key: string]: string }>;
}

export interface ReportRow {
  row_type: 'Header' | 'Section' | 'Row' | 'SummaryRow';
  title?: string;
  cells: ReportCell[];
  rows: ReportRow[];
}

export interface ReportSummary {
  [key: string]: number | string | boolean | null | undefined | unknown[];
}

export interface ProfitAndLossSummary extends ReportSummary {
  revenue: number;
  other_income: number;
  total_income: number;
  cost_of_sales: number;
  gross_profit: number;
  operating_expenses: number;
  total_expenses: number;
  operating_profit: number;
  net_profit: number;
  gross_margin_pct?: number | null;
  net_margin_pct?: number | null;
  expense_ratio_pct?: number | null;
}

export interface BalanceSheetSummary extends ReportSummary {
  current_assets: number;
  non_current_assets: number;
  total_assets: number;
  current_liabilities: number;
  non_current_liabilities: number;
  total_liabilities: number;
  equity: number;
  current_ratio?: number | null;
  debt_to_equity?: number | null;
}

export interface AgedReceivablesSummary extends ReportSummary {
  total: number;
  current: number;
  overdue_30: number;
  overdue_60: number;
  overdue_90: number;
  overdue_90_plus: number;
  overdue_total: number;
  overdue_pct?: number | null;
  high_risk_contacts: Array<{
    name: string;
    amount: number;
  }>;
}

export interface AgedPayablesSummary extends ReportSummary {
  total: number;
  current: number;
  overdue_30: number;
  overdue_60: number;
  overdue_90: number;
  overdue_90_plus: number;
  overdue_total: number;
}

export interface TrialBalanceSummary extends ReportSummary {
  total_debits: number;
  total_credits: number;
  is_balanced: boolean;
  account_count: number;
}

export interface BankSummarySummary extends ReportSummary {
  total_opening: number;
  total_received: number;
  total_spent: number;
  total_closing: number;
  net_movement: number;
  account_count: number;
}

export interface ReportResponse {
  id: string;
  report_type: XeroReportType;
  report_name: string;
  report_titles: string[];
  period_key: string;
  period_start: string | null;
  period_end: string | null;
  as_of_date: string | null;
  summary: ReportSummary;
  rows: ReportRow[];
  fetched_at: string;
  cache_expires_at: string;
  is_current_period: boolean;
  is_stale: boolean;
}

export interface ReportStatusItem {
  report_type: XeroReportType;
  display_name: string;
  is_available: boolean;
  last_synced_at: string | null;
  is_stale: boolean;
  sync_status: string | null;
  periods_available: string[];
}

export interface ReportListResponse {
  connection_id: string;
  organization_name: string;
  reports: ReportStatusItem[];
}

export interface RefreshReportRequest {
  period_key: string;
  force?: boolean;
}

export interface RateLimitError {
  error: string;
  message: string;
  retry_after_seconds: number;
  last_sync_at: string | null;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * List available reports for a Xero connection
 */
export async function listReports(
  token: string,
  connectionId: string
): Promise<ReportListResponse> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/reports`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<ReportListResponse>(response);
}

/**
 * Get a specific report by type and period
 */
export async function getReport(
  token: string,
  connectionId: string,
  reportType: XeroReportType,
  period: string = 'current',
  forceRefresh: boolean = false
): Promise<ReportResponse> {
  const params = new URLSearchParams({
    period,
    force_refresh: forceRefresh.toString(),
  });

  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/reports/${reportType}?${params}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<ReportResponse>(response);
}

/**
 * Request a refresh of a specific report
 */
export async function refreshReport(
  token: string,
  connectionId: string,
  reportType: XeroReportType,
  periodKey: string
): Promise<ReportResponse> {
  const request: RefreshReportRequest = { period_key: periodKey };

  const response = await apiClient.post(
    `/api/v1/integrations/xero/connections/${connectionId}/reports/${reportType}/refresh`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }
  );

  // Check for rate limit error
  if (response.status === 429) {
    const responseData = await response.json();
    // FastAPI wraps error in {detail: {...}}
    const errorData = (responseData.detail || responseData) as RateLimitError;
    throw new RateLimitExceededError(errorData);
  }

  return apiClient.handleResponse<ReportResponse>(response);
}

// =============================================================================
// Error Classes
// =============================================================================

export class RateLimitExceededError extends Error {
  retryAfterSeconds: number;
  lastSyncAt: string | null;

  constructor(errorData: RateLimitError) {
    super(errorData.message);
    this.name = 'RateLimitExceededError';
    this.retryAfterSeconds = errorData.retry_after_seconds;
    this.lastSyncAt = errorData.last_sync_at;
  }
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get display name for a report type
 */
export function getReportDisplayName(reportType: XeroReportType): string {
  return REPORT_TYPE_DISPLAY_NAMES[reportType] || reportType;
}

/**
 * Check if report data is stale
 */
export function isReportStale(cacheExpiresAt: string): boolean {
  return new Date(cacheExpiresAt) < new Date();
}

/**
 * Format a period key for display
 */
export function formatPeriodKey(periodKey: string): string {
  // Handle financial year (YYYY-FY)
  if (periodKey.endsWith('-FY')) {
    const year = periodKey.split('-')[0];
    return `FY ${year}`;
  }

  // Handle quarter (YYYY-QN)
  if (periodKey.includes('-Q')) {
    const [year, quarter] = periodKey.split('-Q');
    return `Q${quarter} ${year}`;
  }

  // Handle month (YYYY-MM)
  if (periodKey.length === 7) {
    const parts = periodKey.split('-');
    const year = parts[0] || '2024';
    const month = parts[1] || '01';
    const date = new Date(parseInt(year), parseInt(month) - 1);
    return date.toLocaleDateString('en-AU', { month: 'short', year: 'numeric' });
  }

  // Handle date (YYYY-MM-DD)
  if (periodKey.length === 10) {
    const date = new Date(periodKey);
    return date.toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  }

  return periodKey;
}

/**
 * Generate period options for a report type
 */
export function generatePeriodOptions(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _reportType: XeroReportType
): Array<{ value: string; label: string }> {
  const now = new Date();
  const options: Array<{ value: string; label: string }> = [];

  // Current period
  options.push({ value: 'current', label: 'Current Period' });

  // Last 6 months
  for (let i = 0; i < 6; i++) {
    const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    const label = date.toLocaleDateString('en-AU', { month: 'short', year: 'numeric' });
    options.push({ value, label });
  }

  // Last 4 quarters
  const currentQuarter = Math.floor(now.getMonth() / 3) + 1;
  for (let i = 0; i < 4; i++) {
    let quarter = currentQuarter - i;
    let year = now.getFullYear();
    while (quarter <= 0) {
      quarter += 4;
      year -= 1;
    }
    const value = `${year}-Q${quarter}`;
    const label = `Q${quarter} ${year}`;
    options.push({ value, label });
  }

  // Last 2 financial years (Australian FY July-June)
  const currentFY = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
  for (let i = 0; i < 2; i++) {
    const fy = currentFY - i;
    options.push({ value: `${fy}-FY`, label: `FY ${fy}/${fy + 1}` });
  }

  return options;
}

/**
 * Format currency value for display
 */
export function formatCurrency(
  value: number | undefined | null,
  locale: string = 'en-AU',
  currency: string = 'AUD'
): string {
  if (value === undefined || value === null) return '-';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Format percentage for display
 */
export function formatPercentage(
  value: number | undefined | null,
  decimals: number = 1
): string {
  if (value === undefined || value === null) return '-';
  return `${value.toFixed(decimals)}%`;
}
