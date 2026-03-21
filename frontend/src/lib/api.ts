import createClient from 'openapi-fetch';

import type { paths } from '@/types/api';

/**
 * API client for Clairo backend.
 *
 * Uses openapi-fetch for type-safe API calls based on the OpenAPI schema.
 * Types are generated from the backend's OpenAPI spec.
 *
 * @example
 * const { data, error } = await api.GET('/health');
 */
export const api = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
});

/**
 * Set the authentication token for API requests.
 *
 * @param token - JWT token to use for authentication
 */
export function setAuthToken(token: string | null) {
  if (token) {
    api.use({
      onRequest: ({ request }) => {
        request.headers.set('Authorization', `Bearer ${token}`);
        return request;
      },
    });
  }
}

/**
 * API error type for consistent error handling.
 */
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

/**
 * Extract error from API response.
 */
export function getApiError(error: unknown): ApiError {
  if (typeof error === 'object' && error !== null && 'error' in error) {
    const apiError = (error as { error: ApiError }).error;
    return apiError;
  }
  return {
    code: 'UNKNOWN_ERROR',
    message: 'An unexpected error occurred',
  };
}
