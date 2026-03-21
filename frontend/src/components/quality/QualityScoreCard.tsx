'use client';

import { Info, RefreshCw, TrendingUp, AlertTriangle } from 'lucide-react';

import { ThresholdTooltip } from '@/components/insights/ThresholdTooltip';
import {
  type QualityScoreResponse,
  getQualityTier,
  getDimensionName,
  getDimensionDescription,
  getDimensionColor,
} from '@/lib/quality';
import { cn } from '@/lib/utils';

import { QualityBadge } from './QualityBadge';

interface QualityScoreCardProps {
  quality: QualityScoreResponse | null;
  isLoading?: boolean;
  onRecalculate?: () => void;
  isRecalculating?: boolean;
  className?: string;
}

/**
 * Quality score card with dimension breakdown.
 * Shows overall score and individual dimension scores.
 */
export function QualityScoreCard({
  quality,
  isLoading = false,
  onRecalculate,
  isRecalculating = false,
  className,
}: QualityScoreCardProps) {
  if (isLoading) {
    return (
      <div className={cn('rounded-lg border border-border bg-card p-6', className)}>
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-32 bg-muted rounded" />
          <div className="h-20 w-20 bg-muted rounded-full mx-auto" />
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-4 bg-muted rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!quality || !quality.has_score) {
    return (
      <div className={cn('rounded-lg border border-border bg-card p-6', className)}>
        <div className="text-center py-8">
          <TrendingUp className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-medium text-foreground">
            No Quality Score
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Quality scores are calculated after data is synced from Xero.
          </p>
          {onRecalculate && (
            <button
              onClick={onRecalculate}
              disabled={isRecalculating}
              className="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-primary-foreground bg-primary hover:bg-primary/90 disabled:opacity-50"
            >
              {isRecalculating ? (
                <>
                  <RefreshCw className="animate-spin -ml-1 mr-2 h-4 w-4" />
                  Calculating...
                </>
              ) : (
                'Calculate Score'
              )}
            </button>
          )}
        </div>
      </div>
    );
  }

  const tier = getQualityTier(quality.overall_score);
  const tierDescriptions = {
    good: 'Data quality is good. Ready for BAS preparation.',
    fair: 'Some issues need attention before lodging BAS.',
    poor: 'Significant data quality issues found.',
  };

  const dimensions = [
    { key: 'freshness', dim: quality.dimensions.freshness },
    { key: 'reconciliation', dim: quality.dimensions.reconciliation },
    { key: 'categorization', dim: quality.dimensions.categorization },
    { key: 'completeness', dim: quality.dimensions.completeness },
    ...(quality.dimensions.payg_readiness?.applicable
      ? [{ key: 'payg_readiness', dim: quality.dimensions.payg_readiness }]
      : []),
  ];

  const totalIssues =
    quality.issue_counts.critical +
    quality.issue_counts.error +
    quality.issue_counts.warning +
    quality.issue_counts.info;

  return (
    <div className={cn('rounded-lg border border-border bg-card', className)}>
      {/* Header */}
      <div className="border-b border-border px-6 py-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">Data Quality</h3>
        {onRecalculate && (
          <button
            onClick={onRecalculate}
            disabled={isRecalculating}
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground disabled:opacity-50"
            title="Recalculate quality score"
          >
            <RefreshCw
              className={cn('h-4 w-4', isRecalculating && 'animate-spin')}
            />
          </button>
        )}
      </div>

      {/* Overall Score */}
      <div className="px-6 py-6 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-4xl font-bold text-foreground">
              {Math.round(quality.overall_score)}%
            </div>
            <div className="mt-1">
              <ThresholdTooltip metricKey="quality_score">
                <QualityBadge score={quality.overall_score} showLabel />
              </ThresholdTooltip>
            </div>
          </div>

          {/* Circular Progress (visual indicator) */}
          <div className="relative w-20 h-20">
            <svg className="w-full h-full transform -rotate-90">
              <circle
                cx="40"
                cy="40"
                r="36"
                stroke="hsl(var(--muted))"
                strokeWidth="8"
                fill="none"
              />
              <circle
                cx="40"
                cy="40"
                r="36"
                stroke={
                  tier === 'good'
                    ? 'hsl(var(--status-success))'
                    : tier === 'fair'
                      ? 'hsl(var(--status-warning))'
                      : 'hsl(var(--status-danger))'
                }
                strokeWidth="8"
                fill="none"
                strokeDasharray={`${(quality.overall_score / 100) * 226} 226`}
                strokeLinecap="round"
              />
            </svg>
          </div>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">{tierDescriptions[tier]}</p>
      </div>

      {/* Dimensions */}
      <div className="px-6 py-4">
        <h4 className="text-sm font-medium text-foreground mb-4">
          Quality Dimensions
        </h4>
        <div className="space-y-4">
          {dimensions.map(({ key, dim }) => (
            <div key={key}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-foreground flex items-center gap-1">
                  {getDimensionName(key)}
                  {key === 'reconciliation' && (
                    <span title="Reconciliation score is a proxy for bank authorisation status">
                      <Info className="w-3 h-3 text-muted-foreground" />
                    </span>
                  )}
                </span>
                <span className="text-sm font-medium text-foreground">
                  {Math.round(dim.score)}%
                </span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className={cn('h-2 rounded-full', getDimensionColor(dim.score))}
                  style={{ width: `${dim.score}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {dim.details || getDimensionDescription(key)}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Issue Summary */}
      {totalIssues > 0 && (
        <div className="px-6 py-4 border-t border-border bg-muted rounded-b-lg">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-status-warning" />
            <span className="text-sm text-foreground">
              {totalIssues} issue{totalIssues !== 1 ? 's' : ''} found
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {quality.issue_counts.critical > 0 && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-status-danger/10 text-status-danger">
                {quality.issue_counts.critical} critical
              </span>
            )}
            {quality.issue_counts.error > 0 && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-status-danger/10 text-status-danger">
                {quality.issue_counts.error} error
              </span>
            )}
            {quality.issue_counts.warning > 0 && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-status-warning/10 text-status-warning">
                {quality.issue_counts.warning} warning
              </span>
            )}
            {quality.issue_counts.info > 0 && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary">
                {quality.issue_counts.info} info
              </span>
            )}
          </div>
        </div>
      )}

      {/* Last calculated */}
      {quality.last_checked_at && (
        <div className="px-6 py-3 border-t border-border text-xs text-muted-foreground">
          Last calculated:{' '}
          {new Date(quality.last_checked_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}

export default QualityScoreCard;
