'use client';

/**
 * A2UI SelectField Component
 * Dropdown select field
 */

import { useState } from 'react';

import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface A2UISelectFieldProps {
  id: string;
  label?: string;
  options: SelectOption[];
  value?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  onChange?: ActionConfig;
  dataBinding?: string;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Component
// =============================================================================

export function SelectField({
  id,
  label,
  options,
  value: initialValue,
  placeholder = 'Select an option',
  required = false,
  disabled = false,
  onChange,
  onAction,
}: A2UISelectFieldProps) {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const handleChange = (newValue: string) => {
    setValue(newValue);
    setError(null);

    if (onChange) {
      handleAction({
        ...onChange,
        payload: { ...onChange.payload, value: newValue },
      });
    }
  };

  const handleOpenChange = (open: boolean) => {
    if (!open && required && !value) {
      setError('Please select an option');
    }
  };

  return (
    <div id={id} className="space-y-2">
      {label && (
        <Label className={cn(error && 'text-destructive')}>
          {label}
          {required && <span className="text-destructive ml-1">*</span>}
        </Label>
      )}
      <Select
        value={value}
        onValueChange={handleChange}
        onOpenChange={handleOpenChange}
        disabled={disabled}
      >
        <SelectTrigger
          className={cn(error && 'border-destructive focus:ring-destructive')}
          aria-invalid={!!error}
        >
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem
              key={option.value}
              value={option.value}
              disabled={option.disabled}
            >
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
