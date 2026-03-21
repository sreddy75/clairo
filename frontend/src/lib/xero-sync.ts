/**
 * Xero Sync Types and API Functions
 *
 * Provides types and API functions for Xero data synchronization.
 */

import { apiClient } from './api-client';

// =============================================================================
// Types
// =============================================================================

export type XeroSyncType = 'contacts' | 'invoices' | 'bank_transactions' | 'accounts' | 'full';

export type XeroSyncStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled';

export interface XeroSyncJob {
  id: string;
  connection_id: string;
  sync_type: XeroSyncType;
  status: XeroSyncStatus;
  started_at: string | null;
  completed_at: string | null;
  records_processed: number;
  records_created: number;
  records_updated: number;
  records_failed: number;
  error_message: string | null;
  progress_details: Record<string, unknown> | null;
  created_at: string;
  // Phased sync fields (Spec 043: Progressive Sync)
  sync_phase: number | null;
  triggered_by: string;
}

export interface XeroSyncRequest {
  sync_type?: XeroSyncType;
  force_full?: boolean;
}

export interface XeroSyncHistoryResponse {
  jobs: XeroSyncJob[];
  total: number;
  limit: number;
  offset: number;
}

export interface XeroConnectionWithSync {
  id: string;
  organization_name: string;
  status: 'active' | 'needs_reauth' | 'disconnected';
  connected_at: string;
  last_used_at: string | null;
  rate_limit_daily_remaining: number;
  rate_limit_minute_remaining: number;
  // Sync timestamps
  last_contacts_sync_at?: string | null;
  last_invoices_sync_at?: string | null;
  last_transactions_sync_at?: string | null;
  last_accounts_sync_at?: string | null;
  last_full_sync_at?: string | null;
  sync_in_progress?: boolean;
}

export type EntityProgressStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';

export interface EntityProgressResponse {
  entity_type: string;
  status: EntityProgressStatus;
  records_processed: number;
  records_created: number;
  records_updated: number;
  records_failed: number;
  error_message: string | null;
  duration_ms: number | null;
}

export type PostSyncTaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

export interface PostSyncTaskResponse {
  task_type: string;
  status: PostSyncTaskStatus;
  sync_phase: number;
  result_summary: Record<string, unknown> | null;
}

export interface SyncStatusResponse {
  job: XeroSyncJob;
  entities: EntityProgressResponse[];
  phase: number | null;
  total_phases: number;
  records_processed: number;
  records_created: number;
  records_updated: number;
  records_failed: number;
  post_sync_tasks: PostSyncTaskResponse[];
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Initiate a sync operation for a Xero connection
 */
export async function initiateSync(
  token: string,
  connectionId: string,
  request?: XeroSyncRequest
): Promise<XeroSyncJob> {
  const response = await apiClient.post(
    `/api/v1/integrations/xero/connections/${connectionId}/sync`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: request ? JSON.stringify(request) : undefined,
    }
  );
  return apiClient.handleResponse<XeroSyncJob>(response);
}

/**
 * Get the status of a sync job
 */
export async function getSyncStatus(
  token: string,
  connectionId: string,
  jobId: string
): Promise<XeroSyncJob> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/sync/${jobId}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<XeroSyncJob>(response);
}

/**
 * Get sync history for a connection
 */
export async function getSyncHistory(
  token: string,
  connectionId: string,
  limit = 10,
  offset = 0
): Promise<XeroSyncHistoryResponse> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/sync/history?limit=${limit}&offset=${offset}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<XeroSyncHistoryResponse>(response);
}

/**
 * Cancel a sync job
 */
export async function cancelSync(
  token: string,
  connectionId: string,
  jobId: string
): Promise<void> {
  const response = await apiClient.delete(
    `/api/v1/integrations/xero/connections/${connectionId}/sync/${jobId}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  await apiClient.handleResponse(response);
}

/**
 * Get per-entity sync progress for a specific sync job
 */
export async function getEntityProgress(
  token: string,
  connectionId: string,
  jobId: string
): Promise<EntityProgressResponse[]> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/sync/${jobId}/entities`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<EntityProgressResponse[]>(response);
}

/**
 * Get enhanced sync status with phase info, per-entity progress, and post-sync tasks
 */
export async function getEnhancedSyncStatus(
  token: string,
  connectionId: string,
  jobId: string
): Promise<SyncStatusResponse> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/connections/${connectionId}/sync/${jobId}/status`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<SyncStatusResponse>(response);
}

// =============================================================================
// Multi-Client Sync Types (Spec 043: Phase 5)
// =============================================================================

export interface MultiClientSyncResponse {
  batch_id: string;
  total_connections: number;
  jobs_queued: number;
  jobs_skipped: number;
  queued: Array<{
    connection_id: string;
    organization_name: string;
    job_id: string;
  }>;
  skipped: Array<{
    connection_id: string;
    organization_name: string;
    reason: string;
  }>;
}

export interface MultiClientConnectionStatus {
  connection_id: string;
  organization_name: string;
  status: string;
  records_processed: number;
  sync_phase: number | null;
  last_sync_at: string | null;
}

export interface MultiClientSyncStatusResponse {
  total_connections: number;
  syncing: number;
  completed: number;
  failed: number;
  pending: number;
  connections: MultiClientConnectionStatus[];
}

// =============================================================================
// Multi-Client Sync API Functions
// =============================================================================

/**
 * Start syncing all connected Xero clients
 */
export async function startMultiClientSync(
  token: string,
  forceFull = false
): Promise<MultiClientSyncResponse> {
  const response = await apiClient.post(
    `/api/v1/integrations/xero/sync/all`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ force_full: forceFull }),
    }
  );
  return apiClient.handleResponse<MultiClientSyncResponse>(response);
}

/**
 * Get aggregate sync status across all connections
 */
export async function getMultiClientSyncStatus(
  token: string
): Promise<MultiClientSyncStatusResponse> {
  const response = await apiClient.get(
    `/api/v1/integrations/xero/sync/all/status`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return apiClient.handleResponse<MultiClientSyncStatusResponse>(response);
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Check if sync data is stale (older than 24 hours)
 */
export function isSyncStale(lastSyncAt: string | null | undefined): boolean {
  if (!lastSyncAt) return true;
  const lastSync = new Date(lastSyncAt);
  const now = new Date();
  const hoursDiff = (now.getTime() - lastSync.getTime()) / (1000 * 60 * 60);
  return hoursDiff > 24;
}

/**
 * Data freshness level based on time since last sync.
 *
 * - fresh:      Less than 1 hour ago (green)
 * - recent:     Between 1 and 24 hours ago (gray/neutral)
 * - stale:      Between 24 and 48 hours ago (amber)
 * - very_stale: More than 48 hours ago (red)
 */
export type SyncFreshness = 'fresh' | 'recent' | 'stale' | 'very_stale';

/**
 * Determine data freshness level from the last sync timestamp.
 */
export function getSyncFreshness(lastSyncAt: string | null | undefined): SyncFreshness {
  if (!lastSyncAt) return 'very_stale';
  const lastSync = new Date(lastSyncAt);
  const now = new Date();
  const hoursDiff = (now.getTime() - lastSync.getTime()) / (1000 * 60 * 60);

  if (hoursDiff < 1) return 'fresh';
  if (hoursDiff < 24) return 'recent';
  if (hoursDiff < 48) return 'stale';
  return 'very_stale';
}

/**
 * Format relative time for display
 */
export function formatRelativeTime(dateString: string | null | undefined): string {
  if (!dateString) return 'Never';

  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}

/**
 * Get human-readable sync type name
 */
export function getSyncTypeName(type: XeroSyncType): string {
  const names: Record<XeroSyncType, string> = {
    contacts: 'Contacts',
    invoices: 'Invoices',
    bank_transactions: 'Transactions',
    accounts: 'Accounts',
    full: 'Full Sync',
  };
  return names[type] || type;
}

/**
 * Get status color classes
 */
export function getStatusColor(status: XeroSyncStatus): string {
  const colors: Record<XeroSyncStatus, string> = {
    pending: 'text-yellow-700 bg-yellow-100',
    in_progress: 'text-blue-700 bg-blue-100',
    completed: 'text-green-700 bg-green-100',
    failed: 'text-red-700 bg-red-100',
    cancelled: 'text-gray-700 bg-gray-100',
  };
  return colors[status] || 'text-gray-700 bg-gray-100';
}
