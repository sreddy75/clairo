'use client';

/**
 * A2UI ApprovalBar Component
 * Action bar for approval/rejection workflows
 */

import { Check, Loader2, X } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useA2UIAction } from '@/lib/a2ui/context';
import type { ActionConfig } from '@/lib/a2ui/types';
import { cn } from '@/lib/utils';


// =============================================================================
// Types
// =============================================================================

interface A2UIApprovalBarProps {
  id: string;
  approveLabel?: string;
  rejectLabel?: string;
  requireComment?: boolean;
  onApprove?: ActionConfig;
  onReject?: ActionConfig;
  dataBinding?: string;
  onAction?: (action: ActionConfig) => Promise<void>;
}

// =============================================================================
// Component
// =============================================================================

export function ApprovalBar({
  id,
  approveLabel = 'Approve',
  rejectLabel = 'Reject',
  requireComment = false,
  onApprove,
  onReject,
  onAction,
}: A2UIApprovalBarProps) {
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState('');
  const [pendingAction, setPendingAction] = useState<'approve' | 'reject' | null>(null);

  const contextAction = useA2UIAction();
  const handleAction = onAction || contextAction;

  const handleApprove = async () => {
    if (requireComment && !comment.trim()) {
      setPendingAction('approve');
      setShowComment(true);
      return;
    }

    if (!onApprove) return;

    setIsApproving(true);
    try {
      await handleAction({
        ...onApprove,
        payload: { ...onApprove.payload, comment: comment.trim() || undefined },
      });
    } finally {
      setIsApproving(false);
      setComment('');
      setShowComment(false);
    }
  };

  const handleReject = async () => {
    if (requireComment && !comment.trim()) {
      setPendingAction('reject');
      setShowComment(true);
      return;
    }

    if (!onReject) return;

    setIsRejecting(true);
    try {
      await handleAction({
        ...onReject,
        payload: { ...onReject.payload, comment: comment.trim() || undefined },
      });
    } finally {
      setIsRejecting(false);
      setComment('');
      setShowComment(false);
    }
  };

  const submitWithComment = async () => {
    if (pendingAction === 'approve') {
      await handleApprove();
    } else if (pendingAction === 'reject') {
      await handleReject();
    }
  };

  const cancelComment = () => {
    setShowComment(false);
    setComment('');
    setPendingAction(null);
  };

  return (
    <div
      id={id}
      className={cn(
        'sticky bottom-0 border-t bg-card border-border p-4',
        showComment && 'space-y-4'
      )}
    >
      {showComment && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">
            {pendingAction === 'reject' ? 'Rejection reason' : 'Comment'}
            {requireComment && <span className="text-status-danger">*</span>}
          </label>
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={
              pendingAction === 'reject'
                ? 'Please provide a reason for rejection...'
                : 'Add an optional comment...'
            }
            rows={3}
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={cancelComment}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={submitWithComment}
              disabled={requireComment && !comment.trim()}
            >
              Submit
            </Button>
          </div>
        </div>
      )}

      {!showComment && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Review the information above and approve or reject.
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleReject}
              disabled={isApproving || isRejecting}
              className="gap-2 border-border text-foreground hover:bg-muted"
            >
              {isRejecting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <X className="h-4 w-4" />
              )}
              {rejectLabel}
            </Button>
            <Button
              onClick={handleApprove}
              disabled={isApproving || isRejecting}
              className="gap-2 bg-status-success hover:bg-status-success/90 text-white"
            >
              {isApproving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              {approveLabel}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
