'use client';

/**
 * Dashboard A2UI Component
 *
 * Displays personalized, context-aware dashboard content using A2UI.
 * Adapts based on time of day, urgency, and workload.
 */

import { useAuth } from '@clerk/nextjs';
import { Loader2, RefreshCw } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { useDeviceContext } from '@/hooks/useDeviceContext';
import { A2UIRenderer } from '@/lib/a2ui';
import type { A2UIMessage } from '@/lib/a2ui/types';
import { apiClient } from '@/lib/api-client';


// =============================================================================
// Types
// =============================================================================

interface DashboardA2UIProps {
  quarter?: number;
  fyYear?: number;
  className?: string;
  demo?: boolean;
}

// =============================================================================
// Component
// =============================================================================

export function DashboardA2UI({ quarter, fyYear, className, demo: demoProp }: DashboardA2UIProps) {
  const { getToken } = useAuth();
  const searchParams = useSearchParams();
  const deviceContext = useDeviceContext();
  const [a2uiMessage, setA2uiMessage] = useState<A2UIMessage | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check for demo mode from URL or prop
  const isDemo = demoProp || searchParams.get('demo') === 'true';

  const fetchDashboardUI = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) {
        setError('Not authenticated');
        return;
      }

      const params = new URLSearchParams();
      if (quarter) params.set('quarter', quarter.toString());
      if (fyYear) params.set('fy_year', fyYear.toString());
      if (isDemo) params.set('demo', 'true');

      const response = await apiClient.get<A2UIMessage>(
        `/api/v1/dashboard/ui${params.toString() ? `?${params.toString()}` : ''}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'X-Device-Type': deviceContext.isMobile
              ? 'mobile'
              : deviceContext.isTablet
                ? 'tablet'
                : 'desktop',
          },
        }
      );

      // Parse the response as JSON
      if (response.ok) {
        const data = await response.json();
        setA2uiMessage(data);
      } else {
        throw new Error(`API error: ${response.status}`);
      }
    } catch (err) {
      console.error('Failed to fetch dashboard UI:', err);
      setError('Failed to load personalized dashboard');
    } finally {
      setIsLoading(false);
    }
  }, [quarter, fyYear, deviceContext.isMobile, deviceContext.isTablet, getToken, isDemo]);

  useEffect(() => {
    fetchDashboardUI();
  }, [fetchDashboardUI]);

  // Handle A2UI navigate action
  const handleNavigate = useCallback((target: string) => {
    window.location.href = target;
  }, []);

  // Handle A2UI custom action
  const handleCustomAction = useCallback(
    async (payload: Record<string, unknown>) => {
      if (payload?.action === 'generate_insights') {
        // Trigger insight generation
        try {
          const token = await getToken();
          if (token) {
            await apiClient.post('/api/v1/insights/generate', {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            });
            // Refresh the dashboard UI
            fetchDashboardUI();
          }
        } catch (err) {
          console.error('Failed to generate insights:', err);
        }
      } else {
        console.log('Custom action:', payload);
      }
    },
    [fetchDashboardUI, getToken]
  );

  // Loading state
  if (isLoading) {
    return (
      <div className={`flex items-center justify-center py-8 ${className || ''}`}>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Loading personalized view...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !a2uiMessage) {
    return (
      <div className={`flex items-center justify-between py-4 px-4 bg-muted/50 rounded-lg ${className || ''}`}>
        <span className="text-sm text-muted-foreground">{error || 'Unable to load'}</span>
        <Button variant="ghost" size="sm" onClick={fetchDashboardUI}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-stone-900">
          {isDemo ? 'A2UI Component Demo' : 'Your Focus Today'}
        </h2>
        <Button variant="ghost" size="sm" onClick={fetchDashboardUI}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>
      <A2UIRenderer
        message={a2uiMessage}
        actionHandlers={{
          navigate: handleNavigate,
          custom: handleCustomAction,
        }}
        className="space-y-4"
      />
    </div>
  );
}
