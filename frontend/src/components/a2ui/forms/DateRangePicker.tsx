'use client';

/**
 * A2UI DateRangePicker Component
 * Date range selection input
 */

import { CalendarIcon } from 'lucide-react';
import { useState } from 'react';
import type { DateRange } from 'react-day-picker';

import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Label } from '@/components/ui/label';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

interface A2UIDateRangePickerProps {
  id: string;
  label?: string;
  startDate?: string;
  endDate?: string;
  minDate?: string;
  maxDate?: string;
  disabled?: boolean;
  onChange?: ActionConfig;
  dataBinding?: string;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Helpers
// =============================================================================

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

// =============================================================================
// Component
// =============================================================================

export function DateRangePicker({
  id,
  label,
  startDate,
  endDate,
  minDate,
  maxDate,
  disabled = false,
  onChange,
  onAction,
}: A2UIDateRangePickerProps) {
  const [range, setRange] = useState<DateRange>({
    from: startDate ? new Date(startDate) : undefined,
    to: endDate ? new Date(endDate) : undefined,
  });
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const handleSelect = (newRange: DateRange | undefined) => {
    if (!newRange) return;

    setRange(newRange);

    if (onChange && newRange.from && newRange.to) {
      handleAction({
        ...onChange,
        payload: {
          ...onChange.payload,
          startDate: newRange.from.toISOString(),
          endDate: newRange.to.toISOString(),
        },
      });
    }
  };

  const displayValue = range.from
    ? range.to
      ? `${formatDate(range.from)} - ${formatDate(range.to)}`
      : formatDate(range.from)
    : 'Select date range';

  return (
    <div id={id} className="space-y-2">
      {label && <Label>{label}</Label>}
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            disabled={disabled}
            className={cn(
              'w-full justify-start text-left font-normal',
              !range.from && 'text-muted-foreground'
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4" />
            {displayValue}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="range"
            selected={range}
            onSelect={handleSelect}
            disabled={(date) => {
              if (minDate && date < new Date(minDate)) return true;
              if (maxDate && date > new Date(maxDate)) return true;
              return false;
            }}
            numberOfMonths={2}
            initialFocus
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}
