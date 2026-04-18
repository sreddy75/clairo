'use client';

import { AlertTriangle } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import type { ReviewerDisagreement } from '@/lib/api/tax-planning';

interface ReviewerWarningBannerProps {
  numbersVerified: boolean;
  disagreements: ReviewerDisagreement[];
}

/**
 * Spec 059 FR-013 — top-of-page amber banner shown when the reviewer's
 * independent ground-truth re-derivation disagrees with a modeller scenario
 * by more than $1. Warns but does not block rendering; the accountant sees
 * the underlying scenarios alongside the banner and can judge.
 */
export function ReviewerWarningBanner({
  numbersVerified,
  disagreements,
}: ReviewerWarningBannerProps) {
  if (numbersVerified || disagreements.length === 0) return null;

  const affectedScenarios = new Set(disagreements.map((d) => d.scenario_id));

  return (
    <Alert className="border-amber-300 bg-amber-50 text-amber-900">
      <AlertTriangle className="h-4 w-4 text-amber-700" />
      <AlertTitle className="text-amber-900">
        Calculator disagreement — {disagreements.length} figure
        {disagreements.length === 1 ? '' : 's'} failed verification
      </AlertTitle>
      <AlertDescription className="text-amber-800">
        <p className="mb-2">
          The reviewer re-derived {affectedScenarios.size} scenario
          {affectedScenarios.size === 1 ? '' : 's'} from raw financials and
          found disagreements above the $1 tolerance. Review the underlying
          figures before sharing with the client.
        </p>
        <ul className="text-xs space-y-1 mt-2">
          {disagreements.slice(0, 5).map((d, i) => (
            <li key={`${d.scenario_id}-${d.field_path}-${i}`} className="font-mono">
              <span className="font-semibold">{d.field_path}</span>:
              {' '}expected ${d.expected.toLocaleString()}, got $
              {d.got.toLocaleString()} (delta ${d.delta.toLocaleString()})
            </li>
          ))}
          {disagreements.length > 5 && (
            <li className="text-amber-700 italic">
              + {disagreements.length - 5} more
            </li>
          )}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
