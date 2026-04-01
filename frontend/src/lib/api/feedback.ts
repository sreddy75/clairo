/**
 * Feedback API client
 */

import type {
  FeedbackSubmission,
  SubmissionDetail,
  SubmissionListResponse,
  SubmissionListParams,
  ConversationResponse,
  ConversationTurnResponse,
  VoiceConversationTurnResponse,
  FeedbackComment,
  FeedbackStats,
  SubmissionType,
  SubmissionStatus,
} from '@/types/feedback';

import { apiClient } from '../api-client';

const BASE = '/api/v1/feedback';

/**
 * Create a new feedback submission with an audio file
 */
export async function createSubmission(
  token: string,
  type: SubmissionType,
  audioFile: File
): Promise<FeedbackSubmission> {
  const formData = new FormData();
  formData.append('type', type);
  formData.append('audio', audioFile);

  const response = await apiClient.post(BASE, {
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  return apiClient.handleResponse<FeedbackSubmission>(response);
}

/**
 * List feedback submissions with filters
 */
export async function listSubmissions(
  token: string,
  params: SubmissionListParams = {}
): Promise<SubmissionListResponse> {
  const searchParams = new URLSearchParams();

  if (params.type) {
    searchParams.append('type', params.type);
  }
  if (params.status) {
    searchParams.append('status', params.status);
  }
  if (params.mine_only) {
    searchParams.append('mine_only', 'true');
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
  return apiClient.handleResponse<SubmissionListResponse>(response);
}

/**
 * Get a single submission by ID
 */
export async function getSubmission(
  token: string,
  id: string
): Promise<SubmissionDetail> {
  const response = await apiClient.get(`${BASE}/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<SubmissionDetail>(response);
}

/**
 * Update a submission's status
 */
export async function updateStatus(
  token: string,
  id: string,
  status: SubmissionStatus
): Promise<FeedbackSubmission> {
  const response = await apiClient.patch(`${BASE}/${id}/status`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ status }),
  });
  return apiClient.handleResponse<FeedbackSubmission>(response);
}

/**
 * Get the conversation for a submission
 */
export async function getConversation(
  token: string,
  id: string
): Promise<ConversationResponse> {
  const response = await apiClient.get(`${BASE}/${id}/conversation`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<ConversationResponse>(response);
}

/**
 * Send a text message in a submission conversation
 */
export async function sendMessage(
  token: string,
  id: string,
  content: string,
  contentType: string = 'text',
  file?: File | null,
): Promise<ConversationTurnResponse> {
  const formData = new FormData();
  formData.append('content', content);
  formData.append('content_type', contentType);
  if (file) formData.append('file', file);

  const response = await apiClient.post(
    `${BASE}/${id}/conversation/message`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    }
  );
  return apiClient.handleResponse<ConversationTurnResponse>(response);
}

/**
 * Send a voice message in a submission conversation
 */
export async function sendVoiceMessage(
  token: string,
  id: string,
  audioFile: File
): Promise<VoiceConversationTurnResponse> {
  const formData = new FormData();
  formData.append('audio', audioFile);

  const response = await apiClient.post(
    `${BASE}/${id}/conversation/voice`,
    {
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    }
  );
  return apiClient.handleResponse<VoiceConversationTurnResponse>(response);
}

/**
 * Confirm a submission brief, optionally with revision notes
 */
export async function confirmBrief(
  token: string,
  id: string,
  revisions?: string
): Promise<FeedbackSubmission> {
  const response = await apiClient.post(`${BASE}/${id}/confirm`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(revisions ? { revisions } : {}),
  });
  return apiClient.handleResponse<FeedbackSubmission>(response);
}

/**
 * Export a submission brief as text
 */
export async function exportBrief(
  token: string,
  id: string
): Promise<string> {
  const response = await apiClient.get(`${BASE}/${id}/export`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error('Failed to export brief');
  }

  return response.text();
}

/**
 * Get feedback statistics
 */
export async function getStats(token: string): Promise<FeedbackStats> {
  const response = await apiClient.get(`${BASE}/stats`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<FeedbackStats>(response);
}

/**
 * List comments for a submission
 */
export async function listComments(
  token: string,
  id: string
): Promise<{ items: FeedbackComment[]; total: number }> {
  const response = await apiClient.get(`${BASE}/${id}/comments`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<{ items: FeedbackComment[]; total: number }>(
    response
  );
}

/**
 * Add a comment to a submission
 */
export async function addComment(
  token: string,
  id: string,
  content: string
): Promise<FeedbackComment> {
  const response = await apiClient.post(`${BASE}/${id}/comments`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content }),
  });
  return apiClient.handleResponse<FeedbackComment>(response);
}
