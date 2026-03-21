/**
 * Types for Bulk Client Import via Multi-Org Xero OAuth (Phase 035)
 *
 * Matches the backend Pydantic schemas and contracts/api.yaml definitions.
 */

// ============================================================================
// Request Types
// ============================================================================

export interface BulkImportInitiateRequest {
  redirect_uri: string;
}

export interface ImportOrgSelection {
  xero_tenant_id: string;
  selected: boolean;
  connection_type?: 'practice' | 'client';
  assigned_user_id?: string | null;
}

export interface BulkImportConfirmRequest {
  auth_event_id: string;
  organizations: ImportOrgSelection[];
}

// ============================================================================
// Response Types
// ============================================================================

export interface BulkImportInitiateResponse {
  auth_url: string;
  state: string;
}

export interface ImportOrganization {
  xero_tenant_id: string;
  organization_name: string;
  already_connected: boolean;
  existing_connection_id: string | null;
  match_status: 'matched' | 'suggested' | 'unmatched' | null;
  matched_client_name: string | null;
}

export interface BulkImportCallbackResponse {
  auth_event_id: string;
  organizations: ImportOrganization[];
  already_connected_count: number;
  new_count: number;
  plan_limit: number;
  current_client_count: number;
  available_slots: number;
}

export type BulkImportJobStatus =
  | 'pending'
  | 'in_progress'
  | 'completed'
  | 'partial_failure'
  | 'failed'
  | 'cancelled';

export type BulkImportOrgStatusType =
  | 'pending'
  | 'importing'
  | 'syncing'
  | 'completed'
  | 'failed'
  | 'skipped';

export interface BulkImportJobResponse {
  job_id: string;
  status: BulkImportJobStatus;
  total_organizations: number;
  imported_count: number;
  failed_count: number;
  skipped_count: number;
  progress_percent: number;
  created_at: string;
}

export interface BulkImportOrgStatus {
  xero_tenant_id: string;
  organization_name: string;
  status: BulkImportOrgStatusType;
  connection_id: string | null;
  connection_type: string;
  assigned_user_id: string | null;
  error_message: string | null;
  sync_started_at: string | null;
  sync_completed_at: string | null;
}

export interface BulkImportJobDetailResponse extends BulkImportJobResponse {
  organizations: BulkImportOrgStatus[];
  started_at: string | null;
  completed_at: string | null;
}

export interface BulkImportJobListResponse {
  jobs: BulkImportJobResponse[];
  total: number;
  limit: number;
  offset: number;
}
