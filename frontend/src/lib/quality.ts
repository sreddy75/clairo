/**
 * Quality Scoring Types and API Functions
 *
 * Provides types and API functions for data quality scoring.
 */

import { apiClient } from './api-client';

// =============================================================================
// Types
// =============================================================================

export type IssueSeverity = 'critical' | 'error' | 'warning' | 'info';

export type IssueCode =
  | 'STALE_DATA'
  | 'UNRECONCILED_TXN'
  | 'MISSING_GST_CODE'
  | 'UNCAT_EXPENSE'
  | 'MISSING_INVOICES'
  | 'MISSING_TXN'
  | 'DATA_GAP'
  | 'MISSING_PAYSLIPS'
  | 'PAYROLL_NOT_SYNCED';

export interface QualityDimension {
  name: string;
  score: number;
  weight: number;
  details: string;
  applicable: boolean;
}

export interface QualityDimensions {
  freshness: QualityDimension;
  reconciliation: QualityDimension;
  categorization: QualityDimension;
  completeness: QualityDimension;
  payg_readiness: QualityDimension;
}

export interface QualityIssueCounts {
  critical: number;
  error: number;
  warning: number;
  info: number;
}

export interface QualityScoreResponse {
  connection_id: string;
  quarter: number;
  fy_year: number;
  overall_score: number;
  dimensions: QualityDimensions;
  issue_counts: QualityIssueCounts;
  last_checked_at: string | null;
  has_score: boolean;
}

export interface QualityIssue {
  id: string;
  code: IssueCode;
  severity: IssueSeverity;
  title: string;
  description: string;
  affected_entity_type: string | null;
  affected_count: number;
  affected_ids: string[] | null;
  suggested_action: string | null;
  first_detected_at: string;
  last_seen_at: string;
  dismissed: boolean;
  dismissed_at: string | null;
  dismissed_reason: string | null;
}

export interface QualityIssuesListResponse {
  issues: QualityIssue[];
  total: number;
  by_severity: QualityIssueCounts;
}

export interface QualityRecalculateResponse {
  connection_id: string;
  overall_score: number;
  issues_found: number;
  calculated_at: string;
}

export interface DismissIssueResponse {
  id: string;
  dismissed: boolean;
  dismissed_at: string;
  dismissed_reason: string;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get quality score for a client connection
 */
export async function getQualityScore(
  token: string,
  connectionId: string,
  quarter?: number,
  fyYear?: number
): Promise<QualityScoreResponse> {
  const params = new URLSearchParams();
  if (quarter) params.append('quarter', quarter.toString());
  if (fyYear) params.append('fy_year', fyYear.toString());

  const queryString = params.toString();
  const url = `/api/v1/clients/${connectionId}/quality${queryString ? `?${queryString}` : ''}`;

  const response = await apiClient.get(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<QualityScoreResponse>(response);
}

/**
 * Get quality issues for a client connection
 */
export async function getQualityIssues(
  token: string,
  connectionId: string,
  options?: {
    quarter?: number;
    fyYear?: number;
    severity?: IssueSeverity;
    issueType?: IssueCode;
    includeDismissed?: boolean;
  }
): Promise<QualityIssuesListResponse> {
  const params = new URLSearchParams();
  if (options?.quarter) params.append('quarter', options.quarter.toString());
  if (options?.fyYear) params.append('fy_year', options.fyYear.toString());
  if (options?.severity) params.append('severity', options.severity);
  if (options?.issueType) params.append('issue_type', options.issueType);
  if (options?.includeDismissed) params.append('include_dismissed', 'true');

  const queryString = params.toString();
  const url = `/api/v1/clients/${connectionId}/quality/issues${queryString ? `?${queryString}` : ''}`;

  const response = await apiClient.get(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<QualityIssuesListResponse>(response);
}

/**
 * Trigger quality score recalculation
 */
export async function recalculateQuality(
  token: string,
  connectionId: string,
  quarter?: number,
  fyYear?: number
): Promise<QualityRecalculateResponse> {
  const params = new URLSearchParams();
  if (quarter) params.append('quarter', quarter.toString());
  if (fyYear) params.append('fy_year', fyYear.toString());

  const queryString = params.toString();
  const url = `/api/v1/clients/${connectionId}/quality/recalculate${queryString ? `?${queryString}` : ''}`;

  const response = await apiClient.post(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<QualityRecalculateResponse>(response);
}

/**
 * Dismiss a quality issue
 */
export async function dismissQualityIssue(
  token: string,
  connectionId: string,
  issueId: string,
  reason: string
): Promise<DismissIssueResponse> {
  const response = await apiClient.post(
    `/api/v1/clients/${connectionId}/quality/issues/${issueId}/dismiss`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ reason }),
    }
  );
  return apiClient.handleResponse<DismissIssueResponse>(response);
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get quality score tier based on overall score
 */
export function getQualityTier(score: number): 'good' | 'fair' | 'poor' {
  if (score > 80) return 'good';
  if (score >= 50) return 'fair';
  return 'poor';
}

/**
 * Get color classes for quality score
 */
export function getQualityScoreColor(score: number): string {
  const tier = getQualityTier(score);
  const colors = {
    good: 'text-green-700 bg-green-100',
    fair: 'text-yellow-700 bg-yellow-100',
    poor: 'text-red-700 bg-red-100',
  };
  return colors[tier];
}

/**
 * Get color classes for issue severity
 */
export function getSeverityColor(severity: IssueSeverity): string {
  const colors: Record<IssueSeverity, string> = {
    critical: 'text-red-700 bg-red-100 border-red-200',
    error: 'text-orange-700 bg-orange-100 border-orange-200',
    warning: 'text-yellow-700 bg-yellow-100 border-yellow-200',
    info: 'text-blue-700 bg-blue-100 border-blue-200',
  };
  return colors[severity];
}

/**
 * Get icon name for severity
 */
export function getSeverityIcon(severity: IssueSeverity): string {
  const icons: Record<IssueSeverity, string> = {
    critical: 'AlertOctagon',
    error: 'AlertTriangle',
    warning: 'AlertCircle',
    info: 'Info',
  };
  return icons[severity];
}

/**
 * Get human-readable dimension name
 */
export function getDimensionName(dimension: string): string {
  const names: Record<string, string> = {
    freshness: 'Data Freshness',
    reconciliation: 'Reconciliation',
    categorization: 'Categorization',
    completeness: 'Completeness',
    payg_readiness: 'PAYG Readiness',
  };
  return names[dimension] || dimension;
}

/**
 * Get dimension description
 */
export function getDimensionDescription(dimension: string): string {
  const descriptions: Record<string, string> = {
    freshness: 'How recently the data was synced from Xero',
    reconciliation: 'Percentage of transactions that are reconciled',
    categorization: 'Percentage of items with proper GST codes',
    completeness: 'Presence of invoices and bank transactions',
    payg_readiness: 'Payroll data completeness for PAYG reporting',
  };
  return descriptions[dimension] || '';
}

/**
 * Calculate color for dimension score
 */
export function getDimensionColor(score: number): string {
  if (score >= 80) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
}
