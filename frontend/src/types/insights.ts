/**
 * TypeScript types for the Insights module.
 *
 * Matches the backend Pydantic schemas in app/modules/insights/schemas.py
 */

export type InsightCategory =
  | 'compliance'
  | 'quality'
  | 'cash_flow'
  | 'tax'
  | 'strategic';

export type InsightPriority = 'high' | 'medium' | 'low';

export type MagicZoneGenerationType = 'rule_based' | 'ai_single' | 'magic_zone';

export type InsightStatus =
  | 'new'
  | 'viewed'
  | 'actioned'
  | 'dismissed'
  | 'resolved'
  | 'expired';

export interface SuggestedAction {
  label: string;
  url?: string;
  action?: string;
}

export type EvidenceCategory = 'financial' | 'aging' | 'gst' | 'quality' | 'trend';

export interface EvidenceItem {
  source: string;
  period: string;
  metric: string;
  value: string;
  category: EvidenceCategory;
}

export interface DataSnapshot {
  version?: string;
  captured_at?: string;
  data_freshness?: string;
  evidence_items?: EvidenceItem[];
  profile?: Record<string, unknown>;
  financial_summary?: Record<string, unknown>;
  aging_summary?: Record<string, unknown>;
  gst_summary?: Record<string, unknown>;
  monthly_trends?: Record<string, unknown>[];
  quality_scores?: Record<string, unknown>;
  perspectives_used?: string[];
  ai_analysis?: boolean;
  generated_at?: string;
  confidence_breakdown?: {
    data_completeness: number;
    data_freshness: number;
    knowledge_match: number;
    perspective_coverage: number;
  } | null;
  calculation_breakdown?: Array<{ label: string; value: string }> | null;
  // Allow other arbitrary snapshot fields
  [key: string]: unknown;
}

export interface Insight {
  id: string;
  tenant_id: string;
  client_id: string | null;
  category: InsightCategory;
  insight_type: string;
  priority: InsightPriority;
  title: string;
  summary: string;
  detail: string | null;
  suggested_actions: SuggestedAction[];
  related_url: string | null;
  status: InsightStatus;
  generated_at: string;
  expires_at: string | null;
  action_deadline: string | null;  // Date by which action should be taken
  viewed_at: string | null;
  actioned_at: string | null;
  generation_source: string;
  confidence: number | null;

  // Magic Zone fields
  generation_type: MagicZoneGenerationType;
  agents_used: string[] | null;
  options_count: number | null;

  // Evidence & traceability
  data_snapshot?: DataSnapshot | null;

  client_name: string | null;
  client_url: string | null;  // Direct link to client page for navigation
}

export interface InsightListResponse {
  insights: Insight[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface InsightStats {
  total: number;
  by_priority: Record<string, number>;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  new_this_week: number;
}

export interface InsightDashboardResponse {
  top_insights: Insight[];
  stats: InsightStats;
  new_count: number;
}

export interface InsightGenerationResponse {
  generated_count: number;
  insights: Insight[];
  client_id: string | null;
}

export interface MarkInsightRequest {
  notes?: string;
}

export interface ClientReference {
  id: string;
  name: string;
  issues: string[];
}

export interface MultiClientQueryRequest {
  query: string;
  include_inactive?: boolean;
}

export interface MultiClientQueryResponse {
  response: string;
  clients_referenced: ClientReference[];
  perspectives_used: string[];
  confidence: number;
  insights_included: number;
}

// Filter types for API calls
export interface InsightFilters {
  status?: InsightStatus[];
  priority?: InsightPriority[];
  category?: InsightCategory[];
  client_id?: string;
  limit?: number;
  offset?: number;
}
