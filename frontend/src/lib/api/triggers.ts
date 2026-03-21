/**
 * Triggers API client
 */

import type {
  Trigger,
  TriggerCreate,
  TriggerExecutionListResponse,
  TriggerListResponse,
  TriggerUpdate,
} from '@/types/triggers';

import { apiClient } from '../api-client';

const BASE = '/api/v1/triggers';

export interface TriggerListParams {
  trigger_type?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

/**
 * List all triggers with optional filters
 */
export async function listTriggers(
  token: string,
  params: TriggerListParams = {}
): Promise<TriggerListResponse> {
  const searchParams = new URLSearchParams();

  if (params.trigger_type) {
    searchParams.append('trigger_type', params.trigger_type);
  }
  if (params.status) {
    searchParams.append('status', params.status);
  }
  if (params.limit) {
    searchParams.append('limit', params.limit.toString());
  }
  if (params.offset) {
    searchParams.append('offset', params.offset.toString());
  }

  const queryString = searchParams.toString();
  const url = queryString ? `${BASE}?${queryString}` : BASE;

  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<TriggerListResponse>(response);
}

/**
 * Get a single trigger by ID
 */
export async function getTrigger(token: string, id: string): Promise<Trigger> {
  const response = await apiClient.get(`${BASE}/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<Trigger>(response);
}

/**
 * Create a new trigger
 */
export async function createTrigger(
  token: string,
  data: TriggerCreate
): Promise<Trigger> {
  const response = await apiClient.post(BASE, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return apiClient.handleResponse<Trigger>(response);
}

/**
 * Update a trigger
 */
export async function updateTrigger(
  token: string,
  id: string,
  data: TriggerUpdate
): Promise<Trigger> {
  const response = await apiClient.patch(`${BASE}/${id}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return apiClient.handleResponse<Trigger>(response);
}

/**
 * Delete a trigger
 */
export async function deleteTrigger(token: string, id: string): Promise<void> {
  const response = await apiClient.delete(`${BASE}/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete trigger');
  }
}

/**
 * Enable a trigger
 */
export async function enableTrigger(
  token: string,
  id: string
): Promise<Trigger> {
  const response = await apiClient.post(`${BASE}/${id}/enable`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<Trigger>(response);
}

/**
 * Disable a trigger
 */
export async function disableTrigger(
  token: string,
  id: string
): Promise<Trigger> {
  const response = await apiClient.post(`${BASE}/${id}/disable`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<Trigger>(response);
}

/**
 * Get trigger execution history
 */
export async function getTriggerExecutions(
  token: string,
  triggerId?: string,
  limit: number = 50,
  offset: number = 0
): Promise<TriggerExecutionListResponse> {
  const searchParams = new URLSearchParams();
  searchParams.append('limit', limit.toString());
  searchParams.append('offset', offset.toString());

  const url = triggerId
    ? `${BASE}/${triggerId}/executions?${searchParams.toString()}`
    : `${BASE}/executions?${searchParams.toString()}`;

  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<TriggerExecutionListResponse>(response);
}

/**
 * Seed default triggers for the tenant
 */
export async function seedDefaultTriggers(
  token: string
): Promise<TriggerListResponse> {
  const response = await apiClient.post(`${BASE}/seed-defaults`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<TriggerListResponse>(response);
}
