'use client';

/**
 * InsightDetailPanel
 *
 * Full-width dialog for viewing AI-generated insight analysis.
 * Uses a two-zone layout: narrow metadata rail + spacious content area.
 * Replaces the previous narrow Sheet sidebar.
 */

import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Cpu,
  ListPlus,
  Loader2,
  Sparkles,
  X,
} from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import type { Insight } from '@/types/insights';

import { ConfidenceBreakdown } from './ConfidenceBreakdown';
import { DataFreshnessIndicator } from './DataFreshnessIndicator';
import { OptionsDisplay } from './OptionsDisplay';

interface InsightDetailPanelProps {
  insight: Insight | null;
  onClose: () => void;
  onAction: (insightId: string, action: 'view' | 'action' | 'dismiss') => void;
  onConvert: (insight: Insight) => void;
  onExpand: (insightId: string) => void;
  isExpanding: boolean;
}

const PRIORITY_CONFIG = {
  high: {
    accent: 'bg-status-danger',
    badge: 'bg-status-danger/10 text-status-danger ring-1 ring-status-danger/20',
    label: 'Urgent',
  },
  medium: {
    accent: 'bg-status-warning',
    badge: 'bg-status-warning/10 text-status-warning ring-1 ring-status-warning/20',
    label: 'Review',
  },
  low: {
    accent: 'bg-primary',
    badge: 'bg-primary/10 text-primary ring-1 ring-primary/20',
    label: 'Info',
  },
} as const;

const CATEGORY_LABELS: Record<string, string> = {
  compliance: 'Compliance',
  quality: 'Data Quality',
  cash_flow: 'Cash Flow',
  tax: 'Tax',
  strategic: 'Strategic',
};

function formatDeadline(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-AU', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

function formatGeneratedDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function InsightDetailPanel({
  insight,
  onClose,
  onAction,
  onConvert,
  onExpand,
  isExpanding,
}: InsightDetailPanelProps) {
  if (!insight) return null;

  const priority = PRIORITY_CONFIG[insight.priority] || PRIORITY_CONFIG.medium;
  const isActioned = insight.status === 'actioned';
  const isMagicZone = insight.generation_type === 'magic_zone';
  const categoryLabel = CATEGORY_LABELS[insight.category] || insight.category.replace('_', ' ');

  return (
    <Dialog open={!!insight} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className={cn(
          'max-w-4xl w-[95vw] p-0 gap-0 overflow-hidden',
          'bg-card border-border',
          'max-h-[90vh] flex flex-col',
          '[&>button:last-child]:hidden', // Hide default close button — we render our own
        )}
      >
        {/* Priority accent bar */}
        <div className={cn('h-1 w-full shrink-0', priority.accent)} />

        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-border shrink-0">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              {/* Badge row */}
              <div className="flex items-center gap-2 flex-wrap mb-2.5">
                <span className={cn('px-2.5 py-0.5 rounded-md text-xs font-semibold', priority.badge)}>
                  {priority.label}
                </span>
                <span className="px-2.5 py-0.5 rounded-md text-xs font-medium bg-muted text-muted-foreground">
                  {categoryLabel}
                </span>
                {isMagicZone && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-medium bg-accent/10 text-accent-foreground">
                    <Sparkles className="w-3 h-3" />
                    Deep Analysis
                  </span>
                )}
                {insight.status === 'new' && (
                  <span className="w-2 h-2 rounded-full bg-primary animate-pulse" title="New insight" />
                )}
                {isActioned && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-medium bg-status-success/10 text-status-success">
                    <CheckCircle2 className="w-3 h-3" />
                    Actioned
                  </span>
                )}
              </div>

              {/* Title — hidden DialogTitle for accessibility, visible custom title */}
              <DialogTitle className="sr-only">{insight.title}</DialogTitle>
              <h2 className="text-xl font-semibold text-foreground leading-tight tracking-tight">
                {insight.title}
              </h2>

              {/* Subtitle metadata */}
              {insight.client_name && (
                <p className="mt-1 text-sm text-muted-foreground">
                  {insight.client_name}
                </p>
              )}
            </div>

            {/* Close button */}
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="flex flex-col lg:flex-row">

            {/* Metadata rail */}
            <aside className="lg:w-64 shrink-0 border-b lg:border-b-0 lg:border-r border-border p-5 space-y-4 bg-muted/50">

              {/* Confidence */}
              {insight.confidence != null && insight.confidence > 0 && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                    Confidence
                  </p>
                  <ConfidenceBreakdown
                    confidence={insight.confidence}
                    breakdown={insight.data_snapshot?.confidence_breakdown}
                  />
                </div>
              )}

              {/* Data Freshness */}
              {insight.data_snapshot?.data_freshness && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                    Data Source
                  </p>
                  <DataFreshnessIndicator lastSyncDate={insight.data_snapshot.data_freshness} />
                </div>
              )}

              {/* Deadline */}
              {insight.action_deadline && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                    Deadline
                  </p>
                  <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-status-danger/10 border border-status-danger/20">
                    <AlertTriangle className="w-3.5 h-3.5 text-status-danger shrink-0" />
                    <span className="text-xs font-medium text-status-danger">
                      {formatDeadline(insight.action_deadline)}
                    </span>
                  </div>
                </div>
              )}

              {/* Analysis info */}
              {insight.agents_used && insight.agents_used.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                    Perspectives
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {insight.agents_used.map((agent) => (
                      <span
                        key={agent}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-muted text-muted-foreground"
                      >
                        <Cpu className="w-2.5 h-2.5" />
                        {agent.charAt(0).toUpperCase() + agent.slice(1)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Generated timestamp */}
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                  Generated
                </p>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Calendar className="w-3 h-3" />
                  {formatGeneratedDate(insight.generated_at)}
                </div>
              </div>

              {/* Suggested actions — in sidebar for clean separation */}
              {insight.suggested_actions && insight.suggested_actions.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                    Quick Actions
                  </p>
                  <div className="space-y-1.5">
                    {insight.suggested_actions.map((action, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          onConvert({
                            ...insight,
                            title: action.label,
                            summary: `Action from insight: ${insight.title}`,
                          });
                        }}
                        className="w-full text-left px-2.5 py-2 text-xs font-medium rounded-lg bg-card border border-border text-foreground hover:border-primary/30 hover:text-primary transition-colors flex items-center gap-2"
                        title="Click to create task"
                      >
                        <ListPlus className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
                        <span className="truncate">{action.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </aside>

            {/* Main content area */}
            <main className="flex-1 min-w-0 p-6">
              {/* Summary */}
              <p className="text-[15px] leading-relaxed text-foreground">
                {insight.summary}
              </p>

              {/* Detail / Options — the rich content */}
              {insight.detail && (
                <div className="mt-6">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="h-px flex-1 bg-border" />
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {isMagicZone ? 'Strategic Analysis' : 'Detail'}
                    </span>
                    <div className="h-px flex-1 bg-border" />
                  </div>
                  <div className="text-sm text-foreground">
                    <OptionsDisplay
                      content={insight.detail}
                      optionsCount={insight.options_count}
                      agentsUsed={insight.agents_used}
                      generationType={insight.generation_type}
                      dataSnapshot={insight.data_snapshot}
                    />
                  </div>
                </div>
              )}
            </main>
          </div>
        </div>

        {/* Sticky action bar */}
        <div className="shrink-0 border-t border-border bg-muted px-6 py-3">
          <div className="flex items-center justify-between">
            <button
              onClick={() => onAction(insight.id, 'dismiss')}
              className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Dismiss
            </button>

            {!isActioned ? (
              <div className="flex items-center gap-2">
                {!isMagicZone && (
                  <button
                    onClick={() => onExpand(insight.id)}
                    disabled={isExpanding}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-accent/30 text-accent-foreground bg-accent/10 hover:bg-accent/20 disabled:opacity-50 transition-colors"
                  >
                    {isExpanding ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Sparkles className="w-4 h-4" />
                    )}
                    {isExpanding ? 'Expanding...' : 'Expand Analysis'}
                  </button>
                )}
                <button
                  onClick={() => onConvert(insight)}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-border text-foreground bg-card hover:bg-muted transition-colors"
                >
                  <ListPlus className="w-4 h-4" />
                  Convert to Task
                </button>
                <button
                  onClick={() => {
                    onAction(insight.id, 'action');
                    onClose();
                  }}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg text-white bg-status-success hover:bg-status-success/90 transition-colors"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Mark as Actioned
                </button>
              </div>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-sm text-status-success">
                <CheckCircle2 className="w-4 h-4" />
                Already actioned
              </span>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
