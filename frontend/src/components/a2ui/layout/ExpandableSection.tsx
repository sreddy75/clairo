'use client';

/**
 * A2UI ExpandableSection Component
 * Single collapsible section with optional icon
 */

import { ChevronDown } from 'lucide-react';
import { useState } from 'react';

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import type { ExpandableSectionProps } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UIExpandableSectionProps extends ExpandableSectionProps {
  id: string;
  dataBinding?: string;
  children?: React.ReactNode;
}

// =============================================================================
// Component
// =============================================================================

export function A2UIExpandableSection({
  id,
  title,
  description,
  defaultExpanded = false,
  children,
}: A2UIExpandableSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultExpanded);

  return (
    <Collapsible id={id} open={isOpen} onOpenChange={setIsOpen} className="w-full">
      <CollapsibleTrigger className="flex w-full items-center justify-between rounded-lg border bg-card p-4 text-left hover:bg-accent/50 transition-colors">
        <div className="space-y-1">
          <h3 className="font-medium text-sm">{title}</h3>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
        </div>
        <ChevronDown
          className={cn(
            'h-4 w-4 text-muted-foreground transition-transform duration-200',
            isOpen && 'rotate-180'
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-2">
        <div className="rounded-lg border bg-card/50 p-4">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  );
}
