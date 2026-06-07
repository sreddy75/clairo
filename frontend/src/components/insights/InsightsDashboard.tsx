'use client';

import { Lightbulb, Loader2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import type { Insight } from '@/types/insights';

import { InsightDetailPanel } from './InsightDetailPanel';
import { computeCounts, groupIntoBuckets } from './insights-utils';
import type { Bucket } from './insights-utils';
import { InsightSection } from './InsightSection';
import { InsightsSummaryBar } from './InsightsSummaryBar';

interface InsightsDashboardProps {
  insights: Insight[];
  insightsLoading: boolean;
  clientName: string;
  onInsightAction: (insightId: string, action: 'view' | 'action' | 'dismiss') => void;
  onExpandInsight: (insightId: string) => void;
  onConvertInsight: (insight: Insight) => void;
  isExpandingInsight: boolean;
  selectedQuarter?: number | null;
  selectedFyYear?: number | null;
}

const BUCKET_ORDER: Bucket[] = ['urgent', 'review', 'later', 'handled'];

const BUCKET_DEFAULTS: Record<Bucket, boolean> = {
  urgent: true,
  review: true,
  later: false,
  handled: false,
};

export function InsightsDashboard({
  insights,
  insightsLoading,
  clientName,
  onInsightAction,
  onExpandInsight,
  onConvertInsight,
  isExpandingInsight,
  selectedQuarter,
  selectedFyYear,
}: InsightsDashboardProps) {
  const [selectedInsight, setSelectedInsight] = useState<Insight | null>(null);

  const buckets = useMemo(() => groupIntoBuckets(insights), [insights]);
  const counts = useMemo(() => computeCounts(insights), [insights]);

  // Keep selectedInsight in sync with insights array (handles stale references after actions)
  useEffect(() => {
    if (!selectedInsight) return;
    const current = insights.find(i => i.id === selectedInsight.id);
    if (!current) {
      setSelectedInsight(null);
    } else if (current !== selectedInsight) {
      setSelectedInsight(current);
    }
  }, [insights, selectedInsight]);

  const handleSelect = (insight: Insight) => {
    setSelectedInsight(insight);
    if (insight.status === 'new') {
      onInsightAction(insight.id, 'view');
    }
  };

  const handleDismissFromPanel = (insightId: string, action: 'view' | 'action' | 'dismiss') => {
    onInsightAction(insightId, action);
    if (action === 'dismiss') {
      setSelectedInsight(null);
    }
  };

  const handleConvertFromPanel = (insight: Insight) => {
    onConvertInsight(insight);
    setSelectedInsight(null);
  };

  const handleExpandFromPanel = (insightId: string) => {
    onExpandInsight(insightId);
  };

  if (insightsLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-amber-600" />
      </div>
    );
  }

  if (insights.length === 0) {
    return (
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            Insights for {clientName}
          </h3>
          <p className="text-sm text-muted-foreground">
            AI-powered analysis of potential issues and opportunities
          </p>
        </div>
        <div className="bg-card rounded-xl border border-border p-12 text-center">
          <Lightbulb className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-foreground mb-2">
            No Insights Yet
          </h3>
          <p className="text-muted-foreground mb-4">
            Use the <strong>Analyze</strong> button in the header to generate insights for this client.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            Insights for {clientName}
            {selectedQuarter && selectedFyYear && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                Q{selectedQuarter} FY{String(selectedFyYear).slice(-2)}
              </span>
            )}
          </h3>
          <p className="text-sm text-muted-foreground">
            AI-powered analysis of potential issues and opportunities
          </p>
        </div>
        <InsightsSummaryBar counts={counts} />
      </div>

      {/* Triage sections */}
      <div className="space-y-3">
        {BUCKET_ORDER.map((bucket) => (
          <InsightSection
            key={bucket}
            bucket={bucket}
            insights={buckets.get(bucket) || []}
            defaultOpen={BUCKET_DEFAULTS[bucket]}
            onSelect={handleSelect}
            onAction={onInsightAction}
            onConvert={onConvertInsight}
          />
        ))}
      </div>

      {/* Detail slide-over panel */}
      <InsightDetailPanel
        insight={selectedInsight}
        onClose={() => setSelectedInsight(null)}
        onAction={handleDismissFromPanel}
        onConvert={handleConvertFromPanel}
        onExpand={handleExpandFromPanel}
        isExpanding={isExpandingInsight}
      />
    </div>
  );
}
