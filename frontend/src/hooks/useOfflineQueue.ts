/**
 * Offline Queue Hook
 *
 * Manages offline upload queue with automatic sync when online.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { useCallback, useEffect, useState } from 'react';

import {
  getQueueStats,
  processQueue,
  retryFailedUploads,
  queuedUploadToFile,
  type QueuedUpload,
} from '@/lib/pwa/upload-queue';

import { useNetworkStatus } from './useNetworkStatus';

interface QueueStats {
  pending: number;
  uploading: number;
  failed: number;
  total: number;
  totalSize: number;
}

interface OfflineQueueHook {
  /** Queue statistics */
  stats: QueueStats;
  /** Whether queue is being processed */
  isProcessing: boolean;
  /** Whether there are pending uploads */
  hasPending: boolean;
  /** Refresh queue stats */
  refresh: () => Promise<void>;
  /** Process pending uploads */
  processNow: () => Promise<{ processed: number; failed: number }>;
  /** Retry failed uploads */
  retryFailed: () => Promise<void>;
}

const INITIAL_STATS: QueueStats = {
  pending: 0,
  uploading: 0,
  failed: 0,
  total: 0,
  totalSize: 0,
};

/**
 * Hook for managing offline upload queue.
 */
export function useOfflineQueue(
  uploadFn?: (requestId: string, file: File, message?: string) => Promise<{ id: string }>
): OfflineQueueHook {
  const { isOnline } = useNetworkStatus();
  const [stats, setStats] = useState<QueueStats>(INITIAL_STATS);
  const [isProcessing, setIsProcessing] = useState(false);

  // Refresh stats from IndexedDB
  const refresh = useCallback(async () => {
    try {
      const queueStats = await getQueueStats();
      setStats(queueStats);
    } catch (err) {
      console.warn('[Queue] Failed to refresh stats:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Process queue when coming online
  useEffect(() => {
    if (isOnline && stats.pending > 0 && !isProcessing && uploadFn) {
      processNow();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOnline, stats.pending]);

  // Listen for service worker messages
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'PROCESS_UPLOAD_QUEUE') {
        processNow();
      }
    };

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', handleMessage);
      return () => {
        navigator.serviceWorker.removeEventListener('message', handleMessage);
      };
    }
    return undefined;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Process pending uploads
  const processNow = useCallback(async () => {
    if (isProcessing || !uploadFn) {
      return { processed: 0, failed: 0 };
    }

    setIsProcessing(true);

    try {
      // First, retry any failed uploads that are ready
      await retryFailedUploads();

      // Then process pending uploads
      const result = await processQueue(async (upload: QueuedUpload) => {
        const file = queuedUploadToFile(upload);
        await uploadFn(upload.requestId, file, upload.message);
      });

      // Refresh stats after processing
      await refresh();

      return result;
    } catch (err) {
      console.error('[Queue] Processing failed:', err);
      return { processed: 0, failed: 0 };
    } finally {
      setIsProcessing(false);
    }
  }, [isProcessing, uploadFn, refresh]);

  // Retry failed uploads
  const retryFailed = useCallback(async () => {
    await retryFailedUploads();
    await refresh();
  }, [refresh]);

  return {
    stats,
    isProcessing,
    hasPending: stats.pending > 0 || stats.uploading > 0,
    refresh,
    processNow,
    retryFailed,
  };
}
