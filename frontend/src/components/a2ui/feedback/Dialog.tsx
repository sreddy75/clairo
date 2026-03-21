'use client';

/**
 * A2UI Dialog Component
 * Modal dialog for confirmations and forms
 */

import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog as ShadcnDialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig } from '@/lib/a2ui/types';


// =============================================================================
// Types
// =============================================================================

interface A2UIDialogProps {
  id: string;
  title?: string;
  description?: string;
  open?: boolean;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'destructive';
  onConfirm?: ActionConfig;
  onCancel?: ActionConfig;
  dataBinding?: string;
  children?: React.ReactNode;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Component
// =============================================================================

export function A2UIDialog({
  id,
  title,
  description,
  open: initialOpen = false,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  onConfirm,
  onCancel,
  children,
  onAction,
}: A2UIDialogProps) {
  const [open, setOpen] = useState(initialOpen);
  const [isLoading, setIsLoading] = useState(false);
  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const handleConfirm = async () => {
    if (!onConfirm) {
      setOpen(false);
      return;
    }

    setIsLoading(true);
    try {
      await handleAction(onConfirm);
      setOpen(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async () => {
    if (onCancel) {
      await handleAction(onCancel);
    }
    setOpen(false);
  };

  const confirmVariant = variant === 'destructive' ? 'destructive' : 'default';

  return (
    <ShadcnDialog open={open} onOpenChange={setOpen}>
      <DialogContent id={id}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {children && <div className="py-4">{children}</div>}
        <DialogFooter>
          <Button variant="outline" onClick={handleCancel} disabled={isLoading}>
            {cancelLabel}
          </Button>
          <Button
            variant={confirmVariant}
            onClick={handleConfirm}
            disabled={isLoading}
          >
            {isLoading ? 'Loading...' : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </ShadcnDialog>
  );
}
