/**
 * BAS Preparation Workflow Types and API Functions
 *
 * Provides types and API functions for BAS preparation workflow.
 */

import { apiClient } from './api-client';

// =============================================================================
// Types
// =============================================================================

export type BASSessionStatus =
  | 'draft'
  | 'in_progress'
  | 'ready_for_review'
  | 'changes_requested'
  | 'approved'
  | 'lodged';

export type VarianceSeverity = 'normal' | 'warning' | 'critical';

export type LodgementMethod = 'ATO_PORTAL' | 'XERO' | 'OTHER';

export type LodgementStatus = 'pending' | 'lodged' | 'all';

export interface BASPeriod {
  id: string;
  connection_id: string;
  period_type: string;
  quarter: number | null;
  month: number | null;
  fy_year: number;
  start_date: string;
  end_date: string;
  due_date: string;
  display_name: string;
  has_session: boolean;
  session_id: string | null;
  session_status: string | null;
  created_at: string;
}

export interface BASPeriodListResponse {
  periods: BASPeriod[];
  total: number;
}

export interface BASSession {
  id: string;
  period_id: string;
  status: BASSessionStatus;
  period_display_name: string;
  quarter: number | null;
  fy_year: number;
  start_date: string;
  end_date: string;
  due_date: string;
  created_by: string;
  created_by_name: string | null;
  approved_by: string | null;
  approved_at: string | null;
  gst_calculated_at: string | null;
  payg_calculated_at: string | null;
  internal_notes: string | null;
  has_calculation: boolean;
  quality_score: string | null;
  // Auto-creation and review tracking
  auto_created: boolean;
  reviewed_by: string | null;
  reviewed_at: string | null;
  reviewed_by_name: string | null;
  // Lodgement tracking (Spec 011)
  lodged_at: string | null;
  lodged_by: string | null;
  lodged_by_name: string | null;
  lodgement_method: LodgementMethod | null;
  lodgement_method_description: string | null;
  ato_reference_number: string | null;
  lodgement_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface BASSessionListResponse {
  sessions: BASSession[];
  total: number;
}

export interface GSTBreakdown {
  g1_total_sales: string;
  g2_export_sales: string;
  g3_gst_free_sales: string;
  g10_capital_purchases: string;
  g11_non_capital_purchases: string;
  field_1a_gst_on_sales: string;
  field_1b_gst_on_purchases: string;
  gst_payable: string;
  invoice_count: number;
  transaction_count: number;
}

export interface PAYGBreakdown {
  w1_total_wages: string;
  w2_amount_withheld: string;
  pay_run_count: number;
  has_payroll: boolean;
}

export interface BASCalculation {
  id: string;
  session_id: string;
  g1_total_sales: string;
  g2_export_sales: string;
  g3_gst_free_sales: string;
  g10_capital_purchases: string;
  g11_non_capital_purchases: string;
  field_1a_gst_on_sales: string;
  field_1b_gst_on_purchases: string;
  w1_total_wages: string;
  w2_amount_withheld: string;
  gst_payable: string;
  total_payable: string;
  is_refund: boolean;
  calculated_at: string;
  calculation_duration_ms: number | null;
  transaction_count: number;
  invoice_count: number;
  pay_run_count: number;
}

export interface BASCalculateTriggerResponse {
  session_id: string;
  gst: GSTBreakdown;
  payg: PAYGBreakdown;
  total_payable: string;
  is_refund: boolean;
  calculated_at: string;
  calculation_duration_ms: number;
}

export interface BASAdjustment {
  id: string;
  session_id: string;
  field_name: string;
  adjustment_amount: string;
  reason: string;
  reference: string | null;
  created_by: string;
  created_by_name: string | null;
  created_at: string;
}

export interface BASAdjustmentListResponse {
  adjustments: BASAdjustment[];
  total: number;
}

export interface FieldVariance {
  field_name: string;
  field_label: string;
  current_value: string;
  prior_value: string | null;
  absolute_change: string | null;
  percent_change: string | null;
  severity: VarianceSeverity;
  comparison_period: string | null;
}

export interface VarianceComparison {
  comparison_type: 'prior_quarter' | 'same_quarter_prior_year';
  comparison_period_name: string | null;
  has_data: boolean;
  variances: FieldVariance[];
}

export interface VarianceAnalysisResponse {
  session_id: string;
  current_period: string;
  prior_quarter: VarianceComparison;
  same_quarter_prior_year: VarianceComparison;
}

export interface BASSummary {
  session: BASSession;
  calculation: BASCalculation | null;
  adjustments: BASAdjustment[];
  adjusted_totals: Record<string, string>;
  quality_score: string | null;
  quality_issues_count: number;
  can_approve: boolean;
  blocking_issues: string[];
}

export interface BASFieldTransaction {
  id: string;
  source: 'invoice' | 'bank_transaction';
  date: string;
  reference: string | null;
  description: string;
  contact_name: string | null;
  line_amount: string;
  tax_amount: string;
  total_amount: string;
  tax_type: string | null;
}

export interface BASFieldTransactionsResponse {
  session_id: string;
  field_name: string;
  field_label: string;
  period_start: string;
  period_end: string;
  total_amount: string;
  transaction_count: number;
  transactions: BASFieldTransaction[];
}

// =============================================================================
// Lodgement Types (Spec 011)
// =============================================================================

export interface LodgementRecordRequest {
  lodgement_date: string; // ISO date string (YYYY-MM-DD)
  lodgement_method: LodgementMethod;
  lodgement_method_description?: string;
  ato_reference_number?: string;
  lodgement_notes?: string;
}

export interface LodgementUpdateRequest {
  lodgement_method?: LodgementMethod;
  lodgement_method_description?: string;
  ato_reference_number?: string;
  lodgement_notes?: string;
}

export interface LodgementField {
  field_code: string;
  field_description: string;
  amount: string;
}

export interface LodgementSummaryResponse {
  session_id: string;
  period_display_name: string;
  lodged_at: string | null;
  lodged_by_name: string | null;
  lodgement_method: LodgementMethod | null;
  lodgement_method_description: string | null;
  ato_reference_number: string | null;
  lodgement_notes: string | null;
  fields: LodgementField[];
  total_payable: string;
  is_refund: boolean;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * List BAS periods for a client connection
 */
export async function listBASPeriods(
  token: string,
  connectionId: string,
  limit?: number
): Promise<BASPeriodListResponse> {
  const params = new URLSearchParams();
  if (limit) params.append('limit', limit.toString());

  const queryString = params.toString();
  const url = `/api/v1/clients/${connectionId}/bas/periods${queryString ? `?${queryString}` : ''}`;

  const response = await apiClient.get(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<BASPeriodListResponse>(response);
}

/**
 * Get or create a BAS period
 */
export async function getOrCreateBASPeriod(
  token: string,
  connectionId: string,
  quarter: number,
  fyYear: number
): Promise<BASPeriod> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/periods`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ quarter, fy_year: fyYear }),
    }
  );
  return apiClient.handleResponse<BASPeriod>(response);
}

/**
 * Create a BAS session for a quarter
 */
export async function createBASSession(
  token: string,
  connectionId: string,
  quarter: number,
  fyYear: number
): Promise<BASSession> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ quarter, fy_year: fyYear }),
    }
  );
  return apiClient.handleResponse<BASSession>(response);
}

/**
 * List BAS sessions for a client connection
 */
export async function listBASSessions(
  token: string,
  connectionId: string,
  limit?: number
): Promise<BASSessionListResponse> {
  const params = new URLSearchParams();
  if (limit) params.append('limit', limit.toString());

  const queryString = params.toString();
  const url = `/api/v1/clients/${connectionId}/bas/sessions${queryString ? `?${queryString}` : ''}`;

  const response = await apiClient.get(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<BASSessionListResponse>(response);
}

/**
 * Get a BAS session by ID
 */
export async function getBASSession(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<BASSession> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<BASSession>(response);
}

/**
 * Update BAS session status
 */
export async function updateBASSessionStatus(
  token: string,
  connectionId: string,
  sessionId: string,
  status: BASSessionStatus
): Promise<BASSession> {
  const response = await apiClient.patch(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ status }),
    }
  );
  return apiClient.handleResponse<BASSession>(response);
}

/**
 * Mark an auto-created BAS session as reviewed by an accountant
 */
export async function markBASSessionReviewed(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<BASSession> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/review`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<BASSession>(response);
}

/**
 * Trigger BAS calculation
 */
export async function triggerBASCalculation(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<BASCalculateTriggerResponse> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/calculate`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<BASCalculateTriggerResponse>(response);
}

/**
 * Get BAS calculation for a session
 */
export async function getBASCalculation(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<BASCalculation> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/calculation`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<BASCalculation>(response);
}

/**
 * Add an adjustment to a BAS session
 */
export async function addBASAdjustment(
  token: string,
  connectionId: string,
  sessionId: string,
  fieldName: string,
  adjustmentAmount: number,
  reason: string,
  reference?: string
): Promise<BASAdjustment> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/adjustments`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        field_name: fieldName,
        adjustment_amount: adjustmentAmount,
        reason,
        reference: reference || null,
      }),
    }
  );
  return apiClient.handleResponse<BASAdjustment>(response);
}

/**
 * List adjustments for a BAS session
 */
export async function listBASAdjustments(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<BASAdjustmentListResponse> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/adjustments`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<BASAdjustmentListResponse>(response);
}

/**
 * Delete an adjustment from a BAS session
 */
export async function deleteBASAdjustment(
  token: string,
  connectionId: string,
  sessionId: string,
  adjustmentId: string
): Promise<void> {
  const response = await apiClient.delete(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/adjustments/${adjustmentId}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  await apiClient.handleResponse(response);
}

/**
 * Get variance analysis for a BAS session
 */
export async function getBASVarianceAnalysis(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<VarianceAnalysisResponse> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/variance`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<VarianceAnalysisResponse>(response);
}

/**
 * Get BAS summary for review
 */
export async function getBASSummary(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<BASSummary> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/summary`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<BASSummary>(response);
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get status badge color classes
 */
export function getSessionStatusColor(status: BASSessionStatus): string {
  const colors: Record<BASSessionStatus, string> = {
    draft: 'bg-gray-100 text-gray-800',
    in_progress: 'bg-blue-100 text-blue-800',
    ready_for_review: 'bg-yellow-100 text-yellow-800',
    changes_requested: 'bg-orange-100 text-orange-800',
    approved: 'bg-green-100 text-green-800',
    lodged: 'bg-purple-100 text-purple-800',
  };
  return colors[status];
}

/**
 * Get status label
 */
export function getSessionStatusLabel(status: BASSessionStatus): string {
  const labels: Record<BASSessionStatus, string> = {
    draft: 'Draft',
    in_progress: 'In Progress',
    ready_for_review: 'Ready for Review',
    changes_requested: 'Changes Requested',
    approved: 'Approved',
    lodged: 'Lodged',
  };
  return labels[status];
}

/**
 * Get variance severity color classes
 */
export function getVarianceSeverityColor(severity: VarianceSeverity): string {
  const colors: Record<VarianceSeverity, string> = {
    normal: 'text-gray-600',
    warning: 'text-yellow-600',
    critical: 'text-red-600',
  };
  return colors[severity];
}

/**
 * Get variance severity background color
 */
export function getVarianceSeverityBgColor(severity: VarianceSeverity): string {
  const colors: Record<VarianceSeverity, string> = {
    normal: 'bg-gray-50',
    warning: 'bg-yellow-50',
    critical: 'bg-red-50',
  };
  return colors[severity];
}

/**
 * Format a BAS field name to human-readable label
 */
export function getBASFieldLabel(fieldName: string): string {
  const labels: Record<string, string> = {
    g1_total_sales: 'G1 Total Sales',
    g2_export_sales: 'G2 Export Sales',
    g3_gst_free_sales: 'G3 GST-Free Sales',
    g10_capital_purchases: 'G10 Capital Purchases',
    g11_non_capital_purchases: 'G11 Non-Capital Purchases',
    field_1a_gst_on_sales: '1A GST on Sales',
    field_1b_gst_on_purchases: '1B GST on Purchases',
    gst_payable: 'Net GST Payable',
    w1_total_wages: 'W1 Total Wages',
    w2_amount_withheld: 'W2 PAYG Withheld',
    total_payable: 'Total Payable',
  };
  return labels[fieldName] || fieldName;
}

/**
 * Check if session is editable (draft or in_progress)
 */
export function isSessionEditable(status: BASSessionStatus): boolean {
  return status === 'draft' || status === 'in_progress';
}

/**
 * Get allowed next status transitions
 */
export function getAllowedStatusTransitions(
  currentStatus: BASSessionStatus
): BASSessionStatus[] {
  const transitions: Record<BASSessionStatus, BASSessionStatus[]> = {
    draft: ['in_progress'],
    in_progress: ['ready_for_review', 'draft'],
    ready_for_review: ['approved', 'changes_requested'],
    changes_requested: ['ready_for_review', 'in_progress'],
    approved: ['lodged', 'in_progress'],
    lodged: [],
  };
  return transitions[currentStatus];
}

/**
 * Format currency for display
 */
export function formatBASCurrency(value: string | number): string {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
  }).format(num);
}

/**
 * Format percentage for display
 */
export function formatPercentage(value: string | number | null): string {
  if (value === null) return '-';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(1)}%`;
}

/**
 * Get lodgement method label
 */
export function getLodgementMethodLabel(method: LodgementMethod | null): string {
  if (!method) return '-';
  const labels: Record<LodgementMethod, string> = {
    ATO_PORTAL: 'ATO Business Portal',
    XERO: 'Lodged via Xero',
    OTHER: 'Other Method',
  };
  return labels[method];
}

/**
 * Get lodgement method description
 */
export function getLodgementMethodDescription(method: LodgementMethod): string {
  const descriptions: Record<LodgementMethod, string> = {
    ATO_PORTAL: 'Submit directly through the ATO Business Portal',
    XERO: 'Lodge through Xero Tax integration',
    OTHER: 'Third-party software or tax agent portal',
  };
  return descriptions[method];
}

/**
 * Check if session can be lodged
 */
export function canRecordLodgement(session: BASSession): boolean {
  return session.status === 'approved' && !session.lodged_at;
}

/**
 * Check if session can be submitted for review
 */
export function canSubmitForReview(status: BASSessionStatus): boolean {
  return status === 'in_progress' || status === 'changes_requested';
}

/**
 * Check if session is in review state
 */
export function isInReviewState(status: BASSessionStatus): boolean {
  return status === 'ready_for_review';
}

/**
 * Check if session is lodged
 */
export function isSessionLodged(session: BASSession): boolean {
  return session.status === 'lodged' || !!session.lodged_at;
}

export type ExportFormat = 'pdf' | 'excel' | 'csv';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Export BAS working papers as PDF or Excel
 * Downloads the file directly to the browser
 */
export async function exportBASWorkingPapers(
  token: string,
  connectionId: string,
  sessionId: string,
  format: ExportFormat = 'pdf'
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/export?format=${format}`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Export failed: ${response.statusText}`);
  }

  // Get filename from Content-Disposition header
  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `BAS_Working_Paper.${format === 'pdf' ? 'pdf' : 'xlsx'}`;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="(.+)"/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  // Download the file
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

/**
 * Get transactions that contribute to a specific BAS field
 */
export async function getBASFieldTransactions(
  token: string,
  connectionId: string,
  sessionId: string,
  fieldName: string
): Promise<BASFieldTransactionsResponse> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/transactions/${fieldName}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<BASFieldTransactionsResponse>(response);
}

// =============================================================================
// Lodgement API Functions (Spec 011)
// =============================================================================

/**
 * Record lodgement for an approved BAS session
 */
export async function recordLodgement(
  token: string,
  connectionId: string,
  sessionId: string,
  request: LodgementRecordRequest
): Promise<BASSession> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/lodgement`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }
  );
  return apiClient.handleResponse<BASSession>(response);
}

/**
 * Update lodgement details for a lodged BAS session
 */
export async function updateLodgementDetails(
  token: string,
  connectionId: string,
  sessionId: string,
  request: LodgementUpdateRequest
): Promise<BASSession> {
  const response = await apiClient.patch(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/lodgement`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }
  );
  return apiClient.handleResponse<BASSession>(response);
}

/**
 * Get lodgement summary for a BAS session
 */
export async function getLodgementSummary(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<LodgementSummaryResponse> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/lodgement`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<LodgementSummaryResponse>(response);
}

/**
 * Export BAS with lodgement summary (enhanced export)
 */
export async function exportBASWithLodgementSummary(
  token: string,
  connectionId: string,
  sessionId: string,
  format: ExportFormat = 'pdf'
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/export?format=${format}&include_lodgement_summary=true`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Export failed: ${response.statusText}`);
  }

  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `BAS_Lodgement_Summary.${format === 'pdf' ? 'pdf' : 'xlsx'}`;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="(.+)"/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

/**
 * Export BAS as CSV format
 */
export async function exportBASAsCSV(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/export?format=csv`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Export failed: ${response.statusText}`);
  }

  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `BAS_Export.csv`;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="(.+)"/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

// =============================================================================
// Review Workflow API Functions (Spec 010)
// =============================================================================

/**
 * Submit a BAS session for review
 */
export async function submitForReview(
  token: string,
  connectionId: string,
  sessionId: string,
  notes?: string
): Promise<BASSession> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/submit-for-review`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ notes: notes || null }),
    }
  );
  return apiClient.handleResponse<BASSession>(response);
}

/**
 * Approve a BAS session
 */
export async function approveBASSession(
  token: string,
  connectionId: string,
  sessionId: string,
  notes?: string
): Promise<BASSession> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/approve`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ notes: notes || null }),
    }
  );
  return apiClient.handleResponse<BASSession>(response);
}

/**
 * Request changes on a BAS session
 */
export async function requestChanges(
  token: string,
  connectionId: string,
  sessionId: string,
  feedback: string
): Promise<BASSession> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/request-changes`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ feedback }),
    }
  );
  return apiClient.handleResponse<BASSession>(response);
}

/**
 * Reopen an approved BAS session
 */
export async function reopenBASSession(
  token: string,
  connectionId: string,
  sessionId: string,
  reason?: string
): Promise<BASSession> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/reopen`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ reason: reason || null }),
    }
  );
  return apiClient.handleResponse<BASSession>(response);
}

// =============================================================================
// Tax Code Suggestion Types & API (Spec 046)
// =============================================================================

export interface TaxCodeSuggestion {
  id: string;
  source_type: 'invoice' | 'bank_transaction' | 'credit_note';
  source_id: string;
  line_item_index: number;
  line_item_id: string | null;
  original_tax_type: string;
  suggested_tax_type: string | null;
  applied_tax_type: string | null;
  confidence_score: number | null;
  confidence_tier: string | null;
  suggestion_basis: string | null;
  status: 'pending' | 'approved' | 'rejected' | 'overridden' | 'dismissed';
  resolved_by: string | null;
  resolved_at: string | null;
  dismissal_reason: string | null;
  account_code: string | null;
  account_name: string | null;
  description: string | null;
  line_amount: number | null;
  tax_amount: number | null;
  contact_name: string | null;
  transaction_date: string | null;
}

export interface TaxCodeSuggestionSummary {
  excluded_count: number;
  excluded_amount: number;
  resolved_count: number;
  unresolved_count: number;
  has_suggestions: boolean;
  high_confidence_pending: number;
  can_bulk_approve: boolean;
  blocks_approval: boolean;
}

export interface TaxCodeSuggestionListResponse {
  suggestions: TaxCodeSuggestion[];
  summary: TaxCodeSuggestionSummary;
}

export interface GenerateSuggestionsResult {
  generated: number;
  skipped_already_resolved: number;
  breakdown: Record<string, number>;
}

export interface BulkApproveResult {
  approved_count: number;
  suggestion_ids: string[];
}

export interface SuggestionResolution {
  id: string;
  status: string;
  applied_tax_type: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
}

export interface RecalculateResult {
  applied_count: number;
  recalculation: Record<string, number>;
}

/**
 * Get tax code suggestion summary for the exclusion banner
 */
export async function getTaxCodeSuggestionSummary(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<TaxCodeSuggestionSummary> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/summary`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<TaxCodeSuggestionSummary>(response);
}

/**
 * List tax code suggestions with optional filters
 */
export async function listTaxCodeSuggestions(
  token: string,
  connectionId: string,
  sessionId: string,
  filters?: { status?: string; confidence_tier?: string; min_confidence?: number }
): Promise<TaxCodeSuggestionListResponse> {
  const params = new URLSearchParams();
  if (filters?.status) params.append('status', filters.status);
  if (filters?.confidence_tier) params.append('confidence_tier', filters.confidence_tier);
  if (filters?.min_confidence !== undefined)
    params.append('min_confidence', filters.min_confidence.toString());

  const qs = params.toString();
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions${qs ? `?${qs}` : ''}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<TaxCodeSuggestionListResponse>(response);
}

/**
 * Generate tax code suggestions for excluded transactions
 */
export async function generateTaxCodeSuggestions(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<GenerateSuggestionsResult> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/generate`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    }
  );
  return apiClient.handleResponse<GenerateSuggestionsResult>(response);
}

/**
 * Approve a single suggestion
 */
export async function approveSuggestion(
  token: string,
  connectionId: string,
  sessionId: string,
  suggestionId: string,
  notes?: string
): Promise<SuggestionResolution> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/${suggestionId}/approve`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes: notes || null }),
    }
  );
  return apiClient.handleResponse<SuggestionResolution>(response);
}

/**
 * Reject a suggestion
 */
export async function rejectSuggestion(
  token: string,
  connectionId: string,
  sessionId: string,
  suggestionId: string,
  reason?: string
): Promise<SuggestionResolution> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/${suggestionId}/reject`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason || null }),
    }
  );
  return apiClient.handleResponse<SuggestionResolution>(response);
}

/**
 * Override a suggestion with a different tax code
 */
export async function overrideSuggestion(
  token: string,
  connectionId: string,
  sessionId: string,
  suggestionId: string,
  taxType: string,
  reason?: string
): Promise<SuggestionResolution> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/${suggestionId}/override`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ tax_type: taxType, reason: reason || null }),
    }
  );
  return apiClient.handleResponse<SuggestionResolution>(response);
}

/**
 * Dismiss a suggestion (confirm exclusion is correct)
 */
export async function dismissSuggestion(
  token: string,
  connectionId: string,
  sessionId: string,
  suggestionId: string,
  reason?: string
): Promise<SuggestionResolution> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/${suggestionId}/dismiss`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason || null }),
    }
  );
  return apiClient.handleResponse<SuggestionResolution>(response);
}

/**
 * Bulk approve high-confidence suggestions
 */
export async function bulkApproveSuggestions(
  token: string,
  connectionId: string,
  sessionId: string,
  minConfidence?: number,
  confidenceTier?: string
): Promise<BulkApproveResult> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/bulk-approve`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        min_confidence: minConfidence ?? null,
        confidence_tier: confidenceTier ?? null,
      }),
    }
  );
  return apiClient.handleResponse<BulkApproveResult>(response);
}

/**
 * Apply approved suggestions and recalculate BAS
 */
export async function recalculateBASWithSuggestions(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<RecalculateResult> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/recalculate`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    }
  );
  return apiClient.handleResponse<RecalculateResult>(response);
}

/** Valid tax types for override dropdown (non-excluded from TAX_TYPE_MAPPING) */
export const VALID_TAX_TYPES = [
  { value: 'OUTPUT', label: 'GST on Sales (OUTPUT)', group: 'Sales' },
  { value: 'OUTPUT2', label: 'GST on Sales 2 (OUTPUT2)', group: 'Sales' },
  { value: 'INPUT', label: 'GST on Purchases (INPUT)', group: 'Purchases' },
  { value: 'INPUT2', label: 'GST on Purchases 2 (INPUT2)', group: 'Purchases' },
  { value: 'INPUT3', label: 'GST on Purchases 3 (INPUT3)', group: 'Purchases' },
  { value: 'INPUTTAXED', label: 'Input Taxed (INPUTTAXED)', group: 'Purchases' },
  { value: 'CAPEXINPUT', label: 'Capital Purchase (CAPEXINPUT)', group: 'Capital' },
  { value: 'CAPEXINPUT2', label: 'Capital Purchase 2 (CAPEXINPUT2)', group: 'Capital' },
  { value: 'EXEMPTOUTPUT', label: 'GST-Free Sale (EXEMPTOUTPUT)', group: 'Exempt' },
  { value: 'EXEMPTINCOME', label: 'GST-Free Income (EXEMPTINCOME)', group: 'Exempt' },
  { value: 'EXEMPTEXPENSES', label: 'GST-Free Expense (EXEMPTEXPENSES)', group: 'Exempt' },
  { value: 'EXEMPTEXPORT', label: 'Export Sale (EXEMPTEXPORT)', group: 'Export' },
  { value: 'GSTONEXPORTS', label: 'GST on Exports (GSTONEXPORTS)', group: 'Export' },
  { value: 'ZERORATEDINPUT', label: 'Zero-Rated Input (ZERORATEDINPUT)', group: 'Zero-Rated' },
  { value: 'ZERORATEDOUTPUT', label: 'Zero-Rated Output (ZERORATEDOUTPUT)', group: 'Zero-Rated' },
] as const;
