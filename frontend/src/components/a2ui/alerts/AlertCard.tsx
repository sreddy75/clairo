'use client';

/**
 * A2UI AlertCard Component
 * Displays alerts with severity-based styling
 */

import { AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig, AlertCardProps } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UIAlertCardProps extends AlertCardProps {
  id: string;
  dataBinding?: string;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Severity Configuration
// =============================================================================

const severityConfig = {
  info: {
    icon: Info,
    variant: 'default' as const,
    className: 'border-primary/50 bg-primary/10 text-foreground',
    iconClassName: 'text-primary',
  },
  warning: {
    icon: AlertTriangle,
    variant: 'default' as const,
    className: 'border-status-warning/50 bg-status-warning/10 text-foreground',
    iconClassName: 'text-status-warning',
  },
  error: {
    icon: AlertCircle,
    variant: 'destructive' as const,
    className: 'border-status-danger/50 bg-status-danger/10 text-foreground',
    iconClassName: 'text-status-danger',
  },
  success: {
    icon: CheckCircle2,
    variant: 'default' as const,
    className: 'border-status-success/50 bg-status-success/10 text-foreground',
    iconClassName: 'text-status-success',
  },
};

// =============================================================================
// Component
// =============================================================================

export function AlertCard({
  id,
  severity = 'info',
  title,
  description,
  actions,
  onAction,
}: A2UIAlertCardProps) {
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const config = severityConfig[severity];
  const Icon = config.icon;

  return (
    <Alert
      id={id}
      variant={config.variant}
      className={cn('relative', config.className)}
      role="alert"
      aria-live={severity === 'error' ? 'assertive' : 'polite'}
    >
      <Icon className={cn('h-4 w-4', config.iconClassName)} aria-hidden="true" />
      <AlertTitle className="font-semibold">{title}</AlertTitle>
      {description && (
        <AlertDescription className="mt-1 text-sm opacity-90">
          {description}
        </AlertDescription>
      )}
      {actions && actions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {actions.map((action, index) => (
            <Button
              key={index}
              variant={severity === 'error' ? 'destructive' : 'outline'}
              size="sm"
              onClick={() => handleAction(action)}
              className={cn(
                severity !== 'error' && 'border-current/30 hover:bg-current/10'
              )}
            >
              {action.target?.split('/').pop() || 'Action'}
            </Button>
          ))}
        </div>
      )}
    </Alert>
  );
}
