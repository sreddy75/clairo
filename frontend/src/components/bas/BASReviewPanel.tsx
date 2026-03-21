'use client';

/**
 * BAS Review Panel with A2UI
 *
 * Exception-focused BAS review using A2UI components.
 * Shows anomalies expanded, normal fields collapsed.
 */

import {
  AlertCircle,
  ArrowLeft,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { A2UIRenderer } from '@/lib/a2ui/renderer';
import type { A2UIMessage, A2UIActionHandlers } from '@/lib/a2ui/types';

// =============================================================================
// Types
// =============================================================================

interface BASReviewPanelProps {
  connectionId: string;
  sessionId: string;
  getToken: () => Promise<string | null>;
  onBack?: () => void;
}

interface ReviewUIResponse {
  session_id: string;
  a2ui_message: A2UIMessage;
}

// =============================================================================
// Component
// =============================================================================

export function BASReviewPanel({
  connectionId,
  sessionId,
  getToken,
  onBack,
}: BASReviewPanelProps) {
  const router = useRouter();
  const [a2uiMessage, setA2UIMessage] = useState<A2UIMessage | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch review UI from backend
  const fetchReviewUI = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const token = await getToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(
        `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/review/ui`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to load review');
      }

      const data: ReviewUIResponse = await response.json();
      setA2UIMessage(data.a2ui_message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load BAS review');
    } finally {
      setIsLoading(false);
    }
  }, [connectionId, sessionId, getToken]);

  useEffect(() => {
    fetchReviewUI();
  }, [fetchReviewUI]);

  // A2UI action handlers
  const actionHandlers: A2UIActionHandlers = {
    navigate: (target) => router.push(target),
    approve: async (resourceId) => {
      try {
        const token = await getToken();
        if (!token) throw new Error('Not authenticated');

        await fetch(
          `/api/v1/clients/${connectionId}/bas/sessions/${resourceId}/approve`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({}),
          }
        );

        // Refresh the UI after approval
        await fetchReviewUI();
      } catch (err) {
        console.error('Failed to approve:', err);
      }
    },
    export: async (format, _dataBinding) => {
      try {
        const token = await getToken();
        if (!token) throw new Error('Not authenticated');

        const response = await fetch(
          `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/export?format=${format}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (response.ok) {
          const blob = await response.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `bas-working-papers.${format}`;
          a.click();
          window.URL.revokeObjectURL(url);
        }
      } catch (err) {
        console.error('Failed to export:', err);
      }
    },
    createTask: async (payload) => {
      console.log('Create task:', payload);
    },
    custom: async (payload) => {
      console.log('Custom action:', payload);
    },
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-24" />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-32" />
        <Skeleton className="h-48" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="h-10 w-10 text-red-400 mb-4" />
          <h3 className="text-lg font-medium text-red-900 mb-2">Failed to Load Review</h3>
          <p className="text-sm text-red-600 mb-4">{error}</p>
          <Button onClick={fetchReviewUI} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {onBack && (
            <Button variant="ghost" size="icon" onClick={onBack}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
          )}
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <h2 className="text-xl font-semibold text-foreground">
                Exception-Focused Review
              </h2>
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              Anomalies are highlighted. Normal fields are collapsed.
            </p>
          </div>
        </div>
        <Button variant="outline" onClick={fetchReviewUI}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* A2UI Content */}
      {a2uiMessage && (
        <A2UIRenderer
          message={a2uiMessage}
          actionHandlers={actionHandlers}
          className="rounded-lg"
          enablePerfLogging={false}
        />
      )}

      {/* Empty state */}
      {!a2uiMessage && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-10 w-10 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No review data available</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default BASReviewPanel;
