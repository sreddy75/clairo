/**
 * Cached Dashboard Store Operations
 *
 * Manages offline caching of dashboard data in IndexedDB.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

import { toCachedRequest } from './cached-requests';
import type { CachedDashboard, CachedRequest } from './db';
import { getDB } from './db';

// Dashboard cache expiry time (1 hour)
const DASHBOARD_CACHE_EXPIRY_MS = 60 * 60 * 1000;

/**
 * Cache dashboard data.
 */
export async function cacheDashboard(
  dashboard: Omit<CachedDashboard, 'id' | 'cachedAt'>
): Promise<void> {
  const db = await getDB();
  await db.put('cached-dashboard', {
    id: 'dashboard',
    ...dashboard,
    cachedAt: Date.now(),
  });
}

/**
 * Get cached dashboard data.
 */
export async function getCachedDashboard(): Promise<CachedDashboard | null> {
  const db = await getDB();
  const dashboard = await db.get('cached-dashboard', 'dashboard');

  if (!dashboard) {
    return null;
  }

  // Check if expired (but still return it for offline use)
  return dashboard;
}

/**
 * Check if dashboard cache is stale.
 */
export async function isDashboardCacheStale(): Promise<boolean> {
  const dashboard = await getCachedDashboard();

  if (!dashboard) {
    return true;
  }

  return Date.now() - dashboard.cachedAt > DASHBOARD_CACHE_EXPIRY_MS;
}

/**
 * Get dashboard cache age in milliseconds.
 */
export async function getDashboardCacheAge(): Promise<number | null> {
  const dashboard = await getCachedDashboard();

  if (!dashboard) {
    return null;
  }

  return Date.now() - dashboard.cachedAt;
}

/**
 * Clear cached dashboard.
 */
export async function clearCachedDashboard(): Promise<void> {
  const db = await getDB();
  await db.delete('cached-dashboard', 'dashboard');
}

/**
 * Update cached dashboard with fresh data.
 * Also caches the recent requests for offline request viewing.
 */
export async function updateDashboardCache(
  apiDashboard: {
    connection_id: string;
    organization_name: string;
    pending_requests: number;
    unread_requests: number;
    total_documents: number;
    recent_requests: Array<{
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
    }>;
  }
): Promise<void> {
  const db = await getDB();
  const tx = db.transaction(['cached-dashboard', 'cached-requests'], 'readwrite');

  const cachedAt = Date.now();

  // Convert recent requests to cached format
  const cachedRequests: CachedRequest[] = apiDashboard.recent_requests.map(
    (req) => ({
      ...toCachedRequest(req, apiDashboard.connection_id),
      cachedAt,
    })
  );

  // Store dashboard
  await tx.objectStore('cached-dashboard').put({
    id: 'dashboard',
    connectionId: apiDashboard.connection_id,
    organizationName: apiDashboard.organization_name,
    pendingRequests: apiDashboard.pending_requests,
    unreadRequests: apiDashboard.unread_requests,
    totalDocuments: apiDashboard.total_documents,
    recentRequests: cachedRequests,
    cachedAt,
  });

  // Also cache individual requests for offline viewing
  const requestsStore = tx.objectStore('cached-requests');
  await Promise.all(cachedRequests.map((req) => requestsStore.put(req)));

  await tx.done;

  console.log(
    `[Cache] Dashboard cached with ${cachedRequests.length} requests`
  );
}

/**
 * Get offline-friendly dashboard data.
 * Returns cached data with staleness indicator.
 */
export async function getOfflineDashboard(): Promise<{
  data: CachedDashboard | null;
  isStale: boolean;
  cacheAge: number | null;
} | null> {
  const dashboard = await getCachedDashboard();

  if (!dashboard) {
    return null;
  }

  const cacheAge = Date.now() - dashboard.cachedAt;
  const isStale = cacheAge > DASHBOARD_CACHE_EXPIRY_MS;

  return {
    data: dashboard,
    isStale,
    cacheAge,
  };
}

/**
 * Format cache age for display.
 */
export function formatCacheAge(ageMs: number): string {
  const seconds = Math.floor(ageMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    return `${days} day${days !== 1 ? 's' : ''} ago`;
  }
  if (hours > 0) {
    return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
  }
  if (minutes > 0) {
    return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
  }
  return 'Just now';
}
