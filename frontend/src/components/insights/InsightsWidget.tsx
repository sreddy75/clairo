'use client';

/**
 * Insights Widget for Dashboard
 *
 * Displays a client-grouped summary of insights:
 * - Count of clients needing attention
 * - List of clients with issue counts and priority indicators
 * - Click to navigate to client's Insights tab
 */

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  ArrowRight,
  Building2,
  CheckCircle2,
  Lightbulb,
  Loader2,
} from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui/card';
import { getInsightDashboard } from '@/lib/api/insights';
import { cn } from '@/lib/utils';
import type { Insight, InsightDashboardResponse } from '@/types/insights';

interface ClientInsightSummary {
  clientId: string;
  clientName: string;
  highCount: number;
  mediumCount: number;
  lowCount: number;
  totalCount: number;
  highestPriority: 'high' | 'medium' | 'low';
  topIssues: string[];
}

function groupInsightsByClient(insights: Insight[]): ClientInsightSummary[] {
  const clientMap = new Map<string, ClientInsightSummary>();

  for (const insight of insights) {
    if (!insight.client_id || !insight.client_name) continue;

    let summary = clientMap.get(insight.client_id);
    if (!summary) {
      summary = {
        clientId: insight.client_id,
        clientName: insight.client_name,
        highCount: 0,
        mediumCount: 0,
        lowCount: 0,
        totalCount: 0,
        highestPriority: 'low',
        topIssues: [],
      };
      clientMap.set(insight.client_id, summary);
    }

    summary.totalCount++;
    if (insight.priority === 'high') {
      summary.highCount++;
      summary.highestPriority = 'high';
    } else if (insight.priority === 'medium') {
      summary.mediumCount++;
      if (summary.highestPriority !== 'high') {
        summary.highestPriority = 'medium';
      }
    } else {
      summary.lowCount++;
    }

    if (summary.topIssues.length < 2) {
      summary.topIssues.push(insight.title);
    }
  }

  return Array.from(clientMap.values()).sort((a, b) => {
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    if (priorityOrder[a.highestPriority] !== priorityOrder[b.highestPriority]) {
      return priorityOrder[a.highestPriority] - priorityOrder[b.highestPriority];
    }
    return b.totalCount - a.totalCount;
  });
}

const PRIORITY_DOT: Record<string, string> = {
  high: 'bg-status-danger',
  medium: 'bg-status-warning',
  low: 'bg-status-info',
};

function ClientCard({ summary }: { summary: ClientInsightSummary }) {
  return (
    <Link
      href={`/clients/${summary.clientId}?tab=insights`}
      className="flex items-center gap-3 rounded-lg border border-border/50 p-3 transition-colors hover:bg-muted/50"
    >
      <span className={cn('mt-0.5 h-2 w-2 flex-shrink-0 rounded-full', PRIORITY_DOT[summary.highestPriority])} />
      <Building2 className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate">{summary.clientName}</span>
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            {summary.totalCount}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
          {summary.topIssues.join(' · ')}
        </p>
      </div>
      <ArrowRight className="h-4 w-4 flex-shrink-0 text-muted-foreground/50" />
    </Link>
  );
}

export function InsightsWidget() {
  const { getToken } = useAuth();
  const [data, setData] = useState<InsightDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const token = await getToken();
      if (!token) return;

      const response = await getInsightDashboard(token, 20);
      setData(response);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load insights');
    } finally {
      setIsLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (isLoading) {
    return (
      <Card className="border-0 shadow-sm">
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-0 shadow-sm">
        <CardContent className="py-8 text-center">
          <AlertCircle className="mx-auto h-8 w-8 text-muted-foreground/30" />
          <p className="mt-2 text-sm text-muted-foreground">{error}</p>
          <Button variant="link" size="sm" className="mt-1" onClick={fetchData}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  const clientSummaries = data ? groupInsightsByClient(data.top_insights) : [];
  const clientsNeedingAttention = clientSummaries.filter(c => c.highestPriority === 'high' || c.highestPriority === 'medium').length;
  const highPriorityCount = data?.stats.by_priority?.high || 0;

  return (
    <Card className="border-0 shadow-sm overflow-hidden">
      {/* Header */}
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-status-warning" />
          <h3 className="text-sm font-semibold">Attention Needed</h3>
          {clientsNeedingAttention > 0 && (
            <Badge variant="secondary" className="text-[10px] font-medium text-status-danger">
              {clientsNeedingAttention} client{clientsNeedingAttention !== 1 ? 's' : ''}
            </Badge>
          )}
        </div>
        <Button variant="link" size="sm" className="h-auto p-0 text-xs" asChild>
          <Link href="/assistant">
            AI Assistant
            <ArrowRight className="ml-1 h-3 w-3" />
          </Link>
        </Button>
      </CardHeader>

      {/* Summary Stats */}
      {data && data.stats.total > 0 && (
        <div className="flex items-center gap-4 border-t px-6 py-2 text-xs text-muted-foreground">
          <span>
            <strong className="font-semibold text-foreground">{data.stats.total}</strong> insights across{' '}
            <strong className="font-semibold text-foreground">{clientSummaries.length}</strong> client{clientSummaries.length !== 1 ? 's' : ''}
          </span>
          {highPriorityCount > 0 && (
            <span className="text-status-danger">
              <strong className="font-semibold">{highPriorityCount}</strong> high priority
            </span>
          )}
        </div>
      )}

      {/* Client List */}
      <CardContent className="pt-3">
        {clientSummaries.length > 0 ? (
          <div className="space-y-2">
            {clientSummaries.slice(0, 5).map((summary) => (
              <ClientCard key={summary.clientId} summary={summary} />
            ))}
            {clientSummaries.length > 5 && (
              <p className="pt-2 text-center text-xs text-muted-foreground">
                +{clientSummaries.length - 5} more clients with insights
              </p>
            )}
          </div>
        ) : (
          <div className="py-8 text-center">
            <CheckCircle2 className="mx-auto h-8 w-8 text-status-success/50" />
            <p className="mt-2 font-medium">All clear!</p>
            <p className="mt-1 text-sm text-muted-foreground">No clients require attention</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default InsightsWidget;
