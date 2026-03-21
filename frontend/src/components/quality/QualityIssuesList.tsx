'use client';

import {
  AlertOctagon,
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronDown,
  ChevronRight,
  X,
  CheckCircle,
} from 'lucide-react';
import { useState } from 'react';

import {
  type QualityIssue,
  type IssueSeverity,
  getSeverityColor,
} from '@/lib/quality';
import { cn } from '@/lib/utils';

interface QualityIssuesListProps {
  issues: QualityIssue[];
  isLoading?: boolean;
  onDismiss?: (issueId: string, reason: string) => void;
  isDismissing?: string | null;
  showDismissed?: boolean;
  onToggleDismissed?: (show: boolean) => void;
  className?: string;
}

const severityIcons: Record<IssueSeverity, typeof AlertOctagon> = {
  critical: AlertOctagon,
  error: AlertTriangle,
  warning: AlertCircle,
  info: Info,
};

const severityLabels: Record<IssueSeverity, string> = {
  critical: 'Critical',
  error: 'Error',
  warning: 'Warning',
  info: 'Info',
};

/**
 * Quality issues list component.
 * Displays quality issues with expandable details and dismiss functionality.
 */
export function QualityIssuesList({
  issues,
  isLoading = false,
  onDismiss,
  isDismissing,
  showDismissed = false,
  onToggleDismissed,
  className,
}: QualityIssuesListProps) {
  const [expandedIssues, setExpandedIssues] = useState<Set<string>>(new Set());
  const [dismissReason, setDismissReason] = useState<string>('');
  const [dismissingIssueId, setDismissingIssueId] = useState<string | null>(null);

  const toggleExpanded = (issueId: string) => {
    setExpandedIssues((prev) => {
      const next = new Set(prev);
      if (next.has(issueId)) {
        next.delete(issueId);
      } else {
        next.add(issueId);
      }
      return next;
    });
  };

  const handleDismissClick = (issueId: string) => {
    setDismissingIssueId(issueId);
    setDismissReason('');
  };

  const handleDismissConfirm = () => {
    if (dismissingIssueId && dismissReason.trim() && onDismiss) {
      onDismiss(dismissingIssueId, dismissReason.trim());
      setDismissingIssueId(null);
      setDismissReason('');
    }
  };

  const handleDismissCancel = () => {
    setDismissingIssueId(null);
    setDismissReason('');
  };

  if (isLoading) {
    return (
      <div className={cn('rounded-lg border border-border bg-card p-6', className)}>
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-32 bg-muted rounded" />
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-muted rounded" />
          ))}
        </div>
      </div>
    );
  }

  const activeIssues = issues.filter((i) => !i.dismissed);
  const dismissedIssues = issues.filter((i) => i.dismissed);
  const displayedIssues = showDismissed ? issues : activeIssues;

  return (
    <div className={cn('rounded-lg border border-border bg-card', className)}>
      {/* Header */}
      <div className="border-b border-border px-6 py-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">
          Quality Issues
          {activeIssues.length > 0 && (
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              ({activeIssues.length} active)
            </span>
          )}
        </h3>
        {onToggleDismissed && dismissedIssues.length > 0 && (
          <button
            onClick={() => onToggleDismissed(!showDismissed)}
            className="text-sm text-primary hover:text-primary/80"
          >
            {showDismissed
              ? 'Hide dismissed'
              : `Show dismissed (${dismissedIssues.length})`}
          </button>
        )}
      </div>

      {/* Issues List */}
      <div className="divide-y divide-border">
        {displayedIssues.length === 0 ? (
          <div className="px-6 py-8 text-center">
            <CheckCircle className="mx-auto h-12 w-12 text-status-success" />
            <h4 className="mt-4 text-lg font-medium text-foreground">
              No Issues Found
            </h4>
            <p className="mt-2 text-sm text-muted-foreground">
              All quality checks passed for this quarter.
            </p>
          </div>
        ) : (
          displayedIssues.map((issue) => {
            const Icon = severityIcons[issue.severity];
            const isExpanded = expandedIssues.has(issue.id);
            const isBeingDismissed = dismissingIssueId === issue.id;

            return (
              <div
                key={issue.id}
                className={cn(
                  'px-6 py-4',
                  issue.dismissed && 'bg-muted opacity-60'
                )}
              >
                {/* Issue Header */}
                <div
                  className="flex items-start gap-3 cursor-pointer"
                  onClick={() => toggleExpanded(issue.id)}
                >
                  <Icon
                    className={cn(
                      'h-5 w-5 mt-0.5 flex-shrink-0',
                      issue.severity === 'critical' && 'text-status-danger',
                      issue.severity === 'error' && 'text-status-danger',
                      issue.severity === 'warning' && 'text-status-warning',
                      issue.severity === 'info' && 'text-primary'
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">
                        {issue.title}
                      </span>
                      <span
                        className={cn(
                          'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                          getSeverityColor(issue.severity)
                        )}
                      >
                        {severityLabels[issue.severity]}
                      </span>
                      {issue.dismissed && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground">
                          Dismissed
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                      {issue.description}
                    </p>
                  </div>
                  <div className="flex-shrink-0">
                    {isExpanded ? (
                      <ChevronDown className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="mt-4 ml-8 space-y-4">
                    {/* Affected Items */}
                    {issue.affected_count > 0 && (
                      <div>
                        <span className="text-sm font-medium text-foreground">
                          Affected:{' '}
                        </span>
                        <span className="text-sm text-muted-foreground">
                          {issue.affected_count}{' '}
                          {issue.affected_entity_type || 'items'}
                        </span>
                      </div>
                    )}

                    {/* Suggested Action */}
                    {issue.suggested_action && (
                      <div className="bg-primary/10 rounded-lg p-3">
                        <span className="text-sm font-medium text-primary">
                          Suggested Action:{' '}
                        </span>
                        <span className="text-sm text-primary">
                          {issue.suggested_action}
                        </span>
                      </div>
                    )}

                    {/* Timestamps */}
                    <div className="text-xs text-muted-foreground flex flex-wrap gap-4">
                      <span>
                        First detected:{' '}
                        {new Date(issue.first_detected_at).toLocaleString()}
                      </span>
                      <span>
                        Last seen:{' '}
                        {new Date(issue.last_seen_at).toLocaleString()}
                      </span>
                    </div>

                    {/* Dismissed Info */}
                    {issue.dismissed && issue.dismissed_at && (
                      <div className="text-xs text-muted-foreground">
                        Dismissed:{' '}
                        {new Date(issue.dismissed_at).toLocaleString()}
                        {issue.dismissed_reason && (
                          <span> - &ldquo;{issue.dismissed_reason}&rdquo;</span>
                        )}
                      </div>
                    )}

                    {/* Dismiss Action */}
                    {!issue.dismissed && onDismiss && (
                      <div className="pt-2">
                        {isBeingDismissed ? (
                          <div className="space-y-2">
                            <textarea
                              value={dismissReason}
                              onChange={(e) => setDismissReason(e.target.value)}
                              placeholder="Reason for dismissing this issue..."
                              className="w-full px-3 py-2 border border-border rounded-md text-sm bg-card text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                              rows={2}
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={handleDismissConfirm}
                                disabled={
                                  !dismissReason.trim() ||
                                  isDismissing === issue.id
                                }
                                className="px-3 py-1 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                              >
                                {isDismissing === issue.id
                                  ? 'Dismissing...'
                                  : 'Confirm'}
                              </button>
                              <button
                                onClick={handleDismissCancel}
                                className="px-3 py-1 text-sm text-muted-foreground hover:text-foreground"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDismissClick(issue.id);
                            }}
                            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
                          >
                            <X className="h-4 w-4 mr-1" />
                            Dismiss issue
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default QualityIssuesList;
