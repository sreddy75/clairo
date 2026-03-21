/**
 * Upload Queue Operations
 *
 * Manages offline upload queue in IndexedDB with background sync.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

import type { QueuedUpload } from './db';
import { getDB } from './db';

export type { QueuedUpload };

// =============================================================================
// Queue Operations
// =============================================================================

/**
 * Add an upload to the queue.
 */
export async function queueUpload(
  requestId: string,
  file: File,
  message?: string
): Promise<string> {
  const db = await getDB();

  const id = crypto.randomUUID();
  const fileData = await file.arrayBuffer();

  const upload: QueuedUpload = {
    id,
    requestId,
    fileName: file.name,
    fileType: file.type,
    fileSize: file.size,
    fileData,
    message,
    status: 'pending',
    retryCount: 0,
    createdAt: Date.now(),
  };

  await db.add('upload-queue', upload);

  // Try to register background sync
  await registerBackgroundSync();

  console.log(`[Queue] Upload queued: ${id}`);
  return id;
}

/**
 * Get all queued uploads.
 */
export async function getQueuedUploads(): Promise<QueuedUpload[]> {
  const db = await getDB();
  return db.getAll('upload-queue');
}

/**
 * Get pending uploads (not yet processed).
 */
export async function getPendingUploads(): Promise<QueuedUpload[]> {
  const db = await getDB();
  return db.getAllFromIndex('upload-queue', 'by-status', 'pending');
}

/**
 * Get failed uploads.
 */
export async function getFailedUploads(): Promise<QueuedUpload[]> {
  const db = await getDB();
  return db.getAllFromIndex('upload-queue', 'by-status', 'failed');
}

/**
 * Get uploads by request ID.
 */
export async function getUploadsByRequest(
  requestId: string
): Promise<QueuedUpload[]> {
  const db = await getDB();
  return db.getAllFromIndex('upload-queue', 'by-request', requestId);
}

/**
 * Update upload status.
 */
export async function updateUploadStatus(
  id: string,
  status: 'pending' | 'uploading' | 'failed',
  error?: string
): Promise<void> {
  const db = await getDB();
  const upload = await db.get('upload-queue', id);

  if (!upload) {
    throw new Error(`Upload ${id} not found`);
  }

  upload.status = status;
  upload.lastAttemptAt = Date.now();

  if (status === 'failed') {
    upload.retryCount += 1;
    upload.error = error;
  }

  await db.put('upload-queue', upload);
}

/**
 * Remove upload from queue (after successful upload).
 */
export async function removeUpload(id: string): Promise<void> {
  const db = await getDB();
  await db.delete('upload-queue', id);
  console.log(`[Queue] Upload removed: ${id}`);
}

/**
 * Clear all uploads from queue.
 */
export async function clearQueue(): Promise<void> {
  const db = await getDB();
  await db.clear('upload-queue');
  console.log('[Queue] Queue cleared');
}

/**
 * Get queue statistics.
 */
export async function getQueueStats(): Promise<{
  pending: number;
  uploading: number;
  failed: number;
  total: number;
  totalSize: number;
}> {
  const uploads = await getQueuedUploads();

  const stats = {
    pending: 0,
    uploading: 0,
    failed: 0,
    total: uploads.length,
    totalSize: 0,
  };

  for (const upload of uploads) {
    stats.totalSize += upload.fileSize;

    switch (upload.status) {
      case 'pending':
        stats.pending++;
        break;
      case 'uploading':
        stats.uploading++;
        break;
      case 'failed':
        stats.failed++;
        break;
    }
  }

  return stats;
}

// =============================================================================
// Background Sync
// =============================================================================

const SYNC_TAG = 'upload-queue';
const MAX_RETRIES = 5;
const RETRY_DELAYS = [1000, 5000, 15000, 60000, 300000]; // 1s, 5s, 15s, 1m, 5m

/**
 * Register background sync.
 */
export async function registerBackgroundSync(): Promise<boolean> {
  if (!('serviceWorker' in navigator)) {
    console.log('[Queue] Service worker not supported');
    return false;
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    // @ts-expect-error - sync is not in TypeScript types
    await registration.sync.register(SYNC_TAG);
    console.log('[Queue] Background sync registered');
    return true;
  } catch (err) {
    console.warn('[Queue] Failed to register background sync:', err);
    return false;
  }
}

/**
 * Process the upload queue.
 * Called by service worker or manually when online.
 */
export async function processQueue(
  uploadFn: (upload: QueuedUpload) => Promise<void>
): Promise<{ processed: number; failed: number }> {
  const pending = await getPendingUploads();

  let processed = 0;
  let failed = 0;

  for (const upload of pending) {
    // Skip if too many retries
    if (upload.retryCount >= MAX_RETRIES) {
      await updateUploadStatus(upload.id, 'failed', 'Max retries exceeded');
      failed++;
      continue;
    }

    try {
      await updateUploadStatus(upload.id, 'uploading');
      await uploadFn(upload);
      await removeUpload(upload.id);
      processed++;
      console.log(`[Queue] Upload processed: ${upload.id}`);
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Upload failed';
      await updateUploadStatus(upload.id, 'failed', error);
      failed++;
      console.error(`[Queue] Upload failed: ${upload.id}`, err);
    }
  }

  return { processed, failed };
}

/**
 * Retry failed uploads with exponential backoff.
 */
export async function retryFailedUploads(): Promise<void> {
  const failed = await getFailedUploads();
  const now = Date.now();

  for (const upload of failed) {
    if (upload.retryCount >= MAX_RETRIES) {
      continue;
    }

    const delay = RETRY_DELAYS[Math.min(upload.retryCount, RETRY_DELAYS.length - 1)] ?? RETRY_DELAYS[0] ?? 1000;
    const lastAttempt = upload.lastAttemptAt || upload.createdAt;

    if (now - lastAttempt >= delay) {
      // Reset to pending for next processing cycle
      await updateUploadStatus(upload.id, 'pending');
      console.log(`[Queue] Retrying upload: ${upload.id} (attempt ${upload.retryCount + 1})`);
    }
  }
}

/**
 * Convert QueuedUpload back to File for upload.
 */
export function queuedUploadToFile(upload: QueuedUpload): File {
  const blob = new Blob([upload.fileData], { type: upload.fileType });
  return new File([blob], upload.fileName, { type: upload.fileType });
}
