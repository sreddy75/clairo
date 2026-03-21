'use client';

import { useAuth } from '@clerk/nextjs';
import { Calendar, ChevronDown, Loader2, StickyNote, User, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { createActionItem } from '@/lib/api/action-items';
import { listTenantUsers, type TenantUser } from '@/lib/api/users';
import { cn } from '@/lib/utils';
import type { ActionItem, ActionItemPriority } from '@/types/action-items';
import { PRIORITY_CONFIG } from '@/types/action-items';

interface CreateActionItemModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (actionItem: ActionItem) => void;
}

const priorityOptions: ActionItemPriority[] = ['urgent', 'high', 'medium', 'low'];

export function CreateActionItemModal({
  isOpen,
  onClose,
  onSuccess,
}: CreateActionItemModalProps) {
  const { getToken, userId } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);

  // Form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [notes, setNotes] = useState('');
  const [priority, setPriority] = useState<ActionItemPriority>('medium');
  const [dueDate, setDueDate] = useState('');
  const [assignedToUserId, setAssignedToUserId] = useState('');

  // Fetch users on modal open
  const fetchUsers = useCallback(async () => {
    setIsLoadingUsers(true);
    try {
      const token = await getToken();
      if (!token) return;
      const response = await listTenantUsers(token);
      setUsers(response.users);
    } catch (err) {
      console.error('Failed to fetch users:', err);
    } finally {
      setIsLoadingUsers(false);
    }
  }, [getToken]);

  useEffect(() => {
    if (isOpen) {
      fetchUsers();
      // Reset form when modal opens
      setTitle('');
      setDescription('');
      setNotes('');
      setPriority('medium');
      setDueDate('');
      setAssignedToUserId('');
      setError(null);
    }
  }, [isOpen, fetchUsers]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    setIsSubmitting(true);

    try {
      const token = await getToken();
      if (!token) {
        setError('Not authenticated');
        return;
      }

      // Find selected user's name
      const selectedUser = users.find((u) => u.clerk_id === assignedToUserId);

      const actionItem = await createActionItem(token, {
        title: title.trim(),
        description: description.trim() || undefined,
        notes: notes.trim() || undefined,
        priority,
        due_date: dueDate || undefined,
        assigned_to_user_id: assignedToUserId || undefined,
        assigned_to_name: selectedUser?.email || undefined,
      });

      onSuccess?.(actionItem);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create action item');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-lg rounded-xl bg-card p-6 shadow-xl">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              New Action Item
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Create a new task to track
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Title */}
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">
              Title <span className="text-status-danger">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              placeholder="What needs to be done?"
              className="w-full rounded-lg border border-border bg-card text-foreground px-3 py-2 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20"
            />
          </div>

          {/* Description */}
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Add more details..."
              className="w-full rounded-lg border border-border bg-card text-foreground px-3 py-2 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20"
            />
          </div>

          {/* Priority and Due Date row */}
          <div className="grid grid-cols-2 gap-4">
            {/* Priority */}
            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">
                Priority
              </label>
              <div className="relative">
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as ActionItemPriority)}
                  className="w-full appearance-none rounded-lg border border-border bg-card text-foreground px-3 py-2 pr-8 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20"
                >
                  {priorityOptions.map((p) => (
                    <option key={p} value={p}>
                      {PRIORITY_CONFIG[p].label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              </div>
            </div>

            {/* Due Date */}
            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">
                <Calendar className="mr-1 inline h-4 w-4" />
                Due Date
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full rounded-lg border border-border bg-card text-foreground px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20"
              />
            </div>
          </div>

          {/* Assignee */}
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">
              <User className="mr-1 inline h-4 w-4" />
              Assign To
            </label>
            <div className="relative">
              <select
                value={assignedToUserId}
                onChange={(e) => setAssignedToUserId(e.target.value)}
                disabled={isLoadingUsers}
                className="w-full appearance-none rounded-lg border border-border bg-card text-foreground px-3 py-2 pr-8 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20 disabled:bg-muted"
              >
                <option value="">Unassigned</option>
                {users.map((user) => (
                  <option key={user.id} value={user.clerk_id}>
                    {user.email}
                    {user.clerk_id === userId ? ' (Me)' : ''}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">
              <StickyNote className="mr-1 inline h-4 w-4" />
              Notes (internal)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Add any internal notes..."
              className="w-full rounded-lg border border-border bg-card text-foreground px-3 py-2 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20"
            />
          </div>

          {/* Error message */}
          {error && (
            <div className="rounded-lg border border-status-danger/20 bg-status-danger/10 p-3 text-sm text-status-danger">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !title.trim()}
              className={cn(
                'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors',
                'bg-primary hover:bg-primary/90 disabled:bg-muted disabled:cursor-not-allowed'
              )}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Action Item'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
