/**
 * Network Status Hook
 *
 * Tracks online/offline status and provides network state information.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { useSyncExternalStore } from 'react';

interface NetworkState {
  /** Whether the device is online */
  isOnline: boolean;
  /** Whether the connection is slow (effective type is 2g or slow-2g) */
  isSlow: boolean;
  /** Connection type if available */
  connectionType: string | null;
  /** Effective connection type (4g, 3g, 2g, slow-2g) */
  effectiveType: string | null;
  /** Downlink speed in Mbps */
  downlink: number | null;
  /** Round trip time in ms */
  rtt: number | null;
}

// Cached network state to prevent infinite re-renders
let cachedState: NetworkState | null = null;

// Get initial network state (cached to prevent new object on every call)
function getNetworkState(): NetworkState {
  if (typeof navigator === 'undefined') {
    return {
      isOnline: true,
      isSlow: false,
      connectionType: null,
      effectiveType: null,
      downlink: null,
      rtt: null,
    };
  }

  const connection =
    (navigator as any).connection ||
    (navigator as any).mozConnection ||
    (navigator as any).webkitConnection;

  const effectiveType = connection?.effectiveType ?? null;
  const isSlow =
    effectiveType === '2g' ||
    effectiveType === 'slow-2g' ||
    (connection?.rtt && connection.rtt > 500);

  const newState: NetworkState = {
    isOnline: navigator.onLine,
    isSlow,
    connectionType: connection?.type ?? null,
    effectiveType,
    downlink: connection?.downlink ?? null,
    rtt: connection?.rtt ?? null,
  };

  // Only update cache if state actually changed
  if (
    !cachedState ||
    cachedState.isOnline !== newState.isOnline ||
    cachedState.isSlow !== newState.isSlow ||
    cachedState.effectiveType !== newState.effectiveType
  ) {
    cachedState = newState;
  }

  return cachedState;
}

// Subscribe to network changes
function subscribe(callback: () => void): () => void {
  window.addEventListener('online', callback);
  window.addEventListener('offline', callback);

  const connection =
    (navigator as any).connection ||
    (navigator as any).mozConnection ||
    (navigator as any).webkitConnection;

  if (connection) {
    connection.addEventListener('change', callback);
  }

  return () => {
    window.removeEventListener('online', callback);
    window.removeEventListener('offline', callback);
    if (connection) {
      connection.removeEventListener('change', callback);
    }
  };
}

// Server snapshot for SSR
function getServerSnapshot(): NetworkState {
  return {
    isOnline: true,
    isSlow: false,
    connectionType: null,
    effectiveType: null,
    downlink: null,
    rtt: null,
  };
}

/**
 * Hook to track network status.
 *
 * @returns Network state including online status and connection info
 */
export function useNetworkStatus(): NetworkState {
  const state = useSyncExternalStore(
    subscribe,
    getNetworkState,
    getServerSnapshot
  );

  return state;
}

/**
 * Simplified hook that just returns online status.
 */
export function useIsOnline(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => (typeof navigator !== 'undefined' ? navigator.onLine : true),
    () => true
  );
}
