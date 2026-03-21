'use client';

/**
 * Feedback List Page
 *
 * Dual-view (kanban + table) for managing voice-powered feedback submissions.
 * Status filter tabs, stats bar, and view toggle.
 */

import { useAuth } from '@clerk/nextjs';
import { Plus, LayoutGrid, List, MessageSquare, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { KanbanBoard } from '@/components/feedback/KanbanBoard';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { listSubmissions, updateStatus, getStats } from '@/lib/api/feedback';
import { formatRelativeTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type {
  FeedbackSubmission,
  SubmissionStatus,
  FeedbackStats,
} from '@/types/feedback';

// ─── Status Config ──────────────────────────────────────────────────────────

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'new', label: 'New' },
  { value: 'in_review', label: 'In Review' },
  { value: 'planned', label: 'Planned' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'done', label: 'Done' },
] as const;

const STATUS_DOT_COLORS: Record<SubmissionStatus, string> = {
  draft: 'bg-stone-400',
  new: 'bg-blue-500',
  in_review: 'bg-amber-500',
  planned: 'bg-violet-500',
  in_progress: 'bg-emerald-500',
  done: 'bg-stone-400',
};

const STATUS_LABELS: Record<SubmissionStatus, string> = {
  draft: 'Draft',
  new: 'New',
  in_review: 'In Review',
  planned: 'Planned',
  in_progress: 'In Progress',
  done: 'Done',
};

// ─── Component ──────────────────────────────────────────────────────────────

export default function FeedbackPage() {
  const { getToken } = useAuth();
  const [submissions, setSubmissions] = useState<FeedbackSubmission[]>([]);
  const [stats, setStats] = useState<FeedbackStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [view, setView] = useState<'kanban' | 'list'>('kanban');

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const token = await getToken();
      if (!token) {
        setError('Not authenticated');
        return;
      }

      const [submissionRes, statsRes] = await Promise.all([
        listSubmissions(token, {
          status: statusFilter
            ? (statusFilter as SubmissionStatus)
            : undefined,
          limit: 100,
        }),
        getStats(token),
      ]);

      setSubmissions(submissionRes.items);
      setStats(statsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load feedback');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, statusFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleStatusChange = async (id: string, newStatus: SubmissionStatus) => {
    try {
      const token = await getToken();
      if (!token) return;
      await updateStatus(token, id, newStatus);
      await fetchData();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to update status'
      );
    }
  };

  const handleSubmissionClick = (submission: FeedbackSubmission) => {
    // SubmissionDetail dialog will be added in Phase 5
    console.log('Clicked submission:', submission.id);
  };

  // ─── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Feedback</h1>
          <p className="text-sm text-muted-foreground">
            Voice-powered feedback from your team
          </p>
        </div>
        <Button asChild size="sm">
          <Link href="/feedback/new">
            <Plus className="mr-1.5 h-4 w-4" />
            New Submission
          </Link>
        </Button>
      </div>

      {/* Stats Bar */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {[
            { label: 'Total', value: stats.total },
            { label: 'New', value: stats.by_status.new ?? 0 },
            { label: 'In Review', value: stats.by_status.in_review ?? 0 },
            { label: 'Planned', value: stats.by_status.planned ?? 0 },
            { label: 'In Progress', value: stats.by_status.in_progress ?? 0 },
            { label: 'Done', value: stats.by_status.done ?? 0 },
          ].map((stat) => (
            <Card key={stat.label} className="shadow-sm">
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">{stat.label}</p>
                <p className="text-2xl font-semibold tabular-nums">
                  {stat.value}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Filter Tabs + View Toggle */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {/* Status Tabs */}
        <div className="flex gap-1">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setStatusFilter(tab.value)}
              className={cn(
                'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                statusFilter === tab.value
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* View Toggle */}
        <div className="flex gap-1">
          <Button
            variant={view === 'kanban' ? 'default' : 'ghost'}
            size="icon"
            className="h-8 w-8"
            onClick={() => setView('kanban')}
          >
            <LayoutGrid className="h-4 w-4" />
          </Button>
          <Button
            variant={view === 'list' ? 'default' : 'ghost'}
            size="icon"
            className="h-8 w-8"
            onClick={() => setView('list')}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">
            Loading...
          </span>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && submissions.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <MessageSquare className="mb-3 h-10 w-10 text-muted-foreground/50" />
          <p className="text-sm font-medium text-muted-foreground">
            No feedback yet
          </p>
          <Link
            href="/feedback/new"
            className="mt-2 text-sm text-primary hover:underline"
          >
            Create your first submission
          </Link>
        </div>
      )}

      {/* Content Views */}
      {!isLoading && !error && submissions.length > 0 && (
        <>
          {view === 'kanban' ? (
            <KanbanBoard
              submissions={submissions}
              onStatusChange={handleStatusChange}
              onCardClick={handleSubmissionClick}
            />
          ) : (
            <Card className="shadow-sm">
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="px-4">Title</TableHead>
                      <TableHead className="px-4">Type</TableHead>
                      <TableHead className="px-4">Status</TableHead>
                      <TableHead className="px-4">Submitter</TableHead>
                      <TableHead className="px-4">Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {submissions.map((submission) => (
                      <TableRow
                        key={submission.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => handleSubmissionClick(submission)}
                      >
                        <TableCell className="px-4 font-medium">
                          <span className="line-clamp-1">
                            {submission.title ?? 'Untitled'}
                          </span>
                        </TableCell>
                        <TableCell className="px-4">
                          <Badge
                            variant={
                              submission.type === 'feature_request'
                                ? 'default'
                                : 'secondary'
                            }
                            className={cn(
                              'text-xs',
                              submission.type === 'feature_request'
                                ? 'bg-primary/10 text-primary hover:bg-primary/20'
                                : 'bg-blue-500/10 text-blue-600 hover:bg-blue-500/20'
                            )}
                          >
                            {submission.type === 'feature_request'
                              ? 'Feature'
                              : 'Bug'}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-4">
                          <div className="flex items-center gap-2">
                            <span
                              className={cn(
                                'inline-block h-2 w-2 rounded-full',
                                STATUS_DOT_COLORS[submission.status]
                              )}
                            />
                            <span className="text-sm">
                              {STATUS_LABELS[submission.status]}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="px-4 text-muted-foreground">
                          {submission.submitter_name}
                        </TableCell>
                        <TableCell className="px-4 text-muted-foreground">
                          {formatRelativeTime(submission.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
