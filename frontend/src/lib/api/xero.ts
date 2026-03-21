/**
 * Xero API Client
 *
 * Handles API calls for Xero connections and related data.
 * Uses Clerk authentication.
 */

import { useAuth } from '@clerk/nextjs';

import { apiClient } from '@/lib/api-client';

const BASE = '/api/v1/integrations/xero';

// ============================================================================
// Types
// ============================================================================

export interface XeroConnection {
  id: string;
  xero_tenant_id: string;
  organisation_name: string | null;
  status: 'active' | 'disconnected' | 'pending';
  primary_contact_email: string | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface XeroConnectionsResponse {
  connections: XeroConnection[];
  total: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Create an authenticated API function with the given token getter.
 */
export function createXeroApi(getToken: () => Promise<string | null>) {
  return {
    /**
     * Get all Xero connections for the tenant.
     */
    getConnections: async (): Promise<XeroConnectionsResponse> => {
      const token = await getToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await apiClient.get(`${BASE}/connections`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      return apiClient.handleResponse<XeroConnectionsResponse>(response);
    },

    /**
     * Get a specific Xero connection by ID.
     */
    getConnection: async (connectionId: string): Promise<XeroConnection> => {
      const token = await getToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await apiClient.get(`${BASE}/connections/${connectionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      return apiClient.handleResponse<XeroConnection>(response);
    },
  };
}

/**
 * React hook for Xero API with Clerk authentication.
 */
export function useXeroApi() {
  const { getToken } = useAuth();
  return createXeroApi(getToken);
}
