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
  // Spec 049: count of approved overrides not yet synced to Xero
  approved_unsynced_count: number;
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
// Writeback Types (Spec 049)
// =============================================================================

export type WritebackJobStatus = 'pending' | 'in_progress' | 'completed' | 'partial' | 'failed';
export type WritebackItemStatus = 'pending' | 'success' | 'skipped' | 'failed';
export type WritebackSkipReason =
  | 'voided'
  | 'deleted'
  | 'period_locked'
  | 'reconciled'
  | 'authorised_locked'
  | 'credit_note_applied'
  | 'invalid_tax_type'
  | 'conflict_changed';

export interface WritebackTransactionContext {
  contact_name: string | null;
  transaction_date: string | null;
  description: string | null;
  total_line_amount: number | null;
}

export interface WritebackItemResponse {
  id: string;
  xero_document_id: string;
  local_document_id: string;
  source_type: string;
  status: WritebackItemStatus;
  skip_reason: WritebackSkipReason | null;
  error_detail: string | null;
  xero_http_status: number | null;
  before_tax_types: Record<string, string> | null;
  after_tax_types: Record<string, string> | null;
  processed_at: string | null;
  override_ids: string[];
  transaction_context: WritebackTransactionContext | null;
}

export interface WritebackJobResponse {
  id: string;
  session_id: string;
  status: WritebackJobStatus;
  total_count: number;
  succeeded_count: number;
  skipped_count: number;
  failed_count: number;
  triggered_by: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  created_at: string;
}

export interface WritebackJobDetailResponse extends WritebackJobResponse {
  items: WritebackItemResponse[];
}

// =============================================================================
// Send-Back Types (Spec 049)
// =============================================================================

export interface AgentNoteResponse {
  id: string;
  classification_id: string;
  note_text: string;
  is_send_back_comment: boolean;
  created_by: string;
  created_by_name: string | null;
  created_at: string;
}

export interface SendBackItem {
  classification_id: string;
  agent_comment: string;
}

export interface SendBackResponse {
  new_request_id: string;
  client_email: string;
  expires_at: string;
  round_number: number;
  items_sent_back: number;
}

export interface ClassificationRoundResponse {
  round_number: number;
  agent_comment: string | null;
  client_response_category: string | null;
  client_response_description: string | null;
  client_classified_at: string | null;
  request_id: string;
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
// Writeback API Functions (Spec 049)
// =============================================================================

export async function initiateWriteback(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<WritebackJobResponse> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/writeback`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<WritebackJobResponse>(response);
}

export async function listWritebackJobs(
  token: string,
  connectionId: string,
  sessionId: string
): Promise<WritebackJobResponse[]> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/writeback/jobs`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<WritebackJobResponse[]>(response);
}

export async function getWritebackJob(
  token: string,
  connectionId: string,
  sessionId: string,
  jobId: string
): Promise<WritebackJobDetailResponse> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/writeback/jobs/${jobId}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<WritebackJobDetailResponse>(response);
}

export async function retryWritebackJob(
  token: string,
  connectionId: string,
  sessionId: string,
  jobId: string
): Promise<WritebackJobResponse> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/writeback/jobs/${jobId}/retry`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<WritebackJobResponse>(response);
}

// =============================================================================
// Send-Back API Functions (Spec 049)
// =============================================================================

export async function sendItemsBack(
  token: string,
  connectionId: string,
  sessionId: string,
  requestId: string,
  items: SendBackItem[]
): Promise<SendBackResponse> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/classification-requests/${requestId}/send-back`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    }
  );
  return apiClient.handleResponse<SendBackResponse>(response);
}

export async function listAgentNotes(
  token: string,
  connectionId: string,
  sessionId: string,
  requestId: string
): Promise<AgentNoteResponse[]> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/classification-requests/${requestId}/notes`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<AgentNoteResponse[]>(response);
}

export async function getTransactionRounds(
  token: string,
  connectionId: string,
  sessionId: string,
  sourceType: string,
  docId: string,
  lineItemIndex: number
): Promise<ClassificationRoundResponse[]> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/transactions/${sourceType}/${docId}/${lineItemIndex}/rounds`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return apiClient.handleResponse<ClassificationRoundResponse[]>(response);
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
  note_text: string | null;
  note_updated_by: string | null;
  note_updated_by_name: string | null;
  note_updated_at: string | null;
  account_code: string | null;
  account_name: string | null;
  description: string | null;
  line_amount: number | null;
  tax_amount: number | null;
  contact_name: string | null;
  transaction_date: string | null;
  is_reconciled: boolean | null;
  auto_park_reason: string | null;
}

/**
 * Save or update a note on a suggestion.
 */
export async function saveNote(
  token: string,
  connectionId: string,
  sessionId: string,
  suggestionId: string,
  noteText: string,
  syncToXero: boolean = false,
): Promise<SuggestionNoteResponse> {
  const response = await apiClient.put(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/${suggestionId}/note`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ note_text: noteText, sync_to_xero: syncToXero }),
    },
  );
  return apiClient.handleResponse<SuggestionNoteResponse>(response);
}

/**
 * Delete a note from a suggestion.
 */
export async function deleteNote(
  token: string,
  connectionId: string,
  sessionId: string,
  suggestionId: string,
): Promise<void> {
  const response = await apiClient.delete(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/${suggestionId}/note`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!response.ok && response.status !== 204) {
    await apiClient.handleResponse(response);
  }
}

export interface SuggestionNoteResponse {
  suggestion_id: string;
  note_text: string;
  note_updated_by: string | null;
  note_updated_by_name: string | null;
  note_updated_at: string | null;
}

/**
 * Xero BAS cross-check data.
 */
export interface XeroBASCrossCheckResponse {
  xero_report_found: boolean | null;
  xero_figures: {
    label_1a_gst_on_sales: number;
    label_1b_gst_on_purchases: number;
    net_gst: number;
  } | null;
  clairo_figures: {
    label_1a_gst_on_sales: number;
    label_1b_gst_on_purchases: number;
    net_gst: number;
  } | null;
  differences: Record<string, { xero: number; clairo: number; delta: number; material: boolean }> | null;
  period_label: string;
  fetched_at: string;
  xero_error?: string;
}

/**
 * Spec 057: Refresh Xero reconciliation status for all bank-transaction suggestions.
 * Re-fetches is_reconciled from local DB and reclassifies auto-parked suggestions.
 */
export async function refreshReconciliationStatus(
  token: string,
  connectionId: string,
  sessionId: string,
): Promise<{ reclassified_count: number; newly_reconciled: number; newly_unreconciled: number }> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/refresh-reconciliation`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  const body = await apiClient.handleResponse<{ data: { reclassified_count: number; newly_reconciled: number; newly_unreconciled: number } }>(response);
  return body.data;
}

/**
 * Fetch Xero BAS cross-check for a session.
 */
export async function getXeroBASCrossCheck(
  token: string,
  connectionId: string,
  sessionId: string,
  forceRefresh = false,
): Promise<XeroBASCrossCheckResponse> {
  const url = forceRefresh
    ? `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/xero-crosscheck?force_refresh=true`
    : `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/xero-crosscheck`;
  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<XeroBASCrossCheckResponse>(response);
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
  // Spec 057: Reconciliation grouping counts
  reconciled_count: number;
  reconciled_needs_review_count: number;
  auto_parked_count: number;
}

/** Lightweight bank transaction for period-level reconciliation view (Spec 057). */
export interface PeriodBankTransaction {
  id: string;
  transaction_date: string | null;
  total_amount: number;
  description: string | null;
  contact_name: string | null;
  is_reconciled: boolean;
  tax_types: string[];
  has_suggestion: boolean;
}

export interface TaxCodeSuggestionListResponse {
  suggestions: TaxCodeSuggestion[];
  summary: TaxCodeSuggestionSummary;
  /** ALL bank transactions for the period, regardless of tax code status (Spec 057). */
  period_bank_transactions: PeriodBankTransaction[];
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
 * @deprecated Spec 056: Use dismissSuggestion instead. This endpoint maps to dismiss internally.
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
 * Unpark a suggestion — return to Manual Required (pending).
 */
export async function unparkSuggestion(
  token: string,
  connectionId: string,
  sessionId: string,
  suggestionId: string,
): Promise<SuggestionResolution> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/tax-code-suggestions/${suggestionId}/unpark`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
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

/**
 * Fetch the active tax types configured for this Xero org.
 * Falls back to an empty array on error — caller should use VALID_TAX_TYPES as fallback.
 */
export async function fetchOrgTaxTypes(
  token: string,
  connectionId: string,
): Promise<{ tax_type: string; name: string }[]> {
  try {
    const response = await apiClient.get(
      `/api/v1/clients/${connectionId}/xero/tax-rates`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    const data = await apiClient.handleResponse<{ tax_types: { tax_type: string; name: string }[] }>(response);
    return data.tax_types;
  } catch {
    return [];
  }
}

// =============================================================================
// Split overrides (Spec 049 US10/US11)
// =============================================================================

export type WritebackStatus = 'pending_sync' | 'synced' | 'failed' | 'skipped';

export interface XeroLineItemView {
  index: number;
  tax_type: string | null;
  line_amount: string | null;
  description: string | null;
  account_code: string | null;
}

export interface TransactionSplitsResponse {
  original_line_items: XeroLineItemView[];
  overrides: TaxCodeOverrideWithSplit[];
}

export interface TaxCodeOverrideWithSplit {
  id: string;
  source_type: string;
  source_id: string;
  line_item_index: number;
  original_tax_type: string | null;
  override_tax_type: string;
  writeback_status: WritebackStatus;
  is_new_split: boolean;
  is_deleted: boolean;
  line_amount: string | null;
  line_description: string | null;
  line_account_code: string | null;
  is_active: boolean;
  applied_at: string;
}

export interface SplitCreateRequest {
  line_item_index: number;
  override_tax_type: string;
  line_amount?: string | null;
  line_description?: string | null;
  line_account_code?: string | null;
  is_new_split?: boolean;
  is_deleted?: boolean;
}

export interface SplitUpdateRequest {
  override_tax_type?: string;
  line_amount?: string;
  line_description?: string | null;
  line_account_code?: string | null;
  is_deleted?: boolean;
}

export interface SplitValidationError {
  detail: string;
  expected_total: string;
  actual_total: string;
}

/**
 * List active split overrides for a bank transaction
 */
export async function listTransactionSplits(
  token: string,
  connectionId: string,
  sessionId: string,
  sourceId: string,
): Promise<TransactionSplitsResponse> {
  const response = await apiClient.get(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/bank-transactions/${sourceId}/splits`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  return apiClient.handleResponse<TransactionSplitsResponse>(response);
}

/**
 * Create a new split override on a bank transaction
 */
export async function createSplit(
  token: string,
  connectionId: string,
  sessionId: string,
  sourceId: string,
  body: SplitCreateRequest,
): Promise<TaxCodeOverrideWithSplit> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/bank-transactions/${sourceId}/splits`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  return apiClient.handleResponse<TaxCodeOverrideWithSplit>(response);
}

/**
 * Update an existing split override
 */
export async function updateSplit(
  token: string,
  connectionId: string,
  sessionId: string,
  sourceId: string,
  overrideId: string,
  body: SplitUpdateRequest,
): Promise<TaxCodeOverrideWithSplit> {
  const response = await apiClient.patch(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/bank-transactions/${sourceId}/splits/${overrideId}`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  return apiClient.handleResponse<TaxCodeOverrideWithSplit>(response);
}

/**
 * Delete (soft-delete) a split override
 */
export async function deleteSplit(
  token: string,
  connectionId: string,
  sessionId: string,
  sourceId: string,
  overrideId: string,
): Promise<void> {
  const response = await apiClient.delete(
    `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/bank-transactions/${sourceId}/splits/${overrideId}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok && response.status !== 204) {
    await apiClient.handleResponse<void>(response);
  }
}

// =============================================================================
// Xero Accounts (for account code autocomplete in splits)
// =============================================================================

export interface XeroAccountOption {
  account_code: string;
  account_name: string;
  account_type: string;
}

/** Fetch synced chart of accounts for a connection (active accounts only). */
export async function listXeroAccounts(
  token: string,
  connectionId: string,
): Promise<XeroAccountOption[]> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/accounts?is_active=true`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  const data = await apiClient.handleResponse<{ accounts: Array<{ account_code: string | null; account_name: string; account_type: string }> }>(response);
  return data.accounts
    .filter((a) => a.account_code)
    .map((a) => ({ account_code: a.account_code!, account_name: a.account_name, account_type: a.account_type }));
}

/** Valid tax types for override dropdown (non-excluded from TAX_TYPE_MAPPING) */
export const VALID_TAX_TYPES = [
  { value: 'OUTPUT', label: 'GST on Sales (OUTPUT)', group: 'Sales' },
  { value: 'INPUT', label: 'GST on Purchases (INPUT)', group: 'Purchases' },
  { value: 'INPUTTAXED', label: 'Input Taxed (INPUTTAXED)', group: 'Purchases' },
  { value: 'CAPEXINPUT', label: 'Capital Purchase (CAPEXINPUT)', group: 'Capital' },
  { value: 'EXEMPTCAPITAL', label: 'GST-Free Capital (EXEMPTCAPITAL)', group: 'Exempt' },
  { value: 'EXEMPTOUTPUT', label: 'GST-Free Sale (EXEMPTOUTPUT)', group: 'Exempt' },
  { value: 'EXEMPTEXPENSES', label: 'GST-Free Expense (EXEMPTEXPENSES)', group: 'Exempt' },
  { value: 'EXEMPTEXPORT', label: 'Export Sale (EXEMPTEXPORT)', group: 'Exempt' },
  { value: 'GSTONIMPORTS', label: 'GST on Imports (GSTONIMPORTS)', group: 'Imports' },
  { value: 'GSTONCAPIMPORTS', label: 'GST on Capital Imports (GSTONCAPIMPORTS)', group: 'Imports' },
  { value: 'BASEXCLUDED', label: 'BAS Excluded (BASEXCLUDED)', group: 'BAS Excluded' },
] as const;
