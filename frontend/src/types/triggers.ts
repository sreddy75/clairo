/**
 * Trigger types for the triggers management system
 */

export type TriggerType = 'data_threshold' | 'time_scheduled' | 'event_based';
export type TriggerStatus = 'active' | 'disabled' | 'error';

export interface Trigger {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  trigger_type: TriggerType;
  config: Record<string, unknown>;
  target_analyzers: string[];
  dedup_window_hours: number;
  status: TriggerStatus;
  is_system_default: boolean;
  last_executed_at: string | null;
  last_error: string | null;
  consecutive_failures: number;
  created_at: string;
  updated_at: string;
  // Computed fields
  executions_24h: number | null;
  insights_24h: number | null;
}

export interface TriggerCreate {
  name: string;
  description?: string;
  trigger_type: TriggerType;
  config: Record<string, unknown>;
  target_analyzers: string[];
  dedup_window_hours?: number;
}

export interface TriggerUpdate {
  name?: string;
  description?: string;
  config?: Record<string, unknown>;
  target_analyzers?: string[];
  dedup_window_hours?: number;
  status?: TriggerStatus;
}

export interface TriggerListResponse {
  items: Trigger[];
  total: number;
  limit: number;
  offset: number;
}

export interface TriggerExecution {
  id: string;
  trigger_id: string;
  tenant_id: string;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  status: 'running' | 'success' | 'failed' | 'partial';
  clients_evaluated: number;
  insights_created: number;
  insights_deduplicated: number;
  error_message: string | null;
  trigger_name: string | null;
}

export interface TriggerExecutionListResponse {
  items: TriggerExecution[];
  total: number;
  limit: number;
  offset: number;
}

// Config type helpers
export interface DataThresholdConfig {
  metric: string;
  operator: 'gt' | 'gte' | 'lt' | 'lte' | 'eq';
  threshold: number;
}

export interface TimeScheduledConfig {
  cron: string;
  timezone: string;
  days_before_deadline?: number;
}

export interface EventBasedConfig {
  event: string;
  conditions?: Record<string, unknown>;
}
