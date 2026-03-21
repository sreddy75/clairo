'use client';

/**
 * Action Items Page
 *
 * A curated list of tasks converted from AI-generated insights.
 * Supports filtering by status, priority, and assignment.
 */

import { useAuth } from '@clerk/nextjs';
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  ListChecks,
  Plus,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import {
  ActionItemCard,
  ActionItemFiltersBar,
  CreateActionItemModal,
  QuickFilterTabs,
} from '@/components/action-items';
import type { ActionItemFilters } from '@/components/action-items';
import {
  cancelActionItem,
  completeActionItem,
  deleteActionItem,
  getActionItemStats,
  listActionItems,
  startActionItem,
} from '@/lib/api/action-items';
import type { ActionItem, ActionItemStats } from '@/types/action-items';

type QuickFilterTab = 'all' | 'urgent' | 'overdue' | 'mine';

export default function ActionItemsPage() {
  const { getToken, userId } = useAuth();

  // Data state
  const [items, setItems] = useState<ActionItem[]>([]);
  const [stats, setStats] = useState<ActionItemStats | null>(null);
  const [total, setTotal] = useState(0);

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Filter state
  const [activeTab, setActiveTab] = useState<QuickFilterTab>('all');
  const [filters, setFilters] = useState<ActionItemFilters>({
    status: [],
    priority: [],
    includeCompleted: false,
  });

  // Pagination
  const [page, setPage] = useState(1);
  const limit = 20;

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const data = await getActionItemStats(token);
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  }, [getToken]);

  // Fetch items
  const fetchItems = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const token = await getToken();
      if (!token) {
        setError('Not authenticated');
        return;
      }

      // Build filter params based on active tab and filters
      const params: Record<string, unknown> = {
        limit,
        offset: (page - 1) * limit,
        include_completed: filters.includeCompleted,
      };

      // Apply quick filter tab
      if (activeTab === 'urgent') {
        params.priority = ['urgent'];
      } else if (activeTab === 'mine' && userId) {
        params.assigned_to_user_id = userId;
      }
      // Note: 'overdue' is handled client-side since API doesn't have overdue filter

      // Apply detailed filters
      if (filters.status.length > 0) {
        params.status = filters.status;
      }
      if (filters.priority.length > 0 && activeTab !== 'urgent') {
        params.priority = filters.priority;
      }

      const response = await listActionItems(
        token,
        params as Parameters<typeof listActionItems>[1]
      );

      // Filter overdue items if needed (client-side)
      let filteredItems = response.items;
      if (activeTab === 'overdue') {
        filteredItems = response.items.filter((item) => item.is_overdue);
      }

      setItems(filteredItems);
      setTotal(activeTab === 'overdue' ? filteredItems.length : response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load action items');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, page, activeTab, filters, userId]);

  // Initial load
  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Fetch items when filters change
  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [activeTab, filters]);

  // Action handlers
  const handleStart = async (id: string) => {
    try {
      const token = await getToken();
      if (!token) return;

      await startActionItem(token, id);
      await fetchItems();
      await fetchStats();
    } catch (err) {
      console.error('Failed to start item:', err);
    }
  };

  const handleComplete = async (id: string) => {
    try {
      const token = await getToken();
      if (!token) return;

      await completeActionItem(token, id);
      await fetchItems();
      await fetchStats();
    } catch (err) {
      console.error('Failed to complete item:', err);
    }
  };

  const handleCancel = async (id: string) => {
    try {
      const token = await getToken();
      if (!token) return;

      await cancelActionItem(token, id);
      await fetchItems();
      await fetchStats();
    } catch (err) {
      console.error('Failed to cancel item:', err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this action item?')) {
      return;
    }
    try {
      const token = await getToken();
      if (!token) return;

      await deleteActionItem(token, id);
      await fetchItems();
      await fetchStats();
    } catch (err) {
      console.error('Failed to delete item:', err);
    }
  };

  // Pagination
  const totalPages = Math.ceil(total / limit);

  // Count for quick filter tabs
  const tabCounts = stats
    ? {
        all: stats.pending + stats.in_progress,
        urgent: stats.urgent,
        overdue: stats.overdue,
        mine: undefined, // Would need separate API call
      }
    : undefined;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Action Items</h1>
          <p className="text-sm text-muted-foreground">
            Track and manage tasks from AI-generated insights
          </p>
        </div>

        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Action Item
        </button>
      </div>

      <div>
        {/* Stats Summary */}
        {stats && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm font-medium text-muted-foreground">Pending</p>
              <p className="mt-1 text-2xl font-bold text-foreground tabular-nums">{stats.pending}</p>
            </div>
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm font-medium text-muted-foreground">In Progress</p>
              <p className="mt-1 text-2xl font-bold text-status-info tabular-nums">{stats.in_progress}</p>
            </div>
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm font-medium text-muted-foreground">Overdue</p>
              <p className="mt-1 text-2xl font-bold text-status-danger tabular-nums">{stats.overdue}</p>
            </div>
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm font-medium text-muted-foreground">Completed</p>
              <p className="mt-1 text-2xl font-bold text-status-success tabular-nums">{stats.completed}</p>
            </div>
          </div>
        )}

        {/* Quick Filter Tabs */}
        <div className="mb-4">
          <QuickFilterTabs
            activeTab={activeTab}
            onChange={setActiveTab}
            counts={tabCounts}
          />
        </div>

        {/* Detailed Filters */}
        <div className="mb-6 rounded-xl border border-border bg-card p-4">
          <ActionItemFiltersBar filters={filters} onChange={setFilters} />
        </div>

        {/* Error State */}
        {error && (
          <div className="mb-6 rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-3">
              <span className="h-2 w-2 rounded-full bg-status-danger" />
              <div>
                <p className="font-medium text-foreground">Error loading action items</p>
                <p className="text-sm text-status-danger">{error}</p>
              </div>
              <button
                onClick={fetchItems}
                className="ml-auto text-sm text-muted-foreground underline hover:text-foreground"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="rounded-xl border border-border bg-card p-12 text-center">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
            <p className="mt-2 text-muted-foreground">Loading action items...</p>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && items.length === 0 && (
          <div className="rounded-xl border border-border bg-card p-12 text-center">
            <ListChecks className="mx-auto h-12 w-12 text-muted-foreground/30" />
            <h3 className="mt-4 text-lg font-medium text-foreground">No action items</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {activeTab === 'all' && !filters.status.length && !filters.priority.length
                ? 'Convert insights to action items to see them here'
                : 'No items match your current filters'}
            </p>
            {(activeTab !== 'all' || filters.status.length > 0 || filters.priority.length > 0) && (
              <button
                onClick={() => {
                  setActiveTab('all');
                  setFilters({ status: [], priority: [], includeCompleted: false });
                }}
                className="mt-4 text-sm text-primary hover:text-primary/80"
              >
                Clear filters
              </button>
            )}
          </div>
        )}

        {/* Action Items List */}
        {!isLoading && !error && items.length > 0 && (
          <>
            <div className="space-y-3">
              {items.map((item) => (
                <ActionItemCard
                  key={item.id}
                  item={item}
                  onStart={handleStart}
                  onComplete={handleComplete}
                  onCancel={handleCancel}
                  onDelete={handleDelete}
                />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-6 flex items-center justify-between rounded-xl border border-border bg-card px-4 py-3">
                <p className="text-sm text-muted-foreground">
                  Showing {(page - 1) * limit + 1} - {Math.min(page * limit, total)} of {total}{' '}
                  items
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(page - 1)}
                    disabled={page === 1}
                    className="rounded p-1 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 text-muted-foreground"
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>
                  <span className="text-sm text-muted-foreground">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={page === totalPages}
                    className="rounded p-1 hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 text-muted-foreground"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {/* Completed Section (if showing completed) */}
        {!isLoading && filters.includeCompleted && stats && stats.completed > 0 && (
          <div className="mt-8">
            <div className="mb-4 flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-status-success" />
              <h2 className="text-lg font-medium text-foreground">
                Completed ({stats.completed})
              </h2>
            </div>
            {/* Completed items are included in the main list when filter is enabled */}
          </div>
        )}
      </div>

      {/* Create Action Item Modal */}
      <CreateActionItemModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={() => {
          fetchItems();
          fetchStats();
        }}
      />
    </div>
  );
}
