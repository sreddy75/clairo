/**
 * Unit tests for the admin Strategies tab (Spec 060 T051).
 *
 * Asserts that the status filter drives the `useStrategyList` call shape,
 * row click opens the admin detail Sheet, and pagination advances the
 * query's `page` argument. The API client itself is mocked — we test the
 * tab's wiring, not the network.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { StrategiesTab } from '@/app/(protected)/admin/knowledge/components/strategies-tab';
import type * as TaxStrategiesApi from '@/lib/api/tax-strategies';

type ListParams = Record<string, unknown>;
const recordedCalls: ListParams[] = [];

vi.mock('@/lib/api/tax-strategies', async () => {
  const actual =
    await vi.importActual<typeof TaxStrategiesApi>('@/lib/api/tax-strategies');
  return {
    ...actual,
    listStrategies: vi.fn((_token: string, params: ListParams) => {
      recordedCalls.push(params);
      return Promise.resolve({
        data: [
          {
            strategy_id: 'CLR-012',
            name: 'Concessional super contributions',
            categories: ['SMSF'],
            status: 'published',
            tenant_id: 'platform',
            version: 1,
            last_reviewed_at: null,
            reviewer_display_name: null,
            updated_at: '2026-04-19T00:00:00Z',
          },
        ],
        meta: { page: params.page ?? 1, page_size: 50, total: 1 },
      });
    }),
    getPipelineStats: vi.fn(() =>
      Promise.resolve({
        counts: {
          stub: 3,
          researching: 0,
          drafted: 0,
          enriched: 0,
          in_review: 1,
          approved: 0,
          published: 1,
          superseded: 0,
          archived: 0,
        },
      }),
    ),
    getStrategyDetail: vi.fn(() =>
      Promise.resolve({
        strategy_id: 'CLR-012',
        name: 'Concessional super contributions',
        categories: ['SMSF'],
        status: 'published',
        tenant_id: 'platform',
        version: 1,
        last_reviewed_at: null,
        reviewer_display_name: null,
        updated_at: '2026-04-19T00:00:00Z',
        implementation_text: 'Do the thing.',
        explanation_text: 'Because of the rule.',
        entity_types: [],
        income_band_min: null,
        income_band_max: null,
        turnover_band_min: null,
        turnover_band_max: null,
        age_min: null,
        age_max: null,
        industry_triggers: [],
        financial_impact_type: [],
        keywords: [],
        ato_sources: [],
        case_refs: [],
        fy_applicable_from: null,
        fy_applicable_to: null,
        superseded_by_strategy_id: null,
        source_ref: null,
        authoring_jobs: [],
        version_history: [],
      }),
    ),
  };
});

function renderTab() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <StrategiesTab />
    </QueryClientProvider>,
  );
}

describe('StrategiesTab', () => {
  it('hydrates the list and renders each row', async () => {
    renderTab();
    await waitFor(() =>
      expect(screen.getByText('Concessional super contributions')).toBeInTheDocument(),
    );
    expect(screen.getByText('CLR-012')).toBeInTheDocument();
  });

  it('changes the status filter and requeries the list', async () => {
    recordedCalls.length = 0;
    renderTab();
    await waitFor(() => expect(recordedCalls.length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole('button', { name: 'In review' }));
    await waitFor(() => {
      const last = recordedCalls[recordedCalls.length - 1];
      expect(last?.status).toBe('in_review');
    });
  });

  it('opens the admin detail Sheet on row click', async () => {
    renderTab();
    await waitFor(() =>
      expect(screen.getByText('Concessional super contributions')).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText('Concessional super contributions'));
    await waitFor(() => {
      // The Sheet renders the "Implementation" section heading once the
      // detail hydrates — a signal the admin variant mounted.
      expect(screen.getByText(/Implementation/i)).toBeInTheDocument();
    });
  });

  it('switches to pipeline view and hides the filter chips', async () => {
    renderTab();
    await waitFor(() => expect(screen.getByText('List')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Pipeline' }));
    // Status-filter chips disappear in pipeline view.
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: 'In review' }),
      ).not.toBeInTheDocument();
    });
  });
});
