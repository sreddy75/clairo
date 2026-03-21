/**
 * Type definitions for Multi-Perspective Agent System.
 * Matches backend schemas from app/modules/agents/schemas.py
 */

// =============================================================================
// Perspective Types
// =============================================================================

export type Perspective = 'compliance' | 'quality' | 'strategy' | 'insight';

export const PERSPECTIVE_CONFIG: Record<
  Perspective,
  { label: string; description: string; color: string; bgColor: string; icon: string }
> = {
  compliance: {
    label: 'Compliance',
    description: 'ATO rules, GST, BAS requirements, tax obligations',
    color: 'text-blue-700',
    bgColor: 'bg-blue-100',
    icon: 'Shield',
  },
  quality: {
    label: 'Quality',
    description: 'Data issues, reconciliation, coding errors, duplicates',
    color: 'text-orange-700',
    bgColor: 'bg-orange-100',
    icon: 'AlertTriangle',
  },
  strategy: {
    label: 'Strategy',
    description: 'Tax optimization, business structure, growth advice',
    color: 'text-green-700',
    bgColor: 'bg-green-100',
    icon: 'TrendingUp',
  },
  insight: {
    label: 'Insight',
    description: 'Trends, patterns, anomalies, projections',
    color: 'text-purple-700',
    bgColor: 'bg-purple-100',
    icon: 'LineChart',
  },
};

// =============================================================================
// Agent Chat Types
// =============================================================================

export interface AgentChatRequest {
  query: string;
  connection_id?: string | null;
  conversation_id?: string | null;
  /** Optional specialist tax domain slug to scope knowledge retrieval */
  domain?: string | null;
}

export interface PerspectiveResult {
  perspective: Perspective;
  content: string;
  citations: Citation[];
  confidence: number;
}

export interface Citation {
  id: string;
  source: string;
  title: string;
  section: string;
  score: number;
}

export interface AgentChatResponse {
  correlation_id: string;
  content: string;
  perspectives_used: Perspective[];
  perspective_results: PerspectiveResult[];
  confidence: number;
  escalation_required: boolean;
  escalation_reason: string | null;
  citations: Citation[];
  processing_time_ms: number;
}

export interface AgentChatMetadata {
  correlation_id: string;
  perspectives_used: Perspective[];
  confidence: number;
  escalation_required: boolean;
  escalation_reason: string | null;
  citations: Citation[];
  processing_time_ms: number;
}

// =============================================================================
// Escalation Types
// =============================================================================

export type EscalationStatus = 'pending' | 'resolved' | 'dismissed';

export const ESCALATION_STATUS_CONFIG: Record<
  EscalationStatus,
  { label: string; color: string; bgColor: string }
> = {
  pending: {
    label: 'Pending',
    color: 'text-amber-700',
    bgColor: 'bg-amber-100',
  },
  resolved: {
    label: 'Resolved',
    color: 'text-green-700',
    bgColor: 'bg-green-100',
  },
  dismissed: {
    label: 'Dismissed',
    color: 'text-slate-600',
    bgColor: 'bg-slate-100',
  },
};

export interface Escalation {
  id: string;
  query_id: string;
  reason: string;
  confidence: number;
  status: EscalationStatus;
  query_preview: string;
  perspectives_used: Perspective[];
  connection_id: string | null;
  created_at: string;
  resolved_at: string | null;
  resolved_by_name: string | null;
}

export interface ResolveEscalationRequest {
  resolution_notes: string;
  accountant_response?: string | null;
  feedback_useful?: boolean | null;
}

export interface EscalationStats {
  pending_count: number;
  resolved_today: number;
  average_confidence: number;
  top_reasons: { reason: string; count: number }[];
}

// =============================================================================
// Query Audit Types
// =============================================================================

export interface QueryDetail {
  id: string;
  correlation_id: string;
  perspectives_used: Perspective[];
  confidence: number;
  escalation_required: boolean;
  escalation_reason: string | null;
  processing_time_ms: number;
  token_usage: number | null;
  created_at: string;
}

// =============================================================================
// Streaming Types
// =============================================================================

export interface AgentStreamEvent {
  type: 'text' | 'perspective' | 'metadata' | 'done' | 'error';
  content?: string;
  perspective?: Perspective;
  metadata?: AgentChatMetadata;
  message?: string;
}

// =============================================================================
// UI Helper Types
// =============================================================================

export interface ParsedPerspectiveSection {
  perspective: Perspective;
  content: string;
}

/**
 * Parse perspective sections from response content.
 * Looks for [Perspective] markers in the text.
 */
export function parsePerspectiveSections(content: string): ParsedPerspectiveSection[] {
  const sections: ParsedPerspectiveSection[] = [];
  const pattern = /\[(\w+)\]\s*([\s\S]*?)(?=\[(?:Compliance|Quality|Strategy|Insight)\]|$)/gi;

  let match;
  while ((match = pattern.exec(content)) !== null) {
    const rawPerspective = match[1];
    const rawContent = match[2];

    if (!rawPerspective || !rawContent) continue;

    const perspectiveName = rawPerspective.toLowerCase() as Perspective;
    const sectionContent = rawContent.trim();

    if (sectionContent && ['compliance', 'quality', 'strategy', 'insight'].includes(perspectiveName)) {
      sections.push({
        perspective: perspectiveName,
        content: sectionContent,
      });
    }
  }

  return sections;
}

/**
 * Get confidence level label and color.
 */
export function getConfidenceLevel(confidence: number): {
  label: string;
  color: string;
  bgColor: string;
} {
  if (confidence >= 0.8) {
    return { label: 'High Confidence', color: 'text-green-700', bgColor: 'bg-green-100' };
  } else if (confidence >= 0.6) {
    return { label: 'Good Confidence', color: 'text-blue-700', bgColor: 'bg-blue-100' };
  } else if (confidence >= 0.4) {
    return { label: 'Review Recommended', color: 'text-amber-700', bgColor: 'bg-amber-100' };
  } else {
    return { label: 'Low Confidence', color: 'text-red-700', bgColor: 'bg-red-100' };
  }
}
