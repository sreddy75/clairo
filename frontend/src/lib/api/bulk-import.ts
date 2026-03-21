/**
 * Bulk Import API Client (Phase 035)
 *
 * Handles API calls for bulk importing Xero client organizations.
 * Uses Clerk authentication.
 */

import { useAuth } from '@clerk/nextjs';

import { apiClient } from '@/lib/api-client';
import type {
  BulkImportCallbackResponse,
  BulkImportConfirmRequest,
  BulkImportInitiateResponse,
  BulkImportJobDetailResponse,
  BulkImportJobListResponse,
  BulkImportJobResponse,
} from '@/types/bulk-import';

const BASE = '/api/v1/integrations/xero/bulk-import';

// ============================================================================
// API Functions
// ============================================================================

/**
 * Create an authenticated bulk import API with the given token getter.
 */
export function createBulkImportApi(getToken: () => Promise<string | null>) {
  return {
    /**
     * Initiate a bulk import OAuth flow.
     * Returns the Xero authorization URL to redirect the user to.
     */
    initiateBulkImport: async (
      redirectUri: string
    ): Promise<BulkImportInitiateResponse> => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const response = await apiClient.post(`${BASE}/initiate`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ redirect_uri: redirectUri }),
      });

      return apiClient.handleResponse<BulkImportInitiateResponse>(response);
    },

    /**
     * Handle the OAuth callback after Xero authorization.
     * Returns the list of authorized organizations for configuration.
     */
    handleBulkCallback: async (
      code: string,
      state: string
    ): Promise<BulkImportCallbackResponse> => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const params = new URLSearchParams({ code, state });
      const response = await apiClient.get(`${BASE}/callback?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      return apiClient.handleResponse<BulkImportCallbackResponse>(response);
    },

    /**
     * Confirm selected organizations and start the bulk import.
     * Creates connections and queues sync for each selected org.
     */
    confirmBulkImport: async (
      request: BulkImportConfirmRequest,
      state: string
    ): Promise<BulkImportJobResponse> => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const params = new URLSearchParams({ state });
      const response = await apiClient.post(
        `${BASE}/confirm?${params}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(request),
        }
      );

      return apiClient.handleResponse<BulkImportJobResponse>(response);
    },

    /**
     * Get the status of a bulk import job with per-org details.
     */
    getBulkImportStatus: async (
      jobId: string
    ): Promise<BulkImportJobDetailResponse> => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const response = await apiClient.get(`${BASE}/${jobId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      return apiClient.handleResponse<BulkImportJobDetailResponse>(response);
    },

    /**
     * Retry failed organization syncs within a bulk import job.
     */
    retryFailedOrgs: async (
      jobId: string
    ): Promise<BulkImportJobResponse> => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const response = await apiClient.post(`${BASE}/${jobId}/retry`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      return apiClient.handleResponse<BulkImportJobResponse>(response);
    },

    /**
     * List bulk import jobs for the tenant.
     */
    listBulkImportJobs: async (
      limit: number = 20,
      offset: number = 0
    ): Promise<BulkImportJobListResponse> => {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');

      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
      });
      const response = await apiClient.get(`${BASE}/jobs?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      return apiClient.handleResponse<BulkImportJobListResponse>(response);
    },
  };
}

/**
 * React hook for bulk import API with Clerk authentication.
 */
export function useBulkImportApi() {
  const { getToken } = useAuth();
  return createBulkImportApi(getToken);
}
