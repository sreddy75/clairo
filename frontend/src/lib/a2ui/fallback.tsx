'use client';

/**
 * A2UI Fallback Components
 * Error handling and fallback UI for A2UI rendering
 */

import { AlertCircle, AlertTriangle, Info } from 'lucide-react';


import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

// =============================================================================
// Unknown Component Fallback
// =============================================================================

interface A2UIUnknownComponentProps {
  type: string;
  props?: Record<string, unknown>;
  className?: string;
}

export function A2UIUnknownComponent({
  type,
  props,
  className,
}: A2UIUnknownComponentProps) {
  const isDev = process.env.NODE_ENV === 'development';

  return (
    <Card className={cn('border-yellow-500/50 bg-yellow-50/10', className)}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm text-yellow-600">
          <AlertTriangle className="h-4 w-4" />
          Unknown Component
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="font-mono text-sm text-muted-foreground">
          Type: <code className="rounded bg-muted px-1">{type}</code>
        </p>
        {isDev && props && Object.keys(props).length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              View props
            </summary>
            <pre className="mt-2 overflow-auto rounded bg-muted p-2">
              {JSON.stringify(props, null, 2)}
            </pre>
          </details>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Text Fallback
// =============================================================================

interface A2UIFallbackProps {
  message: string;
  className?: string;
}

export function A2UIFallback({ message, className }: A2UIFallbackProps) {
  return (
    <Alert className={cn('bg-muted/50', className)}>
      <Info className="h-4 w-4" />
      <AlertTitle>Content</AlertTitle>
      <AlertDescription className="whitespace-pre-wrap">{message}</AlertDescription>
    </Alert>
  );
}

// =============================================================================
// Error Fallback
// =============================================================================

interface A2UIErrorFallbackProps {
  error: Error;
  resetError?: () => void;
  className?: string;
}

export function A2UIErrorFallback({
  error,
  resetError,
  className,
}: A2UIErrorFallbackProps) {
  const isDev = process.env.NODE_ENV === 'development';

  return (
    <Alert variant="destructive" className={className}>
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Rendering Error</AlertTitle>
      <AlertDescription className="space-y-2">
        <p>Failed to render dynamic content.</p>
        {isDev && (
          <details className="text-xs">
            <summary className="cursor-pointer hover:underline">
              Error details
            </summary>
            <pre className="mt-2 overflow-auto whitespace-pre-wrap rounded bg-destructive/10 p-2">
              {error.message}
              {error.stack && `\n\n${error.stack}`}
            </pre>
          </details>
        )}
        {resetError && (
          <Button
            variant="outline"
            size="sm"
            onClick={resetError}
            className="mt-2"
          >
            Try Again
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}

// =============================================================================
// Loading Fallback
// =============================================================================

interface A2UILoadingFallbackProps {
  message?: string;
  className?: string;
}

export function A2UILoadingFallback({
  message = 'Loading content...',
  className,
}: A2UILoadingFallbackProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-4 p-8 text-center',
        className
      )}
    >
      <div className="relative h-8 w-8">
        <div className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
        <div className="absolute inset-0 animate-pulse rounded-full bg-primary/40" />
        <div className="absolute inset-1 rounded-full bg-primary" />
      </div>
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

// =============================================================================
// Empty State Fallback
// =============================================================================

interface A2UIEmptyFallbackProps {
  title?: string;
  message?: string;
  className?: string;
}

export function A2UIEmptyFallback({
  title = 'No content',
  message = 'There is nothing to display at the moment.',
  className,
}: A2UIEmptyFallbackProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 p-8 text-center',
        className
      )}
    >
      <div className="rounded-full bg-muted p-3">
        <Info className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="font-medium">{title}</h3>
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

// =============================================================================
// Error Boundary Fallback (for use with React Error Boundary)
// =============================================================================

interface A2UIErrorBoundaryFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
}

export function A2UIErrorBoundaryFallback({
  error,
  resetErrorBoundary,
}: A2UIErrorBoundaryFallbackProps) {
  return (
    <A2UIErrorFallback
      error={error}
      resetError={resetErrorBoundary}
    />
  );
}
