'use client';

import {
  AlertTriangle,
  Bot,
  ChevronDown,
  ChevronUp,
  LineChart,
  Shield,
  TrendingUp,
  User,
} from 'lucide-react';
import { useMemo, useState } from 'react';

import {
  type Perspective,
  PERSPECTIVE_CONFIG,
  parsePerspectiveSections,
} from '@/types/agents';
import type { Citation } from '@/types/knowledge';

import {
  ConfidenceIndicator,
  EscalationBanner,
  PerspectiveBadgeList,
} from './PerspectiveBadges';

// =============================================================================
// Icon Mapping
// =============================================================================

const PERSPECTIVE_ICONS = {
  compliance: Shield,
  quality: AlertTriangle,
  strategy: TrendingUp,
  insight: LineChart,
} as const;

// =============================================================================
// Types
// =============================================================================

export interface AgentMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
  // Agent-specific metadata
  perspectivesUsed?: Perspective[];
  confidence?: number;
  escalationRequired?: boolean;
  escalationReason?: string | null;
  processingTimeMs?: number;
}

interface AgentChatMessageProps {
  message: AgentMessage;
  showMetadata?: boolean;
}

// =============================================================================
// Perspective Section Component
// =============================================================================

interface PerspectiveSectionProps {
  perspective: Perspective;
  content: string;
  isExpanded: boolean;
  onToggle: () => void;
}

function PerspectiveSection({
  perspective,
  content,
  isExpanded,
  onToggle,
}: PerspectiveSectionProps) {
  const config = PERSPECTIVE_CONFIG[perspective];
  const Icon = PERSPECTIVE_ICONS[perspective];

  return (
    <div className={`rounded-lg border ${config.bgColor.replace('100', '50')} border-${config.color.split('-')[1]}-200`}>
      <button
        type="button"
        onClick={onToggle}
        className={`w-full flex items-center justify-between px-3 py-2 text-left ${config.color}`}
      >
        <div className="flex items-center gap-2">
          <Icon size={16} />
          <span className="font-medium text-sm">{config.label}</span>
        </div>
        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {isExpanded && (
        <div className="px-3 pb-3 text-sm text-foreground prose prose-sm max-w-none">
          {content.split('\n').map((line, i) => (
            <p key={i} className="mb-2 last:mb-0">
              {renderTextWithCitations(line)}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Inline Citation Parser
// =============================================================================

/**
 * Parse inline citation markers like [Data: P&L FY2025] or [Source: ATO GST Guide]
 * and render them as styled inline pills within text.
 */
function renderTextWithCitations(text: string): React.ReactNode[] {
  const citationPattern = /\[(Data|Source):\s*([^\]]+)\]/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  while ((match = citationPattern.exec(text)) !== null) {
    // Add text before the citation
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const type = match[1]; // "Data" or "Source"
    const label = match[2]?.trim() ?? '';
    const isData = type === 'Data';

    parts.push(
      <span
        key={`cite-${match.index}`}
        className={`inline-flex items-center px-1.5 py-0.5 mx-0.5 text-[11px] font-medium rounded ${
          isData
            ? 'bg-primary/10 text-primary'
            : 'bg-teal-50 text-teal-700'
        }`}
        title={`${type}: ${label}`}
      >
        {label}
      </span>
    );

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

// =============================================================================
// Main Component
// =============================================================================

export function AgentChatMessage({ message, showMetadata = true }: AgentChatMessageProps) {
  const [expandedSections, setExpandedSections] = useState<Set<Perspective>>(new Set());
  const [showAllSections, setShowAllSections] = useState(true);

  // Parse perspective sections from content
  const sections = useMemo(() => {
    if (message.role !== 'assistant') return [];
    return parsePerspectiveSections(message.content);
  }, [message.content, message.role]);

  const hasSections = sections.length > 0;

  const toggleSection = (perspective: Perspective) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(perspective)) {
        next.delete(perspective);
      } else {
        next.add(perspective);
      }
      return next;
    });
  };

  const toggleAllSections = () => {
    if (showAllSections) {
      setExpandedSections(new Set());
    } else {
      setExpandedSections(new Set(sections.map((s) => s.perspective)));
    }
    setShowAllSections(!showAllSections);
  };

  // User message
  if (message.role === 'user') {
    return (
      <div className="flex gap-3">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center">
          <User className="w-4 h-4 text-teal-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-foreground">{message.content}</p>
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="flex gap-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
        <Bot className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0 space-y-3">
        {/* Escalation Banner */}
        {message.escalationRequired && showMetadata && (
          <EscalationBanner reason={message.escalationReason || null} />
        )}

        {/* Content with Perspective Sections */}
        {hasSections ? (
          <div className="space-y-2">
            {/* Section Toggle */}
            <div className="flex items-center justify-between">
              <PerspectiveBadgeList
                perspectives={sections.map((s) => s.perspective)}
                activePerspective={null}
              />
              <button
                type="button"
                onClick={toggleAllSections}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {showAllSections ? 'Collapse All' : 'Expand All'}
              </button>
            </div>

            {/* Perspective Sections */}
            <div className="space-y-2">
              {sections.map((section) => (
                <PerspectiveSection
                  key={section.perspective}
                  perspective={section.perspective}
                  content={section.content}
                  isExpanded={showAllSections || expandedSections.has(section.perspective)}
                  onToggle={() => toggleSection(section.perspective)}
                />
              ))}
            </div>
          </div>
        ) : (
          // Plain text response (no sections parsed)
          <div className="text-sm text-foreground prose prose-sm max-w-none">
            {message.isStreaming ? (
              <span>{message.content}<span className="animate-pulse">|</span></span>
            ) : (
              message.content.split('\n').map((line, i) => (
                <p key={i} className="mb-2 last:mb-0">
                  {renderTextWithCitations(line)}
                </p>
              ))
            )}
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="pt-2 border-t border-border">
            <p className="text-xs font-medium text-muted-foreground mb-1">Sources:</p>
            <div className="flex flex-wrap gap-1">
              {message.citations.map((citation, i) => (
                <a
                  key={i}
                  href={citation.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-2 py-0.5 text-xs text-teal-700 bg-teal-50 rounded hover:bg-teal-100 transition-colors"
                >
                  <span className="font-medium">[{citation.number}]</span>
                  <span className="truncate max-w-[150px]">
                    {citation.title || citation.source_type}
                  </span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Metadata Footer */}
        {showMetadata && message.confidence !== undefined && !message.isStreaming && (
          <div className="flex items-center gap-4 pt-2 text-xs text-muted-foreground">
            <ConfidenceIndicator confidence={message.confidence} showLabel size="sm" />
            {message.processingTimeMs && (
              <span>{(message.processingTimeMs / 1000).toFixed(1)}s</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
