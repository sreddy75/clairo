'use client';

/**
 * Hook for managing XPM client Xero organization connections.
 *
 * Provides methods for:
 * - Initiating OAuth for individual clients
 * - Sequential "Connect All" workflow
 * - Tracking connection progress
 * - Handling OAuth callbacks
 */

import { useAuth } from '@clerk/nextjs';
import { useCallback, useState } from 'react';

import {
  connectClientXero,
  connectNextClient,
  getConnectionProgress,
  getXpmClients,
  setAuthToken,
  syncXeroConnections,
  type ConnectNextClientResponse,
  type XpmClient,
  type XpmClientConnectionProgress,
  type XpmClientConnectionStatus,
} from '@/lib/api/onboarding';

interface UseClientXeroConnectionState {
  // Connection progress
  progress: XpmClientConnectionProgress | null;
  isLoadingProgress: boolean;

  // XPM clients list
  clients: XpmClient[];
  totalClients: number;
  isLoadingClients: boolean;

  // Connect flow state
  isConnecting: boolean;
  currentClient: XpmClient | null;
  connectError: string | null;

  // Connect-all flow state
  isConnectAllActive: boolean;
  connectAllProgress: {
    current: number;
    total: number;
    skipped: string[];
  };
}

interface UseClientXeroConnectionReturn extends UseClientXeroConnectionState {
  // Methods
  fetchProgress: () => Promise<void>;
  fetchClients: (
    search?: string,
    status?: XpmClientConnectionStatus,
    page?: number
  ) => Promise<void>;
  syncConnections: () => Promise<void>;

  // Individual client connection
  connectClient: (client: XpmClient) => Promise<void>;

  // Connect-all flow
  startConnectAll: () => Promise<void>;
  connectNext: () => Promise<ConnectNextClientResponse | null>;
  skipClient: (clientId: string) => void;
  pauseConnectAll: () => void;
  resumeConnectAll: () => Promise<void>;

  // Callback handling
  handleOAuthCallback: (success: boolean, clientId?: string) => void;

  // Reset
  resetError: () => void;
}

export function useClientXeroConnection(): UseClientXeroConnectionReturn {
  const { getToken } = useAuth();

  // State
  const [progress, setProgress] = useState<XpmClientConnectionProgress | null>(
    null
  );
  const [isLoadingProgress, setIsLoadingProgress] = useState(false);

  const [clients, setClients] = useState<XpmClient[]>([]);
  const [totalClients, setTotalClients] = useState(0);
  const [isLoadingClients, setIsLoadingClients] = useState(false);

  const [isConnecting, setIsConnecting] = useState(false);
  const [currentClient, setCurrentClient] = useState<XpmClient | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);

  const [isConnectAllActive, setIsConnectAllActive] = useState(false);
  const [connectAllProgress, setConnectAllProgress] = useState({
    current: 0,
    total: 0,
    skipped: [] as string[],
  });

  // Helper to set auth token
  const ensureAuth = useCallback(async () => {
    const token = await getToken();
    if (token) {
      setAuthToken(token);
    }
    return !!token;
  }, [getToken]);

  // Fetch connection progress
  const fetchProgress = useCallback(async () => {
    try {
      setIsLoadingProgress(true);
      await ensureAuth();
      const data = await getConnectionProgress();
      setProgress(data);
    } catch (error) {
      console.error('Failed to fetch connection progress:', error);
    } finally {
      setIsLoadingProgress(false);
    }
  }, [ensureAuth]);

  // Fetch XPM clients
  const fetchClients = useCallback(
    async (
      search?: string,
      status?: XpmClientConnectionStatus,
      page: number = 1
    ) => {
      try {
        setIsLoadingClients(true);
        await ensureAuth();
        const data = await getXpmClients(search, status, page);
        setClients(data.clients);
        setTotalClients(data.total);
      } catch (error) {
        console.error('Failed to fetch XPM clients:', error);
      } finally {
        setIsLoadingClients(false);
      }
    },
    [ensureAuth]
  );

  // Sync Xero connections
  const syncConnections = useCallback(async () => {
    try {
      setIsLoadingClients(true);
      await ensureAuth();
      await syncXeroConnections();
      // Refresh clients and progress after sync
      await Promise.all([fetchClients(), fetchProgress()]);
    } catch (error) {
      console.error('Failed to sync connections:', error);
      setConnectError(
        error instanceof Error ? error.message : 'Failed to sync connections'
      );
    } finally {
      setIsLoadingClients(false);
    }
  }, [ensureAuth, fetchClients, fetchProgress]);

  // Connect individual client
  const connectClient = useCallback(
    async (client: XpmClient) => {
      try {
        setIsConnecting(true);
        setCurrentClient(client);
        setConnectError(null);
        await ensureAuth();

        const response = await connectClientXero(client.id);

        // Store current client in session storage for callback handling
        sessionStorage.setItem(
          'xero_connecting_client',
          JSON.stringify({
            id: client.id,
            name: client.name,
          })
        );

        // Redirect to Xero OAuth
        window.location.href = response.authorization_url;
      } catch (error) {
        setIsConnecting(false);
        setCurrentClient(null);
        setConnectError(
          error instanceof Error
            ? error.message
            : 'Failed to initiate Xero connection'
        );
      }
    },
    [ensureAuth]
  );

  // Start connect-all flow
  const startConnectAll = useCallback(async () => {
    try {
      setIsConnectAllActive(true);
      setConnectError(null);
      await ensureAuth();

      // Get initial progress
      const progressData = await getConnectionProgress();
      setProgress(progressData);

      setConnectAllProgress({
        current: progressData.connected,
        total: progressData.total_clients,
        skipped: [],
      });

      // Get first unconnected client
      const response = await connectNextClient();

      if (response.has_next && response.authorization_url) {
        setCurrentClient(response.next_client);

        // Store connect-all state for callback
        sessionStorage.setItem(
          'xero_connect_all',
          JSON.stringify({
            active: true,
            current: progressData.connected,
            total: progressData.total_clients,
            skipped: [],
          })
        );

        // Redirect to Xero OAuth
        window.location.href = response.authorization_url;
      } else {
        // No clients to connect
        setIsConnectAllActive(false);
      }
    } catch (error) {
      setIsConnectAllActive(false);
      setConnectError(
        error instanceof Error
          ? error.message
          : 'Failed to start connect-all flow'
      );
    }
  }, [ensureAuth]);

  // Connect next client in flow
  const connectNext = useCallback(async () => {
    try {
      await ensureAuth();
      const response = await connectNextClient();

      if (response.has_next && response.authorization_url) {
        setCurrentClient(response.next_client);
        setProgress(response.progress);

        setConnectAllProgress((prev) => ({
          ...prev,
          current: response.progress.connected,
        }));

        // Update session storage
        const stored = sessionStorage.getItem('xero_connect_all');
        if (stored) {
          const state = JSON.parse(stored);
          sessionStorage.setItem(
            'xero_connect_all',
            JSON.stringify({
              ...state,
              current: response.progress.connected,
            })
          );
        }

        return response;
      } else {
        // All clients connected
        setIsConnectAllActive(false);
        setCurrentClient(null);
        sessionStorage.removeItem('xero_connect_all');
        return response;
      }
    } catch (error) {
      setConnectError(
        error instanceof Error ? error.message : 'Failed to connect next client'
      );
      return null;
    }
  }, [ensureAuth]);

  // Skip client in connect-all flow
  const skipClient = useCallback((clientId: string) => {
    setConnectAllProgress((prev) => ({
      ...prev,
      skipped: [...prev.skipped, clientId],
    }));

    // Update session storage
    const stored = sessionStorage.getItem('xero_connect_all');
    if (stored) {
      const state = JSON.parse(stored);
      sessionStorage.setItem(
        'xero_connect_all',
        JSON.stringify({
          ...state,
          skipped: [...(state.skipped || []), clientId],
        })
      );
    }
  }, []);

  // Pause connect-all flow
  const pauseConnectAll = useCallback(() => {
    setIsConnectAllActive(false);
    setCurrentClient(null);
    sessionStorage.removeItem('xero_connect_all');
  }, []);

  // Resume connect-all flow
  const resumeConnectAll = useCallback(async () => {
    const stored = sessionStorage.getItem('xero_connect_all');
    if (stored) {
      const state = JSON.parse(stored);
      setIsConnectAllActive(true);
      setConnectAllProgress({
        current: state.current || 0,
        total: state.total || 0,
        skipped: state.skipped || [],
      });

      // Get next client
      await connectNext();
    } else {
      // Start fresh
      await startConnectAll();
    }
  }, [connectNext, startConnectAll]);

  // Handle OAuth callback
  const handleOAuthCallback = useCallback(
    (success: boolean, _clientId?: string) => {
      setIsConnecting(false);

      if (success) {
        // Check if this was part of connect-all flow
        const connectAllState = sessionStorage.getItem('xero_connect_all');
        if (connectAllState) {
          const state = JSON.parse(connectAllState);
          if (state.active) {
            setIsConnectAllActive(true);
            setConnectAllProgress({
              current: state.current + 1,
              total: state.total,
              skipped: state.skipped || [],
            });
          }
        }

        // Clear single client state
        sessionStorage.removeItem('xero_connecting_client');

        // Refresh data
        fetchProgress();
        fetchClients();
      } else {
        setConnectError('Xero connection was cancelled or failed');

        // Clear states
        sessionStorage.removeItem('xero_connecting_client');
        sessionStorage.removeItem('xero_connect_all');
        setIsConnectAllActive(false);
      }

      setCurrentClient(null);
    },
    [fetchClients, fetchProgress]
  );

  // Reset error
  const resetError = useCallback(() => {
    setConnectError(null);
  }, []);

  return {
    // State
    progress,
    isLoadingProgress,
    clients,
    totalClients,
    isLoadingClients,
    isConnecting,
    currentClient,
    connectError,
    isConnectAllActive,
    connectAllProgress,

    // Methods
    fetchProgress,
    fetchClients,
    syncConnections,
    connectClient,
    startConnectAll,
    connectNext,
    skipClient,
    pauseConnectAll,
    resumeConnectAll,
    handleOAuthCallback,
    resetError,
  };
}
