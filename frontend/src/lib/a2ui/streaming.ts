/**
 * A2UI Streaming Support
 * Utilities for handling streaming A2UI messages via Server-Sent Events
 */

import type { A2UIMessage, RenderControl } from './types';

// =============================================================================
// Types
// =============================================================================

export interface StreamingState {
  message: Partial<A2UIMessage> | null;
  isComplete: boolean;
  error: string | null;
}

export interface StreamingOptions {
  onUpdate?: (state: StreamingState) => void;
  onComplete?: (message: A2UIMessage) => void;
  onError?: (error: Error) => void;
}

// =============================================================================
// Stream Parser
// =============================================================================

export class A2UIStreamParser {
  private buffer: string = '';
  private currentMessage: Partial<A2UIMessage> | null = null;

  /**
   * Process a chunk of SSE data
   */
  processChunk(chunk: string): Partial<A2UIMessage> | null {
    this.buffer += chunk;

    // Process complete SSE events
    const lines = this.buffer.split('\n');
    this.buffer = lines.pop() || ''; // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') {
          return this.currentMessage;
        }

        try {
          const parsed = JSON.parse(data);
          this.mergeUpdate(parsed);
        } catch {
          // Ignore parse errors for incomplete JSON
        }
      }
    }

    return this.currentMessage;
  }

  /**
   * Merge an update into the current message
   */
  private mergeUpdate(update: Partial<A2UIMessage>): void {
    if (!this.currentMessage) {
      this.currentMessage = update;
      return;
    }

    // Handle render control for streaming updates
    const renderControl = update.renderControl as RenderControl | undefined;

    if (renderControl?.replace && this.currentMessage.surfaceUpdate) {
      // Replace specific components
      for (const id of renderControl.replace) {
        const index = this.currentMessage.surfaceUpdate.components.findIndex(
          (c) => c.id === id
        );
        const newComponent = update.surfaceUpdate?.components.find(
          (c) => c.id === id
        );
        if (index >= 0 && newComponent) {
          this.currentMessage.surfaceUpdate.components[index] = newComponent;
        }
      }
    } else if (renderControl?.appendTo && this.currentMessage.surfaceUpdate) {
      // Append to specific container
      const newComponents = update.surfaceUpdate?.components || [];
      this.currentMessage.surfaceUpdate.components.push(...newComponents);
    } else if (update.surfaceUpdate) {
      // Default: merge surface update
      if (!this.currentMessage.surfaceUpdate) {
        this.currentMessage.surfaceUpdate = update.surfaceUpdate;
      } else {
        this.currentMessage.surfaceUpdate.components = [
          ...this.currentMessage.surfaceUpdate.components,
          ...update.surfaceUpdate.components,
        ];
      }
    }

    // Merge data model updates
    if (update.dataModelUpdate) {
      this.currentMessage.dataModelUpdate = {
        ...this.currentMessage.dataModelUpdate,
        ...update.dataModelUpdate,
      };
    }

    // Update meta
    if (update.meta) {
      this.currentMessage.meta = {
        ...this.currentMessage.meta,
        ...update.meta,
      };
    }
  }

  /**
   * Reset the parser state
   */
  reset(): void {
    this.buffer = '';
    this.currentMessage = null;
  }

  /**
   * Check if streaming is complete
   */
  isComplete(): boolean {
    return this.currentMessage?.renderControl?.complete === true;
  }
}

// =============================================================================
// Stream Fetcher
// =============================================================================

export async function fetchA2UIStream(
  url: string,
  options: StreamingOptions & RequestInit = {}
): Promise<A2UIMessage> {
  const { onUpdate, onComplete, onError, ...fetchOptions } = options;

  const parser = new A2UIStreamParser();

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers: {
        Accept: 'text/event-stream',
        ...fetchOptions.headers,
      },
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
      const message = parser.processChunk(chunk);

      if (message && onUpdate) {
        onUpdate({
          message,
          isComplete: parser.isComplete(),
          error: null,
        });
      }
    }

    const finalMessage = parser.processChunk('');

    if (!finalMessage?.surfaceUpdate || !finalMessage?.meta) {
      throw new Error('Incomplete A2UI message received');
    }

    const completeMessage = finalMessage as A2UIMessage;

    if (onComplete) {
      onComplete(completeMessage);
    }

    return completeMessage;
  } catch (error) {
    const err = error instanceof Error ? error : new Error(String(error));
    if (onError) {
      onError(err);
    }
    throw err;
  }
}

// =============================================================================
// Event Source Helper
// =============================================================================

export function createA2UIEventSource(
  url: string,
  options: StreamingOptions = {}
): EventSource {
  const { onUpdate, onComplete, onError } = options;

  const parser = new A2UIStreamParser();
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    if (event.data === '[DONE]') {
      const message = parser.processChunk('');
      if (message && onComplete) {
        onComplete(message as A2UIMessage);
      }
      eventSource.close();
      return;
    }

    parser.processChunk(`data: ${event.data}\n`);
    const message = parser.processChunk('');

    if (message && onUpdate) {
      onUpdate({
        message,
        isComplete: parser.isComplete(),
        error: null,
      });
    }
  };

  eventSource.onerror = () => {
    if (onError) {
      onError(new Error('EventSource connection failed'));
    }
    eventSource.close();
  };

  return eventSource;
}
