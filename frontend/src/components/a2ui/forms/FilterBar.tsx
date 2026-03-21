'use client';

/**
 * A2UI FilterBar Component
 * Dynamic filter controls for data filtering
 */

import { Filter, X } from 'lucide-react';
import { useCallback, useState } from 'react';


import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig } from '@/lib/a2ui/types';

// =============================================================================
// Types
// =============================================================================

interface FilterOption {
  value: string;
  label: string;
}

interface LocalFilterConfig {
  key: string;
  label: string;
  type: 'select' | 'text' | 'dateRange';
  placeholder?: string;
  options?: FilterOption[];
}

interface A2UIFilterBarProps {
  id: string;
  filters?: LocalFilterConfig[];
  onFilterChange?: ActionConfig;
  dataBinding?: string;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Component
// =============================================================================

export function FilterBar({
  id,
  filters,
  onFilterChange,
  onAction,
}: A2UIFilterBarProps) {
  const [filterValues, setFilterValues] = useState<Record<string, string | string[]>>({});
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const updateFilter = useCallback(
    (key: string, value: string | string[]) => {
      const newValues = { ...filterValues, [key]: value };
      setFilterValues(newValues);

      if (onFilterChange) {
        handleAction({
          ...onFilterChange,
          payload: { ...onFilterChange.payload, filters: newValues },
        });
      }
    },
    [filterValues, onFilterChange, handleAction]
  );

  const clearFilter = useCallback(
    (key: string) => {
      const newValues = { ...filterValues };
      delete newValues[key];
      setFilterValues(newValues);

      if (onFilterChange) {
        handleAction({
          ...onFilterChange,
          payload: { ...onFilterChange.payload, filters: newValues },
        });
      }
    },
    [filterValues, onFilterChange, handleAction]
  );

  const clearAllFilters = useCallback(() => {
    setFilterValues({});
    if (onFilterChange) {
      handleAction({
        ...onFilterChange,
        payload: { ...onFilterChange.payload, filters: {} },
      });
    }
  }, [onFilterChange, handleAction]);

  const renderFilter = (filter: LocalFilterConfig) => {
    const value = filterValues[filter.key];

    switch (filter.type) {
      case 'select':
        return (
          <Select
            value={value as string}
            onValueChange={(v) => updateFilter(filter.key, v)}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder={filter.placeholder || filter.label} />
            </SelectTrigger>
            <SelectContent>
              {filter.options?.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );

      case 'text':
        return (
          <Input
            placeholder={filter.placeholder || filter.label}
            value={(value as string) || ''}
            onChange={(e) => updateFilter(filter.key, e.target.value)}
            className="w-[200px]"
          />
        );

      case 'dateRange':
        return (
          <div className="flex items-center gap-2">
            <Input
              type="date"
              value={(value as string[])?.[0] || ''}
              onChange={(e) =>
                updateFilter(filter.key, [e.target.value, (value as string[])?.[1] || ''])
              }
              className="w-[140px]"
            />
            <span className="text-muted-foreground">to</span>
            <Input
              type="date"
              value={(value as string[])?.[1] || ''}
              onChange={(e) =>
                updateFilter(filter.key, [(value as string[])?.[0] || '', e.target.value])
              }
              className="w-[140px]"
            />
          </div>
        );

      default:
        return null;
    }
  };

  const activeFilters = Object.entries(filterValues).filter(
    ([, v]) => v && (Array.isArray(v) ? v.some(Boolean) : true)
  );

  return (
    <div id={id} className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Filter className="h-4 w-4" />
          <span>Filters</span>
        </div>

        {filters?.map((filter) => (
          <div key={filter.key}>{renderFilter(filter)}</div>
        ))}

        {activeFilters.length > 0 && (
          <Button variant="ghost" size="sm" onClick={clearAllFilters}>
            Clear all
          </Button>
        )}
      </div>

      {activeFilters.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {activeFilters.map(([key, value]) => {
            const filter = filters?.find((f) => f.key === key);
            const displayValue = Array.isArray(value) ? value.join(' - ') : value;
            return (
              <Badge key={key} variant="secondary" className="gap-1">
                <span className="text-muted-foreground">{filter?.label}:</span>
                <span>{displayValue}</span>
                <button
                  onClick={() => clearFilter(key)}
                  className="ml-1 hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            );
          })}
        </div>
      )}
    </div>
  );
}
