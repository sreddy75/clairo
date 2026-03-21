'use client';

/**
 * OptionsDisplay Component
 *
 * Renders Magic Zone OPTIONS format insights with structured cards.
 * Parses markdown OPTIONS and renders them as styled cards with:
 * - Recommended option highlighted with green border
 * - Pros/Cons with checkmarks and x-marks
 * - "Best if" condition emphasized
 * - Action button for each option
 *
 * Also parses [Perspective] prefixed text blocks (e.g. [Quality], [Compliance])
 * into visually distinct, styled sections with colored perspective badges.
 *
 * Falls back to standard markdown rendering if no OPTIONS found.
 */

import {
  Check,
  CheckCircle2,
  LineChart,
  Scale,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';

import { cn } from '@/lib/utils';
import type { DataSnapshot } from '@/types/insights';

import { EvidenceSection } from './EvidenceSection';

interface ParsedOption {
  number: number;
  name: string;
  isRecommended: boolean;
  bestIf: string | null;
  pros: string[];
  cons: string[];
  action: string | null;
}

interface OptionsDisplayProps {
  content: string;
  optionsCount?: number | null;
  agentsUsed?: string[] | null;
  generationType?: string;
  dataSnapshot?: DataSnapshot | null;
}

function parseOptions(content: string): ParsedOption[] {
  const options: ParsedOption[] = [];

  // Match "### Option X: Name (Recommended)" pattern
  const optionPattern = /###\s*Option\s+(\d+):\s*([^\n(]+)(\(Recommended\))?/gi;
  const matches = Array.from(content.matchAll(optionPattern));

  for (let i = 0; i < matches.length; i++) {
    const match = matches[i];
    if (!match) continue;

    const number = parseInt(match[1] ?? '0', 10);
    const name = (match[2] ?? '').trim();
    const isRecommended = !!match[3];

    // Get content until next option or end
    const startPos = (match.index ?? 0) + match[0].length;
    const nextMatch = matches[i + 1];
    const endPos = nextMatch ? (nextMatch.index ?? content.length) : content.length;
    const optionContent = content.slice(startPos, endPos);

    // Extract "Best if:" line
    const bestIfMatch = optionContent.match(/\*\*Best if:\*\*\s*(.+?)(?:\n|$)/i);
    const bestIf = bestIfMatch?.[1]?.trim() ?? null;

    // Extract Pros
    const pros: string[] = [];
    const prosSection = optionContent.match(/\*\*Pros:\*\*([\s\S]*?)(?=\*\*Cons:\*\*|\*\*Action:\*\*|$)/i);
    if (prosSection?.[1]) {
      const proLines = prosSection[1].match(/[-•]\s*(.+)/g);
      if (proLines) {
        pros.push(...proLines.map(line => line.replace(/^[-•]\s*/, '').trim()));
      }
    }

    // Extract Cons
    const cons: string[] = [];
    const consSection = optionContent.match(/\*\*Cons:\*\*([\s\S]*?)(?=\*\*Action:\*\*|###|$)/i);
    if (consSection?.[1]) {
      const conLines = consSection[1].match(/[-•]\s*(.+)/g);
      if (conLines) {
        cons.push(...conLines.map(line => line.replace(/^[-•]\s*/, '').trim()));
      }
    }

    // Extract Action
    const actionMatch = optionContent.match(/\*\*Action:\*\*\s*(.+?)(?:\n|$)/i);
    const action = actionMatch?.[1]?.trim() ?? null;

    options.push({
      number,
      name,
      isRecommended,
      bestIf,
      pros,
      cons,
      action,
    });
  }

  return options;
}

function OptionCard({ option, evidence }: { option: ParsedOption; evidence?: DataSnapshot['evidence_items'] }) {
  return (
    <div
      className={`rounded-lg border-2 p-4 ${
        option.isRecommended
          ? 'border-status-success bg-status-success/10 ring-2 ring-status-success/20'
          : 'border-border bg-card'
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-sm font-bold ${
              option.isRecommended
                ? 'bg-status-success text-white'
                : 'bg-muted text-foreground'
            }`}
          >
            {option.number}
          </span>
          <h4 className="font-semibold text-foreground">{option.name}</h4>
        </div>
        {option.isRecommended && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-status-success/10 text-status-success rounded-full">
            <CheckCircle2 className="w-3 h-3" />
            Recommended
          </span>
        )}
      </div>

      {/* Best if */}
      {option.bestIf && (
        <div className="mb-3 px-3 py-2 bg-primary/10 border border-primary/20 rounded-md">
          <p className="text-sm text-primary">
            <span className="font-medium">Best if: </span>
            {option.bestIf}
          </p>
        </div>
      )}

      {/* Pros and Cons */}
      <div className="grid grid-cols-2 gap-4 mb-3">
        {/* Pros */}
        <div>
          <h5 className="text-xs font-medium text-muted-foreground uppercase mb-1">Pros</h5>
          <ul className="space-y-1">
            {option.pros.map((pro, idx) => (
              <li key={idx} className="flex items-start gap-1.5 text-sm text-foreground">
                <Check className="w-4 h-4 text-status-success flex-shrink-0 mt-0.5" />
                <span>{pro}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Cons */}
        <div>
          <h5 className="text-xs font-medium text-muted-foreground uppercase mb-1">Cons</h5>
          <ul className="space-y-1">
            {option.cons.map((con, idx) => (
              <li key={idx} className="flex items-start gap-1.5 text-sm text-foreground">
                <X className="w-4 h-4 text-status-danger flex-shrink-0 mt-0.5" />
                <span>{con}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Action */}
      {option.action && (
        <div className="pt-3 border-t border-border">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Action: </span>
            {option.action}
          </p>
        </div>
      )}

      {/* Evidence */}
      {evidence && <EvidenceSection evidence={evidence} />}
    </div>
  );
}

/* ── Perspective block parsing ──────────────────────────────────────── */

const PERSPECTIVE_CONFIG: Record<
  string,
  { label: string; icon: typeof ShieldCheck; color: string; bg: string; border: string }
> = {
  compliance: {
    label: 'Compliance',
    icon: ShieldCheck,
    color: 'text-primary',
    bg: 'bg-primary/10',
    border: 'border-primary/20',
  },
  quality: {
    label: 'Data Quality',
    icon: Search,
    color: 'text-status-warning',
    bg: 'bg-status-warning/10',
    border: 'border-status-warning/20',
  },
  strategy: {
    label: 'Strategy',
    icon: LineChart,
    color: 'text-status-success',
    bg: 'bg-status-success/10',
    border: 'border-status-success/20',
  },
  insight: {
    label: 'Insight',
    icon: Scale,
    color: 'text-accent-foreground',
    bg: 'bg-accent/10',
    border: 'border-accent/20',
  },
};

interface ParsedPerspectiveBlock {
  perspective: string;
  content: string;
}

/**
 * Splits text that contains [Perspective] markers into structured blocks.
 * Text before any marker becomes a "preamble" with perspective = ''.
 * E.g. "[Quality] The data shows..." → { perspective: "quality", content: "The data shows..." }
 */
function parsePerspectiveBlocks(text: string): ParsedPerspectiveBlock[] {
  const blocks: ParsedPerspectiveBlock[] = [];
  // Match [Word] at start of line or after newlines — case-insensitive
  const pattern = /\[([A-Za-z\s]+?)\]\s*/g;
  const matches = Array.from(text.matchAll(pattern));

  if (matches.length === 0) {
    return [{ perspective: '', content: text }];
  }

  // Preamble text before the first marker
  const firstIdx = matches[0]!.index ?? 0;
  const preamble = text.slice(0, firstIdx).trim();
  if (preamble) {
    blocks.push({ perspective: '', content: preamble });
  }

  for (let i = 0; i < matches.length; i++) {
    const m = matches[i]!;
    const perspectiveName = (m[1] ?? '').trim().toLowerCase();
    const startPos = (m.index ?? 0) + m[0].length;
    const nextMatch = matches[i + 1];
    const endPos = nextMatch ? (nextMatch.index ?? text.length) : text.length;
    const blockContent = text.slice(startPos, endPos).trim();

    if (blockContent) {
      blocks.push({ perspective: perspectiveName, content: blockContent });
    }
  }

  return blocks;
}

/** Returns true if the text contains perspective markers like [Quality], [Compliance], etc. */
function hasPerspectiveMarkers(text: string): boolean {
  const knownPerspectives = Object.keys(PERSPECTIVE_CONFIG);
  return knownPerspectives.some((p) =>
    new RegExp(`\\[${p}\\]`, 'i').test(text),
  );
}

function PerspectiveBlock({ block }: { block: ParsedPerspectiveBlock }) {
  const config = PERSPECTIVE_CONFIG[block.perspective];

  // Plain preamble or unknown perspective — render as normal markdown
  if (!config) {
    return (
      <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:text-muted-foreground">
        <ReactMarkdown>{block.content}</ReactMarkdown>
      </div>
    );
  }

  const Icon = config.icon;

  return (
    <div className={cn('rounded-lg border p-4', config.bg, config.border)}>
      <div className="flex items-center gap-2 mb-2.5">
        <Icon className={cn('w-4 h-4', config.color)} />
        <span className={cn('text-xs font-semibold uppercase tracking-wider', config.color)}>
          {config.label}
        </span>
      </div>
      <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:text-foreground prose-p:my-1.5 prose-ul:my-1.5 prose-li:my-0.5">
        <ReactMarkdown>{block.content}</ReactMarkdown>
      </div>
    </div>
  );
}

/* ── Main component ─────────────────────────────────────────────────── */

export function OptionsDisplay({
  content,
  optionsCount,
  agentsUsed,
  generationType,
  dataSnapshot,
}: OptionsDisplayProps) {
  const isMagicZone = generationType === 'magic_zone';
  const options = parseOptions(content);

  // If no options parsed, render as perspective blocks or plain markdown
  if (options.length === 0) {
    // Check for [Perspective] markers and render as styled blocks
    if (hasPerspectiveMarkers(content)) {
      const blocks = parsePerspectiveBlocks(content);
      return (
        <div className="space-y-3">
          {blocks.map((block, idx) => (
            <PerspectiveBlock key={idx} block={block} />
          ))}
        </div>
      );
    }

    return (
      <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:text-muted-foreground">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    );
  }

  // Extract any intro text before the first option
  const firstOptionMatch = content.match(/###\s*Option\s+\d+:/);
  const introText = firstOptionMatch
    ? content.slice(0, firstOptionMatch.index).trim()
    : null;

  return (
    <div className="space-y-4">
      {/* Magic Zone Badge */}
      {isMagicZone && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-accent/10 text-accent-foreground rounded-full">
              <Sparkles className="w-3.5 h-3.5" />
              Magic Zone Analysis
            </span>
            {optionsCount && optionsCount > 0 && (
              <span className="text-xs text-muted-foreground">
                {optionsCount} options
              </span>
            )}
          </div>
          {agentsUsed && agentsUsed.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Analyzed by: {agentsUsed.map(a => a.charAt(0).toUpperCase() + a.slice(1)).join(', ')}
            </p>
          )}
        </div>
      )}

      {/* Intro Text — may contain [Perspective] blocks */}
      {introText && (
        hasPerspectiveMarkers(introText) ? (
          <div className="space-y-3">
            {parsePerspectiveBlocks(introText).map((block, idx) => (
              <PerspectiveBlock key={idx} block={block} />
            ))}
          </div>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:text-muted-foreground">
            <ReactMarkdown>{introText}</ReactMarkdown>
          </div>
        )
      )}

      {/* Options Grid */}
      <div className="space-y-3">
        {options.map((option) => (
          <OptionCard key={option.number} option={option} evidence={dataSnapshot?.evidence_items} />
        ))}
      </div>
    </div>
  );
}

export default OptionsDisplay;
