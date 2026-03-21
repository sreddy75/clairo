/**
 * Request Templates API Client
 *
 * Handles API calls for document request templates (accountant-facing).
 * Uses Clerk authentication.
 */

import { useAuth } from '@clerk/nextjs';
import { useMemo } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class RequestsApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'RequestsApiError';
  }
}

async function parseErrorResponse(response: Response): Promise<RequestsApiError> {
  try {
    const data = await response.json();
    const error = data.error || data.detail || data;
    return new RequestsApiError(
      typeof error === 'string' ? error : error.message || `Request failed with status ${response.status}`,
      response.status,
      error.code,
      error.details
    );
  } catch {
    return new RequestsApiError(
      `Request failed with status ${response.status}`,
      response.status
    );
  }
}

// ============================================================================
// Types
// ============================================================================

export interface DocumentRequestTemplate {
  id: string;
  tenant_id: string | null;
  name: string;
  description_template: string;
  expected_document_types: string[];
  icon: string | null;
  default_priority: 'low' | 'normal' | 'high' | 'urgent';
  default_due_days: number;
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TemplateListResponse {
  templates: DocumentRequestTemplate[];
  total: number;
}

export interface CreateTemplateRequest {
  name: string;
  description_template: string;
  expected_document_types?: string[];
  icon?: string;
  default_priority?: 'low' | 'normal' | 'high' | 'urgent';
  default_due_days?: number;
}

export interface UpdateTemplateRequest {
  name?: string;
  description_template?: string;
  expected_document_types?: string[];
  icon?: string;
  default_priority?: 'low' | 'normal' | 'high' | 'urgent';
  default_due_days?: number;
  is_active?: boolean;
}

// ============================================================================
// Document Request Types
// ============================================================================

export type RequestPriority = 'low' | 'normal' | 'high' | 'urgent';
export type RequestStatus = 'draft' | 'pending' | 'viewed' | 'in_progress' | 'complete' | 'cancelled';

export interface DocumentRequest {
  id: string;
  connection_id: string;
  template_id: string | null;
  title: string;
  description: string;
  due_date: string | null;
  priority: RequestPriority;
  period_start: string | null;
  period_end: string | null;
  status: RequestStatus;
  sent_at: string | null;
  viewed_at: string | null;
  responded_at: string | null;
  completed_at: string | null;
  auto_remind: boolean;
  reminder_count: number;
  last_reminder_at: string | null;
  bulk_request_id: string | null;
  created_at: string;
  updated_at: string;
  is_overdue: boolean;
  days_until_due: number | null;
  response_count: number;
  document_count: number;
}

export interface PortalDocument {
  id: string;
  connection_id: string;
  response_id: string | null;
  filename: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  document_type: string | null;
  period_start: string | null;
  period_end: string | null;
  tags: string[] | null;
  uploaded_at: string;
  uploaded_by_client: boolean;
  scan_status: string | null;
  scanned_at: string | null;
}

export interface ResponseSummary {
  id: string;
  request_id: string;
  note: string | null;
  submitted_at: string;
  document_count: number;
  documents: PortalDocument[];
}

export interface RequestEvent {
  id: string;
  request_id: string;
  event_type: string;
  event_data: Record<string, unknown> | null;
  actor_type: string;
  actor_id: string | null;
  created_at: string;
}

export interface DocumentRequestDetail extends DocumentRequest {
  organization_name: string;
  recipient_email: string | null;
  first_viewed_at: string | null;
  responses: ResponseSummary[];
  events: RequestEvent[];
}

export interface CreateDocumentRequest {
  connection_id: string;
  template_id?: string;
  title: string;
  description: string;
  recipient_email: string;
  due_date?: string;
  priority?: RequestPriority;
  period_start?: string;
  period_end?: string;
  auto_remind?: boolean;
  send_immediately?: boolean;
}

export interface UpdateDocumentRequest {
  title?: string;
  description?: string;
  due_date?: string;
  priority?: RequestPriority;
  auto_remind?: boolean;
}

export interface DocumentRequestListResponse {
  requests: DocumentRequest[];
  total: number;
  page: number;
  page_size: number;
}

export interface DocumentRequestFilters {
  connection_id?: string;
  status?: RequestStatus;
  priority?: RequestPriority;
  is_overdue?: boolean;
  from_date?: string;
  to_date?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

// ============================================================================
// Bulk Request Types
// ============================================================================

export type BulkRequestStatus = 'pending' | 'processing' | 'completed' | 'partial' | 'failed';

export interface BulkRequest {
  id: string;
  template_id: string | null;
  title: string;
  due_date: string | null;
  total_clients: number;
  sent_count: number;
  failed_count: number;
  status: BulkRequestStatus;
  progress_percent: number;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BulkRequestDetail extends BulkRequest {
  requests: DocumentRequest[];
  failed_connections: string[];
}

export interface CreateBulkRequest {
  connection_ids: string[];
  template_id?: string;
  title: string;
  description: string;
  priority?: RequestPriority;
  due_date?: string;
}

export interface BulkRequestPreview {
  total_clients: number;
  valid_clients: number;
  invalid_clients: number;
  issues: { connection_id: string; issue: string }[];
}

export interface BulkRequestListResponse {
  bulk_requests: BulkRequest[];
  total: number;
  page: number;
  page_size: number;
}

export interface BulkRequestFilters {
  status?: BulkRequestStatus;
  page?: number;
  page_size?: number;
}

// ============================================================================
// Tracking Types
// ============================================================================

export interface TrackingRequestItem {
  id: string;
  connection_id: string;
  organization_name: string;
  title: string;
  due_date: string | null;
  priority: RequestPriority;
  status: RequestStatus;
  sent_at: string | null;
  viewed_at: string | null;
  responded_at: string | null;
  is_overdue: boolean;
  days_until_due: number | null;
  response_count: number;
}

export interface TrackingStatusGroup {
  status: RequestStatus;
  count: number;
  requests: TrackingRequestItem[];
}

export interface TrackingSummary {
  total: number;
  pending: number;
  viewed: number;
  in_progress: number;
  completed: number;
  cancelled: number;
  overdue: number;
  due_today: number;
  due_this_week: number;
}

export interface TrackingResponse {
  summary: TrackingSummary;
  groups: TrackingStatusGroup[];
  page: number;
  page_size: number;
}

export interface TrackingSummaryResponse {
  summary: TrackingSummary;
  recent_activity: TrackingRequestItem[];
}

export interface TrackingFilters {
  status?: RequestStatus;
  page?: number;
  page_size?: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Create an authenticated API function with the given token.
 */
export function createRequestsApi(getToken: () => Promise<string | null>) {
  const authenticatedFetch = async (
    path: string,
    options: RequestInit = {}
  ): Promise<Response> => {
    const token = await getToken();

    if (!token) {
      throw new RequestsApiError('Not authenticated', 401);
    }

    return fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        ...options.headers,
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });
  };

  return {
    templates: {
      /**
       * List all available templates (system + tenant-specific).
       */
      list: async (includeInactive = false): Promise<TemplateListResponse> => {
        const response = await authenticatedFetch(
          `/api/v1/request-templates?include_inactive=${includeInactive}`
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Get a specific template by ID.
       */
      get: async (templateId: string): Promise<DocumentRequestTemplate> => {
        const response = await authenticatedFetch(
          `/api/v1/request-templates/${templateId}`
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Create a new custom template.
       */
      create: async (data: CreateTemplateRequest): Promise<DocumentRequestTemplate> => {
        const response = await authenticatedFetch('/api/v1/request-templates', {
          method: 'POST',
          body: JSON.stringify(data),
        });

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Update an existing template.
       */
      update: async (
        templateId: string,
        data: UpdateTemplateRequest
      ): Promise<DocumentRequestTemplate> => {
        const response = await authenticatedFetch(
          `/api/v1/request-templates/${templateId}`,
          {
            method: 'PATCH',
            body: JSON.stringify(data),
          }
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Delete a template (soft delete).
       */
      delete: async (templateId: string): Promise<void> => {
        const response = await authenticatedFetch(
          `/api/v1/request-templates/${templateId}`,
          { method: 'DELETE' }
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }
      },
    },

    // ========================================================================
    // Document Requests
    // ========================================================================
    requests: {
      /**
       * Create a new document request.
       */
      create: async (
        connectionId: string,
        data: CreateDocumentRequest
      ): Promise<DocumentRequest> => {
        const response = await authenticatedFetch(
          `/api/v1/clients/${connectionId}/requests`,
          {
            method: 'POST',
            body: JSON.stringify(data),
          }
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Send a draft document request.
       */
      send: async (requestId: string): Promise<DocumentRequest> => {
        const response = await authenticatedFetch(
          `/api/v1/requests/${requestId}/send`,
          { method: 'POST' }
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * List all document requests with filters.
       */
      list: async (
        filters: DocumentRequestFilters = {}
      ): Promise<DocumentRequestListResponse> => {
        const params = new URLSearchParams();
        if (filters.connection_id) params.set('connection_id', filters.connection_id);
        if (filters.status) params.set('status', filters.status);
        if (filters.priority) params.set('priority', filters.priority);
        if (filters.is_overdue !== undefined)
          params.set('is_overdue', String(filters.is_overdue));
        if (filters.from_date) params.set('from_date', filters.from_date);
        if (filters.to_date) params.set('to_date', filters.to_date);
        if (filters.search) params.set('search', filters.search);
        if (filters.page) params.set('page', String(filters.page));
        if (filters.page_size) params.set('page_size', String(filters.page_size));

        const response = await authenticatedFetch(
          `/api/v1/requests?${params.toString()}`
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * List document requests for a specific client.
       */
      listByClient: async (
        connectionId: string,
        filters: Omit<DocumentRequestFilters, 'connection_id'> = {}
      ): Promise<DocumentRequestListResponse> => {
        const params = new URLSearchParams();
        if (filters.status) params.set('status', filters.status);
        if (filters.priority) params.set('priority', filters.priority);
        if (filters.is_overdue !== undefined)
          params.set('is_overdue', String(filters.is_overdue));
        if (filters.page) params.set('page', String(filters.page));
        if (filters.page_size) params.set('page_size', String(filters.page_size));

        const response = await authenticatedFetch(
          `/api/v1/clients/${connectionId}/requests?${params.toString()}`
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Get a specific document request by ID.
       */
      get: async (requestId: string): Promise<DocumentRequestDetail> => {
        const response = await authenticatedFetch(`/api/v1/requests/${requestId}`);

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Update a document request.
       */
      update: async (
        requestId: string,
        data: UpdateDocumentRequest
      ): Promise<DocumentRequest> => {
        const response = await authenticatedFetch(`/api/v1/requests/${requestId}`, {
          method: 'PATCH',
          body: JSON.stringify(data),
        });

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Cancel a document request.
       */
      cancel: async (requestId: string, reason?: string): Promise<DocumentRequest> => {
        const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';
        const response = await authenticatedFetch(
          `/api/v1/requests/${requestId}/cancel${params}`,
          { method: 'POST' }
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Mark a document request as complete.
       */
      complete: async (requestId: string, note?: string): Promise<DocumentRequest> => {
        const params = note ? `?note=${encodeURIComponent(note)}` : '';
        const response = await authenticatedFetch(
          `/api/v1/requests/${requestId}/complete${params}`,
          { method: 'POST' }
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },
    },

    // ========================================================================
    // Documents
    // ========================================================================
    documents: {
      /**
       * Download a portal document.
       * Returns a blob that can be saved as a file.
       */
      download: async (documentId: string, filename: string): Promise<void> => {
        const response = await authenticatedFetch(
          `/api/v1/documents/${documentId}/download`
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        // Get blob and trigger download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      },
    },

    // ========================================================================
    // Bulk Requests
    // ========================================================================
    bulkRequests: {
      /**
       * Create a bulk document request for multiple clients.
       */
      create: async (data: CreateBulkRequest): Promise<BulkRequest> => {
        const response = await authenticatedFetch('/api/v1/bulk-requests', {
          method: 'POST',
          body: JSON.stringify(data),
        });

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Preview a bulk request before sending.
       */
      preview: async (
        data: Omit<CreateBulkRequest, 'priority'>
      ): Promise<BulkRequestPreview> => {
        const response = await authenticatedFetch('/api/v1/bulk-requests/preview', {
          method: 'POST',
          body: JSON.stringify(data),
        });

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * List all bulk requests.
       */
      list: async (
        filters: BulkRequestFilters = {}
      ): Promise<BulkRequestListResponse> => {
        const params = new URLSearchParams();
        if (filters.status) params.set('status', filters.status);
        if (filters.page) params.set('page', String(filters.page));
        if (filters.page_size) params.set('page_size', String(filters.page_size));

        const response = await authenticatedFetch(
          `/api/v1/bulk-requests?${params.toString()}`
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Get a specific bulk request with details.
       */
      get: async (bulkId: string): Promise<BulkRequestDetail> => {
        const response = await authenticatedFetch(`/api/v1/bulk-requests/${bulkId}`);

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },
    },

    // ========================================================================
    // Request Tracking
    // ========================================================================
    tracking: {
      /**
       * Get full tracking data with grouped requests.
       */
      getData: async (filters: TrackingFilters = {}): Promise<TrackingResponse> => {
        const params = new URLSearchParams();
        if (filters.status) params.set('status', filters.status);
        if (filters.page) params.set('page', String(filters.page));
        if (filters.page_size) params.set('page_size', String(filters.page_size));

        const response = await authenticatedFetch(
          `/api/v1/requests/tracking?${params.toString()}`
        );

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },

      /**
       * Get quick summary of tracking statistics.
       */
      getSummary: async (): Promise<TrackingSummaryResponse> => {
        const response = await authenticatedFetch('/api/v1/requests/tracking/summary');

        if (!response.ok) {
          throw await parseErrorResponse(response);
        }

        return response.json();
      },
    },
  };
}

// ============================================================================
// Portal Invitation Types
// ============================================================================

export interface PortalInvitation {
  id: string;
  connection_id: string;
  email: string;
  status: 'pending' | 'accepted' | 'expired' | 'revoked';
  sent_at: string | null;
  accepted_at: string | null;
  expires_at: string;
  created_at: string;
}

export interface InvitationCreateResponse {
  invitation: PortalInvitation;
  magic_link_url: string;
}

export interface InvitationListResponse {
  invitations: PortalInvitation[];
  total: number;
}

// ============================================================================
// Portal Invitation API
// ============================================================================

export function createPortalApi(getToken: () => Promise<string | null>) {
  const authenticatedFetch = async (url: string, options: RequestInit = {}) => {
    const token = await getToken();
    if (!token) {
      throw new RequestsApiError('Not authenticated', 401, 'UNAUTHORIZED');
    }

    return fetch(`${API_BASE_URL}${url}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...options.headers,
      },
    });
  };

  const parseErrorResponse = async (response: Response): Promise<RequestsApiError> => {
    try {
      const data = await response.json();
      return new RequestsApiError(
        data.detail || data.message || 'Request failed',
        response.status,
        data.code,
        data
      );
    } catch {
      return new RequestsApiError('Request failed', response.status);
    }
  };

  return {
    /**
     * Create a portal invitation for a client.
     */
    createInvitation: async (
      connectionId: string,
      email: string
    ): Promise<InvitationCreateResponse> => {
      const response = await authenticatedFetch(
        `/api/v1/portal/clients/${connectionId}/invite`,
        {
          method: 'POST',
          body: JSON.stringify({ email }),
        }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * List invitations for a client.
     */
    listInvitations: async (connectionId: string): Promise<InvitationListResponse> => {
      const response = await authenticatedFetch(
        `/api/v1/portal/clients/${connectionId}/invitations`
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Resend an invitation.
     */
    resendInvitation: async (
      connectionId: string,
      invitationId: string
    ): Promise<PortalInvitation> => {
      const response = await authenticatedFetch(
        `/api/v1/portal/clients/${connectionId}/invite/${invitationId}/resend`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Revoke an invitation.
     */
    revokeInvitation: async (
      connectionId: string,
      invitationId: string
    ): Promise<void> => {
      const response = await authenticatedFetch(
        `/api/v1/portal/clients/${connectionId}/invite/${invitationId}/revoke`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }
    },
  };
}

/**
 * React hook for portal API with Clerk authentication.
 */
export function usePortalApi() {
  const { getToken } = useAuth();
  return useMemo(() => createPortalApi(getToken), [getToken]);
}

/**
 * React hook for requests API with Clerk authentication.
 * Memoized to prevent infinite re-renders in useEffect dependencies.
 */
export function useRequestsApi() {
  const { getToken } = useAuth();
  return useMemo(() => createRequestsApi(getToken), [getToken]);
}
