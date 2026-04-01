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
): Promise<FinancialsPullResponse> {
  const response = await apiClient.post(
    `${BASE}/${planId}/financials/pull-xero`,
    {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ force_refresh: forceRefresh }),
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
