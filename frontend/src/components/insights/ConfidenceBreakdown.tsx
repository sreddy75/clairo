'use client';

/**
 * ConfidenceBreakdown Component
 *
 * Displays a confidence score badge with an interactive popover
 * showing the breakdown factors that compose the score.
 */

import { Info } from 'lucide-react';
import { useState } from 'react';

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';

interface ConfidenceBreakdownData {
  data_completeness: number;
  data_freshness: number;
  knowledge_match: number;
  perspective_coverage: number;
}

interface ConfidenceBreakdownProps {
  confidence: number;
  breakdown?: ConfidenceBreakdownData | null;
  className?: string;
}

const FACTORS = [
  { key: 'data_completeness' as const, label: 'Data Completeness', weight: '40%', description: 'How much financial data was available' },
  { key: 'data_freshness' as const, label: 'Data Freshness', weight: '25%', description: 'How recently the data was synced' },
  { key: 'knowledge_match' as const, label: 'Knowledge Match', weight: '20%', description: 'Relevant compliance/advisory content found' },
  { key: 'perspective_coverage' as const, label: 'Perspective Coverage', weight: '15%', description: 'Number of analysis perspectives used' },
];

function getConfidenceTier(score: number): 'high' | 'medium' | 'low' {
  if (score >= 0.7) return 'high';
  if (score >= 0.4) return 'medium';
  return 'low';
}

const TIER_STYLES = {
  high: 'bg-status-success/10 text-status-success border-status-success/20',
  medium: 'bg-status-warning/10 text-status-warning border-status-warning/20',
  low: 'bg-status-danger/10 text-status-danger border-status-danger/20',
};

const BAR_COLORS = {
  high: 'bg-status-success',
  medium: 'bg-status-warning',
  low: 'bg-status-danger',
};

export function ConfidenceBreakdown({ confidence, breakdown, className }: ConfidenceBreakdownProps) {
  const [open, setOpen] = useState(false);
  const tier = getConfidenceTier(confidence);
  const pct = Math.round(confidence * 100);

  // No breakdown available (legacy insights) — show badge only
  if (!breakdown) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
          TIER_STYLES[tier],
          className,
        )}
      >
        {pct}% confidence
      </span>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          className={cn(
            'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium cursor-pointer hover:opacity-80 transition-opacity',
            TIER_STYLES[tier],
            className,
          )}
        >
          {pct}% confidence
          <Info className="w-3 h-3 opacity-60" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="start"
        className="w-72 p-4 bg-card border border-border"
      >
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-foreground">
              Confidence Breakdown
            </p>
            <span className={cn('text-xs font-bold', tier === 'high' ? 'text-status-success' : tier === 'medium' ? 'text-status-warning' : 'text-status-danger')}>
              {pct}%
            </span>
          </div>
          <div className="space-y-2.5">
            {FACTORS.map((factor) => {
              const value = breakdown[factor.key];
              const factorTier = getConfidenceTier(value);
              return (
                <div key={factor.key}>
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs text-foreground">
                      {factor.label}
                      <span className="text-muted-foreground ml-1">({factor.weight})</span>
                    </span>
                    <span className="text-xs font-medium text-foreground">
                      {Math.round(value * 100)}%
                    </span>
                  </div>
                  <div className="w-full bg-muted rounded-full h-1.5">
                    <div
                      className={cn('h-1.5 rounded-full', BAR_COLORS[factorTier])}
                      style={{ width: `${Math.round(value * 100)}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {factor.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export default ConfidenceBreakdown;
