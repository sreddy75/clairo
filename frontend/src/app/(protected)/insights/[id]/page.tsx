'use client';

/**
 * Insight Detail Page with A2UI Integration
 *
 * Displays an individual insight using the A2UI renderer for dynamic,
 * context-aware presentation based on insight severity and type.
 */

import { ArrowLeft, Loader2, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useDeviceContext } from '@/hooks/useDeviceContext';
import { A2UIRenderer } from '@/lib/a2ui';
import type { A2UIMessage } from '@/lib/a2ui/types';
import { apiClient } from '@/lib/api-client';


// =============================================================================
// Types
// =============================================================================

interface InsightDetail {
  id: string;
  title: string;
  category: string;
  priority: string;
  status: string;
  created_at: string;
}

// =============================================================================
// Component
// =============================================================================

export default function InsightDetailPage() {
  const params = useParams();
  const router = useRouter();
  const insightId = params.id as string;
  const deviceContext = useDeviceContext();

  const [insight, setInsight] = useState<InsightDetail | null>(null);
  const [a2uiMessage, setA2uiMessage] = useState<A2UIMessage | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInsightUI = useCallback(async () => {
    if (!insightId) return;

    setIsLoading(true);
    setError(null);

    try {
      // Fetch insight details and A2UI message in parallel
      const [insightResponse, a2uiResponse] = await Promise.all([
        apiClient.get<InsightDetail>(`/api/v1/insights/${insightId}`),
        apiClient.get<A2UIMessage>(`/api/v1/insights/${insightId}/ui`, {
          headers: {
            'X-Device-Type': deviceContext.isMobile
              ? 'mobile'
              : deviceContext.isTablet
                ? 'tablet'
                : 'desktop',
          },
        }),
      ]);

      setInsight(insightResponse.data ?? null);
      setA2uiMessage(a2uiResponse.data ?? null);
    } catch (err) {
      console.error('Failed to fetch insight:', err);
      setError('Failed to load insight. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [insightId, deviceContext.isMobile, deviceContext.isTablet]);

  useEffect(() => {
    fetchInsightUI();
  }, [fetchInsightUI]);

  // Handle A2UI actions - individual handlers for each action type
  const handleNavigate = useCallback(
    (target: string) => {
      router.push(target);
    },
    [router]
  );

  const handleCreateTask = useCallback(
    async (payload: Record<string, unknown>) => {
      try {
        const priority = (payload?.priority as string) || 'medium';
        await apiClient.post(`/api/v1/insights/${insightId}/convert-to-action-item`, {
          body: JSON.stringify({ priority }),
        });
        router.push('/action-items');
      } catch (err) {
        console.error('Failed to create task:', err);
      }
    },
    [insightId, router]
  );

  const handleCustomAction = useCallback(
    async (payload: Record<string, unknown>) => {
      // Handle dismiss action
      if (payload?.action === 'dismiss') {
        try {
          await apiClient.post(`/api/v1/insights/${insightId}/dismiss`);
          router.push('/assistant');
        } catch (err) {
          console.error('Failed to dismiss insight:', err);
        }
        return;
      }
      console.log('Custom action:', payload);
    },
    [insightId, router]
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex items-center gap-3 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>Loading insight...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !a2uiMessage) {
    return (
      <div className="min-h-screen bg-background p-6">
        <Card className="max-w-2xl mx-auto">
          <CardHeader>
            <CardTitle className="text-destructive">Error</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-muted-foreground">{error || 'Insight not found'}</p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => router.back()}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Go Back
              </Button>
              <Button onClick={fetchInsightUI}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b border-border sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link
                href="/assistant"
                className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                <span className="text-sm font-medium">Back to Assistant</span>
              </Link>
              {insight && (
                <div className="hidden sm:block">
                  <span className="text-border mx-2">|</span>
                  <span className="text-sm text-muted-foreground">{insight.category}</span>
                </div>
              )}
            </div>
            <Button variant="ghost" size="sm" onClick={fetchInsightUI}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content - A2UI Rendered */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <A2UIRenderer
          message={a2uiMessage}
          actionHandlers={{
            navigate: handleNavigate,
            createTask: handleCreateTask,
            custom: handleCustomAction,
          }}
          className="space-y-6"
        />
      </main>
    </div>
  );
}
