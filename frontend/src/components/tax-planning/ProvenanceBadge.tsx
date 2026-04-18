'use client';

import { cn } from '@/lib/utils';
import type { Provenance } from '@/types/tax-planning';

interface ProvenanceBadgeProps {
  provenance: Provenance | undefined;
  className?: string;
}

const LABEL: Record<Provenance, string> = {
  confirmed: 'Confirmed',
  derived: 'Derived',
  estimated: 'Estimated',
};

// Colour tokens follow the design system's status semantics (green=good,
// neutral=derived, amber=attention). `estimated` is amber precisely because
// the accountant needs to review before exporting (FR-016).
const STYLES: Record<Provenance, string> = {
  confirmed:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
  derived: 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
  estimated:
    'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
};

/**
 * Spec 059 FR-011 — renders a small pill badge indicating how a numeric
 * field was produced. An absent provenance (no key in source_tags) renders
 * nothing — we do not paint fields red just because the tag is missing, as
 * pre-spec-059 scenarios will have empty source_tags.
 */
export function ProvenanceBadge({ provenance, className }: ProvenanceBadgeProps) {
  if (!provenance) return null;
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-1.5 py-0 text-[10px] font-medium',
        STYLES[provenance],
        className,
      )}
    >
      {LABEL[provenance]}
    </span>
  );
}
