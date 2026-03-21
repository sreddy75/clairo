'use client';

/**
 * Trigger Form Modal
 *
 * Modal for creating and editing triggers with dynamic config fields.
 * Supports all three trigger types with appropriate config options.
 */

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  Calendar,
  Database,
  Loader2,
  Sparkles,
  X,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import { createTrigger, updateTrigger } from '@/lib/api/triggers';
import type {
  Trigger,
  TriggerCreate,
  TriggerType,
  TriggerUpdate,
} from '@/types/triggers';

// Available analyzers
const ANALYZERS = [
  { id: 'cash_flow', label: 'Cash Flow Analysis', description: 'Analyzes cash position & trends' },
  { id: 'quality', label: 'Data Quality', description: 'Checks for reconciliation issues' },
  { id: 'compliance', label: 'Compliance', description: 'BAS deadlines & GST status' },
];

// Data threshold metrics
const DATA_METRICS = [
  { id: 'bank_balance', label: 'Bank Balance', unit: '$' },
  { id: 'overdue_receivables', label: 'Overdue Receivables', unit: '$' },
  { id: 'overdue_payables', label: 'Overdue Payables', unit: '$' },
  { id: 'annual_turnover', label: 'Annual Turnover', unit: '$' },
  { id: 'unreconciled_count', label: 'Unreconciled Transactions', unit: '' },
  { id: 'expense_change_pct', label: 'Expense Change %', unit: '%' },
];

// Operators
const OPERATORS = [
  { id: 'gt', label: 'Greater than', symbol: '>' },
  { id: 'gte', label: 'Greater than or equal', symbol: '>=' },
  { id: 'lt', label: 'Less than', symbol: '<' },
  { id: 'lte', label: 'Less than or equal', symbol: '<=' },
  { id: 'eq', label: 'Equal to', symbol: '=' },
];

// Event types
const EVENT_TYPES = [
  { id: 'xero_connection_created', label: 'New Xero Connection', description: 'When a new client connects Xero' },
  { id: 'xero_sync_complete', label: 'Xero Sync Complete', description: 'After data sync finishes' },
  { id: 'bas_lodged', label: 'BAS Lodged', description: 'When BAS is marked as lodged' },
];

// Preset templates
const TEMPLATES = [
  {
    id: 'cash_crisis',
    name: 'Cash Crisis Alert',
    description: 'Alert when bank balance drops below threshold',
    trigger_type: 'data_threshold' as TriggerType,
    config: { metric: 'bank_balance', operator: 'lt', threshold: 10000 },
    target_analyzers: ['cash_flow'],
    dedup_window_hours: 168,
  },
  {
    id: 'large_payables',
    name: 'Large Overdue Payables',
    description: 'Flag clients with significant overdue bills',
    trigger_type: 'data_threshold' as TriggerType,
    config: { metric: 'overdue_payables', operator: 'gt', threshold: 50000 },
    target_analyzers: ['cash_flow'],
    dedup_window_hours: 168,
  },
  {
    id: 'gst_threshold',
    name: 'GST Registration Alert',
    description: 'Notify when turnover approaches GST threshold',
    trigger_type: 'data_threshold' as TriggerType,
    config: { metric: 'annual_turnover', operator: 'gte', threshold: 75000 },
    target_analyzers: ['compliance'],
    dedup_window_hours: 720,
  },
  {
    id: 'bas_reminder',
    name: 'BAS Deadline Reminder',
    description: 'Review clients before BAS deadline',
    trigger_type: 'time_scheduled' as TriggerType,
    config: { cron: '0 9 * * 1', timezone: 'Australia/Sydney', days_before_deadline: 14 },
    target_analyzers: ['compliance', 'quality'],
    dedup_window_hours: 168,
  },
  {
    id: 'monthly_review',
    name: 'Monthly Health Check',
    description: 'Run full analysis on 1st of each month',
    trigger_type: 'time_scheduled' as TriggerType,
    config: { cron: '0 8 1 * *', timezone: 'Australia/Sydney' },
    target_analyzers: ['cash_flow', 'quality', 'compliance'],
    dedup_window_hours: 168,
  },
  {
    id: 'new_client',
    name: 'New Client Onboarding',
    description: 'Run quality check when new client connects',
    trigger_type: 'event_based' as TriggerType,
    config: { event: 'xero_connection_created' },
    target_analyzers: ['quality', 'compliance'],
    dedup_window_hours: 0,
  },
];

interface TriggerFormModalProps {
  trigger?: Trigger | null;
  onClose: () => void;
  onSuccess: () => void;
}

export function TriggerFormModal({
  trigger,
  onClose,
  onSuccess,
}: TriggerFormModalProps) {
  const { getToken } = useAuth();
  const isEditing = !!trigger;

  // Form state
  const [name, setName] = useState(trigger?.name || '');
  const [description, setDescription] = useState(trigger?.description || '');
  const [triggerType, setTriggerType] = useState<TriggerType>(
    trigger?.trigger_type || 'data_threshold'
  );
  const [targetAnalyzers, setTargetAnalyzers] = useState<string[]>(
    trigger?.target_analyzers || ['cash_flow']
  );
  const [dedupWindowHours, setDedupWindowHours] = useState(
    trigger?.dedup_window_hours || 168
  );

  // Data threshold config
  const [metric, setMetric] = useState('bank_balance');
  const [operator, setOperator] = useState('lt');
  const [threshold, setThreshold] = useState(10000);

  // Time scheduled config
  const [cronExpression, setCronExpression] = useState('0 9 * * 1');
  const [timezone, setTimezone] = useState('Australia/Sydney');
  const [daysBeforeDeadline, setDaysBeforeDeadline] = useState<number | null>(null);

  // Event based config
  const [eventType, setEventType] = useState('xero_sync_complete');

  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTemplates, setShowTemplates] = useState(!isEditing);

  // Load existing trigger config
  useEffect(() => {
    if (trigger?.config) {
      const config = trigger.config as Record<string, unknown>;
      if (trigger.trigger_type === 'data_threshold') {
        setMetric((config.metric as string) || 'bank_balance');
        setOperator((config.operator as string) || 'lt');
        setThreshold((config.threshold as number) || 10000);
      } else if (trigger.trigger_type === 'time_scheduled') {
        setCronExpression((config.cron as string) || '0 9 * * 1');
        setTimezone((config.timezone as string) || 'Australia/Sydney');
        setDaysBeforeDeadline((config.days_before_deadline as number) || null);
      } else if (trigger.trigger_type === 'event_based') {
        setEventType((config.event as string) || 'xero_sync_complete');
      }
    }
  }, [trigger]);

  // Apply template
  const applyTemplate = (template: typeof TEMPLATES[0]) => {
    setName(template.name);
    setDescription(template.description);
    setTriggerType(template.trigger_type);
    setTargetAnalyzers(template.target_analyzers);
    setDedupWindowHours(template.dedup_window_hours);

    const config = template.config as Record<string, unknown>;
    if (template.trigger_type === 'data_threshold') {
      setMetric(config.metric as string);
      setOperator(config.operator as string);
      setThreshold(config.threshold as number);
    } else if (template.trigger_type === 'time_scheduled') {
      setCronExpression(config.cron as string);
      setTimezone(config.timezone as string);
      setDaysBeforeDeadline((config.days_before_deadline as number) || null);
    } else if (template.trigger_type === 'event_based') {
      setEventType(config.event as string);
    }

    setShowTemplates(false);
  };

  // Toggle analyzer
  const toggleAnalyzer = (id: string) => {
    setTargetAnalyzers((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  };

  // Build config object
  const buildConfig = (): Record<string, unknown> => {
    if (triggerType === 'data_threshold') {
      return { metric, operator, threshold };
    } else if (triggerType === 'time_scheduled') {
      const config: Record<string, unknown> = { cron: cronExpression, timezone };
      if (daysBeforeDeadline !== null) {
        config.days_before_deadline = daysBeforeDeadline;
      }
      return config;
    } else {
      return { event: eventType };
    }
  };

  // Submit form
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('Name is required');
      return;
    }

    if (targetAnalyzers.length === 0) {
      setError('Select at least one analyzer');
      return;
    }

    try {
      setIsSubmitting(true);
      const token = await getToken();
      if (!token) {
        setError('Not authenticated');
        return;
      }

      if (isEditing && trigger) {
        const updateData: TriggerUpdate = {
          name: name.trim(),
          description: description.trim() || undefined,
          config: buildConfig(),
          target_analyzers: targetAnalyzers,
          dedup_window_hours: dedupWindowHours,
        };
        await updateTrigger(token, trigger.id, updateData);
      } else {
        const createData: TriggerCreate = {
          name: name.trim(),
          description: description.trim() || undefined,
          trigger_type: triggerType,
          config: buildConfig(),
          target_analyzers: targetAnalyzers,
          dedup_window_hours: dedupWindowHours,
        };
        await createTrigger(token, createData);
      }

      onSuccess();
    } catch (err) {
      console.error('Failed to save trigger:', err);
      setError('Failed to save trigger. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl bg-white shadow-xl">
        {/* Header */}
        <div className="sticky top-0 flex items-center justify-between border-b border-border bg-white px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">
                {isEditing ? 'Edit Trigger' : 'Create Trigger'}
              </h2>
              <p className="text-sm text-muted-foreground">
                {isEditing
                  ? 'Modify trigger configuration'
                  : 'Set up automated insight generation'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Templates (only for new triggers) */}
        {showTemplates && !isEditing && (
          <div className="border-b border-border bg-muted px-6 py-4">
            <h3 className="text-sm font-medium text-foreground mb-3">
              Start from a template
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {TEMPLATES.map((template) => (
                <button
                  key={template.id}
                  onClick={() => applyTemplate(template)}
                  className="flex items-start gap-3 rounded-lg border border-border bg-white p-3 text-left hover:border-primary/30 hover:bg-primary/5 transition-colors"
                >
                  <div className="mt-0.5">
                    {template.trigger_type === 'data_threshold' && (
                      <Database className="h-4 w-4 text-primary" />
                    )}
                    {template.trigger_type === 'time_scheduled' && (
                      <Calendar className="h-4 w-4 text-primary" />
                    )}
                    {template.trigger_type === 'event_based' && (
                      <Zap className="h-4 w-4 text-status-warning" />
                    )}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-foreground">
                      {template.name}
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {template.description}
                    </div>
                  </div>
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowTemplates(false)}
              className="mt-3 text-sm text-primary hover:text-primary/80"
            >
              Or create from scratch
            </button>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Basic Info */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Trigger Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Cash Flow Alert"
                className="w-full rounded-lg border border-border px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Description (optional)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What does this trigger do?"
                rows={2}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>

          {/* Trigger Type */}
          {!isEditing && (
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Trigger Type
              </label>
              <div className="grid grid-cols-3 gap-3">
                <button
                  type="button"
                  onClick={() => setTriggerType('data_threshold')}
                  className={`flex flex-col items-center gap-2 rounded-lg border p-4 transition-colors ${
                    triggerType === 'data_threshold'
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border hover:border-border'
                  }`}
                >
                  <Database className="h-5 w-5" />
                  <span className="text-sm font-medium">Data Threshold</span>
                  <span className="text-xs text-center text-muted-foreground">
                    When metrics cross limits
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setTriggerType('time_scheduled')}
                  className={`flex flex-col items-center gap-2 rounded-lg border p-4 transition-colors ${
                    triggerType === 'time_scheduled'
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border hover:border-border'
                  }`}
                >
                  <Calendar className="h-5 w-5" />
                  <span className="text-sm font-medium">Scheduled</span>
                  <span className="text-xs text-center text-muted-foreground">
                    Run on a schedule
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setTriggerType('event_based')}
                  className={`flex flex-col items-center gap-2 rounded-lg border p-4 transition-colors ${
                    triggerType === 'event_based'
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border hover:border-border'
                  }`}
                >
                  <Zap className="h-5 w-5" />
                  <span className="text-sm font-medium">Event-Based</span>
                  <span className="text-xs text-center text-muted-foreground">
                    React to events
                  </span>
                </button>
              </div>
            </div>
          )}

          {/* Type-specific Config */}
          <div className="rounded-lg border border-border bg-muted p-4">
            <h4 className="text-sm font-medium text-foreground mb-4">
              {triggerType === 'data_threshold' && 'Threshold Configuration'}
              {triggerType === 'time_scheduled' && 'Schedule Configuration'}
              {triggerType === 'event_based' && 'Event Configuration'}
            </h4>

            {triggerType === 'data_threshold' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">
                    Metric
                  </label>
                  <select
                    value={metric}
                    onChange={(e) => setMetric(e.target.value)}
                    className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm focus:border-ring focus:outline-none"
                  >
                    {DATA_METRICS.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-muted-foreground mb-1">
                      Condition
                    </label>
                    <select
                      value={operator}
                      onChange={(e) => setOperator(e.target.value)}
                      className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm focus:border-ring focus:outline-none"
                    >
                      {OPERATORS.map((op) => (
                        <option key={op.id} value={op.id}>
                          {op.label} ({op.symbol})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm text-muted-foreground mb-1">
                      Threshold
                    </label>
                    <div className="relative">
                      {DATA_METRICS.find((m) => m.id === metric)?.unit === '$' && (
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                          $
                        </span>
                      )}
                      <input
                        type="number"
                        value={threshold}
                        onChange={(e) => setThreshold(Number(e.target.value))}
                        className={`w-full rounded-lg border border-border py-2 text-sm focus:border-ring focus:outline-none ${
                          DATA_METRICS.find((m) => m.id === metric)?.unit === '$'
                            ? 'pl-7 pr-3'
                            : 'px-3'
                        }`}
                      />
                      {DATA_METRICS.find((m) => m.id === metric)?.unit === '%' && (
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                          %
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <p className="text-xs text-muted-foreground bg-white rounded p-2 border border-border">
                  Trigger will fire when{' '}
                  <strong>{DATA_METRICS.find((m) => m.id === metric)?.label}</strong>{' '}
                  is {OPERATORS.find((o) => o.id === operator)?.label.toLowerCase()}{' '}
                  <strong>
                    {DATA_METRICS.find((m) => m.id === metric)?.unit === '$' && '$'}
                    {threshold.toLocaleString()}
                    {DATA_METRICS.find((m) => m.id === metric)?.unit === '%' && '%'}
                  </strong>
                </p>
              </div>
            )}

            {triggerType === 'time_scheduled' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-muted-foreground mb-1">
                    Schedule (Cron Expression)
                  </label>
                  <input
                    type="text"
                    value={cronExpression}
                    onChange={(e) => setCronExpression(e.target.value)}
                    placeholder="0 9 * * 1"
                    className="w-full rounded-lg border border-border px-3 py-2 text-sm font-mono focus:border-ring focus:outline-none"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Format: minute hour day month weekday (e.g., &quot;0 9 * * 1&quot; = 9am every Monday)
                  </p>
                </div>

                <div>
                  <label className="block text-sm text-muted-foreground mb-1">
                    Timezone
                  </label>
                  <select
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm focus:border-ring focus:outline-none"
                  >
                    <option value="Australia/Sydney">Australia/Sydney (AEST/AEDT)</option>
                    <option value="Australia/Melbourne">Australia/Melbourne</option>
                    <option value="Australia/Brisbane">Australia/Brisbane</option>
                    <option value="Australia/Perth">Australia/Perth (AWST)</option>
                    <option value="Australia/Adelaide">Australia/Adelaide (ACST)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-muted-foreground mb-1">
                    Days Before BAS Deadline (optional)
                  </label>
                  <input
                    type="number"
                    value={daysBeforeDeadline ?? ''}
                    onChange={(e) =>
                      setDaysBeforeDeadline(e.target.value ? Number(e.target.value) : null)
                    }
                    placeholder="e.g., 14"
                    className="w-full rounded-lg border border-border px-3 py-2 text-sm focus:border-ring focus:outline-none"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    If set, only runs for clients with BAS due within this many days
                  </p>
                </div>
              </div>
            )}

            {triggerType === 'event_based' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-muted-foreground mb-2">
                    Event Type
                  </label>
                  <div className="space-y-2">
                    {EVENT_TYPES.map((event) => (
                      <label
                        key={event.id}
                        className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                          eventType === event.id
                            ? 'border-primary bg-primary/10'
                            : 'border-border hover:border-border'
                        }`}
                      >
                        <input
                          type="radio"
                          name="eventType"
                          value={event.id}
                          checked={eventType === event.id}
                          onChange={(e) => setEventType(e.target.value)}
                          className="mt-1"
                        />
                        <div>
                          <div className="text-sm font-medium text-foreground">
                            {event.label}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {event.description}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Target Analyzers */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Target Analyzers
            </label>
            <p className="text-xs text-muted-foreground mb-3">
              Select which analysis to run when this trigger fires
            </p>
            <div className="space-y-2">
              {ANALYZERS.map((analyzer) => (
                <label
                  key={analyzer.id}
                  className={`flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    targetAnalyzers.includes(analyzer.id)
                      ? 'border-primary bg-primary/10'
                      : 'border-border hover:border-border'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={targetAnalyzers.includes(analyzer.id)}
                    onChange={() => toggleAnalyzer(analyzer.id)}
                    className="rounded border-border text-primary focus:ring-ring"
                  />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-foreground">
                      {analyzer.label}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {analyzer.description}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Dedup Window */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              Deduplication Window (hours)
            </label>
            <p className="text-xs text-muted-foreground mb-2">
              Prevent duplicate alerts for the same client within this period
            </p>
            <select
              value={dedupWindowHours}
              onChange={(e) => setDedupWindowHours(Number(e.target.value))}
              className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm focus:border-ring focus:outline-none"
            >
              <option value={0}>No deduplication (always fire)</option>
              <option value={24}>24 hours (1 day)</option>
              <option value={72}>72 hours (3 days)</option>
              <option value={168}>168 hours (1 week)</option>
              <option value={336}>336 hours (2 weeks)</option>
              <option value={720}>720 hours (30 days)</option>
            </select>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-foreground hover:bg-muted rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary-foreground bg-primary hover:bg-primary/90 rounded-lg disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  {isEditing ? 'Save Changes' : 'Create Trigger'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
