/**
 * Admin API client for tax strategies (Spec 060 T045).
 *
 * Mirrors `backend/app/modules/tax_strategies/router.py` exactly. Every
 * function requires a Clerk super_admin JWT — the backend rejects anything
 * else. Public hydration (`/public`) is already handled by
 * `components/tax-planning/useStrategyHydration.ts`.
 */

import { apiClient } from '../api-client';

const ADMIN_BASE = '/api/v1/admin/tax-strategies';

export type StrategyStatus =
  | 'stub'
  | 'researching'
  | 'drafted'
  | 'enriched'
  | 'in_review'
  | 'approved'
  | 'published'
  | 'superseded'
  | 'archived';

export type StrategyStage = 'research' | 'draft' | 'enrich' | 'publish';

// Mirrors ALLOWED_CATEGORIES in backend/app/modules/tax_strategies/schemas.py.
// Stringly-typed on the wire; kept in sync with the backend's fixed taxonomy.
export const STRATEGY_CATEGORIES = [
  'Business',
  'Recommendations',
  'Employees',
  'ATO_obligations',
  'Rental_properties',
  'Investors_retirees',
  'Business_structures',
  'SMSF',
] as const;

export type StrategyCategory = (typeof STRATEGY_CATEGORIES)[number];

export type AuthoringJobStatus = 'pending' | 'running' | 'succeeded' | 'failed';

export interface TaxStrategyListItem {
  strategy_id: string;
  name: string;
  categories: string[];
  status: StrategyStatus;
  tenant_id: string;
  version: number;
  last_reviewed_at: string | null;
  reviewer_display_name: string | null;
  updated_at: string;
}

export interface TaxStrategyListResponse {
  data: TaxStrategyListItem[];
  meta: { page: number; page_size: number; total: number };
}

export interface AuthoringJob {
  id: string;
  strategy_id: string;
  stage: StrategyStage;
  status: AuthoringJobStatus;
  started_at: string | null;
  completed_at: string | null;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown> | null;
  error: string | null;
  triggered_by: string;
  created_at: string;
}

export interface TaxStrategyDetail extends TaxStrategyListItem {
  implementation_text: string;
  explanation_text: string;
  entity_types: string[];
  income_band_min: number | null;
  income_band_max: number | null;
  turnover_band_min: number | null;
  turnover_band_max: number | null;
  age_min: number | null;
  age_max: number | null;
  industry_triggers: string[];
  financial_impact_type: string[];
  keywords: string[];
  ato_sources: string[];
  case_refs: string[];
  fy_applicable_from: string | null;
  fy_applicable_to: string | null;
  superseded_by_strategy_id: string | null;
  source_ref: string | null;
  authoring_jobs: AuthoringJob[];
  version_history: TaxStrategyListItem[];
}

export interface PipelineStatsResponse {
  counts: Record<StrategyStatus, number>;
}

export type StalenessReason =
  | 'content_drift'
  | 'missing_row'
  | 'version_ahead'
  | 'yaml_missing';

export interface StalenessReportResponse {
  total: number;
  by_reason: Partial<Record<StalenessReason, string[]>>;
  entries: Array<{ strategy_id: string; reason: StalenessReason }>;
}

export interface ListStrategiesParams {
  status?: StrategyStatus | null;
  category?: string | null;
  tenant_id?: string | null;
  q?: string | null;
  page?: number;
  page_size?: number;
}

export interface SeedSummaryResponse {
  created: number;
  skipped: number;
  errors: string[];
}

function authHeader(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

function buildListQuery(params: ListStrategiesParams): string {
  const q = new URLSearchParams();
  if (params.status) q.set('status', params.status);
  if (params.category) q.set('category', params.category);
  if (params.tenant_id) q.set('tenant_id', params.tenant_id);
  if (params.q) q.set('q', params.q);
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  const qs = q.toString();
  return qs ? `?${qs}` : '';
}

export async function listStrategies(
  token: string,
  params: ListStrategiesParams = {},
): Promise<TaxStrategyListResponse> {
  const response = await apiClient.get(
    `${ADMIN_BASE}${buildListQuery(params)}`,
    { headers: authHeader(token) },
  );
  return apiClient.handleResponse<TaxStrategyListResponse>(response);
}

export async function getStrategyDetail(
  token: string,
  strategyId: string,
): Promise<TaxStrategyDetail> {
  const response = await apiClient.get(`${ADMIN_BASE}/${strategyId}`, {
    headers: authHeader(token),
  });
  return apiClient.handleResponse<TaxStrategyDetail>(response);
}

export async function getPipelineStats(
  token: string,
): Promise<PipelineStatsResponse> {
  const response = await apiClient.get(`${ADMIN_BASE}/pipeline-stats`, {
    headers: authHeader(token),
  });
  return apiClient.handleResponse<PipelineStatsResponse>(response);
}

export async function triggerStage(
  token: string,
  strategyId: string,
  stage: Exclude<StrategyStage, 'publish'>,
): Promise<AuthoringJob> {
  const response = await apiClient.post(
    `${ADMIN_BASE}/${strategyId}/${stage}`,
    { headers: authHeader(token) },
  );
  return apiClient.handleResponse<AuthoringJob>(response);
}

export async function submitForReview(
  token: string,
  strategyId: string,
): Promise<TaxStrategyDetail> {
  const response = await apiClient.post(`${ADMIN_BASE}/${strategyId}/submit`, {
    headers: authHeader(token),
  });
  return apiClient.handleResponse<TaxStrategyDetail>(response);
}

export async function approveAndPublish(
  token: string,
  strategyId: string,
): Promise<AuthoringJob> {
  const response = await apiClient.post(`${ADMIN_BASE}/${strategyId}/approve`, {
    headers: authHeader(token),
  });
  return apiClient.handleResponse<AuthoringJob>(response);
}

export async function rejectToDraft(
  token: string,
  strategyId: string,
  reviewerNotes: string,
): Promise<TaxStrategyDetail> {
  const response = await apiClient.post(`${ADMIN_BASE}/${strategyId}/reject`, {
    headers: { ...authHeader(token), 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer_notes: reviewerNotes }),
  });
  return apiClient.handleResponse<TaxStrategyDetail>(response);
}

export async function getStalenessReport(
  token: string,
): Promise<StalenessReportResponse> {
  const response = await apiClient.get(`${ADMIN_BASE}/staleness`, {
    headers: authHeader(token),
  });
  return apiClient.handleResponse<StalenessReportResponse>(response);
}

export async function seedFromCsv(token: string): Promise<SeedSummaryResponse> {
  const response = await apiClient.post(`${ADMIN_BASE}/seed-from-csv`, {
    headers: authHeader(token),
  });
  return apiClient.handleResponse<SeedSummaryResponse>(response);
}
