'use client';

import { useAuth } from '@clerk/nextjs';
import { useState } from 'react';

import { Input } from '@/components/ui/input';
import { confirmScenarioField } from '@/lib/api/tax-planning';
import { formatCurrency } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { Provenance } from '@/types/tax-planning';

import { ProvenanceBadge } from './ProvenanceBadge';

interface InlineConfirmInputProps {
  planId: string;
  scenarioId: string;
  fieldPath: string;
  value: number;
  provenance: Provenance | undefined;
  onConfirmed?: (next: { value: number; provenance: Provenance }) => void;
  className?: string;
}

/**
 * Spec 059 FR-015 — controlled input with inline confirm-to-green UX.
 *
 * - `estimated` → amber left border + editable; on blur/Enter with a
 *   non-empty numeric value we PATCH the provenance to `confirmed` (and
 *   optionally update the value).
 * - `confirmed` / `derived` → renders as read-only text with the relevant
 *   provenance badge.
 *
 * Empty confirms surface as a visible error; we never auto-confirm a blank
 * input (spec research.md R13).
 */
export function InlineConfirmInput({
  planId,
  scenarioId,
  fieldPath,
  value,
  provenance,
  onConfirmed,
  className,
}: InlineConfirmInputProps) {
  const { getToken } = useAuth();
  const [draft, setDraft] = useState<string>(String(value));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localProvenance, setLocalProvenance] = useState<Provenance | undefined>(
    provenance,
  );

  const isEditable = localProvenance === 'estimated';

  if (!isEditable) {
    return (
      <span className={cn('inline-flex items-center gap-1.5 tabular-nums', className)}>
        {formatCurrency(value)}
        <ProvenanceBadge provenance={localProvenance} />
      </span>
    );
  }

  const commit = async () => {
    setError(null);
    const trimmed = draft.trim();
    if (!trimmed) {
      setError('Enter a value before confirming');
      return;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
      setError('Not a number');
      return;
    }
    setSaving(true);
    try {
      const token = await getToken();
      if (!token) throw new Error('not authenticated');
      await confirmScenarioField(token, planId, scenarioId, fieldPath, parsed);
      setLocalProvenance('confirmed');
      onConfirmed?.({ value: parsed, provenance: 'confirmed' });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      <Input
        type="number"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            commit();
          }
        }}
        disabled={saving}
        className={cn(
          'h-7 w-32 px-2 text-sm tabular-nums border-l-4 border-l-amber-400',
          saving && 'opacity-60',
        )}
      />
      <ProvenanceBadge provenance={localProvenance} />
      {error && (
        <span className="text-[10px] text-red-600" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
