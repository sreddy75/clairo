'use client';

/**
 * A2UI Checkbox Component
 * Checkbox input with label
 */

import { useState } from 'react';

import { Checkbox as ShadcnCheckbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig } from '@/lib/a2ui/types';


// =============================================================================
// Types
// =============================================================================

interface A2UICheckboxProps {
  id: string;
  label?: string;
  checked?: boolean;
  disabled?: boolean;
  description?: string;
  onChange?: ActionConfig;
  dataBinding?: string;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Component
// =============================================================================

export function A2UICheckbox({
  id,
  label,
  checked: initialChecked = false,
  disabled = false,
  description,
  onChange,
  onAction,
}: A2UICheckboxProps) {
  const [checked, setChecked] = useState(initialChecked);
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const handleChange = (newChecked: boolean) => {
    setChecked(newChecked);

    if (onChange) {
      handleAction({
        ...onChange,
        payload: { ...onChange.payload, checked: newChecked },
      });
    }
  };

  return (
    <div id={id} className="flex items-start gap-3">
      <ShadcnCheckbox
        id={`${id}-checkbox`}
        checked={checked}
        onCheckedChange={handleChange}
        disabled={disabled}
        aria-describedby={description ? `${id}-description` : undefined}
      />
      <div className="grid gap-1.5 leading-none">
        {label && (
          <Label
            htmlFor={`${id}-checkbox`}
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            {label}
          </Label>
        )}
        {description && (
          <p id={`${id}-description`} className="text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
    </div>
  );
}
