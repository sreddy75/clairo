/**
 * Cached Requests Store Operations
 *
 * Manages offline caching of document requests in IndexedDB.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

import type { CachedRequest } from './db';
import { getDB } from './db';

// Cache expiry time (24 hours)
const CACHE_EXPIRY_MS = 24 * 60 * 60 * 1000;

/**
 * Cache a document request.
 */
export async function cacheRequest(request: Omit<CachedRequest, 'cachedAt'>): Promise<void> {
  const db = await getDB();
  await db.put('cached-requests', {
    ...request,
    cachedAt: Date.now(),
  });
}

/**
 * Cache multiple document requests.
 */
export async function cacheRequests(
  requests: Omit<CachedRequest, 'cachedAt'>[]
): Promise<void> {
  const db = await getDB();
  const tx = db.transaction('cached-requests', 'readwrite');
  const store = tx.objectStore('cached-requests');

  const cachedAt = Date.now();
  await Promise.all([
    ...requests.map((request) =>
      store.put({
        ...request,
        cachedAt,
      })
    ),
    tx.done,
  ]);
}

/**
 * Get a cached request by ID.
 */
export async function getCachedRequest(id: string): Promise<CachedRequest | undefined> {
  const db = await getDB();
  const request = await db.get('cached-requests', id);

  // Check if expired
  if (request && isExpired(request.cachedAt)) {
    await db.delete('cached-requests', id);
    return undefined;
  }

  return request;
}

/**
 * Get all cached requests for a connection.
 */
export async function getCachedRequestsByConnection(
  connectionId: string
): Promise<CachedRequest[]> {
  const db = await getDB();
  const requests = await db.getAllFromIndex(
    'cached-requests',
    'by-connection',
    connectionId
  );

  // Filter out expired requests
  const now = Date.now();
  const validRequests = requests.filter((r) => !isExpired(r.cachedAt, now));

  // Clean up expired ones in background
  const expiredIds = requests
    .filter((r) => isExpired(r.cachedAt, now))
    .map((r) => r.id);
  if (expiredIds.length > 0) {
    cleanupExpiredRequests(expiredIds);
  }

  return validRequests;
}

/**
 * Get all cached requests.
 */
export async function getAllCachedRequests(): Promise<CachedRequest[]> {
  const db = await getDB();
  const requests = await db.getAll('cached-requests');

  // Filter out expired requests
  const now = Date.now();
  return requests.filter((r) => !isExpired(r.cachedAt, now));
}

/**
 * Get cached requests by status.
 */
export async function getCachedRequestsByStatus(
  status: string
): Promise<CachedRequest[]> {
  const db = await getDB();
  const requests = await db.getAllFromIndex('cached-requests', 'by-status', status);

  const now = Date.now();
  return requests.filter((r) => !isExpired(r.cachedAt, now));
}

/**
 * Delete a cached request.
 */
export async function deleteCachedRequest(id: string): Promise<void> {
  const db = await getDB();
  await db.delete('cached-requests', id);
}

/**
 * Delete all cached requests for a connection.
 */
export async function deleteCachedRequestsByConnection(
  connectionId: string
): Promise<void> {
  const db = await getDB();
  const requests = await db.getAllFromIndex(
    'cached-requests',
    'by-connection',
    connectionId
  );

  const tx = db.transaction('cached-requests', 'readwrite');
  await Promise.all([
    ...requests.map((r) => tx.store.delete(r.id)),
    tx.done,
  ]);
}

/**
 * Clear all cached requests.
 */
export async function clearCachedRequests(): Promise<void> {
  const db = await getDB();
  await db.clear('cached-requests');
}

/**
 * Get the last cache timestamp.
 */
export async function getLastCacheTime(): Promise<number | null> {
  const db = await getDB();
  const requests = await db.getAllFromIndex('cached-requests', 'by-cached-at');

  if (requests.length === 0) {
    return null;
  }

  // Get the most recent cache time
  return Math.max(...requests.map((r) => r.cachedAt));
}

/**
 * Check if cache is stale (older than expiry time).
 */
export async function isCacheStale(): Promise<boolean> {
  const lastCacheTime = await getLastCacheTime();

  if (lastCacheTime === null) {
    return true;
  }

  return isExpired(lastCacheTime);
}

/**
 * Get cache statistics.
 */
export async function getCacheStats(): Promise<{
  totalRequests: number;
  pendingRequests: number;
  lastCacheTime: number | null;
  isStale: boolean;
}> {
  const db = await getDB();
  const allRequests = await db.getAll('cached-requests');
  const now = Date.now();

  const validRequests = allRequests.filter((r) => !isExpired(r.cachedAt, now));
  const pendingRequests = validRequests.filter(
    (r) => r.status === 'pending' || r.status === 'sent' || r.status === 'viewed'
  );

  const lastCacheTime =
    validRequests.length > 0
      ? Math.max(...validRequests.map((r) => r.cachedAt))
      : null;

  return {
    totalRequests: validRequests.length,
    pendingRequests: pendingRequests.length,
    lastCacheTime,
    isStale: lastCacheTime === null || isExpired(lastCacheTime, now),
  };
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Check if a cache entry is expired.
 */
function isExpired(cachedAt: number, now: number = Date.now()): boolean {
  return now - cachedAt > CACHE_EXPIRY_MS;
}

/**
 * Clean up expired requests in background.
 */
async function cleanupExpiredRequests(ids: string[]): Promise<void> {
  try {
    const db = await getDB();
    const tx = db.transaction('cached-requests', 'readwrite');
    await Promise.all([
      ...ids.map((id) => tx.store.delete(id)),
      tx.done,
    ]);
    console.log(`[Cache] Cleaned up ${ids.length} expired requests`);
  } catch (error) {
    console.warn('[Cache] Failed to clean up expired requests:', error);
  }
}

/**
 * Convert API response to cached request format.
 */
export function toCachedRequest(
  apiRequest: {
    id: string;
    title: string;
    description: string;
    status: string;
    priority: string;
    due_date?: string | null;
    sent_at?: string | null;
    viewed_at?: string | null;
    responded_at?: string | null;
    is_overdue?: boolean;
    days_until_due?: number | null;
  },
  connectionId: string
): Omit<CachedRequest, 'cachedAt'> {
  return {
    id: apiRequest.id,
    connectionId,
    title: apiRequest.title,
    description: apiRequest.description,
    status: apiRequest.status,
    priority: apiRequest.priority,
    dueDate: apiRequest.due_date ?? null,
    sentAt: apiRequest.sent_at ?? null,
    viewedAt: apiRequest.viewed_at ?? null,
    respondedAt: apiRequest.responded_at ?? null,
    isOverdue: apiRequest.is_overdue ?? false,
    daysUntilDue: apiRequest.days_until_due ?? null,
  };
}
