/**
 * Insights API Client
 *
 * Provides typed API functions for the insights module:
 * - List insights with filtering
 * - Get dashboard summary
 * - Mark insights as viewed/actioned/dismissed
 * - Trigger insight generation
 * - Multi-client queries
 */

import type {
  Insight,
  InsightDashboardResponse,
  InsightFilters,
  InsightGenerationResponse,
  InsightListResponse,
  MultiClientQueryRequest,
  MultiClientQueryResponse,
} from '@/types/insights';

import { apiClient } from '../api-client';

const BASE = '/api/v1/insights';

// =============================================================================
// List & Dashboard
// =============================================================================

export async function getInsights(
  token: string,
  filters: InsightFilters = {}
): Promise<InsightListResponse> {
  const params = new URLSearchParams();

  if (filters.status?.length) {
    filters.status.forEach((s) => params.append('status', s));
  }
  if (filters.priority?.length) {
    filters.priority.forEach((p) => params.append('priority', p));
  }
  if (filters.category?.length) {
    filters.category.forEach((c) => params.append('category', c));
  }
  if (filters.client_id) {
    params.set('client_id', filters.client_id);
  }
  if (filters.limit) {
    params.set('limit', filters.limit.toString());
  }
  if (filters.offset) {
    params.set('offset', filters.offset.toString());
  }

  const url = params.toString() ? `${BASE}?${params}` : BASE;
  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<InsightListResponse>(response);
}

export async function getInsightDashboard(
  token: string,
  topCount: number = 5
): Promise<InsightDashboardResponse> {
  const response = await apiClient.get(
    `${BASE}/dashboard?top_count=${topCount}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  return apiClient.handleResponse<InsightDashboardResponse>(response);
}

export async function getInsight(
  token: string,
  insightId: string
): Promise<Insight> {
  const response = await apiClient.get(`${BASE}/${insightId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<Insight>(response);
}

// =============================================================================
// Actions
// =============================================================================

export async function markInsightViewed(
  token: string,
  insightId: string
): Promise<Insight> {
  const response = await apiClient.post(`${BASE}/${insightId}/view`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<Insight>(response);
}

export async function markInsightActioned(
  token: string,
  insightId: string,
  notes?: string
): Promise<Insight> {
  const response = await apiClient.post(`${BASE}/${insightId}/action`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: notes ? JSON.stringify({ notes }) : undefined,
  });
  return apiClient.handleResponse<Insight>(response);
}

export async function dismissInsight(
  token: string,
  insightId: string,
  notes?: string
): Promise<Insight> {
  const response = await apiClient.post(`${BASE}/${insightId}/dismiss`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: notes ? JSON.stringify({ notes }) : undefined,
  });
  return apiClient.handleResponse<Insight>(response);
}

export async function expandInsight(
  token: string,
  insightId: string
): Promise<Insight> {
  const response = await apiClient.post(`${BASE}/${insightId}/expand`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<Insight>(response);
}

// =============================================================================
// Generation
// =============================================================================

export async function generateInsights(
  token: string,
  clientId?: string
): Promise<InsightGenerationResponse> {
  const url = clientId
    ? `${BASE}/generate?client_id=${clientId}`
    : `${BASE}/generate`;

  const response = await apiClient.post(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<InsightGenerationResponse>(response);
}

// =============================================================================
// Multi-Client Query
// =============================================================================

export async function queryInsights(
  token: string,
  request: MultiClientQueryRequest
): Promise<MultiClientQueryResponse> {
  const response = await apiClient.post(`${BASE}/query`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  return apiClient.handleResponse<MultiClientQueryResponse>(response);
}
