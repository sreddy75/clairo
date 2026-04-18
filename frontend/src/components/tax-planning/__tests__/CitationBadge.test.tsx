/**
 * Unit tests for CitationBadge strategy-citation rollup (Spec 060 T047).
 *
 * Verifies that strategy counts land in the badge label and that the
 * overall verification status collapses to the worst component state.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { CitationBadge } from '@/components/tax-planning/CitationBadge';
import type { CitationVerification } from '@/types/tax-planning';

function base(): CitationVerification {
  return {
    total_citations: 0,
    verified_count: 0,
    unverified_count: 0,
    verification_rate: 1.0,
    status: 'verified',
    citations: [],
    strategy_citations: [],
  };
}

describe('CitationBadge strategy rollup', () => {
  it('renders nothing when verification is null', () => {
    const { container } = render(<CitationBadge verification={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('does NOT append strategy count when there are no strategy citations', () => {
    render(<CitationBadge verification={base()} />);
    expect(screen.queryByText(/strategy cited/)).not.toBeInTheDocument();
    expect(screen.queryByText(/strategies cited/)).not.toBeInTheDocument();
  });

  it('appends "N strategies cited (all verified)" for all-verified citations', () => {
    const v = {
      ...base(),
      strategy_citations: [
        { strategy_id: 'CLR-012', cited_name: 'A', status: 'verified', name_drift: 0.1 },
        { strategy_id: 'CLR-241', cited_name: 'B', status: 'verified', name_drift: 0.2 },
      ] as CitationVerification['strategy_citations'],
    };
    render(<CitationBadge verification={v} />);
    expect(screen.getByText(/2 strategies cited/)).toBeInTheDocument();
    expect(screen.getByText(/all verified/)).toBeInTheDocument();
  });

  it('rolls up status to partially_verified when any strategy partial', () => {
    const v: CitationVerification = {
      ...base(),
      status: 'verified',
      strategy_citations: [
        { strategy_id: 'CLR-012', cited_name: 'A', status: 'verified', name_drift: 0.1 },
        { strategy_id: 'CLR-241', cited_name: 'drifted', status: 'partially_verified', name_drift: 0.45 },
      ],
    };
    const { container } = render(<CitationBadge verification={v} />);
    // Badge label is "Some sources unverified" when rolled up to partially_verified.
    expect(container.textContent).toMatch(/Some sources unverified/);
    expect(container.textContent).toMatch(/1 partial/);
  });

  it('rolls up to unverified when any strategy unverified', () => {
    const v: CitationVerification = {
      ...base(),
      status: 'verified',
      strategy_citations: [
        { strategy_id: 'CLR-012', cited_name: 'A', status: 'verified', name_drift: 0.1 },
        { strategy_id: 'CLR-999', cited_name: 'Fake', status: 'unverified', name_drift: 0 },
      ],
    };
    const { container } = render(<CitationBadge verification={v} />);
    expect(container.textContent).toMatch(/Sources could not be verified/);
    expect(container.textContent).toMatch(/1 unverified/);
  });

  it('preserves the original status when no strategy citations are present', () => {
    const v: CitationVerification = {
      ...base(),
      status: 'low_confidence',
      strategy_citations: [],
    };
    const { container } = render(<CitationBadge verification={v} />);
    expect(container.textContent).toMatch(/Low source confidence/);
  });
});
