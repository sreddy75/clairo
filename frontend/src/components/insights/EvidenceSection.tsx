'use client';

/**
 * EvidenceSection Component
 *
 * Renders a collapsible section showing evidence items that back
 * an AI-generated insight option. Collapsed by default, shows
 * a count indicator. Expands to show evidence grouped by category.
 */

import {
  BarChart3,
  ChevronDown,
  Clock,
  DollarSign,
  FileText,
  TrendingUp,
} from 'lucide-react';
import { useState } from 'react';

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { EvidenceCategory, EvidenceItem } from '@/types/insights';

interface EvidenceSectionProps {
  evidence: EvidenceItem[];
}

const categoryConfig: Record<
  EvidenceCategory,
  { label: string; icon: typeof DollarSign; color: string }
> = {
  financial: {
    label: 'Financial',
    icon: DollarSign,
    color: 'text-status-success',
  },
  aging: {
    label: 'Receivables / Payables',
    icon: Clock,
    color: 'text-status-warning',
  },
  gst: {
    label: 'GST',
    icon: FileText,
    color: 'text-primary',
  },
  quality: {
    label: 'Data Quality',
    icon: BarChart3,
    color: 'text-accent-foreground',
  },
  trend: {
    label: 'Trends',
    icon: TrendingUp,
    color: 'text-primary',
  },
};

function groupByCategory(items: EvidenceItem[]): Record<string, EvidenceItem[]> {
  const groups: Record<string, EvidenceItem[]> = {};
  for (const item of items) {
    const key = item.category || 'financial';
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
  }
  return groups;
}

export function EvidenceSection({ evidence }: EvidenceSectionProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (!evidence || evidence.length === 0) {
    return (
      <div className="mt-3 pt-3 border-t border-border">
        <p className="text-xs text-muted-foreground italic">
          No evidence data available
        </p>
      </div>
    );
  }

  const grouped = groupByCategory(evidence);
  const categoryKeys = Object.keys(grouped) as EvidenceCategory[];

  return (
    <div className="mt-3 pt-3 border-t border-border">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger className="flex w-full items-center gap-2 text-left group">
          <ChevronDown
            className={cn(
              'h-3.5 w-3.5 text-muted-foreground transition-transform duration-200',
              isOpen && 'rotate-180'
            )}
          />
          <span className="text-xs font-medium text-muted-foreground group-hover:text-foreground transition-colors">
            {evidence.length} data point{evidence.length !== 1 ? 's' : ''}
          </span>
        </CollapsibleTrigger>

        <CollapsibleContent className="mt-2">
          <div className="space-y-2">
            {categoryKeys.map((category) => {
              const config = categoryConfig[category] || categoryConfig.financial;
              const Icon = config.icon;
              const items = grouped[category] || [];

              return (
                <div key={category}>
                  <div className="flex items-center gap-1.5 mb-1">
                    <Icon className={cn('h-3 w-3', config.color)} />
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {config.label}
                    </span>
                  </div>
                  <div className="space-y-0.5 pl-4">
                    {items.map((item, idx) => (
                      <div
                        key={idx}
                        className="text-xs text-muted-foreground leading-relaxed"
                      >
                        <span className="text-muted-foreground/70">
                          {item.source}
                          {item.period ? ` · ${item.period}` : ''}
                          {' — '}
                        </span>
                        <span className="font-medium text-foreground">
                          {item.metric}: {item.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

export default EvidenceSection;
