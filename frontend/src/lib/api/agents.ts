/**
 * Multi-Perspective Agent API Client
 *
 * Provides typed API functions for the agent system:
 * - Multi-perspective chat queries
 * - Escalation management
 * - Query audit retrieval
 */

import type {
  AgentChatRequest,
  AgentChatResponse,
  Escalation,
  EscalationStats,
  QueryDetail,
  ResolveEscalationRequest,
} from '@/types/agents';

import { apiClient } from '../api-client';

const AGENT_BASE = '/api/v1/agents';

// =============================================================================
// Chat API
// =============================================================================

/**
 * Send a query to the multi-perspective agent system.
 */
export async function agentChat(
  token: string,
  request: AgentChatRequest
): Promise<AgentChatResponse> {
  const response = await apiClient.post(`${AGENT_BASE}/chat`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  return apiClient.handleResponse<AgentChatResponse>(response);
}

/**
 * Streaming event types from the agent system.
 */
export interface AgentStreamEvent {
  type: 'thinking' | 'perspectives' | 'response' | 'metadata' | 'done' | 'error';
  stage?: string;
  message?: string;
  perspectives?: string[];
  content?: string;
  perspective_results?: Array<{ perspective: string; content: string }>;
  correlation_id?: string;
  conversation_id?: string;
  perspectives_used?: string[];
  confidence?: number;
  escalation_required?: boolean;
  escalation_reason?: string | null;
  processing_time_ms?: number;
  citations?: Array<{
    id: string;
    source: string;
    title: string;
    section: string;
    score: number;
    url?: string;
    /** Enhanced citation fields from spec 045 */
    verified?: boolean;
    section_ref?: string | null;
    effective_date?: string | null;
    text_preview?: string;
  }>;
  /** Knowledge response confidence tier from spec 045 (high/medium/low) */
  knowledge_confidence?: 'high' | 'medium' | 'low';
  /** Knowledge response numeric confidence score (0-1) */
  knowledge_confidence_score?: number;
  /** Auto-detected specialist domain slug */
  domain_detected?: string | null;
  /** Classified query type (SECTION_LOOKUP, RULING_LOOKUP, CONCEPTUAL, etc.) */
  query_type?: string | null;
  /** Warnings about superseded content referenced in the response */
  superseded_warnings?: string[];
  /** Attribution text for legislation/ATO sources */
  attribution?: string | null;
  /** A2UI message for rich UI components */
  a2ui_message?: {
    surfaceUpdate: {
      components: Array<{
        id: string;
        type: string;
        props?: Record<string, unknown>;
        dataBinding?: string;
        children?: unknown[];
      }>;
      layout?: 'stack' | 'grid' | 'flow' | 'sidebar';
    };
    dataModelUpdate?: Record<string, unknown>;
    meta: {
      messageId: string;
      generatedAt: string;
      agentId?: string;
      fallbackText?: string;
      deviceContext?: {
        isMobile?: boolean;
        isTablet?: boolean;
      };
    };
  };
}

/**
 * Stream a query response from the agent system with thinking status updates.
 * Returns an async generator that yields structured events.
 */
export async function* agentChatStream(
  token: string,
  request: AgentChatRequest,
  file?: File | null,
): AsyncGenerator<AgentStreamEvent, void, unknown> {
  const formData = new FormData();
  formData.append('query', request.query);
  if (request.connection_id) formData.append('connection_id', request.connection_id);
  if (request.conversation_id) formData.append('conversation_id', request.conversation_id);
  if (file) formData.append('file', file);

  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${AGENT_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'text/event-stream',
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Agent chat stream failed: ${error}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data === '[DONE]') return;

          try {
            const event = JSON.parse(data) as AgentStreamEvent;
            yield event;

            if (event.type === 'error') {
              throw new Error(event.message || 'Stream error');
            }
            if (event.type === 'done') {
              return;
            }
          } catch (e) {
            // Re-throw if it's our error
            if (e instanceof Error && e.message !== 'Stream error') {
              // Skip non-JSON lines silently
            } else {
              throw e;
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// =============================================================================
// Escalations API
// =============================================================================

/**
 * List escalations for the current tenant.
 */
export async function listEscalations(
  token: string,
  options?: {
    status?: string;
    limit?: number;
    offset?: number;
  }
): Promise<Escalation[]> {
  const params = new URLSearchParams();
  if (options?.status) params.set('status', options.status);
  if (options?.limit) params.set('limit', options.limit.toString());
  if (options?.offset) params.set('offset', options.offset.toString());

  const url = `${AGENT_BASE}/escalations${params.toString() ? `?${params}` : ''}`;
  const response = await apiClient.get(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<Escalation[]>(response);
}

/**
 * Get a specific escalation by ID.
 */
export async function getEscalation(
  token: string,
  escalationId: string
): Promise<Escalation> {
  const response = await apiClient.get(`${AGENT_BASE}/escalations/${escalationId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<Escalation>(response);
}

/**
 * Get escalation statistics.
 */
export async function getEscalationStats(token: string): Promise<EscalationStats> {
  const response = await apiClient.get(`${AGENT_BASE}/escalations/stats`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<EscalationStats>(response);
}

/**
 * Resolve an escalation with accountant input.
 */
export async function resolveEscalation(
  token: string,
  escalationId: string,
  request: ResolveEscalationRequest
): Promise<Escalation> {
  const response = await apiClient.post(
    `${AGENT_BASE}/escalations/${escalationId}/resolve`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }
  );
  return apiClient.handleResponse<Escalation>(response);
}

/**
 * Dismiss an escalation.
 */
export async function dismissEscalation(
  token: string,
  escalationId: string,
  reason: string
): Promise<Escalation> {
  const response = await apiClient.post(
    `${AGENT_BASE}/escalations/${escalationId}/dismiss?reason=${encodeURIComponent(reason)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<Escalation>(response);
}

// =============================================================================
// Query Audit API
// =============================================================================

/**
 * Get details of a specific agent query by correlation ID.
 */
export async function getQueryDetail(
  token: string,
  correlationId: string
): Promise<QueryDetail> {
  const response = await apiClient.get(`${AGENT_BASE}/queries/${correlationId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<QueryDetail>(response);
}
