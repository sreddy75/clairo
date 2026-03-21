'use client';

/**
 * useSyncProgress Hook
 *
 * React hook for consuming real-time sync progress events via Server-Sent Events.
 * Wraps the native EventSource API to connect to the backend SSE endpoint.
 *
 * The auth token is passed as a query parameter since the browser EventSource API
 * does not support custom HTTP headers.
 */

import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useRef, useState } from 'react';

// =============================================================================
// Constants
// =============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Delay in milliseconds before attempting to reconnect after an SSE error. */
const RECONNECT_DELAY_MS = 3_000;

/** Delay before auto-disconnecting after a terminal event. */
const TERMINAL_DISCONNECT_DELAY_MS = 1_000;

// =============================================================================
// Types
// =============================================================================

export type SyncEventType =
  | 'sync_started'
  | 'entity_progress'
  | 'phase_complete'
  | 'sync_complete'
  | 'sync_failed'
  | 'post_sync_progress';

export interface SyncStartedEvent {
  type: 'sync_started';
  connection_id: string;
  job_id: string;
  phase: number;
  total_entities: number;
}

export interface EntityProgressEvent {
  type: 'entity_progress';
  entity_type: string;
  status: string;
  records_processed?: number;
  records_created?: number;
  records_updated?: number;
  records_failed?: number;
}

export interface PhaseCompleteEvent {
  type: 'phase_complete';
  phase: number;
  next_phase: number | null;
  entities_completed: number;
  records_processed: number;
}

export interface SyncCompleteEvent {
  type: 'sync_complete';
  connection_id: string;
  job_id: string;
  status: string;
  records_processed: number;
  records_created: number;
  records_updated: number;
  records_failed: number;
}

export interface SyncFailedEvent {
  type: 'sync_failed';
  connection_id: string;
  job_id: string;
  error: string;
}

export interface PostSyncProgressEvent {
  type: 'post_sync_progress';
  task_type: string;
  status: string;
  result_summary?: Record<string, unknown>;
}

export type SyncEvent =
  | SyncStartedEvent
  | EntityProgressEvent
  | PhaseCompleteEvent
  | SyncCompleteEvent
  | SyncFailedEvent
  | PostSyncProgressEvent;

export type SSEConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface UseSyncProgressOptions {
  /** The Xero connection ID to subscribe to. */
  connectionId: string;
  /** Optional job ID to filter events for a specific sync job. */
  jobId?: string;
  /** Whether the SSE connection should be active. Defaults to true. */
  enabled?: boolean;
  /** Callback invoked for each received event. */
  onEvent?: (event: SyncEvent) => void;
  /** Callback invoked when the sync reaches a terminal state (complete or failed). */
  onComplete?: () => void;
  /** Callback invoked when the sync fails, providing the error message. */
  onError?: (error: string) => void;
}

export interface UseSyncProgressReturn {
  /** Current SSE connection status. */
  status: SSEConnectionStatus;
  /** Ordered list of all received events. */
  events: SyncEvent[];
  /** The most recently received event, or null if none yet. */
  lastEvent: SyncEvent | null;
  /** Manually disconnect the SSE stream. */
  disconnect: () => void;
}

// =============================================================================
// Hook
// =============================================================================

/**
 * Hook for streaming real-time Xero sync progress via Server-Sent Events.
 *
 * Connects to the backend `/sync/stream` SSE endpoint and parses typed events.
 * Handles automatic reconnection on error, auto-disconnects on terminal events,
 * and supports optional job_id filtering.
 *
 * @example
 * ```tsx
 * const { status, events, lastEvent, disconnect } = useSyncProgress({
 *   connectionId: 'abc-123',
 *   jobId: 'def-456',
 *   onComplete: () => queryClient.invalidateQueries(['client-data']),
 *   onError: (err) => toast.error(err),
 * });
 * ```
 */
export function useSyncProgress({
  connectionId,
  jobId,
  enabled = true,
  onEvent,
  onComplete,
  onError,
}: UseSyncProgressOptions): UseSyncProgressReturn {
  const { getToken } = useAuth();
  const [status, setStatus] = useState<SSEConnectionStatus>('disconnected');
  const [events, setEvents] = useState<SyncEvent[]>([]);
  const [lastEvent, setLastEvent] = useState<SyncEvent | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Store callbacks in refs to avoid triggering reconnections when they change
  const onEventRef = useRef(onEvent);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);
  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setStatus('disconnected');
  }, []);

  useEffect(() => {
    if (!enabled || !connectionId) {
      disconnect();
      return;
    }

    let cancelled = false;

    const connect = async () => {
      try {
        const token = await getToken();
        if (!token || cancelled) return;

        setStatus('connecting');

        // Build SSE URL with auth token as query param (EventSource cannot send custom headers)
        let url = `${API_BASE_URL}/api/v1/integrations/xero/connections/${connectionId}/sync/stream?token=${encodeURIComponent(token)}`;
        if (jobId) {
          url += `&job_id=${encodeURIComponent(jobId)}`;
        }

        const es = new EventSource(url);
        eventSourceRef.current = es;

        es.onopen = () => {
          if (!cancelled) setStatus('connected');
        };

        es.onerror = () => {
          if (cancelled) return;
          setStatus('error');
          es.close();
          eventSourceRef.current = null;

          // Attempt reconnection after a delay
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!cancelled) connect();
          }, RECONNECT_DELAY_MS);
        };

        // Register listeners for each known event type
        const eventTypes: SyncEventType[] = [
          'sync_started',
          'entity_progress',
          'phase_complete',
          'sync_complete',
          'sync_failed',
          'post_sync_progress',
        ];

        for (const eventType of eventTypes) {
          es.addEventListener(eventType, (e: MessageEvent) => {
            if (cancelled) return;
            try {
              const data = JSON.parse(e.data);
              const event: SyncEvent = { type: eventType, ...data };

              setEvents((prev) => [...prev, event]);
              setLastEvent(event);
              onEventRef.current?.(event);

              // Handle terminal events
              if (eventType === 'sync_complete' || eventType === 'sync_failed') {
                onCompleteRef.current?.();

                // Auto-disconnect shortly after terminal event
                setTimeout(() => {
                  if (!cancelled) disconnect();
                }, TERMINAL_DISCONNECT_DELAY_MS);
              }

              if (eventType === 'sync_failed') {
                onErrorRef.current?.((event as SyncFailedEvent).error);
              }
            } catch {
              // Ignore JSON parse errors for malformed events
            }
          });
        }
      } catch {
        if (!cancelled) setStatus('error');
      }
    };

    connect();

    return () => {
      cancelled = true;
      disconnect();
    };
    // Only reconnect when connectionId, jobId, or enabled changes.
    // Callback refs are used to avoid reconnection on callback changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId, jobId, enabled, getToken, disconnect]);

  return { status, events, lastEvent, disconnect };
}
