/**
 * Knowledge Base Admin API Client
 *
 * Provides typed API functions for managing the knowledge base:
 * - Collections management
 * - Source CRUD operations
 * - Ingestion job tracking
 * - Search testing
 */

import type {
  ChatRequest,
  ChatRequestWithConversation,
  ChatResponse,
  ChatStreamEvent,
  Citation,
  CollectionInfo,
  CollectionInitResponse,
  Conversation,
  ConversationListItem,
  ConversationsWithClientsResponse,
  IngestionJob,
  IngestionJobSummary,
  JobsFilter,
  KnowledgeSource,
  KnowledgeSourceCreate,
  KnowledgeSourceUpdate,
  SearchRequest,
  SearchResponse,
} from '@/types/knowledge';

import { apiClient } from '../api-client';

const ADMIN_BASE = '/api/v1/admin/knowledge';

// =============================================================================
// Collections API
// =============================================================================

export async function getCollections(token: string): Promise<CollectionInfo[]> {
  const response = await apiClient.get(`${ADMIN_BASE}/collections`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<CollectionInfo[]>(response);
}

export async function initializeCollections(
  token: string
): Promise<CollectionInitResponse> {
  const response = await apiClient.post(`${ADMIN_BASE}/collections/initialize`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<CollectionInitResponse>(response);
}

export async function deleteCollection(
  token: string,
  collectionName: string
): Promise<{ message: string }> {
  const response = await apiClient.delete(
    `${ADMIN_BASE}/collections/${collectionName}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<{ message: string }>(response);
}

// =============================================================================
// Collection Content Browsing API
// =============================================================================

export interface CollectionContentItem {
  id: string;
  title: string | null;
  source_url: string;
  source_type: string;
  natural_key: string | null;
  content_type: string | null;
  section_ref: string | null;
  created_at: string;
}

export interface CollectionContentResponse {
  items: CollectionContentItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  source_type_counts: Record<string, number>;
}

const KNOWLEDGE_BASE = '/api/v1/knowledge';

export async function getCollectionContent(
  token: string,
  collectionName: string,
  options?: {
    page?: number;
    pageSize?: number;
    sourceType?: string;
    search?: string;
  }
): Promise<CollectionContentResponse> {
  const params = new URLSearchParams();
  if (options?.page) params.set('page', options.page.toString());
  if (options?.pageSize) params.set('page_size', options.pageSize.toString());
  if (options?.sourceType) params.set('source_type', options.sourceType);
  if (options?.search) params.set('search', options.search);

  const queryString = params.toString();
  const url = queryString
    ? `${KNOWLEDGE_BASE}/collections/${collectionName}/content?${queryString}`
    : `${KNOWLEDGE_BASE}/collections/${collectionName}/content`;

  const response = await apiClient.get(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<CollectionContentResponse>(response);
}

// =============================================================================
// Sources API
// =============================================================================

export async function getSources(token: string): Promise<KnowledgeSource[]> {
  const response = await apiClient.get(`${ADMIN_BASE}/sources`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<KnowledgeSource[]>(response);
}

export async function getSource(
  token: string,
  sourceId: string
): Promise<KnowledgeSource> {
  const response = await apiClient.get(`${ADMIN_BASE}/sources/${sourceId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<KnowledgeSource>(response);
}

export async function createSource(
  token: string,
  data: KnowledgeSourceCreate
): Promise<KnowledgeSource> {
  const response = await apiClient.post(`${ADMIN_BASE}/sources`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return apiClient.handleResponse<KnowledgeSource>(response);
}

export async function updateSource(
  token: string,
  sourceId: string,
  data: KnowledgeSourceUpdate
): Promise<KnowledgeSource> {
  const response = await apiClient.patch(`${ADMIN_BASE}/sources/${sourceId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return apiClient.handleResponse<KnowledgeSource>(response);
}

export async function deleteSource(
  token: string,
  sourceId: string
): Promise<{ message: string }> {
  const response = await apiClient.delete(`${ADMIN_BASE}/sources/${sourceId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<{ message: string }>(response);
}

export async function triggerIngestion(
  token: string,
  sourceId: string
): Promise<IngestionJob> {
  const response = await apiClient.post(
    `${ADMIN_BASE}/sources/${sourceId}/ingest`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<IngestionJob>(response);
}

// =============================================================================
// Source Content API
// =============================================================================

export interface SourceChunkContent {
  chunk_id: string;
  text: string;
  title: string | null;
  source_url: string | null;
  source_type: string | null;
  chunk_index: number | null;
}

export interface SourceContentResponse {
  source_id: string;
  source_name: string;
  collection: string;
  total_chunks: number;
  chunks: SourceChunkContent[];
}

export async function getSourceContent(
  token: string,
  sourceId: string,
  limit: number = 50,
  offset: number = 0
): Promise<SourceContentResponse> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });

  const response = await apiClient.get(
    `${ADMIN_BASE}/sources/${sourceId}/content?${params.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<SourceContentResponse>(response);
}

// =============================================================================
// Manual Content Upload API
// =============================================================================

export interface ManualContentUpload {
  title: string;
  text: string;
  source_url?: string;
}

export interface ManualContentUploadResponse {
  source_id: string;
  chunks_created: number;
  message: string;
}

export interface FileUploadResponse {
  source_id: string;
  filename: string;
  document_type: string;
  page_count: number;
  word_count: number;
  chunks_created: number;
  message: string;
}

export async function addManualContent(
  token: string,
  sourceId: string,
  content: ManualContentUpload
): Promise<ManualContentUploadResponse> {
  const response = await apiClient.post(
    `${ADMIN_BASE}/sources/${sourceId}/content`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(content),
    }
  );
  return apiClient.handleResponse<ManualContentUploadResponse>(response);
}

export async function uploadDocument(
  token: string,
  sourceId: string,
  file: File,
  title?: string,
  sourceUrl?: string
): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (title) formData.append('title', title);
  if (sourceUrl) formData.append('source_url', sourceUrl);

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${ADMIN_BASE}/sources/${sourceId}/upload`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
}

// =============================================================================
// Jobs API
// =============================================================================

export async function getJobs(
  token: string,
  filters?: JobsFilter
): Promise<IngestionJobSummary[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set('status', filters.status);
  if (filters?.source_id) params.set('source_id', filters.source_id);

  const queryString = params.toString();
  const url = queryString
    ? `${ADMIN_BASE}/jobs?${queryString}`
    : `${ADMIN_BASE}/jobs`;

  const response = await apiClient.get(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<IngestionJobSummary[]>(response);
}

export async function getJob(
  token: string,
  jobId: string
): Promise<IngestionJob> {
  const response = await apiClient.get(`${ADMIN_BASE}/jobs/${jobId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<IngestionJob>(response);
}

export async function deleteJob(
  token: string,
  jobId: string
): Promise<{ message: string }> {
  const response = await apiClient.delete(`${ADMIN_BASE}/jobs/${jobId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<{ message: string }>(response);
}

export async function restartJob(
  token: string,
  jobId: string
): Promise<IngestionJob> {
  const response = await apiClient.post(`${ADMIN_BASE}/jobs/${jobId}/restart`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<IngestionJob>(response);
}

export async function cancelAllJobs(
  token: string
): Promise<{ message: string; pending_cancelled: number; running_cancelled: number }> {
  const response = await apiClient.post(`${ADMIN_BASE}/jobs/cancel-all`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return apiClient.handleResponse<{
    message: string;
    pending_cancelled: number;
    running_cancelled: number;
  }>(response);
}

// =============================================================================
// Search API
// =============================================================================

export async function testSearch(
  token: string,
  request: SearchRequest
): Promise<SearchResponse> {
  const response = await apiClient.post(`${ADMIN_BASE}/search/test`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  return apiClient.handleResponse<SearchResponse>(response);
}

// =============================================================================
// Spec 045: Ingestion & Freshness API
// =============================================================================

export interface IngestionTriggerResponse {
  data: {
    job_id: string;
    source_type: string;
    status: string;
    message: string;
  };
}

export interface FreshnessSourceReport {
  source_type: string;
  source_name: string;
  last_ingested_at: string | null;
  chunk_count: number;
  error_count: number;
  freshness_status: 'fresh' | 'stale' | 'error' | 'never_ingested';
}

export interface FreshnessReport {
  data: {
    sources: FreshnessSourceReport[];
    total_chunks: number;
    last_updated: string;
  };
}

export async function getFreshness(token: string): Promise<FreshnessReport> {
  const response = await apiClient.get(`${ADMIN_BASE}/freshness`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<FreshnessReport>(response);
}

export async function triggerLegislationIngestion(
  token: string,
  acts?: string[],
  forceRefresh?: boolean,
  devMode?: boolean
): Promise<IngestionTriggerResponse> {
  const response = await apiClient.post(`${ADMIN_BASE}/ingest/legislation`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      acts: acts || null,
      force_refresh: forceRefresh || false,
      dev_mode: devMode || false,
    }),
  });
  return apiClient.handleResponse<IngestionTriggerResponse>(response);
}

export async function triggerCaseLawIngestion(
  token: string,
  source?: string,
  filterTaxOnly?: boolean,
  devMode?: boolean
): Promise<IngestionTriggerResponse> {
  const response = await apiClient.post(`${ADMIN_BASE}/ingest/case-law`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      source: source || 'all',
      filter_tax_only: filterTaxOnly ?? true,
      dev_mode: devMode || false,
    }),
  });
  return apiClient.handleResponse<IngestionTriggerResponse>(response);
}

export async function triggerAtoLegalDbIngestion(
  token: string,
  devMode?: boolean
): Promise<IngestionTriggerResponse> {
  const url = devMode
    ? `${ADMIN_BASE}/ingest/ato-legal-db?dev_mode=true`
    : `${ADMIN_BASE}/ingest/ato-legal-db`;
  const response = await apiClient.post(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({}),
  });
  return apiClient.handleResponse<IngestionTriggerResponse>(response);
}

export async function triggerTpbTreasuryIngestion(
  token: string,
  devMode?: boolean
): Promise<IngestionTriggerResponse> {
  const url = devMode
    ? `${ADMIN_BASE}/ingest/tpb-treasury?dev_mode=true`
    : `${ADMIN_BASE}/ingest/tpb-treasury`;
  const response = await apiClient.post(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({}),
  });
  return apiClient.handleResponse<IngestionTriggerResponse>(response);
}

export async function triggerTaxPlanningTopicsIngestion(
  token: string,
): Promise<IngestionTriggerResponse> {
  const response = await apiClient.post(`${ADMIN_BASE}/ingest/tax-planning-topics`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({}),
  });
  return apiClient.handleResponse<IngestionTriggerResponse>(response);
}

// =============================================================================
// Ingestion Task Status Polling
// =============================================================================

export interface IngestionTaskProgress {
  processed: number;
  added: number;
  updated: number;
  skipped: number;
  failed: number;
  source_type: string | null;
  current_item?: string;
}

export interface IngestionTaskStatus {
  task_id: string;
  status: 'PENDING' | 'STARTED' | 'PROGRESS' | 'SUCCESS' | 'FAILURE' | 'REVOKED';
  progress: IngestionTaskProgress;
  result?: Record<string, unknown>;
  error?: string;
}

export async function getIngestionTaskStatus(
  token: string,
  taskId: string
): Promise<IngestionTaskStatus> {
  const response = await apiClient.get(`${ADMIN_BASE}/ingest/status/${taskId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<IngestionTaskStatus>(response);
}

// =============================================================================
// Embedding Test API
// =============================================================================

export async function testEmbedding(
  token: string,
  text: string
): Promise<{ dimensions: number; latency_ms: number }> {
  const response = await apiClient.post(`${ADMIN_BASE}/embed/test`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  });
  return apiClient.handleResponse<{ dimensions: number; latency_ms: number }>(
    response
  );
}

// =============================================================================
// Chatbot API
// =============================================================================

export async function chat(
  token: string,
  request: ChatRequest
): Promise<ChatResponse> {
  const response = await apiClient.post(`${ADMIN_BASE}/chat`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  return apiClient.handleResponse<ChatResponse>(response);
}

/**
 * Stream chat response via Server-Sent Events.
 * Returns an async generator that yields ChatStreamEvent objects.
 */
export async function* chatStream(
  token: string,
  request: ChatRequest
): AsyncGenerator<ChatStreamEvent, void, unknown> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(`${baseUrl}${ADMIN_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Chat error: ${response.statusText}`);
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

      // Process complete SSE messages
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data.trim()) {
            try {
              const event: ChatStreamEvent = JSON.parse(data);
              yield event;
            } catch {
              // Ignore parse errors for incomplete JSON
            }
          }
        }
      }
    }

    // Process any remaining buffer
    if (buffer.startsWith('data: ')) {
      const data = buffer.slice(6);
      if (data.trim()) {
        try {
          const event: ChatStreamEvent = JSON.parse(data);
          yield event;
        } catch {
          // Ignore
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Stream chat response with conversation persistence via Server-Sent Events.
 * Creates or continues a conversation, saves messages to database.
 */
export async function* chatStreamPersistent(
  token: string,
  userId: string,
  request: ChatRequestWithConversation
): AsyncGenerator<ChatStreamEvent, void, unknown> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(
    `${baseUrl}${ADMIN_BASE}/chat/persistent/stream?user_id=${encodeURIComponent(userId)}`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }
  );

  if (!response.ok) {
    throw new Error(`Chat error: ${response.statusText}`);
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

      // Process complete SSE messages
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data.trim()) {
            try {
              const event: ChatStreamEvent = JSON.parse(data);
              yield event;
            } catch {
              // Ignore parse errors for incomplete JSON
            }
          }
        }
      }
    }

    // Process any remaining buffer
    if (buffer.startsWith('data: ')) {
      const data = buffer.slice(6);
      if (data.trim()) {
        try {
          const event: ChatStreamEvent = JSON.parse(data);
          yield event;
        } catch {
          // Ignore
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// =============================================================================
// Conversations API
// =============================================================================

export async function getConversations(
  token: string,
  userId: string,
  options?: {
    limit?: number;
    offset?: number;
    clientId?: string;
    generalOnly?: boolean;
  }
): Promise<ConversationListItem[]> {
  const params = new URLSearchParams({ user_id: userId });
  if (options?.limit) params.set('limit', options.limit.toString());
  if (options?.offset) params.set('offset', options.offset.toString());
  if (options?.clientId) params.set('client_id', options.clientId);
  if (options?.generalOnly) params.set('general_only', 'true');

  const response = await apiClient.get(
    `${ADMIN_BASE}/conversations?${params.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<ConversationListItem[]>(response);
}

export async function getConversationsWithClients(
  token: string,
  userId: string,
  limit?: number,
  offset?: number
): Promise<ConversationsWithClientsResponse> {
  const params = new URLSearchParams({ user_id: userId });
  if (limit) params.set('limit', limit.toString());
  if (offset) params.set('offset', offset.toString());

  const response = await apiClient.get(
    `${ADMIN_BASE}/conversations/with-clients?${params.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<ConversationsWithClientsResponse>(response);
}

export async function getConversation(
  token: string,
  userId: string,
  conversationId: string
): Promise<Conversation> {
  const response = await apiClient.get(
    `${ADMIN_BASE}/conversations/${conversationId}?user_id=${encodeURIComponent(userId)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<Conversation>(response);
}

export async function createConversation(
  token: string,
  userId: string,
  title?: string
): Promise<Conversation> {
  const response = await apiClient.post(
    `${ADMIN_BASE}/conversations?user_id=${encodeURIComponent(userId)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ title }),
    }
  );
  return apiClient.handleResponse<Conversation>(response);
}

export async function updateConversation(
  token: string,
  userId: string,
  conversationId: string,
  title: string
): Promise<Conversation> {
  const response = await apiClient.patch(
    `${ADMIN_BASE}/conversations/${conversationId}?user_id=${encodeURIComponent(userId)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ title }),
    }
  );
  return apiClient.handleResponse<Conversation>(response);
}

export async function deleteConversation(
  token: string,
  userId: string,
  conversationId: string
): Promise<{ message: string; id: string }> {
  const response = await apiClient.delete(
    `${ADMIN_BASE}/conversations/${conversationId}?user_id=${encodeURIComponent(userId)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<{ message: string; id: string }>(response);
}

// =============================================================================
// Client Chat API (Spec 013)
// =============================================================================

const CLIENT_CHAT_BASE = '/api/v1/knowledge/client-chat';

export interface ClientSearchResult {
  id: string;
  name: string;
  abn: string | null;
  connection_id: string;
  organization_name: string | null;
  is_active: boolean;
}

export interface ClientProfile {
  id: string;
  name: string;
  abn: string | null;
  entity_type: string | null;
  industry_code: string | null;
  gst_registered: boolean;
  revenue_bracket: string | null;
  employee_count: number;
}

export interface ConnectionStatus {
  status: string;
  organization_name: string | null;
  last_sync: string | null;
  needs_reauth: boolean;
}

export interface ClientProfileResponse {
  profile: ClientProfile;
  connection: ConnectionStatus;
  data_freshness: string | null;
  is_stale: boolean;
}

export interface ClientChatMetadata {
  client_id: string;
  client_name: string;
  query_intent: string;
  context_token_count: number;
  rag_token_count: number;
  data_freshness: string | null;
  is_stale: boolean;
}

export interface ClientChatStreamEvent {
  type: 'text' | 'done' | 'error';
  content?: string;
  citations?: Citation[];
  metadata?: ClientChatMetadata;
  query?: string;
  conversation_id?: string;
  message?: string;
}

export interface ClientChatRequest {
  client_id: string;
  query: string;
  conversation_history?: { role: string; content: string }[];
  collections?: string[];
}

export interface ClientChatRequestWithConversation extends ClientChatRequest {
  conversation_id?: string;
}

/**
 * Search for clients by name with typeahead.
 */
export async function searchClients(
  token: string,
  query: string,
  limit?: number
): Promise<{ results: ClientSearchResult[]; total: number }> {
  const params = new URLSearchParams({ q: query });
  if (limit) params.set('limit', limit.toString());

  const response = await apiClient.get(
    `${CLIENT_CHAT_BASE}/clients/search?${params.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<{ results: ClientSearchResult[]; total: number }>(response);
}

/**
 * Get client profile for chat header display.
 */
export async function getClientProfile(
  token: string,
  clientId: string
): Promise<ClientProfileResponse> {
  const response = await apiClient.get(
    `${CLIENT_CHAT_BASE}/clients/${clientId}/profile`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<ClientProfileResponse>(response);
}

/**
 * Stream client-context chat response via Server-Sent Events.
 */
export async function* clientChatStream(
  token: string,
  request: ClientChatRequest
): AsyncGenerator<ClientChatStreamEvent, void, unknown> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(`${baseUrl}${CLIENT_CHAT_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Chat error: ${response.statusText}`);
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
          if (data.trim()) {
            try {
              const event: ClientChatStreamEvent = JSON.parse(data);
              yield event;
            } catch {
              // Ignore parse errors
            }
          }
        }
      }
    }

    if (buffer.startsWith('data: ')) {
      const data = buffer.slice(6);
      if (data.trim()) {
        try {
          const event: ClientChatStreamEvent = JSON.parse(data);
          yield event;
        } catch {
          // Ignore
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Stream client-context chat with conversation persistence.
 */
export async function* clientChatStreamPersistent(
  token: string,
  userId: string,
  request: ClientChatRequestWithConversation
): AsyncGenerator<ClientChatStreamEvent, void, unknown> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(
    `${baseUrl}${CLIENT_CHAT_BASE}/chat/persistent/stream?user_id=${encodeURIComponent(userId)}`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }
  );

  if (!response.ok) {
    throw new Error(`Chat error: ${response.statusText}`);
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
          if (data.trim()) {
            try {
              const event: ClientChatStreamEvent = JSON.parse(data);
              yield event;
            } catch {
              // Ignore parse errors
            }
          }
        }
      }
    }

    if (buffer.startsWith('data: ')) {
      const data = buffer.slice(6);
      if (data.trim()) {
        try {
          const event: ClientChatStreamEvent = JSON.parse(data);
          yield event;
        } catch {
          // Ignore
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
