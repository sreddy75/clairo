/**
 * API Client for Backend Communication
 *
 * Provides a typed, fetch-based HTTP client for communicating with the backend API.
 * Handles authentication headers, error responses, and provides a consistent interface.
 */

// Use empty base so requests go through Next.js rewrite proxy (avoids CORS)
const API_BASE_URL = '';

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: string | FormData;
}

interface ApiResponse<T = unknown> extends Response {
  data?: T;
}

/**
 * API Error class for handling backend error responses
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Create a full URL from a path
 */
function buildUrl(path: string): string {
  // Handle absolute URLs
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  // Ensure path starts with /
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

/**
 * Parse error response from the API
 */
async function parseErrorResponse(response: Response): Promise<ApiError> {
  try {
    const data = await response.json();
    const error = data.error || data;
    return new ApiError(
      error.message || `Request failed with status ${response.status}`,
      response.status,
      error.code,
      error.details
    );
  } catch {
    return new ApiError(
      `Request failed with status ${response.status}`,
      response.status
    );
  }
}

/**
 * Base request function with error handling
 */
async function request<T = unknown>(
  path: string,
  options: RequestOptions = {}
): Promise<ApiResponse<T>> {
  const url = buildUrl(path);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        ...options.headers,
      },
    });

    return response as ApiResponse<T>;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * API Client with HTTP method helpers
 */
export const apiClient = {
  /**
   * GET request
   */
  get: <T = unknown>(path: string, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: 'GET' }),

  /**
   * POST request
   */
  post: <T = unknown>(path: string, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: 'POST' }),

  /**
   * PUT request
   */
  put: <T = unknown>(path: string, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: 'PUT' }),

  /**
   * PATCH request
   */
  patch: <T = unknown>(path: string, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: 'PATCH' }),

  /**
   * DELETE request
   */
  delete: <T = unknown>(path: string, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: 'DELETE' }),

  /**
   * Helper to check if response is ok and parse JSON
   */
  parseResponse: async <T = unknown>(response: Response): Promise<T> => {
    if (!response.ok) {
      throw await parseErrorResponse(response);
    }
    return response.json();
  },

  /**
   * Helper to handle common API patterns
   */
  handleResponse: async <T = unknown>(response: Response): Promise<T> => {
    if (!response.ok) {
      throw await parseErrorResponse(response);
    }

    // Handle empty responses (204 No Content)
    if (response.status === 204) {
      return {} as T;
    }

    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      return response.json();
    }

    return {} as T;
  },
};

/**
 * Type-safe API endpoints for the Clairo backend
 */
export const api = {
  auth: {
    /**
     * Register a new user and create their practice
     */
    register: async (
      token: string,
      data: { email: string; tenant_name: string }
    ) => {
      const response = await apiClient.post('/api/v1/auth/register', {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      return apiClient.handleResponse<{
        user_id: string;
        tenant_id: string;
        email: string;
      }>(response);
    },

    /**
     * Get current user information
     */
    me: async (token: string) => {
      const response = await apiClient.get('/api/v1/auth/me', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      return apiClient.handleResponse<{
        user_id: string;
        tenant_id: string;
        email: string;
        role: string;
        tenant_name: string;
      }>(response);
    },
  },

  health: {
    /**
     * Check API health status
     */
    check: async () => {
      const response = await apiClient.get('/api/v1/health');
      return apiClient.handleResponse<{
        status: string;
        version: string;
        timestamp: string;
      }>(response);
    },
  },
};

export default apiClient;
