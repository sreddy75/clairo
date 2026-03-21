'use client';

/**
 * A2UI Progress Component
 * Progress indicator with optional label
 */

import { Progress as ShadcnProgress } from '@/components/ui/progress';
import type { ProgressProps } from '@/lib/a2ui/types';


// =============================================================================
// Types
// =============================================================================

interface A2UIProgressProps extends ProgressProps {
  id: string;
  dataBinding?: string;
}

// =============================================================================
// Component
// =============================================================================

export function ProgressIndicator({
  id,
  value,
  max = 100,
  label,
  showPercent = true,
}: A2UIProgressProps) {
  const percentage = Math.round((value / max) * 100);

  return (
    <div id={id} className="space-y-2">
      {(label || showPercent) && (
        <div className="flex items-center justify-between text-sm">
          {label && <span className="text-muted-foreground">{label}</span>}
          {showPercent && (
            <span className="font-medium">{percentage}%</span>
          )}
        </div>
      )}
      <ShadcnProgress
        value={percentage}
        className="h-2"
        aria-label={label || `Progress: ${percentage}%`}
      />
    </div>
  );
}
