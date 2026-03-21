/**
 * Type definitions for Knowledge Base Admin UI.
 * Matches backend schemas from app/modules/knowledge/schemas.py
 */

// =============================================================================
// Knowledge Source Types
// =============================================================================

export interface KnowledgeSource {
  id: string;
  name: string;
  source_type: KnowledgeSourceType;
  base_url: string;
  collection_name: string;
  scrape_config: Record<string, unknown>;
  is_active: boolean;
  last_scraped_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export type KnowledgeSourceType =
  | 'ato_rss'
  | 'ato_web'
  | 'austlii'
  | 'business_gov'
  | 'fair_work';

export interface KnowledgeSourceCreate {
  name: string;
  source_type: KnowledgeSourceType;
  base_url: string;
  collection_name: string;
  scrape_config?: Record<string, unknown>;
  is_active?: boolean;
}

export interface KnowledgeSourceUpdate {
  name?: string;
  scrape_config?: Record<string, unknown>;
  is_active?: boolean;
}

// =============================================================================
// Ingestion Job Types
// =============================================================================

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface IngestionJob {
  id: string;
  source_id: string;
  source_name: string | null;
  status: JobStatus;
  started_at: string | null;
  completed_at: string | null;
  items_processed: number;
  items_added: number;
  items_updated: number;
  items_skipped: number;
  items_failed: number;
  tokens_used: number;
  errors: JobError[];
  triggered_by: string;
  created_at: string;
  duration_seconds: number | null;
  success_rate: number;
}

export interface JobError {
  url?: string;
  error: string;
  timestamp: string;
}

export interface IngestionJobSummary {
  id: string;
  source_id: string;
  source_name: string;
  status: JobStatus;
  started_at: string | null;
  items_processed: number;
  items_added: number;
  created_at: string;
}

// =============================================================================
// Collection Types
// =============================================================================

export interface CollectionInfo {
  name: string;
  description: string;
  exists: boolean;
  vectors_count: number;
  status: string | null;
  config: Record<string, unknown> | null;
  source_type_counts: Record<string, number> | null;
}

export interface CollectionInitResponse {
  collections: Record<string, boolean>;
  message: string;
}

// =============================================================================
// Search Types
// =============================================================================

export interface SearchFilters {
  entity_types?: string[];
  industries?: string[];
  source_types?: string[];
  effective_after?: string;
  exclude_superseded?: boolean;
}

export interface SearchRequest {
  query: string;
  collections?: string[];
  filters?: SearchFilters;
  limit?: number;
  score_threshold?: number;
}

export interface SearchResult {
  chunk_id: string;
  collection: string;
  score: number;
  text: string;
  source_url: string;
  title: string | null;
  source_type: string;
  ruling_number: string | null;
  effective_date: string | null;
  entity_types: string[];
  industries: string[];
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total_results: number;
  collections_searched: string[];
  latency_ms: number;
}

// =============================================================================
// Content Chunk Types
// =============================================================================

export interface ContentChunk {
  id: string;
  source_id: string;
  qdrant_point_id: string;
  collection_name: string;
  source_url: string;
  title: string | null;
  source_type: string;
  effective_date: string | null;
  expiry_date: string | null;
  entity_types: string[];
  industries: string[];
  ruling_number: string | null;
  is_superseded: boolean;
  created_at: string;
  updated_at: string;
}

// =============================================================================
// UI State Types
// =============================================================================

export interface JobsFilter {
  status?: JobStatus;
  source_id?: string;
}

export const COLLECTION_NAMES = [
  'compliance_knowledge',
  'strategic_advisory',
  'industry_knowledge',
  'business_fundamentals',
  'financial_management',
  'people_operations',
] as const;

export type CollectionName = (typeof COLLECTION_NAMES)[number];

export const SOURCE_TYPES: { value: KnowledgeSourceType; label: string }[] = [
  { value: 'ato_rss', label: 'ATO RSS Feed' },
  { value: 'ato_web', label: 'ATO Website' },
  { value: 'austlii', label: 'AustLII Legislation' },
  { value: 'business_gov', label: 'Business.gov.au' },
  { value: 'fair_work', label: 'Fair Work' },
];

export const JOB_STATUS_CONFIG: Record<
  JobStatus,
  { label: string; color: string; bgColor: string }
> = {
  pending: {
    label: 'Pending',
    color: 'text-slate-600',
    bgColor: 'bg-slate-100',
  },
  running: {
    label: 'Running',
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
  },
  completed: {
    label: 'Completed',
    color: 'text-green-600',
    bgColor: 'bg-green-100',
  },
  failed: {
    label: 'Failed',
    color: 'text-red-600',
    bgColor: 'bg-red-100',
  },
  cancelled: {
    label: 'Cancelled',
    color: 'text-orange-600',
    bgColor: 'bg-orange-100',
  },
};

// =============================================================================
// Chatbot Types
// =============================================================================

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  query: string;
  collections?: string[];
  conversation_history?: ChatMessage[];
}

export interface Citation {
  number: number;
  title: string | null;
  url: string;
  source_type: string;
  effective_date: string | null;
  text_preview: string;
  score: number;
}

export interface ChatResponse {
  response: string;
  citations: Citation[];
  query: string;
}

export interface ChatStreamEvent {
  type: 'text' | 'done' | 'error';
  content?: string;
  citations?: Citation[];
  query?: string;
  message?: string;
  conversation_id?: string;
}

// =============================================================================
// Conversation Types
// =============================================================================

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[] | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
}

export interface ConversationListItem {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview: string | null;
  client_id: string | null;
  client_name: string | null;
}

export interface ConversationClientSummary {
  client_id: string;
  client_name: string;
  conversation_count: number;
}

export interface ConversationsWithClientsResponse {
  conversations: ConversationListItem[];
  clients: ConversationClientSummary[];
  total_conversations: number;
  general_count: number;
}

export interface ChatRequestWithConversation {
  query: string;
  conversation_id?: string;
  collections?: string[];
}
