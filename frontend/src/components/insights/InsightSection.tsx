'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';

import type { Insight } from '@/types/insights';

import { InsightCard } from './InsightCard';
import type { Bucket } from './insights-utils';

interface InsightSectionProps {
  bucket: Bucket;
  insights: Insight[];
  defaultOpen?: boolean;
  onSelect: (insight: Insight) => void;
  onAction: (insightId: string, action: 'view' | 'action' | 'dismiss') => void;
  onConvert: (insight: Insight) => void;
}

const SECTION_CONFIG: Record<
  Bucket,
  { label: string; emptyMessage: string; accent?: string }
> = {
  urgent: {
    label: 'Needs Action Now',
    emptyMessage: 'Nothing urgent right now.',
    accent: 'border-l-status-danger',
  },
  review: {
    label: 'Review',
    emptyMessage: 'No items to review.',
  },
  later: {
    label: 'For Later',
    emptyMessage: 'Nothing deferred.',
  },
  handled: {
    label: 'Already Handled',
    emptyMessage: 'No actioned items yet.',
  },
};

export function InsightSection({
  bucket,
  insights,
  defaultOpen = true,
  onSelect,
  onAction,
  onConvert,
}: InsightSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const config = SECTION_CONFIG[bucket];
  const isCompact = bucket === 'handled';
  const hasAccent = bucket === 'urgent' && insights.length > 0;

  return (
    <div
      className={`rounded-xl border border-border overflow-hidden ${
        hasAccent ? 'border-l-4 border-l-status-danger' : ''
      }`}
    >
      {/* Section header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-muted hover:bg-muted/80 transition-colors"
      >
        <div className="flex items-center gap-2">
          <motion.div
            animate={{ rotate: isOpen ? 0 : -90 }}
            transition={{ duration: 0.15 }}
          >
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          </motion.div>
          <span className="text-sm font-semibold text-foreground">
            {config.label}
          </span>
          <span className="text-xs font-medium text-muted-foreground bg-muted rounded-full px-2 py-0.5">
            {insights.length}
          </span>
        </div>
      </button>

      {/* Collapsible content */}
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="p-3 space-y-2">
              {insights.length === 0 ? (
                <p className="text-sm text-muted-foreground px-2 py-3">
                  {config.emptyMessage}
                </p>
              ) : (
                insights.map((insight) => (
                  <InsightCard
                    key={insight.id}
                    insight={insight}
                    compact={isCompact}
                    onSelect={onSelect}
                    onAction={onAction}
                    onConvert={onConvert}
                  />
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
