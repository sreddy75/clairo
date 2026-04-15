/**
 * React Query hooks for BAS session detail data.
 *
 * These hooks replace the manual fetchSessionDetail() + setState pattern with
 * cached, deduplicated queries that persist across session navigation.
 *
 * Benefits:
 * - Instant data on return to a previously-viewed session (5 min stale time)
 * - No double-fetch when multiple components request the same data
 * - Automatic background revalidation after stale time expires
 */

import { useQuery } from '@tanstack/react-query';

import {
  getBASCalculation,
  getBASVarianceAnalysis,
  getXeroBASCrossCheck,
  listBASAdjustments,
  getTaxCodeSuggestionSummary,
  listWritebackJobs,
} from '@/lib/bas';

type GetToken = () => Promise<string | null>;

// ---------------------------------------------------------------------------
// Query key factory — keeps cache keys consistent across the app
// ---------------------------------------------------------------------------

export const basQueryKeys = {
  sessions: (connectionId: string) =>
    ['bas', 'sessions', connectionId] as const,
  calculation: (connectionId: string, sessionId: string) =>
    ['bas', 'calculation', connectionId, sessionId] as const,
  variance: (connectionId: string, sessionId: string) =>
    ['bas', 'variance', connectionId, sessionId] as const,
  adjustments: (connectionId: string, sessionId: string) =>
    ['bas', 'adjustments', connectionId, sessionId] as const,
  taxCodeSummary: (connectionId: string, sessionId: string) =>
    ['bas', 'taxCodeSummary', connectionId, sessionId] as const,
  writebackJobs: (connectionId: string, sessionId: string) =>
    ['bas', 'writebackJobs', connectionId, sessionId] as const,
  crossCheck: (connectionId: string, sessionId: string) =>
    ['bas', 'crossCheck', connectionId, sessionId] as const,
};

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useBASCalculation(
  connectionId: string,
  sessionId: string | undefined,
  getToken: GetToken,
  hasCalculation: boolean,
) {
  return useQuery({
    queryKey: basQueryKeys.calculation(connectionId, sessionId ?? ''),
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return getBASCalculation(token, connectionId, sessionId!);
    },
    enabled: !!sessionId && hasCalculation,
  });
}

export function useBASVariance(
  connectionId: string,
  sessionId: string | undefined,
  getToken: GetToken,
) {
  return useQuery({
    queryKey: basQueryKeys.variance(connectionId, sessionId ?? ''),
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return getBASVarianceAnalysis(token, connectionId, sessionId!);
    },
    enabled: !!sessionId,
  });
}

export function useBASAdjustments(
  connectionId: string,
  sessionId: string | undefined,
  getToken: GetToken,
) {
  return useQuery({
    queryKey: basQueryKeys.adjustments(connectionId, sessionId ?? ''),
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const result = await listBASAdjustments(token, connectionId, sessionId!);
      return result.adjustments;
    },
    enabled: !!sessionId,
  });
}

export function useBASTaxCodeSummary(
  connectionId: string,
  sessionId: string | undefined,
  getToken: GetToken,
  hasCalculation: boolean,
) {
  return useQuery({
    queryKey: basQueryKeys.taxCodeSummary(connectionId, sessionId ?? ''),
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return getTaxCodeSuggestionSummary(token, connectionId, sessionId!);
    },
    enabled: !!sessionId && hasCalculation,
  });
}

export function useBASCrossCheck(
  connectionId: string,
  sessionId: string | undefined,
  getToken: GetToken,
) {
  return useQuery({
    queryKey: basQueryKeys.crossCheck(connectionId, sessionId ?? ''),
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return getXeroBASCrossCheck(token, connectionId, sessionId!);
    },
    enabled: !!sessionId,
  });
}

export function useBASWritebackJobs(
  connectionId: string,
  sessionId: string | undefined,
  getToken: GetToken,
) {
  return useQuery({
    queryKey: basQueryKeys.writebackJobs(connectionId, sessionId ?? ''),
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      return listWritebackJobs(token, connectionId, sessionId!);
    },
    enabled: !!sessionId,
  });
}
