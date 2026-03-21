/**
 * Onboarding API client for Clairo.
 *
 * Provides functions to interact with the onboarding flow endpoints.
 */

// Use empty base so requests go through Next.js rewrite proxy (avoids CORS)
const API_BASE = '';

// Token storage for authenticated requests
let authToken: string | null = null;

/**
 * Set the auth token for API requests.
 */
export function setAuthToken(token: string | null): void {
  authToken = token;
}

/**
 * API fetch helper with authentication.
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  // Add auth token if available
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ error: 'Unknown error' }));
    throw new Error(
      error.error || error.detail || `API error: ${response.status}`
    );
  }

  return response.json();
}

// =============================================================================
// Types
// =============================================================================

export type OnboardingStatus =
  | 'started'
  | 'tier_selected'
  | 'payment_setup'
  | 'xero_connected'
  | 'clients_imported'
  | 'tour_completed'
  | 'completed'
  | 'skipped_xero';

export type SubscriptionTier =
  | 'starter'
  | 'professional'
  | 'growth'
  | 'enterprise';

export interface ChecklistItem {
  id: string;
  label: string;
  completed: boolean;
  completed_at: string | null;
}

export interface OnboardingChecklist {
  items: ChecklistItem[];
  completed_count: number;
  total_count: number;
  dismissed: boolean;
}

export interface OnboardingProgress {
  id: string;
  status: OnboardingStatus;
  current_step: string;
  started_at: string;
  tier_selected_at: string | null;
  payment_setup_at: string | null;
  xero_connected_at: string | null;
  clients_imported_at: string | null;
  tour_completed_at: string | null;
  completed_at: string | null;
  xero_skipped: boolean;
  tour_skipped: boolean;
  checklist: OnboardingChecklist;
}

export interface TierSelectionRequest {
  tier: SubscriptionTier;
  with_trial?: boolean;
}

export interface PaymentCompleteRequest {
  session_id: string;
}

export interface XeroConnectResponse {
  authorization_url: string;
}

// XPM Client Xero Connection Status
export type XpmClientConnectionStatus =
  | 'not_connected'
  | 'connected'
  | 'disconnected'
  | 'no_access';

export interface AvailableClient {
  id: string;
  name: string;
  email: string | null;
  source_type: 'xpm' | 'xero_accounting';
  already_imported: boolean;
  xero_org_status: XpmClientConnectionStatus;
  xero_connection_id: string | null;
}

// XPM Client types for Phase 6b
export interface XpmClient {
  id: string;
  name: string;
  email: string | null;
  abn: string | null;
  xero_contact_id: string;
  is_active: boolean;
  connection_status: XpmClientConnectionStatus;
  xero_connection_id: string | null;
  xero_org_name: string | null;
  connected_at: string | null;
}

export interface XpmClientListResponse {
  clients: XpmClient[];
  total: number;
  page: number;
  page_size: number;
}

export interface XpmClientConnectionProgress {
  total_clients: number;
  connected: number;
  not_connected: number;
  disconnected: number;
  no_access: number;
  connection_rate_percent: number;
  status_counts: {
    connected: number;
    not_connected: number;
    disconnected: number;
    no_access: number;
  };
}

export interface XpmClientConnectXeroResponse {
  authorization_url: string;
  client_id: string;
  client_name: string;
}

export interface ConnectNextClientResponse {
  has_next: boolean;
  next_client: XpmClient | null;
  authorization_url: string | null;
  remaining_count: number;
  progress: XpmClientConnectionProgress;
}

export interface AvailableClientsResponse {
  clients: AvailableClient[];
  total: number;
  source_type: 'xpm' | 'xero_accounting';
  tier_limit: number;
  current_count: number;
  page: number;
  page_size: number;
}

export interface BulkImportRequest {
  client_ids: string[];
  source_type: 'xpm' | 'xero_accounting';
}

export type BulkImportJobStatus =
  | 'pending'
  | 'in_progress'
  | 'completed'
  | 'partial_failure'
  | 'failed'
  | 'cancelled';

export interface ImportedClient {
  source_id: string;
  clairo_id: string;
  name: string;
}

export interface FailedClient {
  source_id: string;
  name: string;
  error: string;
}

export interface BulkImportJob {
  id: string;
  status: BulkImportJobStatus;
  source_type: 'xpm' | 'xero_accounting';
  total_clients: number;
  imported_count: number;
  failed_count: number;
  progress_percent: number;
  imported_clients: ImportedClient[];
  failed_clients: FailedClient[];
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

// =============================================================================
// API Functions
// =============================================================================

const BASE_PATH = '/api/v1/onboarding';

/**
 * Get current onboarding progress.
 */
export async function getProgress(): Promise<OnboardingProgress> {
  return apiRequest<OnboardingProgress>(`${BASE_PATH}/progress`);
}

/**
 * Start onboarding for the current tenant.
 */
export async function startOnboarding(): Promise<OnboardingProgress> {
  return apiRequest<OnboardingProgress>(`${BASE_PATH}/start`, {
    method: 'POST',
  });
}

/**
 * Select subscription tier and start free trial (no checkout redirect).
 */
export async function selectTier(
  request: TierSelectionRequest
): Promise<OnboardingProgress> {
  return apiRequest<OnboardingProgress>(`${BASE_PATH}/tier`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Mark payment setup complete after Stripe checkout.
 * @deprecated Trial subscriptions are now created server-side in selectTier().
 * Kept for in-flight edge cases.
 */
export async function completePayment(
  sessionId: string
): Promise<OnboardingProgress> {
  return apiRequest<OnboardingProgress>(`${BASE_PATH}/payment-complete`, {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  });
}

/**
 * Initiate Xero OAuth connection.
 */
export async function initiateXeroConnect(): Promise<XeroConnectResponse> {
  return apiRequest<XeroConnectResponse>(`${BASE_PATH}/xero/connect`, {
    method: 'POST',
  });
}

/**
 * Skip Xero connection step.
 */
export async function skipXero(): Promise<OnboardingProgress> {
  return apiRequest<OnboardingProgress>(`${BASE_PATH}/xero/skip`, {
    method: 'POST',
  });
}

/**
 * Get clients available for import from Xero/XPM.
 */
export async function getAvailableClients(
  search?: string,
  page: number = 1,
  pageSize: number = 50
): Promise<AvailableClientsResponse> {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  params.set('page', String(page));
  params.set('page_size', String(pageSize));

  return apiRequest<AvailableClientsResponse>(
    `${BASE_PATH}/clients/available?${params}`
  );
}

/**
 * Start bulk client import job.
 */
export async function startBulkImport(
  clientIds: string[],
  sourceType: 'xpm' | 'xero_accounting' = 'xpm'
): Promise<BulkImportJob> {
  return apiRequest<BulkImportJob>(`${BASE_PATH}/clients/import`, {
    method: 'POST',
    body: JSON.stringify({
      client_ids: clientIds,
      source_type: sourceType,
    }),
  });
}

/**
 * Get bulk import job status.
 */
export async function getImportJob(jobId: string): Promise<BulkImportJob> {
  return apiRequest<BulkImportJob>(`${BASE_PATH}/import/${jobId}`);
}

/**
 * Retry failed imports for a job.
 */
export async function retryFailedImports(
  jobId: string
): Promise<BulkImportJob> {
  return apiRequest<BulkImportJob>(`${BASE_PATH}/import/${jobId}/retry`, {
    method: 'POST',
  });
}

/**
 * Mark product tour as complete.
 */
export async function completeTour(): Promise<OnboardingProgress> {
  return apiRequest<OnboardingProgress>(`${BASE_PATH}/tour/complete`, {
    method: 'POST',
  });
}

/**
 * Skip product tour.
 */
export async function skipTour(): Promise<OnboardingProgress> {
  return apiRequest<OnboardingProgress>(`${BASE_PATH}/tour/skip`, {
    method: 'POST',
  });
}

/**
 * Dismiss onboarding checklist.
 */
export async function dismissChecklist(): Promise<OnboardingProgress> {
  return apiRequest<OnboardingProgress>(`${BASE_PATH}/checklist/dismiss`, {
    method: 'POST',
  });
}

// =============================================================================
// XPM Client Xero Connection API (Phase 6b)
// =============================================================================

/**
 * Get list of XPM clients with their Xero connection status.
 */
export async function getXpmClients(
  search?: string,
  status?: XpmClientConnectionStatus,
  page: number = 1,
  pageSize: number = 50
): Promise<XpmClientListResponse> {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (status) params.set('status', status);
  params.set('page', String(page));
  params.set('page_size', String(pageSize));

  return apiRequest<XpmClientListResponse>(
    `${BASE_PATH}/xpm-clients?${params}`
  );
}

/**
 * Get XPM client Xero connection progress.
 */
export async function getConnectionProgress(): Promise<XpmClientConnectionProgress> {
  return apiRequest<XpmClientConnectionProgress>(
    `${BASE_PATH}/xpm-clients/connection-progress`
  );
}

/**
 * Sync Xero connections and match to XPM clients.
 */
export async function syncXeroConnections(): Promise<{
  sync_result: Record<string, unknown>;
  match_result: Record<string, unknown>;
}> {
  return apiRequest(`${BASE_PATH}/xero/sync-connections`, {
    method: 'POST',
  });
}

/**
 * Initiate OAuth for a specific client's Xero organization.
 */
export async function connectClientXero(
  clientId: string
): Promise<XpmClientConnectXeroResponse> {
  return apiRequest<XpmClientConnectXeroResponse>(
    `${BASE_PATH}/xpm-clients/${clientId}/connect-xero`,
    {
      method: 'POST',
    }
  );
}

/**
 * Get next unconnected client and initiate OAuth for sequential connection.
 */
export async function connectNextClient(): Promise<ConnectNextClientResponse> {
  return apiRequest<ConnectNextClientResponse>(
    `${BASE_PATH}/xpm-clients/connect-next`,
    {
      method: 'POST',
    }
  );
}

/**
 * Manually link an XPM client to a Xero connection.
 */
export async function linkClientToXero(
  clientId: string,
  connectionId: string
): Promise<XpmClient> {
  return apiRequest<XpmClient>(
    `${BASE_PATH}/xpm-clients/${clientId}/link-xero`,
    {
      method: 'POST',
      body: JSON.stringify({ xero_connection_id: connectionId }),
    }
  );
}

/**
 * Unlink an XPM client from their Xero connection.
 */
export async function unlinkClientFromXero(
  clientId: string,
  reason?: string
): Promise<XpmClient> {
  return apiRequest<XpmClient>(
    `${BASE_PATH}/xpm-clients/${clientId}/unlink-xero`,
    {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }
  );
}

// =============================================================================
// Manual Matching API (Phase 6b.6)
// =============================================================================

export interface XeroConnection {
  id: string;
  xero_tenant_id: string;
  organization_name: string | null;
  status: 'active' | 'disconnected' | 'expired' | 'revoked';
  connected_at: string | null;
  last_sync_at: string | null;
}

/**
 * Get Xero connections that aren't linked to any XPM client.
 */
export async function getUnmatchedConnections(): Promise<XeroConnection[]> {
  return apiRequest<XeroConnection[]>(
    `${BASE_PATH}/xero/unmatched-connections`
  );
}

/**
 * Link an XPM client to a Xero connection by Xero tenant ID.
 */
export async function linkClientByTenantId(
  clientId: string,
  xeroTenantId: string
): Promise<XpmClient> {
  return apiRequest<XpmClient>(
    `${BASE_PATH}/xpm-clients/${clientId}/link-xero-org`,
    {
      method: 'POST',
      body: JSON.stringify({ xero_tenant_id: xeroTenantId }),
    }
  );
}
