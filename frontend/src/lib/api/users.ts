/**
 * Users API client
 *
 * Provides functions for fetching tenant users
 */

import { apiClient } from '../api-client';

export interface TenantUser {
  id: string;
  user_id: string;
  tenant_id: string;
  clerk_id: string;
  email: string;
  role: 'admin' | 'accountant' | 'staff';
  is_active: boolean;
  mfa_enabled: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserListResponse {
  users: TenantUser[];
  total: number;
}

/**
 * List users in the current tenant
 */
export async function listTenantUsers(
  token: string,
  includeInactive = false
): Promise<UserListResponse> {
  const params = new URLSearchParams();
  if (includeInactive) {
    params.set('include_inactive', 'true');
  }

  const queryString = params.toString();
  const url = queryString ? `/api/v1/auth/users?${queryString}` : '/api/v1/auth/users';

  const response = await apiClient.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return apiClient.handleResponse<UserListResponse>(response);
}
