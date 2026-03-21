'use client';

/**
 * A2UI Tooltip Component
 * Informational tooltip on hover
 */

import {
  Tooltip as ShadcnTooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';


// =============================================================================
// Types
// =============================================================================

interface A2UITooltipProps {
  id: string;
  content?: string;
  position?: 'top' | 'right' | 'bottom' | 'left';
  dataBinding?: string;
  children?: React.ReactNode;
}

// =============================================================================
// Component
// =============================================================================

export function A2UITooltip({
  id,
  content,
  position = 'top',
  children,
}: A2UITooltipProps) {
  const sideMap: Record<string, 'top' | 'right' | 'bottom' | 'left'> = {
    top: 'top',
    right: 'right',
    bottom: 'bottom',
    left: 'left',
  };

  return (
    <TooltipProvider>
      <ShadcnTooltip>
        <TooltipTrigger asChild>
          <span id={id} className="inline-block">
            {children || (
              <button
                type="button"
                className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-muted text-xs text-muted-foreground hover:bg-muted/80"
              >
                ?
              </button>
            )}
          </span>
        </TooltipTrigger>
        <TooltipContent side={sideMap[position] || 'top'}>
          <p className="max-w-xs text-sm">{content}</p>
        </TooltipContent>
      </ShadcnTooltip>
    </TooltipProvider>
  );
}
