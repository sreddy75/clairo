'use client';

/**
 * Day Summary Modal
 *
 * Displays an end-of-day summary with A2UI components.
 * Shows completed work, highlights, pending items, and tomorrow's priorities.
 */

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  Calendar,
  Loader2,
  Moon,
  RefreshCw,
  Sparkles,
  Sun,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { A2UIRenderer } from '@/lib/a2ui/renderer';
import type { A2UIMessage, A2UIActionHandlers } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

interface DaySummaryResponse {
  correlation_id: string;
  summary_date: string;
  text_summary: string;
  a2ui_message: A2UIMessage | null;
  metrics: {
    clients_worked: number;
    bas_completed: number;
    bas_submitted: number;
    time_saved_minutes: number;
  };
}

interface DaySummaryModalProps {
  isOpen: boolean;
  onClose: () => void;
  summaryDate?: string; // ISO date string, defaults to today
}

// =============================================================================
// Helper: Get greeting based on time of day
// =============================================================================

function getTimeGreeting(): { greeting: string; icon: React.ReactNode } {
  const hour = new Date().getHours();
  if (hour < 12) {
    return {
      greeting: 'Good morning',
      icon: <Sun className="h-5 w-5 text-amber-500" />,
    };
  } else if (hour < 17) {
    return {
      greeting: 'Good afternoon',
      icon: <Sun className="h-5 w-5 text-orange-500" />,
    };
  } else {
    return {
      greeting: 'Good evening',
      icon: <Moon className="h-5 w-5 text-indigo-500" />,
    };
  }
}

// =============================================================================
// Component
// =============================================================================

export function DaySummaryModal({
  isOpen,
  onClose,
  summaryDate,
}: DaySummaryModalProps) {
  const { getToken } = useAuth();
  const [summary, setSummary] = useState<DaySummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch day summary from backend
  const fetchSummary = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const token = await getToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const dateParam = summaryDate ? `?summary_date=${summaryDate}` : '';
      const response = await fetch(`/api/v1/productivity/day-summary/ui${dateParam}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to load summary');
      }

      const data: DaySummaryResponse = await response.json();
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load summary');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, summaryDate]);

  // Fetch on open
  useEffect(() => {
    if (isOpen) {
      fetchSummary();
    }
  }, [isOpen, fetchSummary]);

  // A2UI action handlers
  const actionHandlers: A2UIActionHandlers = {
    navigate: (target) => {
      window.location.href = target;
      onClose();
    },
    export: async (format, dataBinding) => {
      console.log('Export:', format, dataBinding);
      // TODO: Implement export functionality
    },
    createTask: async (payload) => {
      console.log('Create task:', payload);
    },
    custom: async (payload) => {
      console.log('Custom action:', payload);
    },
  };

  // Don't render if not open
  if (!isOpen) return null;

  const { greeting, icon } = getTimeGreeting();
  const displayDate = summaryDate
    ? new Date(summaryDate).toLocaleDateString('en-AU', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : new Date().toLocaleDateString('en-AU', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative flex max-h-[90vh] w-full sm:max-w-2xl flex-col rounded-2xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-blue-600">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                {icon}
                <h2 className="text-lg font-semibold text-foreground">
                  {greeting}!
                </h2>
              </div>
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Calendar className="h-3.5 w-3.5" />
                <span>{displayDate}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={fetchSummary}
              disabled={isLoading}
              className="h-8 w-8"
            >
              <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
            </Button>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-muted-foreground"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* Loading State */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="mt-3 text-sm text-muted-foreground">
                Generating your summary...
              </p>
            </div>
          )}

          {/* Error State */}
          {error && !isLoading && (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <AlertCircle className="h-6 w-6 text-status-danger" />
              </div>
              <h3 className="mt-3 text-sm font-medium text-foreground">
                Failed to Load Summary
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">{error}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={fetchSummary}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Try Again
              </Button>
            </div>
          )}

          {/* Summary Content */}
          {!isLoading && !error && summary && (
            <div className="space-y-4">
              {/* Quick Stats Bar */}
              {summary.metrics && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-xl bg-muted p-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-foreground">
                      {summary.metrics.clients_worked}
                    </div>
                    <div className="text-xs text-muted-foreground">Clients</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-foreground">
                      {summary.metrics.bas_completed}
                    </div>
                    <div className="text-xs text-muted-foreground">BAS Done</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-foreground">
                      {summary.metrics.bas_submitted}
                    </div>
                    <div className="text-xs text-muted-foreground">Submitted</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-primary">
                      {Math.floor(summary.metrics.time_saved_minutes / 60)}h{' '}
                      {summary.metrics.time_saved_minutes % 60}m
                    </div>
                    <div className="text-xs text-muted-foreground">Time Saved</div>
                  </div>
                </div>
              )}

              {/* A2UI Content */}
              {summary.a2ui_message && (
                <A2UIRenderer
                  message={summary.a2ui_message}
                  actionHandlers={actionHandlers}
                  className="rounded-lg"
                  enablePerfLogging={false}
                />
              )}

              {/* Fallback if no A2UI */}
              {!summary.a2ui_message && summary.text_summary && (
                <div className="rounded-xl bg-muted p-4">
                  <p className="text-sm text-foreground">{summary.text_summary}</p>
                </div>
              )}
            </div>
          )}

          {/* Empty State */}
          {!isLoading && !error && !summary && (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <Calendar className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="mt-3 text-sm font-medium text-foreground">
                No Summary Available
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                No activity recorded for this day.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-border px-6 py-3">
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Powered by Clairo AI
            </p>
            <Button variant="outline" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DaySummaryModal;
