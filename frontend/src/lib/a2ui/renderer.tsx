'use client';

/**
 * A2UI Renderer
 * Main component for rendering A2UI messages
 */

import { Suspense, memo, useEffect, useMemo, useRef } from 'react';

import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

import { getComponent, hasComponent } from './catalog';
import { A2UIDataProvider, useA2UIData } from './context';
import { A2UIFallback, A2UIUnknownComponent } from './fallback';
import type {
  A2UIMessage,
  A2UIComponent,
  LayoutHint,
  ComponentCondition,
  ActionConfig,
  A2UIActionHandlers,
} from './types';


// =============================================================================
// Performance Logging Types
// =============================================================================

export interface A2UIRenderMetrics {
  messageId: string;
  componentCount: number;
  renderTimeMs: number;
  layout: LayoutHint | undefined;
  timestamp: number;
}

export interface A2UIActionMetrics {
  messageId: string;
  action: ActionConfig;
  timestamp: number;
}

export type OnRenderComplete = (metrics: A2UIRenderMetrics) => void;
export type OnActionTriggered = (metrics: A2UIActionMetrics) => void;


// =============================================================================
// Renderer Props
// =============================================================================

export interface A2UIRendererProps {
  /** A2UI message to render */
  message: A2UIMessage;
  /** Action handlers */
  actionHandlers?: A2UIActionHandlers;
  /** Custom class name */
  className?: string;
  /** Component to show while loading */
  loadingComponent?: React.ReactNode;
  /** Enable performance logging to console */
  enablePerfLogging?: boolean;
  /** Callback when render completes (for external metrics) */
  onRenderComplete?: OnRenderComplete;
  /** Callback when action is triggered (for external metrics) */
  onActionTriggered?: OnActionTriggered;
}

// =============================================================================
// Layout Classes
// =============================================================================

function getLayoutClasses(layout?: LayoutHint): string {
  switch (layout) {
    case 'grid':
      return 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4';
    case 'flow':
      return 'flex flex-wrap gap-4';
    case 'sidebar':
      return 'grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6';
    case 'stack':
    default:
      return 'flex flex-col gap-4';
  }
}

// =============================================================================
// Condition Evaluator
// =============================================================================

function evaluateCondition(
  condition: ComponentCondition,
  getValue: <T>(binding: string) => T | undefined
): boolean {
  const fieldValue = getValue(condition.field);

  switch (condition.operator) {
    case 'eq':
      return fieldValue === condition.value;
    case 'neq':
      return fieldValue !== condition.value;
    case 'gt':
      return typeof fieldValue === 'number' && fieldValue > (condition.value as number);
    case 'lt':
      return typeof fieldValue === 'number' && fieldValue < (condition.value as number);
    case 'gte':
      return typeof fieldValue === 'number' && fieldValue >= (condition.value as number);
    case 'lte':
      return typeof fieldValue === 'number' && fieldValue <= (condition.value as number);
    case 'exists':
      return fieldValue !== undefined && fieldValue !== null;
    case 'empty':
      return (
        fieldValue === undefined ||
        fieldValue === null ||
        fieldValue === '' ||
        (Array.isArray(fieldValue) && fieldValue.length === 0)
      );
    default:
      return true;
  }
}

// =============================================================================
// Component Renderer (Inner)
// =============================================================================

interface ComponentRendererProps {
  component: A2UIComponent;
  onAction?: (action: unknown) => void;
}

const ComponentRenderer = memo(function ComponentRenderer({
  component,
  onAction,
}: ComponentRendererProps) {
  // Evaluate conditional rendering
  const getValue = useA2UIData;
  if (component.condition) {
    const shouldRender = evaluateCondition(component.condition, getValue);
    if (!shouldRender) {
      return null;
    }
  }

  // Get component from catalog
  if (!hasComponent(component.type)) {
    return (
      <A2UIUnknownComponent
        type={component.type}
        props={component.props}
      />
    );
  }

  const Component = getComponent(component.type);
  if (!Component) {
    return (
      <A2UIUnknownComponent
        type={component.type}
        props={component.props}
      />
    );
  }

  // Render children recursively
  const children = component.children?.map((child) => (
    <ComponentRenderer
      key={child.id}
      component={child}
      onAction={onAction}
    />
  ));

  return (
    <Suspense
      fallback={
        <Skeleton className="h-32 w-full rounded-lg" />
      }
    >
      <Component
        id={component.id}
        dataBinding={component.dataBinding}
        onAction={onAction}
        {...component.props}
      >
        {children}
      </Component>
    </Suspense>
  );
});

// =============================================================================
// Main Renderer Component
// =============================================================================

export const A2UIRenderer = memo(function A2UIRenderer({
  message,
  actionHandlers,
  className,
  loadingComponent,
  enablePerfLogging = false,
  onRenderComplete,
  onActionTriggered,
}: A2UIRendererProps) {
  const { surfaceUpdate, dataModelUpdate, meta } = message;

  // Track render start time
  const renderStartRef = useRef<number>(performance.now());

  // Performance logging on mount
  useEffect(() => {
    const renderTimeMs = performance.now() - renderStartRef.current;
    const metrics: A2UIRenderMetrics = {
      messageId: meta.messageId,
      componentCount: surfaceUpdate.components.length,
      renderTimeMs,
      layout: surfaceUpdate.layout,
      timestamp: Date.now(),
    };

    // Console logging if enabled
    if (enablePerfLogging) {
      console.log(
        `[A2UI] Rendered ${metrics.componentCount} components in ${metrics.renderTimeMs.toFixed(2)}ms`,
        { messageId: metrics.messageId, layout: metrics.layout }
      );
    }

    // External callback
    onRenderComplete?.(metrics);
  }, [
    meta.messageId,
    surfaceUpdate.components.length,
    surfaceUpdate.layout,
    enablePerfLogging,
    onRenderComplete,
  ]);

  // Create action handler
  const handleAction = useMemo(() => {
    return async (actionRaw: unknown) => {
      const action = actionRaw as ActionConfig;
      const actionMetrics: A2UIActionMetrics = {
        messageId: meta.messageId,
        action,
        timestamp: Date.now(),
      };

      // Console logging if enabled
      if (enablePerfLogging) {
        console.log('[A2UI] Action triggered:', action);
      }

      // External callback
      onActionTriggered?.(actionMetrics);

      switch (action.type) {
        case 'navigate':
          actionHandlers?.navigate?.(action.target || '');
          break;
        case 'createTask':
          await actionHandlers?.createTask?.(action.payload || {});
          break;
        case 'approve':
          await actionHandlers?.approve?.(action.target || '');
          break;
        case 'export':
          await actionHandlers?.export?.(
            (action.payload?.format as string) || 'csv',
            action.target || ''
          );
          break;
        case 'custom':
          await actionHandlers?.custom?.(action.payload || {});
          break;
      }
    };
  }, [actionHandlers, enablePerfLogging, meta.messageId, onActionTriggered]);

  // Render fallback if no components
  if (!surfaceUpdate.components.length) {
    if (meta.fallbackText) {
      return (
        <A2UIFallback message={meta.fallbackText} />
      );
    }
    return loadingComponent || <Skeleton className="h-48 w-full" />;
  }

  const layoutClasses = getLayoutClasses(surfaceUpdate.layout);

  return (
    <A2UIDataProvider
      data={dataModelUpdate || {}}
      actionHandlers={actionHandlers}
    >
      <div
        className={cn(layoutClasses, className)}
        data-a2ui-message-id={meta.messageId}
        data-a2ui-layout={surfaceUpdate.layout || 'stack'}
        role="region"
        aria-label="Dynamic content"
      >
        {surfaceUpdate.components.map((component) => (
          <ComponentRenderer
            key={component.id}
            component={component}
            onAction={handleAction}
          />
        ))}
      </div>
    </A2UIDataProvider>
  );
});

// =============================================================================
// Streaming Renderer (for progressive updates)
// =============================================================================

export interface A2UIStreamingRendererProps extends Omit<A2UIRendererProps, 'message'> {
  /** Partial message during streaming */
  partialMessage?: Partial<A2UIMessage>;
  /** Whether streaming is complete */
  isComplete?: boolean;
}

export const A2UIStreamingRenderer = memo(function A2UIStreamingRenderer({
  partialMessage,
  isComplete = false,
  actionHandlers,
  className,
  loadingComponent,
}: A2UIStreamingRendererProps) {
  // If no partial message yet, show loading
  if (!partialMessage?.surfaceUpdate?.components?.length) {
    return loadingComponent || (
      <div className="space-y-4">
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  // Build a complete message from partial
  const message: A2UIMessage = {
    surfaceUpdate: {
      components: partialMessage.surfaceUpdate.components,
      layout: partialMessage.surfaceUpdate?.layout,
    },
    dataModelUpdate: partialMessage.dataModelUpdate,
    renderControl: partialMessage.renderControl,
    meta: partialMessage.meta || {
      messageId: 'streaming',
      generatedAt: new Date().toISOString(),
      deviceContext: {
        isMobile: false,
        isTablet: false,
      },
    },
  };

  return (
    <div className="relative">
      <A2UIRenderer
        message={message}
        actionHandlers={actionHandlers}
        className={className}
      />
      {!isComplete && (
        <div className="mt-4 flex items-center gap-2 text-muted-foreground">
          <div className="h-2 w-2 animate-pulse rounded-full bg-primary" />
          <span className="text-sm">Loading more...</span>
        </div>
      )}
    </div>
  );
});
