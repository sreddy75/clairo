'use client';

import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { CitationVerification } from '@/types/tax-planning';

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
  // Spec 059 FR-021 — amber variant for "retrieval confidence below 0.5".
  low_confidence: {
    label: 'AI declined — low source confidence',
    className: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  },
} as const;

export function CitationBadge({ verification }: CitationBadgeProps) {
  if (!verification) return null;

  const config = STATUS_CONFIG[verification.status] || STATUS_CONFIG.no_citations;

  const tooltipText =
    verification.status === 'no_citations'
      ? 'Response is based on general tax knowledge without specific source citations'
      : verification.status === 'low_confidence'
        ? 'AI declined to answer because the retrieved source confidence was below threshold. Consult ATO guidance directly.'
        : `${verification.verified_count} of ${verification.total_citations} citations verified against knowledge base`;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="secondary"
            className={cn('mt-1 cursor-default text-xs font-normal', config.className)}
          >
            {config.label}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">{tooltipText}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
