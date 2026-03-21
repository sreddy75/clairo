'use client';

/**
 * A2UI ActionButton Component
 * Button that triggers A2UI actions
 */

import { Loader2 } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionButtonProps, ActionConfig } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UIActionButtonProps extends ActionButtonProps {
  id: string;
  dataBinding?: string;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Icon Mapping (common icons)
// =============================================================================

const iconMap: Record<string, React.ReactNode> = {
  // Add common Lucide icons here as needed
  // 'arrow-right': <ArrowRight className="h-4 w-4" />,
};

// =============================================================================
// Component
// =============================================================================

export function ActionButton({
  id,
  label,
  action,
  variant = 'default',
  icon,
  disabled = false,
  onAction,
}: A2UIActionButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const handleClick = async () => {
    if (disabled || isLoading) return;

    setIsLoading(true);
    try {
      await handleAction(action);
    } finally {
      setIsLoading(false);
    }
  };

  // Map variant to Button variant
  const buttonVariant = {
    default: 'default',
    secondary: 'secondary',
    outline: 'outline',
    ghost: 'ghost',
    destructive: 'destructive',
  }[variant] as 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive';

  const buttonClassName = cn(
    'gap-2',
    buttonVariant === 'default' &&
      'bg-primary text-primary-foreground hover:bg-primary/90',
    buttonVariant === 'secondary' &&
      'bg-muted text-foreground hover:bg-muted/80',
    buttonVariant === 'outline' &&
      'border-border text-foreground hover:bg-muted'
  );

  return (
    <Button
      id={id}
      variant={buttonVariant}
      disabled={disabled || isLoading}
      onClick={handleClick}
      className={buttonClassName}
    >
      {isLoading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        icon && iconMap[icon]
      )}
      {label}
    </Button>
  );
}
