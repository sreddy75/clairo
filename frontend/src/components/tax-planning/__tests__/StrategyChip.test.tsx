/**
 * Unit tests for StrategyChip (Spec 060 T025).
 *
 * Covers the three verification colour states, the unverified muted-icon
 * rendering (T050), and the click/keyboard open callback.
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { StrategyChip } from '@/components/tax-planning/StrategyChip';
import type { StrategyCitationStatus } from '@/types/tax-planning';

const baseProps = {
  strategyId: 'CLR-012',
  citedName: 'Concessional super contributions',
};

function renderChip(
  status: StrategyCitationStatus,
  onClick?: (id: string) => void,
) {
  return render(
    <StrategyChip
      {...baseProps}
      status={status}
      onClick={onClick}
    />,
  );
}

describe('StrategyChip', () => {
  it.each<[StrategyCitationStatus, RegExp]>([
    ['verified', /emerald/],
    ['partially_verified', /amber/],
    ['unverified', /red/],
  ])('renders %s state with the matching colour family', (status, re) => {
    const { container } = renderChip(status);
    const span = container.querySelector('[role="button"]')!;
    expect(span.className).toMatch(re);
  });

  it('renders the bracketed markup verbatim', () => {
    renderChip('verified');
    expect(
      screen.getByText(/\[CLR-012: Concessional super contributions\]/),
    ).toBeInTheDocument();
  });

  it('shows a muted alert icon only in the unverified state', () => {
    const { rerender } = renderChip('verified');
    expect(
      document.querySelector('[role="button"] svg'),
    ).not.toBeInTheDocument();
    rerender(
      <StrategyChip
        {...baseProps}
        status="unverified"
      />,
    );
    expect(document.querySelector('[role="button"] svg')).toBeInTheDocument();
  });

  it('fires onClick with the strategy id on click', () => {
    const onClick = vi.fn();
    renderChip('verified', onClick);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledWith('CLR-012');
  });

  it('fires onClick with the strategy id on Enter keydown', () => {
    const onClick = vi.fn();
    renderChip('verified', onClick);
    fireEvent.keyDown(screen.getByRole('button'), { key: 'Enter' });
    expect(onClick).toHaveBeenCalledWith('CLR-012');
  });

  it('sets a status-specific title attribute for hover/screen readers', () => {
    renderChip('unverified');
    const span = screen.getByRole('button');
    expect(span.getAttribute('title')).toMatch(/Strategy not found/);
  });
});
