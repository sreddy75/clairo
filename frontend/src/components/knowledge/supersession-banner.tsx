'use client';

/**
 * SupersessionBanner Component
 *
 * Displays a yellow/amber warning banner when a knowledge chat response
 * references superseded content (rulings or legislation). The banner is
 * expandable to show individual warning strings describing which content
 * has been superseded and what replaced it.
 */

import { AlertTriangle, ChevronDown } from 'lucide-react';
import { useState } from 'react';

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

interface SupersessionBannerProps {
  /** Array of supersession warning strings */
  warnings: string[];
  /** Additional CSS classes */
  className?: string;
}

// =============================================================================
// Component
// =============================================================================

export function SupersessionBanner({ warnings, className }: SupersessionBannerProps) {
  const [expanded, setExpanded] = useState(false);

  // Do not render when there are no warnings
  if (!warnings || warnings.length === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        'rounded-lg border border-status-warning/30 bg-status-warning/10',
        className,
      )}
    >
      <Collapsible open={expanded} onOpenChange={setExpanded}>
        <CollapsibleTrigger className="flex w-full items-start gap-2.5 p-3 text-left group">
          <AlertTriangle className="w-4 h-4 text-status-warning shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-status-warning">
              Note: Some referenced content has been superseded.
            </p>
          </div>
          <ChevronDown
            className={cn(
              'w-4 h-4 text-status-warning shrink-0 mt-0.5 transition-transform duration-200',
              expanded && 'rotate-180',
            )}
          />
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="px-3 pb-3 ml-6.5">
            <ul className="space-y-1.5 ml-[26px]">
              {warnings.map((warning, index) => (
                <li
                  key={index}
                  className="text-xs text-status-warning leading-relaxed list-disc"
                >
                  {warning}
                </li>
              ))}
            </ul>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

export default SupersessionBanner;
