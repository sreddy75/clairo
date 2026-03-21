/**
 * Portal API Client
 *
 * Handles API calls for the client portal (business owner-facing).
 * Uses magic link authentication instead of Clerk.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class PortalApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'PortalApiError';
  }
}

async function parseErrorResponse(response: Response): Promise<PortalApiError> {
  try {
    const data = await response.json();
    const error = data.error || data.detail || data;
    return new PortalApiError(
      typeof error === 'string' ? error : error.message || `Request failed with status ${response.status}`,
      response.status,
      error.code,
      error.details
    );
  } catch {
    return new PortalApiError(
      `Request failed with status ${response.status}`,
      response.status
    );
  }
}

// ============================================================================
// Types
// ============================================================================

export interface MagicLinkRequestPayload {
  email: string;
}

export interface MagicLinkRequestResponse {
  message: string;
  expires_in_minutes: number;
}

export interface MagicLinkVerifyPayload {
  token: string;
}

export interface MagicLinkVerifyResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  business_name: string;
}

export interface RefreshTokenPayload {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface SessionInfo {
  connection_id: string;
  tenant_id: string;
  business_name: string;
}

export interface DocumentRequest {
  id: string;
  connection_id: string;
  template_id: string | null;
  title: string;
  description: string;
  due_date: string | null;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  status: 'draft' | 'sent' | 'viewed' | 'in_progress' | 'completed' | 'cancelled';
  sent_at: string | null;
  viewed_at: string | null;
  responded_at: string | null;
  completed_at: string | null;
  is_overdue: boolean;
  days_until_due: number | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardResponse {
  connection_id: string;
  organization_name: string;
  pending_requests: number;
  unread_requests: number;
  total_documents: number;
  recent_requests: DocumentRequest[];
  last_activity_at: string | null;
}

export interface BASStatusResponse {
  connection_id: string;
  current_quarter: string;
  status: string;
  due_date: string;
  items_pending: number;
  last_lodged: string;
  last_lodged_date: string;
}

export interface ActivityItem {
  type: 'document_request' | 'document_upload';
  id: string;
  title?: string;
  filename?: string;
  status?: string;
  timestamp: string;
}

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

export interface RequestListResponse {
  requests: DocumentRequest[];
  total: number;
  page: number;
  page_size: number;
}

export interface SubmitResponsePayload {
  message?: string;
  document_ids?: string[];
}

export interface SubmitResponseResult {
  success: boolean;
  message: string;
  request: DocumentRequest;
}

export interface RequestResponseItem {
  id: string;
  message: string | null;
  submitted_at: string | null;
}

export interface RequestResponsesResult {
  responses: RequestResponseItem[];
  total: number;
}

// Document Upload Types
export interface UploadedDocument {
  id: string;
  filename: string;
  content_type: string;
  file_size: number;
  uploaded_at: string;
}

export interface PresignedUploadResponse {
  upload_url: string;
  document_id: string;
  storage_key: string;
  content_type: string;
  expires_in: number;
}

export interface DocumentListResponse {
  documents: UploadedDocument[];
  total: number;
}

// ============================================================================
// Token Storage Utilities
// ============================================================================

const PORTAL_ACCESS_TOKEN_KEY = 'portal_access_token';
const PORTAL_REFRESH_TOKEN_KEY = 'portal_refresh_token';
const PORTAL_BUSINESS_NAME_KEY = 'portal_business_name';

export const portalTokenStorage = {
  setTokens: (accessToken: string, refreshToken: string, businessName?: string) => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(PORTAL_ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(PORTAL_REFRESH_TOKEN_KEY, refreshToken);
    if (businessName) {
      localStorage.setItem(PORTAL_BUSINESS_NAME_KEY, businessName);
    }
  },

  getAccessToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(PORTAL_ACCESS_TOKEN_KEY);
  },

  getRefreshToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(PORTAL_REFRESH_TOKEN_KEY);
  },

  getBusinessName: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(PORTAL_BUSINESS_NAME_KEY);
  },

  clearTokens: () => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(PORTAL_ACCESS_TOKEN_KEY);
    localStorage.removeItem(PORTAL_REFRESH_TOKEN_KEY);
    localStorage.removeItem(PORTAL_BUSINESS_NAME_KEY);
  },

  isAuthenticated: (): boolean => {
    return !!portalTokenStorage.getAccessToken();
  },
};

// ============================================================================
// Portal Auth API
// ============================================================================

// Helper function to make authenticated requests
async function authenticatedFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const accessToken = portalTokenStorage.getAccessToken();

  if (!accessToken) {
    throw new PortalApiError('Not authenticated', 401);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${accessToken}`,
    },
  });

  return response;
}

export const portalApi = {
  auth: {
    /**
     * Request a magic link to be sent to the given email.
     */
    requestMagicLink: async (email: string): Promise<MagicLinkRequestResponse> => {
      const response = await fetch(`${API_BASE_URL}/api/v1/client-portal/auth/request-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email } as MagicLinkRequestPayload),
      });

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Verify a magic link token and get access/refresh tokens.
     */
    verifyMagicLink: async (token: string): Promise<MagicLinkVerifyResponse> => {
      const response = await fetch(`${API_BASE_URL}/api/v1/client-portal/auth/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token } as MagicLinkVerifyPayload),
      });

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Refresh the access token using a refresh token.
     */
    refreshToken: async (refreshToken: string): Promise<RefreshTokenResponse> => {
      const response = await fetch(`${API_BASE_URL}/api/v1/client-portal/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken } as RefreshTokenPayload),
      });

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Logout and invalidate the current session.
     */
    logout: async (accessToken: string): Promise<void> => {
      const response = await fetch(`${API_BASE_URL}/api/v1/client-portal/auth/logout`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }
    },

    /**
     * Get current session information.
     */
    getSession: async (accessToken: string): Promise<SessionInfo> => {
      const response = await fetch(`${API_BASE_URL}/api/v1/client-portal/auth/me`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },
  },

  dashboard: {
    /**
     * Get the main dashboard data.
     */
    getDashboard: async (): Promise<DashboardResponse> => {
      const response = await authenticatedFetch('/api/v1/portal/dashboard');

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Get BAS status for the client.
     */
    getBASStatus: async (): Promise<BASStatusResponse> => {
      const response = await authenticatedFetch('/api/v1/portal/dashboard/bas-status');

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Get recent activity for the client.
     */
    getRecentActivity: async (limit: number = 10): Promise<ActivityItem[]> => {
      const response = await authenticatedFetch(`/api/v1/portal/dashboard/activity?limit=${limit}`);

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },
  },

  requests: {
    /**
     * List all document requests for the client.
     */
    list: async (
      status?: string,
      page: number = 1,
      pageSize: number = 20
    ): Promise<RequestListResponse> => {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      params.set('page', String(page));
      params.set('page_size', String(pageSize));

      const response = await authenticatedFetch(
        `/api/v1/portal/requests?${params.toString()}`
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Get a specific document request.
     * This also marks the request as viewed if it's pending.
     */
    get: async (requestId: string): Promise<DocumentRequest> => {
      const response = await authenticatedFetch(`/api/v1/portal/requests/${requestId}`);

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Submit a response to a document request.
     */
    respond: async (
      requestId: string,
      payload: SubmitResponsePayload
    ): Promise<SubmitResponseResult> => {
      const response = await authenticatedFetch(
        `/api/v1/portal/requests/${requestId}/respond`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * List all responses submitted for a request.
     */
    listResponses: async (requestId: string): Promise<RequestResponsesResult> => {
      const response = await authenticatedFetch(
        `/api/v1/portal/requests/${requestId}/responses`
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },
  },

  documents: {
    /**
     * Upload a document directly.
     */
    upload: async (
      file: File,
      documentType?: string,
      onProgress?: (progress: number) => void
    ): Promise<UploadedDocument> => {
      const accessToken = portalTokenStorage.getAccessToken();
      if (!accessToken) {
        throw new PortalApiError('Not authenticated', 401);
      }

      const formData = new FormData();
      formData.append('file', file);
      if (documentType) {
        formData.append('document_type', documentType);
      }

      // Use XMLHttpRequest for progress tracking
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable && onProgress) {
            const progress = Math.round((event.loaded / event.total) * 100);
            onProgress(progress);
          }
        });

        xhr.addEventListener('load', async () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText));
          } else {
            try {
              const errorData = JSON.parse(xhr.responseText);
              reject(new PortalApiError(
                errorData.detail || 'Upload failed',
                xhr.status
              ));
            } catch {
              reject(new PortalApiError('Upload failed', xhr.status));
            }
          }
        });

        xhr.addEventListener('error', () => {
          reject(new PortalApiError('Network error during upload', 0));
        });

        xhr.open('POST', `${API_BASE_URL}/api/v1/portal/documents/upload`);
        xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`);
        xhr.send(formData);
      });
    },

    /**
     * Get a presigned URL for uploading a file directly to storage.
     */
    getPresignedUploadUrl: async (
      filename: string,
      contentType?: string
    ): Promise<PresignedUploadResponse> => {
      const response = await authenticatedFetch(
        '/api/v1/portal/documents/upload-url',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename, content_type: contentType }),
        }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Confirm a presigned upload after file is uploaded.
     */
    confirmPresignedUpload: async (data: {
      document_id: string;
      storage_key: string;
      filename: string;
      content_type: string;
      file_size: number;
      document_type?: string;
    }): Promise<UploadedDocument> => {
      const response = await authenticatedFetch(
        '/api/v1/portal/documents/upload/confirm',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * List uploaded documents.
     */
    list: async (
      documentType?: string,
      page: number = 1,
      pageSize: number = 20
    ): Promise<DocumentListResponse> => {
      const params = new URLSearchParams();
      if (documentType) params.set('document_type', documentType);
      params.set('page', String(page));
      params.set('page_size', String(pageSize));

      const response = await authenticatedFetch(
        `/api/v1/portal/documents?${params.toString()}`
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Get a download URL for a document.
     */
    getDownloadUrl: async (documentId: string): Promise<{ download_url: string; filename: string }> => {
      const response = await authenticatedFetch(
        `/api/v1/portal/documents/${documentId}/download-url`
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Delete an uploaded document.
     */
    delete: async (documentId: string): Promise<void> => {
      const response = await authenticatedFetch(
        `/api/v1/portal/documents/${documentId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }
    },
  },

  push: {
    /**
     * Get VAPID public key for push subscription.
     */
    getVapidKey: async (): Promise<{ public_key: string }> => {
      const response = await authenticatedFetch('/api/v1/portal/push/vapid-key');

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Subscribe to push notifications.
     */
    subscribe: async (subscriptionData: {
      endpoint: string;
      keys: { p256dh: string; auth: string };
      device_name?: string;
    }): Promise<{ id: string; endpoint: string; is_active: boolean }> => {
      const response = await authenticatedFetch('/api/v1/portal/push/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(subscriptionData),
      });

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Unsubscribe from push notifications.
     */
    unsubscribe: async (endpoint: string): Promise<void> => {
      const response = await authenticatedFetch(
        `/api/v1/portal/push/unsubscribe?endpoint=${encodeURIComponent(endpoint)}`,
        { method: 'DELETE' }
      );

      if (!response.ok && response.status !== 404) {
        throw await parseErrorResponse(response);
      }
    },

    /**
     * Track notification click.
     */
    trackClick: async (notificationId: string): Promise<void> => {
      const response = await fetch(`${API_BASE_URL}/api/v1/portal/push/clicked`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notification_id: notificationId }),
      });

      if (!response.ok) {
        console.error('[Push] Failed to track click');
      }
    },

    /**
     * Log a PWA event (install, permission, etc).
     */
    logEvent: async (eventData: {
      event_type: string;
      platform?: string;
      metadata?: Record<string, unknown>;
    }): Promise<{ id: string }> => {
      const response = await authenticatedFetch('/api/v1/portal/push/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(eventData),
      });

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    // =========================================================================
    // WebAuthn/Biometric Methods
    // =========================================================================

    /**
     * Get biometric status (whether credentials exist).
     */
    getBiometricStatus: async (): Promise<{
      has_credentials: boolean;
      credential_count: number;
    }> => {
      const response = await authenticatedFetch('/api/v1/portal/push/webauthn/status');

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Get WebAuthn registration options.
     */
    getWebAuthnRegistrationOptions: async (): Promise<{
      challenge: string;
      rp: { id: string; name: string };
      user: { id: string; name: string; displayName: string };
      pub_key_cred_params: Array<{ type: string; alg: number }>;
      timeout: number;
      authenticator_selection?: {
        authenticatorAttachment?: string;
        userVerification?: string;
        residentKey?: string;
      };
      attestation: string;
    }> => {
      const response = await authenticatedFetch(
        '/api/v1/portal/push/webauthn/register/options',
        { method: 'POST' }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Verify WebAuthn registration.
     */
    verifyWebAuthnRegistration: async (
      credential: {
        id: string;
        rawId: string;
        type: string;
        response: {
          clientDataJSON: string;
          attestationObject: string;
        };
      },
      deviceName?: string
    ): Promise<{
      id: string;
      device_name: string | null;
      is_active: boolean;
      created_at: string;
      last_used_at: string | null;
    }> => {
      const response = await authenticatedFetch(
        '/api/v1/portal/push/webauthn/register/verify',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            credential,
            device_name: deviceName,
          }),
        }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Get WebAuthn authentication options.
     */
    getWebAuthnAuthenticationOptions: async (): Promise<{
      challenge: string;
      timeout: number;
      rp_id: string;
      allow_credentials: Array<{
        id: string;
        type: string;
        transports?: string[];
      }>;
      user_verification: string;
    }> => {
      const response = await authenticatedFetch(
        '/api/v1/portal/push/webauthn/authenticate/options',
        { method: 'POST' }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Verify WebAuthn authentication.
     */
    verifyWebAuthnAuthentication: async (credential: {
      id: string;
      rawId: string;
      type: string;
      response: {
        clientDataJSON: string;
        authenticatorData: string;
        signature: string;
        userHandle?: string;
      };
    }): Promise<{ authenticated: boolean }> => {
      const response = await authenticatedFetch(
        '/api/v1/portal/push/webauthn/authenticate/verify',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ credential }),
        }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * List biometric credentials.
     */
    listBiometricCredentials: async (): Promise<{
      credentials: Array<{
        id: string;
        device_name: string | null;
        is_active: boolean;
        created_at: string;
        last_used_at: string | null;
      }>;
      count: number;
    }> => {
      const response = await authenticatedFetch('/api/v1/portal/push/webauthn/credentials');

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }

      return response.json();
    },

    /**
     * Delete a biometric credential.
     */
    deleteBiometricCredential: async (credentialId: string): Promise<void> => {
      const response = await authenticatedFetch(
        `/api/v1/portal/push/webauthn/credentials/${credentialId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) {
        throw await parseErrorResponse(response);
      }
    },
  },

  // ============================================================================
  // Transaction Classification (Spec 047)
  // ============================================================================

  classify: {
    /**
     * Get pending classification requests for this client.
     */
    getPending: async () => {
      const response = await authenticatedFetch(
        `/api/v1/client-portal/classify/pending`
      );
      if (!response.ok) {
        throw await parseErrorResponse(response);
      }
      return response.json();
    },

    /**
     * Get classification request data for the client page.
     */
    getRequest: async (requestId: string) => {
      const response = await authenticatedFetch(
        `/api/v1/client-portal/classify/${requestId}`
      );
      if (!response.ok) {
        throw await parseErrorResponse(response);
      }
      return response.json();
    },

    /**
     * Save a classification for a single transaction (auto-save).
     */
    saveClassification: async (
      requestId: string,
      classificationId: string,
      data: { category?: string; description?: string; is_personal?: boolean; needs_help?: boolean }
    ) => {
      const response = await authenticatedFetch(
        `/api/v1/client-portal/classify/${requestId}/transactions/${classificationId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        }
      );
      if (!response.ok) {
        throw await parseErrorResponse(response);
      }
      return response.json();
    },

    /**
     * Submit all classifications for a request.
     */
    submit: async (requestId: string) => {
      const response = await authenticatedFetch(
        `/api/v1/client-portal/classify/${requestId}/submit`,
        { method: 'POST' }
      );
      if (!response.ok) {
        throw await parseErrorResponse(response);
      }
      return response.json();
    },

    /**
     * Upload a receipt for a transaction.
     */
    uploadReceipt: async (requestId: string, classificationId: string, file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const response = await authenticatedFetch(
        `/api/v1/client-portal/classify/${requestId}/transactions/${classificationId}/receipt`,
        {
          method: 'POST',
          body: formData,
        }
      );
      if (!response.ok) {
        throw await parseErrorResponse(response);
      }
      return response.json();
    },
  },
};

export default portalApi;
