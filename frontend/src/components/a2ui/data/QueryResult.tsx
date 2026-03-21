'use client';

/**
 * A2UI QueryResult Component
 * Displays the result of a natural language query with summary and data
 */

import { CheckCircle2, Clock, MessageSquare } from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UIQueryResultProps {
  id: string;
  query?: string;
  summary?: string;
  confidence?: number;
  executionTime?: number;
  dataBinding?: string;
  children?: React.ReactNode;
}

// =============================================================================
// Component
// =============================================================================

export function QueryResult({
  id,
  query,
  summary,
  confidence,
  executionTime,
  children,
}: A2UIQueryResultProps) {
  const confidenceColor =
    confidence && confidence >= 0.8
      ? 'text-status-success'
      : confidence && confidence >= 0.5
        ? 'text-status-warning'
        : 'text-status-danger';

  return (
    <Card id={id}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <MessageSquare className="h-4 w-4" />
              <span>Query</span>
            </div>
            <CardTitle className="text-base font-medium">&quot;{query}&quot;</CardTitle>
          </div>
          <div className="flex items-center gap-4 text-sm">
            {confidence !== undefined && (
              <div className="flex items-center gap-1">
                <CheckCircle2 className={cn('h-4 w-4', confidenceColor)} />
                <span className={confidenceColor}>
                  {Math.round(confidence * 100)}% confident
                </span>
              </div>
            )}
            {executionTime !== undefined && (
              <div className="flex items-center gap-1 text-muted-foreground">
                <Clock className="h-4 w-4" />
                <span>{executionTime}ms</span>
              </div>
            )}
          </div>
        </div>
        {summary && <CardDescription className="mt-2">{summary}</CardDescription>}
      </CardHeader>
      {children && <CardContent className="pt-0">{children}</CardContent>}
    </Card>
  );
}
