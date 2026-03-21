'use client';

/**
 * useA2UIStream Hook
 * React hook for consuming streaming A2UI messages
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import type { StreamingState } from '@/lib/a2ui/streaming';
import { A2UIStreamParser } from '@/lib/a2ui/streaming';
import type { A2UIMessage } from '@/lib/a2ui/types';

// =============================================================================
// Types
// =============================================================================

export interface UseA2UIStreamOptions {
  /** URL to stream from */
  url: string;
  /** Whether to start streaming immediately */
  autoStart?: boolean;
  /** Headers to include in the request */
  headers?: Record<string, string>;
  /** Callback when streaming completes */
  onComplete?: (message: A2UIMessage) => void;
  /** Callback when an error occurs */
  onError?: (error: Error) => void;
}

export interface UseA2UIStreamResult {
  /** Current partial message being streamed */
  message: Partial<A2UIMessage> | null;
  /** Whether streaming is in progress */
  isStreaming: boolean;
  /** Whether streaming has completed */
  isComplete: boolean;
  /** Error if streaming failed */
  error: Error | null;
  /** Start or restart streaming */
  start: () => void;
  /** Stop streaming */
  stop: () => void;
}

// =============================================================================
// Hook
// =============================================================================

export function useA2UIStream({
  url,
  autoStart = false,
  headers,
  onComplete,
  onError,
}: UseA2UIStreamOptions): UseA2UIStreamResult {
  const [state, setState] = useState<StreamingState>({
    message: null,
    isComplete: false,
    error: null,
  });
  const [isStreaming, setIsStreaming] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const parserRef = useRef<A2UIStreamParser | null>(null);

  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const start = useCallback(async () => {
    // Stop any existing stream
    stop();

    // Reset state
    setState({
      message: null,
      isComplete: false,
      error: null,
    });

    // Create new abort controller and parser
    abortControllerRef.current = new AbortController();
    parserRef.current = new A2UIStreamParser();
    setIsStreaming(true);

    try {
      const response = await fetch(url, {
        headers: {
          Accept: 'text/event-stream',
          ...headers,
        },
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const message = parserRef.current?.processChunk(chunk);

        if (message) {
          const isComplete = parserRef.current?.isComplete() || false;
          setState({
            message,
            isComplete,
            error: null,
          });
        }
      }

      // Process any remaining buffer
      const finalMessage = parserRef.current?.processChunk('');

      if (finalMessage?.surfaceUpdate && finalMessage?.meta) {
        const completeMessage = finalMessage as A2UIMessage;
        setState({
          message: completeMessage,
          isComplete: true,
          error: null,
        });

        if (onComplete) {
          onComplete(completeMessage);
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        // Streaming was intentionally stopped
        return;
      }

      const err = error instanceof Error ? error : new Error(String(error));
      setState((prev) => ({
        ...prev,
        error: err.message,
      }));

      if (onError) {
        onError(err);
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [url, headers, stop, onComplete, onError]);

  // Auto-start if enabled
  useEffect(() => {
    if (autoStart) {
      start();
    }

    return () => {
      stop();
    };
  }, [autoStart, start, stop]);

  return {
    message: state.message,
    isStreaming,
    isComplete: state.isComplete,
    error: state.error ? new Error(state.error) : null,
    start,
    stop,
  };
}
