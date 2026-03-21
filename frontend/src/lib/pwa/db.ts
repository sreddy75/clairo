/**
 * IndexedDB Database Setup for PWA Offline Support
 *
 * Provides offline storage for:
 * - Cached document requests
 * - Dashboard data
 * - Upload queue
 * - Captured pages (for multi-page scanning)
 * - User settings
 *
 * Spec: 032-pwa-mobile-document-capture
 */

import type { DBSchema, IDBPDatabase } from 'idb';
import { openDB } from 'idb';

// =============================================================================
// Database Schema
// =============================================================================

export interface CachedRequest {
  id: string;
  connectionId: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  dueDate: string | null;
  sentAt: string | null;
  viewedAt: string | null;
  respondedAt: string | null;
  isOverdue: boolean;
  daysUntilDue: number | null;
  cachedAt: number; // Timestamp
}

export interface CachedDashboard {
  id: string; // Always 'dashboard' for singleton
  connectionId: string;
  organizationName: string;
  pendingRequests: number;
  unreadRequests: number;
  totalDocuments: number;
  recentRequests: CachedRequest[];
  cachedAt: number;
}

export interface QueuedUpload {
  id: string;
  requestId: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  fileData: ArrayBuffer;
  message?: string;
  status: 'pending' | 'uploading' | 'failed';
  retryCount: number;
  createdAt: number;
  lastAttemptAt?: number;
  error?: string;
}

export interface CapturedPage {
  id: string;
  requestId: string;
  imageData: ArrayBuffer;
  thumbnailData: ArrayBuffer;
  order: number;
  createdAt: number;
}

export interface PWASettings {
  id: string; // Always 'settings' for singleton
  notificationsEnabled: boolean;
  autoUpload: boolean;
  imageQuality: 'low' | 'medium' | 'high';
  maxImageSize: number; // in bytes
  lastSyncAt?: number;
}

interface PortalDBSchema extends DBSchema {
  'cached-requests': {
    key: string;
    value: CachedRequest;
    indexes: {
      'by-connection': string;
      'by-status': string;
      'by-cached-at': number;
    };
  };
  'cached-dashboard': {
    key: string;
    value: CachedDashboard;
  };
  'upload-queue': {
    key: string;
    value: QueuedUpload;
    indexes: {
      'by-request': string;
      'by-status': string;
      'by-created-at': number;
    };
  };
  'captured-pages': {
    key: string;
    value: CapturedPage;
    indexes: {
      'by-request': string;
      'by-order': number;
    };
  };
  settings: {
    key: string;
    value: PWASettings;
  };
}

// =============================================================================
// Database Instance
// =============================================================================

const DB_NAME = 'clairo-portal';
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase<PortalDBSchema>> | null = null;

/**
 * Get the IndexedDB database instance.
 * Creates the database and stores on first access.
 */
export async function getDB(): Promise<IDBPDatabase<PortalDBSchema>> {
  if (dbPromise) {
    return dbPromise;
  }

  dbPromise = openDB<PortalDBSchema>(DB_NAME, DB_VERSION, {
    upgrade(db, oldVersion, newVersion, _transaction) {
      console.log(`[IDB] Upgrading from v${oldVersion} to v${newVersion}`);

      // Create cached-requests store
      if (!db.objectStoreNames.contains('cached-requests')) {
        const requestsStore = db.createObjectStore('cached-requests', {
          keyPath: 'id',
        });
        requestsStore.createIndex('by-connection', 'connectionId');
        requestsStore.createIndex('by-status', 'status');
        requestsStore.createIndex('by-cached-at', 'cachedAt');
      }

      // Create cached-dashboard store
      if (!db.objectStoreNames.contains('cached-dashboard')) {
        db.createObjectStore('cached-dashboard', {
          keyPath: 'id',
        });
      }

      // Create upload-queue store
      if (!db.objectStoreNames.contains('upload-queue')) {
        const uploadStore = db.createObjectStore('upload-queue', {
          keyPath: 'id',
        });
        uploadStore.createIndex('by-request', 'requestId');
        uploadStore.createIndex('by-status', 'status');
        uploadStore.createIndex('by-created-at', 'createdAt');
      }

      // Create captured-pages store
      if (!db.objectStoreNames.contains('captured-pages')) {
        const pagesStore = db.createObjectStore('captured-pages', {
          keyPath: 'id',
        });
        pagesStore.createIndex('by-request', 'requestId');
        pagesStore.createIndex('by-order', 'order');
      }

      // Create settings store
      if (!db.objectStoreNames.contains('settings')) {
        db.createObjectStore('settings', {
          keyPath: 'id',
        });
      }
    },
    blocked() {
      console.warn('[IDB] Database upgrade blocked by another tab');
    },
    blocking() {
      console.warn('[IDB] This tab is blocking a database upgrade');
    },
    terminated() {
      console.error('[IDB] Database connection terminated unexpectedly');
      dbPromise = null;
    },
  });

  return dbPromise;
}

/**
 * Close the database connection.
 */
export async function closeDB(): Promise<void> {
  if (dbPromise) {
    const db = await dbPromise;
    db.close();
    dbPromise = null;
  }
}

/**
 * Delete all data from the database.
 */
export async function clearAllData(): Promise<void> {
  const db = await getDB();
  const tx = db.transaction(
    ['cached-requests', 'cached-dashboard', 'upload-queue', 'captured-pages', 'settings'],
    'readwrite'
  );

  await Promise.all([
    tx.objectStore('cached-requests').clear(),
    tx.objectStore('cached-dashboard').clear(),
    tx.objectStore('upload-queue').clear(),
    tx.objectStore('captured-pages').clear(),
    tx.objectStore('settings').clear(),
    tx.done,
  ]);

  console.log('[IDB] All data cleared');
}

/**
 * Get storage usage estimate.
 */
export async function getStorageEstimate(): Promise<{
  usage: number;
  quota: number;
  usagePercent: number;
}> {
  if ('storage' in navigator && 'estimate' in navigator.storage) {
    const estimate = await navigator.storage.estimate();
    const usage = estimate.usage ?? 0;
    const quota = estimate.quota ?? 0;
    const usagePercent = quota > 0 ? (usage / quota) * 100 : 0;

    return { usage, quota, usagePercent };
  }

  return { usage: 0, quota: 0, usagePercent: 0 };
}

/**
 * Check if IndexedDB is available.
 */
export function isIndexedDBAvailable(): boolean {
  try {
    return typeof indexedDB !== 'undefined' && indexedDB !== null;
  } catch {
    return false;
  }
}

// =============================================================================
// Default Settings
// =============================================================================

export const DEFAULT_SETTINGS: PWASettings = {
  id: 'settings',
  notificationsEnabled: true,
  autoUpload: true,
  imageQuality: 'high',
  maxImageSize: 5 * 1024 * 1024, // 5MB
};

/**
 * Get or create default settings.
 */
export async function getSettings(): Promise<PWASettings> {
  const db = await getDB();
  const settings = await db.get('settings', 'settings');

  if (!settings) {
    await db.put('settings', DEFAULT_SETTINGS);
    return DEFAULT_SETTINGS;
  }

  return settings;
}

/**
 * Update settings.
 */
export async function updateSettings(
  updates: Partial<Omit<PWASettings, 'id'>>
): Promise<PWASettings> {
  const db = await getDB();
  const current = await getSettings();
  const updated = { ...current, ...updates };
  await db.put('settings', updated);
  return updated;
}
