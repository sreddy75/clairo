/**
 * Push Notifications Hook
 *
 * Manages push notification subscriptions via Web Push API.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { useCallback, useEffect, useState } from 'react';

interface PushSubscriptionState {
  /** Whether notifications are supported in this browser */
  isSupported: boolean;
  /** Current permission status */
  permission: NotificationPermission;
  /** Whether we have an active subscription */
  isSubscribed: boolean;
  /** Loading state */
  isLoading: boolean;
  /** Error message if any */
  error: string | null;
}

interface PushNotificationsHook extends PushSubscriptionState {
  /** Request notification permission and subscribe */
  subscribe: () => Promise<boolean>;
  /** Unsubscribe from notifications */
  unsubscribe: () => Promise<boolean>;
  /** Check and update subscription status */
  checkSubscription: () => Promise<void>;
}

const API_BASE = '/api/v1/portal/push';

/**
 * Convert a base64 string to Uint8Array for Web Push API.
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

/**
 * Get device name from user agent.
 */
function getDeviceName(): string {
  const ua = navigator.userAgent;

  if (/iPhone/i.test(ua)) return 'iPhone';
  if (/iPad/i.test(ua)) return 'iPad';
  if (/Android/i.test(ua)) {
    // Try to extract device name from Android UA
    const match = ua.match(/Android.*?;\s*([^)]+)/);
    const devicePart = match?.[1];
    if (devicePart) {
      const buildIndex = devicePart.indexOf(' Build');
      return buildIndex > 0 ? devicePart.substring(0, buildIndex).trim() : devicePart.trim();
    }
    return 'Android Device';
  }
  if (/Mac/i.test(ua)) return 'Mac';
  if (/Windows/i.test(ua)) return 'Windows PC';
  if (/Linux/i.test(ua)) return 'Linux';

  return 'Unknown Device';
}

/**
 * Hook for managing push notification subscriptions.
 */
export function usePushNotifications(): PushNotificationsHook {
  const [state, setState] = useState<PushSubscriptionState>({
    isSupported: false,
    permission: 'default',
    isSubscribed: false,
    isLoading: true,
    error: null,
  });

  // Check if notifications are supported
  useEffect(() => {
    const checkSupport = async () => {
      const isSupported =
        'Notification' in window &&
        'serviceWorker' in navigator &&
        'PushManager' in window;

      if (!isSupported) {
        setState({
          isSupported: false,
          permission: 'denied',
          isSubscribed: false,
          isLoading: false,
          error: 'Push notifications not supported in this browser',
        });
        return;
      }

      const permission = Notification.permission;

      // Check for existing subscription
      let isSubscribed = false;
      try {
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        isSubscribed = subscription !== null;
      } catch {
        console.warn('[Push] Failed to check subscription status');
      }

      setState({
        isSupported: true,
        permission,
        isSubscribed,
        isLoading: false,
        error: null,
      });
    };

    checkSupport();
  }, []);

  /**
   * Fetch VAPID public key from server.
   */
  const fetchVapidKey = useCallback(async (): Promise<string | null> => {
    try {
      const response = await fetch(`${API_BASE}/vapid-key`);
      if (!response.ok) {
        throw new Error('Failed to fetch VAPID key');
      }
      const data = await response.json();
      return data.public_key;
    } catch (error) {
      console.error('[Push] Failed to fetch VAPID key:', error);
      return null;
    }
  }, []);

  /**
   * Subscribe to push notifications.
   */
  const subscribe = useCallback(async (): Promise<boolean> => {
    if (!state.isSupported) {
      return false;
    }

    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // Request notification permission
      const permission = await Notification.requestPermission();

      if (permission !== 'granted') {
        setState((prev) => ({
          ...prev,
          permission,
          isLoading: false,
          error: 'Notification permission denied',
        }));
        return false;
      }

      // Get VAPID public key
      const vapidKey = await fetchVapidKey();
      if (!vapidKey) {
        throw new Error('Push notifications not configured');
      }

      // Get service worker registration
      const registration = await navigator.serviceWorker.ready;

      // Subscribe to push manager
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey) as BufferSource,
      });

      // Send subscription to server
      const subscriptionJson = subscription.toJSON();
      const response = await fetch(`${API_BASE}/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          endpoint: subscriptionJson.endpoint,
          keys: {
            p256dh: subscriptionJson.keys?.p256dh,
            auth: subscriptionJson.keys?.auth,
          },
          device_name: getDeviceName(),
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to register subscription');
      }

      setState((prev) => ({
        ...prev,
        permission: 'granted',
        isSubscribed: true,
        isLoading: false,
        error: null,
      }));

      console.log('[Push] Successfully subscribed to notifications');
      return true;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to subscribe';
      console.error('[Push] Subscription failed:', message);
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: message,
      }));
      return false;
    }
  }, [state.isSupported, fetchVapidKey]);

  /**
   * Unsubscribe from push notifications.
   */
  const unsubscribe = useCallback(async (): Promise<boolean> => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // Get current subscription
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (!subscription) {
        setState((prev) => ({
          ...prev,
          isSubscribed: false,
          isLoading: false,
        }));
        return true;
      }

      // Notify server
      try {
        await fetch(
          `${API_BASE}/unsubscribe?endpoint=${encodeURIComponent(subscription.endpoint)}`,
          { method: 'DELETE' }
        );
      } catch {
        console.warn('[Push] Failed to notify server of unsubscribe');
      }

      // Unsubscribe locally
      await subscription.unsubscribe();

      setState((prev) => ({
        ...prev,
        isSubscribed: false,
        isLoading: false,
        error: null,
      }));

      console.log('[Push] Successfully unsubscribed from notifications');
      return true;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to unsubscribe';
      console.error('[Push] Unsubscribe failed:', message);
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: message,
      }));
      return false;
    }
  }, []);

  /**
   * Check and update subscription status.
   */
  const checkSubscription = useCallback(async (): Promise<void> => {
    if (!state.isSupported) {
      return;
    }

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      setState((prev) => ({
        ...prev,
        isSubscribed: subscription !== null,
        permission: Notification.permission,
      }));
    } catch (error) {
      console.warn('[Push] Failed to check subscription:', error);
    }
  }, [state.isSupported]);

  return {
    ...state,
    subscribe,
    unsubscribe,
    checkSubscription,
  };
}
