/**
 * Service Worker Registration Hook
 *
 * Manages service worker lifecycle: registration, updates, and skip waiting.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { useEffect, useState, useCallback } from 'react';

interface ServiceWorkerState {
  /** Service worker registration object */
  registration: ServiceWorkerRegistration | null;
  /** Whether an update is available and waiting */
  updateAvailable: boolean;
  /** Whether the service worker is ready */
  isReady: boolean;
  /** Any error that occurred during registration */
  error: Error | null;
}

export function useServiceWorker() {
  const [state, setState] = useState<ServiceWorkerState>({
    registration: null,
    updateAvailable: false,
    isReady: false,
    error: null,
  });

  useEffect(() => {
    // Only register in browser and production
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      return;
    }

    const registerServiceWorker = async () => {
      try {
        // Register service worker scoped to /portal
        const reg = await navigator.serviceWorker.register('/portal-sw.js', {
          scope: '/portal',
        });

        setState((prev) => ({
          ...prev,
          registration: reg,
          isReady: !!reg.active,
        }));

        // Listen for updates
        reg.addEventListener('updatefound', () => {
          const newWorker = reg.installing;

          newWorker?.addEventListener('statechange', () => {
            if (
              newWorker.state === 'installed' &&
              navigator.serviceWorker.controller
            ) {
              // New version available
              setState((prev) => ({ ...prev, updateAvailable: true }));
            }
          });
        });

        // Check for existing update
        if (reg.waiting) {
          setState((prev) => ({ ...prev, updateAvailable: true }));
        }

        console.log('[PWA] Service worker registered:', reg.scope);
      } catch (error) {
        console.error('[PWA] Service worker registration failed:', error);
        setState((prev) => ({
          ...prev,
          error: error instanceof Error ? error : new Error(String(error)),
        }));
      }
    };

    registerServiceWorker();

    // Handle controller change (after skipWaiting)
    const handleControllerChange = () => {
      window.location.reload();
    };

    navigator.serviceWorker.addEventListener(
      'controllerchange',
      handleControllerChange
    );

    return () => {
      navigator.serviceWorker.removeEventListener(
        'controllerchange',
        handleControllerChange
      );
    };
  }, []);

  /**
   * Skip the waiting service worker and activate the new version.
   * This will cause a page reload.
   */
  const skipWaiting = useCallback(() => {
    if (state.registration?.waiting) {
      state.registration.waiting.postMessage({ type: 'SKIP_WAITING' });
    }
  }, [state.registration]);

  /**
   * Check for service worker updates.
   */
  const checkForUpdates = useCallback(async () => {
    if (state.registration) {
      try {
        await state.registration.update();
      } catch (error) {
        console.error('[PWA] Failed to check for updates:', error);
      }
    }
  }, [state.registration]);

  return {
    ...state,
    skipWaiting,
    checkForUpdates,
  };
}
