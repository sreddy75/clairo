'use client';

import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type {
  CitationVerification,
  VerificationStatus,
} from '@/types/tax-planning';

interface CitationBadgeProps {
  verification: CitationVerification | null | undefined;
}

const STATUS_CONFIG = {
  verified: {
    label: 'Sources verified',
    className: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
  },
  partially_verified: {
    label: 'Some sources unverified',
    className: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  },
  unverified: {
    label: 'Sources could not be verified',
    className: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  },
  no_citations: {
    label: 'General knowledge',
    className: 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
  },
  // Spec 059 FR-021 / Spec 061 FR-010 (Q2=C) — amber variant for sub-threshold
  // confidence. Under Q2=C the AI's response is preserved; scenarios are
  // cleared; the accountant decides whether to rely on it. The prior "AI
  // declined" copy was pre-Q2=C and misdescribed the current behaviour.
  low_confidence: {
    label: 'Low source confidence — verify before relying',
    className: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  },
} as const;

// Spec 060 T048 — combined status rollup.
// With strategy citations present the overall badge colour must reflect
// the *worst* component state. Mapping (least-severe → most-severe):
//   verified < partially_verified/low_confidence < unverified
// "no_citations" is neutral and only wins when nothing else is set.
function rollupStatus(
  compliance: VerificationStatus,
  strategyWorst: 'verified' | 'partially_verified' | 'unverified' | null,
): VerificationStatus {
  const severity: Record<string, number> = {
    no_citations: 0,
    verified: 1,
    low_confidence: 2,
    partially_verified: 2,
    unverified: 3,
  };
  if (!strategyWorst) return compliance;
  const cs = severity[compliance] ?? 0;
  const ss = severity[strategyWorst] ?? 0;
  if (ss > cs) {
    return strategyWorst === 'unverified' ? 'unverified' : 'partially_verified';
  }
  return compliance;
}

function strategyCounts(verification: CitationVerification): {
  total: number;
  verified: number;
  partial: number;
  unverified: number;
  worst: 'verified' | 'partially_verified' | 'unverified' | null;
} {
  const items = verification.strategy_citations ?? [];
  let verified = 0;
  let partial = 0;
  let unverified = 0;
  for (const s of items) {
    if (s.status === 'verified') verified += 1;
    else if (s.status === 'partially_verified') partial += 1;
    else unverified += 1;
  }
  const worst =
    unverified > 0
      ? ('unverified' as const)
      : partial > 0
        ? ('partially_verified' as const)
        : verified > 0
          ? ('verified' as const)
          : null;
  return {
    total: items.length,
    verified,
    partial,
    unverified,
    worst,
  };
}

export function CitationBadge({ verification }: CitationBadgeProps) {
  if (!verification) return null;

  const counts = strategyCounts(verification);
  const rolledUp = rollupStatus(verification.status, counts.worst);
  const config = STATUS_CONFIG[rolledUp] || STATUS_CONFIG.no_citations;

  const strategyLabel =
    counts.total === 0
      ? null
      : counts.total === 1
        ? '1 strategy cited'
        : `${counts.total} strategies cited`;

  const strategyQualifier =
    counts.total === 0
      ? null
      : counts.unverified > 0
        ? `${counts.unverified} unverified`
        : counts.partial > 0
          ? `${counts.partial} partial`
          : 'all verified';

  const baseTooltip =
    verification.status === 'no_citations'
      ? 'Response is based on general tax knowledge without specific source citations'
      : verification.status === 'low_confidence'
        ? 'The retrieved source confidence was below threshold. The response is shown for context but scenarios have not been persisted — verify against ATO guidance before relying on any figure.'
        : `${verification.verified_count} of ${verification.total_citations} citations verified against knowledge base`;

  const tooltipText =
    counts.total === 0
      ? baseTooltip
      : `${baseTooltip} · ${counts.total} strategy ${counts.total === 1 ? 'citation' : 'citations'} (${counts.verified} verified, ${counts.partial} partial, ${counts.unverified} unverified)`;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="secondary"
            className={cn('mt-1 cursor-default text-xs font-normal', config.className)}
          >
            {config.label}
            {strategyLabel && (
              <span className="ml-1 opacity-80">
                · {strategyLabel} ({strategyQualifier})
              </span>
            )}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">{tooltipText}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
