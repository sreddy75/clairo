'use client';

/**
 * EnhancedCitationPanel Component
 *
 * Displays numbered citations from a knowledge chat response in a
 * collapsible panel. Each citation shows a source type icon, title,
 * section reference, and expands to reveal a text preview and source
 * URL link. Verified citations display a checkmark; unverified ones
 * show a warning indicator.
 */

import { CheckCircle2, ChevronDown, ExternalLink, AlertTriangle } from 'lucide-react';
import { useState } from 'react';

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

/** Enhanced citation with verification status */
export interface Citation {
  number: number;
  title: string | null;
  url: string;
  source_type: string;
  section_ref: string | null;
  effective_date: string | null;
  text_preview: string;
  score: number;
  verified: boolean;
}

interface EnhancedCitationPanelProps {
  /** Array of citations to display */
  citations: Citation[];
  /** Additional CSS classes */
  className?: string;
}

// =============================================================================
// Source type icon mapping
// =============================================================================

const SOURCE_TYPE_ICONS: Record<string, string> = {
  legislation: '\uD83D\uDCDC',   // scroll
  ato_ruling: '\uD83D\uDCCB',    // clipboard
  case_law: '\u2696\uFE0F',      // scales
  ato_web: '\uD83D\uDCCB',       // clipboard
  ato_rss: '\uD83D\uDCCB',       // clipboard
  ato_guide: '\uD83D\uDCCB',     // clipboard
  tpb: '\uD83D\uDCCB',           // clipboard
  treasury: '\uD83D\uDCC4',      // page
};

function getSourceIcon(sourceType: string): string {
  return SOURCE_TYPE_ICONS[sourceType] || '\uD83D\uDCC4'; // default: page
}

function getSourceLabel(sourceType: string): string {
  const labels: Record<string, string> = {
    legislation: 'Legislation',
    ato_ruling: 'ATO Ruling',
    case_law: 'Case Law',
    ato_web: 'ATO Guidance',
    ato_rss: 'ATO Ruling',
    ato_guide: 'ATO Guide',
    tpb: 'TPB',
    treasury: 'Treasury',
  };
  return labels[sourceType] || sourceType;
}

// =============================================================================
// Individual Citation Item
// =============================================================================

interface CitationItemProps {
  citation: Citation;
}

function CitationItem({ citation }: CitationItemProps) {
  const [expanded, setExpanded] = useState(false);
  const icon = getSourceIcon(citation.source_type);
  const sourceLabel = getSourceLabel(citation.source_type);

  return (
    <Collapsible open={expanded} onOpenChange={setExpanded}>
      <CollapsibleTrigger className="flex w-full items-start gap-2 text-left group rounded-lg p-2 hover:bg-muted transition-colors">
        {/* Citation number */}
        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-muted text-[10px] font-bold text-muted-foreground shrink-0 mt-0.5">
          {citation.number}
        </span>

        {/* Source type icon */}
        <span className="text-sm shrink-0 mt-0.5" aria-hidden="true">
          {icon}
        </span>

        {/* Title and metadata */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium text-foreground truncate">
              {citation.title || sourceLabel}
            </span>

            {/* Verified / unverified indicator */}
            {citation.verified ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-status-success shrink-0" />
            ) : (
              <AlertTriangle className="w-3.5 h-3.5 text-status-warning shrink-0" />
            )}
          </div>

          {/* Section ref and source type label */}
          <div className="flex items-center gap-2 mt-0.5">
            {citation.section_ref && (
              <span className="text-[10px] font-mono text-muted-foreground">
                {citation.section_ref}
              </span>
            )}
            <span className="text-[10px] text-muted-foreground/70">
              {sourceLabel}
            </span>
            {citation.effective_date && (
              <span className="text-[10px] text-muted-foreground/70">
                {citation.effective_date}
              </span>
            )}
          </div>
        </div>

        {/* Expand chevron */}
        <ChevronDown
          className={cn(
            'w-4 h-4 text-muted-foreground/70 shrink-0 transition-transform duration-200 mt-0.5',
            expanded && 'rotate-180',
          )}
        />
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="ml-7 pl-2 border-l-2 border-border mt-1 mb-2">
          {/* Text preview */}
          <p className="text-xs text-muted-foreground leading-relaxed whitespace-pre-line">
            {citation.text_preview}
          </p>

          {/* Source link */}
          {citation.url && (
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 mt-2 text-[11px] font-medium text-primary hover:underline"
            >
              View source
              <ExternalLink className="w-3 h-3" />
            </a>
          )}

          {/* Unverified warning */}
          {!citation.verified && (
            <p className="mt-1.5 text-[10px] text-status-warning italic">
              This citation could not be verified against the knowledge base.
            </p>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

// =============================================================================
// Panel Component
// =============================================================================

export function EnhancedCitationPanel({ citations, className }: EnhancedCitationPanelProps) {
  const [panelOpen, setPanelOpen] = useState(false);

  if (!citations || citations.length === 0) {
    return null;
  }

  const verifiedCount = citations.filter((c) => c.verified).length;
  const totalCount = citations.length;

  return (
    <div
      className={cn(
        'mt-3 pt-3 border-t border-border',
        className,
      )}
    >
      <Collapsible open={panelOpen} onOpenChange={setPanelOpen}>
        <CollapsibleTrigger className="flex w-full items-center gap-2 text-left group">
          <ChevronDown
            className={cn(
              'h-3.5 w-3.5 text-muted-foreground/70 transition-transform duration-200',
              panelOpen && 'rotate-180',
            )}
          />
          <span className="text-xs font-medium text-muted-foreground group-hover:text-foreground transition-colors">
            {totalCount} source{totalCount !== 1 ? 's' : ''} cited
          </span>
          <span className="text-[10px] text-muted-foreground/70">
            ({verifiedCount}/{totalCount} verified)
          </span>
        </CollapsibleTrigger>

        <CollapsibleContent className="mt-2">
          <div className="space-y-0.5">
            {citations.map((citation) => (
              <CitationItem key={citation.number} citation={citation} />
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

export default EnhancedCitationPanel;
