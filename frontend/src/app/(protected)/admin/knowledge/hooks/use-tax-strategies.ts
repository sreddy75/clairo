'use client';

/**
 * TanStack Query hooks for the admin Strategies tab (Spec 060 T045).
 *
 * Mutations invalidate the affected query keys on success so the list/detail
 * refetch without manual plumbing. No optimistic updates — the list columns
 * (status + reviewer snapshot + version) are server-authoritative and a
 * post-mutation refetch is cheap at Phase 1 scale (<500 rows).
 */

import { useAuth } from '@clerk/nextjs';
import {
  type UseMutationOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';

import {
  approveAndPublish,
  getPipelineStats,
  getStrategyDetail,
  listStrategies,
  rejectToDraft,
  seedFromCsv,
  submitForReview,
  triggerStage,
  type AuthoringJob,
  type ListStrategiesParams,
  type PipelineStatsResponse,
  type SeedSummaryResponse,
  type StrategyStage,
  type TaxStrategyDetail,
  type TaxStrategyListResponse,
} from '@/lib/api/tax-strategies';

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const taxStrategiesKeys = {
  all: ['admin', 'tax-strategies'] as const,
  list: (params: ListStrategiesParams) =>
    [...taxStrategiesKeys.all, 'list', params] as const,
  detail: (strategyId: string) =>
    [...taxStrategiesKeys.all, 'detail', strategyId] as const,
  pipelineStats: () => [...taxStrategiesKeys.all, 'pipeline-stats'] as const,
};

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useStrategyList(params: ListStrategiesParams = {}) {
  const { getToken } = useAuth();
  return useQuery<TaxStrategyListResponse>({
    queryKey: taxStrategiesKeys.list(params),
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return listStrategies(token, params);
    },
    staleTime: 30_000,
  });
}

export function useStrategyDetail(
  strategyId: string | null,
  options: { enabled?: boolean } = {},
) {
  const { getToken } = useAuth();
  return useQuery<TaxStrategyDetail>({
    queryKey: taxStrategiesKeys.detail(strategyId ?? '__disabled__'),
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return getStrategyDetail(token, strategyId!);
    },
    enabled: (options.enabled ?? true) && !!strategyId,
  });
}

export function usePipelineStats(options: { enabled?: boolean } = {}) {
  const { getToken } = useAuth();
  return useQuery<PipelineStatsResponse>({
    queryKey: taxStrategiesKeys.pipelineStats(),
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return getPipelineStats(token);
    },
    enabled: options.enabled ?? true,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

type TriggerStageVariables = {
  strategyId: string;
  stage: Exclude<StrategyStage, 'publish'>;
};

function useInvalidateStrategy() {
  const queryClient = useQueryClient();
  return (strategyId: string) => {
    queryClient.invalidateQueries({ queryKey: taxStrategiesKeys.all });
    // The detail key is more specific but is already inside `all`.
    queryClient.invalidateQueries({
      queryKey: taxStrategiesKeys.detail(strategyId),
    });
  };
}

export function useTriggerStage(
  options?: UseMutationOptions<AuthoringJob, Error, TriggerStageVariables>,
) {
  const { getToken } = useAuth();
  const invalidate = useInvalidateStrategy();
  return useMutation<AuthoringJob, Error, TriggerStageVariables>({
    mutationFn: async ({ strategyId, stage }) => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return triggerStage(token, strategyId, stage);
    },
    onSuccess: (...args) => {
      invalidate(args[1].strategyId);
      return options?.onSuccess?.(...args);
    },
    ...options,
  });
}

export function useSubmitForReview(
  options?: UseMutationOptions<TaxStrategyDetail, Error, string>,
) {
  const { getToken } = useAuth();
  const invalidate = useInvalidateStrategy();
  return useMutation<TaxStrategyDetail, Error, string>({
    mutationFn: async (strategyId) => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return submitForReview(token, strategyId);
    },
    onSuccess: (...args) => {
      invalidate(args[1]);
      return options?.onSuccess?.(...args);
    },
    ...options,
  });
}

export function useApproveAndPublish(
  options?: UseMutationOptions<AuthoringJob, Error, string>,
) {
  const { getToken } = useAuth();
  const invalidate = useInvalidateStrategy();
  return useMutation<AuthoringJob, Error, string>({
    mutationFn: async (strategyId) => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return approveAndPublish(token, strategyId);
    },
    onSuccess: (...args) => {
      invalidate(args[1]);
      return options?.onSuccess?.(...args);
    },
    ...options,
  });
}

type RejectVariables = { strategyId: string; reviewerNotes: string };

export function useRejectToDraft(
  options?: UseMutationOptions<TaxStrategyDetail, Error, RejectVariables>,
) {
  const { getToken } = useAuth();
  const invalidate = useInvalidateStrategy();
  return useMutation<TaxStrategyDetail, Error, RejectVariables>({
    mutationFn: async ({ strategyId, reviewerNotes }) => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return rejectToDraft(token, strategyId, reviewerNotes);
    },
    onSuccess: (...args) => {
      invalidate(args[1].strategyId);
      return options?.onSuccess?.(...args);
    },
    ...options,
  });
}

export function useSeedFromCsv(
  options?: UseMutationOptions<SeedSummaryResponse, Error, void>,
) {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  return useMutation<SeedSummaryResponse, Error, void>({
    mutationFn: async () => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return seedFromCsv(token);
    },
    onSuccess: (...args) => {
      queryClient.invalidateQueries({ queryKey: taxStrategiesKeys.all });
      return options?.onSuccess?.(...args);
    },
    ...options,
  });
}
