'use client';

/**
 * A2UI StatCard Component
 * Displays a key metric with optional change indicator
 */

import { ArrowDown, ArrowUp, Minus } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import type { StatCardProps } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UIStatCardProps extends StatCardProps {
  id: string;
  dataBinding?: string;
}

// =============================================================================
// Component
// =============================================================================

export function StatCard({ id, label, value, change, icon }: A2UIStatCardProps) {
  const formattedValue =
    typeof value === 'number'
      ? value.toLocaleString('en-AU', {
          style: value >= 1000 ? 'decimal' : undefined,
          maximumFractionDigits: 2,
        })
      : value;

  return (
    <Card id={id} className="overflow-hidden">
      <CardContent className="p-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-xs font-medium text-muted-foreground">{label}</p>
            <p className="text-lg font-semibold">{formattedValue}</p>
          </div>
          {icon && (
            <div className="rounded-full bg-muted p-1.5 text-xs text-muted-foreground">
              {icon}
            </div>
          )}
        </div>

        {change && (
          <div className="mt-1 flex items-center gap-1.5">
            <div
              className={cn(
                'flex items-center gap-0.5 text-xs',
                change.direction === 'up' && 'text-status-success',
                change.direction === 'down' && 'text-status-danger',
                change.direction === 'neutral' && 'text-muted-foreground'
              )}
            >
              {change.direction === 'up' && <ArrowUp className="h-3 w-3" />}
              {change.direction === 'down' && <ArrowDown className="h-3 w-3" />}
              {change.direction === 'neutral' && <Minus className="h-3 w-3" />}
              <span>{change.value > 0 ? '+' : ''}{change.value}%</span>
            </div>
            {change.label && (
              <span className="text-xs text-muted-foreground">{change.label}</span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
