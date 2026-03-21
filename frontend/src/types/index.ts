/**
 * Shared type definitions for Clairo frontend.
 */

/**
 * User type representing an authenticated user.
 */
export interface User {
  id: string;
  email: string;
  name?: string;
  tenantId: string;
  roles: string[];
}

/**
 * Tenant type for multi-tenancy support.
 */
export interface Tenant {
  id: string;
  name: string;
  slug: string;
}

/**
 * Pagination parameters for list endpoints.
 */
export interface PaginationParams {
  skip?: number;
  limit?: number;
}

/**
 * Paginated response wrapper.
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

/**
 * API error response type.
 */
export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

/**
 * Generic result type for operations that can fail.
 */
export type Result<T, E = Error> =
  | { success: true; data: T }
  | { success: false; error: E };
