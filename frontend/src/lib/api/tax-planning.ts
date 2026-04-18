// API wrapper for Tax Planning module (Spec 049)
// Follows pattern from lib/api/insights.ts

import { apiClient } from '@/lib/api-client';
import type {
  ChatResponse,
  ChatStreamEvent,
  FinancialsInput,
  FinancialsPullResponse,
  MessageListResponse,
  TaxPlan,
  TaxPlanCreateRequest,
  TaxPlanListResponse,
  TaxPlanUpdateRequest,
  TaxRatesResponse,
  TaxScenarioListResponse,
  XeroChanges,
} from '@/types/tax-planning';

const BASE = '/api/v1/tax-plans';

// ---------------------------------------------------------------------------
// Plan CRUD
// ---------------------------------------------------------------------------

export async function createTaxPlan(
  token: string,
  data: TaxPlanCreateRequest,
): Promise<TaxPlan> {
  const response = await apiClient.post(BASE, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return apiClient.handleResponse<TaxPlan>(response);
}

export async function getTaxPlan(
  token: string,
  planId: string,
): Promise<TaxPlan> {
  const response = await apiClient.get(`${BASE}/${planId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<TaxPlan>(response);
}

export async function listTaxPlans(
  token: string,
  params?: {
    status?: string;
    financial_year?: string;
    search?: string;
    page?: number;
    page_size?: number;
  },
): Promise<TaxPlanListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.financial_year)
    searchParams.set('financial_year', params.financial_year);
  if (params?.search) searchParams.set('search', params.search);
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.page_size)
    searchParams.set('page_size', String(params.page_size));

  const url = searchParams.toString()
    ? `${BASE}?${searchParams.toString()}`
    : BASE;
  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<TaxPlanListResponse>(response);
}

export async function updateTaxPlan(
  token: string,
  planId: string,
  data: TaxPlanUpdateRequest,
): Promise<TaxPlan> {
  const response = await apiClient.patch(`${BASE}/${planId}`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return apiClient.handleResponse<TaxPlan>(response);
}

// Spec 059 FR-015 — confirm (or replace) an AI-estimated scenario figure.
// Path is the dotted JSON Pointer into impact_data / assumptions. Returns
// the old/new provenance and value envelope.
export interface ConfirmScenarioFieldResponse {
  scenario_id: string;
  field_path: string;
  old_value: unknown;
  new_value: unknown;
  old_provenance: string;
  new_provenance: string;
}

export async function confirmScenarioField(
  token: string,
  planId: string,
  scenarioId: string,
  fieldPath: string,
  value: unknown,
): Promise<ConfirmScenarioFieldResponse> {
  const response = await apiClient.patch(
    `${BASE}/${planId}/scenarios/${scenarioId}/assumptions/${encodeURIComponent(fieldPath)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ value }),
    },
  );
  return apiClient.handleResponse<ConfirmScenarioFieldResponse>(response);
}

export async function deleteTaxPlan(
  token: string,
  planId: string,
): Promise<void> {
  const response = await apiClient.delete(`${BASE}/${planId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Failed to delete tax plan: ${response.status}`);
  }
}

// ---------------------------------------------------------------------------
// Financials
// ---------------------------------------------------------------------------

export async function pullXeroFinancials(
  token: string,
  planId: string,
  forceRefresh = false,
  // Spec 059.1 — optional as-at anchor. When provided, the plan's
  // as_at_date is updated before the pull so the refreshed numbers align
  // with the new anchor in one round-trip. Pass an ISO date string
  // (YYYY-MM-DD) or null/undefined to leave the existing anchor in place.
  asAtDate?: string | null,
): Promise<FinancialsPullResponse> {
  const body: Record<string, unknown> = { force_refresh: forceRefresh };
  if (asAtDate !== undefined) body.as_at_date = asAtDate;
  const response = await apiClient.post(
    `${BASE}/${planId}/financials/pull-xero`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  return apiClient.handleResponse<FinancialsPullResponse>(response);
}

export async function saveManualFinancials(
  token: string,
  planId: string,
  data: FinancialsInput,
): Promise<FinancialsPullResponse> {
  const response = await apiClient.put(`${BASE}/${planId}/financials`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return apiClient.handleResponse<FinancialsPullResponse>(response);
}

// ---------------------------------------------------------------------------
// Scenarios
// ---------------------------------------------------------------------------

export async function listScenarios(
  token: string,
  planId: string,
): Promise<TaxScenarioListResponse> {
  const response = await apiClient.get(`${BASE}/${planId}/scenarios`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<TaxScenarioListResponse>(response);
}

export async function deleteScenario(
  token: string,
  planId: string,
  scenarioId: string,
): Promise<void> {
  const response = await apiClient.delete(
    `${BASE}/${planId}/scenarios/${scenarioId}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok) {
    throw new Error(`Failed to delete scenario: ${response.status}`);
  }
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export async function sendChatMessage(
  token: string,
  planId: string,
  message: string,
): Promise<ChatResponse> {
  const response = await apiClient.post(`${BASE}/${planId}/chat`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  return apiClient.handleResponse<ChatResponse>(response);
}

export async function* chatStream(
  token: string,
  planId: string,
  message: string,
  file?: File | null,
): AsyncGenerator<ChatStreamEvent> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';

  const formData = new FormData();
  formData.append('message', message);
  if (file) {
    formData.append('file', file);
  }

  const response = await fetch(`${apiUrl}${BASE}/${planId}/chat/stream`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Chat stream failed: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event: ChatStreamEvent = JSON.parse(line.slice(6));
          yield event;
        } catch {
          // Skip unparseable lines
        }
      }
    }
  }
}

export async function listMessages(
  token: string,
  planId: string,
  page = 1,
  pageSize = 50,
): Promise<MessageListResponse> {
  const response = await apiClient.get(
    `${BASE}/${planId}/messages?page=${page}&page_size=${pageSize}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  return apiClient.handleResponse<MessageListResponse>(response);
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

export async function exportPlanPdf(
  token: string,
  planId: string,
  includeScenarios = true,
  includeConversation = false,
): Promise<Blob> {
  const params = new URLSearchParams({
    include_scenarios: String(includeScenarios),
    include_conversation: String(includeConversation),
  });
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || ''}${BASE}/${planId}/export?${params}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok) {
    throw new Error(`Export failed: ${response.status}`);
  }
  return response.blob();
}

// ---------------------------------------------------------------------------
// Tax rates
// ---------------------------------------------------------------------------

export async function getTaxRates(
  token: string,
  financialYear: string,
): Promise<TaxRatesResponse> {
  const response = await apiClient.get(`${BASE}/rates/${financialYear}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<TaxRatesResponse>(response);
}

// ---------------------------------------------------------------------------
// Xero change detection
// ---------------------------------------------------------------------------

export async function checkXeroChanges(
  token: string,
  planId: string,
): Promise<XeroChanges> {
  const response = await apiClient.get(`${BASE}/${planId}/xero-changes`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<XeroChanges>(response);
}

// ---------------------------------------------------------------------------
// Analysis Pipeline (Spec 041)
// ---------------------------------------------------------------------------

export interface GenerateAnalysisResponse {
  task_id: string;
  analysis_id: string;
  version: number;
  status: string;
  message: string;
}

export interface AnalysisProgressEvent {
  type: 'progress' | 'complete' | 'error';
  stage?: string;
  stage_number?: number;
  total_stages?: number;
  message?: string;
  analysis_id?: string;
  status?: string;
  retryable?: boolean;
}

// Spec 059 FR-013 — per-field divergence between modeller output and the
// reviewer's independent ground-truth re-derivation.
export interface ReviewerDisagreement {
  scenario_id: string;
  field_path: string;
  expected: number;
  got: number;
  delta: number;
}

export interface ReviewResult {
  numbers_verified?: boolean;
  disagreements?: ReviewerDisagreement[];
  overall_passed?: boolean;
  summary?: string;
  numbers_issues?: string[];
  [key: string]: unknown;
}

export interface AnalysisResponse {
  id: string;
  version: number;
  status: string;
  client_profile: Record<string, unknown> | null;
  strategies_evaluated: Record<string, unknown>[] | null;
  recommended_scenarios: Record<string, unknown>[] | null;
  combined_strategy: Record<string, unknown> | null;
  accountant_brief: string | null;
  client_summary: string | null;
  review_result: ReviewResult | null;
  review_passed: boolean | null;
  implementation_items: {
    id: string;
    title: string;
    description?: string;
    deadline?: string;
    estimated_saving?: number;
    risk_rating?: string;
    status: string;
    client_visible: boolean;
    completed_at?: string;
  }[];
  generation_time_ms: number | null;
  generated_at: string;
  previous_versions: { version: number; generated_at: string; status: string }[];
}

export async function generateAnalysis(
  token: string,
  planId: string,
): Promise<GenerateAnalysisResponse> {
  const response = await apiClient.post(`${BASE}/${planId}/analysis/generate`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<GenerateAnalysisResponse>(response);
}

export async function* analysisProgressStream(
  token: string,
  planId: string,
  taskId: string,
): AsyncGenerator<AnalysisProgressEvent> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
  const response = await fetch(`${apiUrl}${BASE}/${planId}/analysis/progress/${taskId}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' },
  });

  if (!response.ok) throw new Error(`Progress stream failed: ${response.status}`);

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          yield JSON.parse(line.slice(6));
        } catch { /* skip */ }
      }
    }
  }
}

export async function getAnalysis(
  token: string,
  planId: string,
): Promise<AnalysisResponse> {
  const response = await apiClient.get(`${BASE}/${planId}/analysis`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<AnalysisResponse>(response);
}

export async function approveAnalysis(
  token: string,
  planId: string,
): Promise<{ status: string; message: string }> {
  const response = await apiClient.post(`${BASE}/${planId}/analysis/approve`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse(response);
}

export async function shareAnalysis(
  token: string,
  planId: string,
): Promise<{ status: string; shared_at: string; message: string }> {
  const response = await apiClient.post(`${BASE}/${planId}/analysis/share`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse(response);
}
