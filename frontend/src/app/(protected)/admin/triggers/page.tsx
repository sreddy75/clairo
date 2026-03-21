'use client';

/**
 * Triggers Management Page
 *
 * Admin interface for managing automated insight triggers.
 * Allows viewing, enabling/disabling, and monitoring trigger executions.
 */

import { useAuth } from '@clerk/nextjs';
import {
  AlertTriangle,
  Calendar,
  Clock,
  Database,
  Edit3,
  Loader2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { TriggerFormModal } from '@/components/triggers/TriggerFormModal';
import {
  deleteTrigger,
  disableTrigger,
  enableTrigger,
  getTriggerExecutions,
  listTriggers,
  seedDefaultTriggers,
} from '@/lib/api/triggers';
import { formatRelativeTime } from '@/lib/formatters';
import type {
  Trigger,
  TriggerExecution,
  TriggerStatus,
  TriggerType,
} from '@/types/triggers';

// Get trigger type icon and color
function getTriggerTypeInfo(type: TriggerType): {
  icon: React.ReactNode;
  label: string;
  dotColor: string;
} {
  switch (type) {
    case 'data_threshold':
      return {
        icon: <Database className="h-4 w-4" />,
        label: 'Data Threshold',
        dotColor: 'bg-status-info',
      };
    case 'time_scheduled':
      return {
        icon: <Calendar className="h-4 w-4" />,
        label: 'Scheduled',
        dotColor: 'bg-status-warning',
      };
    case 'event_based':
      return {
        icon: <Zap className="h-4 w-4" />,
        label: 'Event',
        dotColor: 'bg-status-neutral',
      };
  }
}

// Get status badge
function getStatusBadge(status: TriggerStatus): React.ReactNode {
  const dotColor = status === 'active' ? 'bg-status-success' : status === 'error' ? 'bg-status-danger' : 'bg-status-neutral';
  const label = status === 'active' ? 'Active' : status === 'error' ? 'Error' : 'Disabled';
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
      <span className="text-muted-foreground">{label}</span>
    </span>
  );
}

export default function TriggersPage() {
  const { getToken } = useAuth();

  // Data state
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [executions, setExecutions] = useState<TriggerExecution[]>([]);

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSeeding, setIsSeeding] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'triggers' | 'executions'>(
    'triggers'
  );

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingTrigger, setEditingTrigger] = useState<Trigger | null>(null);

  // Fetch triggers
  const fetchTriggers = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const token = await getToken();
      if (!token) {
        setError('Not authenticated');
        return;
      }

      const response = await listTriggers(token);
      setTriggers(response.items);
    } catch (err) {
      console.error('Failed to fetch triggers:', err);
      setError('Failed to load triggers');
    } finally {
      setIsLoading(false);
    }
  }, [getToken]);

  // Fetch executions
  const fetchExecutions = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const response = await getTriggerExecutions(token, undefined, 20);
      setExecutions(response.items);
    } catch (err) {
      console.error('Failed to fetch executions:', err);
    }
  }, [getToken]);

  // Toggle trigger status
  const handleToggle = async (trigger: Trigger) => {
    try {
      setTogglingId(trigger.id);
      const token = await getToken();
      if (!token) return;

      if (trigger.status === 'active') {
        await disableTrigger(token, trigger.id);
      } else {
        await enableTrigger(token, trigger.id);
      }

      await fetchTriggers();
    } catch (err) {
      console.error('Failed to toggle trigger:', err);
      setError('Failed to update trigger');
    } finally {
      setTogglingId(null);
    }
  };

  // Seed default triggers
  const handleSeedDefaults = async () => {
    try {
      setIsSeeding(true);
      const token = await getToken();
      if (!token) return;

      await seedDefaultTriggers(token);
      await fetchTriggers();
    } catch (err) {
      console.error('Failed to seed triggers:', err);
      setError('Failed to seed default triggers');
    } finally {
      setIsSeeding(false);
    }
  };

  // Open create modal
  const handleCreate = () => {
    setEditingTrigger(null);
    setShowModal(true);
  };

  // Open edit modal
  const handleEdit = (trigger: Trigger) => {
    setEditingTrigger(trigger);
    setShowModal(true);
  };

  // Handle modal close
  const handleModalClose = () => {
    setShowModal(false);
    setEditingTrigger(null);
  };

  // Handle modal success
  const handleModalSuccess = () => {
    setShowModal(false);
    setEditingTrigger(null);
    fetchTriggers();
  };

  // Delete trigger
  const handleDelete = async (trigger: Trigger) => {
    if (trigger.is_system_default) {
      setError('Cannot delete system default triggers. Disable instead.');
      return;
    }

    if (!confirm(`Delete trigger "${trigger.name}"? This cannot be undone.`)) {
      return;
    }

    try {
      setDeletingId(trigger.id);
      const token = await getToken();
      if (!token) return;

      await deleteTrigger(token, trigger.id);
      await fetchTriggers();
    } catch (err) {
      console.error('Failed to delete trigger:', err);
      setError('Failed to delete trigger');
    } finally {
      setDeletingId(null);
    }
  };

  // Initial load
  useEffect(() => {
    fetchTriggers();
    fetchExecutions();
  }, [fetchTriggers, fetchExecutions]);

  // Stats
  const stats = {
    total: triggers.length,
    active: triggers.filter((t) => t.status === 'active').length,
    disabled: triggers.filter((t) => t.status === 'disabled').length,
    error: triggers.filter((t) => t.status === 'error').length,
    insights24h: triggers.reduce((sum, t) => sum + (t.insights_24h || 0), 0),
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Trigger Management
          </h1>
          <p className="text-sm text-muted-foreground">
            Configure automated insight generation
          </p>
        </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  fetchTriggers();
                  fetchExecutions();
                }}
                className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
              >
                <RefreshCw className="h-4 w-4" />
                Refresh
              </button>
              {triggers.length === 0 && !isLoading && (
                <button
                  onClick={handleSeedDefaults}
                  disabled={isSeeding}
                  className="inline-flex items-center gap-2 rounded-lg border border-border bg-muted px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/80 disabled:opacity-50"
                >
                  {isSeeding ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  Seed Defaults
                </button>
              )}
              <button
                onClick={handleCreate}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                <Plus className="h-4 w-4" />
                Create Trigger
              </button>
            </div>
          </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Total Triggers</div>
          <div className="mt-1 text-2xl font-semibold text-foreground tabular-nums">{stats.total}</div>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Active</div>
          <div className="mt-1 text-2xl font-semibold text-status-success tabular-nums">{stats.active}</div>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Disabled</div>
          <div className="mt-1 text-2xl font-semibold text-muted-foreground tabular-nums">{stats.disabled}</div>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Error State</div>
          <div className="mt-1 text-2xl font-semibold text-status-danger tabular-nums">{stats.error}</div>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Insights (24h)</div>
          <div className="mt-1 text-2xl font-semibold text-foreground tabular-nums">{stats.insights24h}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-border">
        <nav className="-mb-px flex gap-1">
          {(['triggers', 'executions'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                activeTab === tab
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              }`}
            >
              {tab === 'triggers' ? `Triggers (${triggers.length})` : `Recent Executions (${executions.length})`}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      <div>
        {error && (
          <div className="mb-4 rounded-lg border border-border bg-card p-4 text-sm text-status-danger">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : activeTab === 'triggers' ? (
          <div className="space-y-3">
            {triggers.length === 0 ? (
              <div className="rounded-lg border border-border bg-card p-12 text-center">
                <Sparkles className="mx-auto h-12 w-12 text-muted-foreground/30" />
                <h3 className="mt-4 text-lg font-medium text-foreground">
                  No triggers configured
                </h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Click &quot;Seed Default Triggers&quot; to create the default
                  trigger configuration.
                </p>
              </div>
            ) : (
              triggers.map((trigger) => {
                const typeInfo = getTriggerTypeInfo(trigger.trigger_type);
                return (
                  <div
                    key={trigger.id}
                    className="rounded-lg border border-border bg-card p-4 transition-shadow hover:shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3">
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className={`h-1.5 w-1.5 rounded-full ${typeInfo.dotColor}`} />
                            <span className="text-muted-foreground">{typeInfo.label}</span>
                          </span>
                          {getStatusBadge(trigger.status)}
                          {trigger.is_system_default && (
                            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                              System Default
                            </span>
                          )}
                        </div>
                        <h3 className="mt-2 font-medium text-foreground">
                          {trigger.name}
                        </h3>
                        {trigger.description && (
                          <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                            {trigger.description}
                          </p>
                        )}
                        <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5" />
                            Last run: {formatRelativeTime(trigger.last_executed_at)}
                          </span>
                          <span>
                            Analyzers:{' '}
                            {trigger.target_analyzers.join(', ')}
                          </span>
                          <span>Dedup: {trigger.dedup_window_hours}h</span>
                          {trigger.executions_24h !== null && (
                            <span className="font-medium text-foreground">
                              {trigger.executions_24h} runs / {trigger.insights_24h || 0} insights (24h)
                            </span>
                          )}
                        </div>
                        {trigger.last_error && (
                          <div className="mt-2 flex items-start gap-2 rounded bg-muted p-2 text-xs text-status-danger">
                            <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                            <span className="line-clamp-2">{trigger.last_error}</span>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleEdit(trigger)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors"
                          title="Edit trigger"
                        >
                          <Edit3 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleToggle(trigger)}
                          disabled={togglingId === trigger.id}
                          className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                            trigger.status === 'active'
                              ? 'border-border bg-card text-foreground hover:bg-muted'
                              : 'border-border bg-muted text-foreground hover:bg-muted/80'
                          } disabled:opacity-50`}
                        >
                          {togglingId === trigger.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : trigger.status === 'active' ? (
                            <>
                              <Pause className="h-4 w-4" />
                              Disable
                            </>
                          ) : (
                            <>
                              <Play className="h-4 w-4" />
                              Enable
                            </>
                          )}
                        </button>
                        {!trigger.is_system_default && (
                          <button
                            onClick={() => handleDelete(trigger)}
                            disabled={deletingId === trigger.id}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-sm font-medium text-status-danger hover:bg-muted transition-colors disabled:opacity-50"
                            title="Delete trigger"
                          >
                            {deletingId === trigger.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        ) : (
          // Executions tab
          <div className="rounded-lg border border-border bg-card">
            {executions.length === 0 ? (
              <div className="p-12 text-center">
                <Clock className="mx-auto h-12 w-12 text-muted-foreground/30" />
                <h3 className="mt-4 text-lg font-medium text-foreground">
                  No recent executions
                </h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Trigger executions will appear here as they run.
                </p>
              </div>
            ) : (
              <table className="w-full">
                <thead className="border-b border-border bg-muted">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Trigger
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Started
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Duration
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Status
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Results
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {executions.map((exec) => (
                    <tr key={exec.id} className="hover:bg-muted">
                      <td className="px-4 py-3 text-sm font-medium text-foreground">
                        {exec.trigger_name || 'Unknown'}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {formatRelativeTime(exec.started_at)}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {exec.duration_ms
                          ? `${(exec.duration_ms / 1000).toFixed(1)}s`
                          : '-'}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <span className={`h-1.5 w-1.5 rounded-full ${
                            exec.status === 'success' ? 'bg-status-success' :
                            exec.status === 'failed' ? 'bg-status-danger' :
                            exec.status === 'running' ? 'bg-status-info' :
                            'bg-status-warning'
                          }`} />
                          <span className="text-muted-foreground capitalize">{exec.status}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-sm">
                        <span className="text-muted-foreground">
                          {exec.clients_evaluated} clients
                        </span>
                        <span className="mx-2 text-muted-foreground/30">·</span>
                        <span className="font-medium text-foreground">
                          {exec.insights_created} insights
                        </span>
                        {exec.insights_deduplicated > 0 && (
                          <>
                            <span className="mx-2 text-muted-foreground/30">·</span>
                            <span className="text-muted-foreground">
                              {exec.insights_deduplicated} deduped
                            </span>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <TriggerFormModal
          trigger={editingTrigger}
          onClose={handleModalClose}
          onSuccess={handleModalSuccess}
        />
      )}
    </div>
  );
}
