'use client';

/**
 * A2UI TextInput Component
 * Text input field with validation support
 */

import { useCallback, useState } from 'react';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

interface ValidationConfig {
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  message?: string;
}

interface A2UITextInputProps {
  id: string;
  label?: string;
  placeholder?: string;
  value?: string;
  required?: boolean;
  disabled?: boolean;
  validation?: ValidationConfig;
  onChange?: ActionConfig;
  dataBinding?: string;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Component
// =============================================================================

export function TextInput({
  id,
  label,
  placeholder,
  value: initialValue = '',
  required = false,
  disabled = false,
  validation,
  onChange,
  onAction,
}: A2UITextInputProps) {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const validate = useCallback(
    (val: string): string | null => {
      if (required && !val.trim()) {
        return 'This field is required';
      }
      if (validation?.minLength && val.length < validation.minLength) {
        return `Minimum ${validation.minLength} characters required`;
      }
      if (validation?.maxLength && val.length > validation.maxLength) {
        return `Maximum ${validation.maxLength} characters allowed`;
      }
      if (validation?.pattern && !new RegExp(validation.pattern).test(val)) {
        return validation.message || 'Invalid format';
      }
      return null;
    },
    [required, validation]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = e.target.value;
      setValue(newValue);

      if (touched) {
        setError(validate(newValue));
      }

      if (onChange) {
        handleAction({
          ...onChange,
          payload: { ...onChange.payload, value: newValue },
        });
      }
    },
    [touched, validate, onChange, handleAction]
  );

  const handleBlur = useCallback(() => {
    setTouched(true);
    setError(validate(value));
  }, [value, validate]);

  return (
    <div id={id} className="space-y-2">
      {label && (
        <Label htmlFor={`${id}-input`} className={cn(error && 'text-destructive')}>
          {label}
          {required && <span className="text-destructive ml-1">*</span>}
        </Label>
      )}
      <Input
        id={`${id}-input`}
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        className={cn(error && 'border-destructive focus-visible:ring-destructive')}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      {error && (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
