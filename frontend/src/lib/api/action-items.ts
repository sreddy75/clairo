/**
 * Action Items API client
 */

import type {
  ActionItem,
  ActionItemCreate,
  ActionItemListResponse,
  ActionItemStats,
  ActionItemUpdate,
  ConvertInsightRequest,
} from '@/types/action-items';

import { apiClient } from '../api-client';

const BASE = '/api/v1/action-items';

export interface ActionItemListParams {
  status?: string[];
  priority?: string[];
  assigned_to_user_id?: string;
  client_id?: string;
  due_before?: string;
  due_after?: string;
  include_completed?: boolean;
  limit?: number;
  offset?: number;
}

/**
 * List action items with filters
 */
export async function listActionItems(
  token: string,
  params: ActionItemListParams = {}
): Promise<ActionItemListResponse> {
  const searchParams = new URLSearchParams();

  if (params.status?.length) {
    params.status.forEach((s) => searchParams.append('status', s));
  }
  if (params.priority?.length) {
    params.priority.forEach((p) => searchParams.append('priority', p));
  }
  if (params.assigned_to_user_id) {
    searchParams.append('assigned_to_user_id', params.assigned_to_user_id);
  }
  if (params.client_id) {
    searchParams.append('client_id', params.client_id);
  }
  if (params.due_before) {
    searchParams.append('due_before', params.due_before);
  }
  if (params.due_after) {
    searchParams.append('due_after', params.due_after);
  }
  if (params.include_completed) {
    searchParams.append('include_completed', 'true');
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
  return apiClient.handleResponse<ActionItemListResponse>(response);
}

/**
 * Get action item statistics
 */
export async function getActionItemStats(
  token: string,
  assigned_to_user_id?: string
): Promise<ActionItemStats> {
  const url = assigned_to_user_id
    ? `${BASE}/stats?assigned_to_user_id=${assigned_to_user_id}`
    : `${BASE}/stats`;

  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<ActionItemStats>(response);
}

/**
 * Get a single action item by ID
 */
export async function getActionItem(
  token: string,
  id: string
): Promise<ActionItem> {
  const response = await apiClient.get(`${BASE}/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<ActionItem>(response);
}

/**
 * Create a new action item
 */
export async function createActionItem(
  token: string,
  data: ActionItemCreate
): Promise<ActionItem> {
  const response = await apiClient.post(`${BASE}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return apiClient.handleResponse<ActionItem>(response);
}

/**
 * Update an action item
 */
export async function updateActionItem(
  token: string,
  id: string,
  data: ActionItemUpdate
): Promise<ActionItem> {
  const response = await apiClient.patch(`${BASE}/${id}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return apiClient.handleResponse<ActionItem>(response);
}

/**
 * Delete an action item
 */
export async function deleteActionItem(
  token: string,
  id: string
): Promise<void> {
  const response = await apiClient.delete(`${BASE}/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error('Failed to delete action item');
  }
}

/**
 * Start working on an action item (pending -> in_progress)
 */
export async function startActionItem(
  token: string,
  id: string
): Promise<ActionItem> {
  const response = await apiClient.post(`${BASE}/${id}/start`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<ActionItem>(response);
}

/**
 * Complete an action item
 */
export async function completeActionItem(
  token: string,
  id: string,
  resolution_notes?: string
): Promise<ActionItem> {
  const response = await apiClient.post(`${BASE}/${id}/complete`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ resolution_notes }),
  });
  return apiClient.handleResponse<ActionItem>(response);
}

/**
 * Cancel an action item
 */
export async function cancelActionItem(
  token: string,
  id: string
): Promise<ActionItem> {
  const response = await apiClient.post(`${BASE}/${id}/cancel`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<ActionItem>(response);
}

/**
 * Convert an insight to an action item
 */
export async function convertInsightToAction(
  token: string,
  insightId: string,
  data: ConvertInsightRequest = {}
): Promise<ActionItem> {
  const response = await apiClient.post(
    `/api/v1/insights/${insightId}/convert-to-action`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }
  );
  return apiClient.handleResponse<ActionItem>(response);
}
