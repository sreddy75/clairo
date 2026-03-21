/// <reference lib="webworker" />

/**
 * Portal Service Worker
 *
 * Handles:
 * - Offline caching via Workbox
 * - Push notifications
 * - Background sync for upload queue
 *
 * Spec: 032-pwa-mobile-document-capture
 */

import { ExpirationPlugin } from 'workbox-expiration';
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import {
  NetworkFirst,
  StaleWhileRevalidate,
  CacheFirst,
} from 'workbox-strategies';

declare const self: ServiceWorkerGlobalScope;

// Extend notification options to include vibrate
interface ExtendedNotificationOptions extends NotificationOptions {
  vibrate?: number[];
  actions?: Array<{ action: string; title: string }>;
}

// Background sync event type
interface SyncEvent extends ExtendableEvent {
  tag: string;
}

// Clean up old caches
cleanupOutdatedCaches();

// Precache static assets (injected by next-pwa)
precacheAndRoute(self.__WB_MANIFEST || []);

// Cache portal pages with stale-while-revalidate
registerRoute(
  ({ url }) => url.pathname.startsWith('/portal'),
  new StaleWhileRevalidate({
    cacheName: 'portal-pages-v1',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 32,
        maxAgeSeconds: 24 * 60 * 60,
      }),
    ],
  })
);

// Dashboard API - StaleWhileRevalidate for instant offline access
// Returns cached data immediately while fetching fresh data in background
registerRoute(
  ({ url }) => url.pathname === '/api/v1/portal/dashboard',
  new StaleWhileRevalidate({
    cacheName: 'portal-dashboard-v1',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 1,
        maxAgeSeconds: 60 * 60, // 1 hour
      }),
    ],
  })
);

// Requests list API - StaleWhileRevalidate for offline access
registerRoute(
  ({ url }) => url.pathname === '/api/v1/portal/requests',
  new StaleWhileRevalidate({
    cacheName: 'portal-requests-list-v1',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 5,
        maxAgeSeconds: 24 * 60 * 60,
      }),
    ],
  })
);

// Individual request details - NetworkFirst with fallback
registerRoute(
  ({ url }) => /^\/api\/v1\/portal\/requests\/[^/]+$/.test(url.pathname),
  new NetworkFirst({
    cacheName: 'portal-request-details-v1',
    networkTimeoutSeconds: 5,
    plugins: [
      new ExpirationPlugin({
        maxEntries: 50,
        maxAgeSeconds: 24 * 60 * 60,
      }),
    ],
  })
);

// Auth endpoints - NetworkFirst (no caching for auth)
registerRoute(
  ({ url }) =>
    url.pathname.startsWith('/api/v1/portal/auth') ||
    url.pathname.startsWith('/api/v1/client-portal/auth'),
  new NetworkFirst({
    cacheName: 'portal-auth-v1',
    networkTimeoutSeconds: 10,
    plugins: [
      new ExpirationPlugin({
        maxEntries: 10,
        maxAgeSeconds: 60 * 60, // 1 hour
      }),
    ],
  })
);

// Other portal API endpoints - NetworkFirst with cache fallback
registerRoute(
  ({ url }) =>
    url.pathname.startsWith('/api/v1/portal') &&
    url.pathname !== '/api/v1/portal/dashboard' &&
    !url.pathname.startsWith('/api/v1/portal/requests') &&
    !url.pathname.startsWith('/api/v1/portal/auth'),
  new NetworkFirst({
    cacheName: 'portal-api-v1',
    networkTimeoutSeconds: 10,
    plugins: [
      new ExpirationPlugin({
        maxEntries: 50,
        maxAgeSeconds: 24 * 60 * 60,
      }),
    ],
  })
);

// Cache static assets
registerRoute(
  ({ request }) =>
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'image' ||
    request.destination === 'font',
  new CacheFirst({
    cacheName: 'static-assets-v1',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 100,
        maxAgeSeconds: 30 * 24 * 60 * 60,
      }),
    ],
  })
);

// Handle push notifications
self.addEventListener('push', (event) => {
  if (!event.data) return;

  const data = event.data.json();
  const { title, body, icon, badge, data: notificationData } = data;

  const options: ExtendedNotificationOptions = {
    body,
    icon: icon || '/icons/icon.svg',
    badge: badge || '/icons/badge.png',
    data: notificationData,
    vibrate: [100, 50, 100],
    actions: [
      { action: 'open', title: 'Open' },
      { action: 'dismiss', title: 'Dismiss' },
    ],
  };

  event.waitUntil(
    self.registration.showNotification(title, options as NotificationOptions)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const url = event.notification.data?.url || '/portal';

  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then(async (clientList) => {
      // Focus existing window if open
      for (const client of clientList) {
        if (client.url.includes('/portal') && 'focus' in client) {
          await client.navigate(url);
          return client.focus();
        }
      }
      // Open new window
      if (self.clients.openWindow) {
        return self.clients.openWindow(url);
      }
      return undefined;
    })
  );

  // Track notification click
  if (event.notification.data?.notificationId) {
    fetch('/api/v1/portal/push/clicked', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        notification_id: event.notification.data.notificationId,
      }),
    }).catch(() => {
      // Ignore errors - best effort tracking
    });
  }
});

// Handle background sync for upload queue
self.addEventListener('sync', (event: Event) => {
  const syncEvent = event as SyncEvent;
  if (syncEvent.tag === 'upload-queue') {
    syncEvent.waitUntil(processUploadQueue());
  }
});

async function processUploadQueue(): Promise<void> {
  // This will be implemented in the upload-queue.ts module
  // The service worker just triggers the processing
  const clients = await self.clients.matchAll();
  for (const client of clients) {
    client.postMessage({ type: 'PROCESS_UPLOAD_QUEUE' });
  }
}

// Handle skip waiting message
self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// Log service worker lifecycle events
self.addEventListener('install', () => {
  console.log('[SW] Installing service worker...');
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Service worker activated');
  event.waitUntil(self.clients.claim());
});
