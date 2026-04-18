/**
 * Hydrate published tax strategies for inline chat citation chips (Spec 060 T040).
 *
 * Takes an array of CLR-XXX identifiers and fetches the published hydration
 * payload via `GET /api/v1/tax-strategies/public?ids=...`. Uses TanStack Query
 * so the same strategy id is fetched once per session and shared across every
 * chip that references it.
 */

import { useAuth } from '@clerk/nextjs';
import { useQuery } from '@tanstack/react-query';

import { apiClient } from '@/lib/api-client';

export interface PublicTaxStrategy {
  strategy_id: string;
  name: string;
  categories: string[];
  implementation_text: string;
  explanation_text: string;
  ato_sources: string[];
  case_refs: string[];
  fy_applicable_from: string | null;
  fy_applicable_to: string | null;
  version: number;
  is_platform: boolean;
}

interface PublicHydrationBatchResponse {
  data: PublicTaxStrategy[];
}

// Backend caps the batch at 20 ids (router.py). Keep this in sync.
export const STRATEGY_HYDRATION_BATCH_LIMIT = 20;

function dedupe(ids: string[]): string[] {
  return Array.from(new Set(ids.filter(Boolean))).sort();
}

export const strategyHydrationQueryKey = (ids: string[]) =>
  ['tax-strategies', 'hydrate', ...dedupe(ids)] as const;

/**
 * Fetch a batch of strategies and return a Map keyed by strategy_id.
 *
 * `enabled` defaults to true when `ids` is non-empty. Callers don't need to
 * toggle it — the query stays idle when there are no ids.
 */
export function useStrategyHydration(
  strategyIds: string[],
  options: { enabled?: boolean } = {},
) {
  const { getToken } = useAuth();
  const ids = dedupe(strategyIds);
  const enabled = (options.enabled ?? true) && ids.length > 0;

  return useQuery<Map<string, PublicTaxStrategy>>({
    queryKey: strategyHydrationQueryKey(ids),
    queryFn: async () => {
      if (ids.length > STRATEGY_HYDRATION_BATCH_LIMIT) {
        throw new Error(
          `Cannot hydrate more than ${STRATEGY_HYDRATION_BATCH_LIMIT} strategies in one batch`,
        );
      }
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const response = await apiClient.get(
        `/api/v1/tax-strategies/public?ids=${encodeURIComponent(ids.join(','))}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const body =
        await apiClient.handleResponse<PublicHydrationBatchResponse>(response);
      const map = new Map<string, PublicTaxStrategy>();
      for (const row of body.data) map.set(row.strategy_id, row);
      return map;
    },
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}
